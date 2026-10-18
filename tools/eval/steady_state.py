#!/usr/bin/env python3
"""Experiment D G9 (first clause): steady-state chunk service time with OTTER enabled and no migration vs unmodified
generation, same GPU, same seed, `--reps` reps of `--chunks` chunks (preregistration v3 section 7, G9; 3 x 200).

  unmodified    the generation loop alone: Runner.step (the same seeding and input slicing every harness run uses) and a
                device synchronize per chunk; the decode-completion hook is removed
  otter         the GPU node's generation path with OTTER's per-chunk instrumentation on and no migration: the
                decode-completion hook (a device synchronize after every VAE decode, t_decode), the per-chunk Sink-slot
                position read and the metrics row the node writes. The prereg requires t_decode logging enabled for G9.
                PSNR against a reference is a measurement of the evaluation, not part of OTTER, and is off in both modes.
Measured per chunk, for `--chunks` chunks after `--warmup` chunks, per rep and mode: the chunk service time (the model
call plus the device synchronize, perf_counter; the repo's "service time", as in the nodes' service_s; in OTTER mode the
decode-completion hook runs inside it) - the G9 metric - and the inter-chunk completion interval (wall clock between
consecutive chunk completions, which also includes the per-chunk bookkeeping) - reported, descriptive. Modes alternate
in ABBA order across reps; frames are hashed so the two modes are checked to produce identical output. Run on one host with GPU 0 idle and no node process running (the run records the GPU state first).

    python tools/eval/steady_state.py --reps 3 --chunks 200            # -> results/evaluation/expD_G9/steady_<stamp>/
    python tools/eval/steady_state.py --dry_run --reps 1 --chunks 20   # no torch, protocol test only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

import mobility_node as mn  # noqa: E402
from common import CsvLog, git_commit, host_info  # noqa: E402


def gpu0_state(gpu: int) -> dict:
    try:
        u = subprocess.run(["nvidia-smi", "-i", str(gpu), "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30).stdout.strip()
        apps = subprocess.run(["nvidia-smi", "-i", str(gpu), "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30).stdout.strip()
        util, mem = (float(x) for x in u.split(","))
        others = [ln.split(",") for ln in apps.splitlines() if ln.strip()]
        return {"util_pct": util, "mem_used_mib": mem, "others_mib": sum(float(x[1]) for x in others), "processes": [x[0].strip() for x in others]}
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--chunks", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=30)
    ap.add_argument("--experiment", type=str, default="expD_G9")
    a, rest = ap.parse_known_args()
    na = mn.parse_args(["--label", "A", "--migration_chunk", str(a.warmup), "--post_chunks", str(a.chunks)] + rest)
    out = ROOT / "results/evaluation" / (("_dryrun_" if na.dry_run else "") + a.experiment) / f"steady_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=False)
    g0 = None if na.dry_run else gpu0_state(na.gpu_id)
    rt = mn.FakeRuntime(na) if na.dry_run else mn.GpuRuntime(na)
    rt.base = {}   # no PSNR in either mode
    log = CsvLog(out / "chunks.csv", ["rep", "mode", "call", "t_out", "interval_s", "chunk_s", "frame_sha"])
    metrics = CsvLog(out / "otter_metrics.csv", ["call", "t_out", "owner", "chunk_s", "psnr", "ssim", "missing", "sink_bound", "gpu_mem_alloc_mb", "sink_slot_pos", "t_decode", "n_frames"])
    res, hashes = [], {}
    order = ["unmodified", "otter"]
    for rep in range(1, a.reps + 1):
        modes = order if rep % 2 == 1 else order[::-1]   # ABBA across reps
        for mode in modes:
            if not na.dry_run:
                rt.instrument(mode == "otter")
                rt.torch.cuda.reset_peak_memory_stats(rt.device)
                rt.session = rt.runner.start()
            prev, iv, sv = None, [], []
            for c in range(a.warmup + a.chunks):
                if na.dry_run:
                    produced, ps, ss, dt, pos = rt.step(c); fr = None
                elif mode == "unmodified":
                    t0 = time.perf_counter(); fr = rt.runner.step(rt.session, c); rt.torch.cuda.synchronize(rt.device); dt = time.perf_counter() - t0
                else:
                    rt.decodes = []
                    t0 = time.perf_counter(); fr = rt.runner.step(rt.session, c); rt.torch.cuda.synchronize(rt.device); dt = time.perf_counter() - t0
                    pos = rt.sa.slot_positions(rt.pl)["sink_slot_pos"]
                t_out = time.time()
                if mode == "otter":   # the node's per-chunk bookkeeping (metrics row), as in mobility_node.Node._generate
                    dec = list(rt.decodes)
                    metrics.row(call=c, t_out=f"{t_out:.4f}", owner="A", chunk_s=f"{dt:.4f}", psnr=None, ssim=None, missing=fr is None, sink_bound=False,
                                gpu_mem_alloc_mb=f"{rt.gpu_mem_mb():.1f}", sink_slot_pos=pos if not na.dry_run else None, t_decode=dec[-1][0] if dec else None, n_frames=sum(n for _, n in dec))
                h = hashlib.sha256(fr.tobytes()).hexdigest()[:16] if fr is not None else ""
                if rep == 1 and h:
                    hashes.setdefault(c, {})[mode] = h
                interval = None if prev is None else t_out - prev
                prev = t_out
                if c >= a.warmup and interval is not None:
                    iv.append(interval); sv.append(dt)
                log.row(rep=rep, mode=mode, call=c, t_out=f"{t_out:.6f}", interval_s=None if interval is None else f"{interval:.6f}", chunk_s=f"{dt:.6f}", frame_sha=h)
            peak = None if na.dry_run else rt.torch.cuda.max_memory_allocated(rt.device) / 2**20
            res.append({"rep": rep, "mode": mode, "n": len(iv), "median_service_s": float(np.median(sv)), "mean_service_s": float(np.mean(sv)),
                        "median_interval_s": float(np.median(iv)), "mean_interval_s": float(np.mean(iv)),
                        "p95_interval_s": float(np.percentile(iv, 95)), "peak_allocated_mb": peak})
            print(f"[g9] rep {rep} {mode:10s}: service time median {res[-1]['median_service_s'] * 1e3:.1f} ms, completion interval median {res[-1]['median_interval_s'] * 1e3:.1f} ms over {len(iv)} chunks", flush=True)
            if not na.dry_run:
                rt.release()
    log.close(); metrics.close()
    by = lambda m, k: [r[k] for r in res if r["mode"] == m]  # noqa: E731
    med_u, med_o = float(np.median(by("unmodified", "median_service_s"))), float(np.median(by("otter", "median_service_s")))
    iv_u, iv_o = float(np.median(by("unmodified", "median_interval_s"))), float(np.median(by("otter", "median_interval_s")))
    same = all(len(set(v.values())) == 1 for v in hashes.values() if len(v) == 2) if hashes else None
    summary = {"experiment": "G9 steady state", "reps": a.reps, "chunks": a.chunks, "warmup": a.warmup, "per_rep": res,
               "metric": "chunk service time (G9); completion interval descriptive",
               "median_service_over_reps_s": {"unmodified": med_u, "otter": med_o}, "relative_difference": (med_o - med_u) / med_u,
               "median_interval_over_reps_s": {"unmodified": iv_u, "otter": iv_o}, "relative_difference_interval": (iv_o - iv_u) / iv_u,
               "identical_frames_rep1": same, "gpu0_before": g0, "gpu0_idle_before": None if g0 is None else ("error" not in g0 and g0["others_mib"] < 1024 and g0["util_pct"] <= 5),
               "host": socket.gethostname(), "host_info": host_info(None if na.dry_run else na.gpu_id), "git_commit": git_commit(), "args": vars(na), "dry_run": na.dry_run}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(f"[g9] median chunk service time: unmodified {med_u * 1e3:.2f} ms, OTTER enabled {med_o * 1e3:.2f} ms, relative {summary['relative_difference'] * 100:+.2f} %; "
          f"completion interval {summary['relative_difference_interval'] * 100:+.2f} % -> {out.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
