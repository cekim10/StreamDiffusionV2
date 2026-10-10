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
  fig5_mobility_timeline       when execution outruns the Sink transfer     <- mobility/mob_restart_*.json (emulated links)
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
    comp, src = load_bytes()
    inflight, meta = comp["inflight"], comp["meta"]
    imm, sink, recent, vae = inflight + meta, comp["sink"], comp["recent"], comp["vae"]
    total = imm + sink + recent + vae
    pct = lambda b: 100.0 * b / total  # noqa: E731
    fig, ax = plt.subplots(figsize=(PANEL_FIG_SIZE[0] * 1.25, 2.4))
    h, left = 0.56, 0.0
    white_box = dict(boxstyle="square,pad=0.15", fc="white", ec="none")
    segs = [("", imm, RED, None, BLACK), ("Sink KV", sink, BLUE, "x", BLACK), ("Recent KV", recent, DARKGRAY, None, BLACK), ("VAE caches", vae, "white", "//", BLACK)]
    for name, b, fc, hatch, tc in segs:
        ax.barh(0, b / GiB, left=left / GiB, height=h, color=fc, hatch=hatch, edgecolor=BLACK, linewidth=1.2, zorder=2)
        if name:
            text(ax, (left + b / 2) / GiB, 0, f"{name}\n{b / GiB:.2f} GiB", ha="center", va="center", color=tc, zorder=3,
                 bbox=white_box if hatch else None)
        left += b

    def bracket(x0, x1, label, color):
        y = 0.36
        ax.plot([x0, x0, x1, x1], [y, y + 0.07, y + 0.07, y], color=color, lw=1.2, clip_on=False)
        text(ax, (x0 + x1) / 2, y + 0.1, label, ha="center", va="bottom", color=color, clip_on=False)
    bracket((imm + 0.004 * GiB) / GiB, (imm + sink) / GiB - 0.015, f"Durable {pct(sink):.1f}%", BLUE)
    bracket((imm + sink) / GiB + 0.015, total / GiB - 0.004, f"Ephemeral {pct(recent + vae):.1f}%", DIMGRAY)
    ax.set_xlim(0, total / GiB); ax.set_ylim(-0.42, 0.42); ax.set_yticks([])
    ax.set_xticks([0, 1, 2, 3, 4, 5, 6])
    style_axis(ax, xlabel=f"Execution-State Size (GiB; total {total / GiB:.2f} GiB)")
    # zoomed inset: the Immediate state at MiB scale
    ix = ax.inset_axes([0.0, 1.6, 0.42, 0.42])
    ix.barh(0, inflight / MiB, height=0.6, color=RED, edgecolor=BLACK, linewidth=1.0)
    ix.barh(0, meta / MiB, left=inflight / MiB, height=0.6, color="white", hatch="..", edgecolor=RED, linewidth=0)
    ix.barh(0, meta / MiB, left=inflight / MiB, height=0.6, fill=False, edgecolor=BLACK, linewidth=1.0)
    ix.set_xlim(0, imm / MiB); ix.set_ylim(-0.32, 0.32); ix.set_yticks([])
    ix.set_xticks([0, 1, 2]); ix.set_xticklabels(["0", "1", "2 MiB"])
    for sp in ix.spines.values():
        sp.set_linewidth(SPINE_WIDTH)
    ix.tick_params(axis="x", direction="in", width=1, length=3, pad=3, labelsize=TICK_FONT_SIZE - 3)
    text(ix, 0, 0.37, f"In-flight rows {inflight / MiB:.2f} MiB", ANNOT_FONT_SIZE - 2, ha="left", va="bottom")
    text(ix, (inflight + meta / 2) / MiB, 0, f"Metadata {meta / MiB:.2f}", ANNOT_FONT_SIZE - 2, ha="center", va="center",
         bbox=dict(boxstyle="square,pad=0.12", fc="white", ec="none"))
    text(ix, imm / MiB * 1.04, 0.0, f"Immediate {imm / MiB:.2f} MiB\n({pct(imm):.2f}%, zoomed)", ha="left", va="center", color=RED, clip_on=False)
    # the Immediate sliver sits at x = 0 of the main bar: one vertical leader to the zoomed inset
    ax.add_artist(ConnectionPatch(xyA=(0, h / 2), coordsA=ax.transData, xyB=(0, -0.32), coordsB=ix.transData, color=RED, lw=1.2, ls=(0, (3, 2)), zorder=0))
    save(fig, out / "fig2a_state_breakdown")
    return {"source_run": src, "immediate_MiB": imm / MiB, "inflight_MiB": inflight / MiB, "meta_MiB": meta / MiB, "sink_GiB": sink / GiB,
            "recent_GiB": recent / GiB, "vae_GiB": vae / GiB, "total_GiB": total / GiB, "pct": {"immediate": pct(imm), "durable": pct(sink), "ephemeral": pct(recent + vae)}}


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
SITE = {"B": (BLUE, "x"), "C": (ORANGE, "--"), "D": (BLACK, None)}


def gantt(ax, run: Path, t_end: float, brackets: bool):
    exec_blocks, attempts, ready, moves = mm.restart_timeline(run)
    Y = {"exec": 2.6, "sink": 1.6, "cont": 0.6}
    box = dict(boxstyle="square,pad=0.12", fc="white", ec="none")
    ax.set_xlim(0, t_end); ax.set_ylim(0.15, 3.25)
    ax.set_yticks([Y["cont"], Y["sink"], Y["exec"]]); ax.set_yticklabels(["Continuity", "Sink transfer", "Execution"])

    def bar(y, a, b, site, label):
        fc, hatch = SITE[site]
        ax.barh(y, b - a, left=a, height=0.5, color=fc, hatch=hatch, edgecolor=BLACK, lw=1.0, zorder=2)
        if label and b - a > 1.5:
            text(ax, (a + b) / 2, y, label, ha="center", va="center", color="white" if hatch is None else BLACK, zorder=3, bbox=None if hatch is None else box)

    for e, a, b in exec_blocks:
        b = t_end if b is None else min(b, t_end)
        bar(Y["exec"], a, b, e, f"at {e}" if b - a > 4 else e)
    for _, _, t in moves:
        ax.axvline(t, color=BLACK, lw=0.9, ls=":", zorder=1)
    wasted = []
    for e, a, b, ok, mb in attempts:
        b = t_end if b is None else min(b, t_end)
        if ok:
            bar(Y["sink"], a, b, e, f"A→{e}  1.6 GB" if b - a > 4 else "")
            text(ax, b + 0.35, Y["sink"], "bind", ha="left", va="center", color=BLUE)
        else:
            ax.barh(Y["sink"], b - a, left=a, height=0.5, color="white", hatch="xxxx", edgecolor=RED, lw=1.0, zorder=2)
            wasted.append((b, mb))
    if wasted:
        xw = max(b for b, _ in wasted)
        text(ax, xw + 0.4, Y["sink"] - 0.42, " + ".join(f"{mb:.0f}" for _, mb in wasted) + " MiB discarded", ANNOT_FONT_SIZE - 1, ha="left", va="center", color=RED)
    for e, a, b in exec_blocks:
        b = t_end if b is None else min(b, t_end)
        rb = ready.get(e)
        segs = [(a, b, False)] if (rb is None or rb >= b) else [(a, max(a, rb), False), (max(a, rb), b, True)]
        for s0, s1, ok in segs:
            if s1 > s0:
                ax.barh(Y["cont"], s1 - s0, left=s0, height=0.34, color=BLUE if ok else "white", hatch=None if ok else "..",
                        edgecolor=BLUE if ok else RED, lw=1.0, zorder=2)
    if brackets:
        e, a, b, ok, _ = attempts[0]
        if ok:
            ax.annotate("", xy=(a, Y["sink"] - 0.4), xytext=(b, Y["sink"] - 0.4), arrowprops=dict(arrowstyle="<->", lw=1.0))
            text(ax, (a + b) / 2, Y["sink"] - 0.44, r"$T_s$ (Sink transfer)", ha="center", va="top", bbox=box)
        if moves:
            t1 = moves[0][2]
            ax.annotate("", xy=(0, Y["exec"] + 0.4), xytext=(t1, Y["exec"] + 0.4), arrowprops=dict(arrowstyle="<->", lw=1.0))
            text(ax, t1 / 2, Y["exec"] + 0.44, r"$T_m$ (mobility interval)", ha="center", va="bottom")


def fig5(out: Path):
    d = ROOT / "results/state_migration/mobility"
    fig = plt.figure(figsize=(WIDE_W, 5.8))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.15, 1.0], hspace=0.45)
    axA = fig.add_subplot(gs[0]); axB = fig.add_subplot(gs[1], sharex=axA)
    t_end = 46.0
    gantt(axA, d / "mob_restart_tm24_h2.json", t_end, True)
    gantt(axB, d / "mob_restart_tm2_h3_iu.json", t_end, False)
    text(axA, 0.0, 1.14, r"$\rho<1$ ($T_m$ = 24 s, A$\to$B$\to$C): the Sink transfer completes before the next move", LABEL_FONT_SIZE - 2,
         transform=axA.transAxes, va="bottom")
    text(axB, 0.0, 1.04, r"$\rho>1$ ($T_m$ = 2 s, A$\to$B$\to$C$\to$D): execution moves again before the Sink arrives", LABEL_FONT_SIZE - 2,
         transform=axB.transAxes, va="bottom")
    style_axis(axA); style_axis(axB, xlabel="Time After the First Handoff (s)")
    axA.tick_params(labelbottom=False)
    for ax in (axA, axB):
        ax.tick_params(axis="y", length=0)
    handles = [Patch(facecolor=BLUE, hatch="x", edgecolor=BLACK, label="at B"), Patch(facecolor=ORANGE, hatch="--", edgecolor=BLACK, label="at C"),
               Patch(facecolor=BLACK, edgecolor=BLACK, label="at D"), Patch(facecolor="white", hatch="xxxx", edgecolor=RED, label="Discarded transfer"),
               Patch(facecolor=BLUE, edgecolor=BLUE, label="Continuity restored"), Patch(facecolor="white", hatch="..", edgecolor=RED, label="Continuity missing")]
    legend(fig, handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=6, handlelength=1.6)
    save(fig, out / "fig5_mobility_timeline")


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
