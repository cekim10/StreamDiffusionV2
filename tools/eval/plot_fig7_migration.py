#!/usr/bin/env python3
"""Fig. 7a-c (osdi/fig7/preregistration.md section 10): single migration A -> B at call 30, 1 Gbps; Full, Llumnix-style
P-full, ServerlessLLM-style R-full and OTTER (M1 only). Reads osdi/fig7/fig7_results.json (tools/eval/fig7_report.py).

fig7a_ttfo        TTFO-local (s)
fig7b_gap         delivery gap (s)                 (fig7b_gap_linear / fig7b_gap_log: both versions kept, section 10)
fig7c_bytes       transmitted bytes (GB, measured harness bytes)

Marks: bar = median, whisker = IQR, dots = the 5 reps, median printed on each bar. Two bars per method: Low-refresh (dog,
solid) and High-refresh (butterfly, hatched). OTTER in the accent colour, baselines in grays. y axis: log by default; a
panel whose medians span less than one decade uses a linear axis (rule fixed before the runs). Style: the m123 Background
figures (tools/make_background_figures.py F4_*).

Usage: python tools/eval/plot_fig7_migration.py [--out results/evaluation/osdi/fig7/figures]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import make_background_figures as mb  # noqa: E402

RESULTS = ROOT / "results/evaluation/osdi/fig7/fig7_results.json"
METHODS = ("full", "precopy_full", "recompute_full", "precopy_replay")   # prereg order
TICK = {"full": "Full", "precopy_full": "Llumnix", "recompute_full": "SLLM", "precopy_replay": "OTTER"}
WORKLOADS = ("dog", "bfly")
WL_LABEL = {"dog": "Low-refresh", "bfly": "High-refresh"}
FILL = {m: ("#7A7A7A", "#C8C8C8") for m in METHODS[:3]}          # baselines: (dog, butterfly) grays
FILL["precopy_replay"] = (mb.F4_RED, "#EFA3A3")                  # OTTER: accent
HATCH = {"dog": None, "bfly": "///"}
W, OFF = 0.36, 0.2
LEFT = 0.22   # wider than F4_ADJUST's 0.18: the log axes' tick labels (0.1, 100) need the room; same in all three panels
PANELS = {   # key in fig7_results cells, y label, value format
    "ttfo": ("ttfo_local_s", "TTFO-local (s)", lambda v: f"{v:.1f}"),
    "gap": ("delivery_gap_s", "Delivery gap (s)", lambda v: f"{v:.2f}" if v < 10 else f"{v:.1f}"),
    "bytes": ("tx_gb", "Bytes (GB)", lambda v: f"{v:.3f}" if v < 1 else f"{v:.2f}"),
}


def scale_rule(cells, key):
    meds = [cells[w][m][key]["median"] for w in WORKLOADS for m in METHODS if cells[w][m][key]["n"]]
    span = max(meds) / min(meds)
    return ("log" if span >= 10 else "linear"), span


def panel(cells, name, scale, out: Path):
    key, ylabel, fmt = PANELS[name]
    fig = plt.figure(figsize=mb.F4_SIZE)
    A = mb.F4_ADJUST
    ax = fig.add_axes([LEFT, A["bottom"], A["right"] - LEFT, A["top"] - A["bottom"]])
    hi_all = []
    for i, m in enumerate(METHODS):
        for j, w in enumerate(WORKLOADS):
            c = cells[w][m]
            x = i + (j - 0.5) * 2 * OFF
            s = c[key]
            if not s["n"]:   # failed cell: never a bar (section 10)
                ax.text(x, 0.5, f"n/a ({c['n_failed']})", transform=ax.get_xaxis_transform(), rotation=90, ha="center", va="center", fontsize=16)
                continue
            ax.bar(x, s["median"], width=W, color=FILL[m][j], hatch=HATCH[w], edgecolor="black", lw=1.0, zorder=2)
            ax.plot([x, x], [s["q1"], s["q3"]], color="black", lw=1.6, zorder=4)
            vals = s["values"]
            jit = np.linspace(-0.09, 0.09, len(vals))
            ax.scatter(x + jit, vals, s=14, color="black", edgecolor="white", lw=0.5, zorder=5)
            hi = max(max(vals), s["q3"])
            hi_all.append(hi)
            y = hi * 1.4 if scale == "log" else hi + 0.035 * LIM[name, scale][1]
            mb._f4_label(ax, x, y, fmt(s["median"]), mb.F4_VALUE - 2, rotation=90, va="bottom")
    ax.set_yscale(scale)
    lo, top = LIM[name, scale]
    assert lo < min(cells[w][m][key]["q1"] for w in WORKLOADS for m in METHODS if cells[w][m][key]["n"]) and max(hi_all) < top, (name, scale)
    ax.set_ylim(lo, top)
    ax.set_xlim(-0.6, len(METHODS) - 0.4)
    mb._f4_axes(ax, "", ylabel)
    ax.yaxis.set_label_coords(-0.2, 0.5)
    ax.set_xticks(range(len(METHODS)))
    ax.set_xticklabels([TICK[m] for m in METHODS], fontsize=23)
    ax.tick_params(axis="x", length=0)
    if scale == "log":
        ax.yaxis.set_major_locator(mpl.ticker.LogLocator(base=10))
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(mpl.ticker.NullFormatter())
    if name == "ttfo":
        hs = [mpl.patches.Patch(fc="#7A7A7A", ec="black", label=WL_LABEL["dog"]),
              mpl.patches.Patch(fc="#C8C8C8", ec="black", hatch="///", label=WL_LABEL["bfly"])]
        ax.legend(handles=hs, loc="upper right", bbox_to_anchor=(1.0, 1.0), ncol=1,
                  **{"frameon": False, "fontsize": 21, "handlelength": 1.2, "handletextpad": 0.4, "labelspacing": 0.15, "borderaxespad": 0.3})
    mb.save(fig, out, tight=False)


LIM = {("ttfo", "linear"): (0, 320), ("ttfo", "log"): (5, 900), ("gap", "linear"): (0, 75), ("gap", "log"): (0.5, 400),
       ("bytes", "linear"): (0, 34), ("bytes", "log"): (0.02, 300)}   # plotted ranges (readability only; data never clipped)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results/evaluation/osdi/fig7/figures"))
    a = ap.parse_args()
    mb.configure_matplotlib()
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
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
