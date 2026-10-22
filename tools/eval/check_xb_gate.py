#!/usr/bin/env python3
"""XB real-GPU exactness gate (osdi/expXB/preregistration.md section 3.1 / 3.2; before any calibration run).

Gate runs: XB1 setting (A -> B, trigger 30, 1 Gbps, seed 0), dog and butterfly-feeding-slow-motion, P-full and R-full with
--xb_verify_state, default parameters. A run PASSES iff
  P-full: the run is valid; every component (inflight, meta, recent, sink, vae) matched the source's digest at the
          atomic switchover boundary; every delivered call of the destination after the switchover is bit-identical
          to the uninterrupted reference (frame digest), with at least min(50, horizon - 2) calls checked.
  R-full: the run is valid (lossless inputs bit-exact at the switchover); the replayed state matches the source's
          state digests at its stop boundary for every component; every delivered call after the resume is bit-identical
          to the reference (same minimum).
Calibration starts only if every gate run passes; a failure is reported with the failing component or first
mismatching call, and calibration waits for review.

    python tools/eval/check_xb_gate.py --root results/evaluation/expXB_gate_dog --root results/evaluation/expXB_gate_bfly [--write]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from xb_delivery import delivery_metrics, load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

FULL = {"inflight", "meta", "recent", "sink", "vae"}


def check_run(d: Path, dry: bool) -> tuple[bool, list[str], dict]:
    s, m, ev = load_run(d)
    pol = s["policy"]
    ok, why = run_validity_xb(s, d, dry=dry)
    notes = [] if ok else [f"invalid: {why}"]
    D = delivery_metrics(s, m, ev)
    horizon = int(s.get("xb_params", {}).get("horizon") or 100)
    need = min(50, horizon - 2)
    eq = D["output_equivalence"][-1] if D["output_equivalence"] else None
    info = {"policy": pol, "run": d.name, "output_equivalence": eq, "ttfo_local_s": D["ttfo_local_final_s"]}
    if not s.get("xb_params", {}).get("verify_state"):
        notes.append("not a gate run (--xb_verify_state missing)")
    if pol == "precopy_full":
        sv = [e for e in ev if e["event"] == "xb_switch_verified"]
        comps = sv[-1].get("components_ok", {}) if sv else {}
        info["components_ok"] = comps
        if not (sv and set(comps) == FULL and all(comps.values())):
            notes.append(f"switchover digests: {comps or 'none'}")
    elif pol == "recompute_full":
        sv = [e for e in ev if e["event"] == "xb_recompute_state_verified"]
        comps = sv[-1].get("components_ok", {}) if sv else {}
        info["components_ok"] = comps
        if not (sv and set(comps) == FULL and all(comps.values())):
            notes.append(f"replayed state digests: {comps or 'none (no verification ran)'}")
        if s["validation"].get("inputs_exact_at_switchovers") is not True:
            notes.append("decoded inputs not bit-exact")
    else:
        notes.append(f"policy {pol} has no gate")
    if eq is None or eq["checked"] < need or eq["matching"] != eq["checked"]:
        notes.append(f"output equivalence: {eq and eq['matching']} / {eq and eq['checked']} calls match (need all, >= {need}); first mismatch call {eq and eq['first_mismatch_call']}")
    return not notes, notes, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", action="append", required=True)
    ap.add_argument("--write", action="store_true", help="write results/evaluation/osdi/expXB/gate_check.md")
    a = ap.parse_args()
    lines, all_ok, n = ["# XB exactness gate", "", "| run | policy | result | components | output equivalence | notes |", "|---|---|---|---|---|---|"], True, 0
    for root in a.root:
        root = Path(root)
        dry = "_dryrun_" in root.name
        for d in sorted(root.glob("policy=*")):
            if not (d / "summary.json").exists():
                continue
            ok, notes, info = check_run(d, dry)
            n += 1; all_ok &= ok
            eq = info["output_equivalence"] or {}
            lines.append(f"| {d.name} | {info['policy']} | {'PASS' if ok else 'FAIL'} | {info.get('components_ok')} | {eq.get('matching')} / {eq.get('checked')} | {'; '.join(notes) or '-'} |")
    verdict = "GATE PASS" if (all_ok and n) else ("GATE FAIL" if n else "GATE: no runs found")
    lines += ["", verdict, ""]
    print("\n".join(lines))
    if a.write:
        (ROOT / "results/evaluation/osdi/expXB/gate_check.md").write_text("\n".join(lines))
    sys.exit(0 if (all_ok and n) else 1)


if __name__ == "__main__":
    main()
