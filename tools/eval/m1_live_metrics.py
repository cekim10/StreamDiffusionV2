#!/usr/bin/env python3
"""M1 replay live validation (osdi/m1_continuity/e3_plan.md): migration-boundary continuity of real switchovers with
VD-3's frozen metrics and rules. Runs on the destination host, where the node dumped its output frames and the
same-seed reference frames (`mobility_orchestrate.py --dump_frames DIR`).

Per run (DIR/<run_id>/OUT_<dst> and REF): M = the destination's first generated call. The condition stream is the
reference before M (the source's outputs are the reference's: per-call digests checked by the orchestrator,
`replay_source_unchanged_vs_reference` / exact_check) and the destination's outputs from M on. Windows: VD-4 kind with
reset M and window end M + 24 (the OT-1 Sink-less span; here a post-move window, no Sink is missing). P1 V1 at M,
P2a / P2b over [M, M + 24), with dog_s1|OT-1's frozen thresholds and the VC REF P99 of the unit.

    python tools/eval/m1_live_metrics.py --dump_root /home/ckim151/m1r_frames --runs <run_id>,... --unit dog_s1 --input dog
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

OUT = ROOT / "results/evaluation/osdi/m1_continuity"
THR = ROOT / "results/evaluation/osdi/expVD3/vd3_thresholds.json"
SPAN = 24     # OT-1: bind - reset
PH = ("P1", "P2a", "P2b")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump_root", required=True)
    ap.add_argument("--runs", required=True, help="comma list of run ids (directories under --dump_root)")
    ap.add_argument("--unit", default="dog_s1"); ap.add_argument("--input", default="dog"); ap.add_argument("--cell", default="OT-1")
    ap.add_argument("--embedders", default="dino,dinov2,clip"); ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--work", default=str(ROOT / "results/evaluation/expM1R_metrics"))
    ap.add_argument("--out", default=str(OUT / "e3_metrics.json"))
    ap.add_argument("--k", type=int, default=2)
    a = ap.parse_args()
    import numpy as np

    import aggregate_vd3 as a3
    import aggregate_vd4 as a4
    import vc_frames as vf
    import vc_metrics as vm
    from expw_w1 import workload_paths

    tb = THR.read_bytes()
    if hashlib.sha256(tb).hexdigest()[:16] != a4.THR_SHA_FROZEN:
        sys.exit("thresholds differ from VD-3's frozen file")
    T = json.loads(tb)
    key = f"{a.unit}|{a.cell}"
    tol = a3.thresholds_for(T, key)
    p99 = json.loads((ROOT / "results/evaluation/expVC" / a.unit / "metrics.json").read_text())["ref_spike_P99"]
    video, prompt_f = workload_paths(a.input, None)
    prompt = Path(prompt_f).read_text().strip().splitlines()[0]
    getI = vm.input_provider({"video": str(video)}, False)
    emb = vm.make_embedders(a.embedders, a.device)
    res = {"unit": a.unit, "cell_thresholds": key, "ref_p99": p99, "span": SPAN, "runs": {}}
    for run_id in [x for x in a.runs.split(",") if x]:
        d = Path(a.dump_root) / run_id
        outs = sorted(d.glob("OUT_*"))
        if not outs or not (d / "REF" / "index.json").exists():
            res["runs"][run_id] = {"error": "missing dump"}; continue
        D = vf.read_calls(outs[0]); R = vf.read_calls(d / "REF")
        M = min(D)
        end = max(D)
        lo = M - 16
        O = {c: (R[c] if c < M else D[c]) for c in range(lo, end + 1) if (c < M and c in R) or (c >= M and c in D)}
        Rc = {c: R[c] for c in O if c in R}
        I = {c: getI(c - (a.k - 1)) for c in O}
        cond = {"id": run_id, "kind": "vd4", "resets": [M], "binds": [M + SPAN], "cold_call": None, "frames_from": lo, "frames_to": end, "end": end}
        ref_calls = sorted(R)
        Rg = {c: vm.gray_quarter(R[c]) for c in ref_calls}
        Ig = {c: vm.gray_quarter(getI(c - (a.k - 1))) for c in ref_calls}
        ref_trans = vm.transitions(Rg, Rg, Ig)
        ref_spikes = vm.ref_spike_distribution(ref_trans)
        ref_raw = vm.stream_series(R, vm.gray_quarter, emb, prompt)
        W = vm.windows(cond, a.k)
        ref_S = {"lab": ref_raw["lab"], "metrics": vm.series_metrics(ref_raw, ref_calls, W["pre"])}
        cm = vm.condition_metrics(cond, a.k, O, Rc, I, vm.gray_quarter, emb, prompt, ref_trans, ref_spikes, ref_S)
        # the frozen rule functions read a unit directory: write this run as one (metrics.json + summary.json)
        unit = Path(a.work) / run_id / a.unit
        (unit / run_id).mkdir(parents=True, exist_ok=True)
        (unit / "metrics.json").write_text(json.dumps({"embedders": list(emb), "ref_spike_P99": p99, "conditions": {run_id: cm}}, default=float))
        (unit / run_id / "summary.json").write_text(json.dumps({"condition": cond, "valid": True}))
        a3.EMB = "dino" if "dino" in emb else list(emb)[0]
        v = a3.cell(unit, json.loads((unit / "metrics.json").read_text()), run_id)
        rr = a3.rules(v, "replay", tol, p99, None)
        sl = v["P"]["sinkless"]
        res["runs"][run_id] = {"M": M, "dst_calls": [M, end], "frames_dst": len(D), "frames_ref": len(R), "rules": {p: bool(rr[p]) for p in PH},
                               "v1_reset": v["v1_reset"], "v1_reset_ref_same_call": v["v1_reset_ref_same_call"], "D_c": sl.get("D_c"), "C_c": sl.get("C_c"),
                               "dE_cross": sl.get("dE_cross"), "late_D_c": v["P"]["sl_late"].get("D_c"), "X_late": v["X_late"],
                               "warp_excess": (sl["eO"] - sl["eR"]) if sl.get("eO") is not None and sl.get("eR") is not None else None,
                               "frame_diff_ratio": (sl["dO"] / sl["dR"]) if sl.get("dO") and sl.get("dR") else None,
                               "post_window_last10": {k_: v["P"]["last_10"].get(k_) for k_ in ("D_c", "C_c")}}
        print(f"[M1L] {run_id}: M {M}, V1 {v['v1_reset']:.2f} (P99 {p99:.2f}); rules {res['runs'][run_id]['rules']}", flush=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1, default=float))
    print(f"[M1L] wrote {a.out}")


if __name__ == "__main__":
    main()
