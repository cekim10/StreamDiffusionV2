#!/usr/bin/env python3
"""E9 sensitivity to cluster size and load (osdi/fig_cluster/scaling_protocol.md, G6). SIMULATED, PRELIMINARY (Sink delta
beyond 240 calls extrapolated); the caption must say so, and must not call this an end-to-end scalability proof (the
model's core never congests).

Figure A (load, 128 GPUs): x = sessions per GPU; one file per panel and link capacity:
    figs_load_stalled_c<C>, figs_load_local_c<C>
Figure B (cluster size, 8 GPUs per site; 256 GPUs left out, G5): x = GPUs; one file per panel and load:
    figs_size_stalled_rho<50|94>, figs_size_local_rho<50|94>
Medians over seeds. Style, canvas and fonts of plot_cluster.py (never reduced); legend: figc_legend from plot_cluster.

    python3.11 tools/sim/plot_scaling.py --prefix prelim_
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_cluster import AXES_POS, FIG_SIZE, LABEL, OUT, STYLE, legend, save  # noqa: E402
from plot_cluster import configure, finish_axes  # noqa: E402

STALLED = lambda r: r.get("stalled_s_per_session_h", r["stall_frac"] * 3600)  # noqa: E731
LOCAL = lambda r: 100 * r["local_frac"]  # noqa: E731


def med_series(runs, xf, metric, methods):
    out = {}
    for m in methods:
        pts = {}
        for r in runs:
            if r["method"] == m:
                pts.setdefault(xf(r), []).append(metric(r))
        out[m] = sorted((x, st.median(v)) for x, v in pts.items())
    return out


def panel(ser, ylabel, xlabel, out, xticks, xfmt, logx=False, logy=False):
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    for m, s in ser.items():
        if s:
            c, mk, ls = STYLE[m]
            ax.plot([x for x, _ in s], [y for _, y in s], color=c, marker=mk, ls=ls, lw=2.4, ms=10, mfc="white" if m != "otter" else c, mew=2,
                    zorder=4 if m == "otter" else 3)
    if logx:
        ax.set_xscale("log", base=2)
    if logy:
        ax.set_yscale("log")
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:g}k" if v >= 1000 else f"{v:g}"))
        ys = [y for s in ser.values() for _, y in s if y == y and y > 0]
        nice = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000)
        lo = max([v for v in nice if v <= min(ys) / 1.15] or [min(ys) / 1.3])   # down to a labelled tick
        hi = max(ys) * 1.3
        ax.set_ylim(lo, hi)
        ax.yaxis.set_major_locator(FixedLocator([v for v in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000) if lo <= v <= hi]))
    else:
        ax.set_ylim(0, 100)
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks(xticks); ax.set_xticklabels([xfmt(x) for x in xticks])   # fewer labels instead of smaller fonts
    finish_axes(ax, ylabel)
    ax.set_xlabel(xlabel, fontsize=28, labelpad=2)
    ax.margins(x=0.06)
    save(fig, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="prelim_")
    a = ap.parse_args()
    configure()
    fd = OUT / f"{a.prefix}figures"
    load = json.loads((OUT / f"{a.prefix}sweep_load.json").read_text())["runs"]
    methods = [m for m in LABEL if any(r["method"] == m for r in load)]
    for C in sorted({r["cfg"]["C_gbps"] for r in load}, reverse=True):
        rs = [r for r in load if r["cfg"]["C_gbps"] == C]
        xf = lambda r: r["cfg"]["N"] / (r["cfg"]["E"] * r["cfg"]["G"])  # noqa: E731
        xt = [x for x in sorted({xf(r) for r in rs}) if x in (0.25, 0.5, 0.75) or x == max(xf(r) for r in rs)]   # markers at every N
        fmt = lambda x: f"{x:.2f}".rstrip("0").rstrip(".")  # noqa: E731
        panel(med_series(rs, xf, STALLED, methods), "Stalled s per session-h", "Sessions per GPU", fd / f"figs_load_stalled_c{C:g}", xt, fmt, logy=True)
        panel(med_series(rs, xf, LOCAL, methods), "Local service (%)", "Sessions per GPU", fd / f"figs_load_local_c{C:g}", xt, fmt)
    size = [r for r in json.loads((OUT / f"{a.prefix}sweep_scale.json").read_text())["runs"] if r["cfg"]["E"] * r["cfg"]["G"] <= 128]
    for rho in (0.5, 0.94):
        rs = [r for r in size if abs(r["cfg"]["N"] - int(rho * r["cfg"]["E"] * r["cfg"]["G"])) < 1e-9]
        xf = lambda r: r["cfg"]["E"] * r["cfg"]["G"]  # noqa: E731
        xt = sorted({xf(r) for r in rs})
        panel(med_series(rs, xf, STALLED, methods), "Stalled s per session-h", "GPUs", fd / f"figs_size_stalled_rho{round(100 * rho)}", xt, lambda x: f"{x:g}", logx=True, logy=True)
        panel(med_series(rs, xf, LOCAL, methods), "Local service (%)", "GPUs", fd / f"figs_size_local_rho{round(100 * rho)}", xt, lambda x: f"{x:g}", logx=True)
    legend(methods, fd / "figc_legend")


if __name__ == "__main__":
    main()
