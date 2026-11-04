#!/usr/bin/env python3
"""Fig. 14 (osdi/fig14/preregistration.md section 9, DRAFT). Reads osdi/fig14/fig14_results.json (tools/eval/fig14_report.py).

fig14a_overhead   per-call time increase (%) over the same loop's steady state: OTTER tracking inside the native loop
                  (track / native), the source during a transfer (Fig. 7 runs), the owner during staging (Fig. 11 runs);
                  two bars per group (Low-refresh solid, High-refresh hatched), median printed
fig14b1_gpu       single migration: Source and Destination, peak allocated GPU memory (GB); dashed = the source serving
                  without migration state. Low-refresh solid / High-refresh hatched
fig14b2_host      single migration: increase in process RSS (peak - first sample, GB); the retained Sink is drawn inside
                  the bar (part of the increase, not added). User 2026-11-03: RSS increase, not RSS peak (the peak
                  includes the harness's reference frames), and GPU / host in separate panels
fig14c_cluster    Chain (staging on): per node retained + staged Sink at the run end (GB, stacked), cluster total printed
Canvas and axes box of Fig. 6a, style font sizes (never reduced).

Usage: python tools/eval/plot_fig14.py [--prefix _dryrun_]
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from plot_fig7_migration import ANNOT, ANNOT_FONT, BLUE, DARK_GRAY, DIM_GRAY, LEGEND, ROOT, configure, finish_axes

FIG_SIZE = (5.83, 4.78)
AXES_POS = [0.18, 0.22, 0.79, 0.75]
LIGHT_BLUE = "#9DB3F0"
WL = ("dog", "bfly")


def save(fig, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}.{{pdf,png}}")


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def wl_legend(ax, loc="upper left"):
    ax.legend(handles=[Patch(facecolor=BLUE, edgecolor="black", label="Low-refresh"), Patch(facecolor=LIGHT_BLUE, edgecolor="black", hatch="//", label="High-refresh")],
              loc=loc, frameon=False, fontsize=LEGEND, handlelength=1.2, handletextpad=0.3, labelspacing=0.15, borderaxespad=0.2)


def overhead(res, out):
    nat, ph = res["native"], res["phases"]
    groups = ["Tracking", "Transfer", "Staging"]
    vals = {"Tracking": [nat["ratios"][w]["track/native"] for w in WL],
            "Transfer": [med([x["src_ratio"] for x in ph["transfer"] if x["workload"] == w]) for w in WL],
            "Staging": [med([x["ratio"] for x in ph["staging"] if x["workload"] == w]) for w in WL]}
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    top = 0.0
    for gi, g in enumerate(groups):
        for wi, w in enumerate(WL):
            v = vals[g][wi]
            if v is None:
                continue
            pct = 100 * (v - 1)
            x = gi + (-0.2 if wi == 0 else 0.2)
            ax.bar(x, pct, 0.38, color=BLUE if wi == 0 else LIGHT_BLUE, edgecolor="black", lw=1.2, hatch="" if wi == 0 else "//", zorder=3)
            ax.text(x, max(pct, 0) + 0.15, f"{pct:.1f}", ha="center", va="bottom", fontsize=ANNOT, fontfamily=ANNOT_FONT, style="italic", rotation=90)
            top = max(top, pct)
    ax.axhline(0, color="black", lw=1.0)
    ax.set_xticks(range(len(groups))); ax.set_xticklabels(groups)
    ax.set_xlim(-0.6, len(groups) - 0.4)
    finish_axes(ax, "Time per call (+%)")
    ax.set_ylim(min(0, ax.get_ylim()[0]), max(top * 2.2, 3))
    wl_legend(ax)
    save(fig, out)


def _single_bars(res, ax, value, extra=None):
    """Source (A) and Destination (B) of the single migrations, Low-refresh solid / High-refresh hatched (median of 3 reps)."""
    runs = {w: res["memory"].get(f"single|{w}") or [] for w in WL}
    top = 0.0
    for gi, lb in enumerate(("A", "B")):
        for wi, w in enumerate(WL):
            ns = [r["nodes"].get(lb) for r in runs[w] if r["nodes"].get(lb)]
            v = med([value(n) for n in ns]) if ns else None
            if v is None:
                continue
            x = gi + (-0.2 if wi == 0 else 0.2)
            ax.bar(x, v / 1024, 0.38, color=BLUE if wi == 0 else LIGHT_BLUE, edgecolor="black", lw=1.2, hatch="" if wi == 0 else "//", zorder=3)
            if extra:
                e = med([extra(n) for n in ns])
                if e:
                    ax.bar(x, e / 1024, 0.38, color="white", edgecolor="black", lw=1.2, hatch="xx", zorder=4)
            top = max(top, v / 1024)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["Source", "Destination"])
    ax.set_xlim(-0.6, 1.6)
    return top


def memory_gpu(res, out):
    """(b1) peak allocated GPU memory; dashed: the source's allocation while serving without migration state."""
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    top = _single_bars(res, ax, lambda n: n["gpu_alloc_peak_mb"])
    serving = med([r.get("src_serving_alloc_mb") for w in WL for r in res["memory"].get(f"single|{w}") or []])
    if serving:
        ax.axhline(serving / 1024, color="black", lw=2.0, ls="--", zorder=5)
    finish_axes(ax, "GPU peak (GB)")
    ax.set_ylim(0, max(top, 1) * 1.6)
    wl_legend(ax)
    save(fig, out)


def memory_host(res, out):
    """(b2) increase in process RSS over the run (peak - first sample); the retained Sink is part of it (not added)."""
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    top = _single_bars(res, ax, lambda n: n["rss_increase_mb"], extra=lambda n: n["retained_peak_mb"])
    finish_axes(ax, "RSS increase (GB)")
    ax.set_ylim(0, max(top, 1) * 1.75)
    ax.legend(handles=[Patch(facecolor=BLUE, edgecolor="black", label="Low-refresh"), Patch(facecolor=LIGHT_BLUE, edgecolor="black", hatch="//", label="High-refresh"),
                       Patch(facecolor="white", edgecolor="black", hatch="xx", label="Retained Sink")], loc="upper right", frameon=False, fontsize=LEGEND,
              handlelength=1.2, handletextpad=0.3, labelspacing=0.15, borderaxespad=0.2)
    save(fig, out)


def cluster(res, out):
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    labels = ("A", "B", "C", "D")
    top = 0.0
    for wi, w in enumerate(WL):
        runs = res["memory"].get(f"chain|{w}") or []
        if not runs:
            continue
        for li, lb in enumerate(labels):
            ns = [r["nodes"].get(lb) for r in runs if r["nodes"].get(lb)]
            ret = (med([n["retained_end_mb"] for n in ns]) or 0) / 1024
            stg = (med([n["staged_end_mb"] for n in ns]) or 0) / 1024
            x = li + (-0.2 if wi == 0 else 0.2)
            ax.bar(x, ret, 0.38, color=BLUE if wi == 0 else LIGHT_BLUE, edgecolor="black", lw=1.2, hatch="" if wi == 0 else "//", zorder=3)
            ax.bar(x, stg, 0.38, bottom=ret, color="white", edgecolor="black", lw=1.2, hatch="xx", zorder=3)
            top = max(top, ret + stg)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels)
    ax.set_xlim(-0.6, len(labels) - 0.4)
    ax.set_xlabel("Node", fontsize=28, labelpad=2)
    finish_axes(ax, "Held Sink (GB)")
    ax.set_ylim(0, max(top, 0.5) * 1.6)
    ax.legend(handles=[Patch(facecolor=BLUE, edgecolor="black", label="Retained"), Patch(facecolor="white", edgecolor="black", hatch="xx", label="Staged")],
              loc="upper left", frameon=False, fontsize=LEGEND, handlelength=1.2, handletextpad=0.3, labelspacing=0.15, borderaxespad=0.2, ncol=2)
    save(fig, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    configure()
    out = Path(a.out) if a.out else ROOT / f"results/evaluation/osdi/fig14/{a.prefix}figures"
    res = json.load(open(ROOT / f"results/evaluation/osdi/fig14/{a.prefix}fig14_results.json"))
    overhead(res, out / "fig14a_overhead")
    memory_gpu(res, out / "fig14b1_gpu")
    memory_host(res, out / "fig14b2_host")
    cluster(res, out / "fig14c_cluster")


if __name__ == "__main__":
    main()
