#!/usr/bin/env python3
"""Phase 1 figures for physical repeated mobility A -> B -> C -> D (EC-LLM style, Fig. 2 canvas and fonts).

Reads results/evaluation/repeated_mobility/policy=*_bw=1000_rho=<r>_*/ (sweep runs only; the shakedown runs from
2026-10-13 13:0x are excluded) and writes results/evaluation/repeated_mobility/figures/:
    figE1_latency_vs_rho       continuity-ready (first output on the bound Sink) after the final move vs rho
    figE2_bytes_vs_rho         total bytes, unused bytes and source bytes per Sink vs rho (three panels, separate files)
    figE3_timeline_<policy>    Sink availability per node over time for one rho = 4 run (restart and reuse)
    mobility_table.csv         per (policy, rho) medians and ranges

Byte classes (plan, section 3, definition (a)-(c)):
    used    delivered to the final owner, forwarded later, or delivered to an intermediate owner that bound the Sink
    unused  delivered to an owner that neither bound nor forwarded it (abandoned before use)
    lost    sent but never delivered (flow cancelled at a move)
The orchestrator's own `wasted` counts every delivery to a non-final owner that was not forwarded, including copies
that the intermediate owner bound and used (rho 0.5); `unused` excludes those.

    python tools/eval/plot_mobility.py
"""

from __future__ import annotations

import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import make_background_figures as bg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

RUNS = ROOT / "results/evaluation/repeated_mobility"
OUT = RUNS / "figures"
RHOS = [0.5, 1.0, 2.0, 4.0, 8.0]
T_S = 14.05
POL = [("restart", "Restart", bg.RED, "o", "solid"), ("relay", "Relay", bg.DIMGRAY, "s", "dashdot"),
       ("relay_pipe", "Pipelined relay", bg.ORANGE, "^", "dashed"), ("split", "Reuse (fixed routing)", bg.BLUE, "D", "solid"),
       ("direct", "Oracle (final owner known)", bg.BLACK, "x", "dotted")]


def load():
    G = defaultdict(list)
    for d in sorted(RUNS.glob("policy=*_bw=1000_rho=[0-9]*")):
        if "20261013-13" in d.name or not (d / "summary.json").exists():
            continue
        s = json.load(open(d / "summary.json"))
        s["dir"] = d
        s["classes"] = classify(d, s)
        G[(s["policy"], s["rho"])].append(s)
    return G


def classify(d: Path, s: dict) -> dict:
    ev = {r["event"] for r in csv.DictReader(open(d / "events.csv"))}
    bound = {n for n in "ABCD" if f"{n}:sink_bind" in ev}
    final = s["path"][-1]
    rows = list(csv.DictReader(open(d / "fragments.csv")))
    sent_from = defaultdict(list)
    for r in rows:
        if r["event"] == "sent":
            sent_from[(r["src"], r["fragment_id"])].append(float(r["t_rel"]))
    used = unused = 0
    for r in rows:
        if r["event"] != "recv" or r["ok"] != "True" or r["dup"] == "True":
            continue
        n = int(r["bytes"])
        fwd = any(t >= float(r["t_rel"]) - 1e-3 for t in sent_from.get((r["dst"], r["fragment_id"]), []))
        if r["dst"] == final or fwd or r["dst"] in bound:
            used += n
        else:
            unused += n
    lost = s["bytes"]["wasted_in_transit"]
    return {"used": used, "unused": unused, "lost": lost, "dup": s["bytes"]["duplicate"]}


def med(v):
    return st.median(v)


def lineplot(name, G, key, ylabel, ylim, yticks, log=False):
    fig = plt.figure(figsize=bg.FIG2A_SIZE)
    ax = fig.add_axes(bg.FIG2A_AXES)
    for p, lab, col, mk, ls in POL:
        xs, ys, lo, hi = [], [], [], []
        for r in RHOS:
            v = [key(s) for s in G[(p, r)]]
            if v:
                xs.append(r); ys.append(med(v)); lo.append(min(v)); hi.append(max(v))
        ax.plot(xs, ys, color=col, lw=2.4, ls=ls, marker=mk, ms=9, markerfacecolor="white" if p != "split" else col, markeredgewidth=1.8,
                label=lab, zorder=3 if p == "split" else 2)
        ax.fill_between(xs, lo, hi, color=col, alpha=0.12, lw=0)
    ax.set_xscale("log", base=2)
    ax.set_xticks(RHOS); ax.set_xticklabels(["0.5", "1", "2", "4", "8"])
    ax.minorticks_off()
    ax.axvline(1.0, color=bg.BLACK, lw=1.0, ls=":")
    ax.set_xlim(0.42, 9.5); ax.set_ylim(*ylim); ax.set_yticks(yticks)
    bg._fig2a_axis(ax, r"$\rho = T_s / T_m$")
    ax.set_ylabel(ylabel, fontsize=bg.F2_LABEL)
    ax.tick_params(axis="y", length=5)
    return fig, ax


def main():
    bg.configure_matplotlib()
    G = load()
    OUT.mkdir(parents=True, exist_ok=True)
    S = 1725236640
    # E1
    fig, ax = lineplot("E1", G, lambda s: s["latency_after_final_move_s"]["continuity_ready"], "Continuity-ready (s)", (-1, 44), [0, 10, 20, 30, 40])
    bg.legend(ax, loc="upper left", ncol=1, fontsize=bg.F2_ANNOT - 2, handlelength=2.0) if False else ax.legend(
        loc="upper left", frameon=False, prop={"size": bg.F2_ANNOT - 2, "family": bg.FONT_FAMILY}, handlelength=2.2)
    bg.save(fig, OUT / "figE1_latency_vs_rho", tight=False)
    # E2 panels
    for key, name, ylabel, ylim, yt in (
            (lambda s: s["bytes"]["total_sent"] / S, "figE2a_total_bytes", "Total Bytes / Sink", (0, 3.4), [0, 1, 2, 3]),
            (lambda s: (s["classes"]["unused"] + s["classes"]["lost"]) / S, "figE2b_unused_bytes", "Unused Bytes / Sink", (-0.08, 2.3), [0, 0.5, 1.0, 1.5, 2.0]),
            (lambda s: s["bytes"]["by_src"].get("A", 0) / S, "figE2c_source_bytes", "Source Bytes / Sink", (0, 3.4), [0, 1, 2, 3])):
        fig, ax = lineplot(name, G, key, ylabel, ylim, yt)
        if name == "figE2a_total_bytes":
            ax.legend(loc="lower left", frameon=False, prop={"size": bg.F2_ANNOT - 2, "family": bg.FONT_FAMILY}, handlelength=2.2)
        bg.save(fig, OUT / name, tight=False)
    # E3 timelines (rho 4, rep 1): Sink availability per node over time
    for p, lab, col, *_ in POL:
        if p not in ("restart", "split"):
            continue
        s = sorted(G[(p, 4.0)], key=lambda x: x["rep"])[0]
        rows = list(csv.DictReader(open(s["dir"] / "p_current.csv")))
        n = s["n_frags"]
        fig = plt.figure(figsize=bg.FIG2A_SIZE)
        ax = fig.add_axes(bg.FIG2A_AXES)
        node_col = {"B": bg.BLUE, "C": bg.ORANGE, "D": bg.BLACK}
        for node, c in node_col.items():
            t = [float(r["t_rel"]) for r in rows]; y = [100.0 * int(r[f"held_{node}"]) / n for r in rows]
            ax.plot(t, y, color=c, lw=2.4, drawstyle="steps-post", label=f"held at {node}")
        for m in s["moves"][1:]:
            ax.axvline(m["t_req"], color=bg.BLACK, lw=1.0, ls=":")
        F = s["final"]
        for key_, mk_, lab_, ha_, dy_ in (("sink_bind_rel_s", "*", "bind", "right", 104), ("rejoin_rel_s", "v", "rejoin", "left", 104)):
            if F.get(key_) is not None:
                ax.plot([F[key_]], [100], marker=mk_, ms=14, color=bg.C_DUR, markeredgecolor=bg.BLACK, zorder=5, clip_on=False)
                bg._in_label(ax, F[key_] + (-0.4 if ha_ == "right" else 0.4), dy_, lab_, bg.F2_ANNOT - 2, ha=ha_, va="bottom", color=bg.C_DUR, weight="bold")
        ax.set_xlim(0, max(32.0, (F.get("rejoin_rel_s") or 30) + 2)); ax.set_ylim(0, 118); ax.set_yticks([0, 50, 100])
        bg._fig2a_axis(ax, "Time Since Migration Start (s)")
        ax.set_ylabel("Sink Held (%)", fontsize=bg.F2_LABEL); ax.tick_params(axis="y", length=5)
        ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.45), frameon=False, prop={"size": bg.F2_ANNOT - 2, "family": bg.FONT_FAMILY})
        bg.save(fig, OUT / f"figE3_timeline_{p}", tight=False)
    # table
    with open(OUT / "mobility_table.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["policy", "rho", "n", "cont_ready_after_final_median", "cont_ready_min", "cont_ready_max", "rejoin_after_final_median",
                    "total_over_sink", "unused_over_sink", "lost_over_sink", "orchestrator_wasted_over_sink", "source_over_sink"])
        for p, *_ in POL:
            for r in RHOS:
                rs = G[(p, r)]
                if not rs:
                    continue
                cr = [s["latency_after_final_move_s"]["continuity_ready"] for s in rs]
                w.writerow([p, r, len(rs), f"{med(cr):.2f}", f"{min(cr):.2f}", f"{max(cr):.2f}", f"{med([s['latency_after_final_move_s']['rejoin'] for s in rs]):.2f}",
                            f"{med([s['bytes']['total_sent'] / S for s in rs]):.3f}", f"{med([s['classes']['unused'] / S for s in rs]):.3f}",
                            f"{med([s['classes']['lost'] / S for s in rs]):.3f}", f"{med([s['bytes']['wasted'] / S for s in rs]):.3f}",
                            f"{med([s['bytes']['by_src'].get('A', 0) / S for s in rs]):.3f}"])
    print(open(OUT / "mobility_table.csv").read())


if __name__ == "__main__":
    main()
