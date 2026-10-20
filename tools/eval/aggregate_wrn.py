#!/usr/bin/env python3
"""W / R / N aggregation and verdicts, exactly as frozen (results/evaluation/osdi/expW|expR|expN/preregistration.md,
followup_common.md section 3: validity, censoring, order-statistic medians, NOT EVALUABLE rules).

    python tools/eval/aggregate_wrn.py            # -> results/evaluation/osdi/wrn_results.{json,md} + w2_table.csv, r_table.csv, n_table.csv
    python tools/eval/aggregate_wrn.py --dry      # loopback outputs (_dryrun_ prefixes); never reported
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
from aggregate_expD import discarded_sinks  # noqa: E402
from expw_loop_audit import ADJ, cut_calls  # noqa: E402
from wrn_validity import run_validity_wrn  # noqa: E402

EV = ROOT / "results/evaluation"
OUT = ROOT / "results/evaluation/osdi"
M_W, H_W = 34, 100
LAST = M_W + H_W - 1                      # 133
REPO_T = {"dog": 81, "bird": 254, "boxing": 251, "train": 65}
SUP, NOT, NE = "SUPPORTED", "NOT SUPPORTED", "NOT EVALUABLE"


# ---------------------------------------------------------------- censored order statistics (common section 3)
class Val:
    """An observed value, or a right-censored one (> bound)."""

    def __init__(self, x: float | None, censored_at: float | None = None):
        self.x, self.c = x, censored_at

    @property
    def censored(self):
        return self.x is None

    def __repr__(self):
        return f"{self.x:.3f}" if self.x is not None else (f">{self.c:.3f}" if self.c is not None else "NA")


def cmedian(vals: list[Val]) -> Val:
    """Middle order statistic; censored values rank above every observed one (planned 3 reps -> the 2nd)."""
    obs = sorted(v.x for v in vals if not v.censored)
    cens = [v.c for v in vals if v.censored]
    k = (len(vals) - 1) // 2
    if k < len(obs):
        return Val(obs[k])
    return Val(None, min(cens) if cens else None)


def le(x: Val, b: float):
    """x <= b: True / False / None (undecidable)."""
    if not x.censored:
        return x.x <= b
    return False if (x.c is not None and x.c >= b) else None


def ratio_le(x: Val, y: Val, f: float):
    """x <= f * y under censoring (None = undecidable)."""
    if not x.censored and not y.censored:
        return x.x <= f * y.x
    if not x.censored and y.censored:
        return True if (y.c is not None and x.x <= f * y.c) else None
    if x.censored and not y.censored:
        return False if (x.c is not None and x.c >= f * y.x) else None
    return None


def diff_le(x: Val, y: Val, d: float):
    """x <= y + d."""
    if not x.censored and not y.censored:
        return x.x <= y.x + d
    if x.censored and not y.censored and x.c is not None and x.c >= y.x + d:
        return False
    if not x.censored and y.censored:
        return True if x.x <= (y.c or 0) + d else None
    return None


def absdiff_le(x: Val, y: Val, d: float):
    if not x.censored and not y.censored:
        return abs(x.x - y.x) <= d
    for a_, b_ in ((x, y), (y, x)):
        if a_.censored and not b_.censored and a_.c is not None and a_.c - b_.x > d:
            return False
    return None


def verdict(ok, reason_ne="censoring"):
    return SUP if ok is True else (NOT if ok is False else f"{NE} ({reason_ne})")


# ---------------------------------------------------------------- run records
def run_rec(d: Path, dry: bool) -> dict:
    s = json.load(open(d / "summary.json"))
    ok, why = run_validity_wrn(s, d, dry=dry)
    w = s.get("wrn") or {}
    t = w.get("termination") or {}
    L = s["latency_after_final_move_s"]
    elapsed_after_move = (t.get("elapsed_s") or 0) - (s.get("t_final_move_rel_s") or 0)
    bind = Val(L["continuity_ready"]) if L.get("continuity_ready") is not None else Val(None, elapsed_after_move)
    return {"dir": d, "s": s, "valid": ok, "why": why, "policy": s["policy"], "rho": s.get("rho"), "rep": s.get("rep"),
            "applicable": w.get("applicable_single_version", True), "promotions_before_final_bind": w.get("owner_promotions_before_final_bind"),
            "bind": bind, "verified": Val(L["sink_verified"]) if L.get("sink_verified") is not None else Val(None, elapsed_after_move),
            "B_source": s["d0"]["source_bytes_total_sinks"], "B_fwd": s["d0"]["holder_forwarded_sinks"], "replans": s["d0"]["n_replans"],
            "dups": (s.get("bytes") or {}).get("duplicate", 0), "termination": t, "exposure": w.get("exposure"), "trigger": w.get("progress_trigger")}


def runs_in(exp: str, dry: bool) -> list[dict]:
    root = EV / (("_dryrun_" if dry else "") + exp)
    out = []
    for d in sorted(root.glob("policy=*")):
        if (d / "summary.json").exists():
            out.append(run_rec(d, dry))
    return out


def by_cfg(runs, key):
    g = {}
    for r in runs:
        g.setdefault(key(r), []).append(r)
    return g


def valid_reps(rs, n=3, need_applicable=True):
    """Latest valid run per rep (re-runs), applicable if required; returns (list, n_inapplicable)."""
    per = {}
    for r in sorted(rs, key=lambda r: r["dir"].name):
        if r["valid"]:
            per[r["rep"]] = r
    v = list(per.values())
    inap = [r for r in v if not r["applicable"]]
    if need_applicable:
        v = [r for r in v if r["applicable"]]
    return v, len(inap)


def med(rs, f):
    return cmedian([f(r) if isinstance(f(r), Val) else Val(f(r)) for r in rs])


# ---------------------------------------------------------------- W
def loveu_sel():
    return {r["video_id"]: r for r in csv.DictReader(open(OUT / "expW/loveu_selection.csv", newline=""))}


def workloads():
    return list(REPO_T) + list(loveu_sel())


def T_of(w):
    return REPO_T[w] if w in REPO_T else int(loveu_sel()[w]["frames"])


def w2_unit(w, s, dry):
    rs = runs_in(f"expW_W2_{w}_s{s}", dry)
    out = {"workload": w, "seed": s}
    T = T_of(w)
    cuts = cut_calls(T, 400)
    adj = {c + d for c in cuts for d in range(ADJ + 1)}
    for pol in ("reuse_dyn", "cold"):
        cand = [r for r in rs if r["policy"] == pol and r["valid"]]
        if not cand:
            out[pol] = None; continue
        r = cand[-1]; d = r["dir"]; s_ = r["s"]
        m = {int(x["call"]): x for x in csv.DictReader(open(d / "metrics.csv", newline="")) if x["owner"] == s_["path"][-1]}
        ps = {c: float(x["psnr"]) for c, x in m.items() if x["psnr"] not in ("", "None") and c <= LAST}
        chunk = [float(x["chunk_s"]) for c, x in m.items() if x["chunk_s"] not in ("", "None")]
        ev = list(csv.DictReader(open(d / "events.csv", newline="")))
        bind_call = next((json.loads(e["detail"]).get("call") for e in ev if e["event"].endswith(":sink_bind")), None)
        rec = {"run": d.name, "ttfo_s": s_["latency_after_final_move_s"]["first_output"], "service_s": statistics.median(chunk) if chunk else None,
               "c0": r["termination"].get("first_call_final_owner"), "bind_call": bind_call}
        if pol == "reuse_dyn":
            rj = None if bind_call is None else next((c for c in sorted(ps) if c >= bind_call and ps[c] >= 35.0), None)
            sus = None
            if bind_call is not None:
                for c in range(bind_call, LAST - 8):
                    if all(ps.get(x, 0) >= 35.0 for x in range(c, c + 10)):
                        sus = c; break
            F = s_["final"]
            rec.update({"rejoin": rj is not None, "rejoin_call": rj, "rejoin_calls": None if rj is None else rj - bind_call,
                        "censored_at_call": None if rj is not None else LAST,
                        "rejoin_delay_s": (F["rejoin_rel_s"] - F["first_bound_output_rel_s"]) if (rj is not None and F.get("rejoin_rel_s") is not None and F.get("first_bound_output_rel_s") is not None) else None,
                        "sustained_call": sus, "sustained_calls": None if sus is None else sus - bind_call,
                        "min_psnr_after_crossing": min((ps[c] for c in ps if rj is not None and c >= rj), default=None)})
            # RVC from the destination's reference fingerprints (calls c0 .. bind)
            bp = d / f"node_{s_['path'][-1]}" / "baseline_record.json"
            rvc = None
            if bp.exists() and bind_call is not None and rec["c0"] is not None:
                br = json.load(open(bp))
                rvc = [{"call": c, "calls_before_bind": bind_call - c, "cut_induced": c in adj}
                       for c in range(max(1, rec["c0"]), min(bind_call, len(br) - 1) + 1) if br[c]["sink_vfp"] != br[c - 1]["sink_vfp"]]
            rec["rvc"] = rvc
            rec["cuts_between"] = [c for c in cuts if rec["c0"] is not None and rec["c0"] <= c <= (rj if rj is not None else LAST)]
        else:
            rec["reaches_35"] = any(ps.get(c, 0) >= 35.0 for c in range(M_W, LAST + 1))
        rec["psnr_final_call"] = ps.get(LAST)
        tail = [ps[c] for c in range(LAST - 9, LAST + 1) if c in ps]
        rec["psnr_median_last10"] = statistics.median(tail) if tail else None
        out[pol] = rec
    return out


def agg_w(dry):
    units = [w2_unit(w, s, dry) for w in workloads() for s in (0, 1)]
    ot = [u for u in units if u["reuse_dyn"]]
    # W-H1
    per_w = {}
    for w in workloads():
        v = [u["reuse_dyn"]["ttfo_s"] for u in units if u["workload"] == w and u["reuse_dyn"] and u["reuse_dyn"]["ttfo_s"] is not None]
        per_w[w] = sum(v) / len(v) if v else None
    missing_w = [w for w, v in per_w.items() if v is None]
    svc = [u["reuse_dyn"]["service_s"] for u in ot if u["reuse_dyn"]["service_s"]]
    if len(missing_w) > 2 or not svc:
        h1 = f"{NE} ({len(missing_w)} workloads without a valid OTTER run)"
    else:
        vals = [v for v in per_w.values() if v is not None]
        h1 = verdict(all(v <= 1.0 for v in vals) and (max(vals) - min(vals)) <= 0.25 * statistics.median(svc))
    # W-H2 (all units primary) + S1, S2
    def h2(us, label, minimum):
        n = len(us)
        if n < minimum:
            return {"set": label, "n": n, "verdict": f"counts only (n < {minimum})" if minimum == 10 else f"{NE}", "successes": sum(1 for u in us if u["reuse_dyn"]["rejoin"])}
        k = sum(1 for u in us if u["reuse_dyn"]["rejoin"])
        return {"set": label, "n": n, "successes": k, "share": k / n, "verdict": verdict(k / n >= 0.80)}
    missing_units = 40 - len(ot)
    h2p = h2(ot, "all units", 1) if missing_units <= 4 else {"set": "all units", "n": len(ot), "verdict": f"{NE} ({missing_units} units without a valid OTTER run)"}
    s1 = [u for u in ot if u["reuse_dyn"]["rvc"] is not None and not u["reuse_dyn"]["rvc"]]
    s2 = [u for u in ot if u["reuse_dyn"]["rvc"] is not None and not any(e["cut_induced"] for e in u["reuse_dyn"]["rvc"])]
    h2s1, h2s2 = h2(s1, "S1: no RVC", 10), h2(s2, "S2: no cut-induced RVC", 10)
    h2s1["excluded"] = len(ot) - len(s1); h2s2["excluded"] = len(ot) - len(s2)
    # W-H3
    q = [u for u in ot if u["reuse_dyn"]["rejoin"]]
    qc = [u for u in q if u["cold"]]
    if len(q) < 10 or (len(q) - len(qc)) > 0.10 * len(q):
        h3 = f"{NE} (qualifying units {len(q)}, without a valid Cold run {len(q) - len(qc)})"
    else:
        share = sum(1 for u in qc if u["cold"]["reaches_35"]) / len(qc)
        h3 = verdict(share <= 0.20) + f" (Cold reaches 35 dB in {share:.1%} of {len(qc)})"
    # W1
    w1 = {}
    for w in workloads():
        for s in (0, 1):
            ds = sorted((EV / (("_dryrun_" if dry else "") + "expW_W1")).glob(f"{w}_s{s}_2*"))
            if ds and (ds[-1] / "w1_summary.json").exists():
                w1[f"{w}_s{s}"] = json.load(open(ds[-1] / "w1_summary.json"))
    return {"units": units, "W-H1": h1, "W-H1 per workload TTFO": per_w, "W-H2 primary": h2p, "W-H2 S1": h2s1, "W-H2 S2": h2s2, "W-H3": h3,
            "W1": {k: {kk: v.get(kk) for kk in ("first_pass_within_clip", "repeated_within_clip", "boundary_associated", "P_w", "stable_at_w")} for k, v in w1.items()},
            "W1 units present": len(w1)}


# ---------------------------------------------------------------- R
def agg_r(dry):
    res = {"cells": {}, "manipulation_check": {}}
    for c, exp in ((0, "expR_c0"), (3, "expR_c3")):
        g = by_cfg(runs_in(exp, dry), lambda r: (r["policy"], r["rho"]))
        for rho in (0.5, 1.0, 2.0, 4.0, 8.0):
            cell = {}
            for pol in ("restart", "split", "reuse_dyn"):
                rs = g.get((pol, rho), [])
                v, inap = valid_reps(rs)
                for r in v:
                    r["discarded"] = discarded_sinks(r["dir"], r["s"])
                cell[pol] = {"valid_applicable": len(v), "inapplicable": inap, "runs": len(rs),
                             "B_source": med(v, lambda r: r["B_source"]) if len(v) == 3 else None,
                             "discarded": med(v, lambda r: r["discarded"]) if len(v) == 3 else None,
                             "bind": med(v, lambda r: r["bind"]) if len(v) == 3 else None,
                             "exposure_valid_majority": (sum(1 for r in v if (r["exposure"] or {}).get("exposure_valid")) >= 2) if c == 3 and len(v) == 3 else None,
                             "exposure": [r["exposure"] for r in v] if c == 3 else None}
            m1, m2 = cell["restart"], cell["split"]
            ok3 = m1["B_source"] is not None and m2["B_source"] is not None
            if not ok3:
                h1 = f"{NE} (fewer than 3 valid applicable reps)"; h2 = h1; h3 = h1
            else:
                R1, R2 = m1["B_source"].x - 1, m2["B_source"].x - 1
                red = None if R1 < 0.10 else 1 - R2 / R1
                h1 = f"{NE} (R(M1 only) = {R1:.3f} < 0.10)" if red is None else verdict(m2["B_source"].x <= 1.10 and red >= 0.75) + f" (B_src {m1['B_source']} / {m2['B_source']}, R {R1:.3f} / {R2:.3f}, reduction {red:.1%})"
                h2 = verdict(m2["discarded"].x <= 0.10) + f" (discarded M1+M2 {m2['discarded']}, M1 only {m1['discarded']})"
                if c == 0:
                    h3 = verdict(absdiff_le(m2["bind"], m1["bind"], 1.0)) + f" (bind {m2['bind']} vs {m1['bind']})"
                elif rho in (0.5, 1.0, 2.0):
                    if not (m1["exposure_valid_majority"] and m2["exposure_valid_majority"]):
                        h3 = f"{NE} (contention not exposure-valid: M1 only {m1['exposure_valid_majority']}, M1+M2 {m2['exposure_valid_majority']})"
                    else:
                        h3 = verdict(diff_le(m2["bind"], m1["bind"], -1.0)) + f" (bind {m2['bind']} vs {m1['bind']})"
                else:
                    h3 = f"descriptive (bind {m2['bind']} vs {m1['bind']})"
                if c == 0 and rho in (2.0, 4.0, 8.0):
                    res["manipulation_check"][str(rho)] = ("MET" if m1["discarded"].x >= 0.75 * 2 / rho else "NOT MET") + f" (discarded M1 only {m1['discarded']} vs {0.75 * 2 / rho:.3f})"
            res["cells"][f"rho={rho:g},c={c}"] = {"R-H1": h1, "R-H2": h2, ("R-H3(a)" if c == 0 else "R-H3(b)"): h3,
                                                   "policies": {p: {k: (repr(v) if isinstance(v, Val) else v) for k, v in x.items() if k != "exposure"} for p, x in cell.items()}}
    return res


# ---------------------------------------------------------------- N
N_CLASS = {1: "no change", 4: "no change", 7: "no change", 9: "alternative available", 2: "no alternative", 3: "no alternative",
           5: "no alternative", 6: "no alternative", 8: "no alternative", 10: "no alternative"}


def agg_n(dry):
    res = {}
    for cell in range(1, 11):
        g = by_cfg(runs_in(f"expN_cell{cell}", dry), lambda r: r["policy"])
        pol = {}
        for p in ("reuse_aware_in", "reuse_dyn", "split"):
            v, inap = valid_reps(g.get(p, []), need_applicable=False)
            pol[p] = {"n": len(v), "bind": med(v, lambda r: r["bind"]) if len(v) == 3 else None, "B_source": med(v, lambda r: r["B_source"]) if len(v) == 3 else None,
                      "replans": med(v, lambda r: r["replans"]) if len(v) == 3 else None, "dups": med(v, lambda r: r["dups"]) if len(v) == 3 else None,
                      "replans_per_rep": [r["replans"] for r in v], "timeouts": [bool(r["termination"].get("timed_out")) for r in v],
                      "trigger": [r["trigger"] for r in v], "owner_promotions_before_final_bind": [r["promotions_before_final_bind"] for r in v]}
        am, ed = pol["reuse_aware_in"], pol["reuse_dyn"]
        cls = N_CLASS[cell]
        if am["bind"] is None or ed["bind"] is None:
            v_ = f"{NE} (fewer than 3 valid reps)"
        elif cls != "no change" and any(sum(1 for t in pol[p]["trigger"] if t and t.get("t_rel") is not None) < 2 for p in ("reuse_aware_in", "reuse_dyn")):
            v_ = f"{NE} (degradation trigger fired in fewer than 2 of 3 reps)"
        elif cls == "no change":
            c1 = ed["replans"].x == 0
            c2 = absdiff_le(ed["bind"], am["bind"], 1.0)
            c3 = ed["B_source"].x <= am["B_source"].x + 0.02
            v_ = ("N-H1 " + verdict(None if c2 is None else (c1 and c2 and c3))) + f" (re-plans {ed['replans']}, bind {ed['bind']} vs {am['bind']}, B_src {ed['B_source']} vs {am['B_source']})"
        elif cls == "alternative available":
            c1 = ratio_le(ed["bind"], am["bind"], 0.5)
            v_ = "N-H2 " + verdict(None if c1 is None else (c1 and ed["replans"].x <= 2 and ed["dups"].x == 0)) + f" (bind {ed['bind']} vs {am['bind']}, re-plans {ed['replans']}, dups {ed['dups']})"
        else:
            c1 = diff_le(ed["bind"], am["bind"], 1.0)
            c2 = ed["B_source"].x <= am["B_source"].x + 0.05
            v_ = "N-H3 " + verdict(None if c1 is None else (c1 and c2)) + f" (bind {ed['bind']} vs {am['bind']}, B_src {ed['B_source']} vs {am['B_source']}, re-plans {ed['replans']})"
        effect = None
        if am["bind"] is not None and ed["bind"] is not None and not am["bind"].censored and not ed["bind"].censored:
            if ed["bind"].x <= am["bind"].x - 1.0:
                effect = "beneficial"
            elif ed["bind"].x >= am["bind"].x + 1.0 or ed["B_source"].x >= am["B_source"].x + 0.05:
                effect = "harmful"
            else:
                effect = "neutral"
            if effect == "beneficial" and ed["B_source"].x >= am["B_source"].x + 0.05:
                effect += " (traffic flagged)"
        res[str(cell)] = {"class": cls, "verdict": v_, "effect": effect,
                          "policies": {p: {k: (repr(v) if isinstance(v, Val) else v) for k, v in x.items()} for p, x in pol.items()}}
    return res


# ---------------------------------------------------------------- V (M3-v2 holdout, expN/m3v2_holdout_plan.md)
V_CLASS = {1: "no change", 2: "alternative available", 3: "no alternative", 4: "alternative available", 5: "alternative available",
           6: "no alternative", 7: "no alternative", 8: "no alternative"}


V_AMENDED = {1: "expV_a1_cell1", 2: "expV_a1_cell2", 3: "expV_a1_cell3", 8: "expV_a1_cell8"}   # amendment 1 re-runs supersede the originals


def agg_v(dry):
    res = {}
    for cell in range(1, 9):
        exp = V_AMENDED.get(cell, f"expV_cell{cell}")
        if cell in V_AMENDED and not (EV / (("_dryrun_" if dry else "") + exp)).exists():
            exp = f"expV_cell{cell}"   # amendment runs not present yet: the superseded originals are shown, flagged
        g = by_cfg(runs_in(exp, dry), lambda r: r["policy"])
        pol = {}
        for p in ("reuse_aware_in", "split", "reuse_dyn", "reuse_dyn2"):
            v, inap = valid_reps(g.get(p, []), need_applicable=False)
            for r in v:
                r["discarded"] = discarded_sinks(r["dir"], r["s"])
            pol[p] = {"n": len(v), "bind": med(v, lambda r: r["bind"]) if len(v) == 3 else None, "B_source": med(v, lambda r: r["B_source"]) if len(v) == 3 else None,
                      "replans": med(v, lambda r: r["replans"]) if len(v) == 3 else None, "dups": med(v, lambda r: r["dups"]) if len(v) == 3 else None,
                      "discarded": med(v, lambda r: r["discarded"]) if len(v) == 3 else None,
                      "replans_per_rep": [r["replans"] for r in v], "probes_per_rep": [sum(1 for x in r["s"]["d0"]["replans"] if x.get("probe")) for r in v],
                      "timeouts": [bool(r["termination"].get("timed_out")) for r in v], "trigger_fired": [bool((r["trigger"] or {}).get("t_rel")) for r in v]}
        am, v1, v2 = pol["reuse_aware_in"], pol["reuse_dyn"], pol["reuse_dyn2"]
        cls = V_CLASS[cell]
        out = {"class": cls}
        if am["bind"] is None or v2["bind"] is None:
            out["verdict"] = f"{NE} (fewer than 3 valid reps)"
        elif cls != "no change" and sum(v2["trigger_fired"]) < 2:
            out["verdict"] = f"{NE} (trigger fired in fewer than 2 of 3 reps)"
        elif cls == "no change":
            c2 = absdiff_le(v2["bind"], am["bind"], 1.0)
            out["verdict"] = "V-H1 " + verdict(None if c2 is None else (v2["replans"].x == 0 and c2 and v2["B_source"].x <= am["B_source"].x + 0.02)) + f" (re-plans {v2['replans']}, bind {v2['bind']} vs {am['bind']}, B_src {v2['B_source']} vs {am['B_source']})"
        elif cls == "alternative available":
            c1 = ratio_le(v2["bind"], am["bind"], 0.5)
            out["verdict"] = "V-H2 " + verdict(None if c1 is None else (c1 and v2["replans"].x <= 2 and v2["dups"].x == 0)) + f" (bind {v2['bind']} vs {am['bind']}, re-plans {v2['replans']}, dups {v2['dups']})"
        else:
            c1 = diff_le(v2["bind"], am["bind"], 1.0)
            out["verdict"] = "V-H3 " + verdict(None if c1 is None else (c1 and v2["B_source"].x <= am["B_source"].x + 0.05)) + f" (bind {v2['bind']} vs {am['bind']}, B_src {v2['B_source']} vs {am['B_source']}, re-plans {v2['replans']})"
        if v1["bind"] is None or v2["bind"] is None:
            out["V-H4"] = f"{NE} (fewer than 3 valid reps)"
        else:
            c1 = diff_le(v2["bind"], v1["bind"], 1.0)
            out["V-H4"] = verdict(None if c1 is None else (c1 and v2["B_source"].x <= v1["B_source"].x + 0.05 and v2["replans"].x <= v1["replans"].x)) + f" (v2 vs v1: bind {v2['bind']} vs {v1['bind']}, B_src {v2['B_source']} vs {v1['B_source']}, re-plans {v2['replans']} vs {v1['replans']})"
        out["policies"] = {p: {k: (repr(v) if isinstance(v, Val) else v) for k, v in x.items()} for p, x in pol.items()}
        out["source"] = exp + ("" if exp.startswith("expV_a1") or cell not in V_AMENDED else " (SUPERSEDED by amendment 1; re-run pending)")
        res[str(cell)] = out
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    out = {"W": agg_w(a.dry), "R": agg_r(a.dry), "N": agg_n(a.dry), "V": agg_v(a.dry)}
    pre = "_dryrun_" if a.dry else ""
    units = out["W"].pop("units")
    with open(OUT / f"{pre}w2_table.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["workload", "seed", "ttfo_s", "bind_call", "rejoin", "rejoin_calls", "rejoin_delay_s", "censored_at_call", "sustained_calls", "psnr_final_call",
                     "psnr_median_last10", "min_psnr_after_crossing", "rvc_events", "cut_rvc", "cuts_between", "cold_reaches_35", "cold_psnr_median_last10"])
        for u in units:
            o, c = u["reuse_dyn"] or {}, u["cold"] or {}
            wr.writerow([u["workload"], u["seed"], o.get("ttfo_s"), o.get("bind_call"), o.get("rejoin"), o.get("rejoin_calls"), o.get("rejoin_delay_s"), o.get("censored_at_call"),
                         o.get("sustained_calls"), o.get("psnr_final_call"), o.get("psnr_median_last10"), o.get("min_psnr_after_crossing"),
                         json.dumps(o.get("rvc")), any(e["cut_induced"] for e in (o.get("rvc") or [])), json.dumps(o.get("cuts_between")), c.get("reaches_35"), c.get("psnr_median_last10")])
    (OUT / f"{pre}wrn_results.json").write_text(json.dumps(out, indent=1, default=repr))
    L = [f"# W / R / N results{' (LOOPBACK DRY RUN - not results)' if a.dry else ''}", "", "## W", ""]
    for k in ("W-H1", "W-H2 primary", "W-H2 S1", "W-H2 S2", "W-H3"):
        L.append(f"- **{k}**: {out['W'][k]}")
    L.append(f"- W1 units present: {out['W']['W1 units present']} of 40 (per-unit table: `{pre}w2_table.csv`; W1 detail in `{pre}wrn_results.json`)")
    L += ["", "## R", "", "| cell | R-H1 | R-H2 | R-H3 |", "|---|---|---|---|"]
    for k, v in out["R"]["cells"].items():
        L.append(f"| {k} | {v['R-H1']} | {v['R-H2']} | {v.get('R-H3(a)', v.get('R-H3(b)'))} |")
    L += ["", f"Manipulation check (c = 0): {out['R']['manipulation_check']}", "", "## N", "", "| cell | class | verdict | effect |", "|---|---|---|---|"]
    for k, v in out["N"].items():
        L.append(f"| {k} | {v['class']} | {v['verdict']} | {v['effect']} |")
    L += ["", "## V (M3-v2 holdout)", "", "| cell | class | verdict (v2 vs at moves) | V-H4 (v2 vs v1) |", "|---|---|---|---|"]
    for k, v in out["V"].items():
        L.append(f"| V{k} | {v['class']} | {v['verdict']} | {v.get('V-H4')} |" + (f" {v['source']}" if "SUPERSEDED" in v.get("source", "") else ""))
    (OUT / f"{pre}wrn_results.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
