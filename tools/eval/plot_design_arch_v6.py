#!/usr/bin/env python3
"""Design overview, architecture view (draft v6, 2026-11-05): v5 with a more polished look (per user: "more fancy").
Same layout, content and font sizes as v5; added: per-mechanism color families (Replay orange, Versioned purple,
Wavefront green), header bands with section pills, accented step cards, soft drop shadows, gradient fills, a device
icon, stacked cards for the (plural) past-owner sites.

v5 notes follow.

Style follows the OSDI architecture figures the user supplied (M3U, RamRyder, DirectKV, Espresso, Prism), not CAKE:
  - three horizontal layers separated by dashed lines, each named by a rotated label on the left (RamRyder);
  - the runtime is one gray box holding the three mechanisms as side-by-side yellow columns, each a short vertical
    pipeline of steps under an italic "what it handles" line with state squares (M3U);
  - section references as blue italic tags (Prism); black filled step numbers (DirectKV);
  - an arrow legend on top: control / data / metadata (Espresso).
Content (OTTER):
  Session layer   : the streaming session on its owner, with its state by temporal semantics
                    (Sink = durable, recent K/V + VAE cache = ephemeral, input = immediate); the user device.
  OTTER runtime   : 4.2 Continuity Replay | 4.3 Versioned Sink Reconstruction | 4.4 Continuity Wavefront.
  Edge sites      : source (owner) -> destination <- previous owner / staged site.
  Steps: 1 track, 2 retain / stage, 3 migration request, 4 transfer (Sink delta + log; retained Sink),
         5 final sync, verify, resume.
Single-column figure: 6.0 in canvas, used at \\columnwidth (about 0.55x). Conceptual, no measured data.

    python3.11 tools/eval/plot_design_arch_v6.py [--out figures/design]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INK, MUTED = "black", "#555555"
RT_FC, RT_EC = "#EFEFEF", "#7F7F7F"          # runtime box (M3U gray)
COL_FC, COL_EC = "#FFF2CC", "#D6B656"        # mechanism columns (M3U yellow)
SITE_FC, SITE_EC = "#DAE8FC", "#6C8EBF"      # edge sites
SESS_FC = "#FFFFFF"
SEC = "#2F5597"                              # section tags (Prism blue italic)
CTRL, DATA, META = "#C0392B", "#2F6DB5", INK
SINK, RECENT, VAE, INP = "#8A5CC9", "#E08A2C", "#A6A6A6", "#404040"
FS_H, FS, FS_S = 14, 13, 12
XM, YM, W_IN = 70.0, 66.0, 6.0               # data units; 1 unit = W_IN / XM in

COLS = ((6.6, 26.2), (27.7, 47.3), (48.8, 68.4))   # mechanism columns
CX = [(a + b) / 2 for a, b in COLS]


def rbox(ax, x0, y0, x1, y1, fc="white", ec=INK, lw=1.1, r=0.6, z=2, ls="-"):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z, ls=ls))


def step(ax, x0, y0, x1, y1, text, ls="-", italic=False):
    rbox(ax, x0, y0, x1, y1, fc="white", lw=1.0, r=0.4, z=5, ls=ls)
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, text, ha="center", va="center", fontsize=FS, zorder=6, linespacing=1.05,
            style="italic" if italic else "normal")


def arrow(ax, p0, p1, color=INK, lw=1.6, ls="-", ms=11, z=9):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=ms, color=color, lw=lw, ls=ls, zorder=z,
                                 shrinkA=0, shrinkB=0))


def num(ax, x, y, n):
    ax.text(x, y, str(n), ha="center", va="center", fontsize=FS - 0.5, fontweight="bold", color="white", zorder=12,
            bbox=dict(boxstyle="circle,pad=0.18", fc=INK, ec="white", lw=1.2))


def squares(ax, x, y, cols, s=1.7, z=7, ls="-"):
    for i, c in enumerate(cols):
        ax.add_patch(Rectangle((x + i * s, y), s, s, fc=c, ec=INK, lw=0.7, zorder=z, ls=ls))
    return x + len(cols) * s


MECH = (  # body, header, edge
    ("#FEF3E8", "#F8D5B3", "#D9822B"),
    ("#F3EDFA", "#DCCBF2", "#7E50BF"),
    ("#EAF5EE", "#C4E5CF", "#3A8F52"),
)


def shadow(ax, x0, y0, x1, y1, r=0.6, z=1, d=0.45):
    ax.add_patch(FancyBboxPatch((x0 + d, y0 - d), x1 - x0, y1 - y0, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc="#9A9A9A", ec="none", alpha=0.35, zorder=z))


def gbox(ax, x0, y0, x1, y1, c_top, c_bot, ec=INK, lw=1.1, r=0.6, z=2, shade=True):
    """Rounded box with a vertical gradient fill and a soft drop shadow."""
    if shade:
        shadow(ax, x0, y0, x1, y1, r=r, z=z - 0.5)
    p = FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle=f"round,pad=0,rounding_size={r}", fc="none", ec=ec,
                       lw=lw, zorder=z + 0.2)
    ax.add_patch(p)
    cm = LinearSegmentedColormap.from_list("g", [c_bot, c_top])
    im = ax.imshow(np.linspace(0, 1, 64).reshape(-1, 1), cmap=cm, origin="lower", extent=(x0, x1, y0, y1),
                   aspect="auto", zorder=z, interpolation="bicubic")
    im.set_clip_path(p)


def pill(ax, x, y, text, fc):
    ax.text(x, y, text, ha="left", va="center", fontsize=FS_S, fontweight="bold", style="italic", color="white",
            zorder=8, bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.7", fc=fc, ec="none"))


def card(ax, x0, y0, x1, y1, text, edge, dashed=False):
    ls = (0, (3, 2)) if dashed else "-"
    if not dashed:
        shadow(ax, x0, y0, x1, y1, r=0.4, z=4.5, d=0.3)
    rbox(ax, x0, y0, x1, y1, fc="white", ec=edge, lw=1.1, r=0.4, z=5, ls=ls)
    if not dashed:
        ax.add_patch(FancyBboxPatch((x0, y0), 0.8, y1 - y0, boxstyle="round,pad=0,rounding_size=0.4", fc=edge,
                                    ec="none", zorder=5.5))
    ax.text((x0 + x1) / 2 + (0.4 if not dashed else 0), (y0 + y1) / 2, text, ha="center", va="center", fontsize=FS,
            zorder=6, linespacing=1.05, style="italic" if dashed else "normal", color=INK)


def phone(ax, x, y, w=2.4, h=5.0):
    rbox(ax, x, y, x + w, y + h, fc="#3B3B3B", ec=INK, lw=0.9, r=0.45, z=4)
    rbox(ax, x + 0.3, y + 0.75, x + w - 0.3, y + h - 0.55, fc="#BFD7F2", ec="none", lw=0, r=0.15, z=4.5)
    ax.add_patch(plt.Circle((x + w / 2, y + 0.38), 0.18, fc="white", ec="none", zorder=5))


def fig(out: Path):
    f = plt.figure(figsize=(W_IN, W_IN * YM / XM))
    ax = f.add_axes([0, 0, 1, 1])

    # ---------------- arrow legend ----------------
    rbox(ax, 5.5, 62.0, 69.5, 65.6, fc="#FAFAFA", ec="#BFBFBF", lw=1.0, r=0.8, z=1)
    for x, lab, c, ls in ((9.0, "Control", CTRL, "-"), (29.0, "Data", DATA, "-"), (46.0, "Metadata", META, (0, (3, 2)))):
        arrow(ax, (x, 63.8), (x + 5.0, 63.8), color=c, ls=ls, lw=1.8, ms=10)
        ax.text(x + 6.0, 63.8, lab, ha="left", va="center", fontsize=FS_S, color=c)

    # ---------------- layer separators + rotated labels ----------------
    for y in (49.6, 12.6):
        ax.plot([1.0, 69.5], [y, y], color=MUTED, lw=1.0, ls=(0, (5, 3)), zorder=0)
    for y, lab in ((55.6, "Session"), (31.1, "OTTER runtime"), (6.4, "Edge sites")):
        ax.text(2.6, y, lab, ha="center", va="center", rotation=90, fontsize=FS_H, fontweight="bold", zorder=3)

    # ---------------- session layer ----------------
    gbox(ax, 5.5, 50.6, 48.6, 61.0, "#FFFFFF", "#F2F2F2", lw=1.1, r=0.7, z=2)
    ax.text(6.6, 59.4, "Streaming session (on its owner)", ha="left", va="center", fontsize=FS, fontweight="bold",
            zorder=4)
    groups = ((7.2, "Sink", [SINK] * 3, "durable"), (15.6, "Recent K/V", [RECENT] * 3, None),
              (26.4, "VAE cache", [VAE] * 3, None), (38.6, "Input", [INP], "immediate"))
    for x, lab, cols, sem in groups:
        x1 = squares(ax, x, 53.9, cols)
        ax.text((x + x1) / 2, 52.4, lab, ha="center", va="center", fontsize=FS_S, zorder=4)
        if sem:
            ax.text((x + x1) / 2, 57.0, sem, ha="center", va="center", fontsize=FS_S, style="italic", color=MUTED,
                    zorder=4)
    ax.text((15.6 + 26.4 + 5.1) / 2, 57.0, "ephemeral", ha="center", va="center", fontsize=FS_S, style="italic",
            color=MUTED, zorder=4)
    # user device
    gbox(ax, 56.0, 52.0, 68.4, 60.0, "#FFFFFF", "#F2F2F2", lw=1.1, r=0.7, z=2)
    phone(ax, 57.2, 53.5)
    ax.text(64.3, 56.0, "User\ndevice", ha="center", va="center", fontsize=FS, zorder=4, linespacing=1.05)
    arrow(ax, (56.0, 57.6), (48.6, 57.6), color=DATA, lw=1.5, ms=9)
    arrow(ax, (48.6, 54.2), (56.0, 54.2), color=DATA, lw=1.5, ms=9)
    ax.text(52.3, 58.6, "input", ha="center", va="center", fontsize=FS_S, color=DATA)
    ax.text(52.3, 53.1, "output", ha="center", va="center", fontsize=FS_S, color=DATA)

    # ---------------- OTTER runtime ----------------
    gbox(ax, 5.5, 13.6, 69.5, 48.6, "#F4F4F4", "#E1E1E1", ec=RT_EC, lw=1.2, r=0.9, z=1)
    specs = (
        ("§4.2", "Continuity\nReplay", "recent state", [RECENT, VAE],
         ["Sink pre-copy", "log inputs +\ncache events", "shadow replay\nat destination", "final sync +\nverify"]),
        ("§4.3", "Versioned Sink\nReconstruction", "Sink on return", [SINK],
         ["find retained\nversion", "refreshed K/V\n+ RoPE shifts", "rebuild +\ndigest check", "full copy\non mismatch"]),
        ("§4.4", "Continuity\nWavefront", "retained Sinks", [SINK, "white"],
         ["owner lineage", "retain at past\nowners", "stage at\neligible sites", "supply at\nhandoff"]),
    )
    ys = (31.6, 26.0, 20.4, 14.8)   # step card bottoms
    bh = 4.8
    HB = 40.3                       # header band bottom
    for (x0, x1), (sec, name, what, sq, steps), (c_body, c_head, c_edge) in zip(COLS, specs, MECH):
        cx = (x0 + x1) / 2
        gbox(ax, x0, 14.2, x1, 47.8, c_body, c_body, ec=c_edge, lw=1.3, r=0.7, z=3)
        # header band: rounded top, square bottom
        ax.add_patch(FancyBboxPatch((x0, HB), x1 - x0, 47.8 - HB, boxstyle="round,pad=0,rounding_size=0.7",
                                    fc=c_head, ec="none", zorder=3.4))
        ax.add_patch(Rectangle((x0, HB), x1 - x0, 1.0, fc=c_head, ec="none", zorder=3.4))
        ax.plot([x0, x1], [HB, HB], color=c_edge, lw=1.0, zorder=3.5)
        rbox(ax, x0, 14.2, x1, 47.8, fc="none", ec=c_edge, lw=1.3, r=0.7, z=3.6)
        pill(ax, x0 + 0.9, 46.4, sec, c_edge)
        ax.text(cx, 42.6, name, ha="center", va="center", fontsize=FS_H - 0.5, fontweight="bold", zorder=6,
                linespacing=1.05)
        xs = squares(ax, cx - 7.6, 37.7, sq, s=1.5)
        ax.text(xs + 0.6, 38.45, what, ha="left", va="center", fontsize=FS_S, style="italic", color=MUTED, zorder=6)
        for i, (y, t) in enumerate(zip(ys, steps)):
            fallback = sec == "§4.3" and i == 3
            card(ax, x0 + 1.2, y, x1 - 1.2, y + bh, t, c_edge, dashed=fallback)
            if i:
                arrow(ax, (cx, ys[i - 1]), (cx, y + bh), color=c_edge, lw=1.4, ms=8,
                      ls=(0, (3, 2)) if fallback else "-")

    # ---------------- edge sites ----------------
    W_S = 16.2
    sites = [(c - W_S / 2, c + W_S / 2) for c in CX]
    titles = ("Source (owner)", "Destination", "Past owner /\nstaged site")
    # past owners are plural: stacked cards behind
    for k in (2, 1):
        x0, x1 = sites[2]
        rbox(ax, x0 + 0.65 * k, 1.0 + 0.32 * k, x1 + 0.65 * k, 11.6 + 0.32 * k, fc="#C9DBF3", ec=SITE_EC, lw=1.0, r=0.6,
             z=1.5 - 0.1 * k)
    for i, (x0, x1) in enumerate(sites):
        gbox(ax, x0, 1.0, x1, 11.6, "#E8F0FC", "#C6D9F3", ec=SITE_EC, lw=1.8 if i == 1 else 1.2, r=0.6, z=2,
             shade=i != 2)
    ax.text(CX[0], 9.4, titles[0], ha="center", va="center", fontsize=FS, fontweight="bold", zorder=4)
    squares(ax, CX[0] - 6.0, 3.2, [SINK] * 2 + [RECENT] * 2 + [VAE] * 2 + [INP], s=1.7)
    ax.text(CX[1], 9.4, titles[1], ha="center", va="center", fontsize=FS, fontweight="bold", zorder=4)
    squares(ax, CX[1] - 6.0, 3.2, [SINK] * 2 + [RECENT] * 2 + [VAE] * 2 + [INP], s=1.7, ls=(0, (2, 1.5)))
    ax.text(CX[2], 8.8, titles[2], ha="center", va="center", fontsize=FS, fontweight="bold", zorder=4,
            linespacing=1.0)
    squares(ax, CX[2] - 2.55, 3.2, [SINK] * 3, s=1.7)

    # ---------------- numbered flows ----------------
    for x in (CX[0], CX[1]):
        arrow(ax, (x, 50.6), (x, 47.8), color=META, ls=(0, (3, 2)), lw=1.6, ms=9)
    num(ax, CX[0] + 2.4, 49.2, 1); num(ax, CX[1] + 2.4, 49.2, 1)
    arrow(ax, (62.2, 52.0), (62.2, 47.8), color=CTRL, lw=2.0, ms=10)
    num(ax, 64.6, 49.6, 3)
    arrow(ax, (CX[2], 14.2), (CX[2], 11.6), color=META, ls=(0, (3, 2)), lw=1.6, ms=9)
    num(ax, CX[2] + 2.4, 13.0, 2)
    for xa, xb in ((sites[0][1], sites[1][0]), (sites[2][0], sites[1][1])):
        arrow(ax, (xa, 6.0), (xb, 6.0), color=DATA, lw=2.4, ms=12)
        num(ax, (xa + xb) / 2, 8.0, 4)
    arrow(ax, (CX[0], 14.2), (CX[1] - 3.0, 11.6), color=META, ls=(0, (3, 2)), lw=1.6, ms=9)
    num(ax, (CX[0] + CX[1] - 3.0) / 2, 12.9, 5)

    ax.set_xlim(0, XM); ax.set_ylim(0, YM); ax.axis("off")
    for ext in ("pdf", "png"):
        f.savefig(out / f"fig2_architecture_v6.{ext}", dpi=220 if ext == "png" else None)
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
