#!/usr/bin/env python3
"""Aggregate Experiment 3 Scenario B (results/evaluation/<experiment>/policy=*) and apply the pre-registered criteria
from EXPERIMENT_PLAN.md. Writes summary.csv (per run), summary_by_config.csv (medians), criteria.md, and figures in the
Fig. 2 style (figE6_makespan_vs_N, figE7_source_bytes_vs_N, figE7b_coverage_vs_N).

    python tools/eval/aggregate_restore.py --experiment restore_contention_v2
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

TM = 14.05 / 2
POL = [("restart", "Restart", "o", "solid"), ("reuse_fixed", "Reuse (fixed)", "D", "solid"), ("reuse_adaptive", "Reuse (adaptive)", "^", "dashed")]


def load(root: Path):
    runs, incomplete = [], []
    for d in sorted(root.glob("policy=*")):
        if not (d / "summary.json").exists():
            incomplete.append(d.name); continue
        s = json.load(open(d / "summary.json")); s["dir"] = d.name
        runs.append(s)
    return runs, incomplete


def med(v):
    v = [x for x in v if x is not None]
    return st.median(v) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="restore_contention_v2")
    ap.add_argument("--no_figures", action="store_true")
    a = ap.parse_args()
    root = ROOT / "results/evaluation" / a.experiment
    runs, incomplete = load(root)
    S = runs[0]["sink_bytes"] if runs else 1
    invalid = [r["dir"] for r in runs if not all(v for v in r["validation"].values())]
    valid = [r for r in runs if r["dir"] not in invalid]
    G = defaultdict(list)
    for r in valid:
        G[(r["policy"], r["N"], r["moves"])].append(r)
    with open(root / "summary.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["run", "policy", "N", "moves", "rep", "restored", "makespan_s", "first_median_s", "coverage", "source_per_session", "total_per_session",
                    "unused_per_session", "valid"])
        for r in runs:
            w.writerow([r["dir"], r["policy"], r["N"], r["moves"], r["rep"], r["restored_sessions"], r["makespan_s"], r["first_restored"]["median"],
                        f"{r['coverage_mean']:.3f}", f"{r['normalized']['source_per_session']:.3f}", f"{r['normalized']['total_per_session']:.3f}",
                        f"{r['normalized']['unused_per_session']:.3f}", r["dir"] not in invalid])
    Ns = sorted({r["N"] for r in valid})
    rows = []
    for (p, n, mv), rs in sorted(G.items()):
        rows.append({"policy": p, "N": n, "moves": mv, "reps": len(rs), "restored_all_reps": all(r["restored_sessions"] == n for r in rs),
                     "restored_min": min(r["restored_sessions"] for r in rs), "makespan_median": med([r["makespan_s"] for r in rs]),
                     "first_median": med([r["first_restored"]["median"] for r in rs]), "coverage_median": med([r["coverage_mean"] for r in rs]),
                     "source_per_session": med([r["normalized"]["source_per_session"] for r in rs]),
                     "total_per_session": med([r["normalized"]["total_per_session"] for r in rs]),
                     "unused_per_session": med([r["normalized"]["unused_per_session"] for r in rs])})
    with open(root / "summary_by_config.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    R = {(x["policy"], x["N"], x["moves"]): x for x in rows}
    f = lambda v: "-" if v is None else f"{v:.1f}"  # noqa: E731
    out = [f"# Scenario B criteria ({a.experiment}), medians of valid runs", "",
           f"Valid runs {len(valid)}/{len(runs)}; invalid: {invalid or 'none'}; incomplete directories: {incomplete or 'none'}", "",
           "## H3a single move: reuse_fixed makespan shorter than restart by >= 0.5 T_m (3.5 s)", "",
           "| N | restart | reuse_fixed | reuse_adaptive | restart - fixed | H3a |", "|---|---|---|---|---|---|"]
    for n in Ns:
        rs, fx, ad = R.get(("restart", n, 1)), R.get(("reuse_fixed", n, 1)), R.get(("reuse_adaptive", n, 1))
        if not (rs and fx):
            continue
        gap = None if rs["makespan_median"] is None or fx["makespan_median"] is None else rs["makespan_median"] - fx["makespan_median"]
        out.append(f"| {n} | {f(rs['makespan_median'])} | {f(fx['makespan_median'])} | {f(ad and ad['makespan_median'])} | {f(gap)} | "
                   f"{'supported' if gap is not None and gap >= 0.5 * TM else 'not supported'} |")
    out += ["", "## H3a continuous: restart restores < N sessions in all reps while reuse_fixed restores all N in all reps", "",
            "| N | restart restored (min over reps) | reuse_fixed restored all in all reps | reuse_fixed coverage | H3a |", "|---|---|---|---|---|"]
    for n in Ns:
        rs, fx = R.get(("restart", n, 0)), R.get(("reuse_fixed", n, 0))
        if not (rs and fx):
            continue
        rs_max = max(r["restored_sessions"] for r in G[("restart", n, 0)])
        ok = rs_max < n and fx["restored_all_reps"]
        out.append(f"| {n} | {rs['restored_min']}..{rs_max} of {n} | {fx['restored_all_reps']} | {f(fx['coverage_median'])} | {'supported' if ok else 'not supported'} |")
    out += ["", "## H3b: reuse_adaptive better than reuse_fixed (makespan -1 s single move, coverage +0.05 continuous), never worse by the same margin", "",
            "| N | single: fixed / adaptive makespan | continuous: fixed / adaptive coverage | better | worse |", "|---|---|---|---|---|"]
    better, worse = [], []
    for n in Ns:
        fs, as_, fc, ac = R.get(("reuse_fixed", n, 1)), R.get(("reuse_adaptive", n, 1)), R.get(("reuse_fixed", n, 0)), R.get(("reuse_adaptive", n, 0))
        b = w_ = False
        if fs and as_ and fs["makespan_median"] and as_["makespan_median"]:
            b |= as_["makespan_median"] <= fs["makespan_median"] - 1.0; w_ |= as_["makespan_median"] >= fs["makespan_median"] + 1.0
        if fc and ac:
            b |= ac["coverage_median"] >= fc["coverage_median"] + 0.05; w_ |= ac["coverage_median"] <= fc["coverage_median"] - 0.05
        if b: better.append(n)
        if w_: worse.append(n)
        out.append(f"| {n} | {f(fs and fs['makespan_median'])} / {f(as_ and as_['makespan_median'])} | {f(fc and fc['coverage_median'])} / {f(ac and ac['coverage_median'])} | {b} | {w_} |")
    out += ["", f"H3b: {'supported at N = ' + str(better) if better and not worse else 'not supported'} (better at {better or 'none'}, worse at {worse or 'none'})"]
    (root / "criteria.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    if a.no_figures:
        return
    import make_background_figures as bg
    import matplotlib.pyplot as plt
    bg.configure_matplotlib()
    col = {"restart": bg.RED, "reuse_fixed": bg.BLUE, "reuse_adaptive": bg.BLACK}
    figs = [("figE6_makespan_vs_N", 1, lambda r: r["makespan_s"], "Restoration Makespan (s)", "upper left"),
            ("figE7_source_bytes_vs_N", 1, lambda r: r["normalized"]["source_per_session"], "Source Bytes / Sink", "upper right"),
            ("figE7b_coverage_vs_N", 0, lambda r: r["coverage_mean"], "Continuity Coverage", "upper left")]
    for name, mv, key, ylabel, legend_loc in figs:
        fig = plt.figure(figsize=bg.FIG2A_SIZE)
        ax = fig.add_axes(bg.FIG2A_AXES)
        for p, lab, mk, ls in POL:
            xs, ys, lo, hi = [], [], [], []
            for n in Ns:
                v = [key(r) for r in G.get((p, n, mv), []) if key(r) is not None]
                if v:
                    xs.append(n); ys.append(st.median(v)); lo.append(min(v)); hi.append(max(v))
            ax.plot(xs, ys, color=col[p], ls=ls, marker=mk, ms=9, lw=2.4, markerfacecolor="white" if p != "reuse_fixed" else col[p], markeredgewidth=1.8, label=lab)
            ax.fill_between(xs, lo, hi, color=col[p], alpha=0.12, lw=0)
        ax.set_xscale("log", base=2); ax.set_xticks(Ns); ax.set_xticklabels([str(n) for n in Ns]); ax.minorticks_off()
        bg._fig2a_axis(ax, "Concurrent Sessions (N)")
        ax.set_ylabel(ylabel, fontsize=bg.F2_LABEL); ax.tick_params(axis="y", length=5)
        ax.legend(loc=legend_loc, frameon=False, prop={"size": bg.F2_ANNOT - 2, "family": bg.FONT_FAMILY})
        bg.save(fig, root / "figures" / name, tight=False)


if __name__ == "__main__":
    main()
