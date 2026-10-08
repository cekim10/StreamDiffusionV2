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
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.6, 3.0))
    for key, axis, title, ylabel in (("first_output_latency_s", ax, "(a) Execution handoff: time to first output", "seconds after migration"),
                                     ("continuity_ready_rel_s", bx, "(b) Continuity handoff: time to Sink bind", "seconds after migration")):
        for pol in ("full", "cold", "replay", "ours"):
            pts = sorted({bw for (bw, k) in data[pol] if k == key})
            if not pts:
                continue
            med = [np.median(data[pol][(bw, key)]) for bw in pts]
            lo = [np.percentile(data[pol][(bw, key)], 25) for bw in pts]
            hi = [np.percentile(data[pol][(bw, key)], 75) for bw in pts]
            axis.plot(pts, med, marker=MARK[pol], ms=4.5, color=COLOR[pol], label=LABEL[pol])
            axis.fill_between(pts, lo, hi, color=COLOR[pol], alpha=0.18, lw=0)
        axis.set_xscale("log"); axis.set_yscale("log")
        axis.set_xlabel("Link bandwidth (Mbps; rightmost = native)"); axis.set_ylabel(ylabel)
        axis.grid(True, which="both", lw=0.3, alpha=0.5)
        axis.set_title(title, fontsize=9, loc="left")
    ax.legend(frameon=False, fontsize=8)
    bx.text(0.02, 0.04, "Restart and Replay never rejoin the original trajectory", transform=bx.transAxes, fontsize=7, color="#555555")
    fig.tight_layout()
    out = root / "fig6_handoff_latency"
    fig.savefig(out.with_suffix(".pdf")); fig.savefig(out.with_suffix(".png"), dpi=200)
    # companion table
    lines = ["| policy | BW (Mbps) | first output s (median [p25, p75]) | Sink bound s (first output on the transferred Sink) | bytes (MB) |", "|---|---|---|---|---|"]
    for pol in ("full", "cold", "replay", "ours"):
        for bw in sorted({bw for (bw, k) in data[pol]}):
            f = data[pol].get((bw, "first_output_latency_s"), []); c = data[pol].get((bw, "continuity_ready_rel_s"), []); b = data[pol].get((bw, "total_bytes"), [])
            fmt = lambda v: f"{np.median(v):.2f} [{np.percentile(v, 25):.2f}, {np.percentile(v, 75):.2f}]" if v else "-"  # noqa: E731
            lines.append(f"| {LABEL[pol]} | {'native' if bw == a.native_mbps else f'{bw:g}'} | {fmt(f)} | {fmt(c)} | {np.median(b) / 2**20:.1f} |" if b else f"| {LABEL[pol]} | {bw:g} | {fmt(f)} | {fmt(c)} | - |")
    (root / "fig6_table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines)); print(f"-> {out}.png")


if __name__ == "__main__":
    main()
