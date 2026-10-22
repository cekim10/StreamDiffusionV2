#!/usr/bin/env python3
"""Experiment VC emulator (osdi/expVC/implementation_plan.md section 2). Does not modify rd_emulate.py or any mechanism.

One process = one input on one GPU: the uninterrupted reference (GpuRuntime.baseline, frames kept), then each requested
condition of results/evaluation/osdi/expVC/vc_schedules.json from call 0:

  ot   (OT-1, OT-L, OT-R)  RD semantics: an M1 reset before every reset call (serialize, pack in-flight + meta [+ the Sink
                           once per episode], release, provision, unpack, restore_fast); a bind before every bind call
                           (the withheld Sink of the episode). Same operations as rd_emulate.run_condition.
  wfs  (WFS-1, WFS-L)      reset and bind before the same call (RD d = 0): the Sink is bound before generation resumes.
  cold (COLD-1, COLD-L)    at the move call c the destination path of the frozen `cold` policy: release, provision (a
                           fresh destination session, as MANIFEST provisioning), GpuRuntime.cold_restart(c); no model
                           call at c (skip), the cold restart's frames emitted at c + k - 1 (the node's pending_cold rule).

Saved: every output frame of the condition's span (FFV1, vc_frames.FrameStore) in --frames_dir on local disk, and
calls.csv / summary.json under --out_root (results; copied back to elves-01 by run_vc.py).

    python tools/eval/vc_emulate.py --input dog --only OT-L,COLD-1,WFS-1 --frames_dir /local/vc_frames --out_root results/evaluation/expVC0
    python tools/eval/vc_emulate.py --input dog --dry_run --frames_dir /tmp/vcf      # fake runtime (protocol test)
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

from rd_emulate import payload_of, sha  # noqa: E402
import vc_frames as vf  # noqa: E402

SCHED = ROOT / "results/evaluation/osdi/expVC/vc_schedules.json"


def dry_frames(c: int, phase_shift: int, h: int, w: int) -> np.ndarray:
    """Fake runtime only: 4 deterministic frames per call; the pattern shifts after an operation so markers are visible."""
    y, x = np.mgrid[0:h, 0:w]
    return np.stack([np.stack([(x + 3 * (4 * c + f) + phase_shift) % 256, (y + 2 * (4 * c + f)) % 256, ((x + y) // 2 + phase_shift) % 256], -1)
                     for f in range(4)]).astype(np.uint8)


def run_condition(rt, cond: dict, base_record: list, dry: bool, store: vf.FrameStore, k: int, hw) -> tuple[list[dict], dict]:
    resets, binds = set(cond["resets"]), set(cond["binds"])
    cc = cond.get("cold_call")
    t1 = min(cond["resets"] + ([cc] if cc is not None else []))
    rows, log = [], []
    withheld = None
    bound_sha = []
    prefix_ok = True
    pending_cold = None
    shift = 0
    if dry:
        rt.provision(); rt.bound = True
    else:
        rt.session = rt.runner.start()
    t_run = time.time()
    for c in range(cond["end"] + 1):
        event = []
        if c in resets:   # --- identical to rd_emulate.run_condition (withheld Sink, packed once per episode)
            t0 = time.perf_counter()
            snap = rt.serialize_live()
            fast = [rt.pack(snap, comp) for comp in ("inflight", "meta")]
            if withheld is None:
                h, bufs = rt.pack(snap, "sink")
                pl = payload_of(h, bufs)
                withheld = (h, pl, sha(pl), c)
                log.append({"call": c, "op": "episode_open", "sink": "packed", "sha": withheld[2][:16]})
            else:
                log.append({"call": c, "op": "reset_inside_episode", "sink": "kept", "sha": withheld[2][:16]})
            fast_pl = [(dict(h), payload_of(h, bufs)) for h, bufs in fast]
            del snap, fast
            rt.release(); rt.provision()
            for h, pl in fast_pl:
                rt.unpack(dict(h), pl)
            rt.restore_fast()
            event.append("reset"); log[-1]["reset_s"] = time.perf_counter() - t0; shift += 40
        if c in binds:
            assert withheld is not None, f"bind at {c} without a withheld Sink"
            h, pl, s_, at = withheld
            assert sha(pl) == s_, "withheld Sink bytes changed"
            t0 = time.perf_counter()
            rt.unpack(dict(h), pl)
            shifted = rt.bind()
            bound_sha.append({"call": c, "sha": s_, "packed_at": at})
            log.append({"call": c, "op": "bind", "sha": s_[:16], "packed_at": at, "slots_rerotated": shifted, "bind_s": time.perf_counter() - t0})
            withheld = None
            event.append("bind"); shift += 7
        if cc is not None and c == cc:   # --- the frozen `cold` destination path
            t0 = time.perf_counter()
            rt.release(); rt.provision()
            frames_cold, ms = rt.cold_restart(c)
            pending_cold = {"skip": c, "emit": c + k - 1, "frames": frames_cold}
            log.append({"call": c, "op": "cold_restart", "cold_restart_ms": ms, "s": time.perf_counter() - t0})
            event.append("cold_restart"); shift += 90
        out_in = c - (k - 1)
        if pending_cold is not None and c in (pending_cold["skip"], pending_cold["emit"]):
            is_skip = c == pending_cold["skip"] and c != pending_cold["emit"]
            is_emit = c == pending_cold["emit"]
            produced, ps, ss, dt, pos = rt.step(c, override=pending_cold["frames"] if is_emit else None, skip=is_skip)
            if is_skip:
                event.append("skip"); out_in = None
            if is_emit:
                event.append("emit"); out_in = pending_cold["skip"]; pending_cold = None
        else:
            produced, ps, ss, dt, pos = rt.step(c)
        fr = getattr(rt, "last_frames", None)
        if dry and produced:
            fr = dry_frames(out_in, shift, *hw)
        if not produced:
            fr = None
        dg = vf.frame_digest(fr)
        if c < t1 and not dry and dg != base_record[c]["frame_digest"]:
            prefix_ok = False
        phase = "prefix" if c < t1 else ("sinkless" if (withheld is not None) else ("cold" if cc is not None else "bound"))
        ref_dg = base_record[c]["frame_digest"] if (base_record and not dry) else None
        rows.append({"call": c, "phase": phase, "event": "+".join(event), "psnr": ps, "ssim": ss, "produced": produced, "chunk_s": dt,
                     "out_input_call": out_in if produced else None, "frame_digest": dg, "ref_match": (dg == ref_dg) if (dg and ref_dg) else None})
        if cond["frames_from"] <= c <= cond["frames_to"]:
            store.add(c, fr, events=event, phase=phase, out_input_call=out_in if produced else None, digest=dg)
    realized = {"resets": [r["call"] for r in rows if "reset" in r["event"]], "binds": [r["call"] for r in rows if "bind" in r["event"]],
                "cold": [r["call"] for r in rows if "cold_restart" in r["event"]], "no_output": [r["call"] for r in rows if not r["produced"]]}
    exp_no_out = [cc] if (cc is not None and k > 1) else []
    valid = (realized["resets"] == cond["resets"] and realized["binds"] == cond["binds"] and realized["cold"] == ([cc] if cc is not None else [])
             and [c for c in realized["no_output"] if c >= t1] == exp_no_out and (dry or prefix_ok)
             and all((bs["packed_at"] in cond["resets"]) for bs in bound_sha))
    summary = {"condition": {k_: v for k_, v in cond.items() if k_ != "timeline"}, "t_first_op": t1, "events": log, "bound_sink": bound_sha, "realized": realized,
               "prefix_identical_to_reference": None if dry else prefix_ok, "valid": valid, "elapsed_s": time.time() - t_run}
    rt.release()
    return rows, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--only", default="", help="comma list of condition ids (default all seven)")
    ap.add_argument("--schedules", default=str(SCHED))
    ap.add_argument("--frames_dir", required=True, help="local-disk directory for the FFV1 frames (outside the repository)")
    ap.add_argument("--out_root", default=None)
    ap.add_argument("--gpu_id", type=int, default=0)
    ap.add_argument("--loveu_dir", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--no_ref_frames", action="store_true", help="do not store REF frames (checks that need none)")
    a = ap.parse_args()
    sched = json.loads(Path(a.schedules).read_text())["inputs"][a.input]
    conds = [c for c in sched["conditions"] if not a.only or c["id"] in a.only.split(",")]
    from expw_w1 import workload_paths
    import mobility_node as mn

    video, prompt = workload_paths(a.input, a.loveu_dir)
    N = sched["N"]
    hw = (96, 160) if a.dry_run else (480, 832)
    margs = mn.parse_args(["--label", "VC", "--video_path", str(video), "--prompt_file_path", str(prompt), "--seed", str(a.seed), "--gpu_id", str(a.gpu_id),
                           "--migration_chunk", "0", "--post_chunks", str(N), "--sink_fp"] +
                          (["--dry_run", "--dry_service_s", "0.0005", "--dry_sink_mb", "4", "--height", str(hw[0]), "--width", str(hw[1])] if a.dry_run else []))
    rt = mn.FakeRuntime(margs) if a.dry_run else mn.GpuRuntime(margs)
    k = int(rt.k)
    t0 = time.time()
    rt.baseline(0, N, keep_frames=True, write_ref=False)
    base_record = rt.base_record
    t_base = time.time() - t0
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_root = Path(a.out_root or ROOT / f"results/evaluation/{'_dryrun_' if a.dry_run else ''}expVC")
    unit = out_root / f"{a.input}_s{a.seed}"
    frames_root = Path(a.frames_dir) / f"{out_root.name}_{a.input}_s{a.seed}_{stamp}"
    host_meta = {"commit": commit, "host": platform.node(), "gpu_id": a.gpu_id, "dry_run": a.dry_run, "k": k, "baseline_s": t_base, "video": str(video), "prompt_file": str(prompt),
                 "frames_dir": str(frames_root), "versions": {} if a.dry_run else {"torch": rt.torch.__version__, "gpu": rt.torch.cuda.get_device_name(rt.device)}}
    if not a.no_ref_frames:
        ref = sched["ref"]
        st_ = vf.FrameStore(frames_root, "REF")
        for c in range(ref["frames_from"], ref["frames_to"] + 1):
            fr = rt.base.get(c) if not a.dry_run else dry_frames(c - (k - 1), 0, *hw)
            st_.add(c, fr, phase="ref", out_input_call=c - (k - 1), digest=None if a.dry_run else base_record[c]["frame_digest"])
        st_.close({"input": a.input, "condition": "REF", **host_meta})
        d = unit / "REF"; d.mkdir(parents=True, exist_ok=True)
        (d / "summary.json").write_text(json.dumps({"condition": {"id": "REF", "kind": "ref", "frames_from": ref["frames_from"], "frames_to": ref["frames_to"], "resets": [], "binds": [], "cold_call": None},
                                                    "valid": True, "frames": str(frames_root / "REF"), **host_meta}, indent=1))
    for cond in conds:
        store = vf.FrameStore(frames_root, cond["id"])
        rows, summ = run_condition(rt, cond, base_record, a.dry_run, store, k, hw)
        store.close({"input": a.input, "condition": cond["id"], **host_meta})
        d = unit / cond["id"]
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "calls.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
            for r in rows:
                w.writerow({k_: (f"{v:.4f}" if isinstance(v, float) else v) for k_, v in r.items()})
        summ.update({"input": a.input, "seed": a.seed, "frames": str(frames_root / cond["id"]), **host_meta})
        (d / "summary.json").write_text(json.dumps(summ, indent=1, default=str))
        print(f"[VC] {a.input} {cond['id']}: valid {summ['valid']} realized {summ['realized']} {summ['elapsed_s']:.0f} s -> {frames_root / cond['id']}", flush=True)


if __name__ == "__main__":
    main()
