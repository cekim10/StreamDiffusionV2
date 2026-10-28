#!/usr/bin/env python3
"""Experiment VD-5 aggregation (osdi/expVD5/preregistration.md sections 4-7): does restoring the source recent KV and
the exact source Sink together (RS3) resolve P1 and P2? 2 x 2 with VD-4's B0, R, S3 (reused). VD-3's frozen
thresholds and rules (`vd3_thresholds.json`, `aggregate_vd3.rules`) are reused unchanged; VD-4's resolution rule.

Writes vd5_results.{md,json}: validity (RS3 checks incl. the joint-restoration checks, V0 = REF, the reuse gate), the
numeric table of the 12 cells, the blinded session (block A flags against REF of the same session; rater calibration;
block B paired judgments), the formal resolution of RS3, RS3 vs R and vs S3, and the interaction per cell and metric.

    python tools/eval/aggregate_vd5.py [--root DIR] [--dry]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import aggregate_vd3 as a3  # noqa: E402
import aggregate_vd4 as a4  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/expVD5"
THR = ROOT / "results/evaluation/osdi/expVD3/vd3_thresholds.json"
CONFIRM = a4.CONFIRM
VISUAL = ["dog_s1|OT-1", "dog_s1|OT-L", "train_s0|OT-1", "butterfly-feeding-slow-motion_s1|OT-L", "audi-snow-trail_s0|OT-L", "audi-snow-trail_s1|OT-1"]
GATE_ROOT = ROOT / "results/evaluation/expVD5g"
GATE_UNIT, GATE_NAMES = "dog_s1", ("B0", "R", "S3")   # reuse gate: these VD-4 runs re-run at the VD-5 commit (OT-1)
NAMES = ("B0", "R", "S3", "RS3")
PH = ("P1", "P2a", "P2b", "P3")
# block A field indices: 0 jump at M, 1 motion reversal, 2 content change, 3 identity, 4 color, 5 flicker, 6 jump at B
VIS = {"P1": [0], "P2a": [2, 3, 4], "P2b": [5, 1], "P3": [6]}
FLAG = {"mild", "strong", "reversed", "change", "changed", "shift", "flicker", "jump"}
ALLOWED_A = ({"none", "mild", "strong"}, {"none", "reversed", "unclear"}, {"none", "change"}, {"kept", "changed", "unsure"}, {"none", "shift"}, {"none", "flicker"}, {"none", "jump"})
ALLOWED_B = {"left", "right", "no difference"}
VD5_REQUIRED = ("vd5_slot_sets_disjoint", "vd5_slot_sets_cover_ring", "vd5_no_temporary_sink", "vd5_ring_k_equal_snapshot", "vd5_ring_v_equal_snapshot",
                "vd5_ring_positions_rows_equal_snapshot", "vd5_bind_recent_k_unchanged", "vd5_bind_recent_v_unchanged", "vd5_bind_positions_unchanged")
FROZEN_REQUIRED = ("meta_positions_equal_snapshot", "recent_k_equal", "recent_v_equal", "recent_positions_equal", "sink_k_equal", "sink_v_equal", "sink_positions_equal")
SUPP_REQUIRED = ("positions_final_equal_snapshot", "positions_rows_final_equal_snapshot", "recent_k_equal_per_layer_slot", "recent_v_equal_per_layer_slot",
                 "sink_k_equal_per_layer_slot", "sink_v_equal_per_layer_slot", "recent_positions_rows_equal", "sink_positions_rows_equal")
METRICS = ("V1", "D_c", "late D_c", "C_c", "dE_cross", "warp excess", "frame-diff ratio")
RATES = {"1 Gbps": 1e9, "10 Gbps": 10e9}


def cid(name: str, x: str) -> str:
    return f"VD5{x}-RS3" if name == "RS3" else f"VD4{x}-{name}"


def badness(v: dict) -> dict:
    """Each metric in the 'lower is closer to REF' form (preregistration section 7): V1; -D_c; -late D_c; C_c; dE_cross;
    warp excess eO - eR; |dO / dR - 1|."""
    sl, late = v["P"]["sinkless"], v["P"]["sl_late"]
    neg = lambda x: None if x is None else -x  # noqa: E731
    fd = None if (sl.get("dO") is None or not sl.get("dR")) else abs(sl["dO"] / sl["dR"] - 1.0)
    we = None if (sl.get("eO") is None or sl.get("eR") is None) else sl["eO"] - sl["eR"]
    return {"V1": v["v1_reset"], "D_c": neg(sl.get("D_c")), "late D_c": neg(late.get("D_c")), "C_c": sl.get("C_c"), "dE_cross": sl.get("dE_cross"),
            "warp excess": we, "frame-diff ratio": fd}


def tolerances(tol: dict, p99: float, eR: float) -> dict:
    return {"V1": 0.10 * p99, "D_c": tol["dino"], "late D_c": tol["dino"], "C_c": tol["dE_anchor"], "dE_cross": tol["dE_cross"],
            "warp excess": a3.REL_LIMIT * max(eR, a3.ABS_FLOOR), "frame-diff ratio": 0.10}


def table_rows(path: Path, n_fields: int) -> list:
    rows = []
    for line in path.read_text().splitlines():
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= n_fields + 1 and re.fullmatch(r"([0-9A-F]{6}|T\d\d)", cols[0] or ""):
            rows.append((cols[0], [x.lower() for x in cols[1:n_fields + 1]], cols[n_fields + 1] if len(cols) > n_fields + 1 else ""))
    return rows


def session(d: Path, pre: str) -> dict | None:
    """Both blocks recorded and the key matching the forms' SHA-256; else None (not inspected)."""
    ia, ib, fa, kp = d / f"{pre}vd5_inspection_A.md", d / f"{pre}vd5_inspection_B.md", d / f"{pre}vd5_inspection_form_A.md", d / f"{pre}vd5_blind_key.json"
    if not all(p.exists() for p in (ia, ib, fa, kp)) or "STATUS: RECORDED" not in ia.read_text() or "STATUS: RECORDED" not in ib.read_text():
        return None
    kb = kp.read_bytes()
    if hashlib.sha256(kb).hexdigest() != re.search(r"SHA-256 `([0-9a-f]{64})`", fa.read_text()).group(1):
        sys.exit("[vd5] key SHA-256 differs from the form's")
    K = json.loads(kb)
    A, bad = {}, []
    for code, vals, note in table_rows(ia, 7):
        if code not in K["block_a"]:
            continue
        bad += [f"{code}:{i}:{v}" for i, v in enumerate(vals) if v not in ALLOWED_A[i]]
        A[code] = {**K["block_a"][code], "values": vals, "flags": [v in FLAG for v in vals], "note": note}
    B = {}
    for tid, vals, note in table_rows(ib, 2):
        if tid not in K["block_b"]:
            continue
        bad += [f"{tid}:{i}:{v}" for i, v in enumerate(vals) if v not in ALLOWED_B]
        B[tid] = {**K["block_b"][tid], "values": vals, "note": note}
    return {"A": A, "B": B, "vocabulary_errors": bad, "complete": len(A) == len(K["block_a"]) and len(B) == len(K["block_b"])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT / "results/evaluation/expVC"))
    ap.add_argument("--gate_root", default=str(GATE_ROOT))
    ap.add_argument("--out", default=str(OUT / "vd5_results"))
    ap.add_argument("--insp_dir", default=str(OUT))
    ap.add_argument("--thresholds", default=str(THR))
    ap.add_argument("--dry", action="store_true", help="synthetic units (pixel embedder); thresholds SHA not enforced; _dryrun_ session files")
    a = ap.parse_args()
    root, pre = Path(a.root), ("_dryrun_" if a.dry else "")
    tb = Path(a.thresholds).read_bytes()
    if not a.dry and hashlib.sha256(tb).hexdigest()[:16] != a4.THR_SHA_FROZEN:
        sys.exit("[vd5] the thresholds differ from VD-3's frozen file")
    T = json.loads(tb)
    vd4_res = ROOT / "results/evaluation/osdi/expVD4/vd4_results.json"
    vd4_num = json.loads(vd4_res.read_text())["numeric"] if (vd4_res.exists() and not a.dry) else {}
    # ---- validity
    validity, numeric, bad_cells = [], {n: {} for n in NAMES}, {}
    gate = {"unit": GATE_UNIT, "runs": {}}
    for n in GATE_NAMES:
        new, old = a4.digests(Path(a.gate_root) / GATE_UNIT, cid(n, "1")), a4.digests(root / GATE_UNIT, cid(n, "1"))
        gate["runs"][n] = {"calls": len(new), "stored_calls": len(old), "differing": sum(1 for c in set(new) | set(old) if new.get(c) != old.get(c))}
    gate["pass"] = all(r["calls"] > 0 and r["calls"] == r["stored_calls"] and r["differing"] == 0 for r in gate["runs"].values())
    for key in CONFIRM:
        unit_name, ot = key.split("|"); x = ot.split("-")[1]
        unit = root / unit_name
        if not (unit / "metrics.json").exists():
            continue
        M = json.loads((unit / "metrics.json").read_text())
        a3.EMB = "dino" if "dino" in M.get("embedders", []) else M.get("embedders", ["dino"])[0]
        ctrl, tol, p99 = a3.cell(unit, M, ot), a3.thresholds_for(T, key), M.get("ref_spike_P99")
        s = a4.vd4_summary(unit, cid("RS3", x))
        if s:
            v4 = s.get("vd4") or {}
            ck, cs = v4.get("checks") or {}, v4.get("checks_supp") or {}
            miss = [c for c in FROZEN_REQUIRED if c not in ck] + [f"supp:{c}" for c in SUPP_REQUIRED + VD5_REQUIRED if c not in cs]
            fail = [c for c, v in ck.items() if v is False] + [f"supp:{c}" for c, v in cs.items() if v is False]
            validity.append({"cell": key, "check": "RS3: stream valid, oracle checks, joint-restoration checks", "pass": bool(s.get("valid")) and not miss and not fail and s.get("prefix_identical_to_reference") is not False,
                             "missing": miss, "failed": fail, "bind": (v4.get("supp") or {}).get("vd5_bind"), "bytes": v4.get("bytes")})
        if key in VISUAL:
            v0 = a4.vd4_summary(unit, f"VD4{x}-V0")
            validity.append({"cell": key, "check": "V0 equals REF after the move", "pass": bool(v0) and bool(v0.get("valid")) and bool((v0.get("vd4") or {}).get("v0_pass", a.dry))})
        for n in NAMES:
            if not a4.vd4_summary(unit, cid(n, x)):
                continue
            v = a3.cell(unit, M, cid(n, x))
            if v is None or ctrl is None or tol is None:
                continue
            rr = a3.rules(v, n, tol, p99, ctrl)
            numeric[n][key] = {"rules": {p: bool(rr[p]) for p in PH}, "v1": v["v1_reset"], "late_D_c": v["P"]["sl_late"].get("D_c"), "X_late": v["X_late"],
                               "sinkless": {k_: v["P"]["sinkless"].get(k_) for k_ in ("D_c", "C_c", "dE_cross", "eO", "eR", "dO", "dR")},
                               "badness": badness(v), "tol": tolerances(tol, p99, v["P"]["sinkless"].get("eR") or 0.0), "p99": p99,
                               "bytes": (a4.vd4_summary(unit, cid(n, x)).get("vd4") or {}).get("bytes")}
    reuse_same = {n: all(numeric[n][k]["rules"] == vd4_num[n][k]["rules"] and abs(numeric[n][k]["v1"] - vd4_num[n][k]["v1"]) < 1e-12 for k in numeric[n] if k in vd4_num.get(n, {}))
                  for n in ("B0", "R", "S3")} if vd4_num else {}
    valid_all = all(r["pass"] for r in validity) and gate["pass"] and len(numeric["RS3"]) == len(CONFIRM)
    # ---- the blinded session
    S = session(Path(a.insp_dir), pre)
    vis, calib, pairs = {}, None, None
    if S:
        for code, r in S["A"].items():
            if not r["repeat"]:
                vis.setdefault(r["cell"], {})[r["name"]] = r["flags"]
        reps = [r for r in S["A"].values() if r["repeat"]]
        first = {(r["cell"], r["name"]): r["values"] for r in S["A"].values() if not r["repeat"]}
        rep_same = sum(1 for r in reps if first.get((r["cell"], r["name"])) == r["values"])
        v0_fields = [sum(1 for c in VISUAL if (vis.get(c) or {}).get("V0", [False] * 7)[i]) for i in range(7)]
        ref_fields = [sum(1 for c in VISUAL if (vis.get(c) or {}).get("REF", [False] * 7)[i]) for i in range(7)]
        catch = [t for t in S["B"].values() if t["kind"] == "catch"]
        catch_ok = sum(1 for t in catch if t["values"] == ["no difference", "no difference"])
        calib = {"v0_flags_per_field": v0_fields, "ref_flags_per_field": ref_fields, "v0_ok": all(v <= r + 1 for v, r in zip(v0_fields, ref_fields)),
                 "catch_ok": catch_ok, "catch": len(catch), "repeats_identical": rep_same, "repeats": len(reps)}
        calib["pass"] = calib["v0_ok"] and catch_ok == len(catch) and rep_same >= 3
        pairs = {}
        for t in S["B"].values():
            if t["kind"] != "pair":
                continue
            other = t["left"] if t["right"] == "RS3" else t["right"]
            side = "left" if t["left"] == "RS3" else "right"
            res = ["RS3 better" if v == side else ("no difference" if v == "no difference" else "RS3 worse") for v in t["values"]]
            pairs.setdefault(other, []).append({"cell": t["cell"], "at M": res[0], "closer to REF": res[1]})
    # ---- formal resolution of RS3; within-session descriptive status of the controls
    res = {}
    for n in NAMES + (("REF", "V0") if S else ()):
        if n in ("REF", "V0"):
            res[n] = {"flags": {p: sum(1 for c in VISUAL if any((vis.get(c) or {}).get(n, [False] * 7)[i] for i in VIS[p])) for p in PH}}
            continue
        row = {"phases": {}}
        for p in PH:
            npass = sum(1 for k in CONFIRM if k in numeric[n] and numeric[n][k]["rules"][p])
            flags = sum(1 for c in VISUAL if any((vis.get(c) or {}).get(n, [False] * 7)[i] for i in VIS[p])) if S else 0
            refl = sum(1 for c in VISUAL if any((vis.get(c) or {}).get("REF", [False] * 7)[i] for i in VIS[p])) if S else 0
            st = a4.resolution(npass, len([k for k in CONFIRM if k in numeric[n]]), flags, refl, len(VISUAL) if S else 0)
            row["phases"][p] = {"numeric_pass": npass, "of": len([k for k in CONFIRM if k in numeric[n]]), "visual_flags": flags, "ref_flags_same_session": refl,
                                "resolution": st if n == "RS3" else f"{st} (VD-5 session; descriptive)"}
        tot = max((sum(v for kk, v in (numeric[n][k]["bytes"] or {}).items() if kk.startswith("oracle")) for k in numeric[n]), default=0)
        row["oracle_bytes"] = tot
        row["transfer_lower_bound_s"] = {r_: tot * 8 / b_ for r_, b_ in RATES.items()}
        res[n] = row
    calib_ok = bool(calib and calib["pass"])
    rs = res["RS3"]["phases"]
    good = lambda p: rs[p]["resolution"] in ("STRICT", "NEAR")  # noqa: E731
    num12 = lambda p: rs[p]["numeric_pass"] == rs[p]["of"] == 12  # noqa: E731
    if not S:
        primary = "not inspected"
    elif calib_ok:
        primary = ("fully yes" if all(good(p) for p in ("P1", "P2a", "P2b")) else
                   "yes" if good("P1") and any(good(p) and rs[o]["numeric_pass"] >= 11 for p, o in (("P2a", "P2b"), ("P2b", "P2a"))) else "no")
    else:
        primary = ("numeric only (rater calibration failed): " + ("fully yes" if all(num12(p) for p in ("P1", "P2a", "P2b")) else
                   "yes" if num12("P1") and any(num12(p) and rs[o]["numeric_pass"] >= 11 for p, o in (("P2a", "P2b"), ("P2b", "P2a"))) else "no"))
    # ---- RS3 vs R (P1) and vs S3 (P2): numeric non-inferiority on the 12 cells; block B tallies
    ni = {"vs R (P1)": [], "vs S3 (P2)": []}
    for k in CONFIRM:
        if not all(k in numeric[n] for n in NAMES):
            continue
        r3, r, s3 = numeric["RS3"][k], numeric["R"][k], numeric["S3"][k]
        t = r3["tol"]
        ni["vs R (P1)"].append({"cell": k, "ok": r3["v1"] <= r["v1"] + t["V1"], "V1 RS3": r3["v1"], "V1 R": r["v1"], "margin": t["V1"]})
        a_, b_ = r3["sinkless"], s3["sinkless"]
        T_ = a3.thresholds_for(T, k)
        ok = (a_["D_c"] >= b_["D_c"] - T_["dino"] and a_["C_c"] <= b_["C_c"] + T_["dE_anchor"]
              and (a_["eO"] - a_["eR"]) <= (b_["eO"] - b_["eR"]) + t["warp excess"] and abs(a_["dO"] - b_["dO"]) <= 0.10 * b_["dR"])
        ni["vs S3 (P2)"].append({"cell": k, "ok": ok})

    def tally(lst, q):
        return {w: sum(1 for x in lst if x[q] == w) for w in ("RS3 better", "no difference", "RS3 worse")}
    comp = {"RS3 vs R": {"numeric_non_inferior_P1": sum(x["ok"] for x in ni["vs R (P1)"]), "of": len(ni["vs R (P1)"]),
                         "block_B_at_M": tally((pairs or {}).get("R", []), "at M") if pairs is not None else None},
            "RS3 vs S3": {"numeric_non_inferior_P2": sum(x["ok"] for x in ni["vs S3 (P2)"]), "of": len(ni["vs S3 (P2)"]),
                          "block_B_closer_to_REF": tally((pairs or {}).get("S3", []), "closer to REF") if pairs is not None else None}}
    for k_, q, n_ in (("RS3 vs R", "block_B_at_M", "numeric_non_inferior_P1"), ("RS3 vs S3", "block_B_closer_to_REF", "numeric_non_inferior_P2")):
        bb = comp[k_][q]
        comp[k_]["non_inferior"] = comp[k_][n_] == comp[k_]["of"] == 12 and (bb is None or bb["RS3 worse"] <= bb["RS3 better"])
    # ---- interaction I = (RS3 - S3) - (R - B0) on the badness form, per cell and metric
    inter, cls = {}, {m: {"additive": 0, "synergistic": 0, "antagonistic": 0, "missing": 0} for m in METRICS}
    for k in CONFIRM:
        if not all(k in numeric[n] for n in NAMES):
            continue
        bd = {n: numeric[n][k]["badness"] for n in NAMES}
        tl = numeric["RS3"][k]["tol"]
        inter[k] = {}
        for m in METRICS:
            vals = [bd[n][m] for n in NAMES]
            if any(v is None for v in vals):
                inter[k][m] = None; cls[m]["missing"] += 1; continue
            I = (bd["RS3"][m] - bd["S3"][m]) - (bd["R"][m] - bd["B0"][m])
            c = "additive" if abs(I) <= tl[m] else ("synergistic" if I < 0 else "antagonistic")
            inter[k][m] = {"I": I, "tol": tl[m], "class": c, "additive_prediction": bd["R"][m] + bd["S3"][m] - bd["B0"][m], "RS3": bd["RS3"][m]}
            cls[m][c] += 1
    n_int = len(inter)
    complementary = n_int == 12 and all(cls[m]["additive"] >= 10 for m in METRICS)
    interaction = [m for m in METRICS if cls[m]["synergistic"] >= 3 or cls[m]["antagonistic"] >= 3]
    reading = "complementary" if complementary else ("interaction: " + ", ".join(interaction) if interaction else "mixed")
    out = {"validity": validity, "reuse_gate": gate, "reused_values_equal_vd4": reuse_same, "valid": valid_all, "numeric": numeric, "resolution": res,
           "calibration": calib, "primary": primary, "comparisons": comp, "non_inferiority_cells": ni, "pairs": pairs, "interaction": inter,
           "interaction_classes": cls, "interaction_reading": reading, "session_complete": S["complete"] if S else None,
           "vocabulary_errors": S["vocabulary_errors"] if S else None, "notes": {c: r["note"] for c, r in (S["A"].items() if S else []) if r["note"]}}
    Path(a.out + ".json").write_text(json.dumps(out, indent=1, default=str))
    f = lambda x, d=3: "-" if x is None else f"{x:+.{d}f}"  # noqa: E731
    L = ["# VD-5 results (oracle sufficiency of joint recent KV + exact Sink restoration; not a practical migration)", "",
         f"Thresholds: VD-3's frozen `vd3_thresholds.json` (SHA-256 {a4.THR_SHA_FROZEN}); VD-4's resolution rule. Validity: **{'PASS' if valid_all else 'FAIL'}**.", "",
         "## Validity", "",
         f"- reuse gate ({GATE_UNIT} OT-1, B0 / R / S3 re-run at the VD-5 commit vs the stored VD-4 runs): **{'PASS' if gate['pass'] else 'FAIL'}** {gate['runs']}",
         f"- reused B0 / R / S3 rule outcomes and V1 equal VD-4's aggregate: {reuse_same or 'not compared (dry)'}"]
    for r in validity:
        L.append(f"- {r['cell']} {r['check']}: {'PASS' if r['pass'] else 'FAIL'}" + (f"; missing {r['missing']}; failed {r['failed']}; bind {r.get('bind')}" if r['check'].startswith("RS3") and not r["pass"] else "")
                 + (f"; bind re-rotated {(r.get('bind') or {}).get('slots_rerotated')}, Sink equal to the restored one after the bind {(r.get('bind') or {}).get('sink_k_equal_before_bind')}" if r['check'].startswith("RS3") and r["pass"] else ""))
    L += ["", "## Formal results (12 cells numeric; flags on the six inspected cells against REF of the same session)", "",
          "| condition | phase | numeric | flags (REF) | resolution |", "|---|---|---|---|---|"]
    for n in NAMES:
        for p in PH:
            q = res[n]["phases"][p]
            L.append(f"| {n} | {p} | {q['numeric_pass']} / {q['of']} | {q['visual_flags']} ({q['ref_flags_same_session']}) | {q['resolution']} |")
    if "V0" in res:
        L.append(f"| V0 (catch) | flags per phase | - | {res['V0']['flags']} | - |")
    L += ["", f"Oracle bytes RS3: {res['RS3']['oracle_bytes'] / 1e6:.1f} MB (idealized lower bounds {', '.join(f'{k} {v:.2f} s' for k, v in res['RS3']['transfer_lower_bound_s'].items())}; not a migration latency).", "",
          f"**Primary question (RS3 sufficient for P1 and P2):** {primary}", "",
          f"Rater calibration: {calib if calib else 'not inspected'}", "",
          "## RS3 vs R and vs S3", "", f"- RS3 vs R (P1): {comp['RS3 vs R']}", f"- RS3 vs S3 (P2): {comp['RS3 vs S3']}", "",
          "## Per-cell numeric values", "", "| cell | condition | V1 (P99) | D_c | late D_c | X_late | C_c | dE_cross | warp eO - eR | dO / dR | P1 P2a P2b P3 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in CONFIRM:
        for n in NAMES:
            if k not in numeric[n]:
                continue
            q = numeric[n][k]; sl = q["sinkless"]
            L.append(f"| {k} | {n} | {q['v1']:.2f} ({q['p99']:.2f}) | {f(sl['D_c'])} | {f(q['late_D_c'])} | {f(q['X_late'])} | {sl['C_c']:.2f} | {sl['dE_cross']:.2f} | "
                     f"{sl['eO'] - sl['eR']:+.2f} | {sl['dO'] / sl['dR']:.3f} | {' '.join('y' if q['rules'][p] else 'n' for p in PH)} |")
    L += ["", f"## Interaction I = (RS3 - S3) - (R - B0) (lower-is-closer form; additive when |I| <= the cell's tolerance): **{reading}**", "",
          "| metric | additive | synergistic | antagonistic |", "|---|---|---|---|"]
    L += [f"| {m} | {cls[m]['additive']} | {cls[m]['synergistic']} | {cls[m]['antagonistic']} |" for m in METRICS]
    L += ["", "| cell | " + " | ".join(METRICS) + " |", "|---|" + "---|" * len(METRICS)]
    for k, row in inter.items():
        L.append(f"| {k} | " + " | ".join("-" if row[m] is None else f"{row[m]['I']:+.3f} ({row[m]['class'][0]})" for m in METRICS) + " |")
    if S:
        L += ["", "## Block A flags per cell (fields: jump M, reversal, content, identity, color, flicker, jump B)", ""]
        for c in VISUAL:
            L.append(f"- {c}: " + "; ".join(f"{n} {''.join('x' if b else '.' for b in (vis.get(c) or {}).get(n, []))}" for n in ("REF", "V0") + NAMES))
        L += ["", "## Block B (paired, against the labelled reference)", ""] + [f"- {o}: {lst}" for o, lst in (pairs or {}).items()]
        L += ["", f"Notes (never scored): {out['notes'] or 'none'}"]
    Path(a.out + ".md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:60]))


if __name__ == "__main__":
    main()
