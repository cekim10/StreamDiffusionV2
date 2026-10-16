#!/usr/bin/env python3
"""Preliminary OSDI evaluation figures generated ONLY from committed measurements (no model or analytical values are
plotted as data). One file per panel under results/evaluation/paper_figures/{eval,design}/ plus a <name>.meta.json
sidecar naming the source data, the measurement configuration, the git commit and what is missing. Design diagrams
(design/) are schematics and are labelled as such; evaluation panels (eval/) are measured.

Style: shared with tools/make_background_figures.py (Times New Roman, closed frame, inward ticks, 28 pt labels on a
7.7 x 4.8 in canvas; wide panels use 15.4 x 4.8 in). Policy names and colors are fixed in POLICY below and used by
every panel. Error bars: min-max over repetitions (all runs here have 3 reps unless the meta file says otherwise;
deterministic network emulation gives rep spreads <= 0.1-0.5 s, which the meta files report).

    python tools/eval/plot_paper_figures.py            # all panels
    python tools/eval/plot_paper_figures.py --only F2  # one group
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import statistics as st
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import make_background_figures as bg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

EV = ROOT / "results/evaluation"
OUT = EV / "paper_figures"
WIDE = (15.4, 4.8)
WIDE_AXES = [0.095, 0.20, 0.89, 0.73]

# ---- one naming/color scheme for the whole paper
POLICY = {
    # single handoff (M1)
    "full": ("Full migration", bg.DIMGRAY, "s"),
    "cold": ("Cold restart", bg.DARKGRAY, "v"),
    "replay": ("Replay", bg.BLACK, "^"),
    "ours": ("OTTER (M1)", bg.BLUE, "o"),
    # restoration under mobility
    "restart": ("Restart", bg.RED, "o"),
    "relay": ("Relay", "#9e9e9e", "x"),
    "relay_pipe": ("Pipelined relay", "#5f5f5f", "+"),
    "split": ("Wavefront (M2)", "#2a9d8f", "D"),
    "reuse_fixed": ("Wavefront (M2)", "#2a9d8f", "D"),
    "direct": ("Oracle", bg.BLACK, "*"),
    "reuse_adaptive": ("Probe-rate adaptive", "#7a5195", "^"),
    "pp_star": ("PP-Star", "#f4a582", "o"),
    "fixed_line": ("Fixed line", "#7f7f7f", "s"),
    "fixed_tree": ("Fixed tree", "#bdbdbd", "^"),
    "fixed_butterfly": ("Fixed butterfly-like", bg.ORANGE, "D"),
    "reuse_aware": ("OTTER assign (no ingress term)", "#9db8f5", "s"),
    "reuse_aware_in": ("OTTER (M2+M3, at moves)", "#8fb3ff", "s"),
    "reuse_dyn": ("OTTER (M2+M3, event-driven)", bg.BLUE, "o"),
    # dissemination plans
    "star": ("Star", bg.RED, "o"), "line": ("Pipelined line", "#7f7f7f", "s"), "tree": ("Tree", "#bdbdbd", "^"),
    "multipath": ("Butterfly-like", bg.ORANGE, "D"), "aware": ("OTTER assignment", bg.BLUE, "o"),
    # pre-positioning
    "none": ("No placement", bg.DARKGRAY, "o"), "oracle": ("Oracle", bg.BLACK, "*"), "top1": ("Top-1", bg.BLUE, "s"),
    "proportional": ("Proportional", bg.ORANGE, "^"),
}
FULLE_POL = ["restart", "pp_star", "fixed_line", "fixed_tree", "fixed_butterfly", "reuse_aware_in", "reuse_dyn"]


def commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def meta(name, **kw):
    p = OUT / f"{name}.meta.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    kw.setdefault("plot_script", "tools/eval/plot_paper_figures.py")
    kw["plot_commit"] = commit()
    p.write_text(json.dumps(kw, indent=1))


def rcsv(path):
    return list(csv.DictReader(open(path)))


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def new(wide=False):
    fig = plt.figure(figsize=WIDE if wide else bg.FIG2A_SIZE)
    ax = fig.add_axes(WIDE_AXES if wide else bg.FIG2A_AXES)
    return fig, ax


def finish(ax, xlabel, ylabel, legend=None, legend_kw=None):
    bg._fig2a_axis(ax, xlabel)
    ax.set_ylabel(ylabel, fontsize=bg.F2_LABEL); ax.tick_params(axis="y", length=5)
    if legend is not False:
        ax.legend(frameon=False, prop={"size": bg.F2_ANNOT - 4, "family": bg.FONT_FAMILY}, **(legend_kw or {}))


def bars(ax, groups, series, values, err=None, width=0.8, log=False, labels_fmt=None):
    """groups on x; one bar per series inside each group; values[(g, s)] (None = not run)."""
    n = len(series); w = width / n
    x = np.arange(len(groups))
    for i, s in enumerate(series):
        lab, col, _ = POLICY[s]
        v = [values.get((g, s)) for g in groups]
        pos = x + (i - (n - 1) / 2) * w
        ok = [j for j, y in enumerate(v) if y is not None]
        yerr = None
        if err:
            lo = [v[j] - err[(groups[j], s)][0] for j in ok]; hi = [err[(groups[j], s)][1] - v[j] for j in ok]
            yerr = [lo, hi]
        ax.bar(pos[ok], [v[j] for j in ok], w, color=col, edgecolor="black", linewidth=0.6, label=lab, yerr=yerr,
               error_kw={"elinewidth": 1.0, "capsize": 2})
    ax.set_xticks(x); ax.set_xticklabels(groups, fontsize=bg.F2_ANNOT)
    if log:
        ax.set_yscale("log")


# ======================================================================================== F1 state decomposition
def f1():
    rows = rcsv(ROOT / "results/state_migration/prompt_sweep/summary.csv")
    rows = [r for r in rows if r.get("no_sink_mean16")]
    fig, ax = new()
    xs = np.arange(len(rows))
    clips = [r["clip"] for r in rows]
    sink = [fnum(r["no_sink_mean16"]) for r in rows]; eph = [fnum(r["no_eph_last16"]) for r in rows]
    refreshed = [r["refresh_before_M"] not in ("", "[]") for r in rows]
    ax.scatter(xs, sink, marker="o", s=60, facecolor=bg.RED, edgecolor="black", label="Sink KV lost (mean, 16 chunks after M)", zorder=3)
    ax.scatter([x for x, f in zip(xs, refreshed) if not f], [e for e, f in zip(eph, refreshed) if not f], marker="s", s=60,
               facecolor=bg.BLUE, edgecolor="black", label="Ephemeral lost (last 16), no refresh before M", zorder=3)
    ax.scatter([x for x, f in zip(xs, refreshed) if f], [e for e, f in zip(eph, refreshed) if f], marker="s", s=60,
               facecolor="white", edgecolor=bg.BLUE, linewidth=1.6, label="Ephemeral lost (last 16), refresh before M", zorder=3)
    ax.axhline(35, color="black", ls="--", lw=1.2)
    ax.text(len(rows) - 0.5, 35.6, "35 dB", ha="right", va="bottom", fontsize=bg.F2_ANNOT - 4, family=bg.FONT_FAMILY)
    ax.set_xticks([]); ax.set_ylim(10, 66)
    finish(ax, f"Runs ({len(rows)}: clips x seeds x prompts)", "PSNR to ref. (dB)", legend_kw={"loc": "upper left", "ncol": 1})
    bg.save(fig, OUT / "eval/F1c_loss_by_component_sweep", tight=False)
    meta("eval/F1c_loss_by_component_sweep", rq="RQ1", source="results/state_migration/prompt_sweep/summary.csv",
         config="single GPU, bit-exact same-seed reference; one component withheld at migration chunk M; k=2; 31 runs over clips/seeds/prompts",
         measured=True, notes="Panels F1a/F1b are the existing Fig. 2a/2b/3 (tools/make_background_figures.py); this panel adds the sweep.",
         missing="GPU-time cost of reconstructing ephemeral state is not plotted (it is the rejoin time in F3).")


# ======================================================================================== F2 TTFO vs bandwidth
BW_ORDER = ["250", "500", "1000", "2500", "5000", "native"]


def single_handoff_table():
    T = {}
    for r in rcsv(EV / "single_handoff/summary_by_policy_bw.csv"):
        bw = r["bw_mbps"]; bw = "native" if bw in ("", "0", "0.0", "nan") or fnum(bw) is None or fnum(bw) <= 0 else str(int(float(bw)))
        T[(r["policy"], bw)] = r
    return T


def f2():
    T = single_handoff_table()
    fig, ax = new()
    x = np.arange(len(BW_ORDER))
    for p in ("full", "replay", "cold", "ours"):
        lab, col, mk = POLICY[p]
        ys, lo, hi, xs = [], [], [], []
        for i, bw in enumerate(BW_ORDER):
            r = T.get((p, bw))
            if r and fnum(r["first_output_latency_s_median"]) is not None:
                xs.append(i); ys.append(fnum(r["first_output_latency_s_median"]))
                lo.append(ys[-1] - fnum(r["first_output_latency_s_p25"])); hi.append(fnum(r["first_output_latency_s_p75"]) - ys[-1])
        ax.errorbar(xs, ys, yerr=[lo, hi], color=col, marker=mk, ms=9, lw=2.2, capsize=3, markerfacecolor="white" if p != "ours" else col,
                    markeredgewidth=1.8, label=lab)
    ax.set_yscale("log"); ax.set_xticks(x); ax.set_xticklabels(["0.25", "0.5", "1", "2.5", "5", "9.4*"])
    finish(ax, "Link bandwidth (Gbps)", "First output (s)", legend_kw={"loc": "upper right", "ncol": 2})
    bg.save(fig, OUT / "eval/F2a_first_output_vs_bw", tight=False)
    meta("eval/F2a_first_output_vs_bw", rq="RQ2", source="results/evaluation/single_handoff/summary_by_policy_bw.csv (+ summary_runs.csv)",
         config="elves-01 -> elves-02, L40S, dog clip seed 0 k=2, migration at chunk 30, MSS 1400, token-bucket shaping; 3 reps per point; *native = unshaped 9.4 Gbps",
         measured=True, error_bars="p25-p75 over 3 reps",
         metric="first output = first generated chunk at the destination after the migration trigger (NOT Sink bind, NOT visual rejoin)",
         missing="external baselines (GCR/PhoenixOS/cuda-checkpoint) not run")
    # F2b: OTTER's three distinct events vs bandwidth
    fig, ax = new()
    series = [("first_output_latency_s", "OTTER first output", bg.BLUE, "o"), ("sink_ready_rel_s", "Sink verified at destination", "#2a9d8f", "D"),
              ("continuity_ready_rel_s", "Sink bound (first output on it)", bg.ORANGE, "s")]
    for key, lab, col, mk in series:
        xs, ys, lo, hi = [], [], [], []
        for i, bw in enumerate(BW_ORDER):
            r = T.get(("ours", bw))
            if r and fnum(r[key + "_median"]) is not None:
                xs.append(i); ys.append(fnum(r[key + "_median"])); lo.append(ys[-1] - fnum(r[key + "_p25"])); hi.append(fnum(r[key + "_p75"]) - ys[-1])
        ax.errorbar(xs, ys, yerr=[lo, hi], color=col, marker=mk, ms=9, lw=2.2, capsize=3, markeredgewidth=1.8, label=lab)
    xs = [i for i, bw in enumerate(BW_ORDER) if T.get(("full", bw))]
    ax.plot(xs, [fnum(T[("full", BW_ORDER[i])]["first_output_latency_s_median"]) for i in xs], color=bg.DIMGRAY, ls="--", marker="s", ms=8,
            markerfacecolor="white", lw=1.8, label="Full migration first output")
    ax.set_yscale("log"); ax.set_xticks(np.arange(len(BW_ORDER))); ax.set_xticklabels(["0.25", "0.5", "1", "2.5", "5", "9.4*"])
    finish(ax, "Link bandwidth (Gbps)", "Time after trigger (s)", legend_kw={"loc": "upper right", "ncol": 1})
    bg.save(fig, OUT / "eval/F2b_otter_events_vs_bw", tight=False)
    meta("eval/F2b_otter_events_vs_bw", rq="RQ2", source="results/evaluation/single_handoff/summary_by_policy_bw.csv", measured=True,
         config="as F2a", error_bars="p25-p75 over 3 reps",
         metric="three distinct events: first output (execution resumed), Sink verified (all fragments checksummed), Sink bound (first output on the transferred Sink); visual rejoin is F3",
         missing="per-bandwidth rejoin time in seconds (only 'calls after bind' = 6 at every bandwidth is in the table)")


# ======================================================================================== F3 continuity timeline
def f3():
    rows = rcsv(EV / "continuity/fig7_data.csv")
    fig, ax = new(wide=True)
    ev = defaultdict(dict)
    for r in rows:
        if r["kind"] == "event":
            ev[r["policy"]][r["event"]] = fnum(r["t_rel_s"])
    for p in ("full", "replay", "cold", "ours"):
        pts = sorted((fnum(r["t_rel_s"]), fnum(r["psnr_db"])) for r in rows if r["kind"] == "chunk" and r["policy"] == p and fnum(r["psnr_db"]) is not None)
        lab, col, mk = POLICY[p]
        ax.plot([t for t, _ in pts], [min(v, 52) for _, v in pts], color=col, lw=2.0, marker=mk, ms=4, markevery=3, label=lab)
    o = ev["ours"]
    ch = sorted((fnum(r["t_rel_s"]), fnum(r["psnr_db"])) for r in rows if r["kind"] == "chunk" and r["policy"] == "ours")
    rejoin = next((t for t, v in ch if t > o.get("sink_bind", 1e9) and v is not None and v >= 35), None)
    marks = [("first_output", "first output"), ("sink_ready", "Sink verified"), ("sink_bind", "Sink bound")]
    for k, lab in marks:
        if o.get(k) is not None:
            ax.axvline(o[k], color=bg.BLUE, ls=":", lw=1.4)
            ax.text(o[k] + 0.3, 13, lab, rotation=90, fontsize=bg.F2_ANNOT - 5, family=bg.FONT_FAMILY, va="bottom", color=bg.BLUE)
    if rejoin:
        ax.axvline(rejoin, color=bg.BLUE, ls="-", lw=1.4)
        ax.text(rejoin + 0.3, 13, ">= 35 dB rejoin", rotation=90, fontsize=bg.F2_ANNOT - 5, family=bg.FONT_FAMILY, va="bottom", color=bg.BLUE)
    ax.axhline(35, color="black", ls="--", lw=1.0)
    ax.set_xlim(-1, 60); ax.set_ylim(10, 54)
    finish(ax, "Time after migration trigger (s)", "PSNR to ref. (dB)", legend_kw={"loc": "lower right", "ncol": 4})
    bg.save(fig, OUT / "eval/F3a_continuity_timeline_1gbps", tight=False)
    meta("eval/F3a_continuity_timeline_1gbps", rq="RQ2/RQ7", source="results/evaluation/continuity/fig7_data.csv (one rep per policy, 1 Gbps)", measured=True,
         config="elves-01 -> elves-02, 1 Gbps, dog seed 0 k=2; PSNR of each generated chunk vs the uninterrupted same-seed run (99 dB = bit-exact, clipped at 52)",
         events={k: o.get(k) for k, _ in marks} | {"rejoin_35dB": rejoin}, error_bars="none (single representative rep; per-bandwidth medians in F2b)",
         missing="no multi-rep band; full migration is bit-exact after 53.8 s (clipped)")


# ======================================================================================== F4 repeated mobility
def f4():
    rows = rcsv(EV / "repeated_mobility/figures/mobility_table.csv")
    pols = ["restart", "relay", "relay_pipe", "split", "direct"]
    fig, ax = new()
    for p in pols:
        rr = sorted((fnum(r["rho"]), fnum(r["cont_ready_after_final_median"]), fnum(r["cont_ready_min"]), fnum(r["cont_ready_max"])) for r in rows if r["policy"] == p)
        lab, col, mk = POLICY[p]
        x = [a for a, *_ in rr]; y = [b for _, b, _, _ in rr]
        ax.errorbar(x, y, yerr=[[b - c for _, b, c, _ in rr], [d - b for _, b, _, d in rr]], color=col, marker=mk, ms=9, lw=2.2, capsize=3,
                    markerfacecolor="white" if p not in ("split", "direct") else col, markeredgewidth=1.8, label=lab)
    ax.set_xscale("log", base=2); ax.set_xticks([0.5, 1, 2, 4, 8]); ax.set_xticklabels(["0.5", "1", "2", "4", "8"]); ax.minorticks_off()
    finish(ax, r"Mobility rate $\rho = T_s / T_m$", "Sink bound after\nfinal move (s)", legend_kw={"loc": "upper left", "ncol": 2})
    bg.save(fig, OUT / "eval/F4a_gpu_repeated_mobility_latency", tight=False)
    meta("eval/F4a_gpu_repeated_mobility_latency", rq="RQ3", source="results/evaluation/repeated_mobility/figures/mobility_table.csv", measured=True,
         config="GPU, physical: A->B->C->D on elves-01..04, 1 Gbps per-node caps, T_s 14.05 s, 3 reps per (policy, rho)",
         metric="continuity-ready = first output on the bound Sink after the final move", error_bars="min-max over 3 reps",
         reading="all non-oracle policies are ingress-bound (~15 s) at a single destination; progress preservation shows in bytes (F4b)")
    fig, ax = new()
    for p, key, ls in (("restart", "source_over_sink", "-"), ("relay_pipe", "source_over_sink", "-"), ("split", "source_over_sink", "-"),
                       ("restart", "unused_over_sink", "--"), ("split", "unused_over_sink", "--")):
        rr = sorted((fnum(r["rho"]), fnum(r[key])) for r in rows if r["policy"] == p)
        lab, col, mk = POLICY[p]
        ax.plot([a for a, _ in rr], [b for _, b in rr], color=col, ls=ls, marker=mk, ms=9, lw=2.2, markerfacecolor="white" if ls == "--" else col,
                markeredgewidth=1.8, label=f"{lab}, {'source' if key.startswith('source') else 'discarded'}")
    ax.set_xscale("log", base=2); ax.set_xticks([0.5, 1, 2, 4, 8]); ax.set_xticklabels(["0.5", "1", "2", "4", "8"]); ax.minorticks_off()
    finish(ax, r"Mobility rate $\rho$", "Sinks per session", legend_kw={"loc": "upper right", "ncol": 1})
    bg.save(fig, OUT / "eval/F4b_gpu_repeated_mobility_bytes", tight=False)
    meta("eval/F4b_gpu_repeated_mobility_bytes", rq="RQ3", source="results/evaluation/repeated_mobility/figures/mobility_table.csv", measured=True,
         config="as F4a", metric="source = bytes sent by the original source / Sink size; discarded ('unused', plan definition a) = delivered to an owner that neither bound nor forwarded it")
    # F4c: continuous mobility under a shared source (network level)
    rows = rcsv(EV / "restore_contention_v2/summary_by_config.csv")
    fig, ax = new()
    for p in ("restart", "reuse_fixed", "reuse_adaptive"):
        rr = sorted((int(r["N"]), fnum(r["source_per_session"]), int(r["restored_min"])) for r in rows if r["policy"] == p and r["moves"] == "0")
        lab, col, mk = POLICY[p]
        ax.plot([a for a, *_ in rr], [b for _, b, _ in rr], color=col, marker=mk, ms=9, lw=2.2, markerfacecolor=col, markeredgewidth=1.8, label=lab)
        for n, b, k in rr:
            ax.text(n, b + 0.08, f"{k}/{n}", ha="center", fontsize=bg.F2_ANNOT - 6, family=bg.FONT_FAMILY, color=col)
    ax.set_xscale("log", base=2); ax.set_xticks([1, 2, 4, 8]); ax.set_xticklabels(["1", "2", "4", "8"]); ax.minorticks_off(); ax.set_ylim(0.8, 3.4)
    finish(ax, "Concurrent sessions sharing the source", "Source Sinks / session", legend_kw={"loc": "upper right"})
    bg.save(fig, OUT / "eval/F4c_continuous_mobility_shared_source", tight=False)
    meta("eval/F4c_continuous_mobility_shared_source", rq="RQ3", source="results/evaluation/restore_contention_v2/summary_by_config.csv (moves=0)", measured=True,
         level="network-level harness (no GPU), 4 physical hosts", config="N sessions over B->C->D->B..., rho 2, 1 Gbps caps, run length 2 N T_s + 2 T_m, 3 reps",
         annotation="k/N = sessions restored in every rep (restart restored 0 in all runs: within the run length, not an infinite-time claim)")
    # F4d: revisit (Full E condition 4)
    rows = {(r["cond"], r["policy"]): r for r in rcsv(EV / "restore_fulle/summary_by_config.csv")}
    fig, ax = new()
    c = "4 revisit"
    vals = {("T_r at B (s)", p): fnum(rows[(c, p)]["t_r"]) for p in FULLE_POL if (c, p) in rows}
    srcs = {p: fnum(rows[(c, p)]["source"]) for p in FULLE_POL if (c, p) in rows}
    x = np.arange(len(FULLE_POL))
    for i, p in enumerate(FULLE_POL):
        lab, col, _ = POLICY[p]
        ax.bar(i, vals[("T_r at B (s)", p)], 0.7, color=col, edgecolor="black", linewidth=0.6, label=lab,
               yerr=[[vals[("T_r at B (s)", p)] - fnum(rows[(c, p)]["t_r_min"])], [fnum(rows[(c, p)]["t_r_max"]) - vals[("T_r at B (s)", p)]]], capsize=2)
        ax.text(i, vals[("T_r at B (s)", p)] + 0.4, f"{srcs[p]:.2f}", ha="center", fontsize=bg.F2_ANNOT - 6, family=bg.FONT_FAMILY)
    ax.set_xticks([]); ax.set_ylim(0, 25)
    finish(ax, "Policy (bar label: source Sinks)", "Restore at revisited B (s)", legend=False)
    ax.xaxis.labelpad = 14
    ax.legend(frameon=False, prop={"size": bg.F2_ANNOT - 6, "family": bg.FONT_FAMILY}, loc="upper right", ncol=2)
    bg.save(fig, OUT / "eval/F4d_revisit_restore", tight=False)
    meta("eval/F4d_revisit_restore", rq="RQ3", source="results/evaluation/restore_fulle/summary_by_config.csv (cond '4 revisit')", measured=True, level="network-level, 4 physical hosts",
         config="single session B->C->D->B, rho 2, 1 Gbps, 3 reps; 0.50 Sink still verified at B on return for every policy except restart", error_bars="min-max over 3 reps")


# ======================================================================================== F5 fixed topologies
def f5():
    rows = rcsv(EV / "restore_dissem_hetero/summary_by_config.csv") + rcsv(EV / "restore_dissem_pilot/summary_by_config.csv")
    order = ["Bs=1000/Bf=1000/Bin=1000", "Bs=1000/Bf=500/Bin=1000", "Bs=1000/Bf=125/Bin=1000", "Bs=250/Bf=1000/Bin=1000"]
    names = ["Uniform 1G", "Fwd 500M", "Fwd 125M", "Source 250M"]
    V = {(names[order.index(r["cond"])], r["plan"]): fnum(r["makespan_median"]) for r in rows if r["cond"] in order}
    E = {(names[order.index(r["cond"])], r["plan"]): (fnum(r["makespan_min"]), fnum(r["makespan_max"])) for r in rows if r["cond"] in order}
    fig, ax = new(wide=True)
    bars(ax, names, ["star", "line", "tree", "multipath", "aware"], V, err=E, log=True)
    ax.set_ylim(8, 600)
    from matplotlib.ticker import FixedLocator, NullLocator, ScalarFormatter
    ax.yaxis.set_major_locator(FixedLocator([10, 20, 50, 100, 200, 500])); ax.yaxis.set_minor_locator(NullLocator()); ax.yaxis.set_major_formatter(ScalarFormatter())
    finish(ax, "Network condition (dissemination of one Sink to three nodes)", "Makespan (s)", legend_kw={"loc": "upper left", "ncol": 5})
    bg.save(fig, OUT / "eval/F5a_dissemination_topologies", tight=False)
    meta("eval/F5a_dissemination_topologies", rq="RQ4", source="results/evaluation/restore_dissem_hetero/summary_by_config.csv + restore_dissem_pilot (uniform, 1 rep)",
         measured=True, level="network-level, 4 physical hosts", config="one Sink at A to B, C, D; forwarders pipeline per fragment; 3 reps (uniform: 1 rep)",
         error_bars="min-max", note="OTTER assignment = fragment-level provider assignment computed once from caps, own queue and holdings; it is not a choice among the four families")
    R = {(r["cond"], r["policy"]): r for r in rcsv(EV / "restore_fulle/summary_by_config.csv")}
    conds = ["1 slow-B", "2 shared source", "3 C degradation", "4 revisit"]
    cn = ["Slow holder B", "Shared source\n(N = 4)", "C degrades\nmid-restore", "Revisit B"]
    V = {(cn[conds.index(c)], p): fnum(R[(c, p)]["t_r"]) for c in conds for p in FULLE_POL if (c, p) in R}
    E = {(cn[conds.index(c)], p): (fnum(R[(c, p)]["t_r_min"]), fnum(R[(c, p)]["t_r_max"])) for c in conds for p in FULLE_POL if (c, p) in R}
    fig, ax = new(wide=True)
    bars(ax, cn, FULLE_POL, V, err=E)
    ax.set_ylim(0, 100)
    finish(ax, "Condition (execution mobility, network-level)", "Restore at final owner (s)", legend_kw={"loc": "upper left", "ncol": 4})
    bg.save(fig, OUT / "eval/F5b_mobility_policies_latency", tight=False)
    S = {(cn[conds.index(c)], p): fnum(R[(c, p)]["source"]) for c in conds for p in FULLE_POL if (c, p) in R}
    fig, ax = new(wide=True)
    bars(ax, cn, FULLE_POL, S)
    ax.set_ylim(0, 4.3)
    finish(ax, "Condition (execution mobility, network-level)", "Source Sinks / session", legend_kw={"loc": "upper left", "ncol": 4})
    bg.save(fig, OUT / "eval/F5c_mobility_policies_source_bytes", tight=False)
    for nm in ("eval/F5b_mobility_policies_latency", "eval/F5c_mobility_policies_source_bytes"):
        meta(nm, rq="RQ4/RQ5", source="results/evaluation/restore_fulle/summary_by_config.csv", measured=True, level="network-level, 4 physical hosts, 84 runs",
             config="slow-B: B egress 125 Mbps; shared source: N=4; C degradation: C egress 1G->62.5M when D holds 50 %; revisit B->C->D->B; rho 2; 3 reps",
             frozen_verdicts={"H8a": "NOT SUPPORTED", "H8b": "SUPPORTED", "H8c": "NOT SUPPORTED AS WRITTEN"}, error_bars="min-max over 3 reps (latency panel)",
             metric="T_r = final move -> all fragments verified at the final owner (network fragment completion, NOT GPU Sink binding)")


# ======================================================================================== F6 dynamic morphing
def f6():
    runs = sorted(EV.glob("restore_fulle/policy=*_N=1_moves=2_rho=2_ev=*_rep=1_*"))
    pick = {p: next((d for d in runs if d.name.startswith(f"policy={p}_")), None) for p in ("reuse_aware_in", "reuse_dyn")}
    fig, axes = plt.subplots(1, 2, figsize=WIDE, sharey=True)
    fig.subplots_adjust(left=0.08, right=0.99, bottom=0.2, top=0.88, wspace=0.06)
    rows_y = {"A": 0, "B": 1, "C": 2}
    for ax, (p, d) in zip(axes, pick.items()):
        fl = [r for r in rcsv(d / "flows.csv") if r["dst"] == "D"]
        evs = list(csv.DictReader(open(d / "events.csv")))
        cap = next((fnum(e["t_rel"]) for e in evs if e["event"] == "cap_change"), None)
        rp = [fnum(e["t_rel"]) for e in evs if e["event"] == "replan"]
        rest = next((fnum(e["t_rel"]) for e in evs if e["event"] == "restored" and '"D"' in e["detail"]), None)
        mv = [fnum(e["t_rel"]) for e in evs if e["event"] == "move"]
        for r in fl:
            t0, t1 = fnum(r["t_start_rel"]), fnum(r["t_end_rel"]) or rest
            y = rows_y[r["src"]]
            col = {"A": bg.RED, "B": "#2a9d8f", "C": bg.ORANGE}[r["src"]]
            ax.barh(y, t1 - t0, left=t0, height=0.5, color=col, edgecolor="black", linewidth=0.6, alpha=0.9 if r["cancelled"] != "True" else 0.55)
            ax.text(t0 + (t1 - t0) / 2, y, f"{int(r['bytes']) / 2**20:.0f}", ha="center", va="center", fontsize=13, family=bg.FONT_FAMILY)
        for t in mv:
            ax.axvline(t, color="black", ls="-", lw=1.0)
        if cap:
            ax.axvline(cap, color=bg.RED, ls="--", lw=1.6); ax.text(cap + 0.3, 2.45, "C egress\n1G -> 62.5M", fontsize=11, family=bg.FONT_FAMILY, color=bg.RED, va="top")
        for t in rp:
            ax.axvline(t, color=bg.BLUE, ls=":", lw=1.8)
        if rest:
            ax.axvline(rest, color="black", ls="-.", lw=1.4); ax.text(rest + 0.3, -0.45, f"restored {rest - mv[-1]:.1f} s\nafter final move", fontsize=11, family=bg.FONT_FAMILY)
        ax.set_yticks([0, 1, 2]); ax.set_yticklabels(["A (source)", "B", "C"], fontsize=bg.F2_ANNOT)
        ax.set_xlim(13, 72); ax.set_title(POLICY[p][0] + (f", {len(rp)} re-plans (dotted)" if rp else ""), fontsize=bg.F2_ANNOT, family=bg.FONT_FAMILY)
        ax.set_xlabel("Time (s); flows into the final owner D (labels: MiB sent)", fontsize=bg.F2_ANNOT); ax.tick_params(labelsize=bg.F2_ANNOT - 2, direction="in")
    bg.save(fig, OUT / "eval/F6a_morphing_flow_timeline", tight=False)
    meta("eval/F6a_morphing_flow_timeline", rq="RQ5", source={p: str(d.relative_to(ROOT)) for p, d in pick.items()}, measured=True,
         level="network-level, 4 physical hosts (Full E condition 3, rep 1)",
         config="single session B->C->D, rho 2, 1 Gbps; C egress drops to 62.5 Mbps when D holds 50 %; bars = flows into D (flows.csv start/end, bytes sent); faded = cancelled",
         missing="per-fragment receive timestamps at D live on elves-04 (node_D/fragments.csv was not copied back); a cumulative-progress-by-provider curve needs them")
    rows = {(r["scenario"], r["policy"]): r for r in rcsv(EV / "restore_epilot_v2/summary_by_config.csv")}
    sc = [("A0", "No change"), ("A1", "Forwarder\ncollapse"), ("A2", "Collapse +\nrecovery"), ("B", "Source-share\nchange")]
    fig, ax = new(wide=True)
    V = {(n, p): fnum(rows[(s, p)]["t_r_median"]) for s, n in sc for p in ("reuse_aware_in", "reuse_dyn") if (s, p) in rows}
    # A1 has no reuse_aware_in in v2: take the same condition from Full E (identical harness version, condition 3)
    fe = {(r["cond"], r["policy"]): r for r in rcsv(EV / "restore_fulle/summary_by_config.csv")}
    V[("Forwarder\ncollapse", "reuse_aware_in")] = fnum(fe[("3 C degradation", "reuse_aware_in")]["t_r"])
    bars(ax, [n for _, n in sc], ["reuse_aware_in", "reuse_dyn"], V)
    for i, (s, n) in enumerate(sc):
        r = rows.get((s, "reuse_dyn"))
        if r:
            ax.text(i + 0.2, V[(n, "reuse_dyn")] + 1.0, f"{int(float(r['n_replans']))} re-plans", ha="center", fontsize=bg.F2_ANNOT - 6, family=bg.FONT_FAMILY)
    ax.set_ylim(0, 62)
    finish(ax, "Scenario (E-pilot v2; collapse reference for 'at moves' from Full E cond. 3)", "Restore at owner (s)", legend_kw={"loc": "upper right"})
    bg.save(fig, OUT / "eval/F6b_event_driven_vs_at_moves", tight=False)
    meta("eval/F6b_event_driven_vs_at_moves", rq="RQ5", source=["results/evaluation/restore_epilot_v2/summary_by_config.csv", "results/evaluation/restore_fulle/summary_by_config.csv (cond 3, at-moves value)"],
         measured=True, level="network-level", config="v2 hysteresis (dT > C_switch + max(2 s, 0.1 ETA), idle estimates kept); 3 reps each; 0 premature re-plans, 0 oscillations",
         note="A1 'at moves' bar comes from Full E condition 3 (same condition, same harness version); E-pilot v2 did not rerun it")


def f6c():
    """Measured fragment progress at the final owner D by provider (needs node_D/fragments.csv recovered from elves-04)."""
    runs = sorted(EV.glob("restore_fulle/policy=*_N=1_moves=2_rho=2_ev=*_rep=1_*"))
    pick = {p: next((d for d in runs if d.name.startswith(f"policy={p}_")), None) for p in ("reuse_aware_in", "reuse_dyn")}
    missing = [str(d.relative_to(ROOT)) for d in pick.values() if d is None or not (d / "node_D" / "fragments.csv").exists()]
    if missing:
        print(f"  F6c skipped: node_D/fragments.csv not recovered for {missing}")
        return
    fig, axes = plt.subplots(1, 2, figsize=WIDE, sharey=True)
    fig.subplots_adjust(left=0.08, right=0.99, bottom=0.2, top=0.88, wspace=0.06)
    srcs = {"A": ("source A", bg.RED), "B": ("holder B", "#2a9d8f"), "C": ("holder C", bg.ORANGE)}
    info = {}
    for ax, (p, d) in zip(axes, pick.items()):
        evs = list(csv.DictReader(open(d / "events.csv")))
        t0w = float(next(e for e in evs if e["event"] == "start")["t_wall"])
        rel = lambda name: [float(e["t_rel"]) for e in evs if e["event"] == name]  # noqa: E731
        mv, cap, rp = rel("move"), rel("cap_change"), rel("replan")
        rest = next((float(e["t_rel"]) for e in evs if e["event"] == "restored" and '"D"' in e["detail"]), None)
        rows = [r for r in csv.DictReader(open(d / "node_D" / "fragments.csv")) if r["event"] == "recv" and r["ok"] == "True"]
        seen, pts = set(), defaultdict(list)
        for r in sorted(rows, key=lambda r: float(r["t"])):
            if r["fragment_id"] in seen:
                continue
            seen.add(r["fragment_id"]); pts[r["src"]].append(float(r["t"]) - t0w)
        n = 412
        for s_, (lab, col) in srcs.items():
            ts = pts.get(s_, [])
            if ts:
                ax.step([mv[-1]] + ts, [0] + [100.0 * (i + 1) / n for i in range(len(ts))], where="post", color=col, lw=2.2, label=f"from {lab}")
        allt = sorted(t for v in pts.values() for t in v)
        ax.step([mv[-1]] + allt, [0] + [100.0 * (i + 1) / n for i in range(len(allt))], where="post", color="black", lw=1.6, ls="--", label="total at D")
        for t in cap:
            ax.axvline(t, color=bg.RED, ls="--", lw=1.4)
        for t in rp:
            ax.axvline(t, color=bg.BLUE, ls=":", lw=1.8)
        if rest:
            ax.axvline(rest, color="black", lw=1.0)
        ax.set_xlim(mv[-1] - 0.5, (rest or allt[-1]) + 2); ax.set_ylim(0, 102)
        ax.set_title(POLICY[p][0] + (f" ({len(rp)} re-plans, dotted)" if rp else ""), fontsize=bg.F2_ANNOT, family=bg.FONT_FAMILY)
        ax.set_xlabel("Time (s); dashed red = C egress drop", fontsize=bg.F2_ANNOT); ax.tick_params(labelsize=bg.F2_ANNOT - 2, direction="in")
        info[p] = {"run": str(d.relative_to(ROOT)), "fragments_from": {k: len(v) for k, v in pts.items()}, "restored_s": rest, "final_move_s": mv[-1], "replans_s": rp, "cap_change_s": cap}
    axes[0].set_ylabel("Sink at D (% of fragments)", fontsize=bg.F2_ANNOT)
    axes[0].legend(frameon=False, prop={"size": bg.F2_ANNOT - 5, "family": bg.FONT_FAMILY}, loc="upper left")
    bg.save(fig, OUT / "eval/F6c_fragment_progress_by_provider", tight=False)
    meta("eval/F6c_fragment_progress_by_provider", rq="RQ5", source=info, measured=True, level="network-level, 4 physical hosts (Full E condition 3, rep 1)",
         config="checksum-verified first arrivals of each fragment at D (node_D/fragments.csv recovered from elves-04), by sender",
         clock="node D's wall clock minus the orchestrator's start time on elves-01; hosts are NTP-synchronized, the residual offset (ms) is not removed")


# ======================================================================================== F7 proactive placement
def f7():
    rows = rcsv(EV / "restore_prepos_pilot/summary_by_config.csv")
    V = {(r["dest"] + (" (top-1)" if r["dest"] == "B" else ""), r["prepos"]): fnum(r["t_r_median"]) for r in rows}
    fig, ax = new()
    bars(ax, ["B (top-1)", "C", "D"], ["none", "oracle", "top1", "proportional"], V)
    ax.set_ylim(0, 18)
    finish(ax, "True destination (p = 0.6 / 0.3 / 0.1)", "Restore after move (s)", legend_kw={"loc": "upper left", "ncol": 2})
    bg.save(fig, OUT / "eval/F7a_placement_correct_incorrect", tight=False)
    meta("eval/F7a_placement_correct_incorrect", rq="RQ6", source="results/evaluation/restore_prepos_pilot/summary_by_config.csv", measured=True, level="network-level, 4 hosts",
         config="single session, L = 10 s, budget 1 Sink, 1 Gbps; one run per (policy, destination); incorrect predictions forward from never-owner holders",
         error_bars="none (1 rep; model agreement within 0.2 s)", missing="budget x lookahead (A1) and calibration (A2) sweeps not run; the predictor is synthetic")
    rows = rcsv(EV / "restore_holder_diag/summary_by_config.csv")
    T = {(r["policy"], fnum(r["holder_mbps"]), r["prepos"]): fnum(r["t_r_median"]) for r in rows}
    bhs = sorted({k[1] for k in T})
    fig, ax = new()
    for p in ("reuse_fixed", "reuse_aware_in"):
        g = [T[(p, b, "none")] - T[(p, b, "top1")] for b in bhs]
        lab, col, mk = POLICY[p]
        ax.plot(bhs, g, color=col, marker=mk, ms=9, lw=2.2, markeredgewidth=1.8, label=lab)
    ax.axhline(0, color="black", lw=1.0); ax.axvline(250, color="black", ls=":", lw=1.2)
    ax.text(265, -70, "analytical\ncrossover\n250 Mbps", fontsize=bg.F2_ANNOT - 5, family=bg.FONT_FAMILY)
    ax.set_xscale("log", base=2); ax.set_xticks(bhs); ax.set_xticklabels([f"{b:g}" for b in bhs]); ax.minorticks_off()
    finish(ax, "Holder egress (Mbps)", "Gain of wrong placement (s)", legend_kw={"loc": "lower right"})
    bg.save(fig, OUT / "eval/F7b_wrong_placement_value_vs_holder", tight=False)
    meta("eval/F7b_wrong_placement_value_vs_holder", rq="RQ6", source="results/evaluation/restore_holder_diag/summary_by_config.csv", measured=True, level="network-level",
         config="N=4 sharing a 1 Gbps source; 0.5 Sink pre-positioned at B, true destination C; others start at the move; 3 reps; gain = T_r(no placement) - T_r(top-1)",
         note="diagnostic, not pre-registered (A3's frozen H5e clauses are reported separately: shared-source PASS, ingress-bound PASS, slow-holder fixed PASS, slow-holder aware FAIL by 0.2 s)")


# ======================================================================================== F8 (single migration only)
def single_handoff_runs(bw="1000"):
    out = defaultdict(list)
    for d in sorted(EV.glob(f"single_handoff/policy=*_bw={bw}_rep=*")):
        if not (d / "metrics.csv").exists():
            continue
        pol = d.name.split("_bw=")[0].split("=")[1]
        m = rcsv(d / "metrics.csv")
        t = [fnum(r["t_out_rel"]) for r in m if fnum(r["t_out_rel"]) is not None]
        mem = json.load(open(d / "summary.json")).get("gpu_mem_alloc_mb_max")
        out[pol].append({"dir": d.name, "t": t, "mem": mem})
    return out


def f8():
    R = single_handoff_runs("1000")
    pols = ["full", "replay", "cold", "ours"]
    fig, ax = new()
    for i, p in enumerate(pols):
        gaps = []
        for run in R[p]:
            t = run["t"]
            gaps += [t[0]] + [b - a for a, b in zip(t, t[1:])]   # first entry: trigger -> first output
        lab, col, _ = POLICY[p]
        q = np.percentile(gaps, [50, 95, 99, 100])
        ax.bar([i - 0.3, i - 0.1, i + 0.1, i + 0.3], q, 0.19, color=[col] * 4, edgecolor="black", linewidth=0.6,
               hatch=None, alpha=1.0)
        for xx, v, lab_ in zip([i - 0.3, i - 0.1, i + 0.1, i + 0.3], q, ["p50", "p95", "p99", "max"]):
            ax.text(xx, v * 1.12, lab_, ha="center", fontsize=10, family=bg.FONT_FAMILY, rotation=90, va="bottom")
    ax.set_yscale("log"); ax.set_ylim(0.2, 600)
    ax.set_xticks(range(len(pols))); ax.set_xticklabels([POLICY[p][0] for p in pols], fontsize=bg.F2_ANNOT - 2)
    finish(ax, "Policy (single migration, 1 Gbps)", "Output interval (s)", legend=False)
    bg.save(fig, OUT / "eval/F8a_output_interval_single_migration", tight=False)
    meta("eval/F8a_output_interval_single_migration", rq="RQ7", source="results/evaluation/single_handoff/policy=*_bw=1000_rep=*/metrics.csv", measured=True,
         config="GPU, elves-01 -> elves-02, 1 Gbps, 3 reps x 80 output chunks after the trigger at the destination; interval = time between consecutive chunk outputs, first = trigger -> first output",
         n_samples={p: sum(len(r["t"]) for r in R[p]) for p in pols},
         caution="one chunk = one model call (several frames); per-frame latency, jitter and deadline misses need the Experiment D definitions; repeated / concurrent / degraded scenarios not measured on GPU")


# ======================================================================================== F9 scalability
def f9():
    rows = rcsv(EV / "restore_contention_v2/summary_by_config.csv")
    fig, ax = new()
    for p in ("restart", "reuse_fixed", "reuse_adaptive"):
        rr = sorted((int(r["N"]), fnum(r["makespan_median"])) for r in rows if r["policy"] == p and r["moves"] == "1")
        lab, col, mk = POLICY[p]
        ax.plot([a for a, _ in rr], [b for _, b in rr], color=col, marker=mk, ms=9, lw=2.2, markeredgewidth=1.8, label=lab)
    ax.set_xscale("log", base=2); ax.set_xticks([1, 2, 4, 8]); ax.set_xticklabels(["1", "2", "4", "8"]); ax.minorticks_off()
    finish(ax, "Concurrent sessions sharing the source", "Restoration makespan (s)", legend_kw={"loc": "upper left"})
    bg.save(fig, OUT / "eval/F9a_sessions_makespan", tight=False)
    meta("eval/F9a_sessions_makespan", rq="RQ8", source="results/evaluation/restore_contention_v2/summary_by_config.csv (moves=1)", measured=True, level="network-level",
         config="N sessions, one move each (staggered), 1 Gbps source, 3 reps", missing="GPU memory / utilization overhead and multi-session GPU runs not measured")


# ======================================================================================== design diagrams (schematics)
def design():
    pos = {"A": (0.0, 0.5), "B": (1.0, 0.85), "C": (1.0, 0.5), "D": (1.0, 0.15)}
    plans = {"Star": [("A", "B"), ("A", "C"), ("A", "D")], "Line": [("A", "B"), ("B", "C"), ("C", "D")], "Tree": [("A", "B"), ("B", "C"), ("B", "D")],
             "Butterfly-like": [("A", "B"), ("A", "C"), ("A", "D"), ("B", "C"), ("B", "D"), ("C", "B"), ("C", "D"), ("D", "B"), ("D", "C")]}
    # OTTER panel: fragment counts per link actually assigned by the aware rule in the measured B_f = 500 Mbps run
    run = sorted(EV.glob("restore_dissem_hetero/plan=aware_bs=1000_bf=500_*"))[0]
    asg = json.load(open(run / "summary.json"))["assignment"]
    fig, axes = plt.subplots(1, 5, figsize=(16.2, 3.6))
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.12, top=0.84, wspace=0.08)

    def draw(ax, edges, title, widths=None):
        for (u, v) in edges:
            (x0, y0), (x1, y1) = pos[u], pos[v]
            if u != "A" and v != "A":   # forward between edges: curve so both directions are visible
                ax.annotate("", xy=(x1 + 0.08, y1), xytext=(x0 + 0.08, y0), arrowprops=dict(arrowstyle="-|>", lw=(widths or {}).get((u, v), 1.6),
                            color=bg.ORANGE if widths else "black", connectionstyle="arc3,rad=-0.6"))
            else:
                ax.annotate("", xy=(x1 - 0.06, y1), xytext=(x0 + 0.06, y0), arrowprops=dict(arrowstyle="-|>", lw=(widths or {}).get((u, v), 1.6),
                            color=bg.BLUE if widths else "black"))
        for n, (x, y) in pos.items():
            ax.add_patch(plt.Circle((x, y), 0.07, facecolor="white", edgecolor="black", lw=1.5, zorder=5))
            ax.text(x, y, n, ha="center", va="center", fontsize=16, family=bg.FONT_FAMILY, zorder=6)
        ax.set_xlim(-0.2, 1.55); ax.set_ylim(-0.05, 1.05); ax.axis("off"); ax.set_title(title, fontsize=17, family=bg.FONT_FAMILY)

    for ax, (t, e) in zip(axes[:4], plans.items()):
        draw(ax, e, t + " (fixed)")
    E = [tuple(k.split("->")) for k in asg]
    W = {tuple(k.split("->")): 0.8 + 6.0 * v / max(asg.values()) for k, v in asg.items()}
    draw(axes[4], E, "OTTER assignment\n(measured, B_f = 500 Mbps)", W)
    for k, v in asg.items():
        u, w_ = k.split("->")
        (x0, y0), (x1, y1) = pos[u], pos[w_]
        axes[4].text((x0 + x1) / 2 + (0.25 if u != "A" else -0.02), (y0 + y1) / 2 + 0.04, str(v), fontsize=10, family=bg.FONT_FAMILY, color="black")
    bg.save(fig, OUT / "design/D1_transfer_graphs", tight=False)
    meta("design/D1_transfer_graphs", kind="design diagram: panels 1-4 are schematics of the fixed baselines; panel 5 draws the fragment counts per link that the aware rule assigned in one measured run",
         source=str(run.relative_to(ROOT)) + "/summary.json (assignment)", measured="panel 5 only (assignment counts, not timing)",
         caution="does not depict runtime reconfiguration; F6a shows measured re-planning")


def f9b():
    R = single_handoff_runs("1000")
    pols = ["full", "replay", "cold", "ours"]
    fig, ax = new()
    for i, p in enumerate(pols):
        v = [r["mem"] / 1024 for r in R[p] if r["mem"]]
        lab, col, _ = POLICY[p]
        ax.bar(i, st.median(v), 0.6, color=col, edgecolor="black", linewidth=0.6, yerr=[[st.median(v) - min(v)], [max(v) - st.median(v)]], capsize=3)
        ax.text(i, st.median(v) + 0.6, f"{st.median(v):.2f}", ha="center", fontsize=bg.F2_ANNOT - 5, family=bg.FONT_FAMILY)
    ax.set_xticks(range(len(pols))); ax.set_xticklabels([POLICY[p][0] for p in pols], fontsize=bg.F2_ANNOT - 2); ax.set_ylim(0, 32)
    finish(ax, "Policy (destination GPU, 1 Gbps)", "Peak allocated (GiB)", legend=False)
    bg.save(fig, OUT / "eval/F9b_destination_gpu_memory", tight=False)
    meta("eval/F9b_destination_gpu_memory", rq="RQ8", source="results/evaluation/single_handoff/policy=*_bw=1000_rep=*/summary.json (gpu_mem_alloc_mb_max)", measured=True,
         config="max over output chunks of torch.cuda.memory_allocated at the destination (sampled once per chunk, tools/proto_handoff.py), 3 reps",
         caution="allocator peak, not reserved memory or utilization; source-side and multi-session overheads not measured")


GROUPS = {"F1": f1, "F2": f2, "F3": f3, "F4": f4, "F5": f5, "F6": lambda: (f6(), f6c()), "F7": f7, "F8": f8, "F9": lambda: (f9(), f9b()), "D": design}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    bg.configure_matplotlib()
    for k, fn in GROUPS.items():
        if a.only and k not in a.only.split(","):
            continue
        print(f"== {k}")
        fn()


if __name__ == "__main__":
    main()
