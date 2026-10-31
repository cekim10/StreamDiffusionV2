#!/usr/bin/env python3
"""Fig. 9 (osdi/fig9/preregistration.md): M1 design breakdown. Applies the preregistered rules as written.

Steps (one migration A -> B at call 30, 1 Gbps): Wait-for-Sink (`split_wait`), P-sink (`precopy_sink`), OTTER w/o Sink
sync (`precopy_replay` without `--replay_sink_sync`) from the expF9 runs; OTTER (`precopy_replay` with Sink sync) and
P-full (`precopy_full`, 9a only) from the Fig. 7 runs.

9a  dirty bytes of every pre-copy round and of the stop-and-copy (P-full, P-sink); F9-H1: P-sink stops by the threshold in
    >= 4 / 5 runs of each workload.
9b  delivery gap, TTFO-local, total stall (Fig. 8 rule), bytes, PSNR of B's first 24 calls, OTTER cost breakdown;
    F9-H2: median gap(OTTER) < each other step's, F9-H3: median of the per-run median PSNR of B's first 24 calls,
    OTTER >= P-sink and >= Wait-for-Sink; each on both workloads.

    python tools/eval/fig9_report.py                 # -> results/evaluation/osdi/fig9/fig9_results.{json,md}
    python tools/eval/fig9_report.py --sanity        # per-run detail of whatever exists so far
    python tools/eval/fig9_report.py --prefix _dryrun_ --dry
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from aggregate_xb import transmitted_bytes  # noqa: E402
from fig7_report import FIDELITY_WINDOW, byte_parts, c1 as c1_fig7, c2, cutover_interruption, delivered_rows, summary_stats  # noqa: E402
from fig8_report import stalls  # noqa: E402
from xb_delivery import delivery_metrics, load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/fig9"
WORKLOADS = {"dog": "Low-refresh", "bfly": "High-refresh"}
STEPS = ("wait", "psink", "nosync", "otter")   # the 9b ladder, figure order
LABEL = {"wait": "Wait-for-Sink", "psink": "P-sink", "nosync": "OTTER w/o Sink sync", "otter": "OTTER", "pfull": "P-full"}
N_REPS = 5
H1_MIN_THRESHOLD = 4   # P-sink runs (of 5) that stop by the threshold


def step_of(d: Path, policy: str) -> str | None:
    if policy == "split_wait":
        return "wait"
    if policy == "precopy_sink":
        return "psink"
    if policy == "precopy_full":
        return "pfull"
    if policy == "precopy_replay":
        return "otter" if "_sinksync" in d.name else "nosync"
    return None


def validity(s, d, dry):
    if s["policy"] in ("full", "split_wait"):   # not XB pre-copy methods: the XB aggregation judged them with the W / R / N rules
        from wrn_validity import run_validity_wrn
        return run_validity_wrn(s, d, dry=dry)
    return run_validity_xb(s, d, dry=dry)


def first(ev, node, name):
    return next((e for e in ev if e["node"] == node and e["event"] == name), {})


def c1(step, s, ev, rows):
    """State correctness as each step claims it (prereg section 7)."""
    if step in ("otter", "pfull"):
        return c1_fig7(s, ev, rows)
    v = s.get("validation") or {}
    sw = first(ev, "B", "xb_switch_verified")
    sink_ok = (sw.get("components_ok") or {}).get("sink") is True
    if step == "wait":
        bind, out = first(ev, "B", "sink_bind").get("t"), first(ev, "B", "first_output").get("t")
        checks = {"all_fragments_verified": v.get("all_fragments_verified") is True, "sink_version_consistent": v.get("sink_version_consistent") is True,
                  "final_sink_digest_matches_source": v.get("final_sink_digest_matches_source") is True,
                  "no_generation_before_bind": bind is not None and out is not None and out >= bind}
        claim = "Sink exact at bind; recent state from zero"
    elif step == "psink":
        checks = {"switchover_verified": v.get("switchovers_verified") is True and v.get("n_switchovers") == 1, "sink_verified_at_switch": sink_ok}
        claim = "Sink exact at the switch; recent state from zero"
    else:   # nosync
        checks = {"switchover_verified": v.get("switchovers_verified") is True and v.get("n_switchovers") == 1, "sink_resent_verified": sink_ok,
                  "base_verified": v.get("replay_base_verified") is True, "conditioning_equal": v.get("replay_conditioning_equal") is True,
                  "replay_order_ok": v.get("replay_order_ok") is True, "no_lost_or_duplicated_calls": v.get("replay_no_lost_or_duplicated_calls") is True,
                  "meta_consistent_at_switch": v.get("replay_meta_consistent_at_switch") is True}
        claim = "Sink exact at the switch (resent); recent KV rebuilt by replay"
    return {"claim": claim, "checks": checks, "pass": all(checks.values())}


def cost(ev):
    """OTTER steps: replay, patches, verification, DR-2 and waits, from the run's events (descriptive)."""
    cu, ssc, res, sw = first(ev, "B", "replay_caught_up"), first(ev, "B", "sink_sync_check"), first(ev, "B", "resume"), first(ev, "A", "xb_precopy_switch")
    if not cu:
        return None
    return {"replayed_calls": cu.get("n_applied"), "replay_s_per_call": cu.get("replay_s_median"), "replay_s_total": cu.get("replay_s_total"),
            "patches": sw.get("patches"), "patch_mb": (sw.get("patch_bytes") or 0) / 1e6, "log_mb": (sw.get("log_bytes") or 0) / 1e6,
            "base_mb": ((sw.get("base") or {}).get("bytes") or 0) / 1e6, "switch_mb": (sw.get("final_bytes") or 0) / 1e6,
            "ready_wait_s": sw.get("ready_wait_s"), "stop_to_sent_s": sw.get("stop_to_sent_s"), "src_sink_digest_s": sw.get("sink_ck_s"),
            "dst_sink_check_s": ssc.get("ck_s"), "verdict": sw.get("verdict"), "verdict_wait_s": sw.get("verdict_wait_s"),
            "fallback_mb": (sw.get("fallback_bytes") or 0) / 1e6, "restore_s": res.get("restore_s"), "dr2_s": res.get("dr2_s")}


def run_record(d: Path, dry: bool) -> dict | None:
    s, m, ev = load_run(d)
    step = step_of(d, s["policy"])
    if step is None:
        return None
    ok, why = validity(s, d, dry)
    rows = delivered_rows(s, m)
    C1 = c1(step, s, ev, rows)
    D = delivery_metrics(s, m, ev)
    sa = stalls(rows) if rows else {}
    bp = byte_parts(s, ev)
    scope = bp["rounds"][0] if bp["rounds"] else None   # round 1 sends every fragment of the scope
    return {"run": d.name, "step": step, "rep": s.get("rep"), "valid": ok and C1["pass"], "validity_why": why, "c1": C1,
            "ttfo_local_s": D["ttfo_local_final_s"], "delivery_gap_s": D["delivery_gap_s"], "total_stall_s": sa.get("total_stall_s"),
            "n_stalls": sa.get("n_stalls"), "tx_bytes": transmitted_bytes(s, ev), "cutover_interruption_s": cutover_interruption(rows), "c2": c2(rows),
            "rounds": {"dirty_bytes": bp["rounds"], "stop_and_copy_bytes": bp["final"], "scope_bytes": scope, "switch_reason": bp["switch_reason"],
                       "fraction_of_scope": [b / scope for b in bp["rounds"]] + [bp["final"] / scope] if scope else None},
            "cost": cost(ev) if step in ("nosync", "otter") else None}


def collect(prefix, dry):
    recs = {}
    for w in WORKLOADS:
        rs = []
        for exp in (f"{prefix}expF9_{w}", f"{prefix}expF7_{w}"):
            for d in sorted((EVAL / exp).glob("policy=*")):
                if not (d / "summary.json").exists():
                    continue
                if exp.startswith(f"{prefix}expF7") and not d.name.startswith(("policy=precopy_replay", "policy=precopy_full")):
                    continue
                r = run_record(d, dry)
                if r is not None and not (exp.startswith(f"{prefix}expF9") and r["step"] in ("otter", "pfull")):
                    rs.append(r)
        recs[w] = rs
    return recs


def cells(recs):
    out = {}
    for w, rs in recs.items():
        out[w] = {}
        for k in STEPS + ("pfull",):
            mine = [r for r in rs if r["step"] == k]
            ok = [r for r in mine if r["valid"]]
            out[w][k] = {"n_valid": len(ok), "n_runs": len(mine),
                         "invalid": [(r["run"], r["validity_why"], {c: x for c, x in r["c1"]["checks"].items() if not x}) for r in mine if not r["valid"]],
                         **{key: summary_stats([r[key] for r in ok]) for key in ("delivery_gap_s", "ttfo_local_s", "total_stall_s", "tx_bytes", "cutover_interruption_s")},
                         "psnr_first24_median": summary_stats([r["c2"].get(f"median_psnr_first_{FIDELITY_WINDOW}") for r in ok]),
                         "psnr_first24_min": summary_stats([r["c2"].get(f"min_psnr_first_{FIDELITY_WINDOW}") for r in ok]),
                         "psnr_terminal": summary_stats([r["c2"].get("terminal_median_psnr") for r in ok]),
                         "switch_reasons": [r["rounds"]["switch_reason"] for r in ok],
                         "cost": {c: summary_stats([r["cost"][c] for r in ok if r["cost"] and isinstance(r["cost"].get(c), (int, float))])
                                  for c in (ok[0]["cost"] or {}) if isinstance((ok[0]["cost"] or {}).get(c), (int, float))} if ok and ok[0]["cost"] else None,
                         "runs": mine}
    return out


def verdicts(C):
    v = {}
    for w, c in C.items():
        need = all(c[k]["n_valid"] >= N_REPS for k in STEPS)
        h1 = None
        if c["psink"]["n_valid"] >= N_REPS:
            n_thr = sum(x == "threshold" for x in c["psink"]["switch_reasons"])
            h1 = {"n_threshold": n_thr, "holds": n_thr >= H1_MIN_THRESHOLD}
        h2 = h3 = None
        if need:
            g = {k: c[k]["delivery_gap_s"]["median"] for k in STEPS}
            h2 = {"gaps": g, "holds": all(g["otter"] < g[k] for k in ("wait", "psink", "nosync"))}
            p = {k: c[k]["psnr_first24_median"]["median"] for k in STEPS}
            h3 = {"psnr_first24": p, "holds": p["otter"] >= p["psink"] and p["otter"] >= p["wait"]}
        v[w] = {"F9_H1": h1, "F9_H2": h2, "F9_H3": h3}
    agg = {}
    for h in ("F9_H1", "F9_H2", "F9_H3"):
        xs = [v[w][h] for w in v]
        agg[h] = None if any(x is None for x in xs) else all(x["holds"] for x in xs)
    return v, agg


def f(x, n=2):
    return "-" if x is None else f"{x:.{n}f}"


def md(C, v, agg):
    word = {True: "SUPPORTED", False: "NOT SUPPORTED", None: "NOT EVALUABLE"}
    L = ["# Fig. 9 results", "", "Rules: `preregistration.md` (FROZEN). " + "; ".join(f"**{h.replace('_', '-')}: {word[agg[h]]}**" for h in agg), ""]
    for w, lab in WORKLOADS.items():
        c = C[w]
        L += [f"## {lab} ({w})", "", "| step | valid / runs | gap (s) | TTFO-local (s) | total stall (s) | bytes (GB) | PSNR first 24, median (dB) | min (dB) | terminal (dB) | switch reasons |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for k in STEPS + ("pfull",):
            x = c[k]
            def s_(key, n=2, scale=1.0):
                q = x[key]
                return "-" if q["median"] is None else f"{q['median'] * scale:.{n}f} [{q['q1'] * scale:.{n}f}-{q['q3'] * scale:.{n}f}]"
            L.append(f"| {LABEL[k]} | {x['n_valid']} / {x['n_runs']} | {s_('delivery_gap_s')} | {s_('ttfo_local_s', 1)} | {s_('total_stall_s')} | {s_('tx_bytes', 2, 1e-9)} | "
                     f"{s_('psnr_first24_median', 1)} | {s_('psnr_first24_min', 1)} | {s_('psnr_terminal', 1)} | {', '.join(sorted(set(map(str, x['switch_reasons']))))} |")
        L += ["", "9a rounds (GB; last = stop-and-copy):", ""]
        for k in ("pfull", "psink"):
            for r in c[k]["runs"]:
                rd = r["rounds"]
                L.append(f"- {LABEL[k]} rep {r['rep']}: " + " -> ".join(f(b / 1e9, 3) for b in rd["dirty_bytes"]) + f" | stop {f(rd['stop_and_copy_bytes'] / 1e9, 3)} ({rd['switch_reason']})")
        for k in ("nosync", "otter"):
            if c[k]["cost"]:
                L += ["", f"{LABEL[k]} cost (median): " + ", ".join(f"{n} {f(q['median'], 3)}" for n, q in c[k]["cost"].items())]
        vw = v[w]
        L += ["", f"F9-H1 {json.dumps(vw['F9_H1'])}", f"F9-H2 {json.dumps(vw['F9_H2'])}", f"F9-H3 {json.dumps(vw['F9_H3'])}", ""]
        inv = [i for k in C[w] for i in C[w][k]["invalid"]]
        if inv:
            L += ["Excluded runs:", ""] + [f"- {i}" for i in inv] + [""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", default=""); ap.add_argument("--dry", action="store_true"); ap.add_argument("--sanity", action="store_true")
    a = ap.parse_args()
    recs = collect(a.prefix, a.dry)
    if a.sanity:
        for w, rs in recs.items():
            for r in rs:
                if r["step"] in ("otter", "pfull"):
                    continue
                print(f"== {w} {LABEL[r['step']]} rep {r['rep']}: valid {r['valid']} {r['validity_why']}")
                print(f"   C1 {r['c1']['claim']}: {r['c1']['checks']}")
                print(f"   gap {f(r['delivery_gap_s'])} s, TTFO-local {f(r['ttfo_local_s'])} s, stall {f(r['total_stall_s'])} s, bytes {f((r['tx_bytes'] or 0) / 1e9, 3)} GB, cutover {f(r['cutover_interruption_s'])} s")
                print(f"   rounds {r['rounds']}")
                print(f"   C2 {r['c2']}")
                if r["cost"]:
                    print(f"   cost {r['cost']}")
        return
    C = cells(recs)
    v, agg = verdicts(C)
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{a.prefix}fig9_results"
    json.dump({"cells": C, "verdicts": v, **agg}, open(OUT / f"{stem}.json", "w"), indent=1, default=str)
    (OUT / f"{stem}.md").write_text(md(C, v, agg))
    print(md(C, v, agg))


if __name__ == "__main__":
    main()
