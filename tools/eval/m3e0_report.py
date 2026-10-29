#!/usr/bin/env python3
"""M3-E0 report (osdi/m3e0/preregistration.md): per run, the migration / cancellation timeline, transferred, discarded
and reused bytes, serving behavior (XB delivery accounting), the final migration's time decomposition and headroom over
the destination's ingress bound, Sink correctness, continuity (m1_live_metrics output) and the cross-version
classification (m3e0_crossversion.py output); then the preregistered rules Q1 / Q3 / graph headroom and the
recommendation mapping, applied as written.

    python tools/eval/m3e0_report.py
"""

from __future__ import annotations

import csv
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
from xb_delivery import delivery_metrics, load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/m3e0"
EVAL = ROOT / "results/evaluation"
CONFIGS = (("dog_rho1", "dog"), ("dog_rho2", "dog"), ("bfly_rho1", "bfly"), ("bfly_rho2", "bfly"))
SINK_EQ = 1_727_636_688            # one full base (Sink + metadata), E9 / E10
READY_REF = 22.17                  # E9 baseline single-migration readiness (s), frozen reference of Q1
LINK_BPS = 1e9


def events(d: Path) -> list[dict]:
    out = []
    for r in csv.DictReader(open(d / "events.csv", newline="")):
        out.append({"t": float(r["t_rel"]) if r["t_rel"] not in ("", None) else None, "event": r["event"], **(json.loads(r["detail"]) if r["detail"] else {})})
    return out


def nic_mean(d: Path, node: str, lo: float, hi: float, col: str) -> float | None:
    """Mean of the node's 1 s kernel NIC samples (Mbps) with t_wall in [lo, hi]."""
    p = d / f"node_{node}" / "network.csv"
    if not p.exists():
        return None
    v = [float(r[col]) for r in csv.DictReader(open(p, newline="")) if r.get(col) and lo <= float(r["t_wall"]) <= hi]
    return st.mean(v) if v else None


def run_record(name: str) -> dict:
    ds = sorted((EVAL / f"expM3E0_{name}").glob("policy=*"))
    if not ds:
        return {"error": "run missing"}
    d = ds[-1]
    s, m, nev = load_run(d)
    ev = events(d)
    ok, why = run_validity_xb(s, d)
    D = delivery_metrics(s, m, nev)
    first = lambda name_, **kw: next((e for e in ev if e["event"] == name_ and all(e.get(k) == v for k, v in kw.items())), None)  # noqa: E731
    tasks = []
    for e in (e for e in ev if e["event"] == "xb_task_start"):
        tid, src, dst = e["id"], e["src"], e["dst"]
        canc, done = first("xb_task_cancel", task=tid), first("xb_task_done", task=tid)
        base = first(f"{src}:replay_base_sent", task=tid)
        rnd = first(f"{src}:xb_precopy_round", task=tid)
        held = first(f"{dst}:replay_base", task=tid)
        crec = first(f"{src}:xb_precopy_cancelled", task=tid)
        sw = first(f"{src}:xb_precopy_switch", task=tid)
        ready = first(f"{src}:replay_ready", task=tid)
        logrec = crec or sw or {}
        nheld = ((held or {}).get("frags_verified") or {}).get("sink")
        t_end = (canc or done or {}).get("t")
        tasks.append({"task": tid, "src": src, "dst": dst, "t_start": e["t"], "t_end": t_end, "duration_s": (t_end - e["t"]) if t_end is not None else None,
                      "outcome": "cancelled" if canc else ("completed" if done else "open"), "c0": base and base.get("call"),
                      "base_mode": base and base.get("mode"), "dest_version": e.get("dest_version"),
                      "base_bytes_sent": base and base.get("bytes"), "sink_frags_sent": base and base.get("sink_frags_sent"), "sink_frags_total": base and base.get("sink_frags_total"),
                      "round_snapshot_s": rnd and rnd.get("snapshot_s"), "round_send_s": rnd and rnd.get("send_s"),
                      "dest_sink_frags_verified": nheld, "dest_base_verified": held and held.get("verified"), "t_dest_round1_end": held and held["t"],
                      "log_calls": logrec.get("log_calls"), "log_bytes": logrec.get("log_bytes"), "patches": logrec.get("patches"), "patch_bytes": logrec.get("patch_bytes"),
                      "source_call_at_cancel": crec and crec.get("source_call"), "t_replay_ready": ready and ready["t"], "switch_call": sw and sw.get("call")})
    canc = [t for t in tasks if t["outcome"] == "cancelled"]
    fin = next((t for t in reversed(tasks) if t["outcome"] == "completed"), None)
    moves = [{"t": e["t"], "to": e.get("to")} for e in ev if e["event"] == "move"]
    discarded = sum(int(t["base_bytes_sent"] or 0) + int(t["log_bytes"] or 0) for t in canc)
    rec = {"run": d.name, "valid": ok, "why": why, "moves": moves, "tasks": tasks, "n_cancelled": len(canc), "final_completed": fin is not None,
           "transferred_bytes_all_tasks": sum(int(t["base_bytes_sent"] or 0) + int(t["log_bytes"] or 0) for t in tasks),
           "discarded_bytes": discarded, "discarded_sinks": discarded / SINK_EQ,
           "discarded_base_bytes": sum(int(t["base_bytes_sent"] or 0) for t in canc), "discarded_log_bytes": sum(int(t["log_bytes"] or 0) for t in canc),
           "held_verified_at_abandoned_bytes": None,
           "reused_bytes_measured": sum(int(t["base_bytes_sent"] or 0) for t in tasks if t["base_mode"] == "delta"),
           "serving": {"ttfo_local": D["ttfo_local"], "delivery_gap_s": D["delivery_gap_s"], "remote_chunks": D["remote_chunks"], "remote_wall_s": D["remote_wall_s"],
                       "remote_stretches": D["remote_stretches"], "output_equivalence": D["output_equivalence"], "trajectory_final": D["trajectory_final"]},
           "cutover": s.get("cutover"), "validation": {k: v for k, v in (s.get("validation") or {}).items() if k != "gpu0_before_run"}}
    cs = [float(r["chunk_s"]) for r in m if r.get("chunk_s") not in ("", None)]
    rec["per_call_service_s"] = {"n": len(cs), "median": st.median(cs) if cs else None, "p95": sorted(cs)[int(0.95 * (len(cs) - 1))] if cs else None, "max": max(cs) if cs else None}
    if fin is not None:
        t0 = fin["t_start"]
        base_ev = first(f"{fin['dst']}:replay_base", task=fin["task"])
        ss = first(f"{fin['dst']}:sink_sync_check")
        fo = next((e for e in ev if e["event"] == f"{fin['dst']}:first_output"), None)
        cap = (s.get("bw_mbps") or LINK_BPS / 1e6)
        ingress_s = int(fin["base_bytes_sent"] or 0) * 8 / (cap * 1e6)   # the base alone through the destination's ingress cap
        rnd_t = next((e["t"] for e in ev if e["event"] == f"{fin['src']}:xb_precopy_round" and e.get("task") == fin["task"]), None)
        hi = s["t0_wall"] + rnd_t if rnd_t is not None else None
        lo = hi - float(fin["round_send_s"]) if (hi is not None and fin["round_send_s"] is not None) else None
        rx = nic_mean(d, fin["dst"], lo, hi, "net_rx_mbps") if lo is not None else None
        tx = nic_mean(d, fin["src"], lo, hi, "net_tx_mbps") if lo is not None else None
        unused = float(fin["round_send_s"]) * max(0.0, 1 - rx / cap) if rx is not None else None
        rec["final"] = {"task": fin["task"], "t_start": t0, "chase_s": t0, "base_ready_s": base_ev and base_ev["t"] - t0, "readiness_s": fin["t_replay_ready"] and fin["t_replay_ready"] - t0,
                        "first_output_s": fo and fo["t"] - t0, "trigger_to_first_output_s": fo and fo["t"], "switch_call": fin["switch_call"],
                        "round_snapshot_s": fin["round_snapshot_s"], "base_send_s": fin["round_send_s"], "base_ingress_bound_s": ingress_s,
                        "base_excess_over_ingress_bound_s": (fin["round_send_s"] - ingress_s) if fin["round_send_s"] is not None else None,
                        "dst_rx_mean_mbps_during_base": rx, "src_tx_mean_mbps_during_base": tx,
                        "graph_headroom_s": unused,   # preregistered UB: unused destination-ingress capacity during the final base transfer
                        "replay_catchup_s": (fin["t_replay_ready"] - base_ev["t"]) if (fin["t_replay_ready"] and base_ev) else None,
                        "log_bytes": fin["log_bytes"], "patch_bytes": fin["patch_bytes"],
                        "sink_sync": ss and {k: ss.get(k) for k in ("call", "match", "n_block_mismatch", "positions_equal")},
                        "base_verified": base_ev and base_ev.get("verified"), "interruption_s": (s.get("cutover") or {}).get("interruption_s")}
        rs_ = D["remote_wall_s"] or 0.0
        f_ = rec["final"]
        rec["remote_serving_decomposition"] = {"remote_wall_s": rs_, "chase_s": t0, "final_snapshot_s": fin["round_snapshot_s"], "final_base_send_s": fin["round_send_s"],
                                               "final_replay_catchup_s": f_["replay_catchup_s"], "final_ready_to_first_output_s": (f_["first_output_s"] - f_["readiness_s"]) if (f_["first_output_s"] and f_["readiness_s"]) else None,
                                               "chase_share": (t0 / rs_) if rs_ else None, "graph_ub_share": (unused / rs_) if (rs_ and unused is not None) else None}
    return rec


def main():
    rep = {"configs": {}}
    for name, wl in CONFIGS:
        R = run_record(name)
        xf = OUT / f"e0x_{wl}.json"
        if "error" not in R and xf.exists():
            X = json.load(open(xf))["runs"].get(R["run"])
            R["crossversion"] = X
            if X:
                R["held_verified_at_abandoned_bytes"] = sum(x["held_bytes"] for x in X["tasks"])
        mf = OUT / f"e0_metrics_{name}.json"
        if "error" not in R and mf.exists():
            mm = next(iter(json.load(open(mf))["runs"].values()), {})
            R["continuity"] = {k: mm.get(k) for k in ("M", "rules", "v1_reset", "v1_reset_ref_same_call", "D_c", "C_c", "late_D_c", "warp_excess", "frame_diff_ratio", "error")}
        rep["configs"][name] = R
    # ---- preregistered rules (section 5 of the preregistration), applied as written
    C = {k: v for k, v in rep["configs"].items() if "error" not in v}
    q1 = {k: bool(v["n_cancelled"] >= 1 and v["discarded_sinks"] >= 0.5 and (v["serving"]["remote_wall_s"] or 0) >= 1.5 * READY_REF) for k, v in C.items()}
    rep["Q1"] = {"per_config": q1, "supported": sum(q1.values()) >= 3 and len(C) == 4}

    def frac_union(v, keys):
        u = ((v.get("crossversion") or {}).get("union_over_abandoned_holders_vs_final")) or None
        return None if u is None else sum(u[k]["bytes"] for k in keys) / SINK_EQ
    q3 = {k: frac_union(v, ("identical",)) for k, v in C.items()}
    strict = {k: sum(x["held_bytes"] for x in (v.get("crossversion") or {}).get("tasks", []) if x.get("strict_same_version")) / SINK_EQ if v.get("crossversion") else None for k, v in C.items()}
    rep["Q3"] = {"same_content_union_sinks": q3, "strict_same_version_sinks": strict,
                 "same_version_sufficient": sum(1 for k in C if ((q3[k] or 0) + (strict[k] or 0)) >= 0.25) >= 3 and all(q3[k] is not None for k in C)}
    rep["cross_version_union_sinks"] = {k: frac_union(v, ("identical", "shift_only")) for k, v in C.items()}
    G = {k: (v.get("final") or {}).get("graph_headroom_s") for k, v in C.items()}
    share = {k: (v.get("remote_serving_decomposition") or {}).get("graph_ub_share") for k, v in C.items()}
    meaningful = {k: bool(G[k] is not None and G[k] >= 2.0 and share[k] is not None and share[k] >= 0.10) for k in C}
    rep["Q4_graph_headroom"] = {"ub_s": G, "ub_share_of_remote_serving": share, "meaningful": meaningful, "meaningful_count": sum(meaningful.values()),
                                "chase_share": {k: (v.get("remote_serving_decomposition") or {}).get("chase_share") for k, v in C.items()}}
    xv = sum(1 for k in C if (rep["cross_version_union_sinks"][k] or 0) >= 0.25)
    if not rep["Q1"]["supported"]:
        rec = "NO-GO / REASSESS (Q1 not supported: repeated mobility is not a meaningful problem here)"
    elif rep["Q4_graph_headroom"]["meaningful_count"] < 3:
        rec = "NO-GO / REASSESS (Q1 supported, but the restoration-graph upper bound is < 2 s or < 10 % of remote serving in more than one configuration)"
    elif rep["Q3"]["same_version_sufficient"]:
        rec = "GO - same-version integration"
    elif xv >= 3:
        rec = "EXPAND - versioned holders"
    else:
        rec = "NO-GO / REASSESS (headroom exists, but the reusable state at abandoned holders is < 0.25 Sink even with cross-version reconstruction)"
    rep["recommendation_by_rule"] = rec
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "e0_report.json").write_text(json.dumps(rep, indent=1, default=str))
    for k, v in rep["configs"].items():
        if "error" in v:
            print(k, v["error"]); continue
        f = v.get("final") or {}
        print(f"{k:10s} valid {v['valid']} cancelled {v['n_cancelled']} discarded {v['discarded_bytes'] / 1e6:.1f} MB ({v['discarded_sinks']:.2f} Sink) "
              f"remote {v['serving']['remote_wall_s']:.1f} s; final: chase {f.get('chase_s')}, base {f.get('base_ready_s')}, ready {f.get('readiness_s')}, "
              f"UB {f.get('graph_headroom_s')}, interruption {f.get('interruption_s')}, SINK {f.get('sink_sync')}")
    print(json.dumps({k: rep[k] for k in ("Q1", "Q3", "cross_version_union_sinks", "Q4_graph_headroom", "recommendation_by_rule")}, indent=1, default=str))


if __name__ == "__main__":
    main()
