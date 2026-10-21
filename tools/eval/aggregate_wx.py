#!/usr/bin/env python3
"""Experiment WX verdicts (results/evaluation/osdi/expWX/preregistration.md, frozen a181126).

Imported frozen hypotheses evaluated per workload with their frozen code paths and thresholds:
R-H1 / R-H2 / R-H3(a) (aggregate_wrn.agg_r, c = 0) on X1 (rho 1), X2 (rho 4), X3 (rho 2); M3E H4 (X3), H1 (X4), H2 (X5),
H3 (X6), H6 / H7 per configuration on X3-X6 (aggregate_m3e). Dog = the frozen R / M3E verdicts (read, not recomputed).
Generality: "supported on k of 4 tested inputs" per hypothesis and configuration.

    python tools/eval/aggregate_wx.py [--dry]   # -> results/evaluation/osdi/expWX/wx_results.{md,json}
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from aggregate_m3e import extra  # noqa: E402
from aggregate_wrn import NE, NOT, SUP, Val, absdiff_le, cmedian, diff_le, discarded_sinks, le, ratio_le, runs_in, valid_reps, verdict  # noqa: E402

WL = {"bfly": "butterfly-feeding-slow-motion", "audi": "audi-snow-trail", "train": "train"}
CFG = {"X1": (("restart", "split"), False, 1.0), "X2": (("restart", "split"), False, 4.0), "X3": (("restart", "split", "reuse_dyn2"), False, 2.0),
       "X4": (("restart", "split", "reuse_dyn2"), False, 2.0), "X5": (("restart", "split", "reuse_dyn2", "reuse_aware_in"), True, 2.0),
       "X6": (("split", "reuse_dyn2"), True, 2.0)}
DOG_R = {"X1": "rho=1,c=0", "X2": "rho=4,c=0", "X3": "rho=2,c=0"}
DOG_M3E = {"X3": ["H4"], "X4": ["H1"], "X5": ["H2"], "X6": ["H3"]}


def group(exp, pols, cap, dry):
    runs = runs_in(exp, dry)
    out = {}
    for p in pols:
        rs = [r for r in runs if r["policy"] == p]
        v, inap = valid_reps(rs)
        if cap:
            v = [r for r in v if extra(r)["cap_fired"] >= 1]
        for r in v:
            r["x"] = extra(r); r["discarded"] = discarded_sinks(r["dir"], r["s"])
        out[p] = {"runs": v, "n_valid": len(v), "n_all": len(rs), "n_inapplicable": inap, "invalid": [(r["dir"].name, r["why"]) for r in rs if not r["valid"]]}
    return out


def med(g, f):
    return cmedian([f(r) if isinstance(f(r), Val) else Val(f(r)) for r in g["runs"]])


def mm(g, f):
    v = [f(r) for r in g["runs"] if f(r) is not None]
    return st.median(v) if v else None


def three(G, *ps):
    return all(G[p]["n_valid"] >= 3 for p in ps)


def r_hyps(G, rho):
    """Frozen R rules at c = 0 (aggregate_wrn.agg_r)."""
    if not three(G, "restart", "split"):
        ne = f"{NE} (fewer than 3 valid applicable reps)"
        return {"R-H1": ne, "R-H2": ne, "R-H3(a)": ne}, None
    m1s, m2s = med(G["restart"], lambda r: r["B_source"]), med(G["split"], lambda r: r["B_source"])
    R1, R2 = m1s.x - 1, m2s.x - 1
    red = None if R1 < 0.10 else 1 - R2 / R1
    h1 = f"{NE} (R(M1 only) = {R1:.3f} < 0.10)" if red is None else verdict(m2s.x <= 1.10 and red >= 0.75) + f" (B_src {m1s} / {m2s}, reduction {red:.1%})"
    d1, d2 = med(G["restart"], lambda r: r["discarded"]), med(G["split"], lambda r: r["discarded"])
    h2 = verdict(d2.x <= 0.10) + f" (discarded M1+M2 {d2}, M1 only {d1})"
    b1, b2 = med(G["restart"], lambda r: r["bind"]), med(G["split"], lambda r: r["bind"])
    h3 = verdict(absdiff_le(b2, b1, 1.0)) + f" (bind {b2} vs {b1})"
    manip = None
    if rho in (2.0, 4.0):
        manip = ("MET" if d1.x >= 0.75 * 2 / rho else "NOT MET") + f" (M1 only discarded {d1} vs {0.75 * 2 / rho:.3f})"
    return {"R-H1": h1, "R-H2": h2, "R-H3(a)": h3}, manip


def m3e_hyp(x, G):
    """Frozen M3E rules (aggregate_m3e) for the scenario X replicates."""
    bind = lambda r: r["bind"]  # noqa: E731
    src = lambda r: r["B_source"]  # noqa: E731
    out, note = {}, None
    if x == "X4":
        if three(G, "restart", "split", "reuse_dyn2"):
            v3, v1, v2 = med(G["reuse_dyn2"], bind), med(G["restart"], bind), med(G["split"], bind)
            c1, c2, c3 = diff_le(v3, v1, -3.5), diff_le(v3, v2, 1.0), le(med(G["reuse_dyn2"], src), med(G["split"], src).x + 0.05)
            out["H1"] = verdict(None if None in (c1, c2, c3) else (c1 and c2 and c3))
        else:
            out["H1"] = f"{NE} (< 3 valid reps)"
    if x == "X5":
        if three(G, "split", "reuse_dyn2", "reuse_aware_in"):
            v = G["reuse_dyn2"]
            c1, c2 = ratio_le(med(v, bind), med(G["reuse_aware_in"], bind), 0.5), ratio_le(med(v, bind), med(G["split"], bind), 0.5)
            per = all(r["replans"] <= 2 and r["x"]["probes"] <= 1 and r["x"]["probe_frags_max"] <= 4 and r["x"]["dup_bytes"] == 0 for r in v["runs"])
            c3 = le(med(v, src), 1.35)
            out["H2"] = verdict(None if None in (c1, c2, c3) else (c1 and c2 and c3 and per))
            if G["restart"]["n_valid"] >= 3:
                r1 = med(G["restart"], src).x - 1
                note = {"M1_only_redundant_sinks": r1, "M3v2_redundant_sinks": med(v, src).x - 1,
                        "fraction_removed": None if r1 <= 0 else 1 - (med(v, src).x - 1) / r1}
        else:
            out["H2"] = f"{NE} (< 3 valid reps or cap event not fired)"
    if x in ("X6",):
        if three(G, "split", "reuse_dyn2"):
            v = G["reuse_dyn2"]
            per = all(r["x"]["full_replans"] == 0 and r["x"]["probes"] <= 1 for r in v["runs"])
            c1, c2 = diff_le(med(v, bind), med(G["split"], bind), 1.0), le(med(v, src), med(G["split"], src).x + 0.02)
            out["H3"] = verdict(None if None in (c1, c2) else (per and c1 and c2))
        else:
            out["H3"] = f"{NE} (< 3 valid reps or cap event not fired)"
    if x == "X3":
        if three(G, "split", "reuse_dyn2"):
            v = G["reuse_dyn2"]
            per = all(r["replans"] == 0 for r in v["runs"])
            c1, c2 = absdiff_le(med(v, bind), med(G["split"], bind), 1.0), le(med(v, src), med(G["split"], src).x + 0.01)
            out["H4"] = verdict(None if None in (c1, c2) else (per and c1 and c2))
        else:
            out["H4"] = f"{NE} (< 3 valid reps)"
    if x in ("X3", "X4", "X5", "X6"):
        if three(G, "split", "reuse_dyn2"):
            t3, t2 = mm(G["reuse_dyn2"], lambda r: r["x"]["ttfo"]), mm(G["split"], lambda r: r["x"]["ttfo"])
            c3, c2 = mm(G["reuse_dyn2"], lambda r: r["x"]["chunk_s_move_to_bind"]), mm(G["split"], lambda r: r["x"]["chunk_s_move_to_bind"])
            out["H6"] = verdict(None if None in (t3, t2) else t3 <= t2 + 0.2)
            out["H7"] = verdict(None if None in (c3, c2) else abs(c3 - c2) <= 0.02 * c2)
        else:
            out["H6"] = out["H7"] = f"{NE} (< 3 valid reps)"
    return out, note


def dog_verdicts():
    wrn = json.load(open(ROOT / "results/evaluation/osdi/wrn_results.json"))["R"]["cells"]
    m3e = json.load(open(ROOT / "results/evaluation/osdi/expM3E/m3e_results.json"))
    out = {}
    for x, cell in DOG_R.items():
        for h in ("R-H1", "R-H2", "R-H3(a)"):
            out[(x, h)] = wrn[cell][h].split(" (")[0]
    for x, hs in DOG_M3E.items():
        for h in hs:
            out[(x, h)] = m3e["hypotheses"][h].split(" (")[0]
    for h in ("H6", "H7"):
        by = m3e.get(f"{h.lower()}_by_scenario") or {}
        for x, sc in (("X3", "S4"), ("X4", "S1"), ("X5", "S2"), ("X6", "S3")):
            out[(x, h)] = SUP if by.get(sc) is True else (NOT if by.get(sc) is False else NE)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    res, notes, tables = {}, {}, {}
    for ws in WL:
        for x, (pols, cap, rho) in CFG.items():
            G = group(f"expWX_{ws}_{x}", pols, cap, a.dry)
            h = {}
            if x in ("X1", "X2", "X3"):
                rh, manip = r_hyps(G, rho)
                h.update(rh)
                if manip:
                    notes[(ws, x, "manipulation_check")] = manip
            mh, note = m3e_hyp(x, G)
            h.update(mh)
            if note:
                notes[(ws, x, "H2_source_rationale")] = note
            res[(ws, x)] = h
            tables[(ws, x)] = {p: {"valid": g["n_valid"], "all": g["n_all"], "inapplicable": g["n_inapplicable"], "invalid": g["invalid"],
                                   "bind": repr(med(g, lambda r: r["bind"])) if g["runs"] else None, "B_source": mm(g, lambda r: r["B_source"]),
                                   "discarded": mm(g, lambda r: r["discarded"]), "replans": [r["replans"] for r in g["runs"]], "probes": [r["x"]["probes"] for r in g["runs"]],
                                   "ttfo": mm(g, lambda r: r["x"]["ttfo"])} for p, g in G.items()}
    dog = dog_verdicts()
    hyps = [(x, h) for x in CFG for h in (("R-H1", "R-H2", "R-H3(a)") if x in ("X1", "X2", "X3") else ()) + tuple(DOG_M3E.get(x, ())) + (("H6", "H7") if x in ("X3", "X4", "X5", "X6") else ())]
    L = [f"# WX verdicts{' (DRY RUN: loopback, not meaningful)' if a.dry else ''} (frozen preregistration a181126)", "",
         "Per workload, imported frozen hypotheses; dog = frozen R / M3E verdicts. Generality: supported on k of 4 tested inputs (seed 0, one model).", "",
         "| config | hypothesis | dog (frozen) | butterfly | audi-snow-trail | train | supported on |", "|---|---|---|---|---|---|---|"]
    gen = {}
    for x, h in hyps:
        cells = [dog.get((x, h), NE)] + [res[(ws, x)].get(h, NE) for ws in WL]
        k = sum(1 for c in cells if c.startswith(SUP))
        gen[f"{x} {h}"] = {"dog": cells[0], **{WL[ws]: res[(ws, x)].get(h) for ws in WL}, "supported_on": k}
        short = lambda c: c if len(c) < 60 else c[:57] + "..."  # noqa: E731
        L.append(f"| {x} | {h} | {short(cells[0])} | " + " | ".join(short(c) for c in cells[1:]) + f" | {k} / 4 |")
    L += ["", "Notes (descriptive):"] + [f"- {ws} {x} {k}: {v}" for (ws, x, k), v in notes.items()]
    out = {"dry": a.dry, "generality": gen, "per_workload": {f"{ws} {x}": v for (ws, x), v in res.items()}, "notes": {f"{ws} {x} {k}": v for (ws, x, k), v in notes.items()},
           "tables": {f"{ws} {x}": v for (ws, x), v in tables.items()}}
    od = ROOT / "results/evaluation/osdi/expWX"
    stem = "_dryrun_wx_results" if a.dry else "wx_results"
    (od / f"{stem}.json").write_text(json.dumps(out, indent=1, default=str))
    (od / f"{stem}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
