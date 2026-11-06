#!/usr/bin/env python3
"""Design overview, architecture view (draft v8, 2026-11-06): v7 + technical content (per user: "structure good, but
nothing technical inside"). Each mechanism column gets a mini data-structure glyph (Replay: chunk log with the
replay window W; Versioned Sink: retained v2 -> current v5 blocks, reused / RoPE-rotated / refreshed; Wavefront:
migration, staging and current-entry edges among E1-E3) and its step cards become named components with a one-line
detail (Sink pre-copy / chunk log / shadow replay / cutover sync; version store / delta / local rebuild / digest check;
lineage / retention / staging / assembly). Canvas taller (YM 66 -> 78); fonts unchanged.

v7 notes: v6 recolored to the paper colorset (advisor: at most
3-4 colors, no white text): gray / blue #2F6DB5 / yellow-orange #E69F00 / black, same meanings as in the other figures
(orange = Sink, blue = reconstruction / recent state, gray = neutral). Replay column blue, Versioned Sink orange,
Wavefront gray; section pills and step numbers now black text on white; control arrows black.

v6 notes: v5 with a more polished look (per user: "more fancy").
Same layout, content and font sizes as v5; added: per-mechanism color families (Replay orange, Versioned purple,
Wavefront green), header bands with section pills, accented step cards, soft drop shadows, gradient fills, stacked cards for the (plural) past-owner sites.

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
  OTTER runtime   : 3.2 Continuity Replay | 3.3 Versioned Sink Reconstruction | 3.4 Continuity Wavefront.
  Edge sites      : source (owner) -> destination <- previous owner / staged site.
  Steps: 1 track, 2 retain / stage, 3 migration request, 4 transfer (Sink delta + log; retained Sink),
         5 final sync, verify, resume.
Single-column figure: 6.0 in canvas, used at \\columnwidth (about 0.55x). Conceptual, no measured data.

    python3.11 tools/eval/plot_design_arch_v8.py [--out figures/design]
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
SITE_FC, SITE_EC = "#EFEFEF", "#6E6E6E"      # edge sites (neutral gray)
SESS_FC = "#FFFFFF"
SEC = "#2F5597"                              # section tags (Prism blue italic)
CTRL, DATA, META = INK, "#2F6DB5", INK          # control solid black, data blue, metadata dashed black
SINK, RECENT, VAE, INP = "#E69F00", "#2F6DB5", "#A6A6A6", "black"   # = fig2a
SINK_TXT = "#B07800"
FS_H, FS, FS_S = 14, 13, 12
XM, YM, W_IN = 70.0, 78.0, 6.0               # data units; 1 unit = W_IN / XM in

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
    ax.text(x, y, str(n), ha="center", va="center", fontsize=FS - 0.5, fontweight="bold", color=INK, zorder=12,
            bbox=dict(boxstyle="circle,pad=0.18", fc="white", ec=INK, lw=1.4))


def squares(ax, x, y, cols, s=1.7, z=7, ls="-"):
    for i, c in enumerate(cols):
        ax.add_patch(Rectangle((x + i * s, y), s, s, fc=c, ec=INK, lw=0.7, zorder=z, ls=ls))
    return x + len(cols) * s


MECH = (  # body, header, edge -- Replay blue, Versioned Sink orange, Wavefront gray
    ("#F1F6FC", "#C9DCF2", "#2F6DB5"),
    ("#FFF8E8", "#FCEBC2", "#E69F00"),
    ("#F7F7F7", "#E3E3E3", "#6E6E6E"),
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
    ax.text(x, y, text, ha="left", va="center", fontsize=FS_S, fontweight="bold", style="italic", color=INK,
            zorder=8, bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.7", fc="white", ec=fc, lw=1.3))


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


BLUE_LT, LGRAY = "#C9DCF2", "#E4E4E4"
DY = 12.0                                     # session layer and legend moved up by the extra canvas height


def tcard(ax, x0, y0, x1, y1, name, detail, edge, dashed=False):
    """Component card: bold name over an italic one-line detail."""
    ls = (0, (3, 2)) if dashed else "-"
    if not dashed:
        shadow(ax, x0, y0, x1, y1, r=0.4, z=4.5, d=0.3)
    rbox(ax, x0, y0, x1, y1, fc="white", ec=edge, lw=1.1, r=0.4, z=5, ls=ls)
    if not dashed:
        ax.add_patch(FancyBboxPatch((x0, y0), 0.8, y1 - y0, boxstyle="round,pad=0,rounding_size=0.4", fc=edge,
                                    ec="none", zorder=5.5))
    cx, cy = (x0 + x1) / 2 + (0.4 if not dashed else 0), (y0 + y1) / 2
    ax.text(cx, cy + 1.25, name, ha="center", va="center", fontsize=FS, fontweight="bold", zorder=6, color=INK,
            style="italic" if dashed else "normal")
    ax.text(cx, cy - 1.35, detail, ha="center", va="center", fontsize=FS_S, style="italic", zorder=6, color=MUTED)


def sq(ax, x, y, c, s, ec=INK, hatch=None, z=7):
    ax.add_patch(Rectangle((x, y), s, s, fc=c, ec=ec, lw=0.7, zorder=z, hatch=hatch))


def glyph_replay(ax, x0, x1, y0):
    """Chunk log c0..M; the last W chunks are replayed (teacher-forced) at the destination."""
    cx, s, g, n, w = (x0 + x1) / 2, 1.6, 0.35, 8, 4
    xs = cx - (n * (s + g) - g) / 2
    for i in range(n):
        rep = i >= n - w
        sq(ax, xs + i * (s + g), y0 + 2.2, BLUE_LT if rep else LGRAY, s, ec=RECENT if rep else INK)
    xl = xs + (n - 1) * (s + g) + s
    ax.text(xl - s / 2, y0 + 0.9, "$M$", ha="center", va="center", fontsize=FS_S, zorder=7)
    ax.text((xs + xl - w * (s + g)) / 2, y0 + 0.9, "chunk log", ha="center", va="center", fontsize=FS_S,
            style="italic", color=MUTED, zorder=7)
    bx0, by = xs + (n - w) * (s + g), y0 + 4.4
    ax.plot([bx0, bx0, xl, xl], [by - 0.4, by, by, by - 0.4], color=RECENT, lw=1.3, zorder=7)
    ax.text((bx0 + xl) / 2, by + 1.15, "replay $W$", ha="center", va="center", fontsize=FS_S, color=RECENT, zorder=7)
    sq(ax, xs, y0 + 4.2, SINK, s)                                   # Sink base snapshot at c0
    ax.text(xs + s + 0.5, y0 + 5.0, "base", ha="left", va="center", fontsize=FS_S, style="italic", color=MUTED,
            zorder=7)


def glyph_versioned(ax, x0, x1, y0):
    """Retained v2 at the destination -> current v5: reused, RoPE-rotated, refreshed (sent), stale."""
    s, g = 1.6, 0.45
    xs = x0 + 4.6
    top = [LGRAY, SINK_ROT := RECENT, RECENT, LGRAY, SINK, RECENT]
    for i, c in enumerate(top):
        x = xs + i * (s + g)
        sq(ax, x, y0 + 4.5, c, s)
        stale = i == 4
        sq(ax, x, y0 + 0.9, "white" if stale else LGRAY, s, ec="#7F7F7F" if stale else INK,
           hatch="xxxx" if stale else None)
        if not stale:
            arrow(ax, (x + s / 2, y0 + 2.6), (x + s / 2, y0 + 4.4), color=RECENT if c == RECENT else "#6E6E6E",
                  lw=1.1, ms=6)
    ax.text(x0 + 2.6, y0 + 5.3, "$v_5$", ha="center", va="center", fontsize=FS_S, zorder=7)
    ax.text(x0 + 2.6, y0 + 1.7, "$v_2$", ha="center", va="center", fontsize=FS_S, zorder=7)
    xr = xs + 4 * (s + g) + s / 2
    arrow(ax, (xr, y0 + 7.5), (xr, y0 + 6.2), color=SINK, lw=1.4, ms=7)
    ax.text(xr + 1.0, y0 + 6.9, "$e$", ha="left", va="center", fontsize=FS_S, color=SINK_TXT, zorder=7)
    ax.text(xs + 5 * (s + g) + s + 0.35, y0 + 3.5, "$\\delta$", ha="left", va="center", fontsize=FS_S, color=RECENT,
            zorder=7)


def glyph_wavefront(ax, x0, x1, y0):
    """E1 -> E2 migration (black), E1 -> E3 staging (dashed gray), E2 -> E3 current entries (orange)."""
    cx, w, h = (x0 + x1) / 2, 3.8, 2.3
    pos = {"E1": (x0 + 3.6, y0 + 1.9), "E2": (cx, y0 + 5.7), "E3": (x1 - 3.6, y0 + 1.9)}
    for k, (x, y) in pos.items():
        rbox(ax, x - w / 2, y - h / 2, x + w / 2, y + h / 2, fc="white", ec=INK, lw=1.0, r=0.35, z=7)
        ax.text(x, y, k, ha="center", va="center", fontsize=FS_S, fontweight="bold", zorder=8)
    (a, b), (c, d), (e, f) = pos["E1"], pos["E2"], pos["E3"]
    arrow(ax, (a + 0.6, b + h / 2), (c - w / 2, d - 0.2), color=INK, lw=1.4, ms=7)
    arrow(ax, (a + w / 2, b), (e - w / 2, f), color="#6E6E6E", lw=1.4, ms=7, ls=(0, (3, 2)))
    arrow(ax, (c + w / 2, d - 0.2), (e - 0.6, f + h / 2), color=SINK, lw=1.6, ms=7)


def fig(out: Path):
    f = plt.figure(figsize=(W_IN, W_IN * YM / XM))
    ax = f.add_axes([0, 0, 1, 1])

    # ---------------- arrow legend ----------------
    rbox(ax, 5.5, 62.0 + DY, 69.5, 65.6 + DY, fc="#FAFAFA", ec="#BFBFBF", lw=1.0, r=0.8, z=1)
    for x, lab, c, ls in ((9.0, "Control", CTRL, "-"), (29.0, "Data", DATA, "-"), (46.0, "Metadata", META, (0, (3, 2)))):
        arrow(ax, (x, 63.8 + DY), (x + 5.0, 63.8 + DY), color=c, ls=ls, lw=1.8, ms=10)
        ax.text(x + 6.0, 63.8 + DY, lab, ha="left", va="center", fontsize=FS_S, color=c)

    # ---------------- layer separators + rotated labels ----------------
    for y in (49.6 + DY, 12.6):
        ax.plot([1.0, 69.5], [y, y], color=MUTED, lw=1.0, ls=(0, (5, 3)), zorder=0)
    for y, lab in ((55.6 + DY, "Session"), (37.1, "OTTER runtime"), (6.4, "Edge sites")):
        ax.text(2.6, y, lab, ha="center", va="center", rotation=90, fontsize=FS_H, fontweight="bold", zorder=3)

    # ---------------- session layer ----------------
    gbox(ax, 5.5, 50.6 + DY, 48.6, 61.0 + DY, "#FFFFFF", "#F2F2F2", lw=1.1, r=0.7, z=2)
    ax.text(6.6, 59.4 + DY, "Streaming session (on its owner)", ha="left", va="center", fontsize=FS, fontweight="bold",
            zorder=4)
    groups = ((7.2, "Sink", [SINK] * 3, "durable"), (15.6, "Recent K/V", [RECENT] * 3, None),
              (26.4, "VAE cache", [VAE] * 3, None), (38.6, "Input", [INP], "immediate"))
    for x, lab, cols, sem in groups:
        x1 = squares(ax, x, 53.9 + DY, cols)
        ax.text((x + x1) / 2, 52.4 + DY, lab, ha="center", va="center", fontsize=FS_S, zorder=4)
        if sem:
            ax.text((x + x1) / 2, 57.0 + DY, sem, ha="center", va="center", fontsize=FS_S, style="italic",
                    color=MUTED, zorder=4)
    ax.text((15.6 + 26.4 + 5.1) / 2, 57.0 + DY, "ephemeral", ha="center", va="center", fontsize=FS_S,
            style="italic", color=MUTED, zorder=4)
    gbox(ax, 56.0, 52.0 + DY, 68.4, 60.0 + DY, "#FFFFFF", "#F2F2F2", lw=1.1, r=0.7, z=2)
    ax.text(62.2, 56.0 + DY, "User\ndevice", ha="center", va="center", fontsize=FS, zorder=4, linespacing=1.05)
    arrow(ax, (56.0, 57.6 + DY), (48.6, 57.6 + DY), color=DATA, lw=1.5, ms=9)
    arrow(ax, (48.6, 54.2 + DY), (56.0, 54.2 + DY), color=DATA, lw=1.5, ms=9)
    ax.text(52.3, 58.6 + DY, "input", ha="center", va="center", fontsize=FS_S, color=DATA)
    ax.text(52.3, 53.1 + DY, "output", ha="center", va="center", fontsize=FS_S, color=DATA)

    # ---------------- OTTER runtime ----------------
    TOP = 47.8 + DY
    gbox(ax, 5.5, 13.6, 69.5, 48.6 + DY, "#F4F4F4", "#E1E1E1", ec=RT_EC, lw=1.2, r=0.9, z=1)
    specs = (
        ("§3.2", "Continuity\nReplay", glyph_replay,
         [("Sink pre-copy", "base at $c_0$"), ("Chunk log", "$x_t$ + patches"),
          ("Shadow replay", "teacher-forced"), ("Cutover sync", "state + digest")]),
        ("§3.3", "Versioned Sink\nReconstruction", glyph_versioned,
         [("Version store", "retained $v_k$"), ("Sink delta", "$e$ + $\\delta$ list"),
          ("Local rebuild", "rotate K by $\\delta$"), ("Digest check", "else full copy")]),
        ("§3.4", "Continuity\nWavefront", glyph_wavefront,
         [("Lineage", "owners, holders"), ("Retention", "$v_k$ at holders"),
          ("Staging", "valid entries"), ("Assembly", "holders + owner")]),
    )
    bh, gap = 6.2, 1.1
    ys = [15.0 + k * (bh + gap) for k in range(4)][::-1]     # card bottoms, top card first
    HB = TOP - 7.5
    for (x0, x1), (sec, name, glyph, steps), (c_body, c_head, c_edge) in zip(COLS, specs, MECH):
        cx = (x0 + x1) / 2
        gbox(ax, x0, 14.2, x1, TOP, c_body, c_body, ec=c_edge, lw=1.3, r=0.7, z=3)
        ax.add_patch(FancyBboxPatch((x0, HB), x1 - x0, TOP - HB, boxstyle="round,pad=0,rounding_size=0.7",
                                    fc=c_head, ec="none", zorder=3.4))
        ax.add_patch(Rectangle((x0, HB), x1 - x0, 1.0, fc=c_head, ec="none", zorder=3.4))
        ax.plot([x0, x1], [HB, HB], color=c_edge, lw=1.0, zorder=3.5)
        rbox(ax, x0, 14.2, x1, TOP, fc="none", ec=c_edge, lw=1.3, r=0.7, z=3.6)
        pill(ax, x0 + 0.9, TOP - 1.4, sec, c_edge)
        ax.text(cx, HB + 2.3, name, ha="center", va="center", fontsize=FS_H - 0.5, fontweight="bold", zorder=6,
                linespacing=1.05)
        glyph(ax, x0, x1, ys[0] + bh + 1.2)
        for i, (y, (nm, dt)) in enumerate(zip(ys, steps)):
            fallback = sec == "§3.3" and i == 3
            tcard(ax, x0 + 1.2, y, x1 - 1.2, y + bh, nm, dt, c_edge, dashed=fallback)
            if i:
                arrow(ax, (cx, ys[i - 1]), (cx, y + bh), color=c_edge, lw=1.4, ms=8,
                      ls=(0, (3, 2)) if fallback else "-")

    # ---------------- edge sites ----------------
    W_S = 16.2
    sites = [(c - W_S / 2, c + W_S / 2) for c in CX]
    titles = ("Source (owner)", "Destination", "Past owner /\nstaged site")
    for k in (2, 1):
        x0, x1 = sites[2]
        rbox(ax, x0 + 0.65 * k, 1.0 + 0.32 * k, x1 + 0.65 * k, 11.6 + 0.32 * k, fc="#DCDCDC", ec=SITE_EC, lw=1.0, r=0.6,
             z=1.5 - 0.1 * k)
    for i, (x0, x1) in enumerate(sites):
        gbox(ax, x0, 1.0, x1, 11.6, "#FAFAFA", "#E4E4E4", ec=SITE_EC, lw=1.8 if i == 1 else 1.2, r=0.6, z=2,
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
        arrow(ax, (x, 50.6 + DY), (x, TOP), color=META, ls=(0, (3, 2)), lw=1.6, ms=9)
    num(ax, CX[0] + 2.4, 49.2 + DY, 1); num(ax, CX[1] + 2.4, 49.2 + DY, 1)
    arrow(ax, (62.2, 52.0 + DY), (62.2, TOP), color=CTRL, lw=2.0, ms=10)
    num(ax, 64.6, 49.6 + DY, 3)
    arrow(ax, (CX[2], 14.2), (CX[2], 11.6), color=META, ls=(0, (3, 2)), lw=1.6, ms=9)
    num(ax, CX[2] + 2.4, 13.0, 2)
    for xa, xb in ((sites[0][1], sites[1][0]), (sites[2][0], sites[1][1])):
        arrow(ax, (xa, 6.0), (xb, 6.0), color=DATA, lw=2.4, ms=12)
        num(ax, (xa + xb) / 2, 8.0, 4)
    arrow(ax, (CX[0], 14.2), (CX[1] - 3.0, 11.6), color=META, ls=(0, (3, 2)), lw=1.6, ms=9)
    num(ax, (CX[0] + CX[1] - 3.0) / 2, 12.9, 5)

    ax.set_xlim(0, XM); ax.set_ylim(0, YM); ax.axis("off")
    for ext in ("pdf", "png"):
        f.savefig(out / f"fig2_architecture_v8.{ext}", dpi=220 if ext == "png" else None)
    check_inside(f, ax)
    plt.close(f)


def check_inside(f, ax):
    """Report any text whose extent leaves its column card (overflow check; fonts never shrunk)."""
    r = f.canvas.get_renderer()
    inv = ax.transData.inverted()
    for t in ax.texts:
        bb = t.get_window_extent(r).transformed(inv)
        for x0, x1 in COLS:
            if x0 - 1 < (bb.x0 + bb.x1) / 2 < x1 + 1 and 14.2 < (bb.y0 + bb.y1) / 2 < 47.8 + DY:
                if bb.x0 < x0 + 0.3 or bb.x1 > x1 - 0.3:
                    print(f"  OVERFLOW {t.get_text()!r}: {bb.x0:.1f}-{bb.x1:.1f} vs column {x0}-{x1}")



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "figures/design"))
    a = ap.parse_args()
    mpl.rcParams.update({"font.family": "Arial", "pdf.fonttype": 42, "ps.fonttype": 42})
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fig(out)


if __name__ == "__main__":
    main()
