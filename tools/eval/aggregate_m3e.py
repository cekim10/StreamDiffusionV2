#!/usr/bin/env python3
"""Experiment M3E verdicts (results/evaluation/osdi/expM3E/preregistration.md, frozen abf74d6).

    python tools/eval/aggregate_m3e.py [--dry]   # -> results/evaluation/osdi/expM3E/m3e_results.{md,json}

Uses the W / R / N run validity, applicability and censored-median helpers (aggregate_wrn.py) unchanged. Re-plan counts
include probes (V convention); "full re-plans" = re-plans - probes. Historical M3-v1 numbers (ExpD) are printed next to
the verdicts as cross-commit context only.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from aggregate_wrn import NE, NOT, SUP, Val, absdiff_le, cmedian, diff_le, le, ratio_le, run_rec, runs_in, valid_reps, verdict  # noqa: E402

SCEN = {"S1": ("expM3E_S1", ("restart", "split", "reuse_dyn2")), "S2": ("expM3E_S2", ("restart", "split", "reuse_dyn2", "reuse_aware_in")),
        "S3": ("expM3E_S3", ("restart", "split", "reuse_dyn2")), "S4": ("expM3E_S4", ("restart", "split", "reuse_dyn2")),
        "S5": ("expM3E_S5", ("restart", "split", "reuse_dyn2"))}
CAP = {"S2", "S3", "S5"}
HIST = {"S1": "ExpD E (v1): M1 only 57.07, M1 + M2 43.09, v1 42.82 s", "S2": "ExpD F (v1): M1 only 15.36, M1 + M2 78.39, at moves 51.58, v1 15.80 s (B_source 1.19, 2 re-plans)",
        "S4": "ExpD B rho 2 (v1): M1 only 15.52, M1 + M2 15.11, v1 15.45 s, 0 re-plans", "S3": "no ExpD counterpart (N cell 10 class)", "S5": "no ExpD counterpart (N cell 8 class)"}


def extra(r: dict) -> dict:
    s = r["s"]; d = r["dir"]
    rp = s["d0"].get("replans") or []
    probes = [x for x in rp if x.get("probe")]
    fin = s["path"][-1]
    t_move_call = s["moves"][-1]["call"] if s["moves"] else None
    bcall = s["final"].get("bind_call")
    cs = []
    for row in csv.DictReader(open(d / "metrics.csv", newline="")):
        if row["owner"] == fin and row["chunk_s"] not in ("", "None") and t_move_call is not None and bcall is not None and t_move_call <= int(row["call"]) < bcall:
            cs.append(float(row["chunk_s"]))
    hyb = (s.get("hybrid") or {}).get("network_summary") or {}
    return {"ttfo": s["latency_after_final_move_s"].get("first_output"), "agg": s["d0"].get("aggregate_network_sinks"), "probes": len(probes),
            "full_replans": len(rp) - len(probes), "probe_frags_max": max((x.get("moved_fragments", 0) for x in probes), default=0),
            "dup_bytes": (s.get("bytes") or {}).get("duplicate", 0), "cap_fired": len(s["d0"].get("cap_changes") or []), "chunk_s_move_to_bind": st.median(cs) if cs else None,
            "net_sessions": {k: hyb.get(k) for k in ("restored_sessions", "makespan_s", "first_restored")} if hyb else None,
            "stop": s["validation"].get("stop_reason")}


def collect(sc, dry):
    exp, pols = SCEN[sc]
    runs = runs_in(exp, dry)
    out = {}
    for p in pols:
        rs = [r for r in runs if r["policy"] == p]
        v, n_inap = valid_reps(rs)
        if sc in CAP:
            v = [r for r in v if extra(r)["cap_fired"] >= 1]
        for r in v:
            r["x"] = extra(r)
        out[p] = {"runs": v, "n_valid": len(v), "n_inapplicable": n_inap, "n_all": len(rs), "invalid": [(r["dir"].name, r["why"]) for r in rs if not r["valid"]]}
    return out


def m(g, f):
    return cmedian([f(r) if isinstance(f(r), Val) else Val(f(r)) for r in g["runs"]])


def mm(g, f):
    v = [f(r) for r in g["runs"] if f(r) is not None]
    return st.median(v) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    C = {sc: collect(sc, a.dry) for sc in SCEN}
    enough = lambda sc, *ps: all(C[sc][p]["n_valid"] >= 3 for p in ps)  # noqa: E731
    H = {}
    bind = lambda r: r["bind"]  # noqa: E731
    src = lambda r: r["B_source"]  # noqa: E731
    # H1 (S1)
    if enough("S1", "restart", "split", "reuse_dyn2"):
        g = C["S1"]
        v3, v1, v2 = m(g["reuse_dyn2"], bind), m(g["restart"], bind), m(g["split"], bind)
        c1, c2, c3 = diff_le(v3, v1, -3.5), diff_le(v3, v2, 1.0), le(m(g["reuse_dyn2"], src), m(g["split"], src).x + 0.05)
        H["H1"] = verdict(None if None in (c1, c2, c3) else (c1 and c2 and c3))
    else:
        H["H1"] = f"{NE} (< 3 valid reps)"
    # H2 (S2)
    if enough("S2", "split", "reuse_dyn2", "reuse_aware_in"):
        g = C["S2"]; v = g["reuse_dyn2"]
        c1, c2 = ratio_le(m(v, bind), m(g["reuse_aware_in"], bind), 0.5), ratio_le(m(v, bind), m(g["split"], bind), 0.5)
        per = all(r["replans"] <= 2 and r["x"]["probes"] <= 1 and r["x"]["probe_frags_max"] <= 4 and r["x"]["dup_bytes"] == 0 for r in v["runs"])
        c3 = le(m(v, src), 1.35)
        H["H2"] = verdict(None if None in (c1, c2, c3) else (c1 and c2 and c3 and per))
    else:
        H["H2"] = f"{NE} (< 3 valid reps or cap event not fired)"
    # H3 / H5 (S3 / S5): no harm
    for hid, sc in (("H3", "S3"), ("H5", "S5")):
        if enough(sc, "split", "reuse_dyn2"):
            g = C[sc]; v = g["reuse_dyn2"]
            per = all(r["x"]["full_replans"] == 0 and r["x"]["probes"] <= 1 for r in v["runs"])
            c1 = diff_le(m(v, bind), m(g["split"], bind), 1.0)
            c2 = le(m(v, src), m(g["split"], src).x + 0.02)
            H[hid] = verdict(None if None in (c1, c2) else (per and c1 and c2))
        else:
            H[hid] = f"{NE} (< 3 valid reps or cap event not fired)"
    # H4 (S4)
    if enough("S4", "split", "reuse_dyn2"):
        g = C["S4"]; v = g["reuse_dyn2"]
        per = all(r["replans"] == 0 for r in v["runs"])
        c1 = absdiff_le(m(v, bind), m(g["split"], bind), 1.0)
        c2 = le(m(v, src), m(g["split"], src).x + 0.01)
        H["H4"] = verdict(None if None in (c1, c2) else (per and c1 and c2))
    else:
        H["H4"] = f"{NE} (< 3 valid reps)"
    # H6 / H7 (all scenarios)
    h6, h7 = {}, {}
    for sc in SCEN:
        g = C[sc]
        if not enough(sc, "split", "reuse_dyn2"):
            h6[sc] = h7[sc] = None; continue
        t3, t2 = mm(g["reuse_dyn2"], lambda r: r["x"]["ttfo"]), mm(g["split"], lambda r: r["x"]["ttfo"])
        h6[sc] = None if None in (t3, t2) else t3 <= t2 + 0.2
        c3, c2 = mm(g["reuse_dyn2"], lambda r: r["x"]["chunk_s_move_to_bind"]), mm(g["split"], lambda r: r["x"]["chunk_s_move_to_bind"])
        h7[sc] = None if None in (c3, c2) else abs(c3 - c2) <= 0.02 * c2
    H["H6"] = verdict(None if any(v is None for v in h6.values()) else all(h6.values()), "a scenario not evaluable")
    H["H7"] = verdict(None if any(v is None for v in h7.values()) else all(h7.values()), "a scenario not evaluable")
    ok = lambda h: H[h] == SUP  # noqa: E731
    failed = lambda h: H[h] == NOT  # noqa: E731
    if ok("H1") and ok("H2") and ok("H4") and not failed("H3") and not failed("H5"):
        overall = "M3-v2 is reported as the end-to-end M3 (H1, H2, H4 supported; H3, H5 not failed)"
    else:
        overall = "M3-v2 end-to-end: not all of H1 / H2 / H4 supported or H3 / H5 failed -> stated limitations" + ("; REGRESSION against frozen M2: " + ", ".join(h for h in ("H3", "H4", "H5") if failed(h)) if any(failed(h) for h in ("H3", "H4", "H5")) else "")
    out = {"dry": a.dry, "hypotheses": H, "h6_by_scenario": h6, "h7_by_scenario": h7, "overall": overall, "historical_v1": HIST, "scenarios": {}}
    f = lambda x, n=2: "-" if x is None else (repr(x) if isinstance(x, Val) else f"{x:.{n}f}")  # noqa: E731
    L = [f"# M3E verdicts{' (DRY RUN: loopback, not meaningful)' if a.dry else ''} (frozen preregistration abf74d6)", "",
         "| hypothesis | verdict |", "|---|---|"] + [f"| {k} | {v} |" for k, v in H.items()] + ["", f"**{overall}**", "",
         "| scenario | policy | valid / all | bind-ready (s) | TTFO (s) | B_source | total net | re-plans (probes) per rep | chunk s move->bind | dup bytes | net sessions |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for sc in SCEN:
        out["scenarios"][sc] = {}
        for p, g in C[sc].items():
            row = {"n_valid": g["n_valid"], "n_all": g["n_all"], "invalid": g["invalid"], "bind": repr(m(g, bind)) if g["runs"] else None, "ttfo": mm(g, lambda r: r["x"]["ttfo"]),
                   "B_source": mm(g, src), "agg": mm(g, lambda r: r["x"]["agg"]), "replans": [r["replans"] for r in g["runs"]], "probes": [r["x"]["probes"] for r in g["runs"]],
                   "chunk_s": mm(g, lambda r: r["x"]["chunk_s_move_to_bind"]), "dup": [r["x"]["dup_bytes"] for r in g["runs"]],
                   "net": [r["x"]["net_sessions"] for r in g["runs"]] if sc == "S1" else None, "dirs": [r["dir"].name for r in g["runs"]]}
            out["scenarios"][sc][p] = row
            L.append(f"| {sc} | {p} | {g['n_valid']} / {g['n_all']} | {row['bind'] or '-'} | {f(row['ttfo'])} | {f(row['B_source'], 3)} | {f(row['agg'], 3)} | "
                     f"{row['replans']} ({row['probes']}) | {f(row['chunk_s'], 4)} | {row['dup']} | {'-' if not row['net'] else row['net']} |")
    L += ["", "Historical M3-v1 (ExpD, cross-commit context only, not pooled):"] + [f"- {k}: {v}" for k, v in HIST.items()]
    od = ROOT / "results/evaluation/osdi/expM3E"
    stem = "_dryrun_m3e_results" if a.dry else "m3e_results"
    (od / f"{stem}.json").write_text(json.dumps(out, indent=1, default=str))
    (od / f"{stem}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
