#!/usr/bin/env python3
"""Fig. 14a (osdi/fig14/preregistration.md): OTTER's steady-state tracking inside the native StreamDiffusionV2 loop.

Upstream `streamv2v/inference.py --profile` runs unmodified. This wrapper patches, in its own process only, the method
the upstream loop calls once per chunk (`CausalStreamInferencePipeline.inference_stream`) so that after every call it runs
the exact functions OTTER runs per call in steady state with M2 + M3 tracking on (Fig. 8b OTTER configuration):
  M2  GpuRuntime.sink_track_step (mobility_node.py): Sink slot positions -> refreshed entries and ordered shifts
  M3  m3_path.gpu_track_events + LineageHistory.record: the same detection, kept as per-call lineage
bound to a stand-in that exposes the native pipeline under the attribute names those functions read (pl, sink, fsl).
Variants: `wrap` = the patch with no tracking (the wrapper's own cost), `track` = M2 + M3 tracking. `native` is
fig8_native.py unchanged. Per-chunk wall time comes from upstream's own profile log, parsed exactly as Fig. 8b.

    run   --label A --workload dog --rep 1 --variant native|wrap|track [--gpu 0]  -> osdi/fig14/native/{label}_{w}_{variant}_rep{r}.json
    entry <wrap|track> <tracking json> -- <upstream args>                       (internal: the patched upstream process)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "tools", ROOT / "tools/eval"):   # as mobility_node.py
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import fig8_native as f8  # noqa: E402

OUT_REL = "results/evaluation/osdi/fig14/native"
OUT = ROOT / OUT_REL
VARIANTS = ("native", "wrap", "track")


class NativeRT:
    """The attributes GpuRuntime.sink_track_step and m3_path.gpu_track_events read, over the native pipeline."""

    def __init__(self, pl):
        self.pl, self.sink, self.fsl = pl, int(pl.num_sink_tokens), int(pl.frame_seq_length)
        self._track = None
        import torch

        self.torch = torch

    def _sink_pos_now(self) -> list:
        return self.torch.stack([l_["pos"][:, :self.sink] for l_ in self.pl.kv_cache1]).cpu().tolist()


def entry(variant: str, rec_path: str, upstream_args: list[str]):
    import m3_path as m3
    from mobility_node import GpuRuntime
    from models.wan.causal_stream_inference import CausalStreamInferencePipeline

    stats = {"variant": variant, "calls": 0, "track_s": [], "m2_refresh_events": 0, "m3_refresh": 0, "m3_shift": 0}
    orig = CausalStreamInferencePipeline.inference_stream
    state = {}

    def patched(self, *args, **kwargs):
        out = orig(self, *args, **kwargs)
        if variant == "track":
            t0 = time.perf_counter()
            rt = state.get("rt")
            if rt is None:   # first call: the trackers start from the current positions (as M2 / M3 start at a version)
                rt = state["rt"] = NativeRT(self)
                rt.sink_track_step = types.MethodType(GpuRuntime.sink_track_step, rt)
                GpuRuntime.sink_track_start(rt, {"native": True})
                state["hist"] = m3.LineageHistory(stats["calls"])
                state["last"] = m3.gpu_track_events(rt, None)[0]
            else:
                rt.sink_track_step(stats["calls"])
                state["last"], ref, sh = m3.gpu_track_events(rt, state["last"])
                state["hist"].record(stats["calls"], ref, sh)
            stats["track_s"].append(time.perf_counter() - t0)
        stats["calls"] += 1
        return out

    CausalStreamInferencePipeline.inference_stream = patched
    sys.argv = ["streamv2v/inference.py", *upstream_args]
    sys.path.insert(0, str(ROOT / "streamv2v"))   # as `python streamv2v/inference.py` sets sys.path[0]
    import runpy

    try:
        runpy.run_path(str(ROOT / "streamv2v/inference.py"), run_name="__main__")
    finally:
        if variant == "track" and state.get("rt") is not None:
            tr = state["rt"]._track
            stats["m2_refresh_events"] = tr["refresh_events"]
            stats["m2_distinct_refreshed"] = len(tr["refreshed"])
            stats["m3_refresh"], stats["m3_shift"] = state["hist"].n_refresh, state["hist"].n_shift
        Path(rec_path).write_text(json.dumps(stats))


def run(a):
    video, info = f8.prepare(a.workload)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{a.label}_{a.workload}_{a.variant}_rep{a.rep}"
    log, trk = OUT / f"{tag}.log", OUT / f"{tag}.tracking.json"
    up = ["--config_path", f8.CONFIG, "--checkpoint_folder", f8.CKPT, "--output_folder", str(f8.INP / f"out_f14_{tag}"),
          "--prompt_file_path", f8.WORKLOADS[a.workload][1], "--video_path", str(video), "--noise_scale", "0.8", "--height", "480",
          "--width", "832", "--fps", "16", "--step", "2", "--seed", "0", "--model_type", "T2V-1.3B", "--gpu_id", str(a.gpu), "--profile"]
    if a.variant == "native":   # Fig. 8b's command, unchanged
        cmd = [sys.executable, "streamv2v/inference.py", *up]
    else:
        cmd = [sys.executable, "tools/eval/fig14_native_track.py", "entry", a.variant, str(trk), "--", *up]
    print(f"[F14] {tag}: {' '.join(cmd)}", flush=True)
    with open(log, "w") as fh:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
    res = f8.parse(log.read_text())
    tracking = json.loads(trk.read_text()) if trk.exists() else None
    if tracking and tracking.get("track_s"):
        ts = tracking.pop("track_s")
        win = ts[f8.WINDOW[0]:f8.WINDOW[1] + 1]
        tracking.update(track_ms_median=1e3 * sorted(win)[len(win) // 2] if win else None, track_ms_total=1e3 * sum(ts), n_tracked=len(ts))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rec = {"label": a.label, "workload": a.workload, "variant": a.variant, "rep": a.rep, "rc": rc, "gpu": f8.gpu_name(a.gpu), "commit": commit,
           "input": info, "cmd": cmd, "window": f8.WINDOW, "tracking": tracking, **res}
    (OUT / f"{tag}.json").write_text(json.dumps(rec, indent=1))
    print(f"[F14] {tag}: rc {rc}, {res['n_window']} chunks in the window, median {res['median_chunk_s']} s"
          + (f", tracking {tracking.get('track_ms_median')} ms/call" if tracking else ""), flush=True)
    if rc != 0 or res["n_window"] < f8.WINDOW[1] - f8.WINDOW[0] + 1:
        sys.exit(1)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "entry":
        i = sys.argv.index("--")
        entry(sys.argv[2], sys.argv[3], sys.argv[i + 1:])
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    r = sub.add_parser("run"); r.add_argument("--label", required=True); r.add_argument("--workload", choices=list(f8.WORKLOADS), required=True)
    r.add_argument("--rep", type=int, required=True); r.add_argument("--gpu", type=int, default=0)
    r.add_argument("--variant", choices=VARIANTS, required=True)
    a = ap.parse_args()
    run(a)


if __name__ == "__main__":
    main()
