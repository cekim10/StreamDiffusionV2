#!/usr/bin/env python3
"""Fig. 7a-c (osdi/fig7/preregistration.md section 10): single migration A -> B at call 30, 1 Gbps; Full, Llumnix-style
P-full, ServerlessLLM-style R-full and OTTER (M1 only). Reads osdi/fig7/fig7_results.json (tools/eval/fig7_report.py).

fig7a_ttfo        TTFO-local (s)
fig7b_gap         maximum output delivery gap (s)  (fig7b_gap_linear / fig7b_gap_log: both versions kept, section 10)
fig7c_bytes       transferred data (GB, measured harness bytes)

Marks: bar = median, whisker = IQR, dots = the 5 reps, median printed on each bar. Two bars per method: Low-refresh (dog,
solid) and High-refresh (butterfly, hatched). OTTER in the accent colour, baselines in grays. y axis: log by default; a
panel whose medians span less than one decade uses a linear axis (rule fixed before the runs).

Style: the EC-LLM evaluation figures (EC-LLM tools/plot_eval_figures.py, figure "e3", e.g.
summary_tables/eval_figures/fig_e3_tiered_layout_a_concentration.pdf): 7.70 x 4.80 in canvas saved without a tight bbox,
axes box [0.19, 0.20, 0.78, 0.73], 28 pt Times axis text, 19 pt italic DejaVu Sans values, 25 pt legend, y label at
x = -0.14, bars with 1.2 pt black edges, the BRIGHT palette (ours = blue).

Usage: python tools/eval/plot_fig7_migration.py [--out results/evaluation/osdi/fig7/figures]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results/evaluation/osdi/fig7/fig7_results.json"

# EC-LLM figure "e3" geometry and fonts
FIG_SIZE = (7.7, 4.8)
AXES_POS = [0.19, 0.20, 0.78, 0.73]
YLABEL_X = -0.14
LABEL, TICK, ANNOT, LEGEND = 28, 28, 19, 25
ANNOT_FONT = "DejaVu Sans"
BLUE, DIM_GRAY, DARK_GRAY = "#486EE2", "#696969", "#A9A9A9"   # EC-LLM BRIGHT_PALETTE

METHODS = ("full", "precopy_full", "recompute_full", "precopy_replay")   # prereg order
TICK_LABEL = {"full": "Full", "precopy_full": "Llumnix", "recompute_full": "SLLM", "precopy_replay": "OTTER"}
WORKLOADS = ("dog", "bfly")
WL_LABEL = {"dog": "Low-refresh", "bfly": "High-refresh"}
FILL = {m: (DIM_GRAY, DARK_GRAY) for m in METHODS[:3]}   # baselines: (dog, butterfly) grays
FILL["precopy_replay"] = (BLUE, "#9DB3F0")               # OTTER: accent
HATCH = {"dog": "", "bfly": "//"}
W, OFF = 0.42, 0.23
NUDGE = 0.04   # pair value labels pushed apart (x units) so 5-character labels of equal-height bars do not touch
PANELS = {   # key in fig7_results cells, y label, value format
    "ttfo": ("ttfo_local_s", "TTFO-local (s)", lambda v: f"{v:.0f}" if v >= 100 else f"{v:.1f}"),
    "gap": ("delivery_gap_s", "Max. output gap (s)", lambda v: f"{v:.2f}" if v < 10 else f"{v:.1f}"),
    "bytes": ("tx_gb", "Transferred data (GB)", lambda v: f"{v:.3f}" if v < 1 else f"{v:.2f}" if v < 10 else f"{v:.1f}"),
}
LIM = {("ttfo", "linear"): (0, 290), ("ttfo", "log"): (5, 900), ("gap", "linear"): (0, 72), ("gap", "log"): (0.5, 400),
       ("bytes", "linear"): (0, 33), ("bytes", "log"): (0.02, 250)}   # plotted ranges (readability only; data never clipped)


def configure():
    mpl.rcParams.update({
        "font.family": "Times New Roman", "mathtext.fontset": "stix", "axes.labelcolor": "black",
        "xtick.color": "black", "ytick.color": "black", "axes.linewidth": 2, "xtick.direction": "in",
        "ytick.direction": "in", "pdf.fonttype": 42, "ps.fonttype": 42, "hatch.linewidth": 1.0,
    })


def finish_axes(ax, ylabel):
    """EC-LLM paper_plot_style.finish_paper_axes + plot_eval_figures.style_axes."""
    ax.margins(x=0, y=0)
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_linewidth(2)
        ax.spines[side].set_visible(True)
    ax.tick_params(axis="y", direction="in", width=2, pad=2, length=5, labelsize=TICK)
    ax.tick_params(axis="x", direction="in", width=2, pad=7, length=5, labelsize=TICK)
    ax.grid(axis="y", alpha=0.18, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.yaxis.labelpad = 0.0
    ax.set_ylabel(ylabel, fontsize=LABEL)
    ax.yaxis.set_label_coords(YLABEL_X, 0.5)


def annotate(ax, x, y, text, **kw):
    kw.setdefault("ha", "center"); kw.setdefault("va", "bottom"); kw.setdefault("color", "black")
    ax.text(x, y, text, fontsize=kw.pop("fontsize", ANNOT), fontstyle="italic", fontfamily=ANNOT_FONT, **kw)


def scale_rule(cells, key):
    meds = [cells[w][m][key]["median"] for w in WORKLOADS for m in METHODS if cells[w][m][key]["n"]]
    span = max(meds) / min(meds)
    return ("log" if span >= 10 else "linear"), span


def panel(cells, name, scale, out: Path):
    key, ylabel, fmt = PANELS[name]
    lo, top = LIM[name, scale]
    fig = plt.figure(figsize=FIG_SIZE)
    ax = fig.add_axes(AXES_POS)
    ax.set_yscale(scale)
    hi_all = []
    for i, m in enumerate(METHODS):
        for j, w in enumerate(WORKLOADS):
            c = cells[w][m]
            x = i + (j - 0.5) * 2 * OFF
            s = c[key]
            if not s["n"]:   # failed cell: never a bar (section 10)
                annotate(ax, x, 0.5, f"n/a ({c['n_failed']})", transform=ax.get_xaxis_transform(), rotation=90, va="center")
                continue
            ax.bar(x, s["median"], width=W, color=FILL[m][j], hatch=HATCH[w], edgecolor="black", linewidth=1.2, zorder=3)
            ax.plot([x, x], [s["q1"], s["q3"]], color="black", lw=1.6, zorder=4)
            vals = s["values"]
            ax.scatter(x + np.linspace(-0.1, 0.1, len(vals)), vals, s=16, color="black", edgecolor="white", lw=0.5, zorder=5)
            hi = max(max(vals), s["q3"])
            hi_all.append(hi)
            annotate(ax, x + (2 * j - 1) * NUDGE, hi * 1.12 if scale == "log" else hi + top * 0.04, fmt(s["median"]))
    assert lo < min(cells[w][m][key]["q1"] for w in WORKLOADS for m in METHODS if cells[w][m][key]["n"]) and max(hi_all) < top, (name, scale)
    ax.set_ylim(lo, top)
    ax.set_xlim(-0.55, len(METHODS) - 0.45)
    ax.set_xticks(range(len(METHODS)))
    ax.set_xticklabels([TICK_LABEL[m] for m in METHODS])
    finish_axes(ax, ylabel)
    ax.tick_params(axis="x", length=0)
    if scale == "log":
        ax.yaxis.set_major_locator(LogLocator(base=10))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(NullFormatter())
    if name == "ttfo":
        hs = [Patch(fc=DIM_GRAY, ec="black", lw=1.2, label=WL_LABEL["dog"]),
              Patch(fc=DARK_GRAY, ec="black", lw=1.2, hatch="//", label=WL_LABEL["bfly"])]
        ax.legend(handles=hs, loc="upper right", frameon=False, fontsize=LEGEND, handlelength=1.4, handletextpad=0.4,
                  labelspacing=0.2, borderaxespad=0.3)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(f"  {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}.{{pdf,png}}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results/evaluation/osdi/fig7/figures"))
    a = ap.parse_args()
    configure()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cells = json.load(open(RESULTS))["cells"]
    rec = {}
    for name, stem in (("ttfo", "fig7a_ttfo"), ("gap", "fig7b_gap"), ("bytes", "fig7c_bytes")):
        scale, span = scale_rule(cells, PANELS[name][0])
        rec[name] = dict(scale=scale, median_span=round(span, 2), rule="log unless the panel's medians span < 1 decade")
        panel(cells, name, scale, out / stem)
        if name == "gap":   # both versions of panel b kept in the record
            for alt in ("linear", "log"):
                panel(cells, name, alt, out / f"{stem}_{alt}")
    json.dump(rec, open(out / "fig7_figures.data.json", "w"), indent=1)


if __name__ == "__main__":
    main()
