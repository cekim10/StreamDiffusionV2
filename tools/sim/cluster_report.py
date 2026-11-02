#!/usr/bin/env python3
"""E9 (osdi/fig_cluster/preregistration.md, FROZEN): applies CL-H1 to CL-H3 to a sweep. SIMULATED results.

CL-H1  at the primary point (N 64, C 10 Gbps, M 32 GB, dwell 180 s): OTTER's total stalled seconds per session-hour <
       each of Full / Llumnix / SLLM, and OTTER's local share >= each (median over seeds); reported with the ratio to the
       best of the three and the stalls > 1 / 2 / 5 / 10 s per session-hour.
CL-H2  at the primary N, C and dwell, every M > 0: OTTER's mean delay per move <= Replicate's and OTTER's staging bytes
       per session-hour <= Replicate's.
CL-H3  descriptive: the (C, dwell, M) cells at the primary N where OTTER's mean delay per move < Unstaged's by >= 10 %.

    python3.11 tools/sim/cluster_report.py [--grid primary] [--prefix _smoke_]
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/evaluation/osdi/fig_cluster"
PRIMARY = {"N": 64, "C_gbps": 10.0, "M_gb": 32.0, "dwell_s": 180.0}
BASELINES = ("full", "pfull", "rfull")
LABEL = {"full": "Full", "pfull": "Llumnix", "rfull": "SLLM", "base": "Unstaged", "otter": "OTTER", "naive": "Replicate"}


def at(runs, **kv):
    return [r for r in runs if all(abs(float(r["cfg"][k]) - float(v)) < 1e-9 for k, v in kv.items())]


def med(rs, f):
    xs = [f(r) for r in rs]
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def stalled(r):
    return r.get("stalled_s_per_session_h", r["stall_frac"] * 3600)


def delay(r):
    return r["no_local_after_move_s"].get("mean")


def staging(r):
    return (r.get("bytes_per_session_h_gb") or {}).get("staging", 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="primary")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--primary", default=None, help="test only: N,C,M,dwell to use as the primary point (e.g. the smoke grid)")
    a = ap.parse_args()
    d = json.loads((OUT / f"{a.prefix}sweep_{a.grid}.json").read_text())
    runs = d["runs"]
    by = lambda rs, m: [r for r in rs if r["method"] == m]  # noqa: E731
    if a.primary:
        PRIMARY.update(dict(zip(("N", "C_gbps", "M_gb", "dwell_s"), map(float, a.primary.split(",")))))
    P = at(runs, **PRIMARY)
    v = {}
    # CL-H1
    row = {m: {"stalled_s_h": med(by(P, m), stalled), "local": med(by(P, m), lambda r: r["local_frac"]),
               **{f"stalls_gt{x}": med(by(P, m), lambda r, x=x: r["stalls_per_session_h"][x]) for x in ("1.0", "2.0", "5.0", "10.0")},
               "seeds": len(by(P, m))} for m in LABEL}
    o = row["otter"]
    h1a = all(o["stalled_s_h"] is not None and row[b]["stalled_s_h"] is not None and o["stalled_s_h"] < row[b]["stalled_s_h"] for b in BASELINES)
    h1b = all(o["local"] is not None and row[b]["local"] is not None and o["local"] >= row[b]["local"] for b in BASELINES)
    best = min((row[b]["stalled_s_h"] for b in BASELINES if row[b]["stalled_s_h"] is not None), default=None)
    v["CL-H1"] = {"holds": h1a and h1b, "stalled_lt_each": h1a, "local_ge_each": h1b, "ratio_to_best": o["stalled_s_h"] / best if (best and o["stalled_s_h"] is not None) else None, "primary": row}
    # CL-H2
    fixed = {k: PRIMARY[k] for k in ("N", "C_gbps", "dwell_s")}
    h2 = {}
    for M in sorted({float(r["cfg"]["M_gb"]) for r in runs if float(r["cfg"]["M_gb"]) > 0}):
        cell = at(runs, **fixed, M_gb=M)
        od, nd = med(by(cell, "otter"), delay), med(by(cell, "naive"), delay)
        ob, nb = med(by(cell, "otter"), staging), med(by(cell, "naive"), staging)
        h2[str(M)] = {"otter_delay_s": od, "replicate_delay_s": nd, "otter_staging_gb_h": ob, "replicate_staging_gb_h": nb,
                      "holds": None not in (od, nd, ob, nb) and od <= nd and ob <= nb}
    v["CL-H2"] = {"holds": bool(h2) and all(x["holds"] for x in h2.values()), "per_M": h2}
    # CL-H3 (descriptive)
    cells = []
    for C in sorted({float(r["cfg"]["C_gbps"]) for r in runs}):
        for dw in sorted({float(r["cfg"]["dwell_s"]) for r in runs}):
            for M in sorted({float(r["cfg"]["M_gb"]) for r in runs}):
                cell = at(runs, N=PRIMARY["N"], C_gbps=C, dwell_s=dw, M_gb=M)
                od, bd = med(by(cell, "otter"), delay), med(by(cell, "base"), delay)
                if None in (od, bd):
                    continue
                cells.append({"C_gbps": C, "dwell_s": dw, "M_gb": M, "otter_delay_s": od, "unstaged_delay_s": bd,
                              "gain": 1 - od / bd if bd else None, "staging_helps": bd > 0 and od < 0.9 * bd})
    v["CL-H3"] = {"cells": cells, "n_helps": sum(c["staging_helps"] for c in cells), "n_cells": len(cells)}
    f = lambda x, n=1: "-" if x is None else f"{x:.{n}f}"  # noqa: E731
    L = ["# E9 cluster simulation: results (SIMULATED)", "", f"Rules: `preregistration.md` (FROZEN). Sweep `{a.grid}`, {len(runs)} runs; "
         "medians over seeds. Calibrated from testbed measurements, validated against Fig. 11 (gate 76 / 76).", "",
         f"**CL-H1 {'SUPPORTED' if v['CL-H1']['holds'] else 'NOT SUPPORTED'}** (stalled seconds < each baseline: {h1a}; local share >= each: {h1b}; "
         f"OTTER / best baseline stalled seconds {f(v['CL-H1']['ratio_to_best'], 3)}).", "",
         "| method | stalled s / session-h | local share | stalls > 1 / 2 / 5 / 10 s per session-h | seeds |", "|---|---|---|---|---|"]
    for m in LABEL:
        r = row[m]
        L.append(f"| {LABEL[m]} | {f(r['stalled_s_h'])} | {f(r['local'], 3)} | {f(r['stalls_gt1.0'], 2)} / {f(r['stalls_gt2.0'], 2)} / "
                 f"{f(r['stalls_gt5.0'], 2)} / {f(r['stalls_gt10.0'], 2)} | {r['seeds']} |")
    L += ["", f"**CL-H2 {'SUPPORTED' if v['CL-H2']['holds'] else 'NOT SUPPORTED'}** (N 64, C 10 Gbps, dwell 180 s):", "",
          "| M (GB) | delay per move OTTER / Replicate (s) | staging GB per session-h OTTER / Replicate | holds |", "|---|---|---|---|"]
    for M, x in h2.items():
        L.append(f"| {M} | {f(x['otter_delay_s'])} / {f(x['replicate_delay_s'])} | {f(x['otter_staging_gb_h'], 2)} / {f(x['replicate_staging_gb_h'], 2)} | {x['holds']} |")
    L += ["", f"**CL-H3 (descriptive):** staging helps (OTTER delay per move < 0.9 x Unstaged) in {v['CL-H3']['n_helps']} / {v['CL-H3']['n_cells']} "
          "(C, dwell, M) cells at N 64.", "", "| C (Gbps) | dwell (s) | M (GB) | delay OTTER / Unstaged (s) | gain |", "|---|---|---|---|---|"]
    for c in cells:
        L.append(f"| {c['C_gbps']:g} | {c['dwell_s']:g} | {c['M_gb']:g} | {f(c['otter_delay_s'])} / {f(c['unstaged_delay_s'])} | {f(100 * c['gain'] if c['gain'] is not None else None)} % |")
    (OUT / f"{a.prefix}cluster_results.md").write_text("\n".join(L) + "\n")
    (OUT / f"{a.prefix}cluster_results.json").write_text(json.dumps(v, indent=1))
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()
