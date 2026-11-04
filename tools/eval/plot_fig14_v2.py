#!/usr/bin/env python3
"""Fig. 14 DRAFT 2 (user 2026-11-03: two panels, runtime overhead + GPU memory timeline). Existing data only.

fig14a_dots      per-call slowdown (%) for Tracking / Transfer / Staging as a horizontal dot plot; Low-refresh filled,
                 High-refresh open; each row has its own baseline (caption). Values from fig14_results.json.
fig14b_timeline  GPU allocated memory (GiB) over time on the four nodes of one Fig. 11 chain run with staging
                 (expF14_mem_chain_dog rep 1, the first rep by order, not selected), from node_<X>/memory.csv (2 Hz);
                 shaded = each migration from its start (xb_task_start) to its cutover (xb_precopy_switch).

    python tools/eval/plot_fig14_v2.py
"""

from __future__ import annotations

import csv
import glob
import json
import statistics as st
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from plot_fig11 import XTICK_ROT
from plot_fig7_migration import (ANNOT, ANNOT_FONT, BLUE, DARK_GRAY, DIM_GRAY, FIG_SIZE as FIG_SIZE_78, LABEL, LEGEND, ROOT, TICK,
                                 configure, finish_axes)

OUT = ROOT / "results/evaluation/osdi/fig14/figures/v2"
RES = ROOT / "results/evaluation/osdi/fig14/fig14_results.json"
FIG_SIZE_6A = (5.83, 4.78)          # Fig. 11 canvas and plot box (user 2026-11-03: both panels the same size as Fig. 11)
AXES_POS_11 = [0.18, 0.22, 0.79, 0.75]
WL = ("dog", "bfly")


def save(fig, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT)}.{{pdf,png}}")


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def dots(res, out):
    """Vertical dot plot on the Fig. 11 canvas: rotated 28 pt category labels do not fit a Fig. 11 row (fonts are never
    reduced), so the operations are on x and the slowdown on y (rotated y label)."""
    nat, ph = res["native"], res["phases"]
    rows = [("Tracking", [nat["ratios"][w]["track/native"] for w in WL]),
            ("Transfer", [med([x["src_ratio"] for x in ph["transfer"] if x["workload"] == w]) for w in WL]),
            ("Staging", [med([x["ratio"] for x in ph["staging"] if x["workload"] == w]) for w in WL])]
    fig = plt.figure(figsize=FIG_SIZE_6A); ax = fig.add_axes(AXES_POS_11)
    for x, (name, vals) in enumerate(rows):
        for wi, v in enumerate(vals):
            pct = 100 * (v - 1)
            dx = -0.17 if wi == 0 else 0.17
            ax.scatter(x + dx, pct, s=320, marker="o", facecolor=BLUE if wi == 0 else "white", edgecolor=BLUE, linewidth=2.5, zorder=4)
            ax.text(x + dx, pct + 0.16, f"{pct:.2f}" if pct < 0.5 else f"{pct:.1f}", ha="center", va="bottom", fontsize=ANNOT,
                    fontfamily=ANNOT_FONT, style="italic", rotation=90)
        ax.axvline(x, color="#DDDDDD", lw=1.0, zorder=1)
    ax.set_xticks(range(len(rows))); ax.set_xticklabels([r[0] for r in rows])
    ax.set_xlim(-0.6, len(rows) - 0.4)
    finish_axes(ax, "Per-call slowdown (%)")
    plt.setp(ax.get_xticklabels(), rotation=XTICK_ROT, ha="right", rotation_mode="anchor")   # as Fig. 11 (user 2026-11-03)
    ax.yaxis.set_label_coords(-0.145, 0.5)
    ax.grid(axis="x", visible=False)
    ax.set_ylim(-0.2, 4.0)
    ax.legend(handles=[Line2D([], [], ls="", marker="o", ms=15, mfc=BLUE, mec=BLUE, mew=2.5, label="Low-refresh"),
                       Line2D([], [], ls="", marker="o", ms=15, mfc="white", mec=BLUE, mew=2.5, label="High-refresh")],
              loc="upper left", frameon=False, fontsize=LEGEND, handletextpad=0.2, labelspacing=0.15, borderaxespad=0.2)
    save(fig, out)


def timeline(out):
    d = Path(sorted(glob.glob(str(ROOT / "results/evaluation/expF14_mem_chain_dog/policy=*rep=1_*")))[0])
    ev = list(csv.DictReader(open(d / "events.csv", newline="")))
    starts = [float(e["t_wall"]) for e in ev if e["event"] == "xb_task_start"]
    cuts = [float(e["t_wall"]) for e in ev if e["event"].endswith(":xb_precopy_switch")]
    t0 = starts[0]
    fig = plt.figure(figsize=FIG_SIZE_6A); ax = fig.add_axes(AXES_POS_11)
    style = {"A": (BLUE, "-", 3.0), "B": ("black", "--", 3.0), "C": (DARK_GRAY, "-.", 3.0), "D": (DIM_GRAY, ":", 3.8)}
    for lb, (col, ls, lw) in style.items():
        rows = list(csv.DictReader(open(d / f"node_{lb}/memory.csv", newline="")))
        t = [float(r["t_wall"]) - t0 for r in rows]
        g = [float(r["gpu_alloc_mb"]) / 1024 for r in rows]
        keep = [(a, b) for a, b in zip(t, g) if a >= -6]
        ax.plot([a for a, _ in keep], [b for _, b in keep], color=col, ls=ls, lw=lw, label=lb, zorder=3)
    for i, (s, c) in enumerate(zip(starts, cuts)):
        ax.axvspan(s - t0, c - t0, color="#E8E8E8", zorder=0)
        ax.text((s + c) / 2 - t0, 43.6, f"Hop {i + 1}", ha="center", va="center", fontsize=ANNOT, fontfamily=ANNOT_FONT)
    ax.set_xlim(-6, 150)
    ax.set_xticks([0, 50, 100])   # a 150 label would run past the Fig. 11 canvas
    finish_axes(ax, "GPU allocated (GiB)")
    ax.yaxis.set_label_coords(-0.145, 0.5)
    ax.set_ylim(11, 46)
    ax.set_xlabel("Time (s)", fontsize=LABEL, labelpad=2)
    kw = dict(fontsize=ANNOT, fontfamily=ANNOT_FONT, arrowprops=dict(arrowstyle="-|>", color="black", lw=1.5, mutation_scale=18), zorder=6)
    ax.annotate("Snapshot", xy=(-4.5, 26.2), xytext=(-5, 31.5), ha="left", va="center", **kw)
    ax.annotate("Receive buffer", xy=(33, 25.7), xytext=(22, 22.2), ha="left", va="center", **kw)
    ax.annotate("Receive + outbound", xy=(47, 33.9), xytext=(-5, 37.8), ha="left", va="center", **kw)
    ax.text(112, 20.6, "Serving", ha="left", va="bottom", fontsize=ANNOT, fontfamily=ANNOT_FONT, zorder=6)
    ax.legend(loc="lower right", ncol=4, frameon=False, fontsize=LEGEND, handlelength=1.6, handletextpad=0.3,
              columnspacing=0.8, labelspacing=0.15, borderaxespad=0.2)
    save(fig, out)
    return {"run": d.name, "starts_s": [round(s - t0, 1) for s in starts], "cutovers_s": [round(c - t0, 1) for c in cuts]}


def main():
    configure()
    res = json.load(open(RES))
    dots(res, OUT / "fig14a_dots")
    print(timeline(OUT / "fig14b_timeline"))


if __name__ == "__main__":
    main()
