#!/usr/bin/env python3
"""Design overview, architecture view (draft v3, 2026-11-04, per user): the three mechanisms are three components of the
OTTER runtime that runs on every edge server (CAKE layout: stacked server cards, GPU on top, runtime below, peers on the
right). Continuity Wavefront is a runtime component; its cross-server work is shown by the flows to the peer servers.

Components (rows, each with its section tag, layer and four steps):
  4.2 Continuity Replay              input & cache-event log -> shadow replay -> Sink K/V patches -> final sync
  4.3 Versioned Sink Reconstruction  version tracking -> ordered RoPE shift -> refreshed K/V fetch -> digest check
  4.4 Continuity Wavefront           retained Sink pool -> valid in owner lineage? -> proactive staging -> supply at handoff
Flows as in the Design overview text: 1 tracking, 2 retention / staging with holders, 3 migration request (user moves),
4a Sink reconstruction, 4b replay, 5 final sync, verify, resume. Conceptual, no measured data.
Canvas and fonts of plot_design_arch.py (14 x 6.3 in, figure*; 17 / 15 / 13.5 pt).

    python3.11 tools/eval/plot_design_arch_v3.py [--out figures/design]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INK = "black"
GPU_FC, RT_FC, PEER_FC, SUB_FC = "#D9D9D9", "#FFE699", "#E7E7E7", "#F4F4F4"
PURPLE, ORANGE, BLUE, TEAL, GRAY, RED, GREEN = "#8A5CC9", "#E08A2C", "#3D6FD1", "#2A9D8F", "#9A9A9A", "#C0392B", "#3E9B57"
FS_T, FS, FS_S = 17, 15, 13.5
W, XM, YM = 14.0, 222.0, 100.0


def rbox(ax, x0, y0, x1, y1, fc="white", ec=INK, lw=1.3, r=1.0, z=2):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z))


def box(ax, x0, y0, x1, y1, text, fs=FS_S - 1, z=4):
    rbox(ax, x0, y0, x1, y1, fc="white", lw=1.2, r=0.8, z=z)
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, text, ha="center", va="center", fontsize=fs, zorder=z + 1, linespacing=1.12)


def arrow(ax, p0, p1, lw=2.2, ls="-", ms=16, z=8, color=INK, style="-|>"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=ms, color=color, lw=lw, ls=ls, zorder=z,
                                 shrinkA=0, shrinkB=0))


def path(ax, pts, lw=2.2, ls="-", ms=16, z=8, color=INK):
    for (a, b), (c, d) in zip(pts[:-2], pts[1:-1]):
        ax.plot([a, c], [b, d], color=color, lw=lw, ls=ls, zorder=z, solid_capstyle="butt")
    arrow(ax, pts[-2], pts[-1], lw=lw, ls=ls, ms=ms, z=z, color=color)


def num(ax, x, y, label, color=INK):
    ax.text(x, y, label, ha="center", va="center", fontsize=FS_T, fontweight="bold", zorder=12, color=color,
            bbox=dict(boxstyle="circle,pad=0.12" if len(label) == 1 else "round,pad=0.18,rounding_size=0.9",
                      fc="white", ec=color, lw=1.4))


def tag(ax, x, y, sec, title):
    ax.text(x, y, f" {sec} ", ha="left", va="center", fontsize=FS, fontweight="bold", color="white", zorder=7,
            bbox=dict(boxstyle="round,pad=0.25,rounding_size=0.6", fc=INK, ec="none"))
    ax.text(x + 9.2, y, title, ha="left", va="center", fontsize=FS_T - 0.5, fontweight="bold", zorder=7)


def squares(ax, x, y, cols, s=3.2, z=6):
    for i, c in enumerate(cols):
        ax.add_patch(Rectangle((x + i * s, y), s, s, fc=c, ec=INK, lw=0.8, zorder=z))


def server(ax, x, y, w=11.6, h=7.6, cols=(), z=5):
    rbox(ax, x, y, x + w, y + h, fc="white", lw=1.2, r=0.8, z=z)
    for k in range(2):
        ax.plot([x + 1.5, x + w - 1.5], [y + 2.4 + k * 2.2, y + 2.4 + k * 2.2], color=GRAY, lw=1.2, zorder=z + 1)
    if cols:
        squares(ax, x + (w - 2.6 * len(cols)) / 2, y + h - 3.3, cols, s=2.6, z=z + 1)


def fig(out: Path):
    f = plt.figure(figsize=(W, W * YM / XM))
    ax = f.add_axes([0, 0, 1, 1]); ax.set_xlim(0, XM); ax.set_ylim(0, YM); ax.axis("off")

    # stacked edge-server cards: the runtime runs on every server
    for (dx, dy, lab) in ((10.0, 10.0, "Edge Server N"), (5.0, 5.0, "Edge Server B")):
        ax.add_patch(Rectangle((dx, dy), 158.0, 89.6, fc="white", ec=INK, lw=1.2, zorder=0))
        ax.text(dx + 2.0, dy + 89.6 - 2.5, lab, ha="left", va="center", fontsize=FS, fontweight="bold", zorder=1)
    ax.add_patch(Rectangle((0, 0.4), 158.0, 89.6, fc="white", ec=INK, lw=1.2, zorder=1))
    ax.text(2.0, 87.4, "Edge Server A", ha="left", va="center", fontsize=FS, fontweight="bold", zorder=2)

    # GPU / VRAM
    rbox(ax, 4.0, 70.5, 154.0, 84.8, fc=GPU_FC, lw=1.3, r=1.4, z=2)
    ax.text(6.0, 82.0, "GPU / VRAM", ha="left", va="center", fontsize=FS, fontweight="bold", zorder=4)
    box(ax, 28.0, 72.0, 54.0, 80.0, "Streaming\ndiffusion worker", fs=FS_S)
    ax.text(104.0, 82.0, "Session state", ha="center", va="center", fontsize=FS, zorder=4)
    for x, lab, cols in ((66.0, "Sink KV", [PURPLE] * 3), (88.0, "Recent KV", [ORANGE] * 3),
                         (110.0, "VAE caches", [GRAY] * 3), (131.0, "In-flight", ["#5B5B5B"])):
        ax.text(x + 1.6 * len(cols), 78.4, lab, ha="center", va="center", fontsize=FS_S, zorder=4)
        squares(ax, x, 72.8, cols)
    ax.text(146.0, 74.4, "...", ha="center", va="center", fontsize=FS, zorder=4)

    # OTTER runtime: three components
    rbox(ax, 3.0, 2.0, 155.0, 67.0, fc=RT_FC, lw=1.3, r=1.6, z=2)
    ax.text(62.0, 64.2, "OTTER Runtime", ha="left", va="center", fontsize=FS_T + 1, fontweight="bold", zorder=4)
    xs, bw = [20.0, 54.0, 88.0, 122.0], 29.0

    def component(y0, y1, sec, title, layer):
        rbox(ax, 16.0, y0, 153.0, y1, fc="white", lw=1.2, r=0.4, z=3)
        tag(ax, 17.5, y1 - 3.0, sec, title)
        ax.text(151.4, y1 - 3.0, layer, ha="right", va="center", fontsize=FS_S, style="italic", color="#555555", zorder=5)

    def chain(y0, y1, labels):
        for i, t in enumerate(labels):
            box(ax, xs[i], y0, xs[i] + bw, y1, t)
            if i:
                arrow(ax, (xs[i - 1] + bw, (y0 + y1) / 2), (xs[i], (y0 + y1) / 2), lw=1.4, ms=10)

    component(43.5, 61.0, "§4.2", "Continuity Replay", "execution layer")
    chain(45.3, 54.0, ["Input & Cache-\nEvent Log", "Shadow\nReplay", "Sink K/V\nPatches", "Final Sync"])
    component(23.5, 41.0, "§4.3", "Versioned Sink Reconstruction", "state representation layer")
    chain(25.3, 34.0, ["Version\nTracking", "Ordered\nRoPE Shift", "Refreshed\nK/V Fetch", "Digest\nCheck"])
    component(3.5, 21.0, "§4.4", "Continuity Wavefront", "cluster coordination layer")
    yc = 9.6
    box(ax, xs[0], 5.3, xs[0] + bw, 14.0, "Retained\nSink Pool")
    cx, hw, hh = xs[1] + bw / 2, 15.0, 5.0
    ax.add_patch(Polygon([(cx - hw, yc), (cx, yc + hh), (cx + hw, yc), (cx, yc - hh)], closed=True, fc="white", ec=INK,
                         lw=1.2, zorder=4))
    ax.text(cx, yc, "Valid in owner\nlineage?", ha="center", va="center", fontsize=FS_S - 1.5, zorder=5, linespacing=1.05)
    box(ax, xs[2], 5.3, xs[2] + bw, 14.0, "Proactive\nStaging")
    box(ax, xs[3], 5.3, xs[3] + bw, 14.0, "Supply at\nHandoff")
    arrow(ax, (xs[0] + bw, yc), (cx - hw, yc), lw=1.4, ms=10)
    arrow(ax, (cx + hw, yc), (xs[2], yc), lw=1.4, ms=10)
    arrow(ax, (xs[2] + bw, yc), (xs[3], yc), lw=1.4, ms=10)
    ax.text((cx + hw + xs[2]) / 2, yc + 1.2, "yes", ha="center", va="bottom", fontsize=FS_S - 1.5, zorder=5)

    # migration request (3): the user moves; it starts 4.2 and 4.3
    rbox(ax, 5.0, 23.5, 13.5, 61.0, fc="white", lw=1.5, r=0.6, z=3)
    ax.text(9.25, 38.0, "Migration\nRequest", ha="center", va="center", fontsize=FS_S, fontweight="bold", rotation=90,
            linespacing=1.05, zorder=5)
    num(ax, 9.25, 55.5, "3", color=RED)
    arrow(ax, (13.5, 49.65), (20.0, 49.65), lw=1.6, ms=10, color=RED)
    arrow(ax, (13.5, 29.65), (20.0, 29.65), lw=1.6, ms=10, color=RED)

    # peer edge servers
    px0, px1 = 172.0, 221.4
    ax.add_patch(Rectangle((px0, 0.4), px1 - px0, 99.0, fc=PEER_FC, ec=GRAY, lw=1.4, zorder=0))
    ax.text((px0 + px1) / 2, 96.0, "Peer Edge Servers", ha="center", va="center", fontsize=FS, fontweight="bold")
    rbox(ax, px0 + 2.2, 24.5, px1 - 2.2, 92.0, fc=SUB_FC, ec=GRAY, lw=1.2, r=0.8, z=1)
    ax.text((px0 + px1) / 2, 88.0, "Destination", ha="center", va="center", fontsize=FS_S, fontweight="bold", zorder=3)
    # each flow lands next to what it produces at the destination
    ax.text(178.5, 57.5, "Recent KV", ha="left", va="center", fontsize=FS_S - 1, zorder=3)
    server(ax, 203.0, 53.7, cols=[ORANGE, ORANGE, ORANGE])
    ax.text(196.7, 49.65, "✓ verify, resume", ha="center", va="center", fontsize=FS_S, color=GREEN, zorder=3,
            fontfamily="DejaVu Sans", fontweight="bold")
    ax.text(178.5, 32.0, "Sink", ha="left", va="center", fontsize=FS_S - 1, zorder=3)
    server(ax, 203.0, 28.2, cols=[PURPLE, TEAL, BLUE])
    rbox(ax, px0 + 2.2, 2.6, px1 - 2.2, 21.8, fc=SUB_FC, ec=GRAY, lw=1.2, r=0.8, z=1)
    ax.text((px0 + px1) / 2, 19.2, "Holders", ha="center", va="center", fontsize=FS_S, fontweight="bold", zorder=3)
    for x, cols, lab, c in ((175.6, [PURPLE] * 3, "prev. owner", PURPLE), (190.9, [TEAL, TEAL, "white"], "canceled", TEAL),
                            (206.2, [PURPLE, TEAL, "white"], "eligible", INK)):
        server(ax, x, 8.0, w=11.6, h=7.4, cols=cols)
        ax.text(x + 5.8, 5.0, lab, ha="center", va="center", fontsize=FS_S - 2.5, color=c, zorder=3)
    arrow(ax, (196.7, 21.8), (196.7, 24.5), lw=1.6, ms=10, ls=(0, (3, 2)))

    # 1 normal execution: temporal state updates and Sink versions tracked
    arrow(ax, (41.0, 72.0), (41.0, 61.0), lw=2.2)
    num(ax, 41.0, 65.6, "1")
    # 2 retention and staging with holders (both ways)
    ax.add_patch(FancyArrowPatch((153.0, 9.6), (px0 + 2.2, 9.6), arrowstyle="<|-|>", mutation_scale=16, color=INK,
                                 lw=2.2, ls=(0, (3, 2)), zorder=8, shrinkA=0, shrinkB=0))
    num(ax, 163.0, 9.6, "2")
    # 4b replay, 5 final sync, 4a Sink reconstruction -> destination (horizontal)
    arrow(ax, (153.0, 57.5), (px0 + 2.2, 57.5), lw=2.2)
    num(ax, 163.0, 57.5, "4b")
    arrow(ax, (151.0, 49.65), (px0 + 2.2, 49.65), lw=2.2)
    num(ax, 163.0, 49.65, "5")
    arrow(ax, (153.0, 32.0), (px0 + 2.2, 32.0), lw=2.2)
    num(ax, 163.0, 32.0, "4a")

    for ext in ("pdf", "png"):
        f.savefig(out / f"fig2_architecture_v3.{ext}", dpi=200 if ext == "png" else None)
    plt.close(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "figures/design"))
    a = ap.parse_args()
    mpl.rcParams.update({"font.family": "Arial", "pdf.fonttype": 42, "ps.fonttype": 42})
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fig(out)


if __name__ == "__main__":
    main()
