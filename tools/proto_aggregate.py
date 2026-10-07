#!/usr/bin/env python3
"""Summarize prototype results: handoff stall, bytes, sink bind time and continuity per policy x bandwidth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=str, default="results/state_migration/proto/proto_results.json")
    args = ap.parse_args()
    path = Path(args.results)
    with open(path) as fh:
        res = json.load(fh)
    if not res:
        raise SystemExit("no results")
    S = res[0]["service_s"]
    L = ["# Late-binding handoff prototype: policy x bandwidth\n",
         f"Destination steady-state service time S = {S * 1e3:.0f} ms/chunk (4 frames). Times are seconds after the destination's READY (t_mig). "
         "stall = time to the first output chunk minus S. missed = missing output chunks plus output gaps longer than 2S after resume (hiccups, e.g. from background-transfer contention). "
         "PSNR vs the destination's own bit-exact baseline (99 = identical, ~20 = different stream).\n",
         "| policy | BW (Mbps) | fg MB | bg MB | first output s | stall s | missed/hiccup chunks | sink arrived s | bound at call | PSNR M+0..7 | PSNR gap->bind | PSNR after bind+8 | PSNR M+16.. | PSNR last 8 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(res, key=lambda r: (r["bw_mbps"], r["policy"])):
        calls = r["calls"]
        tf = r["t_first_out"]
        stall = (tf - S) if tf is not None else float("nan")
        # hiccups after resume: output gaps longer than 2 service times (e.g. contention from the background transfer)
        outs = [x["t_out"] for x in calls if not x["missing"]]
        missed = sum(1 for a, b in zip(outs, outs[1:]) if (b - a) > 2 * S) + sum(1 for x in calls if x["missing"])
        p = lambda lo, hi: mean([x["psnr"] for x in calls if lo <= x["rel"] <= hi])  # noqa: E731
        bc = r.get("bound_call")
        gap = p(0, (bc - r["calls"][0]["call"] - 1)) if bc is not None else float("nan")
        after = p(bc - r["calls"][0]["call"] + 8, 10**6) if bc is not None else float("nan")
        n = len(calls)
        L.append(f"| {r['policy']} | {r['bw_mbps']:g} | {r['bytes_fg_mb']:.1f} | {r['bytes_bg_mb']:.0f} | {tf if tf is not None else float('nan'):.2f} | {stall:.2f} | {missed} | "
                 f"{r['t_sink_arrived'] if r['t_sink_arrived'] is not None else float('nan'):.2f} | {bc} | {p(0, 7):.1f} | {gap:.1f} | {after:.1f} | {p(16, 10**6):.1f} | {p(n - 8, 10**6):.1f} |")
    L.append("\nHeadline check: for `ours`, first-output time should be independent of bandwidth (fast path only), while `full` first-output time scales with 9.5 GB / BW; `ours` should rejoin the baseline (PSNR after bind+8 >= 35) once the sink binds, `cold` should stay near 20 dB.")
    out = path.with_name("proto_summary.md")
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
