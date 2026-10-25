#!/usr/bin/env python3
"""Experiment VD-3 tolerances (osdi/expVD3/preregistration.md section 3): numerical tolerances of the paired REF
comparisons, from REF streams alone, fixed before any candidate condition is aggregated. Runs on the host that holds
the frames (needs the REF frames of <input>_s0 and <input>_s1).

Per input and schedule (OT-1, OT-L; the anchor is the schedule's 16 pre-move calls, the span its control's span):
  seed-to-seed natural variation: two uninterrupted generations (seed 0, seed 1) of the same input see the same scene
      evolution, so the difference of their drift statistics over the same 10-call window measures natural
      variability, not scene change. w_seed(m) = P95 over sliding 10-call windows after the anchor of |stat_s1 - stat_s0|
      for content (DINO similarity to the own anchor), color (dE to the own anchor); for warp / motion P95 |ratio - 1|
      of mean e_s1 / mean e_s0 (d_s1 / d_s0); for the candidate-vs-REF color, P95 of the window dE between the two
      REF streams at the same calls.
  band width (the draft-4 definition, kept as an upper bound): P95 - P5 of each REF's 10-call window means over the
      span (relative to the median for warp / motion).
  tolerance w(m) = min(w_seed(m), band(m) of seed 0, band(m) of seed 1).
Assay sensitivity: the frozen-M1 control of every cell is checked against the R2 content clause with these
tolerances; VC-1 established a visible Sink-less change in every frozen-M1 stream, so a cell where the control passes
is reported as non-discriminative (preregistration section 4).

    python tools/eval/vd3_tolerances.py --root results/evaluation/expVC [--embedder dino --device cuda:0] [--dry]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

import vc_frames as vf  # noqa: E402
import vc_metrics as vm  # noqa: E402
import vc_schedules as vs  # noqa: E402

INPUTS = ("dog", "train", "butterfly-feeding-slow-motion", "audi-snow-trail")
WIN = 10
CONFIRM = {("train", 0), ("audi-snow-trail", 0), ("dog", 1), ("train", 1), ("butterfly-feeding-slow-motion", 1), ("audi-snow-trail", 1)}


def wins(x: np.ndarray) -> np.ndarray:
    return np.array([np.nanmean(x[i:i + WIN]) for i in range(len(x) - WIN + 1)]) if len(x) >= WIN else np.array([])


def ref_series(unit: Path, emb: dict, calls: list[int], pre: set, k: int):
    s = json.loads((unit / "REF" / "summary.json").read_text())
    R = vf.read_calls(Path(s["frames"]), calls)
    getI = vm.input_provider(s, bool(s.get("dry_run")), R[min(R)].shape[1:3])
    S = vm.stream_series(R, vm.gray_quarter, emb, None)
    M = vm.series_metrics(S, sorted(R), pre)
    g = {c: vm.gray_quarter(R[c]) for c in sorted(R)}
    gi = {c: vm.gray_quarter(getI(c - (k - 1))) for c in sorted(R)}
    return R, S, M, g, gi


def tolerances(root: Path, inp: str, x: str, emb: dict, sched: dict) -> dict:
    u0, u1 = root / f"{inp}_s0", root / f"{inp}_s1"
    ctrl = next(c for c in vs.unit_sched(sched, u1.name)["conditions"] if c["id"] == f"OT-{x}")
    k = int(json.loads((u0 / "REF" / "summary.json").read_text()).get("k", 2))
    m = ctrl["resets"][0]
    pre = set(range(m - vm.PRE, m))
    calls = list(range(ctrl["frames_from"], ctrl["frames_to"] + 1))
    name = next(iter(emb))
    R0, S0, M0, g0, gi = ref_series(u0, emb, calls, pre, k)
    R1, S1, M1, g1, _ = ref_series(u1, emb, calls, pre, k)
    common = [c for c in calls if c in R0 and c in R1]
    post = [c for c in common if c >= m]
    tr = vm.transitions({c: g1[c] for c in common}, {c: g0[c] for c in common}, {c: gi[c] for c in common})   # O = seed 1, R = seed 0
    per = {c: {} for c in common}
    for t in tr:
        if t["eO"] is not None and t["eR"] is not None:
            per[t["call"]].setdefault("e1", []).append(t["eO"]); per[t["call"]].setdefault("e0", []).append(t["eR"])
        if t["dR"] is not None:
            per[t["call"]].setdefault("d1", []).append(t["dO"]); per[t["call"]].setdefault("d0", []).append(t["dR"])
    ser = lambda key, cs: np.array([np.mean(per[c][key]) if per[c].get(key) else np.nan for c in cs])  # noqa: E731
    v0 = np.array([M0["v5a"][name].get(c, np.nan) for c in post]); v1 = np.array([M1["v5a"][name].get(c, np.nan) for c in post])
    c0 = np.array([M0["v4_pre"].get(c, np.nan) for c in post]); c1 = np.array([M1["v4_pre"].get(c, np.nan) for c in post])
    xde = [vm.de2000(np.mean([S1["lab"][c] for c in post[i:i + WIN]], 0), np.mean([S0["lab"][c] for c in post[i:i + WIN]], 0)) for i in range(len(post) - WIN + 1)]
    e1, e0, d1, d0 = ser("e1", post), ser("e0", post), ser("d1", post), ser("d0", post)
    rat = lambda a, b: np.array([np.nanmean(a[i:i + WIN]) / np.nanmean(b[i:i + WIN]) for i in range(len(a) - WIN + 1)])  # noqa: E731
    seed = {"dino": float(np.nanpercentile(np.abs(wins(v1) - wins(v0)), 95)), "dE_anchor": float(np.nanpercentile(np.abs(wins(c1) - wins(c0)), 95)),
            "dE_cross": float(np.nanpercentile(xde, 95)), "E": float(np.nanpercentile(np.abs(rat(e1, e0) - 1), 95)), "motion": float(np.nanpercentile(np.abs(rat(d1, d0) - 1), 95))}
    allv = lambda M_, key: np.array([M_[key].get(c, np.nan) if key == "v4_pre" else M_["v5a"][name].get(c, np.nan) for c in common])  # noqa: E731

    def band(a):
        w = wins(a)
        p5, p50, p95 = np.nanpercentile(w, [5, 50, 95])
        return float(p95 - p5), float(p50)
    e0a, e1a, d0a, d1a = ser("e0", common), ser("e1", common), ser("d0", common), ser("d1", common)
    bands = {}
    for sd, (Mx, ea, da) in (("s0", (M0, e0a, d0a)), ("s1", (M1, e1a, d1a))):
        wd, _ = band(allv(Mx, "v5a")); wc, _ = band(allv(Mx, "v4_pre"))
        we, me = band(ea); wm, mm = band(da)
        bands[sd] = {"dino": wd, "dE_anchor": wc, "dE_cross_p95_own": float(np.nanpercentile(wins(allv(Mx, "v4_pre")), 95)), "E": we / me if me else None, "motion": wm / mm if mm else None}
    final = {}
    for key in ("dino", "dE_anchor", "E", "motion"):
        cands = [seed[key]] + [bands[s][key] for s in ("s0", "s1") if bands[s][key] is not None]
        final[key] = float(min(cands))
    final["dE_cross"] = float(min(seed["dE_cross"], bands["s0"]["dE_cross_p95_own"], bands["s1"]["dE_cross_p95_own"]))
    return {"input": inp, "schedule": f"OT-{x}", "anchor": [m - vm.PRE, m - 1], "span": [ctrl["frames_from"], ctrl["frames_to"]], "n_post_calls": len(post),
            "embedder": name, "seed_to_seed": seed, "band_widths": bands, "tolerance": final,
            "rules": {"content": f"paired D_c >= -{final['dino']:.4f}", "color_anchor": f"paired C_c <= +{final['dE_anchor']:.3f}",
                      "color_cross": f"window dE candidate vs REF <= {final['dE_cross']:.3f}", "warp": f"E_O / E_R <= {1 + final['E']:.3f}",
                      "motion": f"motion ratio in [{1 - final['motion']:.3f}, {1 + final['motion']:.3f}]"}}


def sensitivity(root: Path, inp: str, seed: int, x: str, tol: dict) -> dict:
    """Frozen-M1 control vs the R2 content clause (must fail for the cell to be discriminative)."""
    mp = root / f"{inp}_s{seed}" / "metrics.json"
    if not mp.exists():
        return {"available": False}
    M = json.loads(mp.read_text())
    cm = M["conditions"].get(f"OT-{x}")
    if cm is None:
        return {"available": False}
    pc, sl = cm["per_call"], cm["sinkless_calls"]
    key = [k_ for k_ in next(iter(pc.values())) if k_.startswith("v5a_") and not k_.startswith("v5a_vbench") and not k_.endswith("_ref")]
    key = "v5a_dino" if "v5a_dino" in key else (key[0] if key else None)
    o = np.array([np.nan if pc[str(c)].get(key) is None else pc[str(c)][key] for c in sl]); r = np.array([np.nan if pc[str(c)].get(key + "_ref") is None else pc[str(c)][key + "_ref"] for c in sl])
    d = float(np.nanmean(o - r))
    return {"available": True, "control_D_c": d, "tolerance": -tol["dino"], "control_fails_R2_content": bool(d < -tol["dino"]), "confirmation": (inp, seed) in CONFIRM}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT / "results/evaluation/expVC"))
    ap.add_argument("--embedder", default="dino")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--inputs", default=",".join(INPUTS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry", action="store_true", help="synthetic units: output named _dryrun_")
    a = ap.parse_args()
    root = Path(a.root)
    dry = a.dry or "_dryrun_" in str(root)
    emb = vm.make_embedders(a.embedder, a.device)
    sched = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())
    res, L = {"cells": {}, "sensitivity": {}}, ["# VD-3 tolerances (REF streams only; fixed before any candidate condition is aggregated)", ""]
    for inp in [x for x in a.inputs.split(",") if x]:
        for x in ("1", "L"):
            t = tolerances(root, inp, x, emb, sched)
            res["cells"][f"{inp}|OT-{x}"] = t
            L.append(f"- {inp} OT-{x}: " + "; ".join(t["rules"].values()) + f"  (seed-to-seed {json.dumps({k_: round(v, 4) for k_, v in t['seed_to_seed'].items()})}; band s0 {json.dumps({k_: (round(v, 4) if v is not None else None) for k_, v in t['band_widths']['s0'].items()})})")
            for sd in (0, 1):
                res["sensitivity"][f"{inp}_s{sd}|OT-{x}"] = sensitivity(root, inp, sd, x, t["tolerance"])
    L += ["", "## Assay sensitivity (frozen M1 must fail the R2 content clause)", ""]
    for kk, v in res["sensitivity"].items():
        if v.get("available"):
            L.append(f"- {kk}{' (confirmation)' if v['confirmation'] else ''}: control D_c {v['control_D_c']:+.3f} vs -{-v['tolerance']:.4f} -> {'discriminative' if v['control_fails_R2_content'] else 'NOT DISCRIMINATIVE'}")
        else:
            L.append(f"- {kk}: control metrics not available")
    nd = [kk for kk, v in res["sensitivity"].items() if v.get("available") and v["confirmation"] and not v["control_fails_R2_content"]]
    res["non_discriminative_confirmation_cells"] = nd
    L += ["", f"Non-discriminative confirmation cells: {nd or 'none'}"]
    out = Path(a.out or ROOT / "results/evaluation/osdi/expVD3" / ("_dryrun_vd3_tolerances" if dry else "vd3_tolerances"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(res, indent=1, default=float)); out.with_suffix(".md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
