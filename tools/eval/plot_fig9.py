#!/usr/bin/env python3
"""Fig. 9a-c (osdi/fig9/preregistration.md section 9). Reads osdi/fig9/fig9_results.json (tools/eval/fig9_report.py).

fig9a_dog, fig9a_bfly   dirty bytes per pre-copy round (MB, log): P-full vs P-sink; the run with the median number of
                        rounds thick, the other reps thin; the stop-and-copy as an open marker after the last round;
                        the 256 MiB threshold dashed.
fig9b_gap               maximum output gap (s) per step: Wait-for-Sink, P-sink, OTTER w/o Sink sync, OTTER.
fig9c_psnr              PSNR of B's first 24 calls (median per run; dB) per step.
9b / 9c: bar = median, whisker = IQR, dots = reps, value printed; Low-refresh solid, High-refresh hatched; OTTER blue,
the other steps gray. 9b y axis: log unless the medians span < 1 decade (the Fig. 7 rule).

Usage: python tools/eval/plot_fig9.py [--prefix _dryrun_] [--out results/evaluation/osdi/fig9/figures]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from plot_fig7_migration import (BLUE, DARK_GRAY, DIM_GRAY, HATCH, LEGEND, OFF, ROOT, W, WL_LABEL, WORKLOADS, annotate, configure,
                                 finish_axes)

STEPS = ("wait", "psink", "nosync", "otter")
TICK = {"wait": "Wait", "psink": "P-sink", "nosync": "w/o sync", "otter": "OTTER"}   # short names: Fig. 6a plot box at 28 pt (caption spells them out)
FILL = {k: (DIM_GRAY, DARK_GRAY) for k in STEPS}
FILL["otter"] = (BLUE, "#9DB3F0")
LINE_A = {"pfull": ("#3A3A3A", "-", "o", "P-full"), "psink": (DARK_GRAY, (0, (5, 2)), "s", "P-sink")}
THRESHOLD_MB = 256 * 2**20 / 1e6
XTICK_ROT = 30   # narrow canvas: rotate the step names (never a smaller font)
# canvas and axes box of Fig. 6a (make_background_figures.F4_SIZE / F4_ADJUST: left 0.18, right 0.97, bottom 0.22, top 0.97),
# saved without a tight bbox so the page size matches
FIG_SIZE = (5.83, 4.78)
AXES_POS = [0.18, 0.22, 0.79, 0.75]
AXES_POS_BARS = AXES_POS   # (b), (c): the same plot box as Fig. 6a


def save(fig, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}.{{pdf,png}}")


def panel_a(C, w, out: Path):
    fig = plt.figure(figsize=FIG_SIZE)
    ax = fig.add_axes(AXES_POS)
    ax.set_yscale("log")
    xmax, rec, ys = 1, {}, []
    for k in ("pfull", "psink"):
        col, ls, mk, _ = LINE_A[k]
        runs = [r for r in C[w][k]["runs"] if r["valid"]]
        if not runs:
            continue
        n = sorted(len(r["rounds"]["dirty_bytes"]) for r in runs)
        med_n = n[(len(n) - 1) // 2]
        main = next(r for r in runs if len(r["rounds"]["dirty_bytes"]) == med_n)
        for r in runs:
            rd = np.array(r["rounds"]["dirty_bytes"]) / 1e6
            x = np.arange(1, len(rd) + 1)
            big = r is main
            kw = dict(color=col, alpha=1 if big else 0.35, zorder=4 if big else 2)
            ax.plot(x, rd, ls=ls, lw=3.0 if big else 1.0, marker=mk, ms=9 if big else 4, mec="black" if big else col, **kw)
            stop = r["rounds"]["stop_and_copy_bytes"] / 1e6
            ys += list(rd) + [stop]
            ax.plot([x[-1], x[-1] + 1], [rd[-1], stop], ls=":", lw=2.0 if big else 0.8, **kw)
            ax.plot(x[-1] + 1, stop, marker=mk, ms=11 if big else 5, mfc="white", mec=col, mew=2.0 if big else 1.0, ls="none", **kw)
            xmax = max(xmax, len(rd) + 1)
        rec[k] = {"median_rep": main["rep"], "rounds": len(main["rounds"]["dirty_bytes"]), "reason": main["rounds"]["switch_reason"]}
    ax.axhline(THRESHOLD_MB, color="black", ls=(0, (2, 2)), lw=1.2, zorder=1)
    annotate(ax, xmax + 0.4, THRESHOLD_MB * 1.15, "256 MiB", ha="right")
    ax.set_xlim(0.5, xmax + 0.5)
    lo, hi = 10 ** np.floor(np.log10(min(ys + [THRESHOLD_MB]) * 0.8)), max(ys) * 1000   # every point inside; headroom for the legend
    ax.set_ylim(lo, hi)
    ax.set_xticks(range(1, xmax + 1))
    ax.yaxis.set_major_locator(LogLocator(base=10, numticks=12))   # every decade labelled
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"$10^{{{int(round(np.log10(v)))}}}$"))   # narrow labels (Fig. 6a canvas)
    ax.yaxis.set_minor_formatter(NullFormatter())
    finish_axes(ax, "Dirty state (MB)")
    ax.yaxis.set_label_coords(-0.14, 0.5)
    ax.set_xlabel("Pre-copy round", fontsize=28, labelpad=2)
    hs = [Line2D([], [], color=LINE_A[k][0], ls=LINE_A[k][1], marker=LINE_A[k][2], lw=3.0, ms=9, mec="black", label=LINE_A[k][3]) for k in ("pfull", "psink")]
    hs.append(Line2D([], [], color="black", marker="o", mfc="white", ls="none", ms=10, label="Stop-and-copy"))
    ax.legend(handles=hs, loc="upper right", ncol=1, frameon=False, fontsize=LEGEND, handlelength=1.8, handletextpad=0.4, labelspacing=0.2,
              borderaxespad=0.3)
    save(fig, out)
    return rec


def bars(C, key, ylabel, fmt, scale, lim, out: Path, legend=True):
    fig = plt.figure(figsize=FIG_SIZE)
    ax = fig.add_axes(AXES_POS_BARS)
    ax.set_yscale(scale)
    lo, top = lim
    for i, k in enumerate(STEPS):
        for j, w in enumerate(WORKLOADS):
            s = C[w][k][key]
            x = i + (j - 0.5) * 2 * OFF
            if not s["n"]:
                annotate(ax, x, 0.5, "n/a", transform=ax.get_xaxis_transform(), rotation=90, va="center")
                continue
            ax.bar(x, s["median"], width=W, color=FILL[k][j], hatch=HATCH[w], edgecolor="black", linewidth=1.2, zorder=3)
            ax.plot([x, x], [s["q1"], s["q3"]], color="black", lw=1.6, zorder=4)
            vals = s["values"]
            ax.scatter(x + np.linspace(-0.1, 0.1, len(vals)), vals, s=16, color="black", edgecolor="white", lw=0.5, zorder=5)
            hi = max(max(vals), s["q3"])
            assert lo < min(vals) or scale == "linear", (key, k, w)
            assert hi < top, (key, k, w, hi, top)
            annotate(ax, x, hi * 1.12 if scale == "log" else hi + top * 0.02, fmt(s["median"]), rotation=90)   # vertical: no pair collisions
    ax.set_ylim(lo, top)
    ax.set_xlim(-0.55, len(STEPS) - 0.45)
    ax.set_xticks(range(len(STEPS)))
    ax.set_xticklabels([TICK[k] for k in STEPS])
    finish_axes(ax, ylabel)
    ax.tick_params(axis="x", length=0)
    plt.setp(ax.get_xticklabels(), rotation=XTICK_ROT, ha="right", rotation_mode="anchor")
    if scale == "log":
        ax.yaxis.set_major_locator(LogLocator(base=10))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(NullFormatter())
    if legend:
        hs = [Patch(fc=DIM_GRAY, ec="black", lw=1.2, label=WL_LABEL["dog"]), Patch(fc=DARK_GRAY, ec="black", lw=1.2, hatch="//", label=WL_LABEL["bfly"])]
        ax.legend(handles=hs, loc="upper right", ncol=1, frameon=False, fontsize=LEGEND, handlelength=1.4, handletextpad=0.4, labelspacing=0.2,
                  borderaxespad=0.3)
    save(fig, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    configure()
    out = Path(a.out) if a.out else ROOT / f"results/evaluation/osdi/fig9/{a.prefix}figures"
    C = json.load(open(ROOT / f"results/evaluation/osdi/fig9/{a.prefix}fig9_results.json"))["cells"]
    rec = {f"9a_{w}": panel_a(C, w, out / f"fig9a_{w}") for w in WORKLOADS}
    meds = [C[w][k]["delivery_gap_s"]["median"] for w in WORKLOADS for k in STEPS if C[w][k]["delivery_gap_s"]["n"]]
    scale = "log" if meds and max(meds) / min(meds) >= 10 else "linear"
    top = max(max(C[w][k]["delivery_gap_s"]["values"] or [0]) for w in WORKLOADS for k in STEPS)
    lim = (0.5, top * 8) if scale == "log" else (0, top * 1.7)   # vertical value labels + legend
    rec["9b"] = {"scale": scale, "median_span": round(max(meds) / min(meds), 2) if meds else None, "rule": "log unless the medians span < 1 decade"}
    bars(C, "delivery_gap_s", "Max. output gap (s)", lambda v: f"{v:.2f}" if v < 10 else f"{v:.1f}", scale, lim, out / "fig9b_gap")
    bars(C, "psnr_first24_median", "PSNR, first 24 calls (dB)", lambda v: f"{v:.1f}", "linear", (0, 62), out / "fig9c_psnr", legend=True)
    json.dump(rec, open(out / "fig9_figures.data.json", "w"), indent=1)


if __name__ == "__main__":
    main()
