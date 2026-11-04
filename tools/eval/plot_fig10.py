#!/usr/bin/env python3
"""Fig. 10a-b (osdi/fig10/preregistration.md section 9). Reads osdi/fig10/fig10_results.json (tools/eval/fig10_report.py).

fig10a_bytes      Sink base transferred at the second migration (MB, log) vs version age: Versioned (M2, measured), Changed-block
                  (computed from the measured block sets), Full (measured); both workloads; refreshed entries annotated.
fig10b_readiness  destination readiness (s) vs version age: Full vs Versioned, plus Versioned base ready (dashed;
                  same start as readiness), both workloads.
Encoding: method by color / line style as Figs. 7-9 (Versioned blue solid, Changed-block gray dashed, Full light gray
solid); workload by marker (Low-refresh filled circle, High-refresh open triangle). Line = median, points = reps.
Canvas of Fig. 6a / Fig. 9.

Usage: python tools/eval/plot_fig10.py [--prefix _dryrun_]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from plot_fig7_migration import BLUE, DARK_GRAY, DIM_GRAY, LEGEND, ROOT, annotate, configure, finish_axes

FIG_SIZE = (5.83, 4.78)
AXES_POS = [0.18, 0.22, 0.79, 0.75]
AGES = (10, 60, 150, 240)
REALIGN = (19, 64, 109, 154, 199, 244)   # ages (calls after S1 = 74) of the realignments at calls 93, 138, ...
WL = {"dog": ("o", True, "Low-refresh"), "bfly": ("^", False, "High-refresh")}
BASE_LS = (0, (5, 2))   # 10b: Versioned base ready (same dash as Changed-block in 10a; color tells the method)
METHOD = {"ver": (BLUE, "-", "Versioned"), "chg": (DIM_GRAY, (0, (5, 2)), "Changed-block"), "full": (DARK_GRAY, "-", "Full")}


def save(fig, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}.{{pdf,png}}")


def series(C, w, arm, key, scale=1.0):
    xs, med, pts = [], [], []
    for a in AGES:
        s = C[f"{w}|{a}"][arm][key]
        if s["median"] is None:
            continue
        xs.append(a); med.append(s["median"] * scale); pts += [(a, v * scale) for v in s["values"]]
    return xs, med, pts


def draw(ax, xs, med, pts, col, ls, mk, filled, lw=3.4, z=4):   # user 2026-11-03: 2.4 -> 3.4
    ax.plot(xs, med, color=col, ls=ls, lw=lw, zorder=z)
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], marker=mk, s=60, facecolor=col if filled else "white", edgecolor=col, lw=1.6, zorder=z + 1)


def common(ax, ylabel):
    for a in REALIGN:
        ax.axvline(a, color="black", lw=0.6, alpha=0.18, zorder=0)
    ax.set_xlim(0, 255)
    ax.set_xticks(AGES)
    finish_axes(ax, ylabel)
    ax.set_xlabel("Version age (calls)", fontsize=28, labelpad=2)


def legend(ax, loc, methods=(), workloads=False, times=False):
    """Style-size legend (never smaller): 10a lists the methods (colors), 10b the workload markers and the two times
    (line style: readiness solid, base ready dashed)."""
    hs = [Line2D([], [], color=METHOD[k][0], ls=METHOD[k][1], lw=3.4, label=METHOD[k][2]) for k in methods]
    if times:
        hs += [Line2D([], [], color="black", ls=l, lw=3.4, label=t) for l, t in (("-", "Readiness"), (BASE_LS, "Base ready"))]
    if workloads:
        hs += [Line2D([], [], color="black", marker=WL[w][0], mfc="black" if WL[w][1] else "white", ls="none", ms=10, label=WL[w][2]) for w in WL]
    ax.legend(handles=hs, loc=loc, frameon=False, fontsize=LEGEND, handlelength=1.6, handletextpad=0.3, labelspacing=0.15, ncol=1, borderaxespad=0.2)


def panel_a(C, out: Path):
    fig = plt.figure(figsize=FIG_SIZE)
    ax = fig.add_axes(AXES_POS)
    ax.set_yscale("log")
    ys = []
    for w, (mk, filled, _) in WL.items():
        for key, m in (("base_bytes", "full"), ("changed_block_bytes", "chg"), ("base_bytes", "ver")):
            arm = "full" if m == "full" else "ver"
            xs, med, pts = series(C, w, arm, key, 1e-6)
            if not xs:
                continue
            col, ls, _ = METHOD[m]
            draw(ax, xs, med, pts, col, ls, mk, filled, z=5 if m == "ver" else 3)
            ys += med
            if m == "ver":   # refreshed entries at each age
                for a, y in zip(xs, med):
                    n = C[f"{w}|{a}"]["ver"]["refreshed_entries"]["median"]
                    if n is None:
                        continue
                    if w == "dog":
                        annotate(ax, a, y * 0.5, f"{n:.0f}", ha="center", va="center", color=BLUE)
                    else:   # High-refresh: below the point, clear of the Changed-block lines
                        first = a == xs[0]
                        annotate(ax, a + (-1.5 if first else 0 if a == xs[-1] else 7), y * (0.4 if first else 0.32), f"{n:.0f}", ha="center", va="center", color=BLUE)
    ax.set_ylim(0.1, 5000)   # top just above Full (1,727.6 MB); the legend goes to the empty bottom right
    ax.yaxis.set_major_locator(LogLocator(base=10, numticks=12))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"$10^{{{int(round(np.log10(v)))}}}$"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    common(ax, "Sink transferred (MB)")
    ax.yaxis.set_label_coords(-0.14, 0.5)
    legend(ax, "lower right", methods=("ver", "chg", "full"))
    save(fig, out)


def panel_b(C, out: Path):
    fig = plt.figure(figsize=FIG_SIZE)
    ax = fig.add_axes(AXES_POS)
    top = 0
    for w, (mk, filled, _) in WL.items():
        for arm in ("full", "ver"):
            xs, med, pts = series(C, w, arm, "readiness_s")
            if not xs:
                continue
            col, ls, _ = METHOD[arm]
            draw(ax, xs, med, pts, col, ls, mk, filled, z=5 if arm == "ver" else 3)
            top = max(top, max(p[1] for p in pts))
        # Versioned base ready (same start: the second migration's task start), below its readiness at every age
        xs, med, pts = series(C, w, "ver", "base_ready_s")
        if xs:
            draw(ax, xs, med, pts, BLUE, BASE_LS, mk, filled, z=4)
    ax.set_ylim(0, max(50, top * 2.0) if top else 1)   # headroom for the 4-row legend above Full
    common(ax, "Time (s)")
    legend(ax, "upper left", workloads=True, times=True)
    save(fig, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    configure()
    out = Path(a.out) if a.out else ROOT / f"results/evaluation/osdi/fig10/{a.prefix}figures"
    C = json.load(open(ROOT / f"results/evaluation/osdi/fig10/{a.prefix}fig10_results.json"))["cells"]
    panel_a(C, out / "fig10a_bytes")
    panel_b(C, out / "fig10b_readiness")


if __name__ == "__main__":
    main()
