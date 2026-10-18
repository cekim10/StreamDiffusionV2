#!/usr/bin/env python3
"""Check the W / R / N GPU shakedown against results/evaluation/osdi/followup_shakedown_conditions.md (incl. Amendment 1).
Execution correctness only; writes results/evaluation/osdi/wrn_shakedown_check.md (or _dryrun_ variant with --dry).

    python tools/eval/check_wrn_shakedown.py            # after `python tools/eval/run_wrn.py shakedown`
    python tools/eval/check_wrn_shakedown.py --dry      # loopback outputs
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
from wrn_validity import run_validity_wrn  # noqa: E402

EV = ROOT / "results/evaluation"


def latest(pattern: str) -> list[Path]:
    return sorted(EV.glob(pattern))


def load(d: Path) -> dict:
    return json.load(open(d / "summary.json"))


def events(d: Path) -> list[dict]:
    out = []
    with open(d / "events.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            out.append(r)
    return out


def ev_named(d: Path, name: str) -> list[dict]:
    res = []
    for r in events(d):
        e = r.get("event", "")
        if e.endswith(":" + name):
            det = json.loads(r.get("detail") or "{}")
            res.append({"node": e.split(":")[0], "t_rel": float(r.get("t_rel") or 0), **det})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    pre = "_dryrun_" if a.dry else ""
    res = []   # (id, passed, detail)

    def add(i, ok, detail):
        res.append((i, bool(ok), detail))

    # ---------------- W
    w1d = latest(f"{pre}expW_W1/mbike-trick_s0_shk_2*") or latest(f"{pre}expW_W1/mbike-trick_s0_2*")
    w2 = {}
    for d in latest(f"{pre}shk_W2_mbike-trick_s0/policy=*"):
        s = load(d); w2[s["policy"]] = (d, s)
    if not w1d or not w2:
        add("W", False, f"missing outputs (W1 {bool(w1d)}, W2 {sorted(w2)})")
    else:
        w1 = w1d[-1]
        rows = list(csv.DictReader(open(w1 / "w1_calls.csv", newline="")))
        fps = [json.loads(r["sink_vfp"]) for r in rows]
        nval = {len(f) for f in fps if f}
        add("W-a", len(rows) == 330 and all(fps) and len(nval) == 1 and (a.dry or nval == {90}), f"{len(rows)} calls; fingerprint values per call {sorted(nval)} (expected 90 = 30 layers x 3 slots on GPU)")
        d_ot, s_ot = w2.get("reuse_dyn", (None, None))
        brec_p = d_ot / "node_B" / "baseline_record.json" if d_ot else None
        brec = json.load(open(brec_p)) if brec_p and brec_p.exists() else None
        if brec is None:
            add("W-b", False, "no node_B/baseline_record.json in the W2 OTTER run"); add("W-c", False, "no baseline record"); add("W-g", False, "no baseline record")
        else:
            n = min(164, len(brec), len(rows))
            dig = sum(1 for c in range(n) if rows[c]["frame_digest"] != brec[c]["frame_digest"])
            fpd = sum(1 for c in range(n) if json.loads(rows[c]["sink_vfp"]) != brec[c]["sink_vfp"])
            add("W-b", n == 164 and dig == 0, f"output-frame digests W1 vs node B baseline, calls 0-{n - 1}: {dig} differ")
            add("W-c", n == 164 and fpd == 0, f"value fingerprints W1 vs node B baseline, calls 0-{n - 1}: {fpd} differ")
            add("W-g", all(brec[c]["sink_vfp"] for c in range(34, min(164, len(brec)))) and len(brec) >= 164, f"reference fingerprints for calls 34-163: {len(brec)} baseline calls")
        pos = [r["sink_slot_pos"] for r in rows]
        pos_only = [c for c in range(1, len(rows)) if pos[c] != pos[c - 1] and fps[c] == fps[c - 1]]
        both = [c for c in range(1, len(rows)) if pos[c] != pos[c - 1] and fps[c] != fps[c - 1]]
        promo = [int(r["call"]) for r in rows if r["promotion"] == "True"]
        add("W-d", all(fps[c] != fps[c - 1] for c in promo), f"promotions {promo[:20]}{'...' if len(promo) > 20 else ''}; position-only changes (realignments, not counted) at {pos_only[:12]}; position+value changes at {both[:12]}"
            + ("; NOTE promotion at call 1 (inspect: sink filling vs promotion)" if 1 in promo else ""))
        audit = {r["workload"]: r for r in json.load(open(ROOT / "results/evaluation/osdi/expW/loop_audit.json"))}
        cuts = [int(r["call"]) for r in rows if r["class"] == "cut"]
        add("W-e", cuts == audit["mbike-trick"]["cut_calls_0_329"], f"cut calls {cuts[:6]}... vs loop_audit {audit['mbike-trick']['cut_calls_0_329'][:6]}...")
        okf, det = True, []
        for pol, (d, s) in sorted(w2.items()):
            t = s["wrn"]["termination"]
            m = [r for r in csv.DictReader(open(d / "metrics.csv", newline="")) if r["owner"] == "B"]
            calls = {int(r["call"]): r for r in m}
            prod = [c for c in range(34, 134) if c in calls and calls[c]["missing"] != "True"]
            nopsnr = [c for c in prod if calls[c]["psnr"] in ("", "None")]
            ok = t["first_call_final_owner"] == 34 and (t["last_call_final_owner"] or 0) >= 133 and t["stop_reason"] == "horizon" and not nopsnr
            if pol == "reuse_dyn":
                binds = ev_named(d, "sink_bind"); rj = ev_named(d, "rejoin")
                bcall = binds[0].get("call") if binds else None
                exp = next((c for c in range(bcall, 134) if c in calls and calls[c]["psnr"] not in ("", "None") and float(calls[c]["psnr"]) >= 35.0), None) if bcall is not None else None
                got = rj[0].get("call") if rj else None
                ok = ok and bcall is not None and exp == got
                det.append(f"{pol}: c0 {t['first_call_final_owner']}, last {t['last_call_final_owner']}, stop {t['stop_reason']}, bind call {bcall}, rejoin event {got} vs recomputed {exp}, calls without PSNR {nopsnr[:5]}")
            else:
                det.append(f"{pol}: c0 {t['first_call_final_owner']}, last {t['last_call_final_owner']}, stop {t['stop_reason']}, calls without PSNR {nopsnr[:5]}")
            okf = okf and ok
        add("W-f", okf and set(w2) == {"reuse_dyn", "cold"}, "; ".join(det))

    # ---------------- R
    rr = {}
    for d in latest(f"{pre}shk_R/policy=*"):
        s = load(d); rr[s["policy"]] = (d, s)
    if set(rr) != {"restart", "split", "reuse_dyn"}:
        add("R", False, f"runs present: {sorted(rr)}")
    else:
        det, ok = [], True
        for pol, (d, s) in sorted(rr.items()):
            mv = [m["t_req"] for m in s["moves"]]
            gaps = [round(y - x, 2) for x, y in zip(mv, mv[1:])]
            tm = s["tm_s"]
            v = run_validity_wrn(s, d, dry=a.dry)
            ok = ok and all(abs(g - tm) <= 0.2 for g in gaps) and len(mv) == 3
            det.append(f"{pol}: move gaps {gaps} (T_m {tm:.2f}), valid {v[0]} {v[1]}")
        add("R-a", ok, "; ".join(det))
        d, s = rr["restart"]
        drops = {e["node"] for e in ev_named(d, "sink_dropped")}
        okr = {"B", "C"} <= drops and s["d0"]["holder_forwarded_sinks"] == 0
        d2, s2 = rr["split"]
        reused = s2["d0"]["verified_progress_reused"]
        binds = ev_named(d2, "sink_bind"); moves = {m["from"]: m["t_req"] for m in s2["moves"]}
        t0 = s2["moves"][0]["t_req"]
        cond = []
        for e in ("B", "C"):
            b = next((x for x in binds if x["node"] == e), None)
            if b is not None and e in moves and b["t_rel"] < moves[e]:
                nxt = s2["path"][s2["path"].index(e) + 1]
                fwd = any(r["src"] == e and r["dst"] == nxt and r["event"] == "recv" and r["ok"] == "True" for r in csv.DictReader(open(d2 / "fragments.csv", newline="")))
                cond.append((e, "bound before leaving", fwd))
        oks = reused is not None and reused >= 0.9 and all(x[2] for x in cond)
        add("R-b'", okr and oks, f"restart drops at {sorted(drops)}, B_fwd {s['d0']['holder_forwarded_sinks']:.3f}; split reused {reused}, bound-before-leaving owners {cond}")
        add("R-c", all(x[1]["wrn"].get("exposure") is not None and "exposure_valid" in x[1]["wrn"]["exposure"] for x in rr.values()),
            "; ".join(f"{p}: {({k: (round(v, 3) if isinstance(v, float) else v) for k, v in (s['wrn']['exposure'] or {}).items() if k in ('coverage_fraction', 'mean_active_background_flows_from_A', 'exposure_valid')})}" for p, (d, s) in sorted(rr.items())))
        add("R-d", all("owner_promotions" in x[1]["wrn"] for x in rr.values()), "; ".join(f"{p}: {s['wrn']['owner_promotions_before_final_bind']} before final bind" for p, (d, s) in sorted(rr.items())))

    # ---------------- N
    nn = {}
    for d in latest(f"{pre}shk_N_cell9/policy=*"):
        s = load(d); nn[s["policy"]] = (d, s)
    if set(nn) != {"reuse_aware_in", "reuse_dyn"}:
        add("N", False, f"runs present: {sorted(nn)}")
    else:
        deg = 6.25 if a.dry else 62.5
        da, db, dc, dets = True, True, True, []
        for pol, (d, s) in sorted(nn.items()):
            cc = s["d0"]["cap_changes"]; pt = s["wrn"]["progress_trigger"] or {}
            need = math.ceil((pt.get("s_size") or 0) / 2)
            ok_a = len(cc) == 1 and cc[0][1] == "B" and cc[0][2] == "out" and abs(cc[0][3] - deg) < 1e-9 and need <= (pt.get("verified_of_S_at_trigger") or -1) <= need + 2
            ok_b = all(k in pt for k in ("t_rel", "s_size", "verified_of_S_at_trigger", "sink_verified_after_trigger_s", "reaction_feasible", "available_elsewhere_at_trigger"))
            ok_c = s["wrn"].get("known_caps_unchanged") is True
            da &= ok_a; db &= ok_b; dc &= ok_c
            dets.append(f"{pol}: cap changes {cc}, |S| {pt.get('s_size')}, verified at trigger {pt.get('verified_of_S_at_trigger')} (need {need}), "
                        f"after-trigger {pt.get('sink_verified_after_trigger_s')}, feasible {pt.get('reaction_feasible')}, available {pt.get('available_elsewhere_at_trigger')}, valid {run_validity_wrn(s, d, dry=a.dry)}")
        add("N-a", da, "; ".join(dets)); add("N-b", db, "trigger record fields"); add("N-c", dc, "known_caps (planner view) unchanged")
    tdir = latest("_dryrun__t_Ntimeout/policy=*")
    if tdir:
        t = load(tdir[-1])["wrn"]["termination"]
        add("N-d (loopback)", t["timed_out"] and t["last_progress_final_owner"] is not None, json.dumps(t))

    lines = [f"# W / R / N shakedown check ({'loopback dry run' if a.dry else 'GPU'})", "", "| id | pass | detail |", "|---|---|---|"]
    lines += [f"| {i} | {'PASS' if ok else '**FAIL**'} | {det} |" for i, ok, det in res]
    allok = all(ok for _, ok, _ in res)
    lines += ["", f"Overall: {'PASS' if allok else 'FAIL'}"]
    out = ROOT / "results/evaluation/osdi" / (("_dryrun_" if a.dry else "") + "wrn_shakedown_check.md")
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()
