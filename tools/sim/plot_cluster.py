#!/usr/bin/env python3
"""Cluster-scale figure (osdi/fig_cluster/preregistration.md section 9). SIMULATED values (calibrated from measured
single migrations); the caption must say so. Reads osdi/fig_cluster/<prefix>sweep_<grid>.json.

figc_a_mobility   time with local service (%) vs user moves per hour, one line per method (other knobs at the
                  primary point)
figc_b_link       time without local service per move (s, mean incl. truncated moves) vs site link capacity (Gbps)
figc_c_budget     the same vs the per-site memory budget for retained / staged state (GB): Unstaged, OTTER, Replicate
figc_stalled      stalled seconds per session-hour vs user moves per hour (log y), same knobs as figc_a (added
                  2026-11-04 by the user's decision: plot only, from the frozen sweep; the paired view of figc_a)
figc_legend       the method legend as its own file (six entries do not fit a 28-pt plot box)
Canvas and axes box of Fig. 6a, fonts never reduced (28 / 19 / 25 pt), no internal mechanism names.

    python tools/sim/plot_cluster.py --prefix _smoke_ --grid smoke
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from plot_fig7_migration import BLUE, DARK_GRAY, DIM_GRAY, LEGEND, ROOT, configure, finish_axes  # noqa: E402

FIG_SIZE = (5.83, 4.78)
AXES_POS = [0.18, 0.22, 0.79, 0.75]
OUT = ROOT / "results/evaluation/osdi/fig_cluster"
LABEL = {"full": "Full", "pfull": "Llumnix", "rfull": "SLLM", "base": "Unstaged", "otter": "OTTER", "naive": "Replicate"}
STYLE = {"full": (DIM_GRAY, "s", "-"), "pfull": (DIM_GRAY, "^", "--"), "rfull": (DARK_GRAY, "D", ":"),
         "base": ("#9DB3F0", "o", "-"), "otter": (BLUE, "o", "-"), "naive": ("#E39B4B", "v", "-")}
PRIMARY = {"N": 64, "C_gbps": 10.0, "M_gb": 32.0, "dwell_s": 180.0}


def save(fig, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT)}.{{pdf,png}}")


def fixed(runs, key):
    vals = sorted({r["cfg"][key] for r in runs})
    return PRIMARY[key] if PRIMARY[key] in vals else vals[len(vals) // 2]


def series(runs, xkey, metric, methods):
    keys = [k for k in PRIMARY if k != xkey]
    fx = {k: fixed(runs, k) for k in keys}
    sel = [r for r in runs if all(r["cfg"][k] == v for k, v in fx.items())]
    out = {}
    for m in methods:
        pts = {}
        for r in sel:
            if r["method"] == m:
                pts.setdefault(r["cfg"][xkey], []).append(metric(r))
        out[m] = sorted((x, st.mean(v)) for x, v in pts.items())
    return out, fx


def ymax(ser):
    top = max((y for s in ser.values() for _, y in s if y == y), default=1.0)
    return 100.0 if top > 60 and top <= 100 else 1.15 * top


def panel(runs, xkey, metric, ylabel, xlabel, out, methods, xfmt=lambda x: x, logx=False, logy=False):
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    ser, fx = series(runs, xkey, metric, methods)
    xs = sorted({x for s in ser.values() for x, _ in s})
    for m, s in ser.items():
        if s:
            c, mk, ls = STYLE[m]
            ax.plot([xfmt(x) for x, _ in s], [y for _, y in s], color=c, marker=mk, ls=ls, lw=2.4, ms=10, mfc="white" if m != "otter" else c, mew=2, zorder=4 if m == "otter" else 3)
    if logx:
        ax.set_xscale("log")
    if logy:
        ax.set_yscale("log")
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ys = [y for s in ser.values() for _, y in s if y == y and y > 0]
        if ys:
            lo, hi = min(ys) / 1.3, max(ys) * 1.3
            ax.set_ylim(lo, hi)
            ax.yaxis.set_major_locator(FixedLocator([v for v in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000) if lo <= v <= hi]))
    else:
        ax.set_ylim(0, ymax(ser))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks([xfmt(x) for x in xs]); ax.set_xticklabels([f"{xfmt(x):g}" for x in xs])
    finish_axes(ax, ylabel)
    ax.set_xlabel(xlabel, fontsize=28, labelpad=2)
    ax.margins(x=0.06)
    save(fig, out)
    return fx


def legend(methods, out):
    fig = plt.figure(figsize=(11.0, 1.7))
    hs = [Line2D([], [], color=STYLE[m][0], marker=STYLE[m][1], ls=STYLE[m][2], lw=2.4, ms=10, mfc="white" if m != "otter" else STYLE[m][0], mew=2, label=LABEL[m]) for m in methods]
    fig.legend(handles=hs, loc="center", ncol=3, frameon=False, fontsize=LEGEND, handlelength=1.8, columnspacing=1.0)
    save(fig, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--grid", default="primary")
    a = ap.parse_args()
    configure()
    runs = json.loads((OUT / f"{a.prefix}sweep_{a.grid}.json").read_text())["runs"]
    methods = [m for m in LABEL if any(r["method"] == m for r in runs)]
    fd = OUT / f"{a.prefix}figures"
    local = lambda r: 100 * r["local_frac"]  # noqa: E731
    delay = lambda r: r["no_local_after_move_s"].get("mean", float("nan"))  # noqa: E731
    fa = panel(runs, "dwell_s", local, "Local service (%)", "Moves per hour", fd / "figc_a_mobility", methods, xfmt=lambda d: round(3600 / d), logx=True)
    fb = panel(runs, "C_gbps", delay, "Delay per move (s)", "Link capacity (Gbps)", fd / "figc_b_link", methods, logx=True, logy=True)
    stalled = lambda r: r.get("stalled_s_per_session_h", r["stall_frac"] * 3600)  # noqa: E731
    fs = panel(runs, "dwell_s", stalled, "Stalled s per session-h", "Moves per hour", fd / "figc_stalled", methods, xfmt=lambda d: round(3600 / d), logx=True, logy=True)
    fc = panel(runs, "M_gb", delay, "Delay per move (s)", "Memory budget (GB)", fd / "figc_c_budget", [m for m in ("base", "otter", "naive") if m in methods])
    legend(methods, fd / "figc_legend")
    print(f"  fixed knobs: a {fa}; stalled {fs}; b {fb}; c {fc}")


if __name__ == "__main__":
    main()
