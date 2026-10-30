#!/usr/bin/env python3
"""M3-S3 report (osdi/m3s3/preregistration.md): lineage-aware staging across an ownership change. Phases P0 (offline,
one GPU), A (end-to-end exactness after an ownership change), C (both live switchovers), B (faults of the
ownership-change path) and D (performance), each judged by its preregistered rule as written.

    python tools/eval/m3s3_report.py [--prefix _dryrun_] [--no_validity]
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
import m3s2_report as R2  # noqa: E402  (run_record, events, latest: the M3-S2 per-run record, unchanged)
from xb_delivery import load_run  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/m3s3"
WLS = ("dog", "bfly")
FAULTS = ("version_mismatch", "corrupt_retained", "old_owner_fail")
CONDS = ("base", "ctl", "s2")


def switch_checks(d: Path, rec: dict) -> dict:
    """Per completed switchover (the frozen replay accounting covers only the first): source verdict SINKOK, destination
    base verified with equal conditioning, Sink digest equal at the switch, metadata consistent at resume, replay order
    ok; over the whole run, generator calls contiguous and unique across all owners, each owner's calls between its
    switches, and no refused switch."""
    s, m, nev = load_run(d)
    ev = R2.events(d)
    out = []
    sws = s.get("switchovers") or []
    for sw in sws:
        t = next((x for x in rec["tasks"] if x["task"] == sw["task"]), None)
        if t is None:
            out.append({"task": sw["task"], "ok": False, "why": "task missing"}); continue
        src, dst = t["src"], t["dst"]
        e_src = next((e for e in ev if e["event"] == f"{src}:xb_precopy_switch" and e.get("task") == sw["task"]), {})
        e_base = next((e for e in reversed(ev) if e["event"] == f"{dst}:replay_base" and e.get("task") == sw["task"] and e.get("verified")), {})
        t_res = next((e["t"] for e in ev if e["event"] == f"{dst}:resume" and e.get("call") == sw["call"]), None)
        e_res = next((e for e in ev if e["event"] == f"{dst}:resume" and e.get("call") == sw["call"]), {})
        e_ck = next((e for e in reversed(ev) if e["event"] == f"{dst}:sink_sync_check" and t_res is not None and e["t"] is not None and e["t"] <= t_res + 1e-6), {})
        e_cu = next((e for e in reversed(ev) if e["event"] == f"{dst}:replay_caught_up" and t_res is not None and e["t"] is not None and e["t"] <= t_res + 1e-6), {})
        c = {"task": sw["task"], "src": src, "dst": dst, "call": sw["call"], "verdict": e_src.get("verdict"), "base_verified": bool(e_base.get("verified")),
             "cond_equal": e_base.get("cond_equal") is True, "sink_match": e_ck.get("match") is True, "meta_consistent": e_res.get("meta_consistent") is True,
             "order_ok": e_cu.get("order_ok") is True, "switch_call_planned": e_src.get("switch_call_planned"), "switch_call_missed": e_src.get("switch_call_missed")}
        c["ok"] = c["verdict"] == "SINKOK" and all(c[k] for k in ("base_verified", "cond_equal", "sink_match", "meta_consistent", "order_ok"))
        out.append(c)
    calls = sorted((int(r["call"]), r["owner"]) for r in m)
    cs = [x[0] for x in calls]
    contiguous = bool(cs) and cs == list(range(cs[0], cs[-1] + 1))
    owners_ok = True
    bounds = [(int(x["call"]), x["dst"]) for x in sws]
    for call, owner in calls:
        exp = s["path"][0]
        for bc, bd in bounds:
            if call >= bc:
                exp = bd
        owners_ok &= owner == exp
    refused = sum(1 for e in ev if e["event"].endswith(":replay_switch_refused"))
    return {"switches": out, "all_switches_ok": bool(out) and all(x["ok"] for x in out), "calls_contiguous_unique": contiguous and len(cs) == len(set(cs)),
            "owners_match_switches": owners_ok, "refused": refused}


def scenario(rec: dict, d: Path) -> dict:
    """The preregistered mobility: A -> B completes before the first move; B -> C starts and is cancelled; B -> D completes."""
    s = json.load(open(d / "summary.json"))
    ev = R2.events(d)
    sws = s.get("switchovers") or []
    t_move1 = next((e["t"] for e in ev if e["event"] == "move"), None)
    t_sw1 = next((e["t"] for e in ev if e["event"] == "xb_task_done"), None)
    tasks = rec["tasks"]
    bc = [t for t in tasks if t["src"] == "B" and t["dst"] == "C"]
    res = {"two_switches_A_B_then_B_D": [(t["src"], t["dst"]) for t in tasks if t["outcome"] == "completed"] == [("A", "B"), ("B", "D")] and len(sws) == 2,
           "A_B_before_first_move": t_sw1 is not None and t_move1 is not None and t_sw1 < t_move1,
           "B_C_cancelled": len(bc) == 1 and bc[0]["outcome"] == "cancelled",
           "s1": sws[0]["call"] if sws else None, "c0_BC": bc[0]["c0"] if bc else None,
           "final_c0": (rec["final"] or {}).get("c0")}
    res["ok"] = res["two_switches_A_B_then_B_D"] and res["A_B_before_first_move"] and res["B_C_cancelled"]
    return res


def provenance(rec: dict, s1, c0_bc) -> dict:
    pv = (((rec["final"] or {}).get("dest") or {}).get("provenance")) or {}
    get = lambda f: sum(int(n) for k, n in pv.items() if f(*k.split("|")))  # noqa: E731
    return {"raw": pv,
            "old_owner_A_at_s1": get(lambda o, src, v: o == "A" and s1 is not None and int(v) == int(s1)),
            "new_owner_partial_at_C": get(lambda o, src, v: o == "B" and src == "C" and c0_bc is not None and int(v) == int(c0_bc)),
            "fresh_from_B": get(lambda o, src, v: o == "B" and src == "B"),
            "other": get(lambda o, src, v: not ((o == "A" and s1 is not None and int(v) == int(s1)) or (o == "B" and src in ("B", "C"))))}


def handover(rec_dir: Path) -> dict:
    s = json.load(open(rec_dir / "summary.json"))
    oc = (s.get("m3") or {}).get("owner_change") or {}
    hs = oc.get("handovers") or []
    h0 = hs[0] if hs else {}
    imp = h0.get("import") or {}
    return {"n": len(hs), "first": h0, "old_A_new_B": h0.get("old") == "A" and h0.get("new") == "B", "accepted": imp.get("accepted") is True,
            "contiguous": imp.get("contiguous") is True, "version_equal": imp.get("version_equal") is True, "issued_retained": imp.get("issued_retained"),
            "n_entries": h0.get("n_entries"), "bad": oc.get("bad_entries") or [], "lost": oc.get("lost_entries") or [], "rerates": len(oc.get("rerates") or [])}


def full_record(d: Path, chk: bool) -> dict:
    r = R2.run_record(d, chk)
    sc = scenario(r, d)
    r["scenario"] = sc
    r["switch"] = switch_checks(d, r)
    r["handover"] = handover(d)
    r["prov"] = provenance(r, sc["s1"], sc["c0_BC"])
    # remote-serving windows (orchestrator clock, relative to the trigger): the old owner serves the user remotely until the
    # first switch; the owner B serves remotely from the first move until the final switch
    ev = R2.events(d)
    done = [e["t"] for e in ev if e["event"] == "xb_task_done"]
    mv1 = next((e["t"] for e in ev if e["event"] == "move"), None)
    r["windows"] = {"to_first_switch_s": done[0] if done else None, "first_move_to_final_switch_s": (done[-1] - mv1) if (len(done) >= 2 and mv1 is not None) else None}
    return r


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--prefix", default=""); ap.add_argument("--no_validity", action="store_true"); a = ap.parse_args()
    chk = not a.no_validity
    rep = {"phases": {}}
    # ---- P0
    P0 = {}
    for wl in WLS:
        f = OUT / f"p0_{wl}.json"
        if f.exists():
            vd = json.load(open(f))["verdict"]
            P0[wl] = {**vd, "pass": all(vd[k] is True for k in ("R_retained_entries_exact", "M_merge_contiguous", "M_gap_refused", "E_retained_all_exact",
                                                                 "E_cross_owner_all_exact", "N_late_start_all_detected", "S_assemblies_all_exact")),
                      "N_exercised": (vd.get("N_late_start_exposed") or 0) > 0}
    rep["phases"]["P0"] = P0
    # ---- A + C
    AC = {}
    for wl in WLS:
        ds = R2.latest(f"expM3S3A_{wl}", a.prefix)
        if not ds:
            continue
        r = full_record(ds[-1], chk)
        fin, sw, ho, pv = r["final"] or {}, r["switch"], r["handover"], r["prov"]
        dst = fin.get("dest") or {}
        A = {"scenario": r["scenario"]["ok"], "handover_accepted": ho["old_A_new_B"] and ho["accepted"] and ho["contiguous"] and ho["version_equal"],
             "final_mode_m3": fin.get("mode") == "m3", "accepted": bool(dst.get("accepted")), "blocks_equal": dst.get("n_block_mismatch") == 0,
             "positions_equal": dst.get("positions_equal") is True, "cond_equal": dst.get("cond_equal") is True, "old_owner_entries_reused": pv["old_owner_A_at_s1"] >= 1}
        if wl == "bfly":
            A["new_owner_partial_reused"] = pv["new_owner_partial_at_C"] >= 1
        C = {"all_switches_ok": sw["all_switches_ok"], "calls_contiguous_unique": sw["calls_contiguous_unique"], "owners_match_switches": sw["owners_match_switches"],
             "no_refused_switch": sw["refused"] == 0}
        AC[wl] = {"run": r["run"], "valid": r["valid"], "why": r["why"], "A": A, "A_pass": r["valid"] and all(A.values()), "C": C, "C_pass": r["valid"] and all(C.values()),
                  "scenario": r["scenario"], "switches": sw["switches"], "handover": ho, "provenance": pv, "final": fin, "remote_s": r["remote_s"], "bytes": r["bytes"],
                  "rx_bytes_by_link": (r["m3"] or {}).get("rx_bytes_by_link"),
                  "continuity_diagnostic": {"interruption_s": fin.get("interruption_s"), "first_output_s": fin.get("first_output_s"), "readiness_s": fin.get("readiness_s")}}
    rep["phases"]["A_C"] = AC
    # ---- B (dog)
    B = {}
    for fault in FAULTS:
        ds = R2.latest(f"expM3S3B_{fault}", a.prefix)
        if not ds:
            continue
        r = full_record(ds[-1], chk)
        fin, sw, ho, pv = r["final"] or {}, r["switch"], r["handover"], r["prov"]
        dst = fin.get("dest") or {}
        last_task = (r["tasks"] or [{}])[-1].get("m3") or {}
        safe = r["scenario"]["ok"] and sw["all_switches_ok"] and sw["calls_contiguous_unique"] and sw["refused"] == 0 and fin.get("mode") == "m3" and bool(dst.get("accepted")) \
            and dst.get("n_block_mismatch") == 0
        if fault == "version_mismatch":
            handled = ho["accepted"] and ho["version_equal"] is False and ho["issued_retained"] == 0 and pv["old_owner_A_at_s1"] == 0
        elif fault == "corrupt_retained":
            ce = (ho["first"] or {}).get("corrupted_entry")
            bad_a = [b for b in ho["bad"] if b.get("src") == "A" and b.get("e") == ce]
            # the corrupted entry is rejected on receipt (hash differs), so it is never held, advertised or assembled from the
            # old owner's bytes; the final Sink is still exact (in 'safe')
            handled = ce is not None and len(bad_a) >= 1
        else:
            lost_a = [x for x in ho["lost"] if x.get("src") == "A"]
            handled = len(lost_a) >= 1 and last_task.get("missing_expected") == 0
        B[fault] = {"run": r["run"], "valid": r["valid"], "why": r["why"], "handled": handled, "exact_and_safe": safe, "pass": r["valid"] and handled and safe,
                    "final_mode": fin.get("mode"), "dest": dst, "handover": ho, "provenance": pv, "advertise": last_task, "remote_s": r["remote_s"]}
    rep["phases"]["B"] = B
    # ---- D
    Dp = {}
    for wl in WLS:
        cells = {}
        for cond in CONDS:
            recs = [full_record(d, chk) for d in R2.latest(f"expM3S3D_{wl}_{cond}", a.prefix)]
            okr = [x for x in recs if x["valid"] and x["scenario"]["ok"] and x["final_completed"] and (cond == "base" or (x["final"] or {}).get("mode") == "m3")]
            med = lambda f: st.median([f(x) for x in okr]) if okr else None  # noqa: E731
            cells[cond] = {"n_runs": len(recs), "n_valid": len(okr), "invalid": [(x["run"], x["why"], x["scenario"]) for x in recs if x not in okr],
                           "remote_s": med(lambda x: x["remote_s"]), "total_mb": med(lambda x: x["bytes"]["total"] / 1e6), "discarded_mb": med(lambda x: x["bytes"]["discarded"] / 1e6),
                           "forward_mb": med(lambda x: x["bytes"]["forward"] / 1e6), "final_base_mb": med(lambda x: (x["bytes"]["final_base"] or 0) / 1e6),
                           "readiness_s": med(lambda x: (x["final"] or {}).get("readiness_s") or 0.0), "interruption_s": med(lambda x: (x["final"] or {}).get("interruption_s") or 0.0),
                           "reused": med(lambda x: (x["final"] or {}).get("reused") or 0), "from_old_owner": med(lambda x: x["prov"]["old_owner_A_at_s1"]),
                           "from_C": med(lambda x: x["prov"]["new_owner_partial_at_C"]), "s1": med(lambda x: x["scenario"]["s1"] or 0),
                           "to_first_switch_s": med(lambda x: x["windows"]["to_first_switch_s"] or 0.0),
                           "first_move_to_final_switch_s": med(lambda x: x["windows"]["first_move_to_final_switch_s"] or 0.0),
                           "per_rep": [{"run": x["run"], "remote_s": x["remote_s"], "total_mb": x["bytes"]["total"] / 1e6, "final_base_mb": (x["bytes"]["final_base"] or 0) / 1e6,
                                        "readiness_s": (x["final"] or {}).get("readiness_s"), "prov": x["prov"]["raw"], "s1": x["scenario"]["s1"], "c0_BC": x["scenario"]["c0_BC"],
                                        "final_c0": x["scenario"]["final_c0"]} for x in okr]}
        b, c, s2 = cells["base"], cells["ctl"], cells["s2"]
        rr = lambda x, y, k: (x[k] / y[k]) if (x[k] is not None and y[k]) else None  # noqa: E731
        Dp[wl] = {"cells": cells, "s2_remote_vs_base": rr(s2, b, "remote_s"), "s2_total_vs_base": rr(s2, b, "total_mb"), "ctl_remote_vs_base": rr(c, b, "remote_s"),
                  "s2_remote_vs_ctl": rr(s2, c, "remote_s"), "s2_post_window_vs_base": rr(s2, b, "first_move_to_final_switch_s")}
        Dp[wl]["R_D1"] = bool(Dp[wl]["s2_remote_vs_base"] is not None and Dp[wl]["s2_remote_vs_base"] <= 0.80 and Dp[wl]["s2_total_vs_base"] is not None and Dp[wl]["s2_total_vs_base"] <= 1.30)
        Dp[wl]["R_D2"] = bool(Dp[wl]["s2_remote_vs_ctl"] is not None and Dp[wl]["s2_remote_vs_ctl"] <= 0.85)
    rep["phases"]["D"] = Dp
    p0_ok = len(P0) == 2 and all(x["pass"] for x in P0.values())
    a_ok = len(AC) == 2 and all(x["A_pass"] for x in AC.values())
    c_ok = len(AC) == 2 and all(x["C_pass"] for x in AC.values())
    b_ok = len(B) == 3 and all(x["pass"] for x in B.values())
    d_ok = len(Dp) == 2 and all(x["R_D1"] for x in Dp.values())
    rep["gates"] = {"P0": p0_ok, "A": a_ok, "B": b_ok, "C": c_ok, "D_R_D1": d_ok, "D_R_D2": len(Dp) == 2 and all(x["R_D2"] for x in Dp.values())}
    if not (P0 and AC and B):
        verdict = "INCOMPLETE (phases missing)"
    elif not (p0_ok and a_ok):
        verdict = "EXACTNESS ACROSS AN OWNERSHIP CHANGE NOT SHOWN: M3 stays scoped to a source that serves until the final switch"
    elif not (b_ok and c_ok):
        verdict = "CORRECTNESS INCOMPLETE: exact assembly after an ownership change holds, but fault handling or a live switchover failed"
    elif not Dp or not all(x["cells"]["s2"]["n_valid"] and x["cells"]["base"]["n_valid"] for x in Dp.values()):
        verdict = "CORRECT (P0, A, B, C pass); performance phase incomplete"
    elif d_ok:
        verdict = "SUPPORTED: exact, fault-safe and live across an ownership change; remote serving <= 0.80 and total bytes <= 1.30 of the M1 / M2 baseline on both workloads"
    else:
        verdict = "CORRECT BUT NOT FASTER BY THE MARGIN: exact, fault-safe and live across an ownership change; R-D1 fails for a workload"
    rep["verdict"] = verdict
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"m3s3_results{'_' + a.prefix.strip('_') if a.prefix else ''}.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep["gates"], indent=1)); print("verdict:", verdict)
    for wl, x in P0.items():
        print(f"P0 {wl}: pass {x['pass']} (N exercised {x['N_exercised']})")
    for wl, x in AC.items():
        print(f"A/C {wl}: A {x['A_pass']} {x['A']} C {x['C_pass']} {x['C']} prov {x['provenance']['raw']} scenario {x['scenario']} remote {x['remote_s']}")
    for f_, x in B.items():
        print(f"B {f_}: pass {x['pass']} (handled {x['handled']}, safe {x['exact_and_safe']}, final mode {x['final_mode']}, prov {x['provenance']['raw']})")
    for wl, x in Dp.items():
        print(f"D {wl}: s2/base remote {x['s2_remote_vs_base']}, total {x['s2_total_vs_base']}, ctl/base remote {x['ctl_remote_vs_base']}, s2/ctl {x['s2_remote_vs_ctl']}; "
              f"R-D1 {x['R_D1']} R-D2 {x['R_D2']}; n_valid {[x['cells'][c]['n_valid'] for c in CONDS]}")


if __name__ == "__main__":
    main()
