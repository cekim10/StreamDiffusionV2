#!/usr/bin/env python3
"""Fig. 11a-b (osdi/fig11/preregistration.md section 9). Reads osdi/fig11/fig11_results.json (tools/eval/fig11_report.py).

fig11a_<scenario>   time without local service (s) per method, stacked: remote-served (lower, method color) and
                    interrupted (upper, darkened); Low-refresh solid, High-refresh hatched; median bars, reps as dots on
                    the total; "n.c." over a bar with a not-converged run.
fig11b_<scenario>   final readiness R_D (TTFO-local at D, s) per method; log if the medians span >= 1 decade (Fig. 7 rule).
Canvas of Fig. 6a / 9 / 10; OTTER blue, OTTER w/o staging light blue, external baselines gray.

Usage: python tools/eval/plot_fig11.py [--prefix _dryrun_]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from plot_fig7_migration import BLUE, DARK_GRAY, DIM_GRAY, HATCH, LEGEND, ROOT, WL_LABEL, WORKLOADS, annotate, configure, finish_axes

FIG_SIZE = (5.83, 4.78)
AXES_POS = [0.18, 0.22, 0.79, 0.75]   # the plot box of Fig. 6a
XTICK_ROT = 30
METHODS = ("full", "pfull", "rfull", "base", "otter")
TICK = {"full": "Full", "pfull": "Llumnix", "rfull": "SLLM", "base": "Unstaged", "otter": "OTTER"}   # short names: Fig. 6a plot box at 28 pt; no internal M-names (user)
FILL = {"full": DIM_GRAY, "pfull": DIM_GRAY, "rfull": DIM_GRAY, "base": "#9DB3F0", "otter": BLUE}
W, OFF = 0.36, 0.19


def save(fig, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}.{{pdf,png}}")


def dark(c, k=0.55):
    import matplotlib.colors as mc
    r, g, b = mc.to_rgb(c)
    return (r * k, g * k, b * k)


def base_axes(ylabel):
    fig = plt.figure(figsize=FIG_SIZE)
    ax = fig.add_axes(AXES_POS)
    return fig, ax


def finish(ax, ylabel):
    ax.set_xlim(-0.55, len(METHODS) - 0.45)
    ax.set_xticks(range(len(METHODS)))
    ax.set_xticklabels([TICK[m] for m in METHODS])
    finish_axes(ax, ylabel)
    ax.yaxis.set_label_coords(-0.155, 0.5)   # clear of three-digit ticks at 28 pt
    ax.tick_params(axis="x", length=0)
    plt.setp(ax.get_xticklabels(), rotation=XTICK_ROT, ha="right", rotation_mode="anchor")   # never a smaller font


def panel_a(C, sc, out: Path):
    fig, ax = base_axes("")
    top = 0
    for i, m in enumerate(METHODS):
        for j, w in enumerate(WORKLOADS):
            c = C[f"{sc}|{w}"][m]
            x = i + (j - 0.5) * 2 * OFF
            n, rem = c["N_s"], c["remote_served_s"]
            if not n["n"]:
                annotate(ax, x, 0.5, "n/a", transform=ax.get_xaxis_transform(), rotation=90, va="center"); continue
            r_, i_ = rem["median"], n["median"] - rem["median"]
            ax.bar(x, r_, width=W, color=FILL[m], hatch=HATCH[w], edgecolor="black", linewidth=1.0, zorder=3)
            ax.bar(x, max(i_, 0), bottom=r_, width=W, color=dark(FILL[m]), hatch=HATCH[w], edgecolor="black", linewidth=1.0, zorder=3)
            ax.scatter(x + np.linspace(-0.08, 0.08, len(n["values"])), n["values"], s=12, color="black", edgecolor="white", lw=0.4, zorder=5)
            hi = max(n["values"])
            top = max(top, hi)
            lab = ("\u2265" if n["median_censored"] else "") + (f"{n['median']:.0f}" if n["median"] >= 10 else f"{n['median']:.1f}")
            annotate(ax, x, hi * 1.02 + 2, lab + (" n.c." if c["n_not_converged"] else ""), rotation=90, va="bottom")   # >= : right-censored
    ax.set_ylim(0, top * 1.9 if top else 1)
    finish(ax, "Local-service delay (s)")
    hs = [Patch(fc="#BBBBBB", ec="black", label="remote-served"), Patch(fc=dark("#BBBBBB"), ec="black", label="interrupted")]
    ax.legend(handles=hs, loc="upper right", ncol=1, frameon=False, fontsize=LEGEND, handlelength=1.2, handletextpad=0.3, labelspacing=0.15, borderaxespad=0.2)
    save(fig, out)


def panel_b(C, sc, out: Path):
    fig, ax = base_axes("")
    meds = [C[f"{sc}|{w}"][m]["R_D_s"]["median"] for w in WORKLOADS for m in METHODS if C[f"{sc}|{w}"][m]["R_D_s"]["n"]]
    scale = "log" if meds and max(meds) / max(min(meds), 1e-9) >= 10 else "linear"
    ax.set_yscale(scale)
    top = 0
    for i, m in enumerate(METHODS):
        for j, w in enumerate(WORKLOADS):
            s = C[f"{sc}|{w}"][m]["R_D_s"]
            x = i + (j - 0.5) * 2 * OFF
            if not s["n"]:
                annotate(ax, x, 0.5, "n.c.", transform=ax.get_xaxis_transform(), rotation=90, va="center"); continue
            ax.bar(x, s["median"], width=W, color=FILL[m], hatch=HATCH[w], edgecolor="black", linewidth=1.0, zorder=3)
            ax.scatter(x + np.linspace(-0.08, 0.08, len(s["values"])), s["values"], s=12, color="black", edgecolor="white", lw=0.4, zorder=5)
            hi = max(s["values"]); top = max(top, hi)
            lab = ("\u2265" if s["median_censored"] else "") + f"{s['median']:.1f}"
            annotate(ax, x, hi * (1.15 if scale == "log" else 1.0) + (0 if scale == "log" else 1), lab, rotation=90, va="bottom")
    if scale == "log":
        ax.set_ylim(min(meds) / 3, top * 30)
        ax.yaxis.set_major_locator(LogLocator(base=10)); ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}")); ax.yaxis.set_minor_formatter(NullFormatter())
    else:
        ax.set_ylim(0, top * 1.9 if top else 1)
    finish(ax, "Final-edge readiness (s)")
    hs = [Patch(fc="white", ec="black", label=WL_LABEL["dog"]), Patch(fc="white", ec="black", hatch="//", label=WL_LABEL["bfly"])]
    ax.legend(handles=hs, loc="upper right", ncol=1, frameon=False, fontsize=LEGEND, handlelength=1.2, handletextpad=0.3, labelspacing=0.15, borderaxespad=0.2)
    save(fig, out)
    return scale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    configure()
    out = Path(a.out) if a.out else ROOT / f"results/evaluation/osdi/fig11/{a.prefix}figures"
    C = json.load(open(ROOT / f"results/evaluation/osdi/fig11/{a.prefix}fig11_results.json"))["cells"]
    for sc in ("chain", "cancel"):
        panel_a(C, sc, out / f"fig11a_{sc}")
        panel_b(C, sc, out / f"fig11b_{sc}")


if __name__ == "__main__":
    main()
