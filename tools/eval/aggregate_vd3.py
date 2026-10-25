#!/usr/bin/env python3
"""Experiment VD-3 aggregation (osdi/expVD3/preregistration.md sections 3-4). GO / NO-GO for DR2+TSin and, as a
distinct candidate, TSinKC; component and control hypotheses C1-C4. Effect sizes per phase first, then rules.

Order of operations (fixed): the restoration thresholds (vd3_thresholds.json, chosen after the Phase T distributions
were reviewed and frozen before any candidate ran) exist before this runs; the blinded inspection (vd3_inspection.md, STATUS: RECORDED, every code answered) is committed before the verdicts are
produced. Without a recorded inspection only the validity section is written. The key
(vd3_blind_key.json, SHA-256 printed in the form) is then used to attach the answers to conditions.

Per confirmation cell and candidate (D1c, 2026-10-25): FAIL (the candidate violates a restoration rule R1-R5),
DISCRIMINATIVE PASS (it passes and frozen M1 fails at least one of R1-R4 there), NON-DISCRIMINATIVE PASS (both pass).
Overall: NO-GO if any confirmation cell is FAIL or the inspection vetoes; otherwise GO only if every confirmation input
has at least one DISCRIMINATIVE PASS; otherwise INCONCLUSIVE (the evidence cannot show that the candidate resolves the
original continuity failure there). Non-discriminative passes are listed.

    python tools/eval/aggregate_vd3.py [--dry] [--root DIR] [--thresholds PATH] [--key PATH] [--inspection PATH]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import rd_metrics as rm  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/expVD3"
INPUTS = ("dog", "train", "butterfly-feeding-slow-motion", "audi-snow-trail")
CONFIRM = {("train", 0), ("audi-snow-trail", 0), ("dog", 1), ("train", 1), ("butterfly-feeding-slow-motion", 1), ("audi-snow-trail", 1)}
CELLS = ("TSin", "DR2", "DR2+TSin", "TSinKC", "DR2stale", "DR2noise")
CANDIDATES = ("DR2+TSin", "TSinKC")
LAT_BYTES = 16 * 60 * 104 * 2
COST_LIMIT_S, BYTES_LIMIT = 1.5, 1e6
PREFERRED_S = 0.3
VETO = {"changed", "shift", "jump", "drifts", "breaks"}   # a field answered exactly with one of these vetoes GO


def bytes_added(name: str) -> int:
    return 2 * LAT_BYTES if name.startswith("DR2") else 0


def sv(pc, calls, key):
    return np.array([np.nan if pc[str(c)].get(key) is None else pc[str(c)][key] for c in calls if str(c) in pc], dtype=float)


def pmean(x):
    return float(np.nanmean(x)) if len(x) and not np.all(np.isnan(x)) else None


def win_calls(cm, name):
    w = cm["windows"].get(name)
    if not w and name in ("sl_early", "sl_late") and cm.get("sinkless_calls"):
        # VC-1's frozen-M1 metrics predate these windows: the same first / last 8 Sink-less calls from the per-call values
        sl = cm["sinkless_calls"]
        return [c for c in (sl[:8] if name == "sl_early" else sl[-8:]) if str(c) in cm["per_call"]]
    return [c for c in range(w["calls"][0], w["calls"][1] + 1) if str(c) in cm["per_call"]] if w else []


EMB = "dino"   # primary embedder (pixel in dry runs)


def phase_stats(cm: dict, name: str, emb=None) -> dict:
    emb = emb or EMB
    cs = win_calls(cm, name)
    if not cs:
        return {}
    pc, w = cm["per_call"], (cm["windows"].get(name) or {})
    o, r = sv(pc, cs, f"v5a_{emb}"), sv(pc, cs, f"v5a_{emb}_ref")
    co, cr = sv(pc, cs, "v4_pre"), sv(pc, cs, "v4_pre_ref")
    return {"calls": [cs[0], cs[-1]], "dino": pmean(o), "dino_ref": pmean(r), "D_c": pmean(o - r), "C_c": pmean(co - cr),
            "dE_cross": w.get("v4_window_to_ref"), "E": w.get("E_ratio"), "motion": w.get("motion_ratio"),
            "eO": pmean(sv(pc, cs, "eO")), "eR": pmean(sv(pc, cs, "eR")), "dO": pmean(sv(pc, cs, "dO")), "dR": pmean(sv(pc, cs, "dR")),
            "clip": pmean(sv(pc, cs, "v5b")), "clip_ref": pmean(sv(pc, cs, "v5b_ref")), "dinov2_D_c": pmean(sv(pc, cs, "v5a_dinov2") - sv(pc, cs, "v5a_dinov2_ref"))}


def cell(unit: Path, M: dict, cid: str) -> dict | None:
    cm = M["conditions"].get(cid)
    if cm is None:
        return None
    ev = {e["kind"]: e for e in cm["events"]}
    s = json.loads((unit / cid / "summary.json").read_text()) if (unit / cid / "summary.json").exists() else {}
    psnr = {}
    if (unit / cid / "calls.csv").exists():
        for r in csv.DictReader(open(unit / cid / "calls.csv", newline="")):
            psnr[int(r["call"])] = float(r["psnr"]) if r["psnr"] not in ("", "None") else None
    tr = rm.trajectory(psnr, cm["b"]) if psnr else {}
    v3 = s.get("vd3") or {}
    P = {n: phase_stats(cm, n) for n in ("sinkless", "sl_early", "sl_late", "post_bind_20", "last_10")}
    e, l_ = P["sl_early"], P["sl_late"]
    X = ((e["dino"] - l_["dino"]) - (e["dino_ref"] - l_["dino_ref"])) if (e.get("dino") is not None and l_.get("dino") is not None) else None
    return {"valid": bool(s.get("valid")) and not v3.get("invalid"), "invalid": v3.get("invalid"),
            "v1_reset": (ev.get("reset") or {}).get("spike"), "v1_reset_ref_same_call": (ev.get("reset") or {}).get("ref_spike_same_call"),
            "v1_bind": (ev.get("bind") or {}).get("spike"), "v1_bind_ref_same_call": (ev.get("bind") or {}).get("ref_spike_same_call"),
            "P": P, "X_late": X, "terminal_psnr": tr.get("T"), "cross_call": tr.get("cross_call"),
            "cost_s": (v3.get("cost_s") or {}).get("total_serial_s"), "cost_parts": v3.get("cost_s"), "kc_copy_s_not_counted": v3.get("kc_copy_s_not_counted"),
            "fidelity": {k: v for k, v in (v3.get("fidelity") or {}).items() if k != "per_layer"} if v3.get("fidelity") else None,
            "temp_slots_left_after_bind": v3.get("temp_slots_left_after_bind"), "ts_slots_written": v3.get("ts_slots_written"), "kc_digest_equal": v3.get("kc_digest_equal")}


# Engineering acceptance criteria (fixed limits, not REF-derived confidence bounds; decision of 2026-10-25)
REL_LIMIT = 0.10      # warp-error ratio <= 1.10; frame-difference (motion) within +/- 10 % of REF
ABS_FLOOR = 1.0       # near-zero safeguard: below a REF window mean of 1.0 gray level the allowance is 0.10 x 1.0 absolute
PHASES = ("P1", "P2a", "P2b", "P3", "cost")


def _rel_ok(o, r):
    """o within REF r by the 10 % engineering limit, with the absolute safeguard for near-zero r."""
    return o is not None and r is not None and abs(o - r) <= REL_LIMIT * max(r, ABS_FLOOR)


def rules(v: dict, name: str, tol: dict, p99: float, ctrl: dict | None = None) -> dict:
    """Restoration rules per phase for one condition of one cell; None-safe (a missing value fails).
    P1  R1  boundary: V1(reset) <= REF P99
    P2a R2a whole Sink-less window content / appearance: D_c >= -t_DINO, C_c <= t_dE, window dE vs REF <= t_dEx
        R3  late window: excess drift X <= t_DINO and late D_c >= -t_DINO
    P2b R2b whole Sink-less window motion / temporal consistency: warp error and frame difference within 10 % of REF
        (absolute safeguard near zero); the warp check is one-sided (more warp error fails), motion two-sided
    P3  R4  no-harm (proposed reading of the 2026-10-25 decision): the last 10 calls satisfy the P2a content / color and
        P2b clauses against REF (full recovery); the bind V1 and the first 20 calls after the bind are not worse than
        frozen M1's in the same cell by more than the same limits (V1(bind) <= max(REF P99, frozen M1's); D_c >=
        frozen M1's - t_DINO; C_c <= frozen M1's + t_dE; warp error and frame difference within 10 % of frozen M1's).
        Without a control (ctrl None) the absolute REF form is used.
    cost R5 serial reconstruction <= 1.5 s and bytes <= 1 MB"""
    def le(a, b):
        return a is not None and b is not None and a <= b
    t = tol

    def content(ps, cross=False):
        return le(-t["dino"], ps.get("D_c")) and le(ps.get("C_c"), t["dE_anchor"]) and (not cross or le(ps.get("dE_cross"), t["dE_cross"]))

    def temporal(ps):
        warp = ps.get("eO") is not None and ps.get("eR") is not None and (ps["eO"] - ps["eR"]) <= REL_LIMIT * max(ps["eR"], ABS_FLOOR)
        return warp and _rel_ok(ps.get("dO"), ps.get("dR"))
    sl, pb, l10 = v["P"]["sinkless"], v["P"]["post_bind_20"], v["P"]["last_10"]
    R = {"R1": le(v["v1_reset"], p99),
         "R2a": content(sl, cross=True),
         "R3": le(v["X_late"], t["dino"]) and le(-t["dino"], v["P"]["sl_late"].get("D_c")),
         "R2b": temporal(sl),
         "R4": no_harm(v, ctrl, t, p99, content, temporal, le),
         "R5": le(v["cost_s"], COST_LIMIT_S) and bytes_added(name) <= BYTES_LIMIT}
    R["P1"], R["P2a"], R["P2b"], R["P3"], R["cost"] = R["R1"], R["R2a"] and R["R3"], R["R2b"], R["R4"], R["R5"]
    R["valid"] = bool(v["valid"])
    R["all"] = R["valid"] and all(R[p] for p in PHASES)
    return R


def no_harm(v, ctrl, t, p99, content, temporal, le) -> bool:
    pb, l10 = v["P"]["post_bind_20"], v["P"]["last_10"]
    if ctrl is None:
        return le(v["v1_bind"], p99) and content(pb) and content(l10) and temporal(pb) and temporal(l10)
    cb = ctrl["P"]["post_bind_20"]
    bind_ok = v["v1_bind"] is not None and v["v1_bind"] <= max(x for x in (p99, ctrl.get("v1_bind")) if x is not None)
    pb_ok = (le(cb.get("D_c") - t["dino"] if cb.get("D_c") is not None else None, pb.get("D_c")) and le(pb.get("C_c"), cb.get("C_c") + t["dE_anchor"] if cb.get("C_c") is not None else None)
             and pb.get("eO") is not None and cb.get("eO") is not None and pb["eO"] - cb["eO"] <= REL_LIMIT * max(cb["eO"], ABS_FLOOR)
             and _rel_ok(pb.get("dO"), cb.get("dO")))
    return bool(bind_ok and pb_ok and content(l10) and temporal(l10))


def classify_phases(rr: dict, rc: dict) -> dict:
    """Per phase: FAIL (the candidate violates it), DISCRIMINATIVE PASS (passes; frozen M1 violates it in this cell),
    NON-DISCRIMINATIVE PASS (both pass). P3 and cost are no-harm / limit checks: PASS or FAIL. An invalid stream fails
    every phase."""
    if not rr.get("valid"):
        return {p: "FAIL" for p in PHASES}
    out = {}
    for p in PHASES:
        if p in ("P3", "cost"):
            out[p] = "PASS" if rr.get(p) else "FAIL"
        else:
            out[p] = "FAIL" if not rr.get(p) else ("DISCRIMINATIVE PASS" if not rc.get(p) else "NON-DISCRIMINATIVE PASS")
    return out


def overall(classes: dict, vetoes: list, inputs: set) -> dict:
    """classes: {cell: {phase: class}} over the confirmation cells; inputs: the confirmation inputs.
    continuity: NO-GO if any phase of any cell FAILs or the inspection vetoes; GO if every input has a discriminative
    pass in P1 and in P2 (P2a or P2b); otherwise INCONCLUSIVE. identity (P2a): ESTABLISHED only if every input has a
    discriminative P2a pass (and continuity is not NO-GO); otherwise INCONCLUSIVE (or NO-GO with the continuity)."""
    if vetoes or any(c == "FAIL" for ph in classes.values() for c in ph.values()):
        return {"continuity": "NO-GO", "identity": "NO-GO"}
    disc = lambda ps: {k.split("_s")[0] for k, ph in classes.items() if any(ph.get(p) == "DISCRIMINATIVE PASS" for p in ps)}  # noqa: E731
    cont = "GO" if (inputs <= disc(["P1"]) and inputs <= disc(["P2a", "P2b"])) else "INCONCLUSIVE"
    return {"continuity": cont, "identity": "ESTABLISHED" if inputs <= disc(["P2a"]) else "INCONCLUSIVE"}


def thresholds_for(T: dict, key: str) -> dict | None:
    return (T.get("cells") or {}).get(key, {}).get("thresholds") or T.get("global")


def improvement(v: dict, ctrl: dict) -> dict:
    gap = ctrl["P"]["sinkless"].get("D_c")
    return {"v1_ratio": (v["v1_reset"] / ctrl["v1_reset"]) if (v["v1_reset"] and ctrl["v1_reset"]) else None,
            "dino_gap_closed": ((v["P"]["sinkless"]["D_c"] - gap) / (0 - gap)) if (gap and gap < 0 and v["P"]["sinkless"].get("D_c") is not None) else None}


def inspection(path: Path, key_path: Path, form_sha: str | None) -> dict:
    if not path.exists():
        return {"recorded": False, "why": f"{path.name} missing"}
    txt = path.read_text()
    if "STATUS: RECORDED" not in txt:
        return {"recorded": False, "why": "STATUS: RECORDED not set"}
    rows = {}
    for line in txt.splitlines():
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 7 and re.fullmatch(r"[0-9A-F]{6}", cols[0] or ""):
            rows[cols[0]] = cols[1:]
    empty = [c for c, a in rows.items() if any(not x for x in a[:6])]
    if empty:
        return {"recorded": False, "why": f"unanswered codes {empty[:5]}"}
    if not key_path.exists():
        return {"recorded": True, "keyed": False, "why": f"key {key_path} not available yet", "n_rows": len(rows)}
    kb = key_path.read_bytes()
    ksha = hashlib.sha256(kb).hexdigest()
    if form_sha and ksha != form_sha:
        return {"recorded": True, "keyed": False, "why": f"key SHA-256 {ksha[:12]} differs from the form's {form_sha[:12]}"}
    key = json.loads(kb)["key"]
    by = {}
    for code, ans in rows.items():
        k = key.get(code)
        if k is None:
            continue
        by.setdefault(k["cell"], {})[k["name"]] = {"code": code, "answers": ans[:6], "notes": ans[6] if len(ans) > 6 else "", "veto": any(x.strip().lower() in VETO for x in ans[:6])}
    return {"recorded": True, "keyed": True, "key_sha256": ksha, "cells": by}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--root", default=None)
    ap.add_argument("--thresholds", default=None, help="frozen restoration thresholds (vd3_thresholds.json)")
    ap.add_argument("--inspection", default=None)
    ap.add_argument("--key", default=None)
    ap.add_argument("--form", default=None)
    ap.add_argument("--out", default=None, help="output stem (default results/evaluation/osdi/expVD3/[_dryrun_]vd3_results)")
    a = ap.parse_args()
    pre = "_dryrun_" if a.dry else ""
    root = Path(a.root or ROOT / "results/evaluation" / f"{pre}expVC")
    tpath = Path(a.thresholds or OUT / f"{pre}vd3_thresholds.json")
    if not tpath.exists():
        sys.exit(f"[vd3] thresholds {tpath} missing: they are chosen from the Phase T distributions and frozen before any candidate runs")
    T = json.loads(tpath.read_text())
    tsha = hashlib.sha256(tpath.read_bytes()).hexdigest()
    f = lambda x, n=3: "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))  # noqa: E731
    cells, validity = {}, []
    for inp in INPUTS:
        for sd in (0, 1):
            unit = root / f"{inp}_s{sd}"
            if not (unit / "metrics.json").exists():
                continue
            M = json.loads((unit / "metrics.json").read_text())
            global EMB
            EMB = "dino" if "dino" in M.get("embedders", []) else M.get("embedders", ["dino"])[0]
            for x in ("1", "L"):
                ctrl = cell(unit, M, f"OT-{x}")
                if ctrl is None:
                    continue
                key = f"{inp}_s{sd}|OT-{x}"
                tol = thresholds_for(T, f"{inp}_s{sd}|OT-{x}")
                sens = ((T.get("cells") or {}).get(f"{inp}_s{sd}|OT-{x}") or {}).get("sensitivity") or {}
                cs = {n: cell(unit, M, f"VD3{x}-{n}") for n in CELLS}
                cells[key] = {"confirmation": (inp, sd) in CONFIRM, "p99": M.get("ref_spike_P99"), "tol": tol, "sens": sens, "control": ctrl, "conds": cs}
                if tol is None:
                    validity.append(f"{key}: no frozen thresholds")
                for n, v in cs.items():
                    if v is None:
                        validity.append(f"{key} {n}: missing")
                    elif not v["valid"]:
                        validity.append(f"{key} {n}: invalid ({v.get('invalid')})")
    L = [f"# VD-3 results{' (DRY RUN - synthetic, not a result)' if a.dry else ''}", "",
         f"Thresholds: `{tpath.name}` (SHA-256 {tsha[:16]}), frozen after the Phase T review. Cells: {len(cells)} "
         f"({sum(1 for c in cells.values() if c['confirmation'])} confirmation). Validity problems: {validity or 'none'}.", ""]
    insp = inspection(Path(a.inspection or OUT / f"{pre}vd3_inspection.md"), Path(a.key or OUT / f"{pre}vd3_blind_key.json"),
                      (re.search(r"SHA-256 `([0-9a-f]{64})`", Path(a.form or OUT / f"{pre}vd3_inspection_form.md").read_text()) or [None, None])[1]
                      if Path(a.form or OUT / f"{pre}vd3_inspection_form.md").exists() else None)
    if not insp.get("recorded") or not insp.get("keyed"):
        L += ["", f"**Verdicts withheld: the blinded inspection is not recorded / keyed yet ({insp.get('why')}).** Only validity is reported."]
        out = Path(a.out or OUT / f"{pre}vd3_results")
        out.with_suffix(".md").write_text("\n".join(L) + "\n")
        out.with_suffix(".json").write_text(json.dumps({"validity": validity, "inspection": insp, "thresholds_sha256": tsha}, indent=1, default=str))
        print("\n".join(L)); return
    # ---- effect sizes per phase, then rules
    R = {cand: {} for cand in CANDIDATES}
    RC = {}   # frozen M1's restoration rules per confirmation cell
    RS, RCS = {}, {}   # the same under the sensitivity threshold sets (B, C)
    C = {"C1": [], "C2": [], "C3": []}
    for key, cc in sorted(cells.items(), key=lambda kv: (not kv[1]["confirmation"], kv[0])):
        ctrl, tol, p99 = cc["control"], cc["tol"], cc["p99"]
        L += ["", f"## {key} ({'confirmation' if cc['confirmation'] else 'replication'}; REF V1 P99 {f(p99, 2)}; thresholds {json.dumps({k_: (round(v, 4) if isinstance(v, (int, float)) else v) for k_, v in (tol or {}).items()})})", "",
              "| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for n, v in [("frozen M1", ctrl)] + [(n, cc["conds"][n]) for n in CELLS]:
            if v is None:
                continue
            sl, pb = v["P"]["sinkless"], v["P"]["post_bind_20"]
            imp = improvement(v, ctrl) if n != "frozen M1" else {}
            rr = rules(v, n if n != "frozen M1" else "OT", tol, p99, ctrl) if tol else {}
            if n in CANDIDATES and cc["confirmation"]:
                R[n][key] = rr
                for sname, st in (cc.get("sens") or {}).items():
                    RS.setdefault(sname, {}).setdefault(n, {})[key] = rules(v, n, st, p99, ctrl)
            if n == "frozen M1" and cc["confirmation"]:
                RC[key] = rr
                for sname, st in (cc.get("sens") or {}).items():
                    RCS.setdefault(sname, {})[key] = rules(v, "OT", st, p99, ctrl)
            L.append(f"| {n} | {v['valid']} | {f(v['v1_reset'], 2)} ({f(v['v1_reset_ref_same_call'], 2)}; {f(imp.get('v1_ratio'), 2)}) | "
                     f"{f(sl.get('D_c'))} / {f(sl.get('C_c'), 2)} / {f(sl.get('dE_cross'), 2)} / {f(sl.get('E'), 2)} / {f(sl.get('motion'), 2)} | "
                     f"{f(v['P']['sl_late'].get('D_c'))}, {f(v['X_late'])} | {f(v['v1_bind'], 2)} ({f(v['v1_bind_ref_same_call'], 2)}) | "
                     f"{f(pb.get('D_c'))} / {f(pb.get('C_c'), 2)} / {f(pb.get('E'), 2)} / {f(pb.get('motion'), 2)} | {f(v['P']['last_10'].get('D_c'))} | "
                     f"{v['cross_call']} / {f(v['terminal_psnr'], 1)} | {f(v['cost_s'])} | {bytes_added(n) / 1e6:.2f} MB | {f(imp.get('dino_gap_closed'), 2)} | "
                     + " ".join(("Y" if rr.get(p_) else "n") for p_ in PHASES) + " |")
        if cc["confirmation"]:
            d, ts, dr2, st_, nz = (cc["conds"].get(k_) for k_ in ("DR2+TSin", "TSin", "DR2", "DR2stale", "DR2noise"))
            ok = all(x is not None and x["valid"] for x in (d, ts, dr2, st_, nz))
            C["C1"].append(ok and d["v1_reset"] is not None and dr2["v1_reset"] is not None and d["v1_reset"] <= 1.1 * dr2["v1_reset"]
                           and d["P"]["sinkless"].get("dino") is not None and ts["P"]["sinkless"].get("dino") is not None and d["P"]["sinkless"]["dino"] >= ts["P"]["sinkless"]["dino"] - 0.01)
            C["C2"].append(ok and ts["v1_reset"] is not None and p99 is not None and ts["v1_reset"] > p99)
            C["C3"].append(ok and None not in (dr2["v1_reset"], st_["v1_reset"], nz["v1_reset"]) and dr2["v1_reset"] < st_["v1_reset"] and dr2["v1_reset"] < nz["v1_reset"])
    n_conf = sum(1 for c in cells.values() if c["confirmation"])
    L += ["", "## GO / NO-GO (phase-level discrimination; primary thresholds A)", "",
          "Per confirmation cell and phase: FAIL / DISCRIMINATIVE PASS (frozen M1 violates that phase there) / NON-DISCRIMINATIVE PASS; "
          "P3 (no-harm) and cost: PASS / FAIL. Continuity: NO-GO on any FAIL or inspection veto; GO if every input has a discriminative pass in P1 and in P2 "
          "(P2a or P2b); otherwise INCONCLUSIVE. Identity preservation: ESTABLISHED only if every input has a discriminative P2a pass.", ""]
    V, CL = {}, {}
    conf_inputs = {k.split("_s")[0] for k, c in cells.items() if c["confirmation"]}
    vetoes_of = {cand: [ck for ck, cv in insp["cells"].items() if ck in cells and cells[ck]["confirmation"] and (cv.get(cand) or {}).get("veto")] for cand in CANDIDATES}
    for cand in CANDIDATES:
        CL[cand] = {ck: classify_phases(rr, RC.get(ck, {})) for ck, rr in R[cand].items()}
        V[cand] = {"continuity": "PENDING", "identity": "PENDING"} if (n_conf < 12 or len(R[cand]) < 12) else overall(CL[cand], vetoes_of[cand], conf_inputs)
        L += [f"### {cand}: continuity **{V[cand]['continuity']}**, identity preservation **{V[cand]['identity']}** (inspection vetoes {vetoes_of[cand] or 'none'})", "",
              "| cell | " + " | ".join(PHASES) + " |", "|---|" + "---|" * len(PHASES)]
        L += [f"| {ck} | " + " | ".join(ph[p_] for p_ in PHASES) + " |" for ck, ph in sorted(CL[cand].items())]
        for p_ in ("P1", "P2a", "P2b"):
            nd = sorted(ck for ck, ph in CL[cand].items() if ph[p_] == "NON-DISCRIMINATIVE PASS")
            L.append(f"- {p_} non-discriminative passes: {nd or 'none'}")
        L.append("")
    L += ["## Sensitivity (threshold sets B and C; never the verdict)", ""]
    for sname in sorted(RS):
        for cand in CANDIDATES:
            cls = {ck: classify_phases(rr, RCS[sname].get(ck, {})) for ck, rr in RS[sname].get(cand, {}).items()}
            res = overall(cls, vetoes_of[cand], conf_inputs) if len(cls) == 12 and n_conf == 12 else {"continuity": "PENDING", "identity": "PENDING"}
            L.append(f"- {sname} / {cand}: continuity {res['continuity']}, identity {res['identity']}; FAIL phases {sorted({(ck, p_) for ck, ph in cls.items() for p_, c in ph.items() if c == 'FAIL'}) or 'none'}")
    L.append("")
    ref_flags = [ck for ck, cv in insp["cells"].items() if (cv.get("REF") or {}).get("veto")]
    m1_flags = [ck for ck, cv in insp["cells"].items() if (cv.get("OT") or {}).get("veto")]
    L += [f"- Inspection calibration: REF clips flagged {ref_flags or 'none'}; frozen-M1 clips flagged {len(m1_flags)} of {len(insp['cells'])} cells.",
          "- A NO-GO rejects the preregistered general claim; descriptive utility on a subset is reported as such, never as continuity preservation.", "",
          "## Component and control hypotheses (confirmation cells)", "",
          f"- C1 (the combination keeps each component's benefit): {sum(C['C1'])} / {len(C['C1'])} -> {'SUPPORTED' if C['C1'] and all(C['C1']) else 'NOT SUPPORTED'}",
          f"- C2 (TS-in alone leaves the boundary jump above REF P99 on the majority): {sum(C['C2'])} / {len(C['C2'])} -> {'SUPPORTED' if C['C2'] and sum(C['C2']) * 2 > len(C['C2']) else 'NOT SUPPORTED'}",
          f"- C3 (the correct latent history beats the stale and noise controls): {sum(C['C3'])} / {len(C['C3'])} -> {'SUPPORTED' if C['C3'] and all(C['C3']) else 'NOT SUPPORTED (attribution not established; not evidence that any warmed cache suffices)'}",
          "- C4 (TSinKC as a distinct candidate): see its GO / NO-GO line and the per-cell rows."]
    out = Path(a.out or OUT / f"{pre}vd3_results")
    out.with_suffix(".md").write_text("\n".join(L) + "\n")
    out.with_suffix(".json").write_text(json.dumps({"cells": cells, "rules": R, "rules_frozen_m1": RC, "rules_sensitivity": RS, "classes": CL, "C": C, "verdicts": V, "inspection": insp, "validity": validity, "thresholds_sha256": tsha}, indent=1, default=str))
    print("\n".join(L[next((i for i, l_ in enumerate(L) if l_.startswith("## GO / NO-GO")), 0):]))


if __name__ == "__main__":
    main()
