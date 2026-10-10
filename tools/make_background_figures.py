#!/usr/bin/env python3
"""Background figures (observation -> insight structure), one file per panel, from the raw experiment records.
Visual style matches the EC-LLM-eval paper figures: Times New Roman, closed frame with inward ticks, no grid,
black-edged hatched fills, white-faced markers, 300 dpi, 5.83 x 3.22 in panels, no in-figure titles.

Background
  fig2a_state_breakdown        execution-state size by temporal role       <- frozen Phase 1 FullMigration bytes
  fig2b_state_ablation         continuity after losing one component        <- gen/original_s0_k2/ablation_raw.csv
  fig3_state_loss_frames       frames after migration (5 time points)       <- mechanism/videos
  fig4a_late_binding           execution resumes first, Sink binds later    <- mechanism/ablation_raw.csv
  fig4b_recovery_aligned       recovery aligned at Sink arrival             <- mechanism/ablation_raw.csv
  fig5a_mobility_slow / fig5b_mobility_fast   Sink progress at the current site + continuity, rho<1 / rho>1  <- mobility/mob_restart_*.json
Evaluation / Appendix (moved out of Background, unchanged content)
  eval/fig_mobility_policies   continuity-ready latency vs rho per policy   <- mobility/mob_{restart,relay,direct}_tm*.json
  eval/fig_late_binding_frames late binding, frames                         <- mechanism/videos
  appendix/fig_semantics_heatmap   temporal-semantics heatmap               <- gen/original_s0_k2/ablation_raw.csv

Temporal roles keep one encoding everywhere: Immediate red, Durable blue (#486ee2), Ephemeral gray.
Usage: python tools/make_background_figures.py [--out results/state_migration/figures/background]
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
import sys
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import ConnectionPatch, Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import make_motivation_figures as mm  # noqa: E402
import make_qualitative_figures as mq  # noqa: E402
from make_state_size_figure import GiB, MiB, load_bytes  # noqa: E402

# ---------------------------------------------------------------- EC-LLM-eval style constants
FONT_FAMILY = "Times New Roman"
LABEL_FONT_SIZE = 19
TICK_FONT_SIZE = 16
LEGEND_FONT_SIZE = 14
ANNOT_FONT_SIZE = 14
SPINE_WIDTH = 1.0
PANEL_FIG_SIZE = (5.83, 3.22)
WIDE_W = 12.4

BLUE, ORANGE, RED = "#486ee2", "#ffb226", "red"
BLACK, DARKGRAY, DIMGRAY = "black", "darkgray", "dimgray"
ROLE = {"Immediate": RED, "Durable": BLUE, "Ephemeral": DIMGRAY}

TAU = 35.0   # rejoin criterion (justified in fig4b from the data)
YMAX = 50.0  # plotted range; the uninterrupted run itself is bit-identical (reported as 99 dB) and off scale


def configure_matplotlib() -> None:
    mpl.rcParams["font.family"] = FONT_FAMILY
    mpl.rcParams["mathtext.fontset"] = "cm"
    mpl.rcParams["axes.spines.right"] = True
    mpl.rcParams["axes.spines.top"] = True
    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"] = 42
    mpl.rcParams["hatch.linewidth"] = 1.0
    # black frame and ink as in the EC-LLM-eval figures (imported helper modules set gray defaults)
    for key in ("axes.edgecolor", "axes.labelcolor", "xtick.color", "ytick.color", "text.color"):
        mpl.rcParams[key] = "black"


def save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix(".png"), bbox_inches="tight", dpi=300)
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"  {path.relative_to(ROOT)}.{{pdf,png}}")


def style_axis(ax, ylabel: str = "", xlabel: str = "", ylim=None, yticks=None) -> None:
    for side in ("left", "bottom", "right", "top"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_linewidth(SPINE_WIDTH)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=LABEL_FONT_SIZE, labelpad=8)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=LABEL_FONT_SIZE, labelpad=5)
    ax.tick_params(axis="y", direction="in", width=1, length=5, pad=5)
    ax.tick_params(axis="x", direction="in", width=1, length=5, pad=7)
    if ylim is not None:
        ax.set_ylim(*ylim)
    if yticks is not None:
        ax.set_yticks(yticks)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontsize(TICK_FONT_SIZE)
        label.set_family(FONT_FAMILY)


def line(ax, x, y, color, marker, linestyle, label, lw=1.8, markevery=4, emphasized=False):
    ax.plot(x, y, lw=2.2 if emphasized else lw, color=color, linestyle=linestyle, marker=marker, markersize=7, markevery=markevery,
            markerfacecolor=color if emphasized else "white", markeredgecolor=color, markeredgewidth=1.4, label=label, zorder=3 if emphasized else 2)


def legend(target, handles=None, **kw):
    base = dict(frameon=False, prop={"size": LEGEND_FONT_SIZE, "family": FONT_FAMILY}, handlelength=2.2, columnspacing=1.0, handletextpad=0.5)
    base.update(kw)
    return target.legend(handles=handles, **base) if handles is not None else target.legend(**base)


def text(ax, x, y, s, size=ANNOT_FONT_SIZE, **kw):
    return ax.text(x, y, s, fontsize=size, family=FONT_FAMILY, **kw)


def post_curves(raw: Path, cfgs: list[str]):
    """Mean PSNR per chunk after migration (rel_call >= 0), unclipped."""
    by = {c: {} for c in cfgs}
    for r in csv.DictReader(open(raw)):
        if r["config"] in by and r["psnr"] and int(r["rel_call"]) >= 0:
            by[r["config"]].setdefault(int(r["rel_call"]), []).append(float(r["psnr"]))
    return {c: (sorted(d), [st.mean(d[k]) for k in sorted(d)]) for c, d in by.items()}


def reference_note(ax):
    """The reference run is bit-identical to itself (the harness reports 99 dB); no curve reaches the 50 dB axis top."""
    text(ax, 1.0, 1.02, "↑ Uninterrupted execution: bit-identical (off scale)", ANNOT_FONT_SIZE - 1, transform=ax.transAxes,
         ha="right", va="bottom", color=DIMGRAY)


# ----------------------------------------------------------------------------- Fig. 2a
def fig2a(out: Path):
    """Area-true treemap of the per-session execution state. The whole square is the full state; areas are exact.
    Dashed outlines nest the three migration objectives: full state > continuity-preserving > immediate handoff."""
    from matplotlib.patches import Rectangle
    comp, src = load_bytes()
    inflight, meta = comp["inflight"], comp["meta"]
    imm, sink, recent, vae = inflight + meta, comp["sink"], comp["recent"], comp["vae"]
    total = imm + sink + recent + vae
    pct = lambda b: 100.0 * b / total  # noqa: E731
    # layout (unit square = total): left column = Sink(+Immediate) below Recent KV, right column = VAE caches
    wl = (imm + sink + recent) / total
    hs = (imm + sink) / (imm + sink + recent)
    s = (imm / total) ** 0.5                        # side of the area-true Immediate square
    fig, ax = plt.subplots(figsize=(7.4, 3.9))
    ax.set_xlim(-0.01, 2.02); ax.set_ylim(-0.02, 1.02); ax.set_aspect("equal"); ax.axis("off")
    box = dict(boxstyle="square,pad=0.15", fc="white", ec="none")

    def block(x, y, w, h, fc, hatch, label, fy=0.5):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, hatch=hatch, edgecolor=BLACK, lw=1.2, zorder=2))
        text(ax, x + w / 2, y + h * fy, label, ANNOT_FONT_SIZE - 1, ha="center", va="center", zorder=4, bbox=box if hatch else None,
             color="white" if fc in (BLUE, BLACK) and not hatch else BLACK, linespacing=1.15)
    block(0, 0, wl, hs, BLUE, "x", f"Sink KV\n{sink / GiB:.2f} GiB\nDurable\n{pct(sink):.1f}%", fy=0.62)
    block(0, hs, wl, 1 - hs, DARKGRAY, None, f"Recent KV\n{recent / GiB:.2f} GiB\nEphemeral\n{pct(recent):.1f}%")
    block(wl, 0, 1 - wl, 1, "white", "//", f"VAE caches\n{vae / GiB:.2f} GiB\nEphemeral\n{pct(vae):.1f}%", fy=0.72)
    # Immediate state: true-to-area square in the Sink corner
    ax.add_patch(Rectangle((0, 0), s, s, facecolor=RED, edgecolor=RED, lw=0.6, zorder=5))
    # migration objectives as nested outlines
    ax.add_patch(Rectangle((0, 0), 1, 1, fill=False, edgecolor=BLACK, lw=2.0, zorder=6))
    # magnified Immediate square (area-true split into in-flight rows and metadata)
    m0x, m0y, ms = 1.10, 0.03, 0.36
    fi = inflight / imm
    ax.add_patch(Rectangle((m0x, m0y), ms * fi, ms, facecolor=RED, edgecolor=BLACK, lw=1.0, zorder=3))
    ax.add_patch(Rectangle((m0x + ms * fi, m0y), ms * (1 - fi), ms, facecolor="white", hatch="..", edgecolor=RED, lw=0, zorder=3))
    ax.add_patch(Rectangle((m0x, m0y), ms, ms, fill=False, edgecolor=RED, lw=2.0, zorder=4))
    ax.plot([s, m0x], [0.002, m0y], color=RED, lw=0.9, ls=(0, (3, 2)), zorder=3)
    ax.plot([s, m0x], [s, m0y + ms], color=RED, lw=0.9, ls=(0, (3, 2)), zorder=3)
    text(ax, m0x + ms * fi / 2, m0y + ms + 0.025, f"In-flight\n{inflight / MiB:.2f} MiB", ANNOT_FONT_SIZE - 3, ha="left", va="bottom")
    text(ax, m0x + ms * (fi + (1 - fi) / 2), m0y + ms / 2, f"Metadata\n{meta / MiB:.2f} MiB", ANNOT_FONT_SIZE - 2, ha="center", va="center", bbox=box)
    text(ax, m0x + ms + 0.03, m0y + ms / 2, f"Immediate state\n{imm / MiB:.2f} MiB ({pct(imm):.2f}%)\nmagnified {ms / s:.0f}× (linear)",
         ANNOT_FONT_SIZE - 1, ha="left", va="center", color=RED)
    # objective key: outline style + bytes each objective must move
    # key: which blocks each migration objective must move (swatches = the blocks themselves)
    keys = [([("white", None, BLACK, 2.0)], "Full-state migration", f"all blocks, {total / GiB:.2f} GiB"),
            ([(RED, None, RED, 0.8), (BLUE, "x", BLACK, 1.0)], "Continuity-preserving", f"{(imm + sink) / GiB:.2f} GiB ({total / (imm + sink):.1f}× less)"),
            ([(RED, None, RED, 0.8)], "Immediate handoff", f"{imm / MiB:.2f} MiB ({total / imm:,.0f}× less)")]
    y = 1.0
    text(ax, 1.10, y, "State each migration objective must move", ANNOT_FONT_SIZE - 1, ha="left", va="top", weight="bold")
    y -= 0.04
    for swatches, name, val in keys:
        y -= 0.12
        for i, (fc, hatch, ec, lw) in enumerate(swatches):
            ax.add_patch(Rectangle((1.10 + i * 0.055, y - 0.035), 0.045, 0.07, facecolor=fc, hatch=hatch, edgecolor=ec, lw=lw))
        text(ax, 1.23, y, f"{name}: {val}", ANNOT_FONT_SIZE - 1, ha="left", va="center")
    save(fig, out / "fig2a_state_breakdown")
    return {"source_run": src, "immediate_MiB": imm / MiB, "inflight_MiB": inflight / MiB, "meta_MiB": meta / MiB, "sink_GiB": sink / GiB,
            "recent_GiB": recent / GiB, "vae_GiB": vae / GiB, "total_GiB": total / GiB, "pct": {"immediate": pct(imm), "durable": pct(sink), "ephemeral": pct(recent + vae)},
            "full_over_immediate": total / imm, "full_over_continuity": total / (imm + sink), "zoom_linear": ms / s}


# ----------------------------------------------------------------------------- Fig. 2b
ABL = [("drop_inflight", "No in-flight rows (0.19 MiB)", RED, "^", "solid", "Immediate"),
       ("drop_kv_recent", "No recent KV (1.61 GiB)", DIMGRAY, "o", "dashed", "Ephemeral"),
       ("drop_vae_all", "No VAE caches (2.80 GiB)", DARKGRAY, "D", "dashdot", "Ephemeral"),
       ("ph_localrefresh", "No Sink KV (1.61 GiB)", BLUE, "s", "solid", "Durable")]


def fig2b(out: Path):
    raw = ROOT / "results/state_migration/gen/original_s0_k2/ablation_raw.csv"
    cv = post_curves(raw, [a[0] for a in ABL])
    fig, ax = plt.subplots(figsize=PANEL_FIG_SIZE)
    ends = {}
    for cfg, label, col, mk, ls, role in ABL:
        x, y = cv[cfg]
        line(ax, x, y, col, mk, ls, label, emphasized=(role == "Durable"))
        ends[cfg] = float(np.mean(y[-3:]))
    lab = {"Immediate": ends["drop_inflight"], "Durable": ends["ph_localrefresh"], "Ephemeral": (ends["drop_kv_recent"] + ends["drop_vae_all"]) / 2}
    for role, yv in lab.items():
        text(ax, 40.0, yv, role, ha="left", va="center", color=ROLE[role], clip_on=False)
    reference_note(ax)
    ax.set_xlim(0, 39); ax.set_xticks([0, 10, 20, 30])
    style_axis(ax, ylabel="PSNR to Uninterrupted (dB)", xlabel="Chunks After Migration", ylim=(8, YMAX), yticks=[10, 20, 30, 40, 50])
    legend(ax, loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=2)
    save(fig, out / "fig2b_state_ablation")
    return {cfg: {"psnr_min": min(cv[cfg][1]), "psnr_max": max(cv[cfg][1]), "psnr_last3_mean": ends[cfg]} for cfg, *_ in ABL}


# ----------------------------------------------------------------------------- Fig. 3
def fig3(out: Path):
    mq.strip([("Uninterrupted", "baseline", "reference"),
              ("No Sink KV", "ph_localrefresh", "plausible, but a\ndifferent trajectory"),
              ("Ephemeral +\nin-flight lost", "xfer_sink+meta", "recent KV, VAE, in-flight\ndropped together")],
             [0, 2, 8, 16, 32], out / "fig3_state_loss_frames", "")
    print(f"  {(out / 'fig3_state_loss_frames').relative_to(ROOT)}.{{pdf,png}}")


# ----------------------------------------------------------------------------- Fig. 4a / 4b
DELAYS = [(1, ORANGE, "o", "dashdot"), (4, BLUE, "s", "dashed"), (8, DIMGRAY, "P", "dotted"), (16, BLACK, "D", "solid")]


def fig4(out: Path):
    raw = ROOT / "results/state_migration/mechanism/ablation_raw.csv"
    cv = post_curves(raw, [f"ph_zero_{d}" for d, *_ in DELAYS] + ["ph_zero_noswap"])
    never_max = max(cv["ph_zero_noswap"][1])
    # (a) absolute time
    fig, ax = plt.subplots(figsize=PANEL_FIG_SIZE)
    for d, col, mk, ls in DELAYS:
        if d == 8:
            continue  # (a) stays readable; delay 8 is in (b)
        x, y = cv[f"ph_zero_{d}"]
        line(ax, x, y, col, mk, ls, f"Sink after {d} chunk{'s' if d > 1 else ''}", emphasized=(d == 16))
        ax.axvline(d, color=col, lw=1.0, ls=(0, (2, 2)), zorder=1)
    x, y = cv["ph_zero_noswap"]
    line(ax, x, y, RED, "^", "solid", "Sink never arrives")
    reference_note(ax)
    text(ax, 38.5, 30.5, "Output from chunk 0\nin every run; only\ncontinuity waits\nfor the Sink", ANNOT_FONT_SIZE - 1, ha="right", va="top")
    ax.set_xlim(0, 39); ax.set_xticks([0, 10, 20, 30])
    style_axis(ax, ylabel="PSNR to Uninterrupted (dB)", xlabel="Chunks After Migration", ylim=(8, YMAX), yticks=[10, 20, 30, 40, 50])
    legend(ax, loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=2)
    save(fig, out / "fig4a_late_binding")
    # (b) aligned at Sink arrival
    fig, bx = plt.subplots(figsize=PANEL_FIG_SIZE)
    rejoin = {}
    for d, col, mk, ls in DELAYS:
        x, y = cv[f"ph_zero_{d}"]
        rel = [(k - d, v) for k, v in zip(x, y) if -6 <= k - d <= 22]
        pre = [(k, v) for k, v in rel if k <= 0]; post = [(k, v) for k, v in rel if k >= 0]
        bx.plot([k for k, _ in pre], [v for _, v in pre], color=col, lw=1.2, ls=ls, alpha=0.35, zorder=1)
        line(bx, [k for k, _ in post], [v for _, v in post], col, mk, ls, f"Δ = {d}", markevery=3, emphasized=(d == 16))
        rejoin[d] = next((k for k, v in post if v >= TAU), None)
    bx.axhspan(8, never_max, color="#eeeeee", zorder=0, lw=0)
    text(bx, 21.6, 9.0, f"Sink never arrives: ≤ {never_max:.1f} dB in every chunk", ANNOT_FONT_SIZE - 1, ha="right", va="bottom")
    bx.axvline(0, color=BLACK, lw=1.0, ls="--")
    bx.axhline(TAU, color=BLACK, lw=1.0, ls=":")
    text(bx, 21.6, TAU + 0.5, f"Rejoin criterion {TAU:.0f} dB", ANNOT_FONT_SIZE - 1, ha="right", va="bottom")
    lo, hi = min(v for v in rejoin.values() if v is not None), max(v for v in rejoin.values() if v is not None)
    text(bx, 21.6, 33.8, f"Rejoins {lo}–{hi} chunks after\nbinding, largely\nindependent of Δ", ANNOT_FONT_SIZE - 1, ha="right", va="top")
    text(bx, -3.0, 9.0, "Waiting\n(no Sink)", ANNOT_FONT_SIZE - 1, ha="center", va="bottom")
    bx.set_xlim(-6, 22); bx.set_xticks([-5, 0, 5, 10, 15, 20])
    style_axis(bx, ylabel="PSNR to Uninterrupted (dB)", xlabel="Chunks After the Sink Arrives", ylim=(8, YMAX), yticks=[10, 20, 30, 40, 50])
    lg = legend(bx, loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=4, title="Sink arrival delay Δ (chunks)")
    lg.get_title().set_fontsize(LEGEND_FONT_SIZE); lg.get_title().set_family(FONT_FAMILY)
    save(fig, out / "fig4b_recovery_aligned")
    return {"never_arrives_max_psnr": never_max, "rejoin_chunks_after_arrival": rejoin}


# ----------------------------------------------------------------------------- Fig. 5
SITE = {"B": (BLUE, "x"), "C": (ORANGE, "--"), "D": (DARKGRAY, None)}


def sink_progress(run: Path):
    """Share of the Sink held by the CURRENT execution site over time, from the measured transfer records.
    Under the restart policy each attempt streams segments from A at the shaped link rate, so progress is linear between
    the attempt's measured start and its measured end (completion or abort at the move) with the measured byte count."""
    exec_blocks, attempts, ready, moves = mm.restart_timeline(run)
    r = __import__("json").load(open(run))
    sink_mib = r["bytes"]["A->" + r["edges"][-1]] / MiB
    return exec_blocks, attempts, ready, moves, sink_mib, r["calls"]


def progress_panel(path: Path, run: Path, t_end: float, label_rho: str):
    exec_blocks, attempts, ready, moves, sink_mib, calls = sink_progress(run)
    fig = plt.figure(figsize=(PANEL_FIG_SIZE[0], 4.6))
    gs = fig.add_gridspec(3, 1, height_ratios=[0.32, 1.6, 1.0], hspace=0.16)
    sx = fig.add_subplot(gs[0]); px = fig.add_subplot(gs[1], sharex=sx); qx = fig.add_subplot(gs[2], sharex=sx)
    box = dict(boxstyle="square,pad=0.1", fc="white", ec="none")
    # execution site strip
    for e, a, b in exec_blocks:
        b = t_end if b is None else min(b, t_end)
        fc, hatch = SITE[e]
        sx.barh(0, b - a, left=a, height=1.0, color=fc, hatch=hatch, edgecolor=BLACK, lw=1.0)
        if b - a > 1.2:
            text(sx, (a + b) / 2, 0, e, ANNOT_FONT_SIZE - 1, ha="center", va="center",
                 color=BLACK, bbox=None if hatch is None else box)
    sx.set_ylim(-0.5, 0.5); sx.set_yticks([0]); sx.set_yticklabels(["Site"])
    # Sink progress at the current site
    discarded, binds = [], []
    for e, a, b, ok, mb in attempts:
        b_c = t_end if b is None else min(b, t_end)
        frac = 100.0 * (mb / sink_mib if not ok else 1.0)
        xs = [a, b_c]; ys = [0.0, frac * (b_c - a) / (b - a) if b and b > a else frac]
        fc, hatch = SITE[e]
        if ok:
            px.fill_between(xs, 0, ys, color=fc, hatch=hatch, edgecolor=BLACK, lw=1.0, alpha=1.0, zorder=2)
            px.plot(xs, ys, color=BLACK, lw=1.2, zorder=3)
            nxt = next((t for _, _, t in moves if t > b), t_end)
            px.plot([b, nxt], [100, 100], color=fc, lw=2.4, zorder=3)
            px.plot([b], [100], marker="*", ms=8, color=BLUE, markeredgecolor=BLACK, markeredgewidth=0.6, zorder=5)
            text(px, b, 105, "bind", ANNOT_FONT_SIZE - 2, ha="center", va="bottom")
            binds.append((e, b))
        else:
            px.fill_between(xs, 0, ys, facecolor="white", hatch="xxxx", edgecolor=RED, lw=0.0, zorder=2)
            px.plot(xs, ys, color=RED, lw=1.4, zorder=3)
            px.plot([b_c, b_c], [ys[1], 0], color=RED, lw=1.4, zorder=3)
            discarded.append(mb)
    for _, to, t in moves:
        for ax in (sx, px, qx):
            ax.axvline(t, color=BLACK, lw=0.9, ls=":", zorder=1)
    if discarded:
        text(px, 0.6, 62, f"{sum(discarded):.0f} MiB transferred,\nnot reused (" + " + ".join(f"{m:.0f}" for m in discarded) + ")",
             ANNOT_FONT_SIZE - 2, ha="left", va="top", color=RED,
             bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"), zorder=4)
    px.axhline(100, color=DIMGRAY, lw=0.8, ls="--", zorder=1)
    px.set_ylim(0, 120); px.set_yticks([0, 50, 100])
    # continuity measured at the executing site (per chunk)
    for e in SITE:
        pts = [(c["t_out"], c["psnr"]) for c in calls if c["node"] == e and c["psnr"] is not None and c["t_out"] <= t_end]
        if pts:
            col = {"B": BLUE, "C": ORANGE, "D": DIMGRAY}[e]
            qx.plot([p[0] for p in pts], [p[1] for p in pts], color=col, lw=1.6, marker="o", ms=3.2, markevery=3,
                    markerfacecolor="white", markeredgecolor=col, markeredgewidth=1.0)
    qx.axhline(TAU, color=BLACK, lw=0.9, ls=":")
    text(qx, 0.5, TAU + 1.0, f"{TAU:.0f} dB rejoin threshold", ANNOT_FONT_SIZE - 3, ha="left", va="bottom")
    # bind (star) -> rejoin (first chunk at or above the threshold at that site): the recovery interval after binding
    for e, tb in binds:
        rj = next((c for c in calls if c["node"] == e and c["t_out"] >= tb and c["psnr"] is not None and c["psnr"] >= TAU), None)
        qx.plot([tb], [12.5], marker="*", ms=8, color=BLUE, markeredgecolor=BLACK, markeredgewidth=0.6, zorder=5, clip_on=False)
        qx.axvline(tb, color=BLUE, lw=0.9, ls="--", zorder=1)
        if rj is None or rj["t_out"] > t_end:
            continue
        tr = rj["t_out"]
        qx.axvspan(tb, tr, color="#dfe6fb", zorder=0, lw=0)
        qx.plot([tr], [rj["psnr"]], marker="v", ms=5.5, color=BLACK, zorder=6)
        qx.annotate("", xy=(tb, 45.5), xytext=(tr, 45.5), arrowprops=dict(arrowstyle="<->", lw=1.0))
        text(qx, (tb + tr) / 2, 46.3, f"{tr - tb:.1f} s", ANNOT_FONT_SIZE - 3, ha="center", va="bottom")
        text(qx, tr - 0.3, TAU + 2.2, "rejoin", ANNOT_FONT_SIZE - 3, ha="right", va="bottom")
    qx.set_ylim(10, 52); qx.set_xlim(0, t_end)
    style_axis(sx); style_axis(px, ylabel="Sink\navailable (%)"); style_axis(qx, ylabel="PSNR (dB)", xlabel="Time since first handoff (s)", yticks=[10, 30, 50])
    for ax in (sx, px):
        ax.tick_params(labelbottom=False)
    sx.tick_params(axis="y", length=0); sx.tick_params(axis="x", length=0)
    text(sx, 0.0, 1.25, label_rho, LABEL_FONT_SIZE - 3, transform=sx.transAxes, ha="left", va="bottom")
    fig.align_ylabels([sx, px, qx])
    save(fig, path)


def fig5(out: Path):
    d = ROOT / "results/state_migration/mobility"
    progress_panel(out / "fig5a_mobility_slow", d / "mob_restart_tm24_h2.json", 50.0, r"(a) Slow mobility ($\rho<1$)")
    progress_panel(out / "fig5b_mobility_fast", d / "mob_restart_tm2_h3_iu.json", 50.0, r"(b) Fast mobility ($\rho>1$)")


# ----------------------------------------------------------------------------- Evaluation / Appendix (moved out of Background)
def eval_mobility_policies(out: Path, t_s: float = 16.6):
    fig, ax = plt.subplots(figsize=PANEL_FIG_SIZE)
    styles = [("restart", "Restart", ORANGE, "o", "dashdot"), ("relay", "Relay", BLUE, "s", "dashed"), ("direct", "Oracle Direct", BLACK, "D", "dotted")]
    for pol, label, col, mk, ls in styles:
        pts = [(tm, y, w) for tm, y, w in mm.mobility_points(pol) if y is not None]
        line(ax, [t_s / tm for tm, _, _ in pts], [y for _, y, _ in pts], col, mk, ls, label, markevery=1)
    ax.axvline(1.0, color=BLACK, lw=1.0, ls="--"); ax.axvspan(1.0, 20, color="#eeeeee", zorder=0)
    ax.set_xscale("log"); ax.set_xlim(0.45, 20)
    ax.set_xticks([0.5, 1, 2, 4, 8, 16]); ax.set_xticklabels(["0.5", "1", "2", "4", "8", "16"]); ax.minorticks_off()
    style_axis(ax, ylabel="Continuity-Ready After\nFinal Move (s)", xlabel=r"$\rho = T_s / T_m$", ylim=(-1, 38), yticks=[0, 10, 20, 30])
    legend(ax, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, handlelength=1.8)
    save(fig, out / "eval" / "fig_mobility_policies")


def eval_late_binding_frames(out: Path):
    mq.strip([("Uninterrupted", "baseline", "reference"),
              ("No durable state", "xfer_meta", "never rejoins"),
              ("Late binding", "ph_zero_16", "Sink arrives at M+16")],
             [0, 2, 4, 8, 12, 16, 20, 24, 32], out / "eval" / "fig_late_binding_frames", "", arrival=16)
    print(f"  {(out / 'eval' / 'fig_late_binding_frames').relative_to(ROOT)}.{{pdf,png}}")


def appendix_heatmap(out: Path):
    raw = ROOT / "results/state_migration/gen/original_s0_k2/ablation_raw.csv"
    order = [("drop_inflight", "No in-flight rows", "Immediate"), ("drop_kv_recent", "No recent KV", "Ephemeral"),
             ("ph_localrefresh", "No Sink KV", "Durable"), ("drop_vae_all", "No VAE caches", "Ephemeral")]
    cv = post_curves(raw, [o[0] for o in order])
    ncol = 40
    M = np.full((len(order), ncol), np.nan)
    for i, (cfg, *_r) in enumerate(order):
        for k, v in zip(*cv[cfg]):
            if k < ncol:
                M[i, k] = min(v, YMAX)
    fig, hx = plt.subplots(figsize=(PANEL_FIG_SIZE[0] * 1.15, 3.0))
    im = hx.imshow(M, aspect="auto", cmap="Blues", vmin=10, vmax=YMAX, interpolation="nearest")
    hx.set_yticks(range(len(order))); hx.set_yticklabels([n for _, n, _ in order])
    for i, (_, _, role) in enumerate(order):
        text(hx, ncol + 0.6, i, role, ha="left", va="center", color=ROLE[role], clip_on=False)
    for i in range(1, len(order)):
        hx.axhline(i - 0.5, color="white", lw=2.0)
    hx.set_xticks([0, 10, 20, 30, 39])
    style_axis(hx, xlabel="Chunks After Migration")
    hx.tick_params(axis="y", length=0)
    cb = fig.colorbar(im, ax=hx, orientation="horizontal", fraction=0.08, pad=0.36, aspect=35)
    cb.set_label("PSNR to Uninterrupted (dB)", fontsize=LABEL_FONT_SIZE - 3, family=FONT_FAMILY)
    cb.ax.tick_params(labelsize=TICK_FONT_SIZE - 2, direction="in")
    save(fig, out / "appendix" / "fig_semantics_heatmap")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default=str(ROOT / "results/state_migration/figures/background"))
    a = ap.parse_args()
    configure_matplotlib()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    print("Background:")
    s2a = fig2a(out); s2b = fig2b(out); fig3(out); s4 = fig4(out); fig5(out)
    print("Evaluation / Appendix:")
    eval_mobility_policies(out); eval_late_binding_frames(out); appendix_heatmap(out)
    print("\nnumbers used in captions:")
    print(f"  Fig 2a: {s2a}")
    print(f"  Fig 2b: { {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in s2b.items()} }")
    print(f"  Fig 4 : {s4}")


if __name__ == "__main__":
    main()
