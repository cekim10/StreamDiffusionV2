#!/usr/bin/env python3
"""Fig. 11 (osdi/fig11/preregistration.md): repeated mobility A -> B -> C -> D on the wall clock. Applies the preregistered
rules as written.

Per run: validity (XB validity; Full by the W / R / N rule, as Fig. 7), C1 per method, the local-service delay N (sum over
the edge changes of change -> first output at the new edge, truncated at the next change; a locality-recovery cost, not a
continuity measure) split into remote-served and interrupted, N_post (the same over the 2nd and 3rd changes), final-edge
readiness R_D (TTFO-local at D), and the continuity measures reported with it: max output gap, total stall (Fig. 8 rule).
Right-censoring: every method is observed for T_OBS = 300 s after the final move; a run whose final edge has not served
locally by then is "not converged": its R_D, N and N_post are lower bounds (censored), never pooled as completed values.
A median whose rank falls on a censored run is itself a lower bound. Rules are applied conservatively: OTTER's value must
be uncensored; a censored baseline median is used as its lower bound.
F11-H1 median N(OTTER) <= 0.5 x min(median N of Full, P-full, R-full); F11-H2 median N_post(OTTER) <= 0.80 x median
N_post(No staging); F11-H3 median R_D(OTTER) < median R_D(No staging). Each scenario x workload.

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
LABEL = {"full": "Full", "pfull": "Llumnix-style", "rfull": "ServerlessLLM-style", "base": "No staging", "otter": "OTTER"}
EXTERNAL = ("full", "pfull", "rfull")
N_REPS = 3
H1_RATIO, H2_RATIO = 0.5, 0.80
T_OBS = 300.0   # observation horizon after the final move, every method (right-censoring)
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


def no_local(D):
    """Local-service delay per edge change: change -> first output at the new edge, truncated at the next change; the final
    edge is observed for T_OBS after its change (censored at T_OBS if it has not served locally by then)."""
    tt = D["ttfo_local"]
    n, per, cens = 0.0, [], False
    for i, x in enumerate(tt):
        last = i + 1 == len(tt)
        nxt = (x["t_change"] + T_OBS) if last else tt[i + 1]["t_change"]
        t1 = x["ttfo_local_s"]
        if last and (t1 is None or t1 > T_OBS):
            w, c = T_OBS, True
        else:
            w, c = (nxt - x["t_change"]) if t1 is None else min(t1, nxt - x["t_change"]), False
        w = max(0.0, w); cens = cens or c
        per.append({"edge": x["edge"], "t_change": x["t_change"], "ttfo_local_s": t1, "without_local_s": w, "censored": c}); n += w
    return n, per, cens


def run_record(d: Path, dry: bool) -> dict | None:
    s, m, ev = load_run(d)
    meth = method_of(d, s["policy"])
    if meth is None:
        return None
    ok, why = validity(s, d, dry)
    D = delivery_metrics(s, m, ev)
    rows = delivered_rows(s, m)
    t_end = D["t_last_delivery_s"]
    N, per, cens = no_local(D)
    t_final = per[-1]["t_change"] if per else 0.0
    C1 = c1(meth, s, ev)
    if ok and C1["pass"] and not cens:
        status = "valid"
    elif cens and set(why) <= NONCONV and t_end is not None and t_end >= t_final + T_OBS - 1.0:
        status = "not_converged"   # observed for the whole horizon without local service at D: censored, kept
    else:
        status = "invalid"
        if cens and (t_end is None or t_end < t_final + T_OBS - 1.0):
            why = why + [f"observed {0 if t_end is None else t_end - t_final:.0f} s < T_OBS {T_OBS:.0f} s after the final move"]
    rem = min(D["remote_wall_s"], N)
    n_post = sum(p["without_local_s"] for p in per[1:])
    sw_d = [e for e in ev if e["node"] == "D" and e["event"] in ("resume",)]
    return {"run": d.name, "method": meth, "rep": s.get("rep"), "status": status, "validity_why": why, "c1": C1, "converged": not cens,
            "censored": cens, "N_s": N, "N_post_s": n_post, "remote_served_s": rem, "interrupted_s": N - rem, "per_move": per,
            "R_D_s": T_OBS if cens else D["ttfo_local_final_s"],
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


def stats(xs, cens=None):
    """Median / range; with right-censored entries (lower bounds) the median is a lower bound when its rank falls on one."""
    pairs = [(x, bool(c)) for x, c in zip(xs, cens or [False] * len(xs)) if x is not None]
    if not pairs:
        return {"median": None, "min": None, "max": None, "n": 0, "values": [], "censored": [], "median_censored": False}
    order = sorted(pairs, key=lambda p: (float("inf") if p[1] else p[0]))
    n = len(order)
    lo, hi = order[(n - 1) // 2], order[n // 2]
    mc = lo[1] or hi[1]
    mv = min(x for x, c in order if c) if mc else (lo[0] + hi[0]) / 2   # censored: the smallest censored bound (a lower bound)
    vals = [p[0] for p in pairs]
    return {"median": mv, "min": min(vals), "max": max(vals), "n": n, "values": vals, "censored": [p[1] for p in pairs], "median_censored": mc}


def cells(C):
    R = {}
    for key, rs in C.items():
        R[key] = {}
        for m in METHODS:
            mine = [r for r in rs if r["method"] == m]
            kept = [r for r in mine if r["status"] in ("valid", "not_converged")]
            R[key][m] = {"n_kept": len(kept), "n_runs": len(mine), "n_not_converged": sum(r["status"] == "not_converged" for r in kept),
                         **{k: stats([r[k] for r in kept], [r["censored"] for r in kept]) for k in ("N_s", "N_post_s", "remote_served_s", "interrupted_s", "R_D_s")},
                         **{k: stats([r[k] for r in kept]) for k in ("gap_s", "total_stall_s", "tx_bytes")},
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
        NP = {m: c[m]["N_post_s"]["median"] for m in ("base", "otter")}
        RD = {m: c[m]["R_D_s"]["median"] for m in ("base", "otter")}
        oc = {k: c["otter"][k]["median_censored"] for k in ("N_s", "N_post_s", "R_D_s")}   # OTTER must be uncensored
        best = min(N[m] for m in EXTERNAL)   # a censored baseline median enters as its lower bound (conservative)
        v[key] = {"evaluable": True, "N": N, "N_post": NP, "R_D": RD, "otter_censored": oc,
                  "median_censored": {m: c[m]["N_s"]["median_censored"] for m in METHODS},
                  "F11_H1": {"ratio": N["otter"] / best, "holds": not oc["N_s"] and N["otter"] <= H1_RATIO * best},
                  "F11_H2": {"ratio": NP["otter"] / NP["base"] if NP["base"] else None, "holds": not oc["N_post_s"] and NP["otter"] <= H2_RATIO * NP["base"]},
                  "F11_H3": {"holds": not oc["R_D_s"] and RD["otter"] is not None and RD["base"] is not None and RD["otter"] < RD["base"]}}
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
        L += [f"## {SCENARIOS[sc]}, {WORKLOADS[w]} ({w})", "",
              "| method | kept / runs (not conv.) | local-service delay N (s) | remote-served (s) | interrupted (s) | N after 1st move (s) | R_D (s) | max gap (s) | total stall (s) | bytes (GB) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for m in METHODS:
            x = c[m]
            def s_(k, n=1, sc_=1.0):
                q = x[k]
                if q["median"] is None:
                    return "-"
                lb = ">=" if q.get("median_censored") else ""
                return f"{lb}{q['median'] * sc_:.{n}f} [{q['min'] * sc_:.{n}f}-{q['max'] * sc_:.{n}f}]"
            L.append(f"| {LABEL[m]} | {x['n_kept']} / {x['n_runs']} ({x['n_not_converged']}) | {s_('N_s')} | {s_('remote_served_s')} | {s_('interrupted_s')} | "
                     f"{s_('N_post_s')} | {s_('R_D_s')} | {s_('gap_s', 2)} | {s_('total_stall_s', 2)} | {s_('tx_bytes', 2, 1e-9)} |")
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
                print(f"   N {f(r['N_s'])} s (remote {f(r['remote_served_s'])}, interrupted {f(r['interrupted_s'])}), N after 1st move {f(r['N_post_s'])} s, "
                      f"censored {r['censored']}, R_D {f(r['R_D_s'])} s, gap {f(r['gap_s'])} s, "
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
