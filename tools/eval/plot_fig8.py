#!/usr/bin/env python3
"""Fig. 8a-b (osdi/fig8/preregistration.md section 8). Reads osdi/fig8/fig8_results.json (tools/eval/fig8_report.py).

fig8a_dog, fig8a_bfly   cumulative stall time (s) vs time since the trigger (s), one panel per workload (Low-refresh,
                        High-refresh); per method the rep with the median total stall as a thick step line, the other
                        reps thin and light; every curve ends at its run's last chunk (marked); total stall printed at the
                        end of each median curve. Re-analysis of the 40 Fig. 7 runs.
fig8b_throughput        steady-state throughput (frames/s) on host B: native upstream StreamDiffusionV2 vs OTTER with M2 +
                        M3 tracking (generation + tracking per call); bar = median, whisker = IQR, dots = reps.

Style: Fig. 7 (tools/eval/plot_fig7_migration.py, EC-LLM figure "e3"): OTTER blue, baselines gray.

Usage: python tools/eval/plot_fig8.py [--out results/evaluation/osdi/fig8/figures]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from plot_fig7_migration import (AXES_POS, AXES_POS_F9, FIG_SIZE_F9, BLUE, DARK_GRAY, DIM_GRAY, FIG_SIZE, LEGEND, METHODS, ROOT, TICK_LABEL, WL_LABEL,
                                 WORKLOADS, annotate, configure, finish_axes)

RESULTS = ROOT / "results/evaluation/osdi/fig8/fig8_results.json"
LINE = {"full": (DIM_GRAY, "-"), "precopy_full": (DARK_GRAY, (0, (5, 2))), "recompute_full": ("#3A3A3A", (0, (1.5, 1.5))),
        "precopy_replay": (BLUE, "-")}
LIM_A = ((0, 310), (0, 100))   # 85 -> 100 on fig9b_gap's narrower canvas: the 61.8 label clears the legend   # plotted ranges (readability only; every curve ends inside)
LIM_B = (0, 10.5)


def median_run(cell):
    med = cell["total_stall_s"]["median"]
    return min((r for r in cell["runs"] if r["valid"]), key=lambda r: abs(r["total_stall_s"] - med))


def save(fig, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}.{{pdf,png}}")


def panel_a(res, w, out: Path):
    fig = plt.figure(figsize=FIG_SIZE_F9)   # user 2026-11-04: fig9b_gap's canvas and plot box
    ax = fig.add_axes(AXES_POS_F9)
    (x0, x1), (y0, y1) = LIM_A
    rec = {}
    for m in METHODS:
        col, ls = LINE[m]
        cell = res[w][m]
        best = median_run(cell)
        for r in cell["runs"]:
            if not r["valid"]:
                continue
            t, s = np.array(r["curve"]).T
            assert t[-1] < x1 and s[-1] < y1, (w, m, t[-1], s[-1])
            main = r is best
            ax.step(t, s, where="post", color=col, ls=ls, lw=4.2 if main else 1.5, alpha=1 if main else 0.35, zorder=4 if main else 2)
            ax.plot(t[-1], s[-1], "o", ms=9 if main else 4, color=col, mec="black" if main else col, mew=1.0, alpha=1 if main else 0.35,
                    zorder=5 if main else 2)
        t_end, s_end = best["curve"][-1]
        txt = f"{cell['total_stall_s']['median']:.2f}" if s_end < 10 else f"{cell['total_stall_s']['median']:.1f}"
        if s_end < 10:   # near the axis floor: right of the end marker, clear of the other curves
            annotate(ax, t_end + x1 * 0.02, s_end + y1 * 0.005, txt, ha="left", va="bottom", zorder=6,
                     bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none", alpha=0.9))
        else:
            annotate(ax, t_end, s_end + y1 * 0.03, txt, ha="right" if t_end > 0.8 * x1 else "center")
        rec[m] = {"median_rep": best["rep"], "total_stall_s": cell["total_stall_s"]["median"], "t_end_s": t_end}
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    finish_axes(ax, "Cumulative stall (s)")
    ax.set_xlabel("Time since migration trigger (s)", fontsize=28, labelpad=2)
    ax.grid(axis="x", alpha=0.18, linewidth=0.7)
    ax.set_xticks([0, 100, 200, 300])
    ax.set_xticklabels(["", "100", "200", "300"])   # the y axis' 0 marks the corner
    hs = [Line2D([], [], color=LINE[m][0], ls=LINE[m][1], lw=4.2, label=TICK_LABEL[m]) for m in METHODS]
    ax.legend(handles=hs, loc="upper left", ncol=2, frameon=False, fontsize=LEGEND, handlelength=1.6, handletextpad=0.4,
              columnspacing=0.8, labelspacing=0.2, borderaxespad=0.3)
    save(fig, out)
    return rec


def panel_b(b, out: Path):
    fig = plt.figure(figsize=FIG_SIZE)
    ax = fig.add_axes(AXES_POS)
    W, OFF = 0.30, 0.20   # user 2026-11-03: narrower bars (0.36 before)
    rec = {}
    for i, w in enumerate(WORKLOADS):
        for j, (key, col, name) in enumerate((("native_B", DIM_GRAY, "Native"), ("otter_per_call", BLUE, "OTTER"))):
            s = b[w][key]
            fps = 4 / np.array(s["values"])   # time per call (4 frames) -> frames/s; median / IQR of the rep medians
            med, q1, q3 = 4 / s["median"], 4 / s["q3"], 4 / s["q1"]
            x = i + (j - 0.5) * 2 * OFF
            ax.bar(x, med, width=W, color=col, edgecolor="black", linewidth=1.2, zorder=3)
            ax.plot([x, x], [q1, q3], color="black", lw=1.6, zorder=4)
            ax.scatter(x + np.linspace(-0.08, 0.08, len(fps)), fps, s=16, color="black", edgecolor="white", lw=0.5, zorder=5)
            annotate(ax, x, max(fps.max(), q3) + LIM_B[1] * 0.02, f"{med:.2f}")
            rec[f"{w}_{name}"] = {"fps_median": med, "fps_q1": q1, "fps_q3": q3, "fps_reps": fps.tolist()}
    ax.set_ylim(*LIM_B)
    ax.set_yticks([0, 2.5, 5, 7.5, 10])
    ax.set_xlim(-0.6, len(WORKLOADS) - 0.4)
    ax.set_xticks(range(len(WORKLOADS)))
    ax.set_xticklabels([WL_LABEL[w] for w in WORKLOADS])
    finish_axes(ax, "Throughput (frames/s)")
    ax.tick_params(axis="x", length=0)
    hs = [Patch(fc=DIM_GRAY, ec="black", lw=1.2, label="Native"), Patch(fc=BLUE, ec="black", lw=1.2, label="OTTER")]
    ax.legend(handles=hs, loc="upper center", ncol=2, frameon=False, fontsize=LEGEND, handlelength=1.4, handletextpad=0.4,
              columnspacing=1.0, borderaxespad=0.3)
    save(fig, out)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results/evaluation/osdi/fig8/figures"))
    a = ap.parse_args()
    configure()
    out = Path(a.out)
    d = json.load(open(RESULTS))
    rec = {f"8a_{w}": panel_a(d["8a"], w, out / f"fig8a_{w}") for w in WORKLOADS}
    rec["8b"] = panel_b(d["8b"], out / "fig8b_throughput")
    out.mkdir(parents=True, exist_ok=True)
    json.dump(rec, open(out / "fig8_figures.data.json", "w"), indent=1)


if __name__ == "__main__":
    main()
