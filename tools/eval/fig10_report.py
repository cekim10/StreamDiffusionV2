#!/usr/bin/env python3
"""Fig. 10 (osdi/fig10/preregistration.md): M2 versioned Sink reuse vs version age. Applies the preregistered rules.

Per run (path A -> B -> A, fixed switch calls S1 = 74 and S2 = S1 + age + 44): validity, both switches at their planned
calls, first cutover SINKOK; second migration (B -> A): base mode / bytes, delta content, the destination's DELTAOK and
its changed blocks vs the retained version, readiness (second task start -> B's replay_ready), base ready, interruption,
second cutover SINKOK / fallback. Computed (not executed) baselines from the Versioned run of the same (workload, age,
rep): changed-block = blocks whose bytes differ from the retained version x 4,792,320 B + the delta's metadata;
unchanged-only (entry granularity) = (distinct refreshed + distinct shifted entries) x 9,584,640 B + the same metadata.

F10-H1  ages crossing >= 1 realignment (60, 150, 240): median Versioned base bytes < median changed-block bytes.
F10-H2  every age: median Versioned base bytes (fallbacks included) < median Full base bytes.
F10-H3  every age: median readiness Versioned < Full.   Each on both workloads.
Extra-rep rule: a (workload, age) cell whose readiness ranges overlap between the arms is listed for 2 more reps.

    python tools/eval/fig10_report.py            # -> results/evaluation/osdi/fig10/fig10_results.{json,md}
    python tools/eval/fig10_report.py --sanity   # per-run detail of whatever exists so far
    python tools/eval/fig10_report.py --prefix _dryrun_ --dry
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
from xb_validity import run_validity_xb  # noqa: E402

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/fig10"
WORKLOADS = {"dog": "Low-refresh", "bfly": "High-refresh"}
AGES = (10, 60, 150, 240)
REALIGN_AGES = (60, 150, 240)
S1, GAP = 74, 44
ARMS = ("full", "ver")
LABEL = {"full": "Full", "ver": "Versioned (M2)"}
N_REPS = 3
ENTRY_B, BLOCK_B = 9_584_640, 4_792_320


def load(d: Path):
    s = json.load(open(d / "summary.json"))
    ev = []
    for r in csv.DictReader(open(d / "events.csv", newline="")):
        node, name = r["event"].split(":", 1) if ":" in r["event"] else ("", r["event"])
        ev.append({"node": node, "event": name, "t": float(r["t_wall"]), **(json.loads(r["detail"]) if r["detail"] else {})})
    m = list(csv.DictReader(open(d / "metrics.csv", newline="")))
    return s, ev, m


def first(ev, node, name, after=-1e18):
    return next((e for e in ev if e["node"] == node and e["event"] == name and e["t"] >= after), None)


def run_record(d: Path, age: int, dry: bool) -> dict:
    s, ev, m = load(d)
    arm = "ver" if "_reuse" in d.name else "full"
    ok, why = run_validity_xb(s, d, dry=dry)
    s2 = S1 + age + GAP
    starts = [e for e in ev if e["event"] == "xb_task_start"]
    t0 = starts[1]["t"] if len(starts) >= 2 else None
    sw1, sw2 = first(ev, "A", "xb_precopy_switch"), first(ev, "B", "xb_precopy_switch")
    bs = first(ev, "B", "replay_base_sent", t0 or 0)
    rdb = first(ev, "A", "replay_delta_base", t0 or 0)
    rb = first(ev, "A", "replay_base", t0 or 0)
    ready = first(ev, "B", "replay_ready", t0 or 0)
    fo = first(ev, "A", "first_output", t0 or 0)
    base_t = rdb["t"] if (rdb and rdb.get("accepted")) else (rb["t"] if rb else None)
    rows = sorted(((int(r["call"]), r["owner"], float(r["t_out_rel"]), r.get("psnr"), r.get("ref_match")) for r in m if r.get("t_out_rel") not in ("", None)),
                  key=lambda x: x[2])
    first_a2 = next((x for x in rows if x[1] == "A" and x[0] >= s2), None)
    last_b = max((x[2] for x in rows if x[1] == "B" and first_a2 is not None and x[2] <= first_a2[2]), default=None)
    checks = {"valid_xb": ok, "switch1_at_plan": bool(sw1) and sw1.get("call") == S1 and not sw1.get("switch_call_missed"),
              "switch2_at_plan": bool(sw2) and sw2.get("call") == s2 and not sw2.get("switch_call_missed"),
              "cutover1_SINKOK": bool(sw1) and sw1.get("verdict") == "SINKOK", "cutover2_SINKOK": bool(sw2) and sw2.get("verdict") == "SINKOK",
              "no_ready_timeout": bool(sw2) and not sw2.get("ready_timeout"), "base2_sent": bs is not None}
    if arm == "ver":
        checks["delta_verdict_recorded"] = bool(bs) and bs.get("delta_verdict") in ("DELTAOK", "DELTANO")
    mode = bs and bs.get("mode")
    meta_b = (bs["bytes"] - bs["delta_value_bytes"]) if (bs and bs.get("delta_value_bytes") is not None) else None
    chg = (rdb or {}).get("changed_vs_retained")
    n_ref = (bs or {}).get("delta_entries") if (bs or {}).get("delta_entries") is not None else (bs or {}).get("distinct_refreshed_entries")
    n_sh = (bs or {}).get("distinct_shifted_entries")
    rec = {"run": d.name, "arm": arm, "age": age, "rep": s.get("rep"), "valid": all(checks.values()), "checks": checks, "validity_why": why,
           "base_mode": mode, "fallback": arm == "ver" and mode != "delta", "base_bytes": bs and bs.get("bytes"),
           "total_bytes_mig2": sum(int(e.get("dirty_bytes") or 0) for e in ev if e["node"] == "B" and e["event"] == "xb_precopy_round") +
           int((sw2 or {}).get("log_bytes") or 0) + int((sw2 or {}).get("final_bytes") or 0),
           "refresh_events": (bs or {}).get("refresh_events"), "refreshed_entries": n_ref, "shift_events": (bs or {}).get("delta_shifts", (bs or {}).get("shift_events_kept")),
           "distinct_shifted_entries": n_sh, "tracked_calls": (bs or {}).get("tracked_calls"), "track_s": (bs or {}).get("track_s"),
           "delta_ok": (rdb or {}).get("accepted"), "n_block_mismatch": (rdb or {}).get("n_block_mismatch"), "changed_vs_retained": chg,
           "rebuild": {k: (rdb or {}).get(k) for k in ("retained_h2d_s", "rebuild_s", "digest_s", "total_s")} if rdb else None,
           "changed_block_bytes": (chg["blocks"] * BLOCK_B + meta_b) if (chg and meta_b is not None) else None,
           "unchanged_only_entry_bytes": ((n_ref + n_sh) * ENTRY_B + meta_b) if (n_ref is not None and n_sh is not None and meta_b is not None) else None,
           "readiness_s": (ready["t"] - t0) if (ready and t0) else None, "base_ready_s": (base_t - t0) if (base_t and t0) else None,
           "interruption_s": (first_a2[2] - last_b) if (first_a2 and last_b is not None) else None,
           "b_outputs": [(c, p, r) for c, o, _, p, r in rows if o == "B" and S1 <= c < s2]}
    return rec


def collect(prefix, dry):
    out = {}
    for w in WORKLOADS:
        for a in AGES:
            out[(w, a)] = [run_record(d, a, dry) for d in sorted((EVAL / f"{prefix}expF10_{w}_a{a}").glob("policy=*")) if (d / "summary.json").exists()]
    return out


def pair_checks(rs):
    """Equivalence between the arms of one (workload, age, rep): B's outputs between S1 and S2 identical."""
    out = {}
    for rep in sorted({r["rep"] for r in rs}):
        f = next((r for r in rs if r["rep"] == rep and r["arm"] == "full"), None)
        v = next((r for r in rs if r["rep"] == rep and r["arm"] == "ver"), None)
        if f and v:
            out[rep] = f["b_outputs"] == v["b_outputs"] and len(f["b_outputs"]) > 0
    return out


def stats(xs):
    xs = [x for x in xs if x is not None]
    return {"median": st.median(xs) if xs else None, "min": min(xs) if xs else None, "max": max(xs) if xs else None, "n": len(xs), "values": xs}


def cells(C, dry=False):
    res = {}
    for (w, a), rs in C.items():
        eq = pair_checks(rs)
        if not dry:   # section 7: B's outputs must be identical between the arms of a rep (dry-run PSNR is random)
            for r in rs:
                if eq.get(r["rep"]) is False:
                    r["valid"] = False; r["checks"]["arms_equivalent"] = False
        cell = {"equivalence_by_rep": eq}
        for arm in ARMS:
            ok = [r for r in rs if r["arm"] == arm and r["valid"]]
            cell[arm] = {"n_valid": len(ok), "n_runs": sum(r["arm"] == arm for r in rs), "fallbacks": sum(r["fallback"] for r in ok),
                         **{k: stats([r[k] for r in ok]) for k in ("base_bytes", "total_bytes_mig2", "readiness_s", "base_ready_s", "interruption_s",
                                                                     "refreshed_entries", "distinct_shifted_entries", "shift_events", "changed_block_bytes",
                                                                     "unchanged_only_entry_bytes")},
                         "changed_vs_retained": [r["changed_vs_retained"] for r in ok], "invalid": [(r["run"], {k: v for k, v in r["checks"].items() if not v}, r["validity_why"]) for r in rs
                                                                                                if r["arm"] == arm and not r["valid"]]}
        f, v = cell["full"]["readiness_s"], cell["ver"]["readiness_s"]
        cell["extra_reps_rule"] = bool(f["n"] and v["n"] and v["max"] >= f["min"] and min(f["n"], v["n"]) < 5)
        res[(w, a)] = cell
    return res


def verdicts(R):
    v = {w: {} for w in WORKLOADS}
    for w in WORKLOADS:
        ev = all(R[(w, a)][arm]["n_valid"] >= N_REPS for a in AGES for arm in ARMS)
        if not ev:
            v[w] = {"evaluable": False}
            continue
        g = lambda a, arm, k: R[(w, a)][arm][k]["median"]  # noqa: E731
        h1 = {a: (g(a, "ver", "base_bytes"), g(a, "ver", "changed_block_bytes")) for a in REALIGN_AGES}
        h2 = {a: (g(a, "ver", "base_bytes"), g(a, "full", "base_bytes")) for a in AGES}
        h3 = {a: (g(a, "ver", "readiness_s"), g(a, "full", "readiness_s")) for a in AGES}
        v[w] = {"evaluable": True,
                "F10_H1": {"pairs": h1, "holds": all(x is not None and y is not None and x < y for x, y in h1.values())},
                "F10_H2": {"pairs": h2, "holds": all(x is not None and y is not None and x < y for x, y in h2.values())},
                "F10_H3": {"pairs": h3, "ratios": {a: (x / y if x and y else None) for a, (x, y) in h3.items()}, "holds": all(x is not None and y is not None and x < y for x, y in h3.values())}}
    agg = {}
    for h in ("F10_H1", "F10_H2", "F10_H3"):
        xs = [v[w].get(h) for w in WORKLOADS]
        agg[h] = None if any(x is None for x in xs) else all(x["holds"] for x in xs)
    return v, agg


def f(x, n=2):
    return "-" if x is None else f"{x:.{n}f}"


def md(R, v, agg):
    word = {True: "SUPPORTED", False: "NOT SUPPORTED", None: "NOT EVALUABLE"}
    L = ["# Fig. 10 results", "", "Rules: `preregistration.md`. " + "; ".join(f"**{h.replace('_', '-')}: {word[agg[h]]}**" for h in agg), ""]
    for w, lab in WORKLOADS.items():
        L += [f"## {lab} ({w})", "", "| age | arm | valid | base (MB) | total mig. 2 (MB) | readiness (s) | base ready (s) | interruption (s) | refreshed entries / distinct shifted entries / shift events | changed-block (MB) | unchanged-only entry (MB) | fallbacks |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for a in AGES:
            for arm in ARMS:
                x = R[(w, a)][arm]
                mb = lambda k: f(x[k]["median"] / 1e6, 1) if x[k]["median"] is not None else "-"  # noqa: E731
                rng = lambda k: f"{f(x[k]['median'])} [{f(x[k]['min'])}-{f(x[k]['max'])}]"  # noqa: E731
                L.append(f"| {a} | {LABEL[arm]} | {x['n_valid']} / {x['n_runs']} | {mb('base_bytes')} | {mb('total_bytes_mig2')} | {rng('readiness_s')} | {rng('base_ready_s')} | "
                         f"{rng('interruption_s')} | {f(x['refreshed_entries']['median'], 0)} / {f(x['distinct_shifted_entries']['median'], 0)} / {f(x['shift_events']['median'], 0)} | {mb('changed_block_bytes')} | "
                         f"{mb('unchanged_only_entry_bytes')} | {x['fallbacks']} |")
            L.append(f"| {a} | equivalence (B's outputs S1..S2 equal per rep) | {R[(w, a)]['equivalence_by_rep']} | | | | | | | | | |")
        L += ["", f"changed vs retained (Versioned): " + "; ".join(f"a{a}: {R[(w, a)]['ver']['changed_vs_retained']}" for a in AGES), ""]
        L += [f"verdicts: {json.dumps(v[w], default=str)}", ""]
        xr = [a for a in AGES if R[(w, a)]["extra_reps_rule"]]
        if xr:
            L += [f"**Extra-rep rule triggered (readiness ranges overlap): ages {xr}** -> `run_fig10.sh extra {w} <age>`", ""]
        inv = [i for a in AGES for arm in ARMS for i in R[(w, a)][arm]["invalid"]]
        if inv:
            L += ["Excluded runs:", ""] + [f"- {i}" for i in inv] + [""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", default=""); ap.add_argument("--dry", action="store_true"); ap.add_argument("--sanity", action="store_true")
    a = ap.parse_args()
    C = collect(a.prefix, a.dry)
    if a.sanity:
        for (w, age), rs in C.items():
            for r in rs:
                print(f"== {w} age {age} {LABEL[r['arm']]} rep {r['rep']}: valid {r['valid']} {r['validity_why']}")
                print(f"   checks {r['checks']}")
                print(f"   base {r['base_mode']} {f((r['base_bytes'] or 0) / 1e6, 1)} MB, total mig2 {f(r['total_bytes_mig2'] / 1e6, 1)} MB, DELTAOK {r['delta_ok']}, mismatched {r['n_block_mismatch']}")
                print(f"   refreshed {r['refreshed_entries']}, shift events {r['shift_events']}, distinct shifted {r['distinct_shifted_entries']}, changed vs retained {r['changed_vs_retained']}")
                print(f"   changed-block {f((r['changed_block_bytes'] or 0) / 1e6, 1)} MB, unchanged-only entry {f((r['unchanged_only_entry_bytes'] or 0) / 1e6, 1)} MB")
                print(f"   readiness {f(r['readiness_s'])} s, base ready {f(r['base_ready_s'])} s, interruption {f(r['interruption_s'])} s, rebuild {r['rebuild']}")
            eq = pair_checks(rs)
            if eq:
                print(f"   equivalence {w} age {age}: {eq}")
        return
    R = cells(C, a.dry)
    v, agg = verdicts(R)
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{a.prefix}fig10_results"
    json.dump({"cells": {f"{w}|{age}": c for (w, age), c in R.items()}, "verdicts": v, **agg}, open(OUT / f"{stem}.json", "w"), indent=1, default=str)
    (OUT / f"{stem}.md").write_text(md(R, v, agg))
    print(md(R, v, agg))


if __name__ == "__main__":
    main()
