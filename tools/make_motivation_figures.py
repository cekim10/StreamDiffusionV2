#!/usr/bin/env python3
"""Background & Motivation figures (all matplotlib) from the raw experiment records.

Fig. 1  Streaming diffusion is stateful (schematic with measured sizes)       <- Phase 0A inventory (k=2)
Fig. 2  State is temporally heterogeneous                                     <- gen/original_s0_k2/ablation_raw.csv
Fig. 3  Continuity can be late-bound                                          <- mechanism/ablation_raw.csv
Fig. 4  Mobility outruns continuity transfer                                  <- mobility/mob_{restart,relay,direct}_tm*.json
Fig. A1 Obs. 1 across videos / k                                              <- gen/*/ablation_raw.csv
Usage: python tools/make_motivation_figures.py [--out results/state_migration/figures]
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAP = 50.0  # PSNR above this is visually identical; bit-exact runs report 99
SEM = {"Immediate": "#d62728", "Durable": "#6a6a6a", "Ephemeral": "#1f77b4"}
C = {"inflight": SEM["Immediate"], "recent": "#1f77b4", "vae": "#2ca02c", "sink": SEM["Durable"],
     "d1": "#1f77b4", "d4": "#ff7f0e", "d8": "#2ca02c", "d16": "#9467bd",
     "restart": "#d62728", "relay": "#ff7f0e", "direct": "#2ca02c"}
plt.rcParams.update({"font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9, "legend.fontsize": 8, "figure.dpi": 160,
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})


def curves(raw: Path, cfgs: list[str], cap: float = CAP):
    by: dict[str, dict[int, list[float]]] = {c: {} for c in cfgs}
    with open(raw) as fh:
        for r in csv.DictReader(fh):
            if r["config"] in by and r["psnr"]:
                by[r["config"]].setdefault(int(r["rel_call"]), []).append(min(float(r["psnr"]), cap))
    return {c: (sorted(d), [st.mean(d[k]) for k in sorted(d)]) for c, d in by.items()}


def window(cv, cfg, lo, hi):
    x, y = cv[cfg]
    vals = [v for k, v in zip(x, y) if lo <= k <= hi]
    return st.mean(vals) if vals else float("nan")


def box(ax, x, y, w, h, text, fc, ec="#333333", fs=7.5, bold=False, tc="black", r=0.02):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=0.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, weight="bold" if bold else "normal", color=tc)


def arrow(ax, p0, p1, color="#333333", lw=1.0, ls="-", ms=8):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=ms, lw=lw, color=color, linestyle=ls, shrinkA=0, shrinkB=0))


# ----------------------------------------------------------------------------- Fig. 1 schematic
def fig1(out: Path):
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 40)
    # pipeline boxes
    box(ax, 1, 15, 11, 10, "camera\nframes", "#f7f7f7")
    box(ax, 17, 15, 14, 10, "streaming VAE\nencoder", "#eef6ee")
    box(ax, 36, 9, 30, 22, "", "#f3f3f3", ec="#999999")
    ax.text(51, 29, "causal video DiT (Stream-Batch)", ha="center", va="center", fontsize=8, weight="bold")
    box(ax, 71, 15, 14, 10, "streaming VAE\ndecoder", "#eef6ee")
    box(ax, 90, 15, 9, 10, "output\nframes", "#f7f7f7")
    for x0, x1 in [(12, 17), (31, 36), (66, 71), (85, 90)]:
        arrow(ax, (x0, 20), (x1, 20))
    # state inside the DiT: rolling KV ring (sink slots + recent slots), in-flight rows, metadata
    for i in range(6):
        fc = SEM["Durable"] if i < 3 else SEM["Ephemeral"]
        box(ax, 38 + i * 4.3, 17, 3.8, 5, "", fc, ec="white", fs=6, r=0.0)
    ax.text(44.3, 15.2, "sink slots (1.6 GB)", ha="center", va="top", fontsize=6.5, color=SEM["Durable"])
    ax.text(57.3, 15.2, "recent slots (1.6 GB)", ha="center", va="top", fontsize=6.5, color=SEM["Ephemeral"])
    ax.text(51, 24.2, "rolling KV cache (ring, 6 latent frames x 30 layers)", ha="center", va="bottom", fontsize=6.5)
    box(ax, 38, 10.5, 12, 3.2, "in-flight rows", SEM["Immediate"], ec="white", fs=6, tc="white", r=0.0)
    box(ax, 51.5, 10.5, 12.5, 3.2, "positions, EMA, ...", "#f0b0b0", ec="white", fs=6, r=0.0)
    # caches under the VAEs
    box(ax, 17, 9.5, 14, 3.6, "conv feature cache", SEM["Ephemeral"], ec="white", fs=6, tc="white", r=0.0)
    box(ax, 71, 9.5, 14, 3.6, "conv feature cache", SEM["Ephemeral"], ec="white", fs=6, tc="white", r=0.0)
    # size annotations
    ax.text(24, 8.2, "1.1 GB", ha="center", va="top", fontsize=6.5)
    ax.text(78, 8.2, "1.8 GB", ha="center", va="top", fontsize=6.5)
    ax.text(44, 7.4, "0.2 MB", ha="center", va="top", fontsize=6.5)
    ax.text(57.75, 7.4, "~2 MB", ha="center", va="top", fontsize=6.5)
    # per-session total + legend
    ax.text(50, 37.5, "per-session execution state: 6.2 GB (1.3B model, 480x832, 2 denoising steps), rewritten every 250 ms chunk",
            ha="center", va="center", fontsize=7.5)
    for i, (name, col) in enumerate([("immediate (must move now)", SEM["Immediate"]), ("durable (anchors continuity)", SEM["Durable"]),
                                     ("ephemeral (regenerates)", SEM["Ephemeral"])]):
        ax.add_patch(FancyBboxPatch((2 + i * 33, 1.2), 2.2, 2.2, boxstyle="square,pad=0", fc=col, ec="none"))
        ax.text(5 + i * 33, 2.3, name, va="center", fontsize=6.8)
    fig.tight_layout(pad=0.2)
    fig.savefig(out / "fig1_stateful_streaming.pdf"); fig.savefig(out / "fig1_stateful_streaming.png"); plt.close(fig)


# ----------------------------------------------------------------------------- Fig. 2
STATES = [("drop_inflight", "In-flight row", 0.2, "Immediate", C["inflight"]),
          ("drop_kv_recent", "Recent KV", 1645, "Ephemeral", C["recent"]),
          ("drop_vae_all", "VAE caches", 2871, "Ephemeral", C["vae"]),
          ("ph_localrefresh", "Sink KV", 1645, "Durable", C["sink"])]


def fig2(out: Path):
    raw = ROOT / "results/state_migration/gen/original_s0_k2/ablation_raw.csv"
    cv = curves(raw, [s_[0] for s_ in STATES])
    fig = plt.figure(figsize=(7.6, 2.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.3, 1.0], wspace=0.55)
    ax = fig.add_subplot(gs[0, 0]); hx = fig.add_subplot(gs[0, 1])
    for cfg, label, mb, sem, col in STATES:
        x, y = cv[cfg]
        size = f"{mb:.1f} MB" if mb < 1 else f"{mb / 1024:.1f} GB"
        ax.plot(x, y, color=col, lw=1.6, label=f"No {label if label.isupper() or label.startswith('VAE') else label[0].lower() + label[1:]} ({size})")
    ax.axhline(CAP, color="k", lw=0.6, ls=":")
    ax.text(39.5, CAP + 0.6, "identical to uninterrupted run", ha="right", va="bottom", fontsize=7)
    ax.set_xlabel("Chunks after migration"); ax.set_ylabel("PSNR to uninterrupted execution (dB)")
    ax.set_xlim(0, 39); ax.set_ylim(8, 54)
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("(a) Continuity after losing one component", loc="left")
    # (b) temporal-semantics heatmap: rows = lost component (sorted by size), columns = chunks, color = PSNR
    order = [("drop_inflight", "In-flight row", 0.2, "Immediate"), ("drop_kv_recent", "Recent KV", 1645, "Ephemeral"),
             ("ph_localrefresh", "Sink KV", 1645, "Durable"), ("drop_vae_all", "VAE caches", 2871, "Ephemeral")]
    ncol = 40
    import numpy as np

    M = np.full((len(order), ncol), np.nan)
    for i, (cfg, *_rest) in enumerate(order):
        x, y = cv[cfg]
        for k, v in zip(x, y):
            if k < ncol:
                M[i, k] = v
    im = hx.imshow(M, aspect="auto", cmap="RdYlGn", vmin=15, vmax=CAP, interpolation="nearest")
    hx.set_yticks(range(len(order)))
    hx.set_yticklabels([f"{name}\n{(f'{mb:.1f} MB' if mb < 1 else f'{mb / 1024:.1f} GB')}" for _, name, mb, _ in order], fontsize=7.5)
    for i, (_, _, _, sem) in enumerate(order):
        hx.text(ncol + 0.6, i, sem, ha="left", va="center", fontsize=7.5, color=SEM[sem], weight="bold", clip_on=False)
    for i in range(1, len(order)):
        hx.axhline(i - 0.5, color="white", lw=1.5)
    hx.set_xlabel("Chunks after migration"); hx.set_xticks([0, 10, 20, 30, 39])
    hx.set_title("(b) Temporal semantics of each state", loc="left")
    hx.tick_params(axis="y", length=0)
    for sp in hx.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=hx, orientation="horizontal", fraction=0.07, pad=0.28, aspect=35)
    cb.set_label("PSNR to uninterrupted execution (dB)", fontsize=7.5); cb.ax.tick_params(labelsize=7)
    cb.set_ticks([15, 25, 35, 45, 50]); cb.set_ticklabels(["15", "25", "35", "45", "≡"])
    fig.savefig(out / "fig2_state_semantics.pdf", bbox_inches="tight"); fig.savefig(out / "fig2_state_semantics.png", bbox_inches="tight"); plt.close(fig)


def fig2_appendix(out: Path):
    runs = [("original_s0_k2", "original, k=2"), ("original_s0_k4", "original, k=4"), ("bird_s0_k2", "bird, k=2"), ("boxing_s0_k2", "boxing, k=2")]
    fig, axes = plt.subplots(1, len(runs), figsize=(1.9 * len(runs), 2.3), sharey=True)
    for ax, (run, title) in zip(axes, runs):
        raw = ROOT / f"results/state_migration/gen/{run}/ablation_raw.csv"
        if not raw.exists():
            ax.set_visible(False); continue
        cv = curves(raw, [s[0] for s in STATES])
        for cfg, label, mb, sem, col in STATES:
            if cfg in cv and cv[cfg][0]:
                ax.plot(*cv[cfg], color=col, lw=1.3, label=f"no {label.lower()}")
        ax.set_title(title, fontsize=8); ax.set_xlim(0, 39); ax.set_ylim(8, 54)
        ax.set_xlabel("chunks after migration", fontsize=7.5)
    axes[0].set_ylabel("PSNR (dB)")
    axes[-1].legend(loc="lower right", frameon=False, fontsize=6.5)
    fig.tight_layout()
    fig.savefig(out / "figA1_semantics_generalization.pdf"); fig.savefig(out / "figA1_semantics_generalization.png"); plt.close(fig)


# ----------------------------------------------------------------------------- Fig. 3
def fig3(out: Path, tau: float = 35.0):
    raw = ROOT / "results/state_migration/mechanism/ablation_raw.csv"
    delays = [(1, "d1"), (4, "d4"), (8, "d8"), (16, "d16")]
    cv = curves(raw, [f"ph_zero_{d}" for d, _ in delays] + ["ph_zero_noswap", "repeat"])
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.2, 2.75), gridspec_kw={"width_ratios": [1.6, 1.0]})
    for d, key in delays:
        if d == 8:
            continue  # keep (a) readable; 8 appears in (b)
        x, y = cv[f"ph_zero_{d}"]
        ax.plot(x, y, color=C[key], lw=1.6, label=f"sink arrives after {d} chunk{'s' if d > 1 else ''}")
        ax.axvline(d, color=C[key], lw=0.8, ls="--", alpha=0.8)
    x, y = cv["ph_zero_noswap"]
    ax.plot(x, y, color=C["sink"], lw=1.6, label="sink never arrives")
    ax.axhline(CAP, color="k", lw=0.6, ls=":")
    ax.text(39.5, CAP + 0.6, "sink never lost: identical", ha="right", va="bottom", fontsize=7)
    ax.annotate("execution resumes\nwithout the sink", xy=(0.4, 28.3), xytext=(5.5, 10.0), fontsize=7, ha="left", arrowprops=dict(arrowstyle="->", lw=0.7))
    ax.set_xlabel("Chunks after migration"); ax.set_ylabel("PSNR to uninterrupted execution (dB)")
    ax.set_xlim(0, 39); ax.set_ylim(8, 54)
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("(a) Execution resumes first; continuity binds later", loc="left")
    # (b) rejoin time and settled continuity vs. arrival delay
    ds, rejoin, settled = [], [], []
    for d, key in delays:
        x, y = cv[f"ph_zero_{d}"]
        after = [(k, v) for k, v in zip(x, y) if k >= d]
        rj = next((k - d for k, v in after if v >= tau), None)
        ds.append(d); rejoin.append(rj if rj is not None else float("nan")); settled.append(st.mean([v for k, v in after if k >= d + 8]))
    bx.bar([str(d) for d in ds], rejoin, color=[C[k] for _, k in delays], width=0.6)
    for i, (r, s_) in enumerate(zip(rejoin, settled)):
        bx.text(i, r + 0.15, f"{s_:.0f} dB\nafter", ha="center", va="bottom", fontsize=6.5)
    bx.set_xlabel("Sink arrival delay (chunks)"); bx.set_ylabel(f"Chunks to rejoin (≥ {tau:.0f} dB)")
    bx.set_ylim(0, max(rejoin) + 3.5)
    bx.set_title("(b) Rejoin cost is flat in delay", loc="left")
    fig.tight_layout()
    fig.savefig(out / "fig3_late_binding.pdf"); fig.savefig(out / "fig3_late_binding.png"); plt.close(fig)


# ----------------------------------------------------------------------------- Fig. 4
def mobility_points(pol: str):
    d = ROOT / "results/state_migration/mobility"
    pts = []
    for tm in (1, 2, 4, 8, 16, 24, 32):
        f = d / f"mob_{pol}_tm{tm}.json"
        if not f.exists():
            f = d / f"mob_{pol}_tm{tm}_h2.json"
        if not f.exists():
            continue
        r = json.load(open(f))
        ready = r.get("t_ready_final", r.get("t_ready_C"))
        last_move = r["moves"][-1]["t"] if r.get("moves") else r.get("t_move")
        wasted = r.get("wasted_mb", 0.0)
        pts.append((tm, None if ready is None else ready - last_move, wasted))
    return pts


EDGE_COL = {"A": "#bbbbbb", "B": "#4c72b0", "C": "#dd8452", "D": "#55a868"}


def restart_timeline(path: Path):
    """Measured timeline of the naive 'restart' policy: execution location, sink transfer attempts, bind times."""
    r = json.load(open(path))
    edges = r.get("edges", ["B", "C"])
    moves = [(m["from"], m["to"], m["t"]) for m in r.get("moves", [])] if r.get("moves") else [("B", "C", r["t_move"])]
    ready = r.get("ready") or {k: v for k, v in {"B": r.get("t_ready_B"), "C": r.get("t_ready_C")}.items() if v is not None}
    bytes_ = r["bytes"]
    # execution blocks
    cuts = [0.0] + [t for _, _, t in moves]
    exec_blocks = [(edges[i], cuts[i], cuts[i + 1] if i + 1 < len(cuts) else None) for i in range(len(cuts))]
    # transfer attempts: one per destination edge, start = when execution arrived there (or 0 for B)
    attempts = []
    for i, e in enumerate(edges):
        start = cuts[i]
        nbytes = bytes_.get(f"A->{e}", bytes_.get("A" + e, 0)) / 2**20
        if e in ready:
            attempts.append((e, start, ready[e], True, nbytes))
        else:
            end = cuts[i + 1] if i + 1 < len(cuts) else None
            attempts.append((e, start, end, False, nbytes))
    return exec_blocks, attempts, ready, moves


def gantt(ax, exec_blocks, attempts, ready, moves, t_end, title, show_brackets):
    ax.set_xlim(0, t_end); ax.set_ylim(0.3, 3.3)
    ax.set_yticks([0.6, 1.6, 2.6]); ax.set_yticklabels(["continuity", "sink transfer", "execution"], fontsize=7.5)
    ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
    # execution row
    for e, a, b in exec_blocks:
        b = t_end if b is None else min(b, t_end)
        ax.barh(2.6, b - a, left=a, height=0.5, color=EDGE_COL[e], edgecolor="white", lw=0.5)
        if b - a > 4:
            ax.text((a + b) / 2, 2.6, f"at {e}", ha="center", va="center", fontsize=7, color="white", weight="bold")
        elif b - a > 1.2:
            ax.text((a + b) / 2, 2.6, e, ha="center", va="center", fontsize=6.5, color="white", weight="bold")
    for _, to, t in moves:
        ax.axvline(t, color="k", lw=0.6, ls=":")
    # sink transfer row
    wasted = []
    for e, a, b, ok, mb in attempts:
        b = t_end if b is None else min(b, t_end)
        if ok:
            ax.barh(1.6, b - a, left=a, height=0.5, color=EDGE_COL[e], alpha=0.85, edgecolor="white", lw=0.5)
            ax.text(b + 0.3, 1.6, "✓ bind", ha="left", va="center", fontsize=7, color="#2ca02c", weight="bold")
            if b - a > 4:
                ax.text((a + b) / 2, 1.6, f"A→{e}  1.6 GB", ha="center", va="center", fontsize=6.8, color="white", weight="bold")
        else:
            ax.barh(1.6, b - a, left=a, height=0.5, facecolor="white", edgecolor=C["restart"], hatch="////", lw=0.8)
            wasted.append((b, mb))
    if wasted:
        xw = max(b for b, _ in wasted)
        ax.text(xw + 0.4, 1.22, "✗ " + " + ".join(f"{mb:.0f}" for _, mb in wasted) + " MB wasted", ha="left", va="center", fontsize=6.5, color=C["restart"])
    # continuity row: bound sink available at the edge where execution is?
    segs = []
    for i, (e, a, b) in enumerate(exec_blocks):
        b = t_end if b is None else min(b, t_end)
        rb = ready.get(e)
        if rb is None or rb >= b:
            segs.append((a, b, False))
        else:
            segs.append((a, max(a, rb), False)); segs.append((max(a, rb), b, True))
    for a, b, ok in segs:
        if b > a:
            ax.barh(0.6, b - a, left=a, height=0.35, color="#2ca02c" if ok else "#d62728", alpha=0.75 if ok else 0.45)
    if show_brackets:
        # T_s bracket under the first completed transfer, T_m bracket above the execution row
        e, a, b, ok, _ = attempts[0]
        if ok:
            ax.annotate("", xy=(a, 1.22), xytext=(b, 1.22), arrowprops=dict(arrowstyle="<->", lw=0.8))
            ax.text((a + b) / 2, 1.17, r"$T_s$ (sink transfer)", ha="center", va="top", fontsize=7.5)
        if moves:
            t1 = moves[0][2]
            ax.annotate("", xy=(0, 3.0), xytext=(t1, 3.0), arrowprops=dict(arrowstyle="<->", lw=0.8))
            ax.text(t1 / 2, 3.04, r"$T_m$ (mobility interval)", ha="center", va="bottom", fontsize=7.5)
    ax.set_title(title, loc="left", fontsize=8.5, pad=14 if show_brackets else 4)


def fig4(out: Path, t_s: float = 16.6):
    fig = plt.figure(figsize=(7.6, 3.3))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.3, 1.0], height_ratios=[1.12, 1.0], hspace=0.55, wspace=0.6)
    axA = fig.add_subplot(gs[0, 0]); axB = fig.add_subplot(gs[1, 0], sharex=axA); ax1 = fig.add_subplot(gs[:, 1])
    d = ROOT / "results/state_migration/mobility"
    t_end = 46.0
    gantt(axA, *restart_timeline(d / "mob_restart_tm24_h2.json"), t_end,
          r"(a) Naive restart, measured.  $\rho<1$ ($T_m$ = 24 s): sink keeps up", True)
    gantt(axB, *restart_timeline(d / "mob_restart_tm2_h3_iu.json"), t_end,
          r"$\rho>1$ ($T_m$ = 2 s): execution outruns the sink", False)
    axA.tick_params(labelbottom=False); axB.set_xlabel("Time after the first handoff (s)")
    for ax in (axA, axB):
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    # (b) measured latency vs rho
    for pol, label, col, mk in [("restart", "Restart", C["restart"], "s"), ("relay", "Relay", C["relay"], "^"), ("direct", "Oracle direct", C["direct"], "o")]:
        pts = [(tm, y, w) for tm, y, w in mobility_points(pol) if y is not None]
        xs = [t_s / tm for tm, _, _ in pts]; ys = [y for _, y, _ in pts]
        ax1.plot(xs, ys, marker=mk, ms=4, lw=1.5, color=col, label=label)
        if pol == "restart":
            for (tm, y, w), x in zip(pts, xs):
                if w and tm in (1, 4, 16):
                    ax1.annotate(f"{w / 1024:.1f} GB\nwasted", (x, y), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=6, color=col)
    ax1.axvline(1.0, color="k", lw=0.8, ls="--"); ax1.axvspan(1.0, 20, color="#f0f0f0", zorder=0)
    ax1.text(3.0, 2.0, "execution outruns\ncontinuity state", fontsize=7, va="bottom", ha="left", color="#444444")
    ax1.set_xscale("log"); ax1.set_xlim(0.45, 20)
    ax1.set_xticks([0.5, 1, 2, 4, 8, 16]); ax1.set_xticklabels(["0.5", "1", "2", "4", "8", "16"])
    ax1.set_xlabel(r"$\rho = T_s / T_m$"); ax1.set_ylabel("Continuity-ready latency\nafter the final move (s)")
    ax1.set_ylim(-1, 38)
    ax1.legend(loc="upper left", frameon=False, bbox_to_anchor=(0.0, 1.02))
    ax1.set_title("(b) A→B→C at 1 Gbps", loc="left")
    fig.savefig(out / "fig4_mobility.pdf", bbox_inches="tight"); fig.savefig(out / "fig4_mobility.png", bbox_inches="tight"); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default=str(ROOT / "results/state_migration/figures"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fig1(out); fig2(out); fig2_appendix(out); fig3(out); fig4(out)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
