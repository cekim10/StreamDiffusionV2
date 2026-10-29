#!/usr/bin/env python3
"""E10 report (osdi/m1_continuity/e10_plan.md): per run (butterfly baseline / M2, dog fault runs) and migration, the
fields of m2_report.migration plus continuity; the butterfly equivalence check (B's outputs 64 .. 163 in both runs).

    python tools/eval/m2_e10_report.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import m2_report as mr  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/m1_continuity"
RUNS = ("bfly_baseline", "bfly_m2", "dog_fault_advertise", "dog_fault_held", "dog_fault_corrupt")


def main():
    rep = {}
    for name in RUNS:
        mr.ROOTS[name] = str(ROOT / f"results/evaluation/expM2E10_{name}")
        R = mr.load(name)
        if R is None:
            rep[name] = {"error": "run missing"}; continue
        v = R["summary"]["validation"]
        rep[name] = {"run": R["dir"].name, "validation": {k: v[k] for k in v if k != "gpu0_before_run"}, "migrations": [mr.migration(R, 1), mr.migration(R, 2)],
                     "psnr_B": {int(m["call"]): m["psnr"] for m in R["mt"] if m["owner"] == "B"}}
        for k in (1, 2):
            f = OUT / f"e10_metrics_{name}_mig{k}.json"
            if f.exists():
                m = next(iter(json.load(open(f))["runs"].values()))
                rep[name]["migrations"][k - 1]["continuity"] = {x: m.get(x) for x in ("M", "rules", "v1_reset", "v1_reset_ref_same_call", "D_c", "C_c", "late_D_c", "warp_excess", "frame_diff_ratio", "stores")}
    pb = lambda n: rep.get(n, {}).get("psnr_B") or {}  # noqa: E731
    for a_, b_, key in (("bfly_baseline", "bfly_m2", "bfly"),):
        x, y = pb(a_), pb(b_)
        common = sorted(set(x) & set(y))
        rep[f"equivalence_{key}"] = {"B_calls_compared": len(common), "B_psnr_equal_every_call": bool(common) and all(x[c] == y[c] for c in common)}
    e9 = OUT / "e9_report.json"
    if e9.exists():   # the dog fault runs' first migration and B segment against E9's dog runs
        b9 = json.load(open(e9))
        rep["e9_dog_reference"] = {"baseline_mig2_continuity": b9["baseline"]["migrations"][1].get("continuity"), "m2_mig2_continuity": b9["m2"]["migrations"][1].get("continuity")}
    for n in RUNS:
        rep.get(n, {}).pop("psnr_B", None)
    (OUT / "e10_report.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
