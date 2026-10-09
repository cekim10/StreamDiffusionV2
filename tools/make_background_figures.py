#!/usr/bin/env python3
"""Background figures (observation -> insight structure), one file per panel, from the raw experiment records.

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

Temporal-role colors are shared by every figure: Immediate red, Durable blue, Ephemeral gray.
Usage: python tools/make_background_figures.py [--out results/state_migration/figures/background]
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import ConnectionPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import make_motivation_figures as mm  # noqa: E402
import make_qualitative_figures as mq  # noqa: E402
from make_state_size_figure import GiB, MiB, load_bytes  # noqa: E402

RED, RED_LIGHT, BLUE = "#e34948", "#f2a5a4", "#2a78d6"
GRAY, GRAY_LIGHT = "#8c8b86", "#c9c8c3"            # fills (bars)
GRAY_LINE, GRAY_LINE_2 = "#6f6e69", "#a3a29c"      # lines (two ephemeral curves: solid / dashed)
BLUES = ["#7fb0ec", "#4a8fe0", "#2a6cc0", "#18467f"]  # ordinal: Sink arrival delay 1, 4, 8, 16
INK, INK_2, INK_3, GRID = "#1f1f1e", "#55544f", "#8a8984", "#e6e5e1"
TAU = 35.0          # rejoin criterion (justified in fig4b from the data)
YMAX = 50.0         # plotted range; the uninterrupted run itself is bit-identical (reported as 99 dB) and off scale
COL_W = 3.45        # one column of a two-column paper (in)

plt.rcParams.update({"font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "legend.fontsize": 7.2, "pdf.fonttype": 42, "ps.fonttype": 42,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": INK_3, "xtick.color": INK_2, "ytick.color": INK_2,
                     "axes.labelcolor": INK_2, "text.color": INK, "savefig.bbox": "tight", "savefig.pad_inches": 0.02})


def save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix(".pdf")); fig.savefig(path.with_suffix(".png"), dpi=250); plt.close(fig)
    print(f"  {path.relative_to(ROOT)}.{{pdf,png}}")


def post_curves(raw: Path, cfgs: list[str]):
    """Mean PSNR per chunk after migration (rel_call >= 0), unclipped."""
    by = {c: {} for c in cfgs}
    for r in csv.DictReader(open(raw)):
        if r["config"] in by and r["psnr"] and int(r["rel_call"]) >= 0:
            by[r["config"]].setdefault(int(r["rel_call"]), []).append(float(r["psnr"]))
    return {c: (sorted(d), [st.mean(d[k]) for k in sorted(d)]) for c, d in by.items()}


def reference_note(ax):
    """The reference run is bit-identical to itself (the harness reports 99 dB); no curve reaches the 50 dB axis top."""
    ax.text(1.0, 1.015, "↑ uninterrupted execution: bit-identical (off scale)", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.4, color=INK_3)


def style(ax):
    ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)


# ----------------------------------------------------------------------------- Fig. 2a
def fig2a(out: Path):
    comp, src = load_bytes()
    inflight, meta = comp["inflight"], comp["meta"]
    imm, sink, recent, vae = inflight + meta, comp["sink"], comp["recent"], comp["vae"]
    total = imm + sink + recent + vae
    pct = lambda b: 100.0 * b / total  # noqa: E731
    fig, ax = plt.subplots(figsize=(COL_W, 1.95))
    fig.subplots_adjust(top=0.52)
    h, left = 0.62, 0.0
    for name, b, c, tc in (("", imm, RED, INK), ("Sink KV", sink, BLUE, "white"), ("Recent KV", recent, GRAY, "white"), ("VAE caches", vae, GRAY_LIGHT, INK)):
        ax.barh(0, b / GiB, left=left / GiB, height=h, color=c, edgecolor="white", linewidth=1.3)
        if name:
            ax.text((left + b / 2) / GiB, 0, f"{name}\n{b / GiB:.2f} GiB", ha="center", va="center", fontsize=6.9, color=tc)
        left += b

    def bracket(x0, x1, label, color):
        y = 0.37
        ax.plot([x0, x0, x1, x1], [y, y + 0.07, y + 0.07, y], color=color, lw=0.9, clip_on=False)
        ax.text((x0 + x1) / 2, y + 0.1, label, ha="center", va="bottom", fontsize=6.8, color=color, clip_on=False)
    bracket((imm + 0.004 * GiB) / GiB, (imm + sink) / GiB - 0.012, f"Durable {pct(sink):.1f}%", BLUE)
    bracket((imm + sink) / GiB + 0.012, total / GiB - 0.004, f"Ephemeral {pct(recent + vae):.1f}%", INK_2)
    ax.set_xlim(0, total / GiB); ax.set_ylim(-0.42, 0.42); ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel(f"per-session execution state (GiB; total {total / GiB:.2f} GiB)")
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    # zoomed inset: Immediate state at MiB scale
    ix = ax.inset_axes([0.0, 1.62, 0.40, 0.42])
    ix.barh(0, inflight / MiB, height=0.6, color=RED, edgecolor="white", linewidth=1.0)
    ix.barh(0, meta / MiB, left=inflight / MiB, height=0.6, color=RED_LIGHT, edgecolor="white", linewidth=1.0)
    ix.set_xlim(0, imm / MiB); ix.set_ylim(-0.32, 0.32); ix.set_yticks([])
    ix.set_xticks([0, 1, 2]); ix.set_xticklabels(["0", "1", "2 MiB"]); ix.tick_params(axis="x", labelsize=6, length=2, pad=1)
    for sp in ("left", "top", "right"):
        ix.spines[sp].set_visible(False)
    ix.text(0, 0.36, f"in-flight rows {inflight / MiB:.2f} MiB", ha="left", va="bottom", fontsize=6.2, color=INK)
    ix.text((inflight + meta / 2) / MiB, 0, f"metadata {meta / MiB:.2f}", ha="center", va="center", fontsize=6.2, color=INK)
    ix.text(imm / MiB * 1.03, 0.02, f"Immediate {imm / MiB:.2f} MiB\n({pct(imm):.2f}%, zoomed)", ha="left", va="center", fontsize=6.6, color=RED, clip_on=False)
    for xa, xb in ((0, 0), (imm / GiB, imm / MiB)):
        ax.add_artist(ConnectionPatch(xyA=(xa, h / 2), coordsA=ax.transData, xyB=(xb, -0.3), coordsB=ix.transData, color=RED, lw=0.6, ls=(0, (2, 2)), zorder=0))
    save(fig, out / "fig2a_state_breakdown")
    return {"source_run": src, "immediate_MiB": imm / MiB, "inflight_MiB": inflight / MiB, "meta_MiB": meta / MiB, "sink_GiB": sink / GiB,
            "recent_GiB": recent / GiB, "vae_GiB": vae / GiB, "total_GiB": total / GiB, "pct": {"immediate": pct(imm), "durable": pct(sink), "ephemeral": pct(recent + vae)}}


# ----------------------------------------------------------------------------- Fig. 2b
ABL = [("drop_inflight", "No in-flight rows (0.19 MiB)", RED, "-", "Immediate"),
       ("drop_kv_recent", "No recent KV (1.61 GiB)", GRAY_LINE, "-", "Ephemeral"),
       ("drop_vae_all", "No VAE caches (2.80 GiB)", GRAY_LINE_2, "--", "Ephemeral"),
       ("ph_localrefresh", "No Sink KV (1.61 GiB)", BLUE, "-", "Durable")]


def fig2b(out: Path):
    raw = ROOT / "results/state_migration/gen/original_s0_k2/ablation_raw.csv"
    cv = post_curves(raw, [a[0] for a in ABL])
    fig, ax = plt.subplots(figsize=(COL_W, 2.35))
    ends = {}
    for cfg, label, col, ls, role in ABL:
        x, y = cv[cfg]
        ax.plot(x, y, color=col, lw=1.5, ls=ls, label=label)
        ends[cfg] = (x[-1], float(np.mean(y[-3:])))
    # direct role labels at the right edge (Ephemeral once for both gray curves)
    lab = {"Immediate": ends["drop_inflight"][1], "Durable": ends["ph_localrefresh"][1],
           "Ephemeral": (ends["drop_kv_recent"][1] + ends["drop_vae_all"][1]) / 2}
    for role, yv in lab.items():
        ax.text(40.0, yv, role, ha="left", va="center", fontsize=7, color={"Immediate": RED, "Durable": BLUE, "Ephemeral": GRAY_LINE}[role], clip_on=False)
    reference_note(ax)
    ax.set_xlim(0, 39); ax.set_ylim(8, YMAX)
    ax.set_xlabel("chunks after migration"); ax.set_ylabel("PSNR to uninterrupted\nexecution (dB)")
    style(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2, frameon=False, fontsize=6.6, handlelength=1.8, columnspacing=1.0)
    save(fig, out / "fig2b_state_ablation")
    return {cfg: {"psnr_min": min(cv[cfg][1]), "psnr_max": max(cv[cfg][1]), "psnr_last3_mean": ends[cfg][1]} for cfg, *_ in ABL}


# ----------------------------------------------------------------------------- Fig. 3
def fig3(out: Path):
    mq.strip([("Uninterrupted", "baseline", "reference"),
              ("No Sink KV", "ph_localrefresh", "plausible, but a\ndifferent trajectory"),
              ("Ephemeral +\nin-flight lost", "xfer_sink+meta", "recent KV, VAE, in-flight\ndropped together")],
             [0, 2, 8, 16, 32], out / "fig3_state_loss_frames", "")
    print(f"  {(out / 'fig3_state_loss_frames').relative_to(ROOT)}.{{pdf,png}}")


# ----------------------------------------------------------------------------- Fig. 4a / 4b
DELAYS = [(1, BLUES[0]), (4, BLUES[1]), (8, BLUES[2]), (16, BLUES[3])]


def fig4(out: Path):
    raw = ROOT / "results/state_migration/mechanism/ablation_raw.csv"
    cv = post_curves(raw, [f"ph_zero_{d}" for d, _ in DELAYS] + ["ph_zero_noswap"])
    never_max = max(cv["ph_zero_noswap"][1])
    # (a) absolute time
    fig, ax = plt.subplots(figsize=(COL_W, 2.35))
    for d, col in DELAYS:
        if d == 8:
            continue  # (a) stays readable; Δ = 8 is in (b)
        x, y = cv[f"ph_zero_{d}"]
        ax.plot(x, y, color=col, lw=1.5, label=f"Sink arrives after {d} chunk{'s' if d > 1 else ''}")
        ax.axvline(d, color=col, lw=0.7, ls=(0, (3, 2)))
    x, y = cv["ph_zero_noswap"]
    ax.plot(x, y, color=GRAY_LINE, lw=1.5, ls="--", label="Sink never arrives")
    reference_note(ax)
    ax.text(38.5, 31.5, "every run produces output from\nchunk 0; only continuity waits\nfor the Sink", ha="right", va="top", fontsize=6.4, color=INK_2)
    ax.set_xlim(0, 39); ax.set_ylim(8, YMAX)
    ax.set_xlabel("chunks after migration"); ax.set_ylabel("PSNR to uninterrupted\nexecution (dB)")
    style(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2, frameon=False, fontsize=6.6, handlelength=1.8, columnspacing=1.0)
    save(fig, out / "fig4a_late_binding")
    # (b) aligned at Sink arrival
    fig, bx = plt.subplots(figsize=(COL_W, 2.35))
    rejoin = {}
    for d, col in DELAYS:
        x, y = cv[f"ph_zero_{d}"]
        rel = [(k - d, v) for k, v in zip(x, y) if -6 <= k - d <= 22]
        pre = [(k, v) for k, v in rel if k <= 0]; post = [(k, v) for k, v in rel if k >= 0]
        bx.plot([k for k, _ in pre], [v for _, v in pre], color=col, lw=1.1, alpha=0.35)
        bx.plot([k for k, _ in post], [v for _, v in post], color=col, lw=1.5, label=f"Δ = {d}")
        rj = next((k for k, v in post if v >= TAU), None)
        rejoin[d] = rj
        if rj is not None:
            bx.plot([rj], [TAU], marker="|", ms=8, mew=1.4, color=col)
    bx.axhspan(8, never_max, color="#f3f2ef", zorder=0, lw=0)
    bx.text(21.6, 9.0, f"Sink never arrives: ≤ {never_max:.1f} dB in every chunk", ha="right", va="bottom", fontsize=6.4, color=INK_2)
    bx.axvline(0, color=INK_2, lw=0.8, ls="--")
    bx.axhline(TAU, color=INK_2, lw=0.7, ls=":")
    bx.text(-5.7, TAU + 0.6, f"rejoin criterion {TAU:.0f} dB", fontsize=6.4, va="bottom", color=INK_2)
    lo, hi = min(v for v in rejoin.values() if v is not None), max(v for v in rejoin.values() if v is not None)
    bx.text(21.6, 33.8, f"rejoins {lo}–{hi} chunks after\nbinding, largely\nindependent of Δ", ha="right", va="top", fontsize=6.5, color=INK)
    bx.text(-3.0, 9.0, "waiting\n(no Sink)", ha="center", va="bottom", fontsize=6.4, color=INK_2)
    bx.set_xlim(-6, 22); bx.set_ylim(8, YMAX); bx.set_xticks([-5, 0, 5, 10, 15, 20])
    bx.set_xlabel("chunks after the Sink arrives"); bx.set_ylabel("PSNR to uninterrupted\nexecution (dB)")
    style(bx)
    bx.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=4, frameon=False, title="Sink arrival delay Δ (chunks)", title_fontsize=6.4, fontsize=6.6,
              columnspacing=1.0, handlelength=1.4)
    save(fig, out / "fig4b_recovery_aligned")
    return {"never_arrives_max_psnr": never_max, "rejoin_chunks_after_arrival": rejoin}


# ----------------------------------------------------------------------------- Fig. 5
def fig5(out: Path):
    d = ROOT / "results/state_migration/mobility"
    fig = plt.figure(figsize=(7.0, 2.55))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.12, 1.0], hspace=0.62)
    axA = fig.add_subplot(gs[0]); axB = fig.add_subplot(gs[1], sharex=axA)
    t_end = 46.0
    mm.gantt(axA, *mm.restart_timeline(d / "mob_restart_tm24_h2.json"), t_end, r"$\rho<1$ ($T_m$ = 24 s, A$\to$B$\to$C): the Sink transfer completes before the next move", True)
    mm.gantt(axB, *mm.restart_timeline(d / "mob_restart_tm2_h3_iu.json"), t_end, r"$\rho>1$ ($T_m$ = 2 s, A$\to$B$\to$C$\to$D): execution moves again before the Sink arrives", False)
    axA.tick_params(labelbottom=False); axB.set_xlabel("time after the first handoff (s)")
    for ax in (axA, axB):
        ax.title.set_fontsize(7.8)
    save(fig, out / "fig5_mobility_timeline")


# ----------------------------------------------------------------------------- Evaluation / Appendix (moved out of Background)
def eval_mobility_policies(out: Path, t_s: float = 16.6):
    fig, ax1 = plt.subplots(figsize=(COL_W, 2.4))
    for pol, label, col, mk in [("restart", "Restart", mm.C["restart"], "s"), ("relay", "Relay", mm.C["relay"], "^"), ("direct", "Oracle direct", mm.C["direct"], "o")]:
        pts = [(tm, y, w) for tm, y, w in mm.mobility_points(pol) if y is not None]
        xs = [t_s / tm for tm, _, _ in pts]; ys = [y for _, y, _ in pts]
        ax1.plot(xs, ys, marker=mk, ms=4, lw=1.4, color=col, label=label, ls="--" if pol == "direct" else "-")
    ax1.axvline(1.0, color=INK_2, lw=0.8, ls="--"); ax1.axvspan(1.0, 20, color="#f3f2ef", zorder=0)
    ax1.set_xscale("log"); ax1.set_xlim(0.45, 20)
    ax1.set_xticks([0.5, 1, 2, 4, 8, 16]); ax1.set_xticklabels(["0.5", "1", "2", "4", "8", "16"])
    ax1.set_xlabel(r"$\rho = T_s / T_m$"); ax1.set_ylabel("continuity-ready latency\nafter the final move (s)")
    ax1.set_ylim(-1, 38); style(ax1)
    ax1.legend(loc="upper left", frameon=False)
    save(fig, out / "eval" / "fig_mobility_policies")


def eval_late_binding_frames(out: Path):
    mq.strip([("Uninterrupted", "baseline", "reference"),
              ("No durable state", "xfer_meta", "never rejoins"),
              ("Late binding", "ph_zero_16", "Sink arrives at M+16")],
             [0, 2, 4, 8, 12, 16, 20, 24, 32], out / "eval" / "fig_late_binding_frames", "", arrival=16)
    print(f"  {(out / 'eval' / 'fig_late_binding_frames').relative_to(ROOT)}.{{pdf,png}}")


def appendix_heatmap(out: Path):
    raw = ROOT / "results/state_migration/gen/original_s0_k2/ablation_raw.csv"
    order = [("drop_inflight", "in-flight rows", "Immediate"), ("drop_kv_recent", "recent KV", "Ephemeral"),
             ("ph_localrefresh", "Sink KV", "Durable"), ("drop_vae_all", "VAE caches", "Ephemeral")]
    cv = post_curves(raw, [o[0] for o in order])
    ncol = 40
    M = np.full((len(order), ncol), np.nan)
    for i, (cfg, *_r) in enumerate(order):
        for k, v in zip(*cv[cfg]):
            if k < ncol:
                M[i, k] = min(v, YMAX)
    fig, hx = plt.subplots(figsize=(COL_W, 1.9))
    im = hx.imshow(M, aspect="auto", cmap="Blues", vmin=10, vmax=YMAX, interpolation="nearest")
    hx.set_yticks(range(len(order))); hx.set_yticklabels([f"no {n}" for _, n, _ in order], fontsize=7)
    for i, (_, _, role) in enumerate(order):
        hx.text(ncol + 0.6, i, role, ha="left", va="center", fontsize=7, color={"Immediate": RED, "Durable": BLUE, "Ephemeral": GRAY_LINE}[role], clip_on=False)
    for i in range(1, len(order)):
        hx.axhline(i - 0.5, color="white", lw=1.5)
    hx.set_xlabel("chunks after migration"); hx.set_xticks([0, 10, 20, 30, 39]); hx.tick_params(axis="y", length=0)
    for sp in hx.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=hx, orientation="horizontal", fraction=0.08, pad=0.36, aspect=35)
    cb.set_label("PSNR to uninterrupted execution (dB)", fontsize=7); cb.ax.tick_params(labelsize=6.5)
    save(fig, out / "appendix" / "fig_semantics_heatmap")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default=str(ROOT / "results/state_migration/figures/background"))
    a = ap.parse_args()
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
