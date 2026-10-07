#!/usr/bin/env python3
"""Summarize A->B->C mobility runs: continuity-ready time at C, wasted and total traffic, continuity windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else float("nan")


def f(v, nd=1):
    return "-" if v is None or (isinstance(v, float) and v != v) else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=str, default="results/state_migration/mobility/mobility_results.json")
    args = ap.parse_args()
    path = Path(args.results)
    res = json.load(open(path))
    S = res[0]["service_s"]
    bw = res[0]["bw_mbps"]
    sink_mb = max(max(r["bytes"]["AB"], r["bytes"]["AC"]) for r in res) / (1024 * 1024)
    t_s = sink_mb * 1024 * 1024 * 8 / (bw * 1e6)
    L = [f"# A -> B -> C mobility: sink policy x mobility interval ({bw:g} Mbps, sink {sink_mb:.0f} MB, link time T_s = {t_s:.1f} s, S = {S * 1e3:.0f} ms/chunk)\n",
         "Times in seconds after the A->B handoff. ready_C = true sink bound at C (continuity restored at the final edge); "
         "ready_after_move = ready_C minus the B->C move time. wasted = sink bytes delivered to an edge that execution had already left (restart). "
         "PSNR vs the uninterrupted baseline: B phase (before the move), C gap (move -> bind), C after bind+8, last 8 calls.\n",
         "| policy | T_m (s) | rho = T_s/T_m | moved at | ready_B | ready_C | ready_after_move | A->B MB | A->C MB | B->C MB | wasted MB | total MB | PSNR B phase | PSNR C gap | PSNR C bind+8.. | PSNR last 8 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(res, key=lambda r: (r["t_m"], r["policy"])):
        calls = r["calls"]
        tm, tmv = r["t_m"], r["t_move"]
        rc = r["t_ready_C"]
        bC = r["bound_call"].get("C") if isinstance(r["bound_call"], dict) else None
        mv_call = next((e["call"] for e in r["events"] if e.get("moved") == "C"), None)
        pB = mean([x["psnr"] for x in calls if x["node"] == "B"])
        pgap = mean([x["psnr"] for x in calls if x["node"] == "C" and (bC is None or x["call"] < bC)])
        pafter = mean([x["psnr"] for x in calls if bC is not None and x["call"] >= bC + 8])
        plast = mean([x["psnr"] for x in calls[-8:]])
        b = r["bytes"]
        L.append(f"| {r['policy']} | {tm:g} | {t_s / tm:.1f} | {f(tmv)} | {f(r['t_ready_B'])} | {f(rc)} | {f((rc - tmv) if (rc is not None and tmv is not None) else None)} | "
                 f"{b['AB'] / 2**20:.0f} | {b['AC'] / 2**20:.0f} | {b['BC'] / 2**20:.0f} | {r['wasted_mb']:.0f} | {r['total_mb']:.0f} | {f(pB)} | {f(pgap)} | {f(pafter)} | {f(plast)} |")
    L.append("\nReading guide: rho < 1 means the sink can reach B before execution leaves; rho > 1 means execution outruns its continuity state and the single-destination policies diverge: restart wastes what reached B, relay delays C by a second hop, direct (oracle) needs to know C in advance.")
    out = path.with_name("mobility_summary.md")
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L)); print(f"\n-> {out}")


if __name__ == "__main__":
    main()
