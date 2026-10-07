#!/usr/bin/env python3
"""Aggregate Phase 0 calibration records into results/evaluation/network_calibration.csv (one row per flow)
and a per-pattern summary (median app throughput per flow, aggregate ingress/egress)."""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=str, default="results/evaluation/network_calibration")
    a = ap.parse_args()
    root = Path(a.root)
    rows = []
    for f in sorted(root.rglob("recv_flow*.json")):
        r = json.load(open(f))
        parts = f.relative_to(root).parts  # <run>/<pattern>/rep<k>/file
        run, pattern, rep = parts[0], parts[1], parts[2]
        mss = next((p.split("=")[1] for p in run.split("_") if p.startswith("mss=")), "")
        rows.append({"run": run, "pattern": pattern, "rep": rep, "flow": r["flow"], "src": r["peer"], "dst": r["host"], "bytes": r["bytes"],
                     "seconds": f"{r['recv_seconds']:.3f}", "mbps_app": f"{r['mbps_app']:.1f}", "mss": r.get("mss") or mss, "mss_cfg": mss,
                     "t_first_byte": r["t_first_byte"], "t_end": r["t_end"]})
    out = root.parent / "network_calibration.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["run"]); w.writeheader(); w.writerows(rows)
    # per pattern: aggregate ingress at the receiving host = sum bytes / (max t_end - min t_first) over the flows of a rep
    agg = defaultdict(list)
    by_rep = defaultdict(list)
    for r in rows:
        by_rep[(r["run"], r["pattern"], r["rep"])].append(r)
    for (run, pattern, rep), fl in by_rep.items():
        t0 = min(x["t_first_byte"] for x in fl); t1 = max(x["t_end"] for x in fl)
        total = sum(int(x["bytes"]) for x in fl)
        agg[(run, pattern)].append({"flows": len(fl), "per_flow_mbps": st.median(float(x["mbps_app"]) for x in fl), "aggregate_mbps": total * 8 / max(1e-9, t1 - t0) / 1e6,
                                    "dsts": sorted({x["dst"] for x in fl})})
    lines = ["run,pattern,reps,flows,per_flow_mbps_median,aggregate_mbps_median,aggregate_mbps_p25,aggregate_mbps_p75,receivers"]
    for (run, pattern), lst in sorted(agg.items()):
        aggs = sorted(x["aggregate_mbps"] for x in lst)
        q = lambda p: aggs[min(len(aggs) - 1, int(p * (len(aggs) - 1)))]  # noqa: E731
        lines.append(f"{run},{pattern},{len(lst)},{lst[0]['flows']},{st.median(x['per_flow_mbps'] for x in lst):.0f},{st.median(aggs):.0f},{q(0.25):.0f},{q(0.75):.0f},{'|'.join(lst[0]['dsts'])}")
    (root.parent / "network_calibration_summary.csv").write_text("\n".join(lines) + "\n")
    print("\n".join(lines)); print(f"-> {out}")


if __name__ == "__main__":
    main()
