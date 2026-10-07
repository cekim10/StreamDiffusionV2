#!/usr/bin/env python3
"""Background & Motivation figures from the raw experiment records.

Fig. 2  State is temporally heterogeneous      <- results/state_migration/gen/original_s0_k2/ablation_raw.csv
Fig. 3  Continuity can be late-bound           <- results/state_migration/mechanism/ablation_raw.csv
Fig. 4  Mobility outruns continuity transfer   <- results/state_migration/mobility/mob_{restart,relay,direct}_tm*.json
Usage: python tools/make_motivation_figures.py [--out results/state_migration/figures]
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
C = {"inflight": "#d62728", "recent": "#1f77b4", "vae": "#2ca02c", "sink": "#7f7f7f", "d1": "#1f77b4", "d4": "#ff7f0e", "d16": "#9467bd",
     "restart": "#d62728", "relay": "#ff7f0e", "direct": "#2ca02c"}
plt.rcParams.update({"font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9, "legend.fontsize": 8, "figure.dpi": 150,
                     "axes.spines.top": False, "axes.spines.right": False})


def curves(raw: Path, cfgs: list[str], cap: float = 50.0) -> dict[str, tuple[list[int], list[float]]]:
    by: dict[str, dict[int, list[float]]] = {c: {} for c in cfgs}
    with open(raw) as fh:
        for r in csv.DictReader(fh):
            if r["config"] in by and r["psnr"]:
                by[r["config"]].setdefault(int(r["rel_call"]), []).append(min(float(r["psnr"]), cap))
    return {c: (sorted(d), [st.mean(d[k]) for k in sorted(d)]) for c, d in by.items()}


# ----------------------------------------------------------------------------- Fig. 2
def fig2(out: Path):
    raw = ROOT / "results/state_migration/gen/original_s0_k2/ablation_raw.csv"
    cv = curves(raw, ["drop_inflight", "drop_kv_recent", "drop_vae_all", "ph_localrefresh"])
    fig, (ax, tx) = plt.subplots(1, 2, figsize=(7.0, 2.7), gridspec_kw={"width_ratios": [1.55, 1.0]})
    spec = [("drop_kv_recent", "No recent KV (1.6 GB)", C["recent"], "-"),
            ("drop_vae_all", "No VAE caches (2.9 GB)", C["vae"], "-"),
            ("drop_inflight", "No in-flight row (0.2 MB)", C["inflight"], "-"),
            ("ph_localrefresh", "No sink KV (1.6 GB)", C["sink"], "-")]
    for cfg, label, col, ls in spec:
        x, y = cv[cfg]
        ax.plot(x, y, ls, color=col, lw=1.6, label=label)
    ax.axhline(50, color="k", lw=0.6, ls=":")
    ax.text(39.5, 50.6, "identical to uninterrupted run", ha="right", va="bottom", fontsize=7, color="k")
    ax.set_xlabel("Chunks after migration")
    ax.set_ylabel("PSNR to uninterrupted execution (dB)")
    ax.set_xlim(0, 39); ax.set_ylim(8, 53)
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("(a) Continuity after losing one state component", loc="left")
    # (b) size vs semantics table
    tx.axis("off")
    rows = [("In-flight row", "0.2 MB", "Immediate"), ("Metadata", "~2 MB", "Immediate"), ("Sink KV", "1.6 GB", "Durable"),
            ("Recent KV", "1.6 GB", "Ephemeral"), ("VAE caches", "2.9 GB", "Ephemeral")]
    tbl = tx.table(cellText=[list(r) for r in rows], colLabels=["State", "Size (k=2)", "Semantics"], loc="center", cellLoc="left", colLoc="left")
    tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1.0, 1.25)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#bbbbbb")
        if r == 0:
            cell.set_text_props(weight="bold")
        elif c == 2:
            cell.set_text_props(color={"Immediate": C["inflight"], "Durable": C["sink"], "Ephemeral": C["recent"]}[rows[r - 1][2]])
    tx.set_title("(b) Size ≠ importance", loc="left")
    fig.tight_layout()
    fig.savefig(out / "fig2_state_semantics.pdf"); fig.savefig(out / "fig2_state_semantics.png"); plt.close(fig)


# ----------------------------------------------------------------------------- Fig. 3
def fig3(out: Path):
    raw = ROOT / "results/state_migration/mechanism/ablation_raw.csv"
    cv = curves(raw, ["ph_zero_1", "ph_zero_4", "ph_zero_16", "ph_zero_noswap"])
    fig, ax = plt.subplots(figsize=(4.6, 2.7))
    for cfg, label, col, d in [("ph_zero_1", "Sink arrives after 1 chunk", C["d1"], 1), ("ph_zero_4", "Sink arrives after 4 chunks", C["d4"], 4),
                               ("ph_zero_16", "Sink arrives after 16 chunks", C["d16"], 16)]:
        x, y = cv[cfg]
        ax.plot(x, y, color=col, lw=1.6, label=label)
        ax.axvline(d, color=col, lw=0.8, ls="--", alpha=0.8)
    x, y = cv["ph_zero_noswap"]
    ax.plot(x, y, color=C["sink"], lw=1.6, label="Sink never arrives")
    ax.axhline(50, color="k", lw=0.6, ls=":")
    ax.text(39.5, 50.6, "sink never lost: identical", ha="right", va="bottom", fontsize=7)
    ax.annotate("execution resumes\nwithout the sink", xy=(0.4, 28.3), xytext=(10.5, 24.0), fontsize=7, ha="left",
                arrowprops=dict(arrowstyle="->", lw=0.7))
    ax.set_xlabel("Chunks after migration"); ax.set_ylabel("PSNR to uninterrupted execution (dB)")
    ax.set_xlim(0, 39); ax.set_ylim(8, 53)
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("Durable state can bind late and still rejoin the original trajectory", loc="left", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(out / "fig3_late_binding.pdf"); fig.savefig(out / "fig3_late_binding.png"); plt.close(fig)


# ----------------------------------------------------------------------------- Fig. 4
def mobility_points(pol: str):
    d = ROOT / "results/state_migration/mobility"
    pts = []
    for tm in (1, 2, 4, 8, 16, 24, 32):
        f = d / f"mob_{pol}_tm{tm}.json"
        if not f.exists():
            f = d / f"mob_{pol}_tm{tm}_h2.json"
        if not f.exists():
            continue
        r = json.load(open(f))
        ready = r.get("t_ready_final", r.get("t_ready_C"))
        last_move = r["moves"][-1]["t"] if r.get("moves") else r.get("t_move")
        pts.append((tm, None if ready is None else ready - last_move))
    return pts


def fig4(out: Path, t_s: float = 16.6):
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(7.2, 2.8), gridspec_kw={"width_ratios": [1.15, 1.0]})
    # (a) timeline illustration
    ax0.axis("off"); ax0.set_xlim(0, 10); ax0.set_ylim(0, 6)

    def lane(y, label):
        ax0.text(-0.1, y, label, ha="right", va="center", fontsize=7.5)

    def arrow(x0, x1, y, color, lw=1.3, ls="-", double=False):
        ax0.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle="-|>", mutation_scale=7, lw=lw, color=color, linestyle=ls))

    # rho < 1
    ax0.text(0.0, 5.6, r"$\rho<1$: state keeps up", fontsize=8, weight="bold")
    lane(4.9, "execution"); lane(4.1, "sink")
    for x0, x1, n in [(0, 3.6, "A→B"), (3.9, 7.5, "B→C")]:
        arrow(x0, x1, 4.9, "#333333"); ax0.text((x0 + x1) / 2, 5.1, n, ha="center", fontsize=6.5)
    arrow(0, 2.4, 4.1, C["sink"], lw=2.2); ax0.text(2.5, 4.1, "✓", color="#2ca02c", va="center", fontsize=8)
    arrow(3.9, 6.3, 4.1, C["sink"], lw=2.2); ax0.text(6.4, 4.1, "✓", color="#2ca02c", va="center", fontsize=8)
    # rho > 1
    ax0.text(0.0, 2.9, r"$\rho>1$: execution outruns state", fontsize=8, weight="bold")
    lane(2.2, "execution"); lane(1.4, "sink")
    for x0, x1, n in [(0, 1.6, "A→B"), (1.9, 3.5, "B→C"), (3.8, 5.4, "C→D")]:
        arrow(x0, x1, 2.2, "#333333"); ax0.text((x0 + x1) / 2, 2.4, n, ha="center", fontsize=6.5)
    arrow(0, 4.6, 1.4, C["sink"], lw=2.2); ax0.text(4.75, 1.4, "✗ B already left", color=C["restart"], va="center", fontsize=7)
    ax0.text(0.0, 0.55, "restart: discard progress, start over   |   relay: keep progress, keep the stale route", fontsize=6.8, color="#444444")
    ax0.set_title("(a) Mobility interval $T_m$ vs. durable-state transfer time $T_s$", loc="left")
    # (b) measured
    for pol, label, col, mk in [("restart", "Restart", C["restart"], "s"), ("relay", "Relay", C["relay"], "^"), ("direct", "Oracle direct", C["direct"], "o")]:
        pts = [(tm, y) for tm, y in mobility_points(pol) if y is not None]
        xs = [t_s / tm for tm, _ in pts]; ys = [y for _, y in pts]
        ax1.plot(xs, ys, marker=mk, ms=4, lw=1.5, color=col, label=label)
    ax1.axvline(1.0, color="k", lw=0.8, ls="--"); ax1.axvspan(1.0, 20, color="#f0f0f0", zorder=0)
    ax1.text(3.0, 2.0, "execution outruns\ncontinuity state", fontsize=7, va="bottom", ha="left", color="#444444")
    ax1.set_xscale("log"); ax1.set_xlim(0.45, 20)
    ax1.set_xticks([0.5, 1, 2, 4, 8, 16]); ax1.set_xticklabels(["0.5", "1", "2", "4", "8", "16"])
    ax1.set_xlabel(r"$\rho = T_s / T_m$"); ax1.set_ylabel("Continuity-ready latency\nafter the final move (s)")
    ax1.set_ylim(-1, 38)
    ax1.legend(loc="upper left", frameon=False, bbox_to_anchor=(0.0, 1.02))
    ax1.set_title("(b) Measured, A→B→C at 1 Gbps", loc="left")
    fig.tight_layout()
    fig.savefig(out / "fig4_mobility.pdf"); fig.savefig(out / "fig4_mobility.png"); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default=str(ROOT / "results/state_migration/figures"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fig2(out); fig3(out); fig4(out)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
