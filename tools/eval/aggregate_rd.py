#!/usr/bin/env python3
"""Experiment RD verdicts (results/evaluation/osdi/expRD/preregistration.md, frozen f850072).

    python tools/eval/aggregate_rd.py phase0 [--dry]   # Phase 0 fidelity gate -> osdi/expRD/phase0_gate.{md,json}; exit 0 iff 5 / 5 pass
    python tools/eval/aggregate_rd.py phase1 [--dry]   # Phase 1 verdicts      -> osdi/expRD/rd_results.{md,json}

Rules applied unchanged: Phase 0 (section 6), D / R / I / E effects, workload classes and the overall statement
(section 7), validity and stopping criteria S2 / S3 (section 9). Per condition id the latest valid run is used.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import rd_metrics as rm  # noqa: E402
import rd_schedule as rs  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/expRD"


def fnum(x):
    try:
        return None if x in ("", "None", None) else float(x)
    except ValueError:
        return None


def load_runs(phase: int, dry: bool) -> dict:
    """{(workload, condition id): {"dir", "summary", "psnr", "valid", "all_dirs"}} (latest valid, else latest)."""
    root = ROOT / "results/evaluation" / f"{'_dryrun_' if dry else ''}expRD_phase{phase}"
    out = {}
    for d in sorted(root.glob("*_s*/*")):
        if not (d / "summary.json").exists():
            continue
        s = json.load(open(d / "summary.json"))
        key = (s["workload"], s["condition"]["id"])
        psnr = {int(r["call"]): fnum(r["psnr"]) for r in csv.DictReader(open(d / "calls.csv", newline=""))}
        rec = {"dir": str(d.relative_to(ROOT)), "summary": s, "psnr": psnr, "valid": bool(s.get("valid"))}
        prev = out.get(key)
        rec["all_dirs"] = (prev["all_dirs"] if prev else []) + [rec["dir"]]
        if prev is None or rec["valid"] or not prev["valid"]:
            out[key] = rec if (prev is None or rec["valid"] or not prev["valid"]) else prev
        else:
            prev["all_dirs"] = rec["all_dirs"]
    return out


# ----------------------------------------------------------------------------- Phase 0
def real_run(target: str) -> dict:
    ds = sorted(glob.glob(str(ROOT / "results/evaluation" / target)))
    assert len(ds) == 1, (target, ds)
    d = Path(ds[0]); s = json.load(open(d / "summary.json"))
    fin = s["path"][-1]
    binds = [b["call"] for b in (s.get("vacw") or {}).get("binds") or []] or [s["final"]["bind_call"]]
    moves = [m["call"] for m in s["moves"]]
    rows = [r for r in csv.DictReader(open(d / "metrics.csv", newline="")) if r["owner"] == fin]
    return {"dir": str(d.relative_to(ROOT)), "resets": moves, "binds": binds, "psnr": {int(r["call"]): fnum(r["psnr"]) for r in rows}}


def phase0(dry: bool) -> bool:
    runs = load_runs(0, dry)
    res, ok_all = [], True
    for t in rs.phase0():
        real = real_run(t["target"])
        em = runs.get((t["workload"], t["id"]))
        r = {"id": t["id"], "target": real["dir"], "schedule_matches_real": real["resets"] == t["resets"] and real["binds"] == t["binds"]}
        if em is None:
            r.update({"pass": False, "why": "no emulated run"}); res.append(r); ok_all = False; continue
        b = t["binds"][-1]
        common = {c for c in range(b, b + rs.H) if real["psnr"].get(c) is not None and em["psnr"].get(c) is not None}
        tr_r, tr_e = rm.trajectory(real["psnr"], b, common), rm.trajectory(em["psnr"], b, common)
        dif = [abs(real["psnr"][c] - em["psnr"][c]) for c in sorted(common)]
        med = st.median(dif) if dif else None
        checks = {"emulated_run_valid": em["valid"], "schedule_matches_real": r["schedule_matches_real"], "common_calls": len(common) >= 10,
                  "same_crossing": tr_r["crossed"] == tr_e["crossed"], "same_sustained": tr_r["sustained"] == tr_e["sustained"],
                  "T_within_1dB": tr_r["T"] is not None and tr_e["T"] is not None and abs(tr_r["T"] - tr_e["T"]) <= 1.0,
                  "median_abs_dpsnr_le_1dB": med is not None and med <= 1.0}
        r.update({"emulated": em["dir"], "n_common": len(common), "real": tr_r, "emulated_traj": tr_e, "median_abs_dpsnr": med, "max_abs_dpsnr": max(dif) if dif else None,
                  "checks": checks, "pass": all(checks.values())})
        ok_all &= r["pass"]
        res.append(r)
    out = {"dry": dry, "n_targets": len(res), "n_pass": sum(r["pass"] for r in res), "gate": "PASS" if ok_all and len(res) == 5 else "FAIL", "targets": res}
    OUT.mkdir(parents=True, exist_ok=True)
    stem = "_dryrun_phase0_gate" if dry else "phase0_gate"
    (OUT / f"{stem}.json").write_text(json.dumps(out, indent=1, default=str))
    f = lambda x: "-" if x is None else f"{x:.2f}"  # noqa: E731
    L = [f"# RD Phase 0 fidelity gate{' (DRY RUN: fake runtime, not meaningful)' if dry else ''}", "", f"**Gate: {out['gate']}** ({out['n_pass']} / {out['n_targets']}; frozen rule: 5 / 5)", "",
         "| target | schedule = real | common calls | crossing real / emul | sustained real / emul | T real / emul (dB) | median / max abs dPSNR | pass |", "|---|---|---|---|---|---|---|---|"]
    for r in res:
        if "real" not in r:
            L.append(f"| {r['id']} | {r['schedule_matches_real']} | - | - | - | - | - | **FAIL** ({r['why']}) |"); continue
        L.append(f"| {r['id']} | {r['schedule_matches_real']} | {r['n_common']} | {r['real']['crossed']} / {r['emulated_traj']['crossed']} | {r['real']['sustained']} / {r['emulated_traj']['sustained']} | "
                 f"{f(r['real']['T'])} / {f(r['emulated_traj']['T'])} | {f(r['median_abs_dpsnr'])} / {f(r['max_abs_dpsnr'])} | {'PASS' if r['pass'] else '**FAIL** ' + str([k for k, v in r['checks'].items() if not v])} |")
    (OUT / f"{stem}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return out["gate"] == "PASS"


# ----------------------------------------------------------------------------- Phase 1
def phase1(dry: bool) -> dict:
    runs = load_runs(1, dry)
    T = lambda w, cid: (runs.get((w, cid)) or {}).get("summary", {}).get("trajectory", {}).get("T") if (runs.get((w, cid)) or {}).get("valid") else None  # noqa: E731
    out = {"dry": dry, "workloads": {}, "stops": [], "runs": {}}
    expected = {(w, c["id"]) for w in rs.PHASE1_WORKLOADS for c in rs.phase1(w)}
    missing = sorted(k for k in expected if not (runs.get(k) or {}).get("valid"))
    out["n_expected"], out["n_valid"], out["missing_or_invalid"] = len(expected), len(expected) - len(missing), [f"{w}/{c}" for w, c in missing]
    # S2 determinism
    det = {}
    for w in rs.PHASE1_WORKLOADS:
        a, b_ = runs.get((w, "b155_r1_d75")), runs.get((w, "b155_r1_d75_rep2"))
        if a and b_:
            t1 = a["summary"]["t_first_reset"]
            dif = [abs(a["psnr"][c] - b_["psnr"][c]) for c in a["psnr"] if c >= t1 and a["psnr"].get(c) is not None and b_["psnr"].get(c) is not None]
            det[w] = st.median(dif) if dif else None
        else:
            det[w] = None
    out["determinism_median_abs_dpsnr"] = det
    if any(v is None or v > 0.5 for v in det.values()):
        out["stops"].append("S2: determinism repeat differs by > 0.5 dB (or missing): verdicts withheld; fallback = 3 runs per condition after approval")
    # S3 dog control
    dog0 = {b: T(rs.CONTROL, f"b{b}_r1_d0") for b in rs.ANCHORS}
    if any(v is None or v < 35.0 for v in dog0.values()):
        out["stops"].append(f"S3: dog r1 d = 0 below 35 dB (or missing) at an anchor {dog0}: harness fault suspected; verdicts withheld")
    classes = {}
    for w in rs.PHASE1_WORKLOADS:
        tab = {f"b{b}_{s}_d{d}": T(w, f"b{b}_{s}_d{d}") for b in rs.ANCHORS for s, ds in (("r1", rs.D_R1), ("r3c", rs.D_R3C), ("r3e", rs.D_R3E)) for d in ds}
        info = {"T": tab}
        need = [k for k in tab if not k.split("_")[1] == "r3e"]
        if any(tab[k] is None for k in need):
            info["class"] = "NOT EVALUABLE (missing / invalid: " + ", ".join(k for k in need if tab[k] is None) + ")"
            out["workloads"][w] = info; continue
        D_each = {}
        for b in rs.ANCHORS:
            seq = [tab[f"b{b}_r1_d{d}"] for d in rs.D_R1]
            D_each[b] = {"drop_0_100": seq[0] - seq[-1], "max_rise": max(y - x for x, y in zip(seq, seq[1:]))}
        D = all(v["drop_0_100"] >= 3.0 and v["max_rise"] <= 1.0 for v in D_each.values())
        dR = {f"b{b}_d{d}": tab[f"b{b}_r1_d{d}"] - tab[f"b{b}_r3c_d{d}"] for b in rs.ANCHORS for d in rs.D_R3C}
        R = st.median(dR.values()) >= 2.0 and sum(1 for v in dR.values() if v > 0) >= 6
        I = R and all(dR[f"b{b}_d100"] - dR[f"b{b}_d25"] >= 2.0 for b in rs.ANCHORS)
        E = all(tab[f"b{b}_r1_d0"] < 35.0 for b in rs.ANCHORS)
        allT = [tab[k] for k in need]
        if E:
            cls = "EPHEMERAL"
        elif D and R:
            cls = "BOTH" + (" + INTERACTION" if I else "")
        elif D:
            cls = "DURATION"
        elif R:
            cls = "RESET"
        elif all(t >= 35.0 for t in allT):
            cls = "NOT REPRODUCED"
        else:
            cls = "UNCLASSIFIED"
        info.update({"D": D, "D_by_anchor": D_each, "R": R, "dR": dR, "dR_median": st.median(dR.values()), "dR_positive": sum(1 for v in dR.values() if v > 0), "I": I, "E": E, "class": cls,
                     "r3e_minus_r3c_d75": {b: tab[f"b{b}_r3e_d75"] - tab[f"b{b}_r3c_d75"] if tab[f"b{b}_r3e_d75"] is not None else None for b in rs.ANCHORS}})
        out["workloads"][w] = info
        if w in rs.REFRESH_HEAVY:
            classes[w] = cls
    base = [c.split(" +")[0] for c in classes.values()]
    top = max(set(base), key=base.count) if base else None
    if out["stops"]:
        out["overall"] = "WITHHELD (" + "; ".join(out["stops"]) + ")"
    elif len(classes) < 3 or any(c.startswith("NOT EVALUABLE") for c in classes.values()):
        out["overall"] = "NOT EVALUABLE (a refresh-heavy workload is not evaluable)"
    elif base.count(top) >= 2 and top == "NOT REPRODUCED":
        out["overall"] = f"NOT REPRODUCED for {base.count(top)} of 3 refresh-heavy workloads: the emulated factors do not reproduce the recovery failure"
    elif base.count(top) >= 2 and top == "UNCLASSIFIED":
        out["overall"] = f"UNCLASSIFIED for {base.count(top)} of 3 refresh-heavy workloads"
    elif base.count(top) >= 2:
        out["overall"] = f"recovery failure is associated with {top} under in-place M1 emulation for {base.count(top)} of 3 refresh-heavy workloads"
    else:
        out["overall"] = "workload-dependent (no class shared by >= 2 of 3 refresh-heavy workloads)"
    out["dog_control_crossed_everywhere"] = all((runs.get((rs.CONTROL, c["id"])) or {}).get("summary", {}).get("trajectory", {}).get("crossed") for c in rs.phase1(rs.CONTROL))
    for (w, cid), r in sorted(runs.items()):
        s = r["summary"]
        out["runs"][f"{w}/{cid}"] = {"dir": r["dir"], "valid": r["valid"], "trajectory": s["trajectory"], "gap_psnr": s["gap_psnr"], "reference_sink_changes": len(s["reference_sink_changes"]),
                                     "no_reference": None if not s.get("no_reference") else {k: v for k, v in s["no_reference"].items() if k not in ("flow",)}, "all_dirs": r["all_dirs"]}
    OUT.mkdir(parents=True, exist_ok=True)
    stem = "_dryrun_rd_results" if dry else "rd_results"
    (OUT / f"{stem}.json").write_text(json.dumps(out, indent=1, default=str))
    f = lambda x: "-" if x is None else f"{x:.1f}"  # noqa: E731
    L = [f"# RD Phase 1 verdicts{' (DRY RUN: fake runtime, not meaningful)' if dry else ''}", "", f"Valid runs {out['n_valid']} / {out['n_expected']}; stops: {out['stops'] or 'none'}",
         f"Determinism (median |dPSNR|, repeat vs first): {det}", f"**Overall: {out['overall']}**", "",
         "| workload | class | D (drop d0->d100 by anchor; max rise) | R (median dR; positive / 8) | I | E |", "|---|---|---|---|---|---|"]
    for w, i in out["workloads"].items():
        if "D" not in i:
            L.append(f"| {w} | {i['class']} | | | | |"); continue
        dtxt = ", ".join("%s: %.1f / %.1f" % (b, v["drop_0_100"], v["max_rise"]) for b, v in i["D_by_anchor"].items())
        L.append(f"| {w} | **{i['class']}** | {i['D']} ({dtxt}) | {i['R']} ({i['dR_median']:.1f}; {i['dR_positive']}) | {i['I']} | {i['E']} |")
    L += ["", "Terminal PSNR T (dB), crossing (x) / sustained (s):", "", "| workload | anchor | " + " | ".join([f"r1 d{d}" for d in rs.D_R1] + [f"r3c d{d}" for d in rs.D_R3C] + [f"r3e d{d}" for d in rs.D_R3E]) + " |",
          "|---|---|" + "---|" * (len(rs.D_R1) + len(rs.D_R3C) + len(rs.D_R3E))]
    for w in rs.PHASE1_WORKLOADS:
        for b in rs.ANCHORS:
            cells = []
            for s_, ds in (("r1", rs.D_R1), ("r3c", rs.D_R3C), ("r3e", rs.D_R3E)):
                for d in ds:
                    r = out["runs"].get(f"{w}/b{b}_{s_}_d{d}")
                    cells.append("-" if not r else f"{f(r['trajectory']['T'])} {'x' if r['trajectory']['crossed'] else ''}{'s' if r['trajectory']['sustained'] else ''}")
            L.append(f"| {w} | {b} | " + " | ".join(cells) + " |")
    (OUT / f"{stem}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["phase0", "phase1"])
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.what == "phase0":
        sys.exit(0 if phase0(a.dry) else 2)
    phase1(a.dry)


if __name__ == "__main__":
    main()
