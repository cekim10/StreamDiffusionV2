#!/usr/bin/env python3
"""Fig. 7 (osdi/fig7/preregistration.md): OTTER's single-migration performance against Full, Llumnix-style P-full and
ServerlessLLM-style R-full. Applies the preregistered rules as written.

Per run: validity (frozen XB validity; Full by the XB aggregation's rule), C1 state correctness as each method claims it,
the three Fig. 7 metrics (TTFO-local, delivery gap, transmitted bytes; `xb_delivery.py` / `aggregate_xb.py`), the cutover
interruption (diagnostic, every method), C2 output fidelity (descriptive, mandatory), and the NIC cross-check
(diagnostic). Per (method, workload): medians and IQR over valid reps. F7-H1 / F7-H2 by medians, on both workloads.

    python tools/eval/fig7_report.py                       # -> results/evaluation/osdi/fig7/fig7_results.{json,md}
    python tools/eval/fig7_report.py --sanity              # first-run check: every run so far, C1 / metrics / bytes in detail
    python tools/eval/fig7_report.py --prefix _dryrun_ --dry
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
from aggregate_xb import transmitted_bytes  # noqa: E402
from xb_delivery import delivery_metrics, load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/fig7"
WORKLOADS = {"dog": "Low-refresh", "bfly": "High-refresh"}
METHODS = ("full", "precopy_full", "recompute_full", "precopy_replay")   # figure order
LABEL = {"full": "Full", "precopy_full": "Llumnix-style", "recompute_full": "ServerlessLLM-style", "precopy_replay": "OTTER"}
BASELINES = ("full", "precopy_full", "recompute_full")
N_REPS = 5
FIDELITY_WINDOW = 24   # calls after the switch for the minimum PSNR (C2)
HEADER_FACTOR = (1388 + 66) / 1388   # TCP/IP + Ethernet headers per 1388 B segment (measured MSS); NIC / payload ratio


def q(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summary_stats(xs):
    xs = [x for x in xs if x is not None]
    return {"median": st.median(xs) if xs else None, "q1": q(xs, 0.25), "q3": q(xs, 0.75), "n": len(xs), "values": xs}


def validity(s, d, dry):
    if s["policy"] == "full":   # not an XB method: the XB aggregation judged it with the W / R / N rules (aggregate_xb.run_record)
        from wrn_validity import run_validity_wrn
        return run_validity_wrn(s, d, dry=dry)
    return run_validity_xb(s, d, dry=dry)


def cutover_interruption(rows, src="A", dst="B"):
    """Last chunk delivered by the source before the destination's first chunk -> that first chunk (delivery log)."""
    first = next((r for r in rows if r["owner"] == dst), None)
    if first is None:
        return None
    last = [r["t"] for r in rows if r["owner"] == src and r["t"] <= first["t"]]
    return first["t"] - (max(last) if last else 0.0)


def delivered_rows(s, m):
    rows = []
    for r in m:
        try:
            t = float(r["t_out_rel"])
        except (TypeError, ValueError):
            continue
        if str(r.get("missing")) in ("True", "true") or t < 0:
            continue
        ps = r.get("psnr")
        rows.append({"call": int(r["call"]), "owner": r["owner"], "t": t, "psnr": float(ps) if ps not in ("", None) else None,
                     "ref_match": {"True": True, "False": False}.get(str(r.get("ref_match")))})
    return sorted(rows, key=lambda x: x["t"])


def c1(s, ev, rows):
    """State correctness as the method claims it (prereg section 6)."""
    v = s.get("validation") or {}
    pol = s["policy"]
    after = [r for r in rows if r["owner"] == "B"]
    bit = [r["ref_match"] for r in after if r["ref_match"] is not None]
    out = {"output_bitexact_calls": f"{sum(bit)}/{len(bit)}"}
    if pol == "full":   # Full records its checks in the W / R / N fields (no per-call ref_match)
        checks = {"full_state_digests_ok": v.get("full_state_digests_ok") is True, "final_sink_digest_matches_source": v.get("final_sink_digest_matches_source") is True,
                  "output_bitexact_after_resume": v.get("full_bit_exact_after_resume") is True}
        out.update(claim="whole state exact", checks=checks)
    elif pol in ("precopy_full", "recompute_full"):
        checks = {"switchover": bool(v.get("switchovers_verified")) if pol != "recompute_full" else bool(v.get("n_switchovers")),
                  "output_bitexact_after_switch": bool(bit) and all(bit)}
        if pol == "recompute_full":
            checks["inputs_exact"] = v.get("inputs_exact_at_switchovers") is True and v.get("input_check") is True
        out.update(claim="whole state exact", checks=checks)
    else:
        sc = next((e for e in ev if e["node"] == "B" and e["event"] == "sink_sync_check"), {})
        checks = {"verdict_SINKOK_or_verified_fallback": v.get("replay_resumed_on_digest_equal_sink_or_fallback") is True,
                  "sink_blocks_0_of_360_mismatching": sc.get("n_block_mismatch") == 0 or (v.get("replay_fallback_used") is True and v.get("replay_resumed_on_digest_equal_sink_or_fallback") is True),
                  "positions_equal": sc.get("positions_equal") is True or v.get("replay_fallback_used") is True,
                  "base_verified": v.get("replay_base_verified") is True, "conditioning_equal": v.get("replay_conditioning_equal") is True,
                  "replay_order_ok": v.get("replay_order_ok") is True, "no_lost_or_duplicated_calls": v.get("replay_no_lost_or_duplicated_calls") is True,
                  "meta_consistent_at_switch": v.get("replay_meta_consistent_at_switch") is True}
        out.update(claim="Sink exact at the switch; recent KV rebuilt by replay", checks=checks, verdict=v.get("replay_verdict"),
                   fallback=v.get("replay_fallback_used"), n_block_mismatch=sc.get("n_block_mismatch"))
    out["pass"] = all(out["checks"].values())
    return out


def c2(rows):
    after = [r for r in rows if r["owner"] == "B" and r["psnr"] is not None]
    ps = [r["psnr"] for r in after]
    return {"first_call_psnr": ps[0] if ps else None, f"min_psnr_first_{FIDELITY_WINDOW}": min(ps[:FIDELITY_WINDOW]) if ps else None,
            f"median_psnr_first_{FIDELITY_WINDOW}": st.median(ps[:FIDELITY_WINDOW]) if ps else None,
            "terminal_median_psnr": st.median(ps[-10:]) if len(ps) >= 10 else None, "calls_scored": len(ps)}


def byte_parts(s, ev):
    rounds = [int(e.get("dirty_bytes") or 0) for e in ev if e["event"] == "xb_precopy_round"]
    sw = [e for e in ev if e["event"] == "xb_precopy_switch"]
    return {"rounds": rounds, "final": sum(int(e.get("final_bytes") or 0) for e in sw), "log": sum(int(e.get("log_bytes") or 0) for e in sw),
            "patches": sum(int(e.get("patch_bytes") or 0) for e in sw), "inputs": int((s.get("inputs") or {}).get("bytes_sent") or 0),
            "switch_reason": sw[-1].get("reason") if sw else None}


def nic_check(d, s, rows, tx):
    """Destination NIC receive bytes from the trigger to B's first chunk (+2 s), over the accounted bytes (diagnostic)."""
    p = d / "node_B/network.csv"
    first = next((r for r in rows if r["owner"] == "B"), None)
    if not p.exists() or first is None or not tx:
        return None
    if s.get("t0_wall") is None:
        return None
    t0, t1 = s["t0_wall"] - 1, s["t0_wall"] + first["t"] + 2
    nr = list(csv.DictReader(open(p)))
    rx = sum(float(b["net_rx_mbps"] or 0) * 1e6 / 8 * (float(b["t_wall"]) - float(a["t_wall"]))
             for a, b in zip(nr, nr[1:]) if float(a["t_wall"]) >= t0 and float(b["t_wall"]) <= t1)
    return {"nic_rx_bytes": rx, "nic_over_accounted": rx / tx, "after_header_factor": rx / tx / HEADER_FACTOR}


def run_record(d: Path, dry: bool) -> dict:
    s, m, ev = load_run(d)
    ok, why = validity(s, d, dry)
    D = delivery_metrics(s, m, ev)
    rows = delivered_rows(s, m)
    tx = transmitted_bytes(s, ev)
    C1 = c1(s, ev, rows)
    served = D["ttfo_local_final_s"] is not None
    rec = {"run": d.name, "policy": s["policy"], "rep": s.get("rep"), "valid": ok and C1["pass"], "validity_why": why, "c1": C1,
           "failed": not served, "ttfo_local_s": D["ttfo_local_final_s"], "delivery_gap_s": D["delivery_gap_s"], "delivery_gap_at_s": D["delivery_gap_at_s"],
           "tx_bytes": tx, "bytes": byte_parts(s, ev), "cutover_interruption_s": cutover_interruption(rows),
           "orchestrator_interruption_s": (s.get("cutover") or {}).get("interruption_s"), "remote_wall_s": D["remote_wall_s"], "c2": c2(rows),
           "nic": None if dry else nic_check(d, s, rows, tx)}
    return rec


def collect(prefix, dry):
    recs = {}
    for w in WORKLOADS:
        base = EVAL / f"{prefix}expF7_{w}"
        recs[w] = [run_record(d, dry) for d in sorted(base.glob("policy=*")) if (d / "summary.json").exists()]
    return recs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", default=""); ap.add_argument("--dry", action="store_true"); ap.add_argument("--sanity", action="store_true")
    a = ap.parse_args()
    recs = collect(a.prefix, a.dry)
    if a.sanity:
        for w, rs in recs.items():
            for r in rs:
                b = r["bytes"]
                print(f"== {w} {LABEL.get(r['policy'], r['policy'])} rep {r['rep']}: valid {r['valid']} {r['validity_why']}")
                print(f"   C1 {r['c1']['claim']}: pass {r['c1']['pass']} {r['c1']['checks']} bit-exact calls {r['c1']['output_bitexact_calls']}"
                      + (f" verdict {r['c1'].get('verdict')} mismatching {r['c1'].get('n_block_mismatch')} fallback {r['c1'].get('fallback')}" if r["policy"] == "precopy_replay" else ""))
                print(f"   TTFO-local {r['ttfo_local_s']} | gap {r['delivery_gap_s']} at {r['delivery_gap_at_s']} | cutover {r['cutover_interruption_s']} (orch {r['orchestrator_interruption_s']})")
                print(f"   bytes {r['tx_bytes']} = rounds {b['rounds']} + final {b['final']} + log {b['log']} (patches {b['patches']}) + inputs {b['inputs']}; switch reason {b['switch_reason']}")
                print(f"   C2 {r['c2']} | NIC {r['nic']}")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    cells, verdicts = {}, {}
    for w, rs in recs.items():
        cells[w] = {}
        for pol in METHODS:
            mine = [r for r in rs if r["policy"] == pol]
            ok = [r for r in mine if r["valid"] and not r["failed"]]
            cells[w][pol] = {"n_runs": len(mine), "n_valid": len(ok), "n_failed": sum(r["failed"] for r in mine),
                             "invalid": [(r["run"], r["validity_why"], {k: x for k, x in r["c1"]["checks"].items() if not x}) for r in mine if not r["valid"]],
                             **{k: summary_stats([r[k] for r in ok]) for k in ("ttfo_local_s", "delivery_gap_s", "cutover_interruption_s", "remote_wall_s")},
                             "tx_gb": summary_stats([r["tx_bytes"] / 1e9 for r in ok if r["tx_bytes"] is not None]),
                             "c2": {k: summary_stats([r["c2"][k] for r in ok]) for k in ("first_call_psnr", f"min_psnr_first_{FIDELITY_WINDOW}", "terminal_median_psnr")},
                             "nic_after_header_factor": summary_stats([(r["nic"] or {}).get("after_header_factor") for r in ok])}
        c = cells[w]
        evaluable = all(c[p]["n_valid"] >= N_REPS for p in METHODS)
        med = lambda p, k: c[p][k]["median"]  # noqa: E731
        best_gap = min((med(p, "delivery_gap_s") for p in BASELINES if med(p, "delivery_gap_s") is not None), default=None)
        best_ttfo = min((med(p, "ttfo_local_s") for p in BASELINES if med(p, "ttfo_local_s") is not None), default=None)
        o_gap, o_ttfo = med("precopy_replay", "delivery_gap_s"), med("precopy_replay", "ttfo_local_s")
        verdicts[w] = {"evaluable": evaluable,
                       "H1_gap_ratio": (o_gap / best_gap) if (o_gap is not None and best_gap) else None,
                       "H1": evaluable and o_gap is not None and best_gap is not None and o_gap <= 0.25 * best_gap,
                       "H2_ttfo_ratio": (o_ttfo / best_ttfo) if (o_ttfo is not None and best_ttfo) else None,
                       "H2": evaluable and o_ttfo is not None and best_ttfo is not None and o_ttfo < best_ttfo,
                       "bytes_vs": {LABEL[p]: (c["precopy_replay"]["tx_gb"]["median"] / c[p]["tx_gb"]["median"])
                                    if c["precopy_replay"]["tx_gb"]["median"] and c[p]["tx_gb"]["median"] else None for p in BASELINES}}
    ev_all = all(v["evaluable"] for v in verdicts.values())
    H1 = ev_all and all(v["H1"] for v in verdicts.values())
    H2 = ev_all and all(v["H2"] for v in verdicts.values())
    concl = ("NOT EVALUABLE (a cell has fewer than 5 valid reps)" if not ev_all else
             "H1 and H2 hold: OTTER's single migration stalls far less and reaches local service sooner than every exact baseline" if H1 and H2 else
             "H1 holds, H2 fails: stalls far less, but not sooner local" if H1 else "H1 fails: no single-migration advantage on stalls")
    res = {"cells": cells, "verdicts": verdicts, "F7_H1": H1, "F7_H2": H2, "conclusion": concl, "runs": recs}
    (OUT / f"{a.prefix}fig7_results.json").write_text(json.dumps(res, indent=1, default=str))
    f = lambda x, n=2: "-" if x is None else f"{x:.{n}f}"  # noqa: E731
    L = [f"# Fig. 7 results ({'dry' if a.dry else 'testbed'})", "", f"**{concl}**", "",
         "Medians [IQR] over valid reps. TTFO-local, delivery gap and bytes are the Fig. 7 metrics; cutover interruption, remote serving, C2 and NIC are diagnostics.", ""]
    for w in WORKLOADS:
        L += [f"## {WORKLOADS[w]} ({w})", "", "| method | valid / runs (failed) | TTFO-local (s) | delivery gap (s) | bytes (GB) | cutover (s) | C2 first / min24 / terminal (dB) |", "|---|---|---|---|---|---|---|"]
        for p in METHODS:
            x = cells[w][p]
            s_ = lambda k: f"{f(x[k]['median'])} [{f(x[k]['q1'])}-{f(x[k]['q3'])}]"  # noqa: E731
            L.append(f"| {LABEL[p]} | {x['n_valid']} / {x['n_runs']} ({x['n_failed']}) | {s_('ttfo_local_s')} | {s_('delivery_gap_s')} | "
                     f"{f(x['tx_gb']['median'], 3)} [{f(x['tx_gb']['q1'], 3)}-{f(x['tx_gb']['q3'], 3)}] | {s_('cutover_interruption_s')} | "
                     f"{f(x['c2']['first_call_psnr']['median'], 1)} / {f(x['c2'][f'min_psnr_first_{FIDELITY_WINDOW}']['median'], 1)} / {f(x['c2']['terminal_median_psnr']['median'], 1)} |")
        v = verdicts[w]
        L += ["", f"H1 gap ratio {f(v['H1_gap_ratio'], 3)} -> {v['H1']}; H2 TTFO ratio {f(v['H2_ttfo_ratio'], 3)} -> {v['H2']}; OTTER bytes / method {json.dumps({k: (round(r, 3) if r else None) for k, r in v['bytes_vs'].items()})}", ""]
    (OUT / f"{a.prefix}fig7_results.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
