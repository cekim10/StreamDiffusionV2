#!/usr/bin/env python3
"""Aggregate Experiment 3 Step 2 (results/evaluation/<experiment>/policy=*_bh=*) and apply the pre-registered criteria
P0 / H4a / H4b / H4c from EXPERIMENT_PLAN.md. Writes summary.csv (per run), summary_by_config.csv (medians),
criteria.md, and figures figE8_makespan_vs_bh_N<n> and figE9_source_vs_bh_N<n> (Fig. 2 style).

    python tools/eval/aggregate_holder.py --experiment restore_holder
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
POL = [("restart", "Restart", "o", "solid"), ("reuse_fixed", "Reuse (fixed)", "D", "solid"),
       ("reuse_adaptive", "Reuse (adaptive)", "^", "dashed"), ("reuse_aware", "Reuse (aware)", "s", "solid"),
       ("reuse_aware_in", "Reuse (aware, ingress)", "v", "dashed")]
# crossover set from the pre-registered fluid model (reuse_fixed predicted slower than restart)
CROSS = {(1, 62.5), (1, 125.0), (1, 250.0), (2, 62.5), (2, 125.0), (4, 62.5)}


def load(root: Path):
    runs, incomplete = [], []
    for d in sorted(root.glob("policy=*")):
        if not (d / "summary.json").exists():
            incomplete.append(d.name); continue
        s = json.load(open(d / "summary.json")); s["dir"] = d.name
        s["bh"] = float(s["caps_mbps"]["B:out"])
        runs.append(s)
    return runs, incomplete


def med(v):
    v = [x for x in v if x is not None]
    return st.median(v) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="restore_holder")
    ap.add_argument("--no_figures", action="store_true")
    ap.add_argument("--allow_loopback", action="store_true", help="dry-run data: ignore the four-distinct-hosts check")
    ap.add_argument("--ref", default=None, help="reference experiment supplying the policies this one did not run (e.g. restore_holder)")
    a = ap.parse_args()
    root = ROOT / "results/evaluation" / a.experiment
    runs, incomplete = load(root)
    if a.ref:   # validation experiments hold one policy; the other policies' runs come from the reference experiment
        ref_runs, _ = load(ROOT / "results/evaluation" / a.ref)
        have = {r["policy"] for r in runs}
        runs += [r for r in ref_runs if r["policy"] not in have]
    skip = {"four_hosts_distinct"} if a.allow_loopback else set()
    invalid = [r["dir"] for r in runs if not all(v for k, v in r["validation"].items() if k not in skip)]
    valid = [r for r in runs if r["dir"] not in invalid]
    G = defaultdict(list)
    for r in valid:
        G[(r["policy"], r["N"], r["bh"])].append(r)
    with open(root / "summary.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["run", "policy", "N", "holder_mbps", "rep", "restored", "makespan_s", "first_median_s", "source_per_session", "total_per_session",
                    "unused_per_session", "valid"])
        for r in runs:
            w.writerow([r["dir"], r["policy"], r["N"], r["bh"], r["rep"], r["restored_sessions"], r["makespan_s"], r["first_restored"]["median"],
                        f"{r['normalized']['source_per_session']:.3f}", f"{r['normalized']['total_per_session']:.3f}",
                        f"{r['normalized']['unused_per_session']:.3f}", r["dir"] not in invalid])
    Ns = sorted({r["N"] for r in valid}); BHs = sorted({r["bh"] for r in valid})
    rows = []
    for (p, n, bh), rs in sorted(G.items()):
        rows.append({"policy": p, "N": n, "holder_mbps": bh, "reps": len(rs), "restored_min": min(r["restored_sessions"] for r in rs),
                     "makespan_median": med([r["makespan_s"] for r in rs]), "makespan_min": min((r["makespan_s"] for r in rs if r["makespan_s"]), default=None),
                     "makespan_max": max((r["makespan_s"] for r in rs if r["makespan_s"]), default=None),
                     "source_per_session": med([r["normalized"]["source_per_session"] for r in rs]),
                     "total_per_session": med([r["normalized"]["total_per_session"] for r in rs]),
                     "unused_per_session": med([r["normalized"]["unused_per_session"] for r in rs])})
    with open(root / "summary_by_config.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    R = {(x["policy"], x["N"], x["holder_mbps"]): x for x in rows}
    f = lambda v, d=1: "-" if v is None else f"{v:.{d}f}"  # noqa: E731
    ms = lambda p, n, bh: (R.get((p, n, bh)) or {}).get("makespan_median")  # noqa: E731
    sb = lambda p, n, bh: (R.get((p, n, bh)) or {}).get("source_per_session")  # noqa: E731
    out = [f"# Step 2 criteria ({a.experiment}), medians of valid runs", "",
           f"Valid runs {len(valid)}/{len(runs)}; invalid: {invalid or 'none'}; incomplete directories: {incomplete or 'none'}", "",
           "## Makespan (s) and source bytes per session (Sinks); C = pre-registered crossover condition", "",
           "| N | B_h | C | restart | reuse_fixed | reuse_adaptive | reuse_aware | P0 restart < fixed - 3.5 s | H4a aware <= 0.85 fixed | H4b aware <= 1.05 min(fixed*, restart) | H4c source |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    fails = defaultdict(list)
    for n in Ns:
        for bh in BHs:
            inC = (n, bh) in CROSS
            rs, fx, ad, aw = (ms(p, n, bh) for p in ("restart", "reuse_fixed", "reuse_adaptive", "reuse_aware"))
            if None in (rs, fx, aw):
                out.append(f"| {n} | {bh:g} | {'yes' if inC else ''} | {f(rs)} | {f(fx)} | {f(ad)} | {f(aw)} | incomplete | | | |"); continue
            p0 = rs <= fx - 0.5 * TM if inC else None
            h4a = aw <= 0.85 * fx if inC else None
            h4b = (aw <= 1.05 * fx if not inC else True) and aw <= 1.05 * rs
            src_aw, src_fx, src_rs = sb("reuse_aware", n, bh), sb("reuse_fixed", n, bh), sb("restart", n, bh)
            h4c = (src_aw <= src_fx + 0.05 if not inC else True) and src_aw <= src_rs
            for k, v in (("P0", p0), ("H4a", h4a), ("H4b", h4b), ("H4c", h4c)):
                if v is False:
                    fails[k].append((n, bh))
            cell = lambda v: "" if v is None else ("ok" if v else "FAIL")  # noqa: E731
            out.append(f"| {n} | {bh:g} | {'yes' if inC else ''} | {f(rs)} /{f(src_rs, 2)} | {f(fx)} /{f(src_fx, 2)} | {f(ad)} /{f(sb('reuse_adaptive', n, bh), 2)} | "
                       f"{f(aw)} /{f(src_aw, 2)} | {cell(p0)} | {cell(h4a)} | {cell(h4b)} | {cell(h4c)} |")
    out += ["", "(* in the no-crossover set only; everywhere aware must also be within 1.05 x restart)", ""]
    if any(p == "reuse_aware_in" for p, _, _ in R):
        out += ["## H4c correction: reuse_aware_in vs reuse_aware (makespan s / source Sinks per session)", "",
                "| N | B_h | aware | aware_in | d makespan | d source |", "|---|---|---|---|---|---|"]
        for n in Ns:
            for bh in BHs:
                aw, ai = R.get(("reuse_aware", n, bh)), R.get(("reuse_aware_in", n, bh))
                if aw and ai and aw["makespan_median"] and ai["makespan_median"]:
                    out.append(f"| {n} | {bh:g} | {f(aw['makespan_median'])} /{f(aw['source_per_session'], 2)} | {f(ai['makespan_median'])} /{f(ai['source_per_session'], 2)} | "
                               f"{ai['makespan_median'] - aw['makespan_median']:+.1f} | {ai['source_per_session'] - aw['source_per_session']:+.2f} |")
        out.append("")
    verdict = {k: ("holds" if not fails[k] else f"fails at {sorted(fails[k])}") for k in ("P0", "H4a", "H4b", "H4c")}
    for k, v in verdict.items():
        out.append(f"- {k}: {v}")
    case = "Case 1 (bottleneck-aware provider selection + progress preservation)" if not (fails["P0"] or fails["H4a"] or fails["H4b"]) else \
           "Case 3 (drop adaptive routing)" if fails["H4b"] else "Case 2 (progress-preserving restoration only)"
    out += ["", f"Outcome mapping: {case}"]
    (root / "criteria.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    if a.no_figures:
        return
    import make_background_figures as bg
    import matplotlib.pyplot as plt
    bg.configure_matplotlib()
    col = {"restart": bg.RED, "reuse_fixed": bg.BLUE, "reuse_adaptive": bg.BLACK, "reuse_aware": bg.ORANGE if hasattr(bg, "ORANGE") else "#e07b00"}
    for n in Ns:
        for name, key, ylabel, loc in [(f"figE8_makespan_vs_bh_N{n}", lambda r: r["makespan_s"], "Restoration Makespan (s)", "upper right"),
                                       (f"figE9_source_vs_bh_N{n}", lambda r: r["normalized"]["source_per_session"], "Source Bytes / Sink", "upper right")]:
            fig = plt.figure(figsize=bg.FIG2A_SIZE)
            ax = fig.add_axes(bg.FIG2A_AXES)
            for p, lab, mk, ls in POL:
                xs, ys, lo, hi = [], [], [], []
                for bh in BHs:
                    v = [key(r) for r in G.get((p, n, bh), []) if key(r) is not None]
                    if v:
                        xs.append(bh); ys.append(st.median(v)); lo.append(min(v)); hi.append(max(v))
                ax.plot(xs, ys, color=col[p], ls=ls, marker=mk, ms=9, lw=2.4, markerfacecolor="white" if p in ("restart", "reuse_adaptive") else col[p],
                        markeredgewidth=1.8, label=lab)
                ax.fill_between(xs, lo, hi, color=col[p], alpha=0.12, lw=0)
            ax.set_xscale("log", base=2); ax.set_xticks(BHs); ax.set_xticklabels([f"{b:g}" for b in BHs]); ax.minorticks_off()
            bg._fig2a_axis(ax, "Holder Egress (Mbps)")
            ax.set_ylabel(ylabel, fontsize=bg.F2_LABEL); ax.tick_params(axis="y", length=5)
            if name.startswith("figE8"):   # the source-bytes panel of the same N shares this legend
                ax.legend(loc=loc, frameon=False, prop={"size": bg.F2_ANNOT - 4, "family": bg.FONT_FAMILY}, title=f"N = {n}",
                          title_fontsize=bg.F2_ANNOT - 4)
            else:
                ax.text(0.04, 0.10, f"N = {n}", transform=ax.transAxes, ha="left", va="bottom", fontsize=bg.F2_ANNOT - 4, family=bg.FONT_FAMILY)
            bg.save(fig, root / "figures" / name, tight=False)


if __name__ == "__main__":
    main()
