#!/usr/bin/env python3
"""M3-S1 report (osdi/m3s1/preregistration.md section 5): medians over valid reps per (workload, rho, policy, order),
rules R1-R5 as written, comparison with the pre-run predictions (s0_predictions.json).

    python tools/eval/m3s1_report.py [--experiment expM3S1]
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/evaluation/osdi/m3s1"
KEYS = ("remote_s", "local_s", "n_cancelled", "final_completed")
BKEYS = ("total", "discarded", "staged", "wasted_staged", "source_bytes_final_base")


def load(exp: str):
    runs = defaultdict(list)
    for d in sorted((ROOT / "results/evaluation" / exp).glob("policy=*")):
        f = d / "summary.json"
        if not f.exists():
            continue
        s = json.load(open(f))
        valid = all(s["validation"].values())
        key = (s["workload"], float(s["rho"]), s["staging"], s["order"])
        fin = next((m for m in reversed(s["migrations"]) if m["outcome"] == "completed"), None)
        runs[key].append({"run": d.name, "rep": s["rep"], "valid": valid, "why": [k for k, v in s["validation"].items() if not v], **{k: s[k] for k in KEYS},
                          **{f"bytes_{k}": s["bytes"][k] for k in BKEYS}, "final_valid": fin and fin["valid"], "final_ready_s": fin and fin.get("readiness_s"),
                          "final_base_mb": fin and fin["base_bytes"] / 1e6, "migrations": s["migrations"]})
    return runs


def med(rows, k):
    xs = [r[k] for r in rows if r.get(k) is not None]
    return st.median(xs) if xs else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--experiment", default="expM3S1"); a = ap.parse_args()
    runs = load(a.experiment)
    pred = json.load(open(OUT / "s0_predictions.json"))["predictions"] if (OUT / "s0_predictions.json").exists() else {}
    agg = {}
    for key, rows in runs.items():
        ok = [r for r in rows if r["valid"]]
        agg[key] = {"n_runs": len(rows), "n_valid": len(ok), "invalid": [(r["run"], r["why"]) for r in rows if not r["valid"]],
                    **{k: med(ok, k) for k in ("remote_s", "local_s", "final_ready_s", "final_valid", "final_base_mb")},
                    **{f"{k}_mb": (med(ok, f"bytes_{k}") or 0) / 1e6 for k in BKEYS},
                    "n_cancelled": med(ok, "n_cancelled"), "final_completed_all": all(r["final_completed"] for r in ok) if ok else None}
    rep = {"experiment": a.experiment, "cells": {}, "rules": {}}
    def cell(wl, rho, stg, order="fwd"):
        return agg.get((wl, rho, stg, order))
    R1, R2, R3, R4 = {}, {}, {}, {}
    for wl in ("dog", "bfly"):
        rho = 1.0
        s0 = cell(wl, rho, "none")
        if not s0 or not s0["n_valid"]:
            continue
        S3 = {o: cell(wl, rho, "S3", o) for o in ("fwd", "rev")}
        S2 = {o: cell(wl, rho, "S2", o) for o in ("fwd", "rev")}
        S1c = {o: cell(wl, rho, "S1c", o) for o in ("fwd", "rev")}
        S1o = cell(wl, rho, "S1o")
        s3 = [c for c in S3.values() if c and c["n_valid"]]
        r1 = {o: {"remote_ratio": c["remote_s"] / s0["remote_s"], "total_ratio": c["total_mb"] / s0["total_mb"], "pass": c["remote_s"] <= 0.80 * s0["remote_s"] and c["total_mb"] <= 1.30 * s0["total_mb"]}
              for o, c in S3.items() if c and c["n_valid"]}
        R1[wl] = {"per_order": r1, "pass": bool(r1) and all(v["pass"] for v in r1.values())}
        worst_s1c = max((c["remote_s"] for c in S1c.values() if c and c["n_valid"]), default=None)
        best_s3 = min((c["remote_s"] for c in s3), default=None)
        R2[wl] = {"S1o_remote_ratio": S1o and S1o["n_valid"] and S1o["remote_s"] / s0["remote_s"], "S1c_remote_ratio": {o: c and c["n_valid"] and c["remote_s"] / s0["remote_s"] for o, c in S1c.items()},
                  "S2_remote_ratio": {o: c and c["n_valid"] and c["remote_s"] / s0["remote_s"] for o, c in S2.items()}, "S3_remote_ratio": {o: c and c["n_valid"] and c["remote_s"] / s0["remote_s"] for o, c in S3.items()},
                  "total_ratio": {k: {o: c and c["n_valid"] and c["total_mb"] / s0["total_mb"] for o, c in D.items()} for k, D in (("S1c", S1c), ("S2", S2), ("S3", S3))},
                  "wasted_mb": {k: {o: c and c["n_valid"] and c["wasted_staged_mb"] for o, c in D.items()} for k, D in (("S1c", S1c), ("S2", S2), ("S3", S3))},
                  "one_candidate_suffices": (worst_s1c is not None and best_s3 is not None and worst_s1c <= 1.10 * best_s3)}
        R3[wl] = {k: (abs(D["fwd"]["remote_s"] - D["rev"]["remote_s"]) / s0["remote_s"] if all(D[o] and D[o]["n_valid"] for o in ("fwd", "rev")) else None) for k, D in (("S3", S3), ("S2", S2), ("S1c", S1c))}
        R3[wl]["pass"] = all(R3[wl][k] is not None and R3[wl][k] <= 0.10 for k in ("S3", "S2"))
        P = pred.get(f"{wl}_rho1", {})
        errs = {}
        for stg, o, pk in (("none", "fwd", "S0"), ("S1o", "fwd", "S1o"), ("S1c", "fwd", "S1c/fwd"), ("S1c", "rev", "S1c/rev"), ("S2", "fwd", "S2/fwd"), ("S2", "rev", "S2/rev"), ("S3", "fwd", "S3/fwd"), ("S3", "rev", "S3/rev")):
            c = cell(wl, rho, stg, o)
            if c and c["n_valid"] and pk in P:
                errs[pk] = {"remote_pred": P[pk]["remote_s"], "remote_meas": c["remote_s"], "remote_err": P[pk]["remote_s"] / c["remote_s"] - 1,
                            "total_pred_mb": P[pk]["total_mb"], "total_meas_mb": c["total_mb"], "total_err": P[pk]["total_mb"] / c["total_mb"] - 1}
        R4[wl] = {"per_policy": errs, "remote_within_15pct_all": bool(errs) and all(abs(e["remote_err"]) <= 0.15 for e in errs.values()),
                  "total_within_15pct_all": bool(errs) and all(abs(e["total_err"]) <= 0.15 for e in errs.values())}
    rep["rules"] = {"R1": R1, "R2": R2, "R3": R3, "R4": R4, "R5_invalid_runs": {str(k): v["invalid"] for k, v in agg.items() if v["invalid"]}}
    r1_all = bool(R1) and len(R1) == 2 and all(v["pass"] for v in R1.values())
    bytes_only = bool(R1) and len(R1) == 2 and all(all(x["remote_ratio"] <= 0.80 for x in v["per_order"].values()) for v in R1.values()) and not r1_all
    if r1_all:
        verdict = "GO (R1 holds for both workloads; next: M3-S2 GPU validation, to be preregistered)"
    elif bytes_only:
        verdict = "CONDITIONAL (remote serving <= 0.80 S0 but total bytes > 1.30 S0)" + (": single-candidate variant" if all(R2[w]["one_candidate_suffices"] for w in R2) else ": NO-GO (two candidates needed and too costly)")
    else:
        verdict = "NO-GO (remote serving not <= 0.80 S0 for a workload under S3)"
    rep["verdict"] = verdict
    rep["cells"] = {f"{k[0]}|rho{k[1]:g}|{k[2]}|{k[3]}": v for k, v in agg.items()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "s1_results.json").write_text(json.dumps(rep, indent=1, default=str))
    L = [f"# M3-S1 results ({a.experiment})", "", "| cell | valid | remote s | local s | cancelled | final valid/180 | final base MB | final ready s | total MB | discarded | staged | wasted |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in sorted(agg.items()):
        f = lambda x, d=1: "-" if x is None else (f"{x:.{d}f}" if isinstance(x, float) else str(x))  # noqa: E731
        L.append(f"| {k[0]} ρ{k[1]:g} {k[2]}/{k[3]} | {v['n_valid']}/{v['n_runs']} | {f(v['remote_s'])} | {f(v['local_s'])} | {f(v['n_cancelled'],0)} | {f(v['final_valid'],0)} | {f(v['final_base_mb'],0)} | {f(v['final_ready_s'])} | {f(v['total_mb'],0)} | {f(v['discarded_mb'],0)} | {f(v['staged_mb'],0)} | {f(v['wasted_staged_mb'],0)} |")
    L += ["", "## Rules", "", "```", json.dumps(rep["rules"], indent=1, default=str), "```", "", f"**Verdict: {verdict}**", ""]
    (OUT / "s1_results.md").write_text("\n".join(L))
    print("\n".join(L[:len(agg) + 4])); print(json.dumps({"R1": R1, "R3": R3, "verdict": verdict}, indent=1, default=str))


if __name__ == "__main__":
    main()
