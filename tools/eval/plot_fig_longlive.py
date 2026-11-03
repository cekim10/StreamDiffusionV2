#!/usr/bin/env python3
"""LongLive cross-model figures (osdi/longlive/m1_prereg.md; measured, 1 Gbps, one migration at call 120, 4 streams x 2
reps). Reads the run JSONs in osdi/longlive/migrate_m1/ (tools/longlive/ll_migrate_runs.py).

figll_a_gap       maximum output gap per method (median bar, the 8 runs as dots, value label): Full (stop-and-copy),
                  Recache (LongLive's own KV recache), OTTER (96-call replay).
figll_b_fidelity  PSNR of every post-cutover call vs the source's uninterrupted continuation: OTTER (bit-exact in every
                  run, drawn at the 99 dB cap = "Exact"), Recache and the 12-call replay (median, min-max band over the
                  8 runs). Full is bit-exact too (not drawn; caption).
Canvas and axes box of Fig. 6a, style font sizes (never reduced); no mechanism names.

Usage: python3.11 tools/eval/plot_fig_longlive.py
"""

from __future__ import annotations

import json
import statistics as st

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from plot_fig7_migration import ANNOT, BLUE, DARK_GRAY, DIM_GRAY, LEGEND, ROOT, annotate, configure, finish_axes

FIG_SIZE = (5.83, 4.78)
AXES_POS = [0.18, 0.22, 0.79, 0.75]
RUNS = ROOT / "results/evaluation/osdi/longlive/migrate_m1"
OUT = ROOT / "results/evaluation/osdi/longlive/figures"
ARMS = ("full", "recache", "otter_w96")
TICK = {"full": "Full", "recache": "Recache", "otter_w96": "OTTER"}
FILL = {"full": DIM_GRAY, "recache": DARK_GRAY, "otter_w96": BLUE}


def load():
    runs = {}
    for f in sorted(RUNS.glob("*.json")):
        runs.setdefault(f.name.split("_bw")[0], []).append(json.loads(f.read_text()))
    return runs


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig((OUT / name).with_suffix(".png"), dpi=300)
    fig.savefig((OUT / name).with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {(OUT / name).relative_to(ROOT)}.{{pdf,png}}")


def fig_gap(runs):
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    top = 60
    for i, arm in enumerate(ARMS):
        vals = [d["max_output_gap_s"] for d in runs[arm]]
        m = st.median(vals)
        ax.bar(i, m, width=0.6, color=FILL[arm], edgecolor="black", linewidth=1.2, zorder=3)
        ax.scatter(i + np.linspace(-0.12, 0.12, len(vals)), vals, s=16, color="black", edgecolor="white", lw=0.5, zorder=5)
        annotate(ax, i, max(vals) + top * 0.03, f"{m:.2f}" if m < 10 else f"{m:.1f}")
    assert max(d["max_output_gap_s"] for a in ARMS for d in runs[a]) < top * 0.9
    ax.set_ylim(0, top); ax.set_xlim(-0.55, len(ARMS) - 0.45)
    ax.set_xticks(range(len(ARMS))); ax.set_xticklabels([TICK[a] for a in ARMS])
    finish_axes(ax, "Max. output gap (s)")
    ax.tick_params(axis="x", length=0)
    save(fig, "figll_a_gap")


def fig_fidelity(runs):
    fig = plt.figure(figsize=FIG_SIZE); ax = fig.add_axes(AXES_POS)
    ks = list(range(1, 101))
    col = lambda arm: [[d["psnr_vs_shadow"][str(k)] for d in runs[arm]] for k in ks]  # noqa: E731
    for arm, color, ls in (("recache", DIM_GRAY, (0, (5, 2))), ("otter_w12", DARK_GRAY, "-")):
        c = col(arm)
        ax.fill_between(ks, [min(x) for x in c], [max(x) for x in c], color=color, alpha=0.18, lw=0, zorder=1)
        ax.plot(ks, [st.median(x) for x in c], color=color, ls=ls, lw=2.4, zorder=3)
    ot = col("otter_w96")
    assert all(v >= 99.0 for x in ot for v in x), "OTTER not bit-exact in every call: the 'Exact' line would be wrong"
    ax.plot(ks, [99.0] * len(ks), color=BLUE, lw=2.4, zorder=4)
    ax.set_xlim(-1, 105); ax.set_xticks([1, 25, 50, 75, 100])
    ax.set_ylim(10, 106)
    ax.set_yticks([20, 40, 60, 80, 99]); ax.set_yticklabels(["20", "40", "60", "80", "Exact"])
    finish_axes(ax, "PSNR (dB)")
    ax.set_xlabel("Calls after the cutover", fontsize=28, labelpad=2)
    hs = [Line2D([], [], color=BLUE, lw=2.4, label="OTTER"), Line2D([], [], color=DARK_GRAY, lw=2.4, label="12-call replay"),
          Line2D([], [], color=DIM_GRAY, ls=(0, (5, 2)), lw=2.4, label="Recache")]
    ax.legend(handles=hs, loc="center right", bbox_to_anchor=(1.0, 0.66), frameon=False, fontsize=LEGEND, handlelength=1.6,
              handletextpad=0.3, labelspacing=0.15, borderaxespad=0.2)
    save(fig, "figll_b_fidelity")


def main():
    configure()
    runs = load()
    assert all(len(runs[a]) == 8 for a in (*ARMS, "otter_w12")), {a: len(v) for a, v in runs.items()}
    fig_gap(runs)
    fig_fidelity(runs)


if __name__ == "__main__":
    main()
