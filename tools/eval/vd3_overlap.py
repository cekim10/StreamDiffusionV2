#!/usr/bin/env python3
"""Experiment VD-3 reconstruction-overlap measurement (osdi/expVD3/preregistration.md section 6). Emulator only, one
GPU; an engineering measurement reported with the verdicts, never a migration TTFO.

At the move call m of one unit (default dog seed 0, OT-1) the destination state after TS-in and the frozen fast path
(state X: temporary Sink written, KV / VAE caches otherwise zero) is saved once, with the RNG states. Each repeat
restores X and runs both orders, alternating:
  serial   DR-2 decode of the source's last 2 latent frames (synchronized), then the first generation call m;
  overlap  the DR-2 decode launched on a second CUDA stream, the first call m launched at once on the main stream;
           the call's own VAE decode waits for the DR-2 decode (CUDA event), since it reads the cache DR-2 writes.
Recorded per trial: the first output's digest, the generation (DiT) GPU time of call m (CUDA events from the call's
start to its decode entry), the wall time from the start of DR-2 to the first output on the host.
Checks: (a) digests equal across all trials of both orders; (b) median overlapped generation time <= 1.10 x the
serial one; (c) median overlapped time to the first output < the serial one. Overlap counts as a latency optimization
only if (a)-(c) all hold.

    python tools/eval/vd3_overlap.py --input dog --seed 0 --schedule OT-1 --reps 5 [--dry_run]
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

import vc_frames as vf  # noqa: E402
import vc_schedules as vs  # noqa: E402
from rd_emulate import payload_of  # noqa: E402

CONTENTION = 1.10


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default="dog"); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--schedule", default="OT-1")
    ap.add_argument("--reps", type=int, default=5); ap.add_argument("--gpu_id", type=int, default=0); ap.add_argument("--loveu_dir", default=None)
    ap.add_argument("--dry_run", action="store_true"); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    from expw_w1 import workload_paths
    import mobility_node as mn
    import vc_emulate as ve

    sched = vs.unit_sched(json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text()), f"{a.input}_s{a.seed}")
    cond = next(c for c in sched["conditions"] if c["id"] == a.schedule)
    m = cond["resets"][0]
    video, prompt = workload_paths(a.input, a.loveu_dir)
    hw = (96, 160) if a.dry_run else (480, 832)
    margs = mn.parse_args(["--label", "VD3OV", "--video_path", str(video), "--prompt_file_path", str(prompt), "--seed", str(a.seed), "--gpu_id", str(a.gpu_id),
                           "--migration_chunk", "0", "--post_chunks", str(m + 2), "--sink_fp"] +
                          (["--dry_run", "--dry_service_s", "0.0005", "--dry_sink_mb", "4", "--height", str(hw[0]), "--width", str(hw[1])] if a.dry_run else []))
    rt = mn.FakeRuntime(margs) if a.dry_run else mn.GpuRuntime(margs)
    dry = a.dry_run
    # --- run the source up to the move, then the frozen fast path + TS-in at the destination (state X)
    if dry:
        rt.provision(); rt.bound = True
    else:
        rt.session = rt.runner.start(); rt.capture_latents = True
    for c in range(m):
        rt.step(c)
    snap = rt.serialize_live()
    fast_pl = [(dict(h), payload_of(h, bufs)) for h, bufs in (rt.pack(snap, comp) for comp in ("inflight", "meta"))]
    lats = [] if dry else list(rt.last_latents)[-2:]
    last_image = None if dry else snap["session"]["last_image"].detach().clone()
    del snap
    if not dry:
        rt.capture_latents = False
    rt.release(); rt.provision()
    log = {"cost_s": {}}
    ve.vd3_reset(rt, m, {"ts": "in", "dr": 0}, fast_pl, dry, log, last_image, [], [], a.seed)
    trials = []
    if dry:
        for r in range(a.reps):
            for order in ("serial", "overlap"):
                t0 = time.perf_counter(); rt.decode_latents([0, 0]); rt.step(m)
                trials.append({"rep": r, "order": order, "digest": "dry", "gen_ms": 1.0, "t_first_s": time.perf_counter() - t0, "dr_s": 0.002})
    else:
        torch = rt.torch
        X = rt.serialize_live()
        rng = (torch.cuda.get_rng_state(rt.device), torch.get_rng_state())
        comps = set(rt.sa.STATE_COMPONENTS)
        side = torch.cuda.Stream(device=rt.device)
        inner = rt.pm._timed_stream_decode

        def restore():
            rt.sa.restore_state(rt.pl, rt.pm, rt.session, X, comps)
            rt.freeze_refresh()
            torch.cuda.set_rng_state(rng[0], rt.device); torch.set_rng_state(rng[1])
            torch.cuda.synchronize(rt.device)

        for r in range(a.reps):
            for order in (("serial", "overlap") if r % 2 == 0 else ("overlap", "serial")):
                restore()
                e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                state = {"ev": None, "entered": False}

                def hooked(pred, _inner=inner, _st=state, _e1=e1):
                    if not _st["entered"]:
                        _e1.record(); _st["entered"] = True
                        if _st["ev"] is not None:
                            torch.cuda.current_stream().wait_event(_st["ev"])
                    return _inner(pred)
                rt.pm._timed_stream_decode = hooked
                t0 = time.perf_counter()
                if order == "serial":
                    dr_s = rt.decode_latents(lats)
                else:
                    with torch.no_grad(), torch.cuda.stream(side):
                        for z in lats:
                            rt.pl.vae.stream_decode_to_pixel(z)
                        state["ev"] = side.record_event()
                    dr_s = None
                e0.record()
                rt.step(m)
                t_first = time.perf_counter() - t0
                torch.cuda.synchronize(rt.device)
                rt.pm._timed_stream_decode = inner
                trials.append({"rep": r, "order": order, "digest": vf.frame_digest(rt.last_frames), "gen_ms": float(e0.elapsed_time(e1)), "t_first_s": t_first, "dr_s": dr_s})
                print(f"[VD3OV] rep {r} {order}: first output {t_first:.3f} s, generation {trials[-1]['gen_ms']:.1f} ms, digest {trials[-1]['digest'][:12]}", flush=True)
    med = lambda o, k: st.median(t[k] for t in trials if t["order"] == o)  # noqa: E731
    res = {"input": a.input, "seed": a.seed, "schedule": a.schedule, "move_call": m, "reps": a.reps, "dry_run": dry, "trials": trials,
           "median": {o: {"gen_ms": med(o, "gen_ms"), "t_first_s": med(o, "t_first_s")} for o in ("serial", "overlap")},
           "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}
    res["checks"] = {"a_digests_equal": len({t["digest"] for t in trials}) == 1,
                     "b_contention_within_10pct": res["median"]["overlap"]["gen_ms"] <= CONTENTION * res["median"]["serial"]["gen_ms"],
                     "c_first_output_earlier": res["median"]["overlap"]["t_first_s"] < res["median"]["serial"]["t_first_s"]}
    res["overlap_counts_as_optimization"] = all(res["checks"].values())
    out = Path(a.out or ROOT / "results/evaluation/osdi/expVD3" / ("_dryrun_vd3_overlap.json" if dry else "vd3_overlap.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != "trials"}, indent=1, default=str))


if __name__ == "__main__":
    main()
