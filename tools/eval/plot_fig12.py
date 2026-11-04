#!/usr/bin/env python3
"""Fig. 12a (osdi/fig12/preregistration.md section 9, DRAFT). Reads osdi/fig12/fig12_results.json (tools/eval/fig12_report.py).

fig12a_gap_<w>        max. output gap vs link bandwidth, the four methods (log-log; median, IQR whiskers)
fig12a_ttfo_<w>       TTFO-local vs link bandwidth, the four methods
fig12a_ready_cmp_bw250  the same split for dog and butterfly at 0.25 Gbps, side by side (where F12-H2 fails), with time and bytes
fig12a_ready_<w>      OTTER's time to the destination's first output split into Sink transfer / replay catch-up / switch
                      (stacked medians per bandwidth): where the Sink transfer stops being the bottleneck
Canvas and axes box of Fig. 7 / 8, style font sizes (never reduced); "Native" = unshaped link, drawn at x = 9.4 Gbps
(the Phase 0 measured single-NIC capacity) and labelled, not scaled.

Usage: python tools/eval/plot_fig12.py [--prefix _dryrun_]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from plot_fig7_migration import AXES_POS, BLUE, DARK_GRAY, DIM_GRAY, FIG_SIZE, LEGEND, ROOT, annotate, configure, finish_axes

# canvas and axes box of Fig. 7 / Fig. 8 (user 2026-11-03: Fig. 12a panels the same size as Fig. 8a, b)
BWS = (250, 500, 1000, 2500, 0)
X = {250: 0.25, 500: 0.5, 1000: 1.0, 2500: 2.5, 0: 9.4}
XT = ["0.25", "0.5", "1", "2.5", "Native"]
METHODS = ("full", "precopy_full", "recompute_full", "precopy_replay")
NAME = {"full": "Full", "precopy_full": "Llumnix", "recompute_full": "SLLM", "precopy_replay": "OTTER"}
STYLE = {"full": (DIM_GRAY, "s", (0, (5, 2))), "precopy_full": (DARK_GRAY, "D", (0, (2, 1.5))), "recompute_full": ("black", "^", (0, (6, 2, 1, 2))),
         "precopy_replay": (BLUE, "o", "-")}
WL = ("dog", "bfly")


def save(fig, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}.{{pdf,png}}")


def xaxis(ax):
    ax.set_xscale("log")
    ax.set_xlim(0.19, 13)
    ax.set_xticks([X[b] for b in BWS]); ax.set_xticklabels(XT)
    ax.minorticks_off()
    ax.set_xlabel("Bandwidth (Gbps; Native = unshaped)", fontsize=28, labelpad=2)   # user 2026-11-03


def lines(cells, w, key, ylabel, out):
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    ax.set_yscale("log")
    for m in METHODS:
        col, mk, ls = STYLE[m]
        pts = [(X[b], cells[f"{w}|{b}|{m}"][key]) for b in BWS if cells[f"{w}|{b}|{m}"][key]["median"] is not None]
        if not pts:
            continue
        xs = [p[0] for p in pts]; md = [p[1]["median"] for p in pts]
        lo = [p[1]["median"] - (p[1]["q1"] if p[1]["q1"] is not None else p[1]["median"]) for p in pts]
        hi = [(p[1]["q3"] if p[1]["q3"] is not None else p[1]["median"]) - p[1]["median"] for p in pts]
        ax.errorbar(xs, md, yerr=[lo, hi], color=col, ls=ls, lw=2.4 if m == "precopy_replay" else 1.8, marker=mk, ms=9,
                    mfc="white" if m != "precopy_replay" else col, mec=col, mew=1.6, capsize=3, zorder=4 if m == "precopy_replay" else 3)
    xaxis(ax)
    finish_axes(ax, ylabel)
    hs = [Line2D([], [], color=STYLE[m][0], ls=STYLE[m][2], marker=STYLE[m][1], ms=9, mfc="white" if m != "precopy_replay" else STYLE[m][0],
                 mec=STYLE[m][0], lw=2, label=NAME[m]) for m in METHODS]
    ax.legend(handles=hs, loc="upper right", frameon=False, fontsize=LEGEND, handlelength=1.6, handletextpad=0.3, labelspacing=0.15,
              borderaxespad=0.2, ncol=2, columnspacing=0.6)
    lo_, hi_ = ax.get_ylim()
    ax.set_ylim(lo_, hi_ * 30)   # room for the two-row legend above the data
    save(fig, out)


def ready(cells, w, out):
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    xs = list(range(len(BWS)))
    parts = []
    for b in BWS:
        bd = cells[f"{w}|{b}|precopy_replay"].get("breakdown") or {}
        s, c, f = (bd.get(k, {}).get("median") for k in ("sink_s", "caught_s", "first_s"))
        parts.append((s or 0, max(0, (c or 0) - (s or 0)), max(0, (f or 0) - (c or 0))))
    bottom = [0.0] * len(BWS)
    for i, (lab, col, hatch) in enumerate((("Sink transfer", BLUE, ""), ("Catch-up", "#9DB3F0", "//"), ("Switch", DARK_GRAY, ""))):
        vals = [p[i] for p in parts]
        ax.bar(xs, vals, 0.62, bottom=bottom, color=col, edgecolor="black", lw=1.2, hatch=hatch, zorder=3, label=lab)
        bottom = [a + v for a, v in zip(bottom, vals)]
    ax.set_xticks(xs); ax.set_xticklabels(XT)
    ax.set_xlim(-0.6, len(BWS) - 0.4)
    ax.set_xlabel("Bandwidth (Gbps)", fontsize=28, labelpad=2)
    finish_axes(ax, "Time (s)")
    ax.set_ylim(0, max(bottom + [1]) * 1.45)
    ax.legend(handles=[Patch(facecolor=BLUE, edgecolor="black", label="Sink transfer"), Patch(facecolor="#9DB3F0", edgecolor="black", hatch="//", label="Catch-up"),
                       Patch(facecolor=DARK_GRAY, edgecolor="black", label="Switch")], loc="upper right", frameon=False, fontsize=LEGEND,
              handlelength=1.2, handletextpad=0.3, labelspacing=0.15, borderaxespad=0.2)
    save(fig, out)


def ready_cmp(cells, b, out):
    """Same split for both workloads at one bandwidth (user request 2026-11-03: where F12-H2 fails, butterfly at
    0.25 Gbps, next to dog); each bar labelled with the time to the first output and OTTER's transmitted bytes."""
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    parts, tops = [], []
    for w in WL:
        bd = cells[f"{w}|{b}|precopy_replay"]["breakdown"]
        s, c, f = (bd[k]["median"] for k in ("sink_s", "caught_s", "first_s"))
        parts.append((s, max(0, c - s), max(0, f - c)))
        tops.append((f, cells[f"{w}|{b}|precopy_replay"]["tx_gb"]["median"], cells[f"{w}|{b}|precopy_replay"]["delivery_gap_s"]["median"]))
    bottom = [0.0] * len(WL)
    for i, (col, hatch) in enumerate(((BLUE, ""), ("#9DB3F0", "//"), (DARK_GRAY, ""))):
        vals = [p[i] for p in parts]
        ax.bar(range(len(WL)), vals, 0.42, bottom=bottom, color=col, edgecolor="black", lw=1.2, hatch=hatch, zorder=3)   # room for the middle label
        bottom = [a + v for a, v in zip(bottom, vals)]
    top = max(bottom) * 1.62
    # user 2026-11-03: show that the output gap stays the same while readiness grows (the catch-up ratio is in the caption)
    for x, (f, gb, gap) in enumerate(tops):
        annotate(ax, x, f + top * 0.02, f"{f:.0f} s\n{gb:.2f} GB\ngap {gap:.2f} s")
    annotate(ax, 0.5, max(t[0] for t in tops) * 0.62, "Gap\nunchanged", va="center")
    ax.set_xticks(range(len(WL))); ax.set_xticklabels(["Low-refresh", "High-refresh"])
    ax.set_xlim(-0.45, len(WL) - 0.55)   # the two 28 pt tick labels need the room
    ax.set_xlabel(f"Input at {X[b]:g} Gbps", fontsize=28, labelpad=2)
    finish_axes(ax, "Time (s)")
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, top)
    ax.legend(handles=[Patch(facecolor=BLUE, edgecolor="black", label="Sink transfer"), Patch(facecolor="#9DB3F0", edgecolor="black", hatch="//", label="Catch-up"),
                       Patch(facecolor=DARK_GRAY, edgecolor="black", label="Switch")], loc="upper left", frameon=False, fontsize=LEGEND,
              handlelength=1.2, handletextpad=0.3, labelspacing=0.15, borderaxespad=0.2)
    save(fig, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    configure()
    out = Path(a.out) if a.out else ROOT / f"results/evaluation/osdi/fig12/{a.prefix}figures"
    cells = json.load(open(ROOT / f"results/evaluation/osdi/fig12/{a.prefix}fig12_results.json"))["cells"]
    for w in WL:
        if not any(cells[f"{w}|{b}|{m}"]["n_valid"] for b in BWS for m in METHODS):
            continue
        lines(cells, w, "delivery_gap_s", "Max. output gap (s)", out / f"fig12a_gap_{w}")
        lines(cells, w, "ttfo_local_s", "TTFO-local (s)", out / f"fig12a_ttfo_{w}")
        ready(cells, w, out / f"fig12a_ready_{w}")
    if all(cells[f"{w}|250|precopy_replay"]["n_valid"] for w in WL):
        ready_cmp(cells, 250, out / "fig12a_ready_cmp_bw250")


if __name__ == "__main__":
    main()
