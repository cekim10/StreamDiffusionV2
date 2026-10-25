#!/usr/bin/env python3
"""Experiment VD-3 aggregation (osdi/expVD3/preregistration.md sections 3-4). GO / NO-GO for DR2+TSin and, as a
distinct candidate, TSinKC; component and control hypotheses C1-C4. Effect sizes per phase first, then rules.

Order of operations (fixed): the tolerances (vd3_tolerances.json, REF streams only) exist before this runs; the
blinded inspection (vd3_inspection.md, STATUS: RECORDED, every code answered) is committed before the verdicts are
produced. Without a recorded inspection only the validity section is written. The key
(vd3_blind_key.json, SHA-256 printed in the form) is then used to attach the answers to conditions.

    python tools/eval/aggregate_vd3.py [--dry] [--root DIR] [--key PATH] [--inspection PATH]
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
    return [c for c in range(w["calls"][0], w["calls"][1] + 1) if str(c) in cm["per_call"]] if w else []


EMB = "dino"   # primary embedder (pixel in dry runs)


def phase_stats(cm: dict, name: str, emb=None) -> dict:
    emb = emb or EMB
    cs = win_calls(cm, name)
    if not cs:
        return {}
    pc, w = cm["per_call"], cm["windows"][name]
    o, r = sv(pc, cs, f"v5a_{emb}"), sv(pc, cs, f"v5a_{emb}_ref")
    co, cr = sv(pc, cs, "v4_pre"), sv(pc, cs, "v4_pre_ref")
    return {"calls": [cs[0], cs[-1]], "dino": pmean(o), "dino_ref": pmean(r), "D_c": pmean(o - r), "C_c": pmean(co - cr),
            "dE_cross": w.get("v4_window_to_ref"), "E": w.get("E_ratio"), "motion": w.get("motion_ratio"),
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


def rules(v: dict, name: str, tol: dict, p99: float) -> dict:
    """R1-R5 (restoration) for one condition of one cell; None-safe (a missing value fails)."""
    def le(a, b):
        return a is not None and b is not None and a <= b
    t = tol
    within = lambda ps: (le(-t["dino"], ps.get("D_c")) and le(ps.get("C_c"), t["dE_anchor"]) and le(ps.get("E"), 1 + t["E"])  # noqa: E731
                         and ps.get("motion") is not None and 1 - t["motion"] <= ps["motion"] <= 1 + t["motion"])
    sl = v["P"]["sinkless"]
    R = {"R1": le(v["v1_reset"], p99),
         "R2": within(sl) and le(sl.get("dE_cross"), t["dE_cross"]),
         "R3": le(v["X_late"], t["dino"]) and le(-t["dino"], v["P"]["sl_late"].get("D_c")),
         "R4": le(v["v1_bind"], p99) and within(v["P"]["post_bind_20"]) and within(v["P"]["last_10"]),
         "R5": le(v["cost_s"], COST_LIMIT_S) and bytes_added(name) <= BYTES_LIMIT}
    R["all"] = v["valid"] and all(R.values())
    return R


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
    ap.add_argument("--tolerances", default=None)
    ap.add_argument("--inspection", default=None)
    ap.add_argument("--key", default=None)
    ap.add_argument("--form", default=None)
    ap.add_argument("--out", default=None, help="output stem (default results/evaluation/osdi/expVD3/[_dryrun_]vd3_results)")
    a = ap.parse_args()
    pre = "_dryrun_" if a.dry else ""
    root = Path(a.root or ROOT / "results/evaluation" / f"{pre}expVC")
    tpath = Path(a.tolerances or OUT / f"{pre}vd3_tolerances.json")
    if not tpath.exists():
        sys.exit(f"[vd3] tolerances {tpath} missing: they are fixed from REF streams before any aggregation")
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
                tol = T["cells"].get(f"{inp}|OT-{x}", {}).get("tolerance")
                cs = {n: cell(unit, M, f"VD3{x}-{n}") for n in CELLS}
                cells[key] = {"confirmation": (inp, sd) in CONFIRM, "p99": M.get("ref_spike_P99"), "tol": tol, "control": ctrl, "conds": cs,
                              "sensitivity": T.get("sensitivity", {}).get(key)}
                for n, v in cs.items():
                    if v is None:
                        validity.append(f"{key} {n}: missing")
                    elif not v["valid"]:
                        validity.append(f"{key} {n}: invalid ({v.get('invalid')})")
    L = [f"# VD-3 results{' (DRY RUN - synthetic, not a result)' if a.dry else ''}", "",
         f"Tolerances: `{tpath.name}` (SHA-256 {tsha[:16]}), REF streams only. Cells: {len(cells)} "
         f"({sum(1 for c in cells.values() if c['confirmation'])} confirmation). Validity problems: {validity or 'none'}.", ""]
    nd = T.get("non_discriminative_confirmation_cells") or []
    L.append(f"Assay sensitivity (frozen M1 must fail the R2 content clause): non-discriminative confirmation cells {nd or 'none'}.")
    insp = inspection(Path(a.inspection or OUT / f"{pre}vd3_inspection.md"), Path(a.key or OUT / f"{pre}vd3_blind_key.json"),
                      (re.search(r"SHA-256 `([0-9a-f]{64})`", Path(a.form or OUT / f"{pre}vd3_inspection_form.md").read_text()) or [None, None])[1]
                      if Path(a.form or OUT / f"{pre}vd3_inspection_form.md").exists() else None)
    if not insp.get("recorded") or not insp.get("keyed"):
        L += ["", f"**Verdicts withheld: the blinded inspection is not recorded / keyed yet ({insp.get('why')}).** Only validity is reported."]
        out = Path(a.out or OUT / f"{pre}vd3_results")
        out.with_suffix(".md").write_text("\n".join(L) + "\n")
        out.with_suffix(".json").write_text(json.dumps({"validity": validity, "inspection": insp, "tolerances_sha256": tsha}, indent=1, default=str))
        print("\n".join(L)); return
    # ---- effect sizes per phase, then rules
    R = {cand: {} for cand in CANDIDATES}
    C = {"C1": [], "C2": [], "C3": []}
    for key, cc in sorted(cells.items(), key=lambda kv: (not kv[1]["confirmation"], kv[0])):
        ctrl, tol, p99 = cc["control"], cc["tol"], cc["p99"]
        L += ["", f"## {key} ({'confirmation' if cc['confirmation'] else 'replication'}; REF V1 P99 {f(p99, 2)}; tolerances {json.dumps({k_: round(v, 4) for k_, v in (tol or {}).items()})})", "",
              "| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | R1 R2 R3 R4 R5 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for n, v in [("frozen M1", ctrl)] + [(n, cc["conds"][n]) for n in CELLS]:
            if v is None:
                continue
            sl, pb = v["P"]["sinkless"], v["P"]["post_bind_20"]
            imp = improvement(v, ctrl) if n != "frozen M1" else {}
            rr = rules(v, n if n != "frozen M1" else "OT", tol, p99) if tol else {}
            if n in CANDIDATES and cc["confirmation"]:
                R[n][key] = rr
            L.append(f"| {n} | {v['valid']} | {f(v['v1_reset'], 2)} ({f(v['v1_reset_ref_same_call'], 2)}; {f(imp.get('v1_ratio'), 2)}) | "
                     f"{f(sl.get('D_c'))} / {f(sl.get('C_c'), 2)} / {f(sl.get('dE_cross'), 2)} / {f(sl.get('E'), 2)} / {f(sl.get('motion'), 2)} | "
                     f"{f(v['P']['sl_late'].get('D_c'))}, {f(v['X_late'])} | {f(v['v1_bind'], 2)} ({f(v['v1_bind_ref_same_call'], 2)}) | "
                     f"{f(pb.get('D_c'))} / {f(pb.get('C_c'), 2)} / {f(pb.get('E'), 2)} / {f(pb.get('motion'), 2)} | {f(v['P']['last_10'].get('D_c'))} | "
                     f"{v['cross_call']} / {f(v['terminal_psnr'], 1)} | {f(v['cost_s'])} | {bytes_added(n) / 1e6:.2f} MB | {f(imp.get('dino_gap_closed'), 2)} | "
                     + " ".join(("Y" if rr.get(r_) else "n") for r_ in ("R1", "R2", "R3", "R4", "R5")) + " |")
        if cc["confirmation"]:
            d, ts, dr2, st_, nz = (cc["conds"].get(k_) for k_ in ("DR2+TSin", "TSin", "DR2", "DR2stale", "DR2noise"))
            ok = all(x is not None and x["valid"] for x in (d, ts, dr2, st_, nz))
            C["C1"].append(ok and d["v1_reset"] is not None and dr2["v1_reset"] is not None and d["v1_reset"] <= 1.1 * dr2["v1_reset"]
                           and d["P"]["sinkless"].get("dino") is not None and ts["P"]["sinkless"].get("dino") is not None and d["P"]["sinkless"]["dino"] >= ts["P"]["sinkless"]["dino"] - 0.01)
            C["C2"].append(ok and ts["v1_reset"] is not None and p99 is not None and ts["v1_reset"] > p99)
            C["C3"].append(ok and None not in (dr2["v1_reset"], st_["v1_reset"], nz["v1_reset"]) and dr2["v1_reset"] < st_["v1_reset"] and dr2["v1_reset"] < nz["v1_reset"])
    n_conf = sum(1 for c in cells.values() if c["confirmation"])
    L += ["", "## GO / NO-GO (restoration rules R1-R5 on every confirmation cell, and no inspection veto)", ""]
    V = {}
    for cand in CANDIDATES:
        quant = len(R[cand]) == 12 and n_conf == 12 and all(r_["all"] for r_ in R[cand].values())
        vetoes = [ck for ck, cv in insp["cells"].items() if ck in cells and cells[ck]["confirmation"] and (cv.get(cand) or {}).get("veto")]
        fails = {ck: [r_ for r_ in ("R1", "R2", "R3", "R4", "R5") if not rr.get(r_)] for ck, rr in R[cand].items() if not rr["all"]}
        if n_conf < 12:
            V[cand] = "PENDING"
        elif nd:
            V[cand] = "INCONCLUSIVE (assay not discriminative on " + ", ".join(nd) + ")"
        else:
            V[cand] = "GO" if (quant and not vetoes) else "NO-GO"
        L.append(f"- **{cand}: {V[cand]}** - quantitative R1-R5 on {sum(1 for r_ in R[cand].values() if r_['all'])} / {n_conf} confirmation cells; "
                 f"failing phases per cell {fails or 'none'}; inspection vetoes {vetoes or 'none'}")
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
    out.with_suffix(".json").write_text(json.dumps({"cells": cells, "rules": R, "C": C, "verdicts": V, "inspection": insp, "validity": validity, "tolerances_sha256": tsha}, indent=1, default=str))
    print("\n".join(L[-14:]))


if __name__ == "__main__":
    main()
