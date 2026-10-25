#!/usr/bin/env python3
"""Experiment VD-3 thresholds (decision of 2026-10-25), written from the Phase T distributions only.

Primary (set A, REF natural window variation), per cell:
  t_DINO = P95 - P5 of REF's 10-call DINO window statistic (content; also the R3 excess-drift limit)
  t_dE   = P95 - P5 of REF's 10-call window dE to the anchor (color drift)
  t_dEx  = P95 of REF's 10-call window dE to the anchor (candidate-vs-REF window color difference)
Sensitivity only: B (lag-10 window change P95 for content and color) and C (cross-seed difference P95).
Fixed, all sets (engineering acceptance criteria, NOT REF-derived confidence bounds): warp-error ratio <= 1.10 and
frame-difference (motion) within +/- 10 % of REF, with an absolute safeguard below a REF window mean of 1.0 gray level
(allowance 0.10 absolute); V1 at the reset and the bind <= REF's own P99 (per unit; `ref_spike_P99` of its metrics).

Before writing, it checks that no VD-3 candidate condition (VD31-*, VD3L-*) exists in any unit, so no candidate
measurement can have informed the thresholds; the check and the SHA-256 of the Phase T file are recorded.

    python tools/eval/vd3_thresholds.py     # -> results/evaluation/osdi/expVD3/vd3_thresholds.{json,md}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import aggregate_vd3 as a3  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/expVD3"


def candidate_data_present(root: Path) -> dict:
    found = {}
    for unit in sorted(root.glob("*_s[01]")):
        ids = [d.name for d in unit.iterdir() if d.is_dir() and d.name.startswith("VD3")]
        mp = unit / "metrics.json"
        mids = [k for k in json.loads(mp.read_text())["conditions"] if k.startswith("VD3")] if mp.exists() else []
        if ids or mids:
            found[unit.name] = sorted(set(ids) | set(mids))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phaseT", default=str(OUT / "vd3_phaseT.json"))
    ap.add_argument("--root", default=str(ROOT / "results/evaluation/expVC"))
    ap.add_argument("--out", default=str(OUT / "vd3_thresholds"))
    a = ap.parse_args()
    found = candidate_data_present(Path(a.root))
    if found:
        sys.exit(f"[vd3] VD-3 candidate data present ({found}): thresholds must be written before any candidate runs")
    pb = Path(a.phaseT).read_bytes()
    P = json.loads(pb)["cells"]
    cells, L = {}, ["# VD-3 thresholds (from the Phase T distributions only; candidate data present: none)", "",
                    f"Source `{Path(a.phaseT).name}` SHA-256 {hashlib.sha256(pb).hexdigest()[:16]}. Primary set A (REF natural window variation) for content "
                    "and color; B (lag-10 change) and C (cross-seed) are sensitivity only. Fixed engineering acceptance criteria (not REF-derived "
                    f"confidence bounds): warp-error ratio <= {1 + a3.REL_LIMIT:.2f}, motion within +/- {a3.REL_LIMIT:.0%} of REF, absolute safeguard "
                    f"below a REF window mean of {a3.ABS_FLOOR} gray level; V1 <= REF P99 per unit.", "",
                    "| cell | conf. | A: t_DINO / t_dE / t_dEx | B: t_DINO / t_dE / t_dEx | C: t_DINO / t_dE / t_dEx |", "|---|---|---|---|---|"]
    for key, c in sorted(P.items()):
        n, s = c["natural_ref_variation"], c["sensitivity_cross_seed"] or {}
        A = {"dino": n["dino"]["P95-P5"], "dE_anchor": n["dE"]["P95-P5"], "dE_cross": n["dE"]["P95"]}
        B = {"dino": n["dino"]["lag10_abs_change"]["P95"], "dE_anchor": n["dE"]["lag10_abs_change"]["P95"], "dE_cross": n["dE"]["P95"]}
        C = {"dino": s["dino"]["P95"], "dE_anchor": s["dE"]["P95"], "dE_cross": s["dE_cross_window"]["P95"]} if s else None
        cells[key] = {"confirmation": c["confirmation"], "counterfactual": c["counterfactual"], "thresholds": A,
                      "sensitivity": {k: v for k, v in (("B", B), ("C", C)) if v}}
        g = lambda d: " / ".join(f"{d[k]:.3f}" for k in ("dino", "dE_anchor", "dE_cross")) if d else "-"  # noqa: E731
        L.append(f"| {key}{' (copied)' if c['counterfactual'] else ''} | {'Y' if c['confirmation'] else '-'} | {g(A)} | {g(B)} | {g(C)} |")
    doc = {"decision": "2026-10-25: A primary for content and color; B and C sensitivity; fixed 10 % warp / motion limits are engineering acceptance criteria",
           "phaseT_sha256": hashlib.sha256(pb).hexdigest(), "candidate_data_present": found,
           "fixed": {"warp_ratio_max": 1 + a3.REL_LIMIT, "motion_rel_max": a3.REL_LIMIT, "abs_floor_gray": a3.ABS_FLOOR, "v1": "REF P99 per unit (ref_spike_P99)",
                     "cost_s_max": a3.COST_LIMIT_S, "bytes_max": a3.BYTES_LIMIT,
                     "p3": {"bind_v1": "<= REF P99 (absolute)", "post_bind_20_non_inferiority_vs_frozen_M1": a3.NI_MARGIN,
                            "last_10": "restoration to the paired REF tolerance (set A content / color; fixed warp / motion)"}}, "cells": cells}
    Path(a.out).with_suffix(".json").write_text(json.dumps(doc, indent=1))
    Path(a.out).with_suffix(".md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
