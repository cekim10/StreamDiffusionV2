#!/usr/bin/env python3
"""Fig. 11 (osdi/fig11/preregistration.md): repeated mobility A -> B -> C -> D on the wall clock. Applies the preregistered
rules as written.

Per run: validity (XB validity; Full by the W / R / N rule, as Fig. 7), "not converged" when the final edge never serves
locally (kept, not excluded), C1 per method, time without local service N (sum over the edge changes of change -> first
output at the new edge, truncated at the next change / the last delivery) split into remote-served and interrupted, final
readiness R_D (TTFO-local at D), per-move TTFO-local, gap, total stall (Fig. 8 rule), bytes.
F11-H1 median N(OTTER) <= 0.5 x min(median N of Full, P-full, R-full); F11-H2 median N(OTTER) <= 0.80 x median N(OTTER
w/o staging); F11-H3 median R_D(OTTER) < median R_D(OTTER w/o staging). Each scenario x workload.

    python tools/eval/fig11_report.py            # -> results/evaluation/osdi/fig11/fig11_results.{json,md}
    python tools/eval/fig11_report.py --sanity
    python tools/eval/fig11_report.py --prefix _dryrun_ --dry
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from aggregate_xb import transmitted_bytes  # noqa: E402
from fig7_report import delivered_rows  # noqa: E402
from fig8_report import stalls  # noqa: E402
from xb_delivery import delivery_metrics, load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/fig11"
SCENARIOS = {"chain": "Chain", "cancel": "Cancel"}
WORKLOADS = {"dog": "Low-refresh", "bfly": "High-refresh"}
METHODS = ("full", "pfull", "rfull", "base", "otter")
LABEL = {"full": "Full", "pfull": "Llumnix-style", "rfull": "ServerlessLLM-style", "base": "OTTER w/o staging", "otter": "OTTER"}
EXTERNAL = ("full", "pfull", "rfull")
N_REPS = 3
H1_RATIO, H2_RATIO = 0.5, 0.80
NONCONV = {"the final edge never served", "cut by max_run_s", "no switchover happened", "a switchover was not verified (or none happened)"}


def method_of(d: Path, policy: str) -> str | None:
    return {"full": "full", "precopy_full": "pfull", "recompute_full": "rfull"}.get(policy) or \
        ({"precopy_replay": "otter" if "_m3=" in d.name else "base"}.get(policy))


def validity(s, d, dry):
    if s["policy"] == "full":
        from wrn_validity import run_validity_wrn
        return run_validity_wrn(s, d, dry=dry)
    return run_validity_xb(s, d, dry=dry)


def c1(m, s, ev):
    v = s.get("validation") or {}
    if m == "full":
        ch = {"full_state_digests_ok": v.get("full_state_digests_ok") is True, "final_sink_digest_matches_source": v.get("final_sink_digest_matches_source") is True}
    elif m == "pfull":
        ch = {"switchovers_verified": v.get("switchovers_verified") is True}
    elif m == "rfull":
        ch = {"inputs_exact_at_switchovers": v.get("inputs_exact_at_switchovers") is True, "input_check": v.get("input_check") is True}
    else:
        checks = [e for e in ev if e["event"] == "sink_sync_check"]
        sw = [e for e in ev if e["event"] == "xb_precopy_switch"]
        fb_ok = all(e.get("verdict") == "SINKOK" or (e.get("verdict") == "SINKNO" and e.get("fallback_bytes")) for e in sw)
        ch = {"every_switch_SINKOK_or_verified_fallback": bool(sw) and fb_ok,
              "sink_blocks_0_of_360_mismatching": bool(checks) and all(e.get("n_block_mismatch") == 0 or not e.get("match") and fb_ok for e in checks),
              "every_switch_verified": all(e.get("ok") for e in ev if e["event"] == "xb_switch_verified"),
              "replay_order_ok": v.get("replay_order_ok") is True, "no_lost_or_duplicated_calls": v.get("replay_no_lost_or_duplicated_calls") is True}
    return {"checks": ch, "pass": all(ch.values())}


def no_local(D, t_end):
    """Time without local service: per edge change, change -> first output at the new edge, truncated at the next change
    (and at the last delivery for the final edge)."""
    tt = D["ttfo_local"]
    n, per = 0.0, []
    for i, x in enumerate(tt):
        nxt = tt[i + 1]["t_change"] if i + 1 < len(tt) else (t_end if t_end is not None else x["t_change"])
        w = nxt - x["t_change"] if x["ttfo_local_s"] is None else min(x["ttfo_local_s"], nxt - x["t_change"])
        w = max(0.0, w); per.append({"edge": x["edge"], "t_change": x["t_change"], "ttfo_local_s": x["ttfo_local_s"], "without_local_s": w}); n += w
    return n, per


def run_record(d: Path, dry: bool) -> dict | None:
    s, m, ev = load_run(d)
    meth = method_of(d, s["policy"])
    if meth is None:
        return None
    ok, why = validity(s, d, dry)
    D = delivery_metrics(s, m, ev)
    rows = delivered_rows(s, m)
    t_end = D["t_last_delivery_s"]
    N, per = no_local(D, t_end)
    converged = D["ttfo_local"][-1]["ttfo_local_s"] is not None if D["ttfo_local"] else False
    C1 = c1(meth, s, ev)
    status = "valid" if (ok and C1["pass"]) else ("not_converged" if (not converged and set(why) <= NONCONV) else "invalid")
    rem = min(D["remote_wall_s"], N)
    sw_d = [e for e in ev if e["node"] == "D" and e["event"] in ("resume",)]
    return {"run": d.name, "method": meth, "rep": s.get("rep"), "status": status, "validity_why": why, "c1": C1, "converged": converged,
            "N_s": N, "remote_served_s": rem, "interrupted_s": N - rem, "per_move": per, "R_D_s": D["ttfo_local_final_s"],
            "gap_s": D["delivery_gap_s"], "total_stall_s": stalls(rows)["total_stall_s"] if rows else None, "tx_bytes": transmitted_bytes(s, ev),
            "moves": [mv.get("t_req") for mv in s.get("moves", [])], "stop_reason": (s.get("validation") or {}).get("stop_reason"),
            "m3": {k: s.get(k) for k in ("m3",) if s.get(k) is not None}, "d_resumes": len(sw_d)}


def collect(prefix, dry):
    out = {}
    for sc in SCENARIOS:
        for w in WORKLOADS:
            out[(sc, w)] = [r for d in sorted((EVAL / f"{prefix}expF11_{sc}_{w}").glob("policy=*")) if (d / "summary.json").exists()
                            for r in [run_record(d, dry)] if r is not None]
    return out


def stats(xs):
    xs = [x for x in xs if x is not None]
    return {"median": st.median(xs) if xs else None, "min": min(xs) if xs else None, "max": max(xs) if xs else None, "n": len(xs), "values": xs}


def cells(C):
    R = {}
    for key, rs in C.items():
        R[key] = {}
        for m in METHODS:
            mine = [r for r in rs if r["method"] == m]
            kept = [r for r in mine if r["status"] in ("valid", "not_converged")]
            R[key][m] = {"n_kept": len(kept), "n_runs": len(mine), "n_not_converged": sum(r["status"] == "not_converged" for r in kept),
                         **{k: stats([r[k] for r in kept]) for k in ("N_s", "remote_served_s", "interrupted_s", "R_D_s", "gap_s", "total_stall_s", "tx_bytes")},
                         "invalid": [(r["run"], r["validity_why"], {k: v for k, v in r["c1"]["checks"].items() if not v}) for r in mine if r["status"] == "invalid"],
                         "runs": mine}
    return R


def verdicts(R):
    v, agg = {}, {}
    for key, c in R.items():
        ev = all(c[m]["n_kept"] >= N_REPS for m in METHODS)
        if not ev:
            v[key] = {"evaluable": False}; continue
        N = {m: c[m]["N_s"]["median"] for m in METHODS}
        RD = {m: c[m]["R_D_s"]["median"] for m in ("base", "otter")}
        best = min(N[m] for m in EXTERNAL)
        v[key] = {"evaluable": True, "N": N, "R_D": RD,
                  "F11_H1": {"ratio": N["otter"] / best, "holds": N["otter"] <= H1_RATIO * best},
                  "F11_H2": {"ratio": N["otter"] / N["base"], "holds": N["otter"] <= H2_RATIO * N["base"]},
                  "F11_H3": {"holds": RD["otter"] is not None and RD["base"] is not None and RD["otter"] < RD["base"]}}
    for h in ("F11_H1", "F11_H2", "F11_H3"):
        xs = [x.get(h) for x in v.values()]
        agg[h] = None if any(x is None for x in xs) else all(x["holds"] for x in xs)
    return v, agg


def f(x, n=1):
    return "-" if x is None else f"{x:.{n}f}"


def md(R, v, agg):
    word = {True: "SUPPORTED", False: "NOT SUPPORTED", None: "NOT EVALUABLE"}
    L = ["# Fig. 11 results", "", "Rules: `preregistration.md`. " + "; ".join(f"**{h.replace('_', '-')}: {word[agg[h]]}**" for h in agg), ""]
    for (sc, w), c in R.items():
        L += [f"## {SCENARIOS[sc]}, {WORKLOADS[w]} ({w})", "", "| method | kept / runs (not conv.) | N without local (s) | remote-served (s) | interrupted (s) | R_D (s) | gap (s) | bytes (GB) |",
              "|---|---|---|---|---|---|---|---|"]
        for m in METHODS:
            x = c[m]
            s_ = lambda k, n=1, sc_=1.0: "-" if x[k]["median"] is None else f"{x[k]['median'] * sc_:.{n}f} [{x[k]['min'] * sc_:.{n}f}-{x[k]['max'] * sc_:.{n}f}]"  # noqa: E731
            L.append(f"| {LABEL[m]} | {x['n_kept']} / {x['n_runs']} ({x['n_not_converged']}) | {s_('N_s')} | {s_('remote_served_s')} | {s_('interrupted_s')} | "
                     f"{s_('R_D_s')} | {s_('gap_s')} | {s_('tx_bytes', 2, 1e-9)} |")
        L += ["", f"verdicts: {json.dumps(v[(sc, w)], default=str)}", ""]
        inv = [i for m in METHODS for i in c[m]["invalid"]]
        if inv:
            L += ["Excluded runs:", ""] + [f"- {i}" for i in inv] + [""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", default=""); ap.add_argument("--dry", action="store_true"); ap.add_argument("--sanity", action="store_true")
    a = ap.parse_args()
    C = collect(a.prefix, a.dry)
    if a.sanity:
        for (sc, w), rs in C.items():
            for r in rs:
                print(f"== {sc} {w} {LABEL[r['method']]} rep {r['rep']}: {r['status']} {r['validity_why']} stop {r['stop_reason']}")
                print(f"   C1 {r['c1']['checks']}")
                print(f"   N {f(r['N_s'])} s (remote {f(r['remote_served_s'])}, interrupted {f(r['interrupted_s'])}), R_D {f(r['R_D_s'])} s, gap {f(r['gap_s'])} s, "
                      f"stall {f(r['total_stall_s'])} s, bytes {f((r['tx_bytes'] or 0) / 1e9, 2)} GB, moves at {[f(t) for t in r['moves']]}")
                print(f"   per move {[(p['edge'], f(p['t_change']), f(p['ttfo_local_s']), f(p['without_local_s'])) for p in r['per_move']]}")
        return
    R = cells(C)
    v, agg = verdicts(R)
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{a.prefix}fig11_results"
    json.dump({"cells": {f"{sc}|{w}": c for (sc, w), c in R.items()}, "verdicts": {f"{sc}|{w}": x for (sc, w), x in v.items()}, **agg},
              open(OUT / f"{stem}.json", "w"), indent=1, default=str)
    (OUT / f"{stem}.md").write_text(md(R, v, agg))
    print(md(R, v, agg))


if __name__ == "__main__":
    main()
