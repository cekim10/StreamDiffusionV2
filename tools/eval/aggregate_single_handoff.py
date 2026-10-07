#!/usr/bin/env python3
"""Aggregate Phase 1 run directories (results/evaluation/single_handoff/*/summary.json) into
summary_runs.csv (one row per run) and summary_by_policy_bw.csv (median, p25, p75 across repetitions)."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

FIELDS = ["policy", "bw_mbps", "rep", "first_output_latency_s", "resume_latency_s", "continuity_ready_rel_s", "sink_ready_rel_s", "bound_call", "rejoin_calls_after_bind",
          "total_bytes", "bytes_bg_sink", "serialize_s", "h2d_fg_s", "h2d_sink_s", "psnr_M0", "psnr_M0_7", "psnr_M16_end", "psnr_after_bind_8", "ssim_M0_7", "ssim_M16_end",
          "missing_chunks", "hiccup_chunks", "gpu_mem_alloc_mb_max", "service_s", "clock_offset_s", "rtt_min_s", "mss_dest", "mss_source", "checksums_all_ok", "identical", "run_dir"]
STATS = ["first_output_latency_s", "continuity_ready_rel_s", "sink_ready_rel_s", "total_bytes", "psnr_M0_7", "psnr_M16_end", "psnr_after_bind_8", "ssim_M16_end", "rejoin_calls_after_bind", "missing_chunks"]


def q(xs, p):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=str, default="results/evaluation/single_handoff")
    a = ap.parse_args()
    root = Path(a.root)
    runs = []
    for sj in sorted(root.glob("*/summary.json")):
        s = json.load(open(sj))
        s["checksums_all_ok"] = s.get("validation", {}).get("checksums_all_ok")
        s["identical"] = s.get("validation", {}).get("full_identical") if s["policy"] == "full" else s.get("validation", {}).get("repeat_identical")
        s["bw_mbps"] = s["bw_mbps"] if s["bw_mbps"] else "native"
        runs.append(s)
    if not runs:
        raise SystemExit("no runs")
    with open(root / "summary_runs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore"); w.writeheader(); w.writerows(runs)
    groups = defaultdict(list)
    for s in runs:
        groups[(s["policy"], s["bw_mbps"])].append(s)
    header = ["policy", "bw_mbps", "n"] + [f"{m}_{st}" for m in STATS for st in ("median", "p25", "p75")]
    lines = [",".join(header)]
    for (pol, bw), lst in sorted(groups.items(), key=lambda kv: (str(kv[0][1]), kv[0][0])):
        cells = [pol, str(bw), str(len(lst))]
        for m in STATS:
            vals = [x.get(m) for x in lst]
            cells += [("" if v is None else f"{v:.4f}") for v in (q(vals, 0.5), q(vals, 0.25), q(vals, 0.75))]
        lines.append(",".join(cells))
    (root / "summary_by_policy_bw.csv").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:1] + lines[1:]))
    bad = [s["run_dir"] for s in runs if s["checksums_all_ok"] is False or s["identical"] is False]
    print(f"\nvalidation failures: {bad if bad else 'none'}")
    print(f"-> {root / 'summary_by_policy_bw.csv'}")


if __name__ == "__main__":
    main()
