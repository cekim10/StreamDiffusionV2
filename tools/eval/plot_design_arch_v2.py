#!/usr/bin/env python3
"""Design overview, architecture view (draft v2, 2026-11-04): what OTTER consists of and where each part runs.

Follows the Design overview text (section 4.1):
  - OTTER is a live migration runtime co-located with streaming diffusion workers on every edge server;
  - no central coordinator: Continuity Wavefront spans servers (owner lineage, holders = previous owners and canceled
    targets, staging at eligible servers, no prediction of the next destination);
  - flows 1 tracking, 2 retention / staging, 3 migration request, 4a Versioned Sink Reconstruction, 4b Continuity
    Replay, 5 final sync at a chunk boundary, verify, resume.
Mechanism details (block colours, rotate / fetch, lineage marks) stay in the section 4.2-4.4 figures.
Conceptual, no measured data. Canvas and fonts of plot_design_arch.py (14 x 6.3 in, figure*; 17 / 15 / 13.5 pt).

    python3.11 tools/eval/plot_design_arch_v2.py [--out figures/design]
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
GPU_FC, RT_FC, PEER_FC, WF_FC = "#D9D9D9", "#FFE699", "#EDEDED", "#EFE8F8"
PURPLE, ORANGE, GRAY, RED, GREEN = "#8A5CC9", "#E08A2C", "#9A9A9A", "#C0392B", "#3E9B57"
FS_T, FS, FS_S = 17, 15, 13.5
W, XM, YM = 14.0, 222.0, 100.0


def rbox(ax, x0, y0, x1, y1, fc="white", ec=INK, lw=1.3, r=1.0, z=2, ls="-"):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z, ls=ls))


def box(ax, x0, y0, x1, y1, text, fs=FS_S, z=4, fc="white", lw=1.2, bold=False):
    rbox(ax, x0, y0, x1, y1, fc=fc, lw=lw, r=0.8, z=z)
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, text, ha="center", va="center", fontsize=fs, zorder=z + 1, linespacing=1.15,
            fontweight="bold" if bold else "normal")


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


def tag(ax, x, y, sec, title, fs=FS):
    ax.text(x, y, f" {sec} ", ha="left", va="center", fontsize=fs, fontweight="bold", color="white", zorder=7,
            bbox=dict(boxstyle="round,pad=0.25,rounding_size=0.6", fc=INK, ec="none"))
    ax.text(x + 9.2, y, title, ha="left", va="center", fontsize=fs, fontweight="bold", zorder=7)


def squares(ax, x, y, cols, s=3.0, z=6):
    for i, c in enumerate(cols):
        ax.add_patch(Rectangle((x + i * s, y), s, s, fc=c, ec=INK, lw=0.8, zorder=z))


def module(ax, x0, y0, x1, y1, sec, title, line):
    rbox(ax, x0, y0, x1, y1, fc="white", lw=1.2, r=0.4, z=3)
    tag(ax, x0 + 1.4, y1 - 3.0, sec, title, fs=FS_S + 0.5)
    ax.text((x0 + x1) / 2, y0 + 3.4, line, ha="center", va="center", fontsize=FS_S, style="italic", zorder=5)


def gpu(ax, x0, x1, y0, y1, worker, groups):
    rbox(ax, x0, y0, x1, y1, fc=GPU_FC, lw=1.3, r=1.2, z=2)
    ax.text(x0 + 1.8, y1 - 2.6, "GPU / VRAM", ha="left", va="center", fontsize=FS_S, fontweight="bold", zorder=4)
    box(ax, x0 + 2.0, y0 + 1.6, x0 + 26.0, y1 - 5.0, worker, fs=FS_S - 0.5)
    for x, lab, cols in groups:
        ax.text(x + 1.5 * len(cols), y1 - 5.6, lab, ha="center", va="center", fontsize=FS_S - 0.5, zorder=4)
        squares(ax, x, y0 + 2.6, cols)


def fig(out: Path):
    f = plt.figure(figsize=(W, W * YM / XM))
    ax = f.add_axes([0, 0, 1, 1]); ax.set_xlim(0, XM); ax.set_ylim(0, YM); ax.axis("off")

    # -------- cluster coordination layer: Continuity Wavefront spans servers (no central coordinator) --------
    rbox(ax, 1.0, 79.5, 221.0, 99.0, fc=WF_FC, ec=PURPLE, lw=1.4, r=1.4, z=1)
    tag(ax, 3.0, 95.6, "§4.4", "Continuity Wavefront")
    ax.text(219.0, 95.6, "cluster coordination layer", ha="right", va="center", fontsize=FS_S, style="italic",
            color="#555555", zorder=5)
    wf = [(14.0, 62.0, "Owner lineage\n(valid Sink versions)"), (84.0, 138.0, "Retain verified entries\n(previous owners, canceled targets)"),
          (160.0, 214.0, "Stage compatible entries\nat eligible servers")]
    for x0, x1, t in wf:
        box(ax, x0, 81.5, x1, 92.0, t)
    arrow(ax, (62.0, 86.75), (84.0, 86.75), lw=1.4, ms=10)
    arrow(ax, (138.0, 86.75), (160.0, 86.75), lw=1.4, ms=10)

    # -------- edge server cards --------
    def card(x0, x1, title):
        rbox(ax, x0, 21.0, x1, 77.0, fc="white", lw=1.3, r=0.6, z=1)
        ax.text(x0 + 1.8, 74.4, title, ha="left", va="center", fontsize=FS, fontweight="bold", zorder=3)

    # source (owner)
    card(1.0, 95.0, "Edge Server: Source (Owner)")
    gpu(ax, 3.0, 93.0, 58.0, 71.5, "Streaming\ndiffusion worker",
        [(33.0, "Sink", [PURPLE] * 3), (49.0, "Recent", [ORANGE] * 3), (65.0, "VAE", [GRAY] * 2), (80.0, "In-flight", ["#5B5B5B"])])
    rbox(ax, 3.0, 23.0, 93.0, 55.5, fc=RT_FC, lw=1.3, r=1.2, z=2)
    ax.text(30.0, 52.6, "OTTER Runtime", ha="left", va="center", fontsize=FS, fontweight="bold", zorder=4)
    box(ax, 5.0, 25.0, 27.0, 49.0, "State\nTracker\n\ninput &\ncache-event log,\nSink versions", fs=FS_S - 0.5)
    module(ax, 30.0, 38.0, 91.0, 49.0, "§4.2", "Continuity Replay", "log + Sink K/V patches")
    module(ax, 30.0, 25.0, 91.0, 36.0, "§4.3", "Versioned Sink Reconstruction", "refreshed K/V + ordered shifts")

    # destination
    card(103.0, 176.0, "Edge Server: Destination")
    gpu(ax, 105.0, 174.0, 58.0, 71.5, "Streaming\ndiffusion worker",
        [(137.0, "Sink", [PURPLE] * 3), (155.0, "Recent", [ORANGE] * 3)])
    rbox(ax, 105.0, 23.0, 174.0, 55.5, fc=RT_FC, lw=1.3, r=1.2, z=2)
    ax.text(107.0, 52.6, "OTTER Runtime", ha="left", va="center", fontsize=FS, fontweight="bold", zorder=4)
    module(ax, 107.0, 38.0, 172.0, 49.0, "§4.2", "Shadow Replay", "rebuilds recent state")
    module(ax, 107.0, 25.0, 172.0, 36.0, "§4.3", "Sink Rebuild", "digest + position check")

    # holder
    card(184.0, 221.0, "Holder")
    box(ax, 186.5, 44.0, 218.5, 64.0, "Retained\nSink version", fs=FS_S - 0.5)
    squares(ax, 197.5, 46.0, [PURPLE, PURPLE, "white"])
    ax.text(202.5, 33.0, "previous owner,\ncanceled target,\nor eligible server", ha="center", va="center", fontsize=FS_S - 1.5,
            style="italic", zorder=3, linespacing=1.15)

    # -------- user lane --------
    rbox(ax, 1.0, 1.0, 221.0, 17.0, fc=PEER_FC, ec=GRAY, lw=1.2, r=0.8, z=0)
    ax.text(3.0, 14.2, "Users", ha="left", va="center", fontsize=FS_S, fontweight="bold", zorder=3)
    for x in (48.0, 139.5):
        box(ax, x - 9.0, 3.5, x + 9.0, 11.5, "user device", fs=FS_S - 1.0)
    arrow(ax, (57.0, 7.5), (130.5, 7.5), lw=1.8, ls=(0, (4, 2)), color=GRAY)
    ax.text(93.75, 9.6, "user moves", ha="center", va="bottom", fontsize=FS_S - 1.0, style="italic", color="#555555")
    for x in (48.0,):
        arrow(ax, (x - 3.0, 11.5), (x - 3.0, 21.0), lw=1.6, ms=11)
        arrow(ax, (x + 3.0, 21.0), (x + 3.0, 11.5), lw=1.6, ms=11)
        ax.text(x - 4.2, 16.2, "input frames", ha="right", va="center", fontsize=FS_S - 1.5)
        ax.text(x + 4.2, 16.2, "output frames", ha="left", va="center", fontsize=FS_S - 1.5)

    # -------- numbered flows --------
    # 1 tracking: worker -> state tracker
    arrow(ax, (16.0, 59.6), (16.0, 49.0), lw=2.2)
    num(ax, 16.0, 56.0, "1")
    # 2 lineage from the owner, staging to the holder, supply to the destination's Sink rebuild
    path(ax, [(10.0, 77.0), (10.0, 81.5 + 4.75), (14.0, 81.5 + 4.75)], lw=1.8, ls=(0, (3, 2)), color=PURPLE, ms=12)
    arrow(ax, (202.5, 81.5), (202.5, 64.0), lw=2.0, ls=(0, (3, 2)), color=PURPLE)
    num(ax, 202.5, 68.5, "2", color=PURPLE)
    path(ax, [(186.5, 50.0), (180.0, 50.0), (180.0, 30.5), (172.0, 30.5)], lw=2.0, ls=(0, (3, 2)), color=PURPLE)
    # 3 migration request (user move) -> the source's and the destination's runtimes
    ax.plot([93.75, 93.75], [12.5, 19.0], color=RED, lw=2.0, zorder=8)
    ax.plot([80.0, 115.0], [19.0, 19.0], color=RED, lw=2.0, zorder=8)
    arrow(ax, (80.0, 19.0), (80.0, 23.0), lw=2.0, color=RED, ms=13)
    arrow(ax, (115.0, 19.0), (115.0, 23.0), lw=2.0, color=RED, ms=13)
    num(ax, 93.75, 15.0, "3", color=RED)
    # 4b continuity replay, 4a versioned sink reconstruction: source -> destination runtime
    arrow(ax, (91.0, 43.5), (107.0, 43.5), lw=2.2)
    num(ax, 99.0, 43.5, "4b")
    arrow(ax, (91.0, 33.5), (107.0, 33.5), lw=2.2)
    num(ax, 99.0, 35.5, "4a")
    # 5 final sync at a chunk boundary: GPU -> GPU, then verify and resume
    arrow(ax, (93.0, 64.0), (105.0, 64.0), lw=2.2)
    num(ax, 99.0, 64.0, "5")
    ax.text(173.0, 70.0, "✓ verify, resume", ha="right", va="center", fontsize=FS_S - 1.0, color=GREEN, zorder=6,
            fontfamily="DejaVu Sans", fontweight="bold")

    for ext in ("pdf", "png"):
        f.savefig(out / f"fig2_architecture_v2.{ext}", dpi=200 if ext == "png" else None)
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
