#!/usr/bin/env python3
"""E10 (osdi/m1_continuity/e10_plan.md): bitwise comparison of the decoded output frames (lossless ffv1 dumps) of two
runs, per node store and call: the butterfly M2 run against its baseline, and each dog fault run against E9's
fresh-base baseline. Equal frames show that the run's outputs are the fresh-base outputs, beyond the per-call PSNR.

    python tools/eval/m2_e10_frames.py   # on elves-02, after A's frames were relayed
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

E10 = Path("/home/ckim151/m2e10_frames")
E9 = Path("/home/ckim151/m2e9_frames")
PAIRS = (("bfly_m2", E10 / "bfly_baseline", E10 / "bfly_m2"),
         ("dog_fault_advertise", E9 / "baseline", E10 / "dog_fault_advertise"),
         ("dog_fault_held", E9 / "baseline", E10 / "dog_fault_held"),
         ("dog_fault_corrupt", E9 / "baseline", E10 / "dog_fault_corrupt"))
STORES = ("OUT_B", "OUT_A", "REF_B", "REF_A")


def run_dir(d: Path) -> Path | None:
    r = sorted(x for x in d.glob("*") if x.is_dir())
    return r[-1] if r else None


def main():
    import numpy as np

    import vc_frames as vf
    res = {}
    for name, base, test in PAIRS:
        a, b = run_dir(base), run_dir(test)
        if a is None or b is None:
            res[name] = {"error": f"missing run under {base if a is None else test}"}; continue
        r = {"base_run": a.name, "test_run": b.name}
        for s in STORES:
            if not (a / s / "index.json").exists() or not (b / s / "index.json").exists():
                r[s] = {"error": "missing store"}; continue
            X, Y = vf.read_calls(a / s), vf.read_calls(b / s)
            common = sorted(set(X) & set(Y))
            diff = [c for c in common if X[c].shape != Y[c].shape or not np.array_equal(X[c], Y[c])]
            r[s] = {"calls_base": [min(X), max(X)], "calls_test": [min(Y), max(Y)], "common": len(common), "bitwise_equal": len(common) - len(diff),
                    "differing_calls": diff[:20], "same_call_set": set(X) == set(Y)}
        res[name] = r
        print(f"[E10F] {name}: " + ", ".join(f"{s} {r[s].get('bitwise_equal')}/{r[s].get('common')}" for s in STORES), flush=True)
    out = ROOT / "results/evaluation/osdi/m1_continuity/e10_frames_bitwise.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"[E10F] wrote {out}")


if __name__ == "__main__":
    main()
