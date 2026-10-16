#!/usr/bin/env python3
"""Aggregate Full Experiment E (results/evaluation/<experiment>/policy=*): four conditions x seven policies. Per
configuration: T_r at the final owner (median over sessions and reps), per-move restoration times, source / total /
unused Sinks per session, re-plans and switching costs, revisit metrics (fragments held at B on return), model
comparison; the frozen H8a / H8b / H8c verdicts (TOPOLOGY_PLAN F) and the Pareto frontier over (T_r, source, total)
per condition. Writes summary.csv, summary_by_config.csv, criteria.md.

    python tools/eval/aggregate_fulle.py --experiment restore_fulle
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

CTRL = 0.3
POL = ["restart", "pp_star", "fixed_line", "fixed_tree", "fixed_butterfly", "reuse_aware_in", "reuse_dyn"]
FWD = ["fixed_line", "fixed_tree", "fixed_butterfly"]


def cond_of(s, cfg):
    ev = cfg["args"].get("cap_events", "")
    if s["N"] == 4:
        return "2 shared source"
    if ev:
        return "3 C degradation"
    if s["moves"] == 3:
        return "4 revisit"
    if s["caps_mbps"]["B:out"] < s["caps_mbps"]["C:out"]:
        return "1 slow-B"
    return "other"


def model(s, cfg):
    caps = {}
    for k, v in s["caps_mbps"].items():
        node, d = k.split(":"); caps[(d, node)] = v * 1e6
    ev = cfg["args"].get("cap_events", "")
    for t, node, d, v in s["dyn"]["cap_changes"]:   # summary holds the final caps; the initial one is the default
        caps[(d, node)] = (cfg["args"]["holder_mbps"] or cfg["args"]["cap_mbps"]) * 1e6
    rm.SINK_BYTES = s["sink_bytes"]; rm.FLEN = s["frag_bytes"]; rm.NFR = -(-s["sink_bytes"] // s["frag_bytes"])
    m = rm.Model(s["policy"], s["N"], s["moves"], s["tm_s"], caps, cap_events=ev)
    r = m.run(horizon=600)
    trs = [r["restored_t"][sid] - r["move_t"][sid] + CTRL for sid in m.sids if r["restored_t"][sid] is not None and sid in r["move_t"]]
    return (st.median(trs) if len(trs) == s["N"] else None), r["source_per_session"], len(r["replans"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="restore_fulle")
    ap.add_argument("--allow_loopback", action="store_true")
    a = ap.parse_args()
    root = ROOT / "results/evaluation" / a.experiment
    runs = []
    for d in sorted(root.glob("policy=*")):
        if (d / "summary.json").exists():
            s = json.load(open(d / "summary.json")); s["dir"] = d.name
            s["cfg"] = json.load(open(d / "config.json")); s["cond"] = cond_of(s, s["cfg"])
            runs.append(s)
    skip = {"four_hosts_distinct", "nodes_same_commit"} if a.allow_loopback else set()
    invalid = [r["dir"] for r in runs if not all(v for k, v in r["validation"].items() if k not in skip)]
    rows = []
    for r in runs:
        sess = list(csv.DictReader(open(root / r["dir"] / "sessions.csv")))
        trs = [float(x["t_r_s"]) for x in sess if x.get("t_r_s")]
        evs = [json.loads(e["detail"]) | {"t_rel": float(e["t_rel"])} for e in csv.DictReader(open(root / r["dir"] / "events.csv")) if e["event"] in ("move", "restored")]
        moves = [e for e in evs if "to" in e]; rest = [e for e in evs if "edge" in e]
        # per-period restoration latency: restoration time at owner minus the move that made it owner (first period: from t0)
        per_move = []
        for sid in sorted({e["session"] for e in moves}):
            ms = [e for e in moves if e["session"] == sid]
            bounds = [0.0] + [e["t_rel"] for e in ms]
            for i, lo in enumerate(bounds):
                hi = bounds[i + 1] if i + 1 < len(bounds) else float("inf")
                rr = next((e["t_rel"] for e in rest if e["session"] == sid and lo - 1e-6 <= e["t_rel"] <= hi), None)
                per_move.append(None if rr is None else round(rr - lo, 2))
        revisit = [e for e in moves if e.get("revisit")]
        held_on_return = st.median([e["held_at_new"] for e in revisit]) / r["sink_bytes"] * r["frag_bytes"] if revisit else None
        mt, ms_, mr = model(r, r["cfg"])
        dy = r["dyn"]
        rows.append({"run": r["dir"], "cond": r["cond"], "policy": r["policy"], "N": r["N"], "moves": r["moves"], "rep": r["rep"],
                     "t_r_s": st.median(trs) if len(trs) == r["N"] else None, "model_t_r_s": mt, "makespan_s": r["makespan_s"], "restored": r["restored_sessions"],
                     "per_move_latency_s": per_move, "held_at_B_on_return": held_on_return,
                     "source_per_session": r["normalized"]["source_per_session"], "model_source": ms_, "total_per_session": r["normalized"]["total_per_session"],
                     "unused_per_session": r["normalized"]["unused_per_session"], "n_replans": dy["n_replans"], "model_replans": mr,
                     "transition_s": [x["transition_delay_s"] for x in dy["replans"]], "drained_mib": [round(x["drained_bytes"] / 2**20, 1) for x in dy["replans"]],
                     "duplicate_mib": dy["duplicate_bytes"] / 2**20, "valid": r["dir"] not in invalid})
    with open(root / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
        for x in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in x.items()})
    G = defaultdict(list)
    for x in rows:
        if x["valid"]:
            G[(x["cond"], x["policy"])].append(x)
    med = lambda xs, k: (st.median([x[k] for x in xs if x[k] is not None]) if any(x[k] is not None for x in xs) else None)  # noqa: E731
    cfg = {}
    for (c, p), xs in G.items():
        cfg[(c, p)] = {"cond": c, "policy": p, "n": len(xs), "t_r": med(xs, "t_r_s"), "t_r_min": min((x["t_r_s"] for x in xs if x["t_r_s"] is not None), default=None),
                       "t_r_max": max((x["t_r_s"] for x in xs if x["t_r_s"] is not None), default=None), "model_t_r": xs[0]["model_t_r_s"],
                       "restored_min": min(x["restored"] for x in xs), "source": med(xs, "source_per_session"), "model_source": xs[0]["model_source"],
                       "total": med(xs, "total_per_session"), "unused": med(xs, "unused_per_session"), "replans": med(xs, "n_replans"), "model_replans": xs[0]["model_replans"],
                       "held_at_B_on_return": med(xs, "held_at_B_on_return"), "per_move": xs[0]["per_move_latency_s"], "duplicate_mib": med(xs, "duplicate_mib")}
    with open(root / "summary_by_config.csv", "w", newline="") as fh:
        rows2 = sorted(cfg.values(), key=lambda x: (x["cond"], POL.index(x["policy"])))
        w = csv.DictWriter(fh, fieldnames=list(rows2[0].keys())); w.writeheader()
        for x in rows2:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in x.items()})
    conds = sorted({c for c, _ in cfg})
    f = lambda v, d=1: "-" if v is None else f"{v:.{d}f}"  # noqa: E731
    g = lambda c, p, k: (cfg.get((c, p)) or {}).get(k)  # noqa: E731
    out = [f"# Full Experiment E ({a.experiment}), medians of valid runs", "",
           f"Valid runs {len(runs) - len(invalid)}/{len(runs)}; invalid: {invalid or 'none'}", ""]
    for c in conds:
        out += [f"## {c}", "", "| policy | T_r final owner (s) | model | per-period latencies (rep 1) | source / S | model | total / S | unused / S | re-plans (model) | held at B on return | dup MiB |", "|---|" + "---|" * 10]
        for p in POL:
            x = cfg.get((c, p))
            if not x:
                continue
            out.append(f"| {p} | {f(x['t_r'])} ({f(x['t_r_min'])}-{f(x['t_r_max'])}) | {f(x['model_t_r'])} | {x['per_move']} | {f(x['source'], 2)} | {f(x['model_source'], 2)} | {f(x['total'], 2)} | {f(x['unused'], 2)} | "
                       f"{f(x['replans'], 0)} ({x['model_replans']}) | {f(x['held_at_B_on_return'], 2)} | {f(x['duplicate_mib'])} |")
        # Pareto frontier over (T_r, source, total): a policy is dominated if another is <= on all three and < on one
        pts = {p: (g(c, p, "t_r"), g(c, p, "source"), g(c, p, "total")) for p in POL if (c, p) in cfg and g(c, p, "t_r") is not None}
        # dominance with measurement tolerances (0.2 s, 0.01 Sink): equal policies do not dominate each other
        TOL = (0.2, 0.01, 0.01)
        dom = {}
        for p, v in pts.items():
            dom[p] = [q for q, w_ in pts.items() if q != p and all(w_[i] <= v[i] + TOL[i] for i in range(3)) and any(w_[i] < v[i] - TOL[i] for i in range(3))]
        front = [p for p in pts if not dom[p]]
        out += ["", f"Pareto frontier (T_r, source Sinks, total Sinks): {front}; dominated: " + ", ".join(f"{p} by {d}" for p, d in dom.items() if d) + "", ""]
    # frozen verdicts
    out += ["## Frozen verdicts (TOPOLOGY_PLAN F)", ""]
    c1 = next((c for c in conds if c.startswith("1")), None)
    if c1:
        aw = g(c1, "reuse_aware_in", "t_r"); best_fwd = min((g(c1, p, "t_r") for p in FWD if g(c1, p, "t_r") is not None), default=None); star = g(c1, "pp_star", "t_r")
        beaten = [p for p in FWD + ["pp_star"] if g(c1, p, "t_r") is not None and g(c1, p, "t_r") < aw - 1.0] if aw else []
        ok = aw is not None and best_fwd is not None and star is not None and aw <= 0.75 * best_fwd and abs(aw - star) <= 1.0 and not beaten
        out.append(f"- H8a (slow-B: aware-at-moves <= 0.75 x best fixed forwarding plan and within 1 s of star; no fixed plan beats it by > 1 s): "
                   f"{'supported' if ok else 'not supported'} (aware {f(aw)}, best forwarding {f(best_fwd)}, star {f(star)}, beaten by {beaten or 'none'})")
    c3 = next((c for c in conds if c.startswith("3")), None)
    if c3:
        aw, dy = g(c3, "reuse_aware_in", "t_r"), g(c3, "reuse_dyn", "t_r"); rp = g(c3, "reuse_dyn", "replans")
        worse = [c for c in conds if c != c3 and g(c, "reuse_dyn", "t_r") is not None and g(c, "reuse_aware_in", "t_r") is not None and g(c, "reuse_dyn", "t_r") > g(c, "reuse_aware_in", "t_r") + 1.0]
        ok = aw is not None and dy is not None and dy <= 0.5 * aw and rp is not None and rp <= 2 and not worse
        out.append(f"- H8b (C degradation: dynamic <= 0.5 x aware-at-moves with <= 2 re-plans; never worse than aware-at-moves by > 1 s elsewhere): "
                   f"{'supported' if ok else 'not supported'} (dynamic {f(dy)}, aware {f(aw)}, re-plans {f(rp, 0)}, worse in {worse or 'none'})")
    c2, c4 = next((c for c in conds if c.startswith("2")), None), next((c for c in conds if c.startswith("4")), None)
    h8c = []
    for c in (c2, c4):
        if not c:
            continue
        rs = g(c, "restart", "source")
        pa = [p for p in POL if p != "restart" and (c, p) in cfg]
        fewer = all(g(c, p, "source") is not None and g(c, p, "source") <= rs - 0.25 for p in pa) if rs is not None else False
        pts = {p: (g(c, p, "t_r"), g(c, p, "source"), g(c, p, "total")) for p in POL if (c, p) in cfg and g(c, p, "t_r") is not None}
        rv = pts.get("restart")
        TOL = (0.2, 0.01, 0.01)
        dominated_by_restart = [p for p, v in pts.items() if p != "restart" and rv and all(rv[i] <= v[i] + TOL[i] for i in range(3)) and any(rv[i] < v[i] - TOL[i] for i in range(3))]
        h8c.append((c, fewer, dominated_by_restart, rs))
    if h8c:
        ok = all(fw and not dr for _, fw, dr, _ in h8c)
        out.append(f"- H8c (shared-source and revisit: every progress-aware policy sends >= 0.25 Sink less from the source than restart and none is Pareto-dominated by restart): "
                   f"{'supported' if ok else 'not supported'} (" + "; ".join(f"{c}: restart {f(rs, 2)} S, fewer-by-0.25 {fw}, dominated by restart {dr or 'none'}" for c, fw, dr, rs in h8c) + ")")
    errs = [abs(x["t_r_s"] - x["model_t_r_s"]) for x in rows if x["valid"] and x["t_r_s"] is not None and x["model_t_r_s"] is not None]
    out += ["", "## Model agreement", "", f"- T_r: max |measured - model| = {max(errs):.2f} s (median {st.median(errs):.2f}) over {len(errs)} runs"]
    (root / "criteria.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
