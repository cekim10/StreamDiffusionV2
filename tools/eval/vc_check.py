#!/usr/bin/env python3
"""Experiment VC-0 validation checks (decided 2026-10-22). VC stops if any check fails; nothing here is evidence.

G1  RD-X replay equivalence: vc_emulate's dog OT-L (the realized schedule of the dog RD-X rep 1 run: reset 80, bind 154)
    reproduces the real run call by call: every call both have (move .. end) with equal output presence and
    |dPSNR| <= 0.001 dB (both logs keep 4 decimals), the emulated prefix digest-identical to REF, the run valid.
G2  W2 cold replay equivalence: vc_emulate's dog COLD-1 reproduces the frozen W2 cold run the same way (including the
    skipped call 34 and the emitted restart frames at 35).
G3  FFV1 frame serialization: for REF and every emulated condition of the unit, vf.check_stream (decode, frame counts,
    per-call digests, contiguous call indices, reset / bind / cold markers equal the schedule, no-output calls, the
    input-to-output alignment rule). For WFS also: the stall duration and the skipped input calls are reported, and
    every output after the resume belongs to input chunk call - (k - 1) (no mismatched input calls are paired).

    python tools/eval/vc_check.py --unit results/evaluation/expVC0/dog_s0 [--g1] [--g2] [--g3] [--write]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import vc_frames as vf  # noqa: E402

SCHED = ROOT / "results/evaluation/osdi/expVC/vc_schedules.json"
TOL_DB = 0.001


def _f(v):
    return None if v in (None, "", "None") else float(v)


def replay_equivalence(unit: Path, cid: str, sched: dict) -> tuple[bool, list[str], dict]:
    cond = next(c for c in sched["inputs"][unit.name.rsplit("_s", 1)[0]]["conditions"] if c["id"] == cid)
    s = json.loads((unit / cid / "summary.json").read_text())
    emu = {int(r["call"]): r for r in csv.DictReader(open(unit / cid / "calls.csv", newline=""))}
    real_dir = ROOT / cond["sources"][0]
    real = {}
    for r in csv.DictReader(open(real_dir / "metrics.csv", newline="")):
        real[int(r["call"])] = r
    move = min(cond["resets"] + ([cond["cold_call"]] if cond.get("cold_call") is not None else []))
    common = sorted(c for c in real if c in emu and c >= move)
    bad, worst, n = [], 0.0, 0
    for c in common:
        rm, em = real[c]["missing"] in ("True", "true"), emu[c]["produced"] not in ("True", "true")
        if rm != em:
            bad.append(f"call {c}: output present real {not rm} vs emulated {not em}"); continue
        pr, pe = _f(real[c]["psnr"]), _f(emu[c]["psnr"])
        if (pr is None) != (pe is None):
            bad.append(f"call {c}: PSNR present real {pr is not None} vs emulated {pe is not None}"); continue
        if pr is not None:
            d = abs(pr - pe); worst = max(worst, d); n += 1
            if d > TOL_DB:
                bad.append(f"call {c}: PSNR real {pr:.4f} vs emulated {pe:.4f}")
    if not s.get("valid"):
        bad.append(f"emulated run not valid: realized {s.get('realized')}")
    if s.get("prefix_identical_to_reference") is False:
        bad.append("emulated prefix differs from REF")
    if len(common) < 50:
        bad.append(f"only {len(common)} common calls")
    return not bad, bad[:20], {"real_run": cond["sources"][0], "common_calls": len(common), "compared_psnr": n, "max_abs_dpsnr": worst,
                               "first_call": common[0] if common else None, "last_call": common[-1] if common else None}


def g3(unit: Path, sched: dict) -> tuple[bool, list[str], dict]:
    inp = unit.name.rsplit("_s", 1)[0]
    conds = {c["id"]: c for c in sched["inputs"][inp]["conditions"]}
    bad, info = [], {}
    for d in sorted(p for p in unit.iterdir() if (p / "summary.json").exists()):
        s = json.loads((d / "summary.json").read_text())
        k = int(s.get("k", 2))
        c = s["condition"]
        exp = {"frames_from": c["frames_from"], "frames_to": c["frames_to"], "resets": c.get("resets", []), "binds": c.get("binds", []),
               "cold_call": c.get("cold_call"), "k": k, "kind": c.get("kind", "ref")}
        ok, why, inf = vf.check_stream(Path(s["frames"]), exp)
        if d.name.startswith("WFS"):
            full = conds[d.name]
            idx = vf.load_index(Path(s["frames"]))["calls"]
            m = full["resets"][0]
            after = [e for e in idx if e["call"] >= m and e["n"]]
            mis = [e["call"] for e in after if e["out_input_call"] != e["call"] - (k - 1)]
            if mis:
                ok = False; why = why + [f"WFS outputs after the resume belong to other input chunks at calls {mis[:5]}"]
            inf.update({"stall_s": full["stall_s"], "skipped_input_calls_harness": full["skipped_input_calls_harness"],
                        "skipped_input_calls_live_realtime": [full["skipped_input_calls_live_realtime"][0], full["skipped_input_calls_live_realtime"][-1],
                                                              len(full["skipped_input_calls_live_realtime"])],
                        "resume_call": m, "first_output_input_chunk": after[0]["out_input_call"] if after else None})
        info[d.name] = {"ok": ok, **inf}
        bad += [f"{d.name}: {w}" for w in why[:10]]
    return not bad, bad, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unit", required=True)
    ap.add_argument("--g1", action="store_true"); ap.add_argument("--g2", action="store_true"); ap.add_argument("--g3", action="store_true")
    ap.add_argument("--schedules", default=str(SCHED))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--name", default="vc0_checks", help="output name under results/evaluation/osdi/expVC (VC-1: vc1_checks_<input>)")
    a = ap.parse_args()
    if not (a.g1 or a.g2 or a.g3):
        a.g1 = a.g2 = a.g3 = True
    unit = Path(a.unit)
    sched = json.loads(Path(a.schedules).read_text())
    res = {}
    if a.g1:
        ok, why, info = replay_equivalence(unit, "OT-L", sched); res["G1"] = {"pass": ok, "failures": why, **info}
    if a.g2:
        ok, why, info = replay_equivalence(unit, "COLD-1", sched); res["G2"] = {"pass": ok, "failures": why, **info}
    if a.g3:
        ok, why, info = g3(unit, sched); res["G3"] = {"pass": ok, "failures": why[:30], "streams": info}
    allok = all(v["pass"] for v in res.values())
    L = [f"# VC-0 checks ({unit})", ""]
    for g, v in res.items():
        L.append(f"- **{g}: {'PASS' if v['pass'] else 'FAIL'}** " + json.dumps({k: x for k, x in v.items() if k not in ('failures', 'streams', 'pass')}, default=str))
        for w in v["failures"]:
            L.append(f"  - {w}")
        for sname, si in (v.get("streams") or {}).items():
            L.append(f"  - {sname}: {'ok' if si['ok'] else 'FAIL'} " + json.dumps({k: x for k, x in si.items() if k != 'ok'}, default=str))
    L += ["", "VC-0: " + ("ALL PASS" if allok else "FAIL - VC stops here")]
    print("\n".join(L))
    if a.write:
        dry = "_dryrun_" in str(unit)
        out = ROOT / "results/evaluation/osdi/expVC" / (("_dryrun_" if dry else "") + a.name)
        out.with_suffix(".md").write_text("\n".join(L) + "\n"); out.with_suffix(".json").write_text(json.dumps(res, indent=1, default=str))
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()
