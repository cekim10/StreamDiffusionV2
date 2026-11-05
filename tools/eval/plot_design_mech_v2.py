#!/usr/bin/env python3
"""Mechanism figures, v2 (2026-11-05, per user): Figs. 2-4 of the design section redrawn in the style of the OSDI
figures the user supplied (M3U, RamRyder, DirectKV, Espresso, Prism) and of the architecture figure v7, in the paper
colorset (gray / blue / yellow-orange / black, no white text). Same content and font sizes as the drafts in
plot_design_figs.py (Times, 16 / 14 pt on the 2x column canvas, 18 / 16 pt on the figure* canvas); the drafts are kept.

  fig2_overview_replay_v2   Continuity Replay: message sequence, source / destination lanes as cards, phase tabs
                            (Prepare / Sync / Resume) with a shaded Sync band, rounded activity bars, numbered steps 1-5.
  fig3_versioned_sink_v2    Versioned Sink Reconstruction: owner and destination as tabbed cards, K / V entry grids,
                            numbered steps 1-4, bytes-on-the-network panel with the legend.
  fig4_wavefront_v2         Continuity Wavefront: three panels as cards with header bands, nodes as rounded cards with
                            role pills, legend in one framed row.

Colors (same meanings as every other figure):
  orange = Sink K/V (sent, fresh, base); blue = reconstruction (replay, K rotated locally); gray = generating /
  neutral; light gray = reused / retained older version; black = control, verification, text.
Conceptual, no measured data.

    python3.11 tools/eval/plot_design_mech_v2.py [--out figures/design]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import numpy as np

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INK, MUTED = "black", "#444444"
GRAY, GRAY_D, LGRAY, BAND = "#A6A6A6", "#6E6E6E", "#E4E4E4", "#F3F3F3"
BLUE, BLUE_LT = "#2F6DB5", "#C9DCF2"
OR, OR_LT, OR_TX = "#E69F00", "#FCEBC2", "#B07800"
FS, FS_S = 16, 14
WC, WT = 6.66, 14.0          # 2x \columnwidth, 2x \textwidth
CHECK = dict(fontfamily="DejaVu Sans", fontweight="bold")


def configure():
    mpl.rcParams.update({"font.family": "Times New Roman", "mathtext.fontset": "cm", "pdf.fonttype": 42,
                         "ps.fonttype": 42, "hatch.linewidth": 1.0, "text.color": INK})


def canvas(w, xm, y0, y1):
    fig = plt.figure(figsize=(w, w * (y1 - y0) / xm))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, xm); ax.set_ylim(y0, y1); ax.axis("off")
    return fig, ax


def rbox(ax, x0, y0, x1, y1, fc="white", ec=INK, lw=1.0, r=0.6, z=2, ls="-", hatch=None):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z, ls=ls, hatch=hatch))


def shadow(ax, x0, y0, x1, y1, r=0.6, z=1.5, d=0.35):
    ax.add_patch(FancyBboxPatch((x0 + d, y0 - d), x1 - x0, y1 - y0, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc="#9A9A9A", ec="none", alpha=0.35, zorder=z))


def arrow(ax, p0, p1, color=INK, lw=1.6, ls="-", ms=13, z=7, rad=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=ms, color=color, lw=lw, ls=ls, zorder=z,
                                 shrinkA=0, shrinkB=0, connectionstyle=f"arc3,rad={rad}"))


def num(ax, x, y, n, fs=FS_S - 1):
    ax.text(x, y, str(n), ha="center", va="center", fontsize=fs, fontweight="bold", color=INK, zorder=12,
            fontfamily="DejaVu Sans", bbox=dict(boxstyle="circle,pad=0.2", fc="white", ec=INK, lw=1.3))


def tab(ax, x0, x1, y0, y1, label, fc, fs=FS):
    """Rotated phase / role tab on the left (RamRyder-style layer label in a rounded tab)."""
    rbox(ax, x0, y0, x1, y1, fc=fc, ec=INK, lw=0.9, r=0.6, z=3)
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, label, rotation=90, ha="center", va="center", fontsize=fs,
            fontweight="bold", zorder=4)


def save(fig, out: Path, name: str):
    for ext in ("pdf", "png"):
        fig.savefig(out / f"{name}.{ext}", dpi=220 if ext == "png" else None)
    plt.close(fig)
    print(f"  {out / name}.{{pdf,png}}")


def text_extent(fig, ax, t):
    """Data-space x extent of a drawn text artist."""
    bb = t.get_window_extent(renderer=fig.canvas.get_renderer())
    (x0, _), (x1, _) = ax.transData.inverted().transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
    return x0, x1


# ----------------------------------------------------------------------------------------------------------------------
# Fig. 2: Continuity Replay
# ----------------------------------------------------------------------------------------------------------------------
def fig2(out: Path):
    XM = 86.0
    WN = WC * XM / 100.0          # same text scale as the other column figures
    fig, ax = canvas(WN, XM, 2.6, 74.4)
    it = dict(fontsize=FS, style="italic", zorder=8)

    # how each state reaches the destination (booktabs table; a square ties each state to its bar color)
    fst = FS_S + 1
    for y, lw in ((73.4, 1.2), (68.4, 0.6), (63.6, 1.2)):
        ax.plot([0.6, XM - 0.6], [y, y], color=INK, lw=lw)
    cols = [(7.0, "State", "Restored", None), (24.6, "Sink KV", "base + patches", (OR, INK)),
            (45.0, "Recent KV", "shadow replay", (BLUE_LT, BLUE)), (63.6, "VAE caches", "rebuilt at $M$", None),
            (79.2, "In-flight", "sent at $M$", None)]   # squares only for the two states drawn as bars
    for x, h, r, sq in cols:
        t = ax.text(x, 70.9, h, ha="center", va="center", fontsize=fst, fontweight="bold")
        ax.text(x, 66.0, r, ha="center", va="center", fontsize=fst, style="normal" if h == "State" else "italic",
                fontweight="bold" if h == "State" else "normal")
        if sq:
            x0, _ = text_extent(fig, ax, t)
            ax.add_patch(Rectangle((x0 - 2.7, 69.9), 2.0, 2.0, fc=sq[0], ec=sq[1], lw=0.8, zorder=5))

    SX, DX, bw = 34.8, 57.6, 2.8
    # lane headers as cards
    for x, half, name in ((SX, 7.5, "Source"), (DX, 12.4, "Destination")):
        shadow(ax, x - half, 58.6, x + half, 62.8, r=0.6, z=2)
        rbox(ax, x - half, 58.6, x + half, 62.8, fc="#FAFAFA", ec=INK, lw=1.0, r=0.6, z=3)
        ax.text(x, 60.7, name, ha="center", va="center", fontsize=FS + 2, fontweight="bold", zorder=4)
    for x in (SX, DX):
        ax.plot([x, x], [58.6, 3.6], color=GRAY_D, lw=0.9, ls=(0, (2, 2)), zorder=1)

    # phases: shaded Sync band, dashed dividers, rotated tabs
    ax.add_patch(Rectangle((6.4, 16.2), XM - 6.4 - 0.6, 19.2, fc=BAND, ec="none", zorder=0))
    for y in (35.4, 16.2):
        ax.plot([6.4, XM - 0.6], [y, y], color="#BBBBBB", lw=0.8, ls=(0, (4, 3)), zorder=0.5)
    tab(ax, 0.8, 5.0, 36.0, 57.6, "Prepare", "white")
    tab(ax, 0.8, 5.0, 16.8, 34.8, "Sync", BAND)
    tab(ax, 0.8, 5.0, 4.0, 15.6, "Resume", "white")

    def bar(x, yt, yb, fc, ec=INK, hatch=None):
        shadow(ax, x - bw / 2, yb, x + bw / 2, yt, r=0.5, z=2.5, d=0.25)
        rbox(ax, x - bw / 2, yb, x + bw / 2, yt, fc=fc, ec=ec, lw=0.9, r=0.5, z=3, hatch=hatch)

    # source lifeline
    bar(SX, 57.2, 55.0, LGRAY, hatch="////")
    bar(SX, 55.0, 36.0, GRAY)
    bar(SX, 34.8, 16.8, "white", hatch="////")
    bar(SX, 15.6, 4.0, OR)
    # destination lifeline
    bar(DX, 52.4, 46.8, OR)
    bar(DX, 46.8, 31.2, BLUE_LT, ec=BLUE)
    bar(DX, 31.2, 23.4, OR_LT)
    bar(DX, 15.6, 4.0, GRAY)

    tr = dict(ha="right", va="center", fontsize=FS, zorder=6)
    tl = dict(ha="left", va="center", fontsize=FS, zorder=6)
    xs, xd = SX - bw / 2 - 1.0, DX + bw / 2 + 1.0
    ax.text(xs, 56.1, "Sink snapshot at $c_0$", **tr)
    ax.text(xs, 46.8, "generates;", **tr)
    ax.text(xs, 43.2, "logs each chunk", **tr)
    ax.text(xs, 28.6, "pauses at $M$", **tr)
    ax.text(xs, 25.0, "(output gap)", **tr)
    ax.text(xs, 11.6, "retains the", **tr)
    ax.text(xs, 8.0, "verified Sink", **tr)
    ax.text(xd, 49.6, "loads Sink base", **tl)
    ax.text(xd, 44.4, "shadow replay", **tl)
    ax.text(xd, 40.8, "(teacher-forced)", **tl)
    ax.text(xd, 37.2, r"$\rightarrow$ Recent KV", **tl)
    ax.text(xd, 29.0, "verifies Sink", **tl)
    ax.text(xd, 25.4, "(block checksums)", **tl)
    ax.text(xd, 11.6, "generates", **tl)
    ax.text(xd, 8.0, "(new owner)", **tl)

    x0, x1 = SX + bw / 2, DX - bw / 2

    def ang(dy):
        return np.degrees(np.arctan2(dy, x1 - x0) * 0.86)   # aspect of the message area

    def msg(y0, y1, color, lw, back=False):
        p0, p1 = ((x1, y0), (x0, y1)) if back else ((x0, y0), (x1, y1))
        arrow(ax, p0, p1, color=color, lw=lw, ms=10 + 3 * lw, z=5)

    def lab(y, text, color, dy, **kw):
        ax.text((x0 + x1) / 2, y, text, ha="center", va="center", color=color, rotation=ang(dy),
                rotation_mode="anchor", **{**it, **kw})

    msg(55.0, 52.4, OR, 2.2)
    lab(55.7, "Sink base", OR_TX, -2.6)
    for y in (46.6, 42.4, 38.2):
        msg(y, y - 2.4, BLUE, 1.1)
    lab(43.4, "log + patches", BLUE, -2.4)
    msg(34.4, 31.2, INK, 1.6)
    lab(29.7, "final state", INK, 0.0)
    lab(26.3, "+ Sink digest", INK, 0.0)
    msg(23.4, 17.4, INK, 1.2, back=True)
    lab(18.3, "Sink OK", INK, 6.0)

    # numbered steps (DirectKV / Espresso style)
    # numbers sit beside the activity bar of the step they mark, clear of the message arrows and labels
    num(ax, x1 - 2.1, 49.6, 1)                 # Sink base loaded
    num(ax, x1 - 2.1, 38.1, 2)                 # log + patches -> shadow replay (between the 2nd and 3rd log arrows)
    num(ax, SX - bw / 2 - 2.2, 32.6, 3)        # pause at M, final state + digest
    num(ax, x1 - 2.1, 17.6, 4)                 # Sink verified, Sink OK
    num(ax, x1 - 2.1, 9.8, 5)                  # destination generates
    save(fig, out, "fig2_overview_replay_v2")


# ----------------------------------------------------------------------------------------------------------------------
# Fig. 3: Versioned Sink Reconstruction
# ----------------------------------------------------------------------------------------------------------------------
UNCH, REFR = "unchanged", "refreshed"
ENTRIES = [UNCH, ("shift", 2), ("shift", 1), UNCH, REFR, ("shift", 1)]


def fig3(out: Path):
    XM = 86.0
    WN = WC * XM / 100.0
    fig, ax = canvas(WN, XM, 14.4, 68.4)
    REUSE, ROT, SENT, FULL = LGRAY, BLUE, OR, "#B3B3B3"   # = Fig. 5a: unchanged, shifted, refresh-required
    fl = FS_S + 1
    FA = FS + 1          # in-figure annotations (v2, e5 ..., rotate locally), larger per user
    w, sp, h, x00 = 6.0, 7.2, 4.0, 13.0
    ex = [x00 + i * sp for i in range(6)]
    cxs = [x + w / 2 for x in ex]

    def kv(y_k, row):
        for i, e in enumerate(ENTRIES):
            kc = vc = REUSE; hatch = None
            if e == REFR:
                if row == "ret":
                    kc = vc = "white"; hatch = "xxxx"
                else:
                    kc = vc = SENT
            elif isinstance(e, tuple) and row != "ret":
                kc = ROT
            for y, c in ((y_k, kc), (y_k - h - 0.4, vc)):
                rbox(ax, ex[i], y, ex[i] + w, y + h, fc=c, ec=GRAY_D if hatch else INK, lw=0.7, r=0.35, z=5,
                     hatch=hatch)
        ax.text(x00 - 1.0, y_k + h / 2, "K", ha="right", va="center", fontsize=FS_S, color=MUTED, zorder=6)
        ax.text(x00 - 1.0, y_k - 0.4 - h / 2, "V", ha="right", va="center", fontsize=FS_S, color=MUTED, zorder=6)

    def card(y0, y1, name, fc):
        shadow(ax, 0.8, y0, XM - 0.8, y1, r=0.8, z=1)
        rbox(ax, 0.8, y0, XM - 0.8, y1, fc=fc, ec=INK, lw=1.0, r=0.8, z=2)
        tab(ax, 0.8, 5.4, y0, y1, name, "#EDEDED")

    tl = dict(ha="left", va="center", fontsize=FS, zorder=6)
    xr = 58.0
    y_own, y_reb, y_ret = 62.4, 45.2, 32.4
    card(56.8, 67.6, "Owner", "#FAFAFA")
    card(26.8, 50.6, "Destination", "#FAFAFA")
    kv(y_own, "own")
    ax.text(xr, y_own, "Sink $v_5$", **tl)
    kv(y_reb, "reb")
    kv(y_ret, "ret")
    ax.text(xr + 3.8, y_reb, "✓", ha="left", va="center", fontsize=FS + 2, color=INK, zorder=6, **CHECK)
    ax.text(xr + 7.4, y_reb, "digest $= v_5$", **tl)
    ax.text(xr, y_ret, "retained $v_2$", **tl)

    # local operations: retained -> rebuilt (shifted keys rotated, the rest reused)
    y_a, y_b = y_ret + h + 0.2, y_reb - h - 0.4 - 0.2
    for i, e in enumerate(ENTRIES):
        if e == REFR:
            continue
        rot = isinstance(e, tuple)
        arrow(ax, (cxs[i], y_a), (cxs[i], y_b), color=BLUE if rot else GRAY_D, lw=1.6 if rot else 1.1, ms=10)
        if rot:
            lb = r"$\delta_1\delta_2$" if e[1] == 2 else r"$\delta_1$"
            ax.text(cxs[i] + 0.5, (y_a + y_b) / 2, lb, ha="left", va="center", fontsize=FS, color=BLUE, zorder=6)
    ax.text(xr + 3.8, (y_a + y_b) / 2, "rotate locally", style="italic", color=MUTED, **{**tl, "fontsize": FA})

    # messages: advertise v2 up, delta down
    arrow(ax, (cxs[0], y_reb + h + 0.2), (cxs[0], y_own - h - 0.4), color=INK, lw=1.3, ms=10)
    ax.text(cxs[0] + 1.2, 53.6, "$v_2$", ha="left", va="center", fontsize=FA, style="italic", zorder=6)
    arrow(ax, (cxs[4], y_own - h - 0.4), (cxs[4], y_reb + h), color=OR, lw=2.0, ms=14, z=6)
    ax.text(cxs[4] + 1.6, 53.6, r"$e_5$, $\delta$ list, digest", ha="left", va="center", fontsize=FA,
            style="italic", color=OR_TX, zorder=6)

    # numbered steps
    num(ax, cxs[0] - 2.4, 53.6, 1)
    num(ax, cxs[4] - 2.4, 53.6, 2)
    num(ax, xr + 1.4, (y_a + y_b) / 2, 3)
    num(ax, xr + 1.4, y_reb, 4)

    # bytes on the network + legend, in one framed panel
    rbox(ax, 0.8, 14.8, XM - 0.8, 25.4, fc="white", ec=GRAY_D, lw=0.9, r=0.8, z=1, ls=(0, (4, 2)))
    ax.text(2.0, 22.4, "full transfer", ha="left", va="center", fontsize=fl)
    ax.text(2.0, 17.6, "OTTER", ha="left", va="center", fontsize=fl)
    rbox(ax, 20.0, 21.2, 40.0, 23.6, fc=FULL, ec=INK, lw=0.7, r=0.35, z=3)
    rbox(ax, 20.0, 16.4, 23.7, 18.8, fc=SENT, ec=INK, lw=0.7, r=0.35, z=3)
    ax.text(24.7, 17.6, "+ KB", ha="left", va="center", fontsize=fl)
    items = [(REUSE, None, "reused"), (SENT, None, "sent"), (ROT, None, "K rotated (RoPE)"), ("white", "xxxx", "stale")]
    for k, (c, hatch, t) in enumerate(items):
        x, y = (43.5, 57.5)[k // 2], (22.4, 17.6)[k % 2]
        rbox(ax, x, y - 1.3, x + 2.6, y + 1.3, fc=c, ec=GRAY_D if hatch else INK, lw=0.7, r=0.3, z=3, hatch=hatch)
        ax.text(x + 3.6, y, t, ha="left", va="center", fontsize=fl)
    save(fig, out, "fig3_versioned_sink_v2")


# ----------------------------------------------------------------------------------------------------------------------
# Fig. 4: Continuity Wavefront
# ----------------------------------------------------------------------------------------------------------------------
V1, V2, CUR, BAD, EMPTY = "v1", "v2", "cur", "bad", "empty"
VCOL = {V1: LGRAY, V2: GRAY, CUR: OR, BAD: "white", EMPTY: "white"}
REFRESHED = {2, 5, 7}          # e3, e6, e8 (0-based) refreshed by the owner E2 after v1
POS = {"E1": (18, 37), "E2": (50, 52), "E3": (82, 37), "E4": (50, 21)}


def fig4(out: Path):
    fig, ax = canvas(WT, 300, 0.0, 70.0)
    nw, nh = 28.0, 12.0
    fb, fsm = FS + 2, FS_S + 2
    FA = FS + 3          # in-figure annotations (lineage, digest), larger per user

    def panel(px, title):
        x0, x1 = px + 1.2, px + 98.8
        shadow(ax, x0, 9.4, x1, 69.4, r=1.2, z=0.5, d=0.5)
        rbox(ax, x0, 9.4, x1, 69.4, fc="white", ec=INK, lw=1.0, r=1.2, z=0.6)
        ax.add_patch(FancyBboxPatch((x0, 62.4), x1 - x0, 7.0, boxstyle="round,pad=0,rounding_size=1.2", fc=BAND,
                                    ec="none", zorder=0.7))
        ax.add_patch(Rectangle((x0, 62.4), x1 - x0, 2.0, fc=BAND, ec="none", zorder=0.7))
        ax.plot([x0, x1], [62.4, 62.4], color=INK, lw=0.8, zorder=0.8)
        rbox(ax, x0, 9.4, x1, 69.4, fc="none", ec=INK, lw=1.0, r=1.2, z=0.9)
        ax.text(px + 50, 65.9, title, ha="center", va="center", fontsize=fb, zorder=2)

    def node(px, name, role, strip, lw=1.0, owner=False):
        cx, cy = POS[name]; cx += px
        x0, y0 = cx - nw / 2, cy - nh / 2
        shadow(ax, x0, y0, x0 + nw, y0 + nh, r=0.8, z=2.5, d=0.4)
        rbox(ax, x0, y0, x0 + nw, y0 + nh, fc="#FAFAFA", ec=INK, lw=lw, r=0.8, z=3)
        ax.text(x0 + 1.2, cy + nh / 2 - 2.9, name, ha="left", va="center", fontsize=fb, fontweight="bold", zorder=5)
        if role:
            ax.text(x0 + nw - 1.6, cy + nh / 2 - 2.9, role, ha="right", va="center", fontsize=fsm, style="italic",
                    zorder=5, bbox=dict(boxstyle="round,pad=0.18,rounding_size=0.6",
                                        fc=GRAY if owner else "white", ec=INK, lw=0.8))
        sw, sp = 2.7, 3.1
        xs0 = cx - (8 * sp - (sp - sw)) / 2
        for i, s in enumerate(strip):
            rbox(ax, xs0 + i * sp, y0 + 1.3, xs0 + i * sp + sw, y0 + 4.9, fc=VCOL[s],
                 ec=INK if s != EMPTY else GRAY, lw=0.6, r=0.3, z=4)
            if s == BAD:
                xa, xb, ya, yb = xs0 + i * sp + 0.45, xs0 + i * sp + sw - 0.45, y0 + 1.75, y0 + 4.45
                ax.plot([xa, xb], [ya, yb], color=INK, lw=1.0, zorder=5)
                ax.plot([xa, xb], [yb, ya], color=INK, lw=1.0, zorder=5)

    def link(px):
        names = list(POS)
        for i in range(4):
            for j in range(i + 1, 4):
                (a, b), (c, d) = POS[names[i]], POS[names[j]]
                ax.plot([a + px, c + px], [b, d], color="#E2E2E2", lw=0.8, zorder=1)

    def edge_pt(px, a, b):
        (ax_, ay), (bx, by) = POS[a], POS[b]
        dx, dy = bx - ax_, by - ay
        t = min((nw / 2) / abs(dx) if dx else 9e9, (nh / 2) / abs(dy) if dy else 9e9)
        return ax_ + px + dx * t, ay + dy * t

    def move(px, a, b, color, lw=1.6, ls="-"):
        arrow(ax, edge_pt(px, a, b), edge_pt(px, b, a), color=color, lw=lw, ls=ls, ms=8 + 3 * lw, z=6)

    titles = [r"(a) $t_1$: migrate E1 $\rightarrow$ E2", r"(b) $t_2$: stage valid entries",
              r"(c) $t_3$: migrate E2 $\rightarrow$ E3"]
    for k, t in enumerate(titles):
        panel(100 * k, t)

    v1 = [V1] * 8
    cur = [CUR if i in REFRESHED else V1 for i in range(8)]
    e1_t2 = [BAD if i in REFRESHED else V1 for i in range(8)]
    e4_part = [V2 if i in (2, 3) else EMPTY for i in range(8)]
    e3_t2 = [V1 if i in (0, 1) else EMPTY for i in range(8)]
    e3_t3 = [V2 if i in (2, 3) else CUR if i in (5, 7) else V1 for i in range(8)]

    # (a) E1 -> E2 completes; E1 keeps its verified Sink as v1
    px = 0; link(px)
    node(px, "E1", "keeps $v_1$", v1)
    node(px, "E2", "owner", v1, owner=True)
    node(px, "E3", "", [EMPTY] * 8)
    node(px, "E4", "", [EMPTY] * 8)
    move(px, "E1", "E2", INK, lw=2.2)

    # (b) owner lineage invalidates refreshed entries; holders stage to every non-owner site
    px = 100; link(px)
    node(px, "E1", "holder", e1_t2)
    node(px, "E2", "owner", cur, owner=True)
    node(px, "E3", "", e3_t2)
    node(px, "E4", "canceled", e4_part)
    move(px, "E2", "E1", INK, lw=1.4, ls=(0, (1, 1.5)))
    ax.text(px + 27.0, 49.6, "lineage", ha="right", va="center", fontsize=FA, style="italic", zorder=6)
    for a, b in (("E1", "E3"), ("E1", "E4"), ("E4", "E3")):
        move(px, a, b, GRAY_D, lw=1.5, ls=(0, (3, 2)))

    # (c) E3 takes each entry's newest valid version, verifies against E2
    px = 200; link(px)
    node(px, "E1", "holder", e1_t2)
    node(px, "E2", "owner", cur, owner=True)
    node(px, "E3", "target", e3_t3, lw=2.0)
    node(px, "E4", "holder", e4_part)
    move(px, "E1", "E3", GRAY_D)
    move(px, "E4", "E3", GRAY_D)
    move(px, "E2", "E3", OR, lw=2.0)
    cx, cy = POS["E3"]
    # below the E4 -> E3 arrow, inside the panel edge (FS + 2: FA would run past the panel)
    ax.text(px + cx - 14.0, cy - nh / 2 - 9.0, "✓", ha="center", va="center", fontsize=FS + 2, zorder=7, **CHECK)
    ax.text(px + cx - 11.6, cy - nh / 2 - 9.0, "digest $=$ E2", ha="left", va="center", fontsize=FS + 2, zorder=7)

    # legend: one framed row (Espresso)
    items = [("cell", LGRAY, "$v_1$ (old owner)"), ("cell", GRAY, "$v_2$ (canceled target)"),
             ("cell", OR, "current (owner)"), ("bad", "white", "invalid"), ("cell", "white", "not held"),
             ("line", INK, "migration"), ("dash", GRAY_D, "staging"), ("dot", INK, "lineage")]
    widths = [(7.2 if k in ("line", "dash", "dot") else 4.0) + len(t.replace("$", "")) * 1.85 for k, _, t in items]
    tot = sum(widths) + 5.0 * (len(items) - 1)
    x = (300.0 - tot) / 2
    rbox(ax, x - 3.0, 0.6, x + tot + 3.0, 7.6, fc="white", ec=GRAY_D, lw=0.9, r=1.0, z=1, ls=(0, (4, 2)))
    for (kind, c, t), wd in zip(items, widths):
        if kind in ("line", "dash", "dot"):
            ls = {"line": "-", "dash": (0, (3, 2)), "dot": (0, (1, 1.5))}[kind]
            ax.plot([x, x + 6.0], [4.1, 4.1], color=c, lw=1.8, ls=ls, zorder=3)
            xt = x + 7.2
        else:
            rbox(ax, x, 2.3, x + 2.7, 5.9, fc=c, ec=INK if c != "white" or kind == "bad" else GRAY, lw=0.6, r=0.3,
                 z=3)
            if kind == "bad":
                ax.plot([x + 0.45, x + 2.25], [2.75, 5.45], color=INK, lw=1.0, zorder=4)
                ax.plot([x + 0.45, x + 2.25], [5.45, 2.75], color=INK, lw=1.0, zorder=4)
            xt = x + 4.0
        ax.text(xt, 4.1, t, ha="left", va="center", fontsize=fsm, zorder=3)
        x += wd + 5.0
    save(fig, out, "fig4_wavefront_v2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "figures/design"))
    a = ap.parse_args()
    configure()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fig2(out); fig3(out); fig4(out)


if __name__ == "__main__":
    main()
