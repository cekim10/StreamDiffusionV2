#!/usr/bin/env python3
"""Design overview, architecture view (draft v4, 2026-11-04, per user): v2's cross-server layout, with the three
mechanisms as three components of the OTTER runtime.

Columns are edge servers (source = owner, destination, holder); the OTTER runtime is one band across all of them (it
runs on every edge server, co-located with the streaming diffusion worker), and each mechanism is one component band:
  4.2 Continuity Replay              source: input & cache-event log + Sink K/V patches  -> 4b ->  destination: shadow replay
                                     source: final sync at a chunk boundary              -> 5  ->  destination: verify, resume
  4.3 Versioned Sink Reconstruction  source: refreshed K/V + ordered shift list           -> 4a ->  destination: rebuild + digest check
                                     holder: retained entries -> destination (dashed)
  4.4 Continuity Wavefront           source: owner lineage -> holder: retain verified entries, stage at eligible servers
                                     -> destination: supply at handoff (dashed, 2)
Users on top: input / output frames; a move issues the migration request (3). Conceptual, no measured data.
Canvas and fonts of plot_design_arch.py (14 x 6.3 in, figure*; 17 / 15 / 13.5 pt).

    python3.11 tools/eval/plot_design_arch_v4.py [--out figures/design]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INK = "black"
GPU_FC, RT_FC, CARD_FC, USER_FC = "#D9D9D9", "#FFE699", "#FFFFFF", "#EDEDED"
PURPLE, ORANGE, GRAY, RED, GREEN = "#8A5CC9", "#E08A2C", "#9A9A9A", "#C0392B", "#3E9B57"
FS_T, FS, FS_S = 17, 15, 13.5
W, XM, YM = 14.0, 222.0, 100.0

# columns (x ranges of the server cards)
SRC, DST, HLD = (1.0, 92.0), (100.0, 176.0), (184.0, 221.0)


def rbox(ax, x0, y0, x1, y1, fc="white", ec=INK, lw=1.3, r=1.0, z=2, ls="-"):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z, ls=ls))


def box(ax, x0, y0, x1, y1, text, fs=FS_S - 0.5, z=5, fc="white", italic=False):
    rbox(ax, x0, y0, x1, y1, fc=fc, lw=1.2, r=0.8, z=z)
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, text, ha="center", va="center", fontsize=fs, zorder=z + 1, linespacing=1.12,
            style="italic" if italic else "normal")


def arrow(ax, p0, p1, lw=2.2, ls="-", ms=16, z=9, color=INK):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=ms, color=color, lw=lw, ls=ls, zorder=z,
                                 shrinkA=0, shrinkB=0))


def path(ax, pts, lw=2.2, ls="-", ms=16, z=9, color=INK):
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


def squares(ax, x, y, cols, s=3.0, z=6):
    for i, c in enumerate(cols):
        ax.add_patch(Rectangle((x + i * s, y), s, s, fc=c, ec=INK, lw=0.8, zorder=z))


def fig(out: Path):
    f = plt.figure(figsize=(W, W * YM / XM))
    ax = f.add_axes([0, 0, 1, 1]); ax.set_xlim(0, XM); ax.set_ylim(0, YM); ax.axis("off")

    # ---------------- users (top) ----------------
    rbox(ax, 1.0, 88.0, 221.0, 99.4, fc=USER_FC, ec=GRAY, lw=1.2, r=0.8, z=0)
    ax.text(3.0, 96.6, "Users", ha="left", va="center", fontsize=FS_S, fontweight="bold", zorder=3)
    box(ax, 70.0, 89.6, 88.0, 96.8, "user device", fs=FS_S - 1.0)
    box(ax, 129.0, 89.6, 147.0, 96.8, "user device", fs=FS_S - 1.0)
    arrow(ax, (88.0, 93.2), (129.0, 93.2), lw=1.8, ls=(0, (4, 2)), color=GRAY)
    ax.text(112.0, 94.6, "user moves", ha="center", va="bottom", fontsize=FS_S - 1.5, style="italic", color="#555555")

    # ---------------- edge-server cards (columns) ----------------
    for (x0, x1), title in ((SRC, "Edge Server: Source (Owner)"), (DST, "Edge Server: Destination"), (HLD, "Edge Server: Holder")):
        rbox(ax, x0, 64.4, x1, 85.6, fc=CARD_FC, lw=1.3, r=0.6, z=1)
        ax.text(x0 + 1.6, 83.0, title, ha="left", va="center", fontsize=FS - 0.5, fontweight="bold", zorder=3)

    # GPU row
    rbox(ax, SRC[0] + 2, 66.0, SRC[1] - 2, 80.0, fc=GPU_FC, lw=1.2, r=1.0, z=2)
    ax.text(SRC[0] + 3.6, 77.6, "GPU", ha="left", va="center", fontsize=FS_S, fontweight="bold", zorder=4)
    box(ax, SRC[0] + 4, 67.4, SRC[0] + 28, 75.2, "Streaming\ndiffusion worker", fs=FS_S - 1)
    for x, lab, cols in ((34.0, "Sink", [PURPLE] * 3), (49.0, "Recent", [ORANGE] * 3), (64.0, "VAE", [GRAY] * 2),
                         (77.0, "In-flight", ["#5B5B5B"])):
        ax.text(x + 1.5 * len(cols), 74.6, lab, ha="center", va="center", fontsize=FS_S - 1.5, zorder=4)
        squares(ax, x, 68.6, cols)
    rbox(ax, DST[0] + 2, 66.0, DST[1] - 2, 80.0, fc=GPU_FC, lw=1.2, r=1.0, z=2)
    ax.text(DST[0] + 3.6, 77.6, "GPU", ha="left", va="center", fontsize=FS_S, fontweight="bold", zorder=4)
    box(ax, DST[0] + 4, 67.4, DST[0] + 28, 75.2, "Streaming\ndiffusion worker", fs=FS_S - 1)
    for x, lab, cols in ((134.0, "Sink", [PURPLE] * 3), (152.0, "Recent", [ORANGE] * 3)):
        ax.text(x + 1.5 * len(cols), 74.6, lab, ha="center", va="center", fontsize=FS_S - 1.5, zorder=4)
        squares(ax, x, 68.6, cols)
    rbox(ax, HLD[0] + 2, 66.0, HLD[1] - 2, 80.0, fc=GPU_FC, lw=1.2, r=1.0, z=2)
    ax.text(HLD[0] + 3.6, 77.6, "GPU", ha="left", va="center", fontsize=FS_S, fontweight="bold", zorder=4)
    ax.text((HLD[0] + HLD[1]) / 2, 73.6, "retained Sink", ha="center", va="center", fontsize=FS_S - 1.5, zorder=4)
    squares(ax, (HLD[0] + HLD[1]) / 2 - 4.5, 68.6, [PURPLE, PURPLE, "white"])

    # ---------------- OTTER runtime: one band across every server ----------------
    rbox(ax, 0.2, 1.6, 221.8, 63.6, fc=RT_FC, ec=INK, lw=1.4, r=1.4, z=3)
    ax.text(2.0, 61.0, "OTTER Runtime", ha="left", va="center", fontsize=FS_T + 1, fontweight="bold", zorder=5)
    ax.text(104.0, 61.0, "(co-located with the worker on every edge server)", ha="left", va="center", fontsize=FS_S,
            style="italic", color="#555555", zorder=5)

    def component(y0, y1, sec, title, layer):
        rbox(ax, 2.0, y0, 220.0, y1, fc="white", lw=1.2, r=0.4, z=4)
        tag(ax, 3.4, y1 - 2.9, sec, title)
        ax.text(218.4, y1 - 2.9, layer, ha="right", va="center", fontsize=FS_S, style="italic", color="#555555", zorder=6)

    # 4.2 Continuity Replay: two steps per side (4b while the source serves, 5 at the chunk boundary)
    y0, y1 = 41.0, 58.0
    component(y0, y1, "§4.2", "Continuity Replay", "execution layer")
    box(ax, 8.0, y0 + 7.0, 86.0, y0 + 12.4, "input & cache-event log + Sink K/V patches")
    box(ax, 8.0, y0 + 1.0, 86.0, y0 + 6.4, "final sync at a chunk boundary")
    box(ax, 106.0, y0 + 7.0, 170.0, y0 + 12.4, "shadow replay rebuilds recent state")
    box(ax, 106.0, y0 + 1.0, 170.0, y0 + 6.4, "verify Sink, resume")
    # 4.3 Versioned Sink Reconstruction
    y0b, y1b = 22.0, 39.0
    component(y0b, y1b, "§4.3", "Versioned Sink Reconstruction", "state representation layer")
    box(ax, 8.0, y0b + 1.6, 86.0, y0b + 10.4, "refreshed K/V + ordered shift list\n(from the retained version)")
    box(ax, 106.0, y0b + 1.6, 170.0, y0b + 10.4, "rotate shifted keys locally;\ndigest + position check")
    box(ax, 187.0, y0b + 1.6, 218.0, y0b + 10.4, "retained\nentries")
    # 4.4 Continuity Wavefront
    y0c, y1c = 3.0, 20.0
    component(y0c, y1c, "§4.4", "Continuity Wavefront", "cluster coordination layer")
    box(ax, 8.0, y0c + 1.6, 86.0, y0c + 10.4, "owner lineage\n(which retained versions are valid)")
    box(ax, 106.0, y0c + 1.6, 170.0, y0c + 10.4, "supply compatible entries\nat handoff")
    box(ax, 187.0, y0c + 1.6, 218.0, y0c + 10.4, "retain, stage\nat eligible\nservers", fs=FS_S - 1.5)

    # ---------------- numbered flows ----------------
    # 1 tracking: worker -> runtime (4.2 log, 4.3 versions)
    arrow(ax, (60.0, 66.0), (60.0, 53.4), lw=2.2)
    num(ax, 60.0, 61.0, "1")
    # 2 Wavefront: the owner's lineage decides validity; holders retain / stage and supply at handoff (dashed purple)
    arrow(ax, (86.0, 8.6), (106.0, 8.6), lw=1.8, ls=(0, (3, 2)), color=PURPLE, ms=12)
    arrow(ax, (187.0, 8.6), (170.0, 8.6), lw=1.8, ls=(0, (3, 2)), color=PURPLE, ms=12)
    num(ax, 178.5, 8.6, "2", color=PURPLE)
    arrow(ax, (187.0, 27.6), (170.0, 27.6), lw=1.8, ls=(0, (3, 2)), color=PURPLE, ms=12)
    # 3 migration request: the user's move reaches the source and the destination
    ax.plot([96.0, 96.0], [93.2, 64.5], color=RED, lw=2.0, zorder=9)
    num(ax, 96.0, 85.0, "3", color=RED)
    arrow(ax, (96.0, 64.5), (96.0, 58.0), lw=2.0, color=RED, ms=13)
    # 4b replay, 5 final sync, 4a Sink reconstruction: source -> destination
    arrow(ax, (86.0, 50.7), (106.0, 50.7), lw=2.2)
    num(ax, 96.0, 50.7, "4b")
    arrow(ax, (86.0, 44.7), (106.0, 44.7), lw=2.2)
    num(ax, 96.0, 44.2, "5")
    arrow(ax, (86.0, 28.0), (106.0, 28.0), lw=2.2)
    num(ax, 96.0, 28.0, "4a")
    # input / output frames between the user and the source worker
    arrow(ax, (76.0, 89.6), (76.0, 80.0), lw=1.6, ms=11)
    arrow(ax, (82.0, 80.0), (82.0, 89.6), lw=1.6, ms=11)
    ax.text(74.8, 86.6, "input", ha="right", va="center", fontsize=FS_S - 2)
    ax.text(83.2, 86.6, "output", ha="left", va="center", fontsize=FS_S - 2)

    for ext in ("pdf", "png"):
        f.savefig(out / f"fig2_architecture_v4.{ext}", dpi=200 if ext == "png" else None)
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
