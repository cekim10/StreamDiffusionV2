#!/usr/bin/env python3
"""Figure 6: time to first output after migration vs bandwidth (median, p25-p75), plus a companion table.
Reads results/evaluation/single_handoff/summary_runs.csv (from aggregate_single_handoff.py). No expected numbers."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

LABEL = {"full": "SDV2-FullMigration", "cold": "SDV2-Restart", "replay": "Replay", "ours": "Ours", "ours_refresh": "Ours (refresh on)"}
COLOR = {"full": "#7f7f7f", "cold": "#d62728", "replay": "#ff7f0e", "ours": "#2ca02c", "ours_refresh": "#98df8a"}
MARK = {"full": "s", "cold": "x", "replay": "^", "ours": "o", "ours_refresh": "o"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=str, default="results/evaluation/single_handoff")
    ap.add_argument("--native_mbps", type=float, default=10000.0, help="x position for 'native' runs")
    a = ap.parse_args()
    root = Path(a.root)
    rows = list(csv.DictReader(open(root / "summary_runs.csv")))
    data = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["policy"] in ("repeat",):
            continue
        bw = a.native_mbps if r["bw_mbps"] == "native" else float(r["bw_mbps"])
        for key in ("first_output_latency_s", "continuity_ready_rel_s", "total_bytes"):
            if r.get(key):
                data[r["policy"]][(bw, key)].append(float(r[key]))
    fig, ax = plt.subplots(figsize=(4.4, 3.0))
    for pol in ("full", "cold", "replay", "ours"):
        pts = sorted({bw for (bw, k) in data[pol] if k == "first_output_latency_s"})
        if not pts:
            continue
        med = [np.median(data[pol][(bw, "first_output_latency_s")]) for bw in pts]
        lo = [np.percentile(data[pol][(bw, "first_output_latency_s")], 25) for bw in pts]
        hi = [np.percentile(data[pol][(bw, "first_output_latency_s")], 75) for bw in pts]
        ax.plot(pts, med, marker=MARK[pol], ms=4.5, color=COLOR[pol], label=LABEL[pol])
        ax.fill_between(pts, lo, hi, color=COLOR[pol], alpha=0.18, lw=0)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Link bandwidth (Mbps; rightmost = native)"); ax.set_ylabel("Time to first output after migration (s)")
    ax.legend(frameon=False, fontsize=8); ax.grid(True, which="both", lw=0.3, alpha=0.5)
    ax.set_title("Execution handoff latency vs. bandwidth (median, p25-p75)", fontsize=9, loc="left")
    fig.tight_layout()
    out = root / "fig6_handoff_latency"
    fig.savefig(out.with_suffix(".pdf")); fig.savefig(out.with_suffix(".png"), dpi=200)
    # companion table
    lines = ["| policy | BW (Mbps) | first output s (median [p25, p75]) | continuity-ready s | bytes (MB) |", "|---|---|---|---|---|"]
    for pol in ("full", "cold", "replay", "ours"):
        for bw in sorted({bw for (bw, k) in data[pol]}):
            f = data[pol].get((bw, "first_output_latency_s"), []); c = data[pol].get((bw, "continuity_ready_rel_s"), []); b = data[pol].get((bw, "total_bytes"), [])
            fmt = lambda v: f"{np.median(v):.2f} [{np.percentile(v, 25):.2f}, {np.percentile(v, 75):.2f}]" if v else "-"  # noqa: E731
            lines.append(f"| {LABEL[pol]} | {'native' if bw == a.native_mbps else f'{bw:g}'} | {fmt(f)} | {fmt(c)} | {np.median(b) / 2**20:.1f} |" if b else f"| {LABEL[pol]} | {bw:g} | {fmt(f)} | {fmt(c)} | - |")
    (root / "fig6_table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines)); print(f"-> {out}.png")


if __name__ == "__main__":
    main()
