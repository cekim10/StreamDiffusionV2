#!/usr/bin/env python3
"""Figure 2: execution-state size and migration criticality in StreamDiffusionV2.

(a) one stacked bar of the per-session execution state, colored by temporal role, with a zoomed inset of
    the immediate component (too small to see at full scale);
(b) state each migration objective must move, on a log axis.

Byte counts are read from a frozen Phase 1 (v3) FullMigration run, which serialized and transferred every
component (results/evaluation/single_handoff/policy=full_bw=native_rep=1_*/summary.json, bytes_fg_by_comp).
Nothing is hardcoded except the role assignment. Units are binary (MiB = 2^20 B, GiB = 2^30 B).

    python tools/make_state_size_figure.py
"""

from __future__ import annotations

import csv
import glob
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import ConnectionPatch, Patch  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results/state_migration/figures"
MiB, GiB = 2.0 ** 20, 2.0 ** 30

# temporal-role colors (validated: OKLab x100 separation >= 8.8 under protan/deutan/tritan simulation)
RED, RED_LIGHT, BLUE, GRAY, GRAY_LIGHT = "#e34948", "#f2a5a4", "#2a78d6", "#8c8b86", "#c9c8c3"
INK, INK_2, INK_3 = "#1f1f1e", "#55544f", "#8a8984"

plt.rcParams.update({"font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5, "legend.fontsize": 8, "pdf.fonttype": 42, "ps.fonttype": 42,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": INK_3, "xtick.color": INK_2, "ytick.color": INK_2,
                     "axes.labelcolor": INK_2, "text.color": INK})


def load_bytes() -> tuple[dict, str]:
    runs = sorted(glob.glob(str(REPO / "results/evaluation/single_handoff/policy=full_bw=native_rep=1_*/summary.json")))
    if not runs:
        raise SystemExit("no frozen Phase 1 FullMigration run found")
    s = json.load(open(runs[0]))
    return s["bytes_fg_by_comp"], Path(runs[0]).parent.name


def fmt(b: float) -> str:
    return f"{b / GiB:.2f} GiB" if b >= 0.1 * GiB else f"{b / MiB:.2f} MiB"


def main():
    comp, src = load_bytes()
    inflight, meta = comp["inflight"], comp["meta"]
    immediate = inflight + meta
    sink, recent, vae = comp["sink"], comp["recent"], comp["vae"]
    total = immediate + sink + recent + vae
    durable, ephemeral = sink, recent + vae
    pct = lambda b: 100.0 * b / total  # noqa: E731

    fig = plt.figure(figsize=(7.0, 4.15))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.25, 1.1], hspace=0.72, left=0.225, right=0.975, top=0.70, bottom=0.10)
    ax = fig.add_subplot(gs[0]); bx = fig.add_subplot(gs[1])

    # ---------------------------------------------------------------- (a) stacked breakdown
    segs = [("Immediate", "in-flight + metadata", immediate, RED), ("Durable", "Sink KV", sink, BLUE),
            ("Ephemeral", "Recent KV", recent, GRAY), ("Ephemeral", "Streaming VAE caches", vae, GRAY_LIGHT)]
    left, h = 0.0, 0.62
    for role, name, b, c in segs:
        ax.barh(0, b / GiB, left=left / GiB, height=h, color=c, edgecolor="white", linewidth=1.6)
        if b > 0.1 * GiB:
            dark = c in (BLUE, GRAY)
            ax.text((left + b / 2) / GiB, 0, f"{name}\n{fmt(b)} ({pct(b):.1f}%)", ha="center", va="center", fontsize=7.6,
                    color="white" if dark else INK)
        left += b
    ax.set_xlim(0, total / GiB); ax.set_ylim(-0.55, 0.55)
    ax.set_yticks([0]); ax.set_yticklabels([f"StreamDiffusionV2\nsession state\n({fmt(total)})"], fontsize=8, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("execution-state size (GiB)")
    ax.grid(axis="x", color="#e6e5e1", lw=0.6); ax.set_axisbelow(True)
    # brackets naming the role of each span (the two grays are both Ephemeral)
    def bracket(x0, x1, label, color):
        y = 0.37
        ax.plot([x0, x0, x1, x1], [y, y + 0.06, y + 0.06, y], color=color, lw=0.9, clip_on=False)
        ax.text((x0 + x1) / 2, y + 0.09, label, ha="center", va="bottom", fontsize=7.4, color=color, clip_on=False,
                bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
    bracket((immediate + 0.004 * GiB) / GiB, (immediate + sink) / GiB - 0.01, f"Durable {fmt(durable)}", BLUE)
    bracket((immediate + sink) / GiB + 0.01, total / GiB - 0.004, f"Ephemeral {fmt(ephemeral)}", INK_2)
    fig.text(0.012, 0.975, "(a) Execution-state breakdown by temporal role", ha="left", va="top", fontsize=9)

    # inset: the immediate component at MiB scale (placed above the bar, connected to the sliver at x=0)
    ix = ax.inset_axes([0.0, 1.45, 0.36, 0.26])
    ix.barh(0, inflight / MiB, height=0.6, color=RED, edgecolor="white", linewidth=1.2)
    ix.barh(0, meta / MiB, left=inflight / MiB, height=0.6, color=RED_LIGHT, edgecolor="white", linewidth=1.2)
    ix.set_xlim(0, immediate / MiB); ix.set_ylim(-0.32, 0.32); ix.set_yticks([])
    ix.tick_params(axis="x", labelsize=6.5, length=2, pad=1)
    for sp in ("left", "top", "right"):
        ix.spines[sp].set_visible(False)
    ix.text(inflight / MiB / 2, 0.36, f"in-flight rows {inflight / MiB:.2f} MiB", ha="left", va="bottom", fontsize=6.6, color=INK, clip_on=False)
    ix.text((inflight + meta / 2) / MiB, 0, f"metadata  {meta / MiB:.2f} MiB", ha="center", va="center", fontsize=6.6, color=INK)
    ix.text(immediate / MiB * 1.02, 0, f"= Immediate {immediate / MiB:.2f} MiB ({pct(immediate):.2f}%)\n   zoomed: invisible at full scale", ha="left", va="center", fontsize=7.0, color=RED, clip_on=False)
    ix.set_xticks([0, 1, 2]); ix.set_xticklabels(["0", "1", "2 MiB"])
    for xa, xb in ((0, 0), (immediate / GiB, immediate / MiB)):
        ax.add_artist(ConnectionPatch(xyA=(xa, h / 2), coordsA=ax.transData, xyB=(xb, -0.3), coordsB=ix.transData, color=RED, lw=0.7, ls=(0, (2, 2)), zorder=0))

    handles = [Patch(color=RED, label=f"Immediate  {pct(immediate):.2f}%"), Patch(color=BLUE, label=f"Durable  {pct(durable):.1f}%"),
               Patch(color=GRAY, label=f"Ephemeral  {pct(ephemeral):.1f}%")]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.985, 0.995), ncol=3, frameon=False, handlelength=1.1, columnspacing=1.2, fontsize=7.6)

    # ---------------------------------------------------------------- (b) state per migration objective (log)
    objectives = [("Full-state migration\n(all roles)", total, GRAY),
                  ("Continuity-preserving\n(Immediate + Durable)", immediate + durable, BLUE),
                  ("Immediate execution\nhandoff (Immediate)", immediate, RED)]
    ys = [2, 1, 0]
    for y, (name, b, c) in zip(ys, objectives):
        bx.barh(y, b / MiB, left=0.5, height=0.56, color=c, edgecolor="white", linewidth=1.2)
        ratio = total / b
        note = fmt(b) + ("" if ratio < 1.01 else f"   ({ratio:,.0f}× smaller than full state)" if ratio >= 10 else f"   ({ratio:.1f}× smaller)")
        bx.text(b / MiB * 1.3, y, note, ha="left", va="center", fontsize=7.6, color=INK)
    bx.set_xscale("log"); bx.set_xlim(0.5, 1.2e5)
    ticks = [1, 10, 100, 1024, 10 * 1024]
    bx.set_xticks(ticks); bx.set_xticklabels(["1 MiB", "10 MiB", "100 MiB", "1 GiB", "10 GiB"])
    bx.minorticks_off()
    bx.set_yticks(ys); bx.set_yticklabels([o[0] for o in objectives], fontsize=7.6, color=INK, linespacing=1.05); bx.tick_params(axis="y", length=0)
    bx.set_ylim(-0.55, 2.55)
    bx.set_xlabel("state that must reach the destination (log scale)")
    bx.grid(axis="x", color="#e6e5e1", lw=0.6); bx.set_axisbelow(True)
    bx.spines["left"].set_visible(False)
    bx.set_title("(b) State required by each migration objective", loc="left", x=-0.255, pad=7)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig2_state_size.pdf"); fig.savefig(OUT / "fig2_state_size.png", dpi=220)
    with open(OUT / "fig2_state_size_data.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["component", "temporal_role", "bytes", "MiB", "percent_of_total", "source_run"])
        for comp_name, role, b in (("in-flight denoising rows", "Immediate", inflight), ("metadata (ring/positions/timestep/last_image)", "Immediate", meta),
                                   ("Sink KV", "Durable", sink), ("Recent KV", "Ephemeral", recent), ("Streaming VAE caches (enc+dec)", "Ephemeral", vae)):
            w.writerow([comp_name, role, b, f"{b / MiB:.3f}", f"{pct(b):.4f}", src])
        w.writerow(["TOTAL", "", total, f"{total / MiB:.3f}", "100", src])
    print(f"source: {src}")
    print(f"immediate {immediate / MiB:.2f} MiB ({pct(immediate):.3f}%), durable {durable / GiB:.3f} GiB ({pct(durable):.1f}%), "
          f"ephemeral {ephemeral / GiB:.3f} GiB ({pct(ephemeral):.1f}%), total {total / GiB:.3f} GiB = {total / 1e9:.2f} GB (decimal)")
    print(f"full / immediate = {total / immediate:,.0f}x ; full / (immediate + durable) = {total / (immediate + durable):.2f}x")
    print(f"-> {OUT / 'fig2_state_size.png'}")


if __name__ == "__main__":
    main()
