#!/usr/bin/env python3
"""M3-S2 report (osdi/m3s2/preregistration.md): Phases A0 (offline exactness), A (end-to-end exactness on the
testbed), B (faults), C (live migration / continuity) and D (performance), each judged by its preregistered rules as
written.

    python tools/eval/m3s2_report.py [--prefix _dryrun_] [--no_validity]
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
from xb_delivery import delivery_metrics, load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/m3s2"
EVAL = ROOT / "results/evaluation"
WLS = ("dog", "bfly")
FAULTS = ("advertise_wrong", "corrupt_held", "holder_fail")
CONDS = ("base", "ctl", "s2")


def events(d: Path) -> list[dict]:
    return [{"t": float(r["t_rel"]) if r["t_rel"] not in ("", None) else None, "event": r["event"], **(json.loads(r["detail"]) if r["detail"] else {})}
            for r in csv.DictReader(open(d / "events.csv", newline=""))]


def run_record(d: Path, check_validity: bool = True) -> dict:
    s, m, nev = load_run(d)
    ev = events(d)
    ok, why = run_validity_xb(s, d) if check_validity else (True, [])
    D = delivery_metrics(s, m, nev)
    first = lambda name_, **kw: next((e for e in ev if e["event"] == name_ and all(e.get(k) == v for k, v in kw.items())), None)  # noqa: E731
    tasks = []
    for e in (e for e in ev if e["event"] == "xb_task_start"):
        tid, src, dst = e["id"], e["src"], e["dst"]
        canc, done = first("xb_task_cancel", task=tid), first("xb_task_done", task=tid)
        base = first(f"{src}:replay_base_sent", task=tid) or first(f"{src}:m3_base_cancelled", task=tid)
        crec, sw = first(f"{src}:xb_precopy_cancelled", task=tid), first(f"{src}:xb_precopy_switch", task=tid)
        ready = first(f"{src}:replay_ready", task=tid)
        logrec = crec or sw or {}
        base_bytes = (base or {}).get("bytes")
        if base_bytes is None and crec is not None:
            base_bytes = crec.get("base_bytes")
        tasks.append({"task": tid, "src": src, "dst": dst, "t_start": e["t"], "outcome": "cancelled" if canc else ("completed" if done else "open"),
                      "c0": (base or {}).get("call"), "base_mode": (base or {}).get("mode"), "base_bytes": int(base_bytes or 0), "log_bytes": int(logrec.get("log_bytes") or 0),
                      "reused": (base or {}).get("reused"), "sent_entries": (base or {}).get("sent_entries"), "header_bytes": (base or {}).get("header_bytes"),
                      "t_ready": ready and ready["t"], "m3": e.get("m3")})
    M3 = s.get("m3") or {}
    fwd_bytes = sum(int(f.get("bytes") or 0) for f in M3.get("forwards") or [])
    fin = next((t for t in reversed(tasks) if t["outcome"] == "completed"), None)
    canc = [t for t in tasks if t["outcome"] == "cancelled"]
    dst_fin = next((b for b in reversed(M3.get("dest_bases") or []) if fin and b.get("task") == fin["task"]), None)
    ss = first(f"{fin['dst']}:sink_sync_check") if fin else None
    fo = next((e for e in ev if fin and e["event"] == f"{fin['dst']}:first_output"), None)
    v = s.get("validation") or {}
    rec = {"run": d.name, "valid": ok, "why": why, "remote_s": D["remote_wall_s"], "n_cancelled": len(canc), "final_completed": fin is not None,
           "bytes": {"base": sum(t["base_bytes"] for t in tasks), "log": sum(t["log_bytes"] for t in tasks), "forward": fwd_bytes,
                     "total": sum(t["base_bytes"] + t["log_bytes"] for t in tasks) + fwd_bytes,
                     "discarded": sum(t["base_bytes"] + t["log_bytes"] for t in canc), "final_base": fin and fin["base_bytes"],
                     "header": sum(int(t["header_bytes"] or 0) for t in tasks)},
           "final": fin and {"task": fin["task"], "mode": fin["base_mode"], "c0": fin["c0"], "reused": fin["reused"], "sent_entries": fin["sent_entries"],
                             "readiness_s": (fin["t_ready"] - fin["t_start"]) if fin["t_ready"] is not None else None,
                             "first_output_s": (fo["t"] - fin["t_start"]) if fo else None, "interruption_s": (s.get("cutover") or {}).get("interruption_s"),
                             "dest": dst_fin, "sink_sync": ss and {k: ss.get(k) for k in ("call", "match", "n_block_mismatch", "positions_equal")}},
           "c0_by_task": {t["task"]: t["c0"] for t in tasks}, "tasks": tasks, "m3": {k: M3.get(k) for k in ("forwards", "rx_bytes_by_link", "entries_lost", "entries_bad", "test_fault", "plans")},
           "replay_validity": {k: v.get(k) for k in ("switchovers_verified", "n_switchovers", "final_edge_served", "replay_base_verified", "replay_conditioning_equal", "replay_order_ok",
                                                     "replay_meta_consistent_at_switch", "replay_no_lost_or_duplicated_calls", "replay_sink_digest_match", "replay_verdict", "replay_switch_refused")}}
    return rec


def latest(name: str, prefix: str):
    ds = sorted((EVAL / f"{prefix}{name}").glob("policy=*"))
    return [d for d in ds if (d / "summary.json").exists()]


def b_holder_reused(rec: dict) -> dict:
    """How many entries of the final base came from the abandoned first destination (version = the first task's c0)."""
    c0s = list(rec["c0_by_task"].values())
    c0_first = c0s[0] if c0s else None
    vers = ((rec["final"] or {}).get("dest") or {}).get("versions") or {}
    return {"first_c0": c0_first, "entries_at_first_c0": int(vers.get(str(c0_first), vers.get(c0_first, 0)) or 0), "versions": vers}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--prefix", default=""); ap.add_argument("--no_validity", action="store_true"); a = ap.parse_args()
    chk = not a.no_validity
    rep = {"phases": {}}
    # ---- A0
    A0 = {}
    for wl in WLS:
        f = OUT / f"a0_{wl}.json"
        if f.exists():
            j = json.load(open(f)); vd = j["verdict"]
            A0[wl] = {**vd, "pass": bool(vd["E_valid_entries_all_exact"] and vd["S_assemblies_all_exact"] and vd["N_noshift_all_detected"] and vd["N_stale_sink_all_detected"]),
                      "valid_entries": j["entry_level"]["valid_entries"], "pairs": j["entry_level"]["pairs"], "refreshed_entries": j["entry_level"]["refreshed_entries"],
                      "refreshed_v_changed": j["entry_level"]["refreshed_v_changed"], "serialization_cost": j.get("serialization_cost")}
    rep["phases"]["A0"] = A0
    # ---- A + C (end-to-end exactness, live migration)
    AC = {}
    for wl in WLS:
        ds = latest(f"expM3S2A_{wl}", a.prefix)
        if not ds:
            continue
        r = run_record(ds[-1], chk)
        fin = r["final"] or {}
        dst = fin.get("dest") or {}
        bh = b_holder_reused(r)
        rv = r["replay_validity"]
        A = {"final_mode_m3": fin.get("mode") == "m3", "accepted": bool(dst.get("accepted")), "blocks_equal": dst.get("n_block_mismatch") == 0,
             "positions_equal": dst.get("positions_equal") is True, "cond_equal": dst.get("cond_equal") is True,
             "abandoned_state_reused": bh["entries_at_first_c0"] > 0, "forward_bytes": r["bytes"]["forward"]}
        C = {"one_switchover_to_D": rv.get("n_switchovers") == 1 and rv.get("final_edge_served") is True, "switch_sinkok": rv.get("replay_verdict") == "SINKOK",
             "replay_checks": all(rv.get(k) is True for k in ("replay_base_verified", "replay_conditioning_equal", "replay_order_ok", "replay_meta_consistent_at_switch",
                                                             "replay_no_lost_or_duplicated_calls", "replay_sink_digest_match")),
             "no_refused_switch": rv.get("replay_switch_refused") == 0}
        AC[wl] = {"run": r["run"], "valid": r["valid"], "why": r["why"], "A": A, "A_pass": r["valid"] and all(v_ is True for k_, v_ in A.items() if k_ != "forward_bytes"),
                  "C": C, "C_pass": r["valid"] and all(C.values()), "holder_reuse": bh, "final": fin, "remote_s": r["remote_s"], "bytes": r["bytes"],
                  "continuity_diagnostic": {"interruption_s": fin.get("interruption_s"), "first_output_s": fin.get("first_output_s"), "readiness_s": fin.get("readiness_s")}}
    rep["phases"]["A_C"] = AC
    # ---- B (faults, dog)
    B = {}
    for fault in FAULTS:
        ds = latest(f"expM3S2B_{fault}", a.prefix)
        if not ds:
            continue
        r = run_record(ds[-1], chk)
        fin = r["final"] or {}
        dst = fin.get("dest") or {}
        rv = r["replay_validity"]
        safe = rv.get("replay_verdict") == "SINKOK" and rv.get("replay_base_verified") is True and rv.get("n_switchovers") == 1 and rv.get("replay_switch_refused") == 0
        last_task = (r["tasks"] or [{}])[-1].get("m3") or {}
        if fault == "advertise_wrong":
            handled = fin.get("mode") == "m3" and bool(dst.get("accepted")) and len(last_task.get("altered") or []) == 3
        elif fault == "corrupt_held":
            handled = dst.get("accepted") is False and (dst.get("n_block_mismatch") or 0) >= 1 and fin.get("mode") == "full"
        else:
            handled = (r["m3"].get("entries_lost") or 0) >= 1 and fin.get("mode") == "m3" and bool(dst.get("accepted")) and (last_task.get("missing_expected") == 0)
        B[fault] = {"run": r["run"], "valid": r["valid"], "why": r["why"], "handled": handled, "exact_and_safe": safe, "pass": r["valid"] and handled and safe,
                    "final_mode": fin.get("mode"), "dest": dst, "advertise": last_task, "remote_s": r["remote_s"]}
    rep["phases"]["B"] = B
    # ---- D (performance)
    Dp = {}
    for wl in WLS:
        cells = {}
        for cond in CONDS:
            recs = [run_record(d, chk) for d in latest(f"expM3S2D_{wl}_{cond}", a.prefix)]
            okr = [x for x in recs if x["valid"] and x["final_completed"] and (cond == "base" or (x["final"] or {}).get("mode") == "m3")]
            med = lambda k, sub=None: st.median([(x[sub][k] if sub else x[k]) for x in okr]) if okr else None  # noqa: E731
            cells[cond] = {"n_runs": len(recs), "n_valid": len(okr), "invalid": [(x["run"], x["why"]) for x in recs if x not in okr],
                           "remote_s": med("remote_s"), "total_mb": (med("total", "bytes") or 0) / 1e6 if okr else None, "discarded_mb": (med("discarded", "bytes") or 0) / 1e6 if okr else None,
                           "forward_mb": (med("forward", "bytes") or 0) / 1e6 if okr else None, "final_base_mb": (med("final_base", "bytes") or 0) / 1e6 if okr else None,
                           "header_bytes": med("header", "bytes"),
                           "readiness_s": st.median([x["final"]["readiness_s"] for x in okr if x["final"] and x["final"]["readiness_s"] is not None]) if okr else None,
                           "interruption_s": st.median([x["final"]["interruption_s"] for x in okr if x["final"] and x["final"]["interruption_s"] is not None]) if okr else None,
                           "reused": st.median([x["final"]["reused"] or 0 for x in okr if x["final"]]) if okr else None}
        b, c, s2 = cells["base"], cells["ctl"], cells["s2"]
        rr = lambda x, y, k: (x[k] / y[k]) if (x[k] is not None and y[k]) else None  # noqa: E731
        Dp[wl] = {"cells": cells, "s2_remote_vs_base": rr(s2, b, "remote_s"), "s2_total_vs_base": rr(s2, b, "total_mb"), "ctl_remote_vs_base": rr(c, b, "remote_s"),
                  "s2_remote_vs_ctl": rr(s2, c, "remote_s"),
                  "header_overhead_of_entry_bytes": (c["header_bytes"] / (c["total_mb"] * 1e6)) if (c["header_bytes"] and c["total_mb"]) else None}
        Dp[wl]["R_D1"] = bool(Dp[wl]["s2_remote_vs_base"] is not None and Dp[wl]["s2_remote_vs_base"] <= 0.80 and Dp[wl]["s2_total_vs_base"] is not None and Dp[wl]["s2_total_vs_base"] <= 1.30)
        Dp[wl]["R_D2"] = bool(Dp[wl]["s2_remote_vs_ctl"] is not None and Dp[wl]["s2_remote_vs_ctl"] <= 0.85)
    rep["phases"]["D"] = Dp
    # ---- verdict (preregistered mapping)
    a0_ok = len(A0) == 2 and all(x["pass"] for x in A0.values())
    a_ok = len(AC) == 2 and all(x["A_pass"] for x in AC.values())
    c_ok = len(AC) == 2 and all(x["C_pass"] for x in AC.values())
    b_ok = len(B) == 3 and all(x["pass"] for x in B.values())
    d_ok = len(Dp) == 2 and all(x["R_D1"] for x in Dp.values())
    rep["gates"] = {"A0": a0_ok, "A": a_ok, "B": b_ok, "C": c_ok, "D_R_D1": d_ok, "D_R_D2": len(Dp) == 2 and all(x["R_D2"] for x in Dp.values())}
    if not (A0 and AC and B):
        verdict = "INCOMPLETE (phases missing)"
    elif not (a0_ok and a_ok):
        verdict = "EXACTNESS NOT SHOWN: mixed-version reconstruction is not established; M3 stays a network-level result"
    elif not (b_ok and c_ok):
        verdict = "CORRECTNESS INCOMPLETE: exact assembly holds, but fault handling or live switchover failed; fix before any performance claim"
    elif not Dp or not all(x["cells"]["s2"]["n_valid"] and x["cells"]["base"]["n_valid"] for x in Dp.values()):
        verdict = "CORRECT (A0, A, B, C pass); performance phase incomplete"
    elif d_ok:
        verdict = "SUPPORTED: exact, fault-safe, live; remote serving <= 0.80 and total bytes <= 1.30 of the M1 / M2 baseline on both workloads"
    else:
        verdict = "CORRECT BUT NOT FASTER BY THE MARGIN: exact, fault-safe, live; R-D1 fails for a workload"
    rep["verdict"] = verdict
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"m3s2_results{'_' + a.prefix.strip('_') if a.prefix else ''}.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep["gates"], indent=1)); print("verdict:", verdict)
    for wl, x in AC.items():
        print(f"A/C {wl}: A {x['A_pass']} C {x['C_pass']} reused from first destination {x['holder_reuse']['entries_at_first_c0']}, versions {x['holder_reuse']['versions']}, remote {x['remote_s']}")
    for f_, x in B.items():
        print(f"B {f_}: pass {x['pass']} (handled {x['handled']}, safe {x['exact_and_safe']}, final mode {x['final_mode']})")
    for wl, x in Dp.items():
        print(f"D {wl}: s2/base remote {x['s2_remote_vs_base']}, total {x['s2_total_vs_base']}, ctl/base remote {x['ctl_remote_vs_base']}, s2/ctl {x['s2_remote_vs_ctl']}; R-D1 {x['R_D1']} R-D2 {x['R_D2']}")


if __name__ == "__main__":
    main()
