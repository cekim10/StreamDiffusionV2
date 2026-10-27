#!/usr/bin/env python3
"""Experiment VD-4 aggregation (osdi/expVD4/preregistration.md sections 4-6). Diagnostic: which oracle state resolves
P1 / P2a / P2b on the 12 VD-3 confirmation cells. VD-3's frozen thresholds and rules (`vd3_thresholds.json`,
`aggregate_vd3.rules`) are reused unchanged; P3 is reported.

Per condition and phase: numeric pass on all 12 cells; visual flags from the blinded session in which the condition was
inspected, against REF's flags in the same session; **strict** resolution = all 12 numeric passes and flags <= REF's;
**near** = all 12 numeric passes and flags <= REF's + 1; raw counts always reported (a zero count is not proof of zero
risk). Attribution: sufficient (a single-state condition resolves), jointly sufficient (DR resolves, D and R do not),
not explained by the tested states. Correspondence of metric violations and visual flags (P2a, P2b): 2 x 2 counts and
Cohen's kappa. Validity: V0 digest equality with REF, B0 = VD-3 DR2+TSin digests, every oracle check, stream validity.
Writes vd4_results.{md,json} and the stage gates (vd4_gates.json).

    python tools/eval/aggregate_vd4.py [--root DIR] [--out STEM] [--sessions stage1,stage2,...]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import aggregate_vd3 as a3  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/expVD4"
THR = ROOT / "results/evaluation/osdi/expVD3/vd3_thresholds.json"
THR_SHA_FROZEN = "792a6ac77ffbca24"   # VD-3 freeze (first 16 hex digits); VD-4 reuses it unchanged
CONFIRM = [f"{u}|OT-{x}" for u in ("train_s0", "audi-snow-trail_s0", "dog_s1", "train_s1", "butterfly-feeding-slow-motion_s1", "audi-snow-trail_s1") for x in ("1", "L")]
SUBSET4 = ["dog_s1|OT-1", "train_s0|OT-1", "butterfly-feeding-slow-motion_s1|OT-1", "audi-snow-trail_s1|OT-1"]
# stage-0 validity cells: one per input, covering the sink-position configurations at the move (source positions of
# slots 0-1 vs the prepare's 0, 1): aligned (dog [0, 1]), positive deltas (train [22, 24]), negative deltas (butterfly
# s0 OT-L [-29, -10]) and mixed (audi s1 OT-1 [22, 1])
STAGE0 = ["dog_s1|OT-1", "train_s0|OT-1", "butterfly-feeding-slow-motion_s0|OT-L", "audi-snow-trail_s1|OT-1"]
STAGE0_NAMES = ("V0", "B0", "A1", "S3")   # A1 / S3: validity of the rotation and of the oracle Sink writes only; no metrics at stage 0
# stage-1 inspection split by cell (each input and both schedules in each session; every cell's REF / B0 in one session)
STAGE1_SESSIONS = {"stage1a": ["train_s0|OT-1", "train_s1|OT-L", "audi-snow-trail_s0|OT-1", "audi-snow-trail_s1|OT-L", "dog_s1|OT-1", "butterfly-feeding-slow-motion_s1|OT-L"],
                   "stage1b": ["train_s0|OT-L", "train_s1|OT-1", "audi-snow-trail_s0|OT-L", "audi-snow-trail_s1|OT-1", "dog_s1|OT-L", "butterfly-feeding-slow-motion_s1|OT-1"]}
NAMES = ("B0", "A1", "D", "R", "DR", "S1", "S2", "S3", "A1S1", "A1S2", "Q8", "Q4")
EXPLORATORY = ("A1S1", "A1S2", "Q8", "Q4")
PH = ("P1", "P2a", "P2b", "P3")
VIS = {"P1": [3], "P2a": [0, 1, 2], "P2b": [4, 5], "P3": [6]}   # form field indices per phase
FLAG = {"changed", "drift", "shift", "jump", "flicker", "unnatural"}
RATES = {"1 Gbps": 1e9, "10 Gbps": 10e9}


def vd4_summary(unit: Path, cid: str) -> dict:
    p = unit / cid / "summary.json"
    return json.loads(p.read_text()) if p.exists() else {}


def digests(unit: Path, cid: str) -> dict:
    p = unit / cid / "calls.csv"
    return {int(r["call"]): r["frame_digest"] for r in csv.DictReader(open(p, newline=""))} if p.exists() else {}


def inspection(sess: str, pre: str = "", d: Path = OUT) -> dict:
    """{cell: {name: [flag per field]}} for a recorded session whose key matches its form; {} otherwise."""
    insp, form, key = d / f"{pre}vd4_inspection_{sess}.md", d / f"{pre}vd4_inspection_form_{sess}.md", d / f"{pre}vd4_{sess}_blind_key.json"
    if not (insp.exists() and form.exists() and key.exists()) or "STATUS: RECORDED" not in insp.read_text():
        return {}
    kb = key.read_bytes()
    want = re.search(r"SHA-256 `([0-9a-f]{64})`", form.read_text()).group(1)
    if hashlib.sha256(kb).hexdigest() != want:
        sys.exit(f"[vd4] {sess}: key SHA-256 differs from the form's")
    K = json.loads(kb)["key"]
    out = {}
    for line in insp.read_text().splitlines():
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 8 and re.fullmatch(r"[0-9A-F]{6}", cols[0] or "") and cols[0] in K:
            k = K[cols[0]]
            out.setdefault(k["cell"], {})[k["name"]] = [x.lower() in FLAG for x in cols[1:8]]
    return out


def resolution(npass: int, of: int, flags: int, ref_flags: int, inspected: int) -> str:
    """STRICT: all 12 numeric passes and visual flags <= REF's in the same session; NEAR: <= REF's + 1."""
    if not inspected:
        return "not inspected"
    all_num = of == 12 and npass == 12
    if all_num and flags <= ref_flags:
        return "STRICT"
    if all_num and flags <= ref_flags + 1:
        return "NEAR"
    return "not resolved"


def kappa(tab: dict) -> float | None:
    n = sum(tab.values())
    if not n:
        return None
    po = (tab["mm"] + tab["pp"]) / n   # m = metric fail, p = visual flag; "mm": both fail/flag, "pp": both pass/none
    pm, pv = (tab["mm"] + tab["mp"]) / n, (tab["mm"] + tab["pm"]) / n
    pe = pm * pv + (1 - pm) * (1 - pv)
    return None if pe == 1 else (po - pe) / (1 - pe)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT / "results/evaluation/expVC"))
    ap.add_argument("--out", default=str(OUT / "vd4_results"))
    ap.add_argument("--sessions", default="stage1a,stage1b,stage2,stage2b,stage3")
    ap.add_argument("--thresholds", default=str(THR))
    ap.add_argument("--insp_dir", default=str(OUT), help="where the inspection forms, records and keys are")
    ap.add_argument("--dry", action="store_true", help="synthetic units (pixel embedder); thresholds SHA not enforced; _dryrun_ session files")
    a = ap.parse_args()
    root, pre = Path(a.root), ("_dryrun_" if a.dry else "")
    tb = Path(a.thresholds).read_bytes()
    if not a.dry and hashlib.sha256(tb).hexdigest()[:16] != THR_SHA_FROZEN:
        sys.exit("[vd4] the thresholds differ from VD-3's frozen file")
    T = json.loads(tb)
    sessions = {s: inspection(s, pre, Path(a.insp_dir)) for s in a.sessions.split(",") if s}
    # every (cell, condition) is inspected in exactly one session; its baseline is REF of the same cell in that session
    where, dup = {}, []
    for sname, ins in sessions.items():
        for cell_, names_ in ins.items():
            for n_ in names_:
                if n_ in ("REF", "B0") and (cell_, n_) in where:
                    dup.append((cell_, n_, where[(cell_, n_)], sname))
                where.setdefault((cell_, n_), sname)

    def flagged(cell_, n_, idx):
        s_ = where.get((cell_, n_))
        fl = sessions[s_][cell_][n_] if s_ else None
        return None if fl is None else any(fl[i] for i in idx)

    def ref_flagged(cell_, n_, idx):
        s_ = where.get((cell_, n_))
        fl = (sessions[s_].get(cell_) or {}).get("REF") if s_ else None
        return bool(fl) and any(fl[i] for i in idx)
    res, validity, numeric = {}, [], {}
    for key in CONFIRM + [k for k in STAGE0 if k not in CONFIRM]:
        unit_name, ot = key.split("|"); x = ot.split("-")[1]
        unit = root / unit_name
        if not (unit / "metrics.json").exists():
            continue
        M = json.loads((unit / "metrics.json").read_text())
        a3.EMB = "dino" if "dino" in M.get("embedders", []) else M.get("embedders", ["dino"])[0]
        ctrl = a3.cell(unit, M, ot)
        tol = a3.thresholds_for(T, key)
        p99 = M.get("ref_spike_P99")
        v0 = vd4_summary(unit, f"VD4{x}-V0")
        if v0:
            validity.append({"cell": key, "check": "V0 equals REF after the move", "pass": bool(v0.get("valid")) and bool((v0.get("vd4") or {}).get("v0_pass", a.dry))})
        b0d, vd3d = digests(unit, f"VD4{x}-B0"), digests(unit, f"VD3{x}-DR2+TSin")
        if b0d and vd3d:
            validity.append({"cell": key, "check": "B0 reproduces VD-3 DR2+TSin digests", "pass": a.dry or b0d == vd3d})
        for n in NAMES:
            cid = f"VD4{x}-{n}"
            s = vd4_summary(unit, cid)
            if not s:
                continue
            v4 = s.get("vd4") or {}
            bad = [k_ for k_, ok in (v4.get("checks") or {}).items() if ok is False]
            validity.append({"cell": key, "check": f"{n}: stream valid and oracle checks", "pass": bool(s.get("valid")) and not bad, "failed": bad})
            v = a3.cell(unit, M, cid)
            if v is None or ctrl is None or tol is None:
                continue
            rr = a3.rules(v, n, tol, p99, ctrl)
            rs = {p: bool(rr[p]) for p in PH}
            numeric.setdefault(n, {})[key] = {"rules": rs, "v1": v["v1_reset"], "sinkless": {k_: v["P"]["sinkless"].get(k_) for k_ in ("D_c", "C_c", "dE_cross", "eO", "eR", "dO", "dR")},
                                              "X_late": v["X_late"], "cost_s": v["cost_s"], "bytes": v4.get("bytes"), "a1": v4.get("a1_rotation"), "a1_deltas": v4.get("a1_deltas_layer0"),
                                              "source_positions": v4.get("source_positions_layer0"), "prepare_positions": v4.get("prepare_positions_layer0")}
    # ---- per condition: numeric, visual, resolution
    for n, cells in numeric.items():
        conf = [k for k in CONFIRM if k in cells]
        row = {"cells": len(conf), "exploratory": n in EXPLORATORY, "sessions": sorted({where[(k, n)] for k in conf if (k, n) in where}), "phases": {}}
        for p in PH:
            npass = sum(1 for k in conf if cells[k]["rules"][p])
            flags = sum(1 for k in conf if flagged(k, n, VIS[p]))
            ref_flags = sum(1 for k in conf if (k, n) in where and ref_flagged(k, n, VIS[p]))
            inspected = sum(1 for k in conf if (k, n) in where)
            status = resolution(npass, len(conf), flags, ref_flags, inspected)
            row["phases"][p] = {"numeric_pass": npass, "of": len(conf), "visual_flags": flags, "ref_flags_same_session": ref_flags, "inspected_cells": inspected, "resolution": status}
        bts = [cells[k].get("bytes") or {} for k in conf]
        tot = max((sum(v for kk, v in b.items() if kk != "oracle_sink_payload") for b in bts), default=0)
        row["bytes_added"] = tot
        row["transfer_lower_bound_s"] = {r: tot * 8 / bps for r, bps in RATES.items()}
        res[n] = row
    # ---- attribution
    ok = lambda n, p: res.get(n, {}).get("phases", {}).get(p, {}).get("resolution") in ("STRICT", "NEAR")  # noqa: E731
    attrib = {}
    for p in ("P1", "P2a", "P2b"):
        suff = [n for n in ("A1", "D", "R", "S1", "S2", "S3") if ok(n, p)]
        joint = ok("DR", p) and not ok("D", p) and not ok("R", p)
        attrib[p] = {"sufficient_single_states": suff, "decoder_and_recent_jointly_sufficient": joint,
                     "not_explained_by_tested_states": not suff and not ok("DR", p)}
    # ---- correspondence (all inspected clips incl. REF / B0)
    corr = {}
    for p in ("P2a", "P2b"):
        tab = {"mm": 0, "mp": 0, "pm": 0, "pp": 0}
        for n, cells in numeric.items():
            for k, c in cells.items():
                vf_ = flagged(k, n, VIS[p])   # one session per (cell, condition): controls are counted once
                if vf_ is None:
                    continue
                mf = not c["rules"][p]
                tab[("m" if mf else "p") + ("m" if vf_ else "p")] += 1
        corr[p] = {"metric_fail_visual_flag": tab["mm"], "metric_fail_no_flag": tab["mp"], "metric_pass_visual_flag": tab["pm"], "metric_pass_no_flag": tab["pp"], "kappa": kappa(tab)}
    # ---- gates
    s3 = res.get("S3", {}).get("phases", {})
    s3_resolves = any(s3.get(p, {}).get("resolution") in ("STRICT", "NEAR") for p in ("P2a", "P2b"))
    s0 = [v for v in validity if v["cell"] in STAGE0]
    gates = {"stage0_valid": bool(s0) and all(v["pass"] for v in s0)
             and all(any(v["cell"] == c and v["check"].startswith(w) for v in s0) for c in STAGE0 for w in ("V0", "B0 reproduces", "A1:", "S3:")),
             "duplicate_controls": dup,
             "stage2_inspected": "S3" in res and s3.get("P2a", {}).get("resolution") != "not inspected",
             "s3_resolves_p2": s3_resolves,
             "stage2b_cells": (CONFIRM if s3_resolves else SUBSET4) if ("S3" in res and s3.get("P2a", {}).get("resolution") != "not inspected") else None,
             "stage3_runs": s3_resolves}
    f = lambda v, n=3: "-" if v is None else (f"{v:.{n}f}" if isinstance(v, float) else str(v))  # noqa: E731
    pos = {k: {"source_sink_positions": (numeric.get("B0", {}).get(k) or {}).get("source_positions"), "a1_deltas": (numeric.get("A1", {}).get(k) or {}).get("a1_deltas"),
               "a1_round_trip": (numeric.get("A1", {}).get(k) or {}).get("a1")} for k in STAGE0}
    for k in STAGE0:   # stage 0 has no metrics: positions and A1 rotation from the summaries
        unit_name, ot = k.split("|"); x = ot.split("-")[1]
        for n_, key_ in (("B0", "source_positions_layer0"), ("A1", "a1_deltas_layer0"), ("A1", "a1_rotation")):
            v4 = (vd4_summary(root / unit_name, f"VD4{x}-{n_}").get("vd4") or {})
            if v4:
                pos[k]["source_sink_positions" if key_ == "source_positions_layer0" else ("a1_deltas" if key_ == "a1_deltas_layer0" else "a1_round_trip")] = v4.get(key_)
    L = ["# VD-4 results (diagnostic; oracle sufficiency at the reset; not necessity, not practical migration)", "",
         "## Stage-0 validity (per cell: V0 = REF, B0 = VD-3, oracle checks, positions)", ""]
    for k in STAGE0:
        rows_ = [v for v in validity if v["cell"] == k]
        L.append(f"- {k}: {'PASS' if rows_ and all(v['pass'] for v in rows_) else 'FAIL'} ({len(rows_)} checks; failed {[v['check'] for v in rows_ if not v['pass']] or 'none'}); "
                 f"source positions {pos[k]['source_sink_positions'] and pos[k]['source_sink_positions'][:3]}, A1 deltas {pos[k]['a1_deltas']}, A1 rotation {pos[k]['a1_round_trip']}")
    L += [f"- duplicate controls across sessions: {dup or 'none'}", ""]
    L += [
         f"Thresholds: VD-3's frozen `vd3_thresholds.json` (SHA-256 {hashlib.sha256(tb).hexdigest()[:16]}). Sessions recorded: "
         f"{[s for s, i in sessions.items() if i] or 'none'}. Validity problems: {[v for v in validity if not v['pass']] or 'none'}.", "",
         "| condition | phase | numeric pass (of 12) | visual flags (REF same session) | resolution | bytes added | lower bound 1 / 10 Gbps |", "|---|---|---|---|---|---|---|"]
    for n in NAMES:
        r = res.get(n)
        if not r:
            continue
        for p in PH:
            ph = r["phases"][p]
            L.append(f"| {n}{' (exploratory)' if r['exploratory'] else ''} | {p} | {ph['numeric_pass']} / {ph['of']} | {ph['visual_flags']} ({ph['ref_flags_same_session']}) | "
                     f"{ph['resolution'] if p != 'P3' else ('no harm' if ph['numeric_pass'] == ph['of'] else 'HARM')} | {r['bytes_added'] / 1e6:.1f} MB | "
                     f"{f(r['transfer_lower_bound_s']['1 Gbps'], 1)} / {f(r['transfer_lower_bound_s']['10 Gbps'], 2)} s |")
    L += ["", "STRICT: all 12 numeric passes and visual flags <= REF's in the same session; NEAR: <= REF's + 1. Raw counts are shown; "
          "a zero count is not proof of zero risk. Lower bounds are idealized transfers of the added bytes, not migration latency.", "",
          "## Attribution (P1, P2a, P2b separately)", ""]
    L += [f"- {p}: sufficient single states {v['sufficient_single_states'] or 'none'}; decoder + recent jointly sufficient: {v['decoder_and_recent_jointly_sufficient']}; "
          f"not explained by the tested states: {v['not_explained_by_tested_states']}" for p, v in attrib.items()]
    L += ["- A Sink-slot effect is reported per slot set (S1 = slot 2; S2 = slots 2, 1; S3 = all); it is not attributed to the number of true slots alone.",
          "", "## Metric violations vs perceptible artifacts", ""]
    L += [f"- {p}: metric fail & flagged {c['metric_fail_visual_flag']}, metric fail & not flagged {c['metric_fail_no_flag']}, metric pass & flagged {c['metric_pass_visual_flag']}, "
          f"both clean {c['metric_pass_no_flag']}; kappa {f(c['kappa'], 2)}" for p, c in corr.items()]
    L += ["", f"## Gates: {json.dumps(gates)}"]
    Path(a.out).with_suffix(".md").write_text("\n".join(L) + "\n")
    Path(a.out).with_suffix(".json").write_text(json.dumps({"stage0_positions": pos, "conditions": res, "numeric": numeric, "attribution": attrib, "correspondence": corr, "validity": validity, "gates": gates}, indent=1, default=str))
    (Path(a.out).parent / f"{pre}vd4_gates.json").write_text(json.dumps(gates, indent=1, default=str))
    print("\n".join(L))


if __name__ == "__main__":
    main()
