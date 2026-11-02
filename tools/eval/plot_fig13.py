#!/usr/bin/env python3
"""Fig. 13 (osdi/fig13/preregistration.md section 10). Reads osdi/fig13/fig13_results.json (tools/eval/fig13_report.py).

fig13a_time      PSNR vs k after the fixed cutover: OTTER median of the undiverged conditions with their min-max range,
                 each diverged condition as its own thin line, P-sink (S = 74) median dashed; windows W1 / W2 / W3 marked.
fig13b_inputs    W3 PSNR of every OTTER condition vs the input's refresh intensity (Fig. 5, log x): filled = Sink
                 schedule followed the reference, open = diverged. Inputs are named in the caption (no per-input ticks:
                 ten names do not fit at 28 pt).
fig13c_temporal  tPSNR (reference-relative temporal consistency) vs refresh intensity: boundary (k = 1, first frame)
                 and W3 median per condition.
Canvas and axes box of Fig. 6a, style font sizes (never reduced). Frame strips (13d) are made separately from re-runs.

Usage: python tools/eval/plot_fig13.py [--prefix _dryrun_]
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from plot_fig7_migration import BLUE, DARK_GRAY, DIM_GRAY, LEGEND, ROOT, configure, finish_axes

FIG_SIZE = (5.83, 4.78)
AXES_POS = [0.18, 0.22, 0.79, 0.75]
LIGHT_BLUE = "#9DB3F0"
REFRESH = {"dog": 3.6, "bird": 3.6, "boxing": 8.2, "basketball": 9.1, "hockey": 16.4, "swimmer": 22.7, "train": 34.5, "audi": 53.6,
           "circus": 89.1, "bfly": 128.2}


def save(fig, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}.{{pdf,png}}")


def legend(ax, hs, loc):
    ax.legend(handles=hs, loc=loc, frameon=False, fontsize=LEGEND, handlelength=1.6, handletextpad=0.3, labelspacing=0.15, borderaxespad=0.2)


def series(r):
    return {int(k): v for k, v in r["psnr"].items() if v is not None and 1 <= int(k) <= 100}


def panel_a(runs, out):
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    ot = [r for r in runs if r["method"] == "otter" and r["rep"] == 1 and r["valid"]]
    und = [series(r) for r in ot if not r["schedule_diverged"]]
    for r in ot:
        if r["schedule_diverged"]:
            s = series(r); ks = sorted(s)
            ax.plot(ks, [s[k] for k in ks], color=LIGHT_BLUE, lw=0.8, alpha=0.7, zorder=2)
    if und:
        ks = list(range(1, 101))
        med = [st.median([s[k] for s in und if k in s]) if any(k in s for s in und) else np.nan for k in ks]
        lo = [min([s[k] for s in und if k in s], default=np.nan) for k in ks]
        hi = [max([s[k] for s in und if k in s], default=np.nan) for k in ks]
        ax.fill_between(ks, lo, hi, color=BLUE, alpha=0.15, lw=0, zorder=1)
        ax.plot(ks, med, color=BLUE, lw=2.4, zorder=4)
    ps = [series(r) for r in runs if r["method"] == "psink" and r["valid"]]
    if ps:
        ks = list(range(1, 101))
        ax.plot(ks, [st.median([s[k] for s in ps if k in s]) if any(k in s for s in ps) else np.nan for k in ks], color=DIM_GRAY, ls=(0, (5, 2)), lw=2.4, zorder=3)
    for xb in (8.5, 24.5):
        ax.axvline(xb, color="black", lw=0.8, alpha=0.35, zorder=0)
    ax.set_xlim(-1, 105); ax.set_xticks([1, 25, 50, 75, 100])   # window edges (8 | 9, 24 | 25) are the vertical lines
    ax.set_ylim(15, 60)
    finish_axes(ax, "PSNR (dB)")
    ax.set_xlabel("Calls after the cutover", fontsize=28, labelpad=2)
    hs = [Line2D([], [], color=BLUE, lw=2.4, label="OTTER"), Line2D([], [], color=LIGHT_BLUE, lw=1.2, label="Diverged"),
          Line2D([], [], color=DIM_GRAY, ls=(0, (5, 2)), lw=2.4, label="No replay")]
    legend(ax, hs, "lower right")
    save(fig, out)


def scatter_vs_refresh(runs, key, ylabel, out, extra=None):
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    ax.set_xscale("log")
    rng = np.random.default_rng(0)
    ys = []
    for r in runs:
        if r["method"] != "otter" or r["rep"] != 1 or not r["valid"] or r.get(key) is None:
            continue
        x = REFRESH.get(r["input"], np.nan) * float(np.exp(rng.uniform(-0.06, 0.06)))   # jitter within an input
        div = r["schedule_diverged"]
        ax.scatter([x], [r[key]], s=40, marker="o", facecolor="white" if div else BLUE, edgecolor=BLUE, lw=1.4, zorder=4)
        ys.append(r[key])
        if extra is not None and r.get(extra) is not None:
            ax.scatter([x], [r[extra]], s=40, marker="^", facecolor="white", edgecolor=DARK_GRAY, lw=1.4, zorder=3)
            ys.append(r[extra])
    ax.axhline(40, color="black", lw=0.8, alpha=0.35, zorder=0)
    ax.set_xlim(2.5, 180)
    ax.set_xticks([3, 10, 30, 100]); ax.set_xticklabels(["3", "10", "30", "100"])
    ax.set_ylim(min(ys + [20]) - 5, max(ys + [50]) + 22)
    finish_axes(ax, ylabel)
    ax.set_xlabel("Refreshes per 100 calls", fontsize=28, labelpad=2)
    hs = [Line2D([], [], marker="o", ls="none", mfc=BLUE, mec=BLUE, ms=9, label="Schedule held"),
          Line2D([], [], marker="o", ls="none", mfc="white", mec=BLUE, ms=9, label="Diverged")]
    if extra is not None:
        hs.append(Line2D([], [], marker="^", ls="none", mfc="white", mec=DARK_GRAY, ms=9, label="Boundary"))
    legend(ax, hs, "upper right")
    save(fig, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    configure()
    out = Path(a.out) if a.out else ROOT / f"results/evaluation/osdi/fig13/{a.prefix}figures"
    runs = json.load(open(ROOT / f"results/evaluation/osdi/fig13/{a.prefix}fig13_results.json"))["runs"]
    panel_a(runs, out / "fig13a_time")
    scatter_vs_refresh(runs, "W3", "W3 PSNR (dB)", out / "fig13b_inputs")
    scatter_vs_refresh(runs, "t_W3", "tPSNR (dB)", out / "fig13c_temporal", extra="t_boundary")


if __name__ == "__main__":
    main()
