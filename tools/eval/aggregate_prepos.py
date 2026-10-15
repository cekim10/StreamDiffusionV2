#!/usr/bin/env python3
"""Aggregate Experiment A (pre-positioning) runs under results/evaluation/<experiment>/policy=*_pp=* and compare them
with the fluid model run at each configuration's own caps. Writes summary.csv (per run), summary_by_config.csv
(medians per pre-positioning policy x true destination), criteria.md (pilot go/no-go: T_r and verified bytes within
1 s / 0.05 Sink of the model; forwarding by non-owner holders exercised in every incorrect-prediction run that had
pre-positioned bytes; source bytes never above 1 Sink + one fragment per candidate flow).

    python tools/eval/aggregate_prepos.py --experiment restore_prepos_pilot
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
sys.path.insert(0, str(ROOT / "tools" / "eval"))
import restore_model as rm  # noqa: E402

CTRL = 0.3   # control-plane seconds added to model T_r (TOPOLOGY_PLAN D)


def load(root: Path):
    runs, incomplete = [], []
    for d in sorted(root.glob("policy=*")):
        if not (d / "summary.json").exists():
            incomplete.append(d.name); continue
        s = json.load(open(d / "summary.json")); s["dir"] = d.name
        if s.get("prepos"):
            runs.append(s)
    return runs, incomplete


def model_tr(s):
    """Fluid-model T_r and verified-at-move allocation for this run's configuration (its caps, Sink size, probs)."""
    pp = s["prepos"]
    caps = {}
    for k, v in s["caps_mbps"].items():
        node, d = k.split(":"); caps[(d, node)] = v * 1e6
    rm.SINK_BYTES = s["sink_bytes"]; rm.FLEN = s["frag_bytes"]; rm.NFR = -(-s["sink_bytes"] // s["frag_bytes"])
    os_ = pp.get("others_start", 0.0) or 0.0
    m = rm.Model(s["policy"], s["N"], 1, s["tm_s"], caps, prepos={"policy": pp["policy"], "probs": pp["probs"], "L": pp["L"], "b": pp["b"],
                                                                 "dest": pp["dest"], "tau": pp["tau"], "others_start": os_})
    r = m.run(horizon=pp["L"] + os_ + 8 * s["N"] * s["sink_bytes"] * 8 / min(caps[("in", "B")], caps[("out", "B")]) + 30)
    om = r.get("others_makespan"); om = None if om is None else om + CTRL
    return (None if r["t_r"] is None else r["t_r"] + CTRL), r["held_at_move"], om   # realized (verified at the move), not assigned


def a3_verdicts(cfg):
    """Frozen H5d / H5e (TOPOLOGY_PLAN.md F): judged on medians; model values shown beside each."""
    TS = 14.05
    R = {(c["N"], c["policy"], c["holder_mbps"], c["others_start"], c["prepos"], c["dest"]): c for c in cfg}
    g = lambda *k: R.get(k)  # noqa: E731
    f = lambda v: "-" if v is None else f"{v:.1f}"  # noqa: E731
    out = ["", "## A3: frozen criteria (medians; model value in brackets)", "",
           "| clause | configuration | measured | model | threshold | verdict |", "|---|---|---|---|---|---|"]
    def row(name, cfgtxt, meas, mod, thr_txt, ok):
        out.append(f"| {name} | {cfgtxt} | {f(meas)} | {f(mod)} | {thr_txt} | {'-' if ok is None else ('PASS' if ok else 'FAIL')} |")
    # H5d main: others' makespan with top-1 pre-positioning (others at t0) minus none
    a_, b_ = g(4, "reuse_aware_in", 1000.0, 0.0, "none", "B"), g(4, "reuse_aware_in", 1000.0, 0.0, "top1", "B")
    if a_ and b_ and a_["others_makespan_median"] is not None and b_["others_makespan_median"] is not None:
        d = b_["others_makespan_median"] - a_["others_makespan_median"]; dm = (b_["model_others_makespan"] or 0) - (a_["model_others_makespan"] or 0)
        row("H5d interference", "N=4, others at t0: others' makespan top-1(0.5) - none", d, dm, ">= 3.5 s", d >= 3.5)
    # H5d idle clause: others start at L (pre-positioning finished before)
    a_, b_ = g(4, "reuse_aware_in", 1000.0, 10.0, "none", "C"), g(4, "reuse_aware_in", 1000.0, 10.0, "top1", "C")
    if a_ and b_ and a_["others_makespan_median"] is not None and b_["others_makespan_median"] is not None:
        d = b_["others_makespan_median"] - a_["others_makespan_median"]; dm = (b_["model_others_makespan"] or 0) - (a_["model_others_makespan"] or 0)
        row("H5d idle source", "N=4, others at L: others' makespan top-1(0.5) - none", d, dm, "< 1 s", d < 1.0)
        d = a_["t_r_median"] - b_["t_r_median"]; dm = a_["model_t_r"] - b_["model_t_r"]
        row("H5e shared source", "N=4, 1 Gbps holders, others at L: T_r none - top-1 -> C (wrong)", d, dm, f">= 0.5 T_s = {0.5 * TS:.1f} s", d >= 0.5 * TS)
    a_, b_ = g(1, "reuse_aware_in", 1000.0, 0.0, "none", "C"), g(1, "reuse_aware_in", 1000.0, 0.0, "top1", "C")
    if a_ and b_:
        d = a_["t_r_median"] - b_["t_r_median"]; dm = a_["model_t_r"] - b_["model_t_r"]
        row("H5e ingress-bound", "N=1: T_r none - top-1 -> C (wrong)", d, dm, "|d| < 1 s", abs(d) < 1.0)
    for pol, thr_txt, test in (("reuse_fixed", "< 1 s", lambda d: d < 1.0), ("reuse_aware_in", f">= 0.5 T_s = {0.5 * TS:.1f} s", lambda d: d >= 0.5 * TS)):
        a_, b_ = g(4, pol, 125.0, 10.0, "none", "C"), g(4, pol, 125.0, 10.0, "top1", "C")
        if a_ and b_:
            d = a_["t_r_median"] - b_["t_r_median"]; dm = a_["model_t_r"] - b_["model_t_r"]
            row(f"H5e slow holder, {pol}", "N=4, 125 Mbps holders, others at L: T_r none - top-1 -> C (wrong)", d, dm, thr_txt, test(d))
    return out


def diag_table(cfg):
    """Holder-bandwidth diagnostic: per holder egress, T_r with the wrongly placed 0.5 Sink vs none, for both policies."""
    R = {(c["policy"], c["holder_mbps"], c["prepos"]): c for c in cfg if c["N"] == 4 and c["dest"] == "C"}
    bhs = sorted({k[1] for k in R})
    f = lambda v: "-" if v is None else f"{v:.1f}"  # noqa: E731
    out = ["", "## Holder-bandwidth diagnostic (N = 4, others start at L, 0.5 Sink at B, destination C; medians)", "",
           "| B_h (Mbps) | fixed: none / top-1 T_r | fixed gain | fixed model gain | aware_in: none / top-1 T_r | aware_in gain | aware_in model gain | provider split for the 0.5 Sink, aware_in (B fwd / A resend) | source Sinks fixed / aware_in | total Sinks fixed / aware_in | others' makespan none / fixed / aware_in |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    cross = {"reuse_fixed": None, "reuse_aware_in": None}
    for bh in bhs:
        nf, tf, na, ta = (R.get(("reuse_fixed", bh, "none")), R.get(("reuse_fixed", bh, "top1")), R.get(("reuse_aware_in", bh, "none")), R.get(("reuse_aware_in", bh, "top1")))
        if not (nf and tf and na and ta):
            continue
        gf, ga = nf["t_r_median"] - tf["t_r_median"], na["t_r_median"] - ta["t_r_median"]
        gfm, gam = nf["model_t_r"] - tf["model_t_r"], na["model_t_r"] - ta["model_t_r"]
        if gf > 0 and cross["reuse_fixed"] is None:
            cross["reuse_fixed"] = bh
        if ga > 0 and cross["reuse_aware_in"] is None:
            cross["reuse_aware_in"] = bh
        out.append(f"| {bh:g} | {f(nf['t_r_median'])} / {f(tf['t_r_median'])} | {gf:+.1f} | {gfm:+.1f} | {f(na['t_r_median'])} / {f(ta['t_r_median'])} | {ga:+.1f} | {gam:+.1f} | "
                   f"{ta['fwd_nonowner']:.2f} / {ta['post_move_source'] - 0.5:.2f} | {tf['source_total']:.2f} / {ta['source_total']:.2f} | {tf['total']:.2f} / {ta['total']:.2f} | "
                   f"{f(nf['others_makespan_median'])} / {f(tf['others_makespan_median'])} / {f(ta['others_makespan_median'])} |")
    out += ["", f"Lowest holder egress in the grid at which the wrongly placed Sink helps: fixed {cross['reuse_fixed']}, aware_in {cross['reuse_aware_in']} Mbps "
            "(the analytical crossover for fixed forwarding is B_h = x B_s / (N (1 - x)) = 250 Mbps for x = 0.5, N = 4; aware_in should never be worse than none)."]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="restore_prepos_pilot")
    ap.add_argument("--allow_loopback", action="store_true")
    ap.add_argument("--diag", action="store_true", help="holder-bandwidth diagnostic table (gain of a wrongly placed 0.5 Sink vs holder egress, fixed vs aware_in)")
    ap.add_argument("--a3", action="store_true", help="apply the frozen H5d / H5e criteria (TOPOLOGY_PLAN F) to the A3 grid")
    ap.add_argument("--ts", type=float, default=14.05, help="T_s used for the 0.5 T_s threshold (measured, 1 Gbps)")
    a = ap.parse_args()
    root = ROOT / "results/evaluation" / a.experiment
    runs, incomplete = load(root)
    skip = {"four_hosts_distinct"} if a.allow_loopback else set()
    invalid = [r["dir"] for r in runs if not all(v for k, v in r["validation"].items() if k not in skip)]
    S = runs[0]["sink_bytes"]
    rows = []
    for r in runs:
        pp = r["prepos"]; mt, alloc, mom = model_tr(r)
        rows.append({"run": r["dir"], "prepos": pp["policy"], "dest": pp["dest"], "correct": pp["correct"], "draw": pp["draw"], "rep": r["rep"],
                     "N": r["N"], "policy": r["policy"], "holder_mbps": r["caps_mbps"]["B:out"], "in_mbps": r["caps_mbps"]["B:in"], "others_start": pp.get("others_start", 0.0) or 0.0,
                     "others_makespan_s": pp.get("others_makespan_s"), "model_others_makespan_s": mom,
                     "L_s": pp["L"], "budget_sinks": pp["b"], "t_r_s": pp["t_r_s"], "model_t_r_s": mt,
                     "verified_at_move": {c: round(v, 3) for c, v in pp["verified_at_move_sinks"].items()},
                     "model_alloc": {c: round(v, 3) for c, v in alloc.items()},
                     "at_chosen": pp["at_chosen_sinks"], "at_nonchosen": pp["at_nonchosen_sinks"],
                     "post_move_source": pp["post_move_source_sinks"], "fwd_nonowner": pp["forwarded_by_nonowner_holders_sinks"],
                     "source_total": r["normalized"]["source_per_session"], "total": r["normalized"]["total_per_session"],
                     "valid": r["dir"] not in invalid})
    with open(root / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
        for x in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in x.items()})
    G = defaultdict(list)
    for x in rows:
        if x["valid"]:
            G[(x["N"], x["policy"], x["holder_mbps"], x["others_start"], x["prepos"], x["dest"])].append(x)
    cfg = []
    for (n_, pol, bh, os_, p, d), xs in sorted(G.items()):
        om = [x["others_makespan_s"] for x in xs if x["others_makespan_s"] is not None]
        cfg.append({"N": n_, "policy": pol, "holder_mbps": bh, "others_start": os_, "prepos": p, "dest": d, "n": len(xs),
                    "t_r_median": st.median(x["t_r_s"] for x in xs), "model_t_r": xs[0]["model_t_r_s"],
                    "others_makespan_median": st.median(om) if om else None, "model_others_makespan": xs[0]["model_others_makespan_s"],
                    "at_chosen": st.median(x["at_chosen"] for x in xs), "at_nonchosen": st.median(x["at_nonchosen"] for x in xs),
                    "fwd_nonowner": st.median(x["fwd_nonowner"] for x in xs), "post_move_source": st.median(x["post_move_source"] for x in xs),
                    "source_total": st.median(x["source_total"] for x in xs), "total": st.median(x["total"] for x in xs)})
    with open(root / "summary_by_config.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cfg[0].keys())); w.writeheader(); w.writerows(cfg)
    f = lambda v, d=2: "-" if v is None else f"{v:.{d}f}"  # noqa: E731
    out = [f"# Experiment A pilot checks ({a.experiment})", "",
           f"Valid runs {len(runs) - len(invalid)}/{len(runs)}; invalid: {invalid or 'none'}; incomplete: {incomplete or 'none'}", "",
           "## Per run: T_r (move -> all fragments verified at the destination) vs the fluid model at the run's caps", "",
           "| prepos | dest | correct | T_r s | model s | d | verified at move (Sinks) | model verified | at chosen | at non-chosen | fwd by non-owner holders | post-move source | source total | total |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    fails = []
    for x in rows:
        d = None if x["t_r_s"] is None or x["model_t_r_s"] is None else x["t_r_s"] - x["model_t_r_s"]
        va = " ".join(f"{c}:{v:.2f}" for c, v in x["verified_at_move"].items()); ma = " ".join(f"{c}:{v:.2f}" for c, v in x["model_alloc"].items())
        out.append(f"| {x['prepos']} | {x['dest']} | {x['correct']} | {f(x['t_r_s'])} | {f(x['model_t_r_s'])} | {'-' if d is None else f'{d:+.2f}'} | {va} | {ma} | "
                   f"{f(x['at_chosen'])} | {f(x['at_nonchosen'])} | {f(x['fwd_nonowner'])} | {f(x['post_move_source'])} | {f(x['source_total'])} | {f(x['total'])} |")
        # model-agreement checks (pilot go/no-go, TOPOLOGY_PLAN G step 2); the forwarding and 1-Sink checks apply to fast
        # holders only: with a slow holder the aware rule deliberately moves fragments back to the source
        if d is None or abs(d) > 1.0:
            fails.append((x["run"], f"T_r off model by {d}"))
        for c, v in x["verified_at_move"].items():
            if abs(v - x["model_alloc"][c]) > 0.05:
                fails.append((x["run"], f"verified at {c} {v:.3f} vs model {x['model_alloc'][c]:.3f}"))
        fast = x["holder_mbps"] >= x.get("in_mbps", 1000.0)
        if fast and x["at_nonchosen"] > 0.02 and x["fwd_nonowner"] < 0.5 * x["at_nonchosen"]:
            fails.append((x["run"], f"non-chosen holders forwarded only {x['fwd_nonowner']:.2f} of {x['at_nonchosen']:.2f} Sink"))
        if fast and x["source_total"] > 1.0 + 3 * runs[0]["frag_bytes"] / S + 0.01:
            fails.append((x["run"], f"source total {x['source_total']:.3f} > 1 Sink"))
    out += ["", "## Model agreement (T_r and verified bytes at the move within 1 s / 0.05 Sink of the fluid model; with fast holders: non-chosen holders forward, source <= 1 Sink)", ""]
    out += [f"- FAIL {r}: {m}" for r, m in fails] or ["- all checks pass: GO"]
    if a.a3:
        out += a3_verdicts(cfg)
    if a.diag:
        out += diag_table(cfg)
    (root / "criteria.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
