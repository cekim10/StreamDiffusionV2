#!/usr/bin/env python3
"""Aggregate Experiment B dissemination runs (results/evaluation/<experiment>/plan=*) and compare them with the fluid
model at each run's caps. Writes summary.csv (per run), summary_by_config.csv (medians per condition x plan),
criteria.md (best fixed plan per condition, aware vs best fixed, H6a-f over the tested conditions) and
figures/figE10_makespan_by_condition (Fig. 2 style).

    python tools/eval/aggregate_dissem.py --experiment restore_dissem_hetero --ref restore_dissem_pilot
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
sys.path.insert(0, str(ROOT / "tools" / "eval"))
import restore_model as rm  # noqa: E402

CTRL = 0.3
PLANS = ["star", "line", "tree", "multipath", "aware"]
FIXED = ["star", "line", "tree", "multipath"]
LABEL = {"star": "Star", "line": "Pipelined line", "tree": "Tree", "multipath": "Multipath", "aware": "Aware"}


def load(root: Path):
    runs, incomplete = [], []
    for d in sorted(root.glob("plan=*")):
        if not (d / "summary.json").exists():
            incomplete.append(d.name); continue
        s = json.load(open(d / "summary.json")); s["dir"] = d.name
        c = s["caps_mbps"]
        s["cond"] = f"Bs={c['A:out']:g}/Bf={c['B:out']:g}/Bin={c['B:in']:g}"
        runs.append(s)
    return runs, incomplete


def model(s):
    caps = {}
    for k, v in s["caps_mbps"].items():
        node, d = k.split(":"); caps[(d, node)] = v * 1e6
    rm.SINK_BYTES = s["sink_bytes"]; rm.FLEN = s["frag_bytes"]; rm.NFR = -(-s["sink_bytes"] // s["frag_bytes"])
    r = rm.DissemModel(s["plan"], caps).run(horizon=1200)
    return (None if r["makespan"] is None else r["makespan"] + CTRL), {d: (None if v is None else v + CTRL) for d, v in r["completion"].items()}, r["source_sinks"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="restore_dissem_hetero")
    ap.add_argument("--ref", default=None, help="experiment supplying extra conditions (e.g. the uniform pilot)")
    ap.add_argument("--no_figures", action="store_true")
    a = ap.parse_args()
    root = ROOT / "results/evaluation" / a.experiment
    runs, incomplete = load(root)
    if a.ref:
        runs += load(ROOT / "results/evaluation" / a.ref)[0]
    invalid = [r["dir"] for r in runs if not all(r["validation"].values())]
    valid = [r for r in runs if r["dir"] not in invalid]
    rows = []
    for r in runs:
        mm, mc, ms = model(r)
        rows.append({"run": r["dir"], "cond": r["cond"], "plan": r["plan"], "rep": r["rep"], "makespan_s": r["makespan_s"], "model_makespan_s": mm,
                     "completion": {d: round(v, 2) for d, v in r["completion_s"].items() if v is not None}, "model_completion": {d: round(v, 2) for d, v in mc.items() if v is not None},
                     "source_sinks": r["normalized"]["source_sinks"], "model_source_sinks": ms, "total_sinks": r["normalized"]["total_sinks"],
                     "egress_by_node": {k: round(v, 2) for k, v in r["normalized"]["egress_sinks_by_node"].items()}, "assignment": r["assignment"],
                     "pipelined": all(r["pipelined"].values()) if r["pipelined"] else None, "valid": r["dir"] not in invalid})
    with open(root / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
        for x in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in x.items()})
    G = defaultdict(list)
    for x in rows:
        if x["valid"]:
            G[(x["cond"], x["plan"])].append(x)
    cfg = {}
    for (c, p), xs in G.items():
        ms = [x["makespan_s"] for x in xs if x["makespan_s"] is not None]
        cfg[(c, p)] = {"cond": c, "plan": p, "n": len(xs), "makespan_median": st.median(ms) if len(ms) == len(xs) else None,
                       "makespan_min": min(ms) if ms else None, "makespan_max": max(ms) if ms else None, "model_makespan": xs[0]["model_makespan_s"],
                       "source_sinks": st.median(x["source_sinks"] for x in xs), "total_sinks": st.median(x["total_sinks"] for x in xs),
                       "completion_B": st.median(x["completion"].get("B", float("nan")) for x in xs), "completion_C": st.median(x["completion"].get("C", float("nan")) for x in xs),
                       "completion_D": st.median(x["completion"].get("D", float("nan")) for x in xs)}
    with open(root / "summary_by_config.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(next(iter(cfg.values())).keys())); w.writeheader(); w.writerows(sorted(cfg.values(), key=lambda x: (x["cond"], PLANS.index(x["plan"]))))
    def cond_key(c):   # uniform first, then slower forwarders, then slower source
        v = {k: float(x) for k, x in (kv.split("=") for kv in c.split("/"))}
        return (-v["Bs"], -v["Bf"], -v["Bin"])
    conds = sorted({c for c, _ in cfg}, key=cond_key)
    f = lambda v, d=1: "-" if v is None else f"{v:.{d}f}"  # noqa: E731
    out = [f"# Experiment B ({a.experiment}{' + ' + a.ref if a.ref else ''}), medians of valid runs", "",
           f"Valid runs {len(valid)}/{len(runs)}; invalid: {invalid or 'none'}; incomplete: {incomplete or 'none'}", "",
           "## Makespan (s) per condition and plan, measured / model; source Sinks in brackets", "",
           "| condition | " + " | ".join(LABEL[p] for p in PLANS) + " | best fixed | aware / best fixed |", "|---|" + "---|" * (len(PLANS) + 2)]
    best = {}; ratio = {}
    for c in conds:
        cells = []
        for p in PLANS:
            x = cfg.get((c, p))
            cells.append("-" if not x or x["makespan_median"] is None else f"{x['makespan_median']:.1f} / {f(x['model_makespan'])} [{x['source_sinks']:.2f}]")
        fx = [(cfg[(c, p)]["makespan_median"], p) for p in FIXED if (c, p) in cfg and cfg[(c, p)]["makespan_median"] is not None]
        if fx and (c, "aware") in cfg and cfg[(c, "aware")]["makespan_median"] is not None:
            bm, bp = min(fx); best[c] = (bp, bm); ratio[c] = cfg[(c, "aware")]["makespan_median"] / bm
            cells += [f"{LABEL[bp]} ({bm:.1f})", f"{ratio[c]:.2f}"]
        else:
            cells += ["-", "-"]
        out.append(f"| {c} | " + " | ".join(cells) + " |")
    out += ["", "## Verdicts over the tested conditions only (TOPOLOGY_PLAN F; the full-grid H6f stays open)", ""]
    m = lambda c, p: (cfg.get((c, p)) or {}).get("makespan_median")  # noqa: E731
    find = lambda **kw: next((c for c in conds if all(f"{k}={v:g}" in c for k, v in kw.items())), None)  # noqa: E731
    c500, c125, c250, cuni = find(Bf=500), find(Bf=125), find(Bs=250), find(Bs=1000, Bf=1000, Bin=1000)
    if len(best) >= 2:
        out.append(f"- H6a (best fixed plan differs across conditions): {'supported' if len({v[0] for v in best.values()}) > 1 else 'not supported'}: " + ", ".join(f"{c}: {LABEL[v[0]]}" for c, v in best.items()))
    if c250 and m(c250, "star"):
        ok = all(m(c250, p) is not None and m(c250, p) <= 0.5 * m(c250, "star") for p in ("line", "tree", "multipath"))
        out.append(f"- H6b (B_s = 250: every forwarding plan <= 0.5 x star): {'supported' if ok else 'not supported'} (star {f(m(c250, 'star'))}, line {f(m(c250, 'line'))}, tree {f(m(c250, 'tree'))}, multipath {f(m(c250, 'multipath'))})")
    if c125 and m(c125, "star"):
        ok = all(m(c125, p) is not None and m(c125, p) >= 2 * m(c125, "star") for p in ("line", "tree"))
        out.append(f"- H6c (B_f = 125: line and tree >= 2 x star): {'supported' if ok else 'not supported'} (star {f(m(c125, 'star'))}, line {f(m(c125, 'line'))}, tree {f(m(c125, 'tree'))})")
    if c500 and m(c500, "multipath") and m(c500, "line") and m(c500, "tree"):
        ok = m(c500, "multipath") <= 0.75 * m(c500, "line") and m(c500, "multipath") <= 0.5 * m(c500, "tree")
        out.append(f"- H6d (B_f = 500: multipath <= 0.75 x line and <= 0.5 x tree): {'supported' if ok else 'not supported'} (multipath {f(m(c500, 'multipath'))}, line {f(m(c500, 'line'))}, tree {f(m(c500, 'tree'))})")
    if cuni and m(cuni, "multipath") and m(cuni, "line"):
        out.append(f"- H6e (uniform: multipath within 1 s of line): {'supported' if abs(m(cuni, 'multipath') - m(cuni, 'line')) <= 1.0 else 'not supported'} ({f(m(cuni, 'multipath'))} vs {f(m(cuni, 'line'))})")
    if ratio:
        worst = max(ratio.values())
        out.append(f"- H6f over the tested subset (aware within 10 % of the best fixed plan in every tested condition): {'supported' if worst <= 1.10 else ('rejected' if worst > 1.25 else 'not supported')}; "
                   f"aware / best fixed = " + ", ".join(f"{c}: {v:.2f}" for c, v in ratio.items()) + ". Full grid: not tested.")
    out += ["", "## Model agreement", ""]
    errs = [abs(x["makespan_s"] - x["model_makespan_s"]) for x in rows if x["valid"] and x["makespan_s"] is not None and x["model_makespan_s"] is not None]
    serr = [abs(x["source_sinks"] - x["model_source_sinks"]) for x in rows if x["valid"]]
    out.append(f"- makespan: max |measured - model| = {max(errs):.2f} s (median {st.median(errs):.2f}); source Sinks: max {max(serr):.3f}")
    out += ["", "## Egress by node (Sinks) and assignment (fragments per link), medians / first rep", ""]
    for c in conds:
        for p in PLANS:
            xs = G.get((c, p))
            if xs:
                out.append(f"- {c} {p}: egress {xs[0]['egress_by_node']}, assignment {xs[0]['assignment']}, pipelined {xs[0]['pipelined']}")
    (root / "criteria.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    if a.no_figures or not conds:
        return
    import make_background_figures as bg
    import matplotlib.pyplot as plt
    import numpy as np
    bg.configure_matplotlib()
    col = {"star": bg.RED, "line": bg.BLUE, "tree": bg.DIMGRAY, "multipath": bg.ORANGE, "aware": "#2a9d3f"}
    fig = plt.figure(figsize=bg.FIG2A_SIZE); ax = fig.add_axes(bg.FIG2A_AXES)
    xs = np.arange(len(conds)); wdt = 0.16
    for i, p in enumerate(PLANS):
        vals = [(cfg.get((c, p)) or {}).get("makespan_median") or 0 for c in conds]
        ax.bar(xs + (i - 2) * wdt, vals, wdt, color=col[p], label=LABEL[p], edgecolor="black", linewidth=0.6)
    from matplotlib.ticker import FixedLocator, NullLocator, ScalarFormatter
    ax.set_yscale("log"); ax.set_ylim(8, 900)
    ax.yaxis.set_major_locator(FixedLocator([10, 20, 50, 100, 200, 500])); ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(ScalarFormatter()); ax.yaxis.get_major_formatter().set_scientific(False)
    ax.set_xticks(xs); ax.set_xticklabels([c.replace("Bs=", "S ").replace("/Bf=", "\nF ").replace("/Bin=1000", "") for c in conds], fontsize=bg.F2_ANNOT - 2)
    ax.set_ylabel("Makespan (s)", fontsize=bg.F2_LABEL); ax.tick_params(axis="y", labelsize=bg.F2_TICK - 4)
    ax.legend(ncol=5, frameon=False, prop={"size": bg.F2_ANNOT - 6, "family": bg.FONT_FAMILY}, loc="upper center", columnspacing=0.8, handlelength=1.2)
    bg.save(fig, root / "figures" / "figE10_makespan_by_condition", tight=False)


if __name__ == "__main__":
    main()
