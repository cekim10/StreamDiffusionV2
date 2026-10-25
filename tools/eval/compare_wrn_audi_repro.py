#!/usr/bin/env python3
"""Provenance reproduction of the W2 audi-snow-trail seed-0 OTTER unit (osdi/audi_s0_w2_provenance.md; approved
2026-10-25). The frozen run `expW_W2_audi-snow-trail_s0/..._20261019-135751` generated train seed 1; the reproduction
(`expWP_W2_audi-snow-trail_s0`, run with the node identity check) is stored separately. Nothing frozen is modified.

1. Verification of the reproduction (required before any comparison): valid under the frozen W / R / N rules; every
   node's HELLO carries an identity with the audi-snow-trail input, seed 0 and a launch token; node A's baseline frame
   digests equal the genuine audi seed-0 generation (`expRDX_audi-snow-trail`, `expWX_audi_*`) and differ from train
   seed 1.
2. Unit metrics side by side: frozen (mislabeled), reproduction, and the genuine but invalid run `..._050104`
   (descriptive only).
3. W-H1 / W-H2 (primary, S1, S2) / W-H3 recomputed by aggregate_wrn.agg_w with the audi seed-0 OTTER run replaced by
   the reproduction (the Cold-restart run is unchanged), next to the frozen recomputation; any changed verdict listed.
4. The reproduction's schedule (move call, bind call, per-call timeline) for VD-3's sensitivity analysis (D2b).

    python tools/eval/compare_wrn_audi_repro.py      # -> results/evaluation/osdi/expW/audi_s0_repro_report.{md,json}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import aggregate_wrn as aw  # noqa: E402

EV = ROOT / "results/evaluation"
UNIT = "expW_W2_audi-snow-trail_s0"
BAD = "policy=reuse_dyn_bw=1000_rho=none_tm=inf_rep=1_20261019-135751"
INVALID_GENUINE = "policy=reuse_dyn_bw=1000_rho=none_tm=inf_rep=1_20261019-050104"
GENUINE_REFS = ("expRDX_audi-snow-trail", "expWX_audi_X1")
TRAIN_S1 = "expW_W2_train_s1"


def digests(run: Path, n=40):
    p = run / "node_A" / "baseline_record.json"
    return [r.get("frame_digest") for r in json.load(open(p))[1:n]] if p.exists() else None


def first_run(exp: str) -> Path | None:
    ds = sorted((EV / exp).glob("policy=*"))
    return next((d for d in ds if digests(d)), None)


def verify(repro: Path) -> tuple[bool, list[str], dict]:
    bad, info = [], {}
    s = json.load(open(repro / "summary.json"))
    ok, why = aw.run_validity_wrn(s, repro, dry=False)
    info["valid"] = ok
    if not ok:
        bad.append(f"not valid under the W / R / N rules: {why}")
    hello = json.load(open(repro / "host_info.json"))
    for lb, h in hello.items():
        idn = (h.get("hello") or {}).get("identity")
        info[f"identity_{lb}"] = idn
        if not isinstance(idn, dict):
            bad.append(f"node {lb}: no identity in HELLO (run without the identity check)"); continue
        if "audi-snow-trail" not in str(idn.get("video_path")) or idn.get("seed") != 0 or not idn.get("launch_id"):
            bad.append(f"node {lb}: identity {idn.get('video_path')} seed {idn.get('seed')} launch {idn.get('launch_id')!r}")
    dg = digests(repro)
    gen = {e: digests(first_run(e)) for e in GENUINE_REFS if first_run(e)}
    tr = digests(first_run(TRAIN_S1))
    info["digest_equal_genuine"] = {e: (dg == g) for e, g in gen.items()}
    info["digest_equal_train_s1"] = dg == tr
    if not dg or not gen or not all(dg == g for g in gen.values()):
        bad.append(f"node A baseline digests do not equal the genuine audi seed-0 generation {info['digest_equal_genuine']}")
    if dg == tr:
        bad.append("node A baseline digests equal train seed 1")
    return not bad, bad, info


def splice(run: Path):
    """aggregate_wrn.runs_in with the audi seed-0 OTTER run replaced by `run` (the Cold-restart run unchanged)."""
    keep = aw.runs_in
    return lambda exp, dry: ([r for r in keep(exp, dry) if r["policy"] != "reuse_dyn"] + [aw.run_rec(run, False)]) if exp == UNIT else keep(exp, dry)


def unit_rec(run: Path) -> dict:
    keep, aw.runs_in = aw.runs_in, splice(run)
    try:
        return aw.w2_unit("audi-snow-trail", 0, False)
    finally:
        aw.runs_in = keep


def schedule(run: Path) -> dict:
    s = json.load(open(run / "summary.json"))
    import csv

    tl = {int(r["call"]): float(r["t_out_rel"]) for r in csv.DictReader(open(run / "metrics.csv", newline="")) if r["t_out_rel"] not in ("", "None")}
    return {"run": str(run.relative_to(ROOT)), "move_call": s["moves"][0]["call"], "bind_call": s["final"].get("bind_call"),
            "sink_bind_rel_s": s["final"].get("sink_bind_rel_s"), "t_out_rel_by_call": tl}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repro_exp", default="expWP_W2_audi-snow-trail_s0")
    ap.add_argument("--out", default=str(ROOT / "results/evaluation/osdi/expW/audi_s0_repro_report"))
    a = ap.parse_args()
    reps = [d for d in sorted((EV / a.repro_exp).glob("policy=reuse_dyn_*")) if (d / "summary.json").exists()]
    if not reps:
        sys.exit(f"[wp] no reproduction run under results/evaluation/{a.repro_exp}")
    repro = reps[-1]
    ok, why, info = verify(repro)
    L = ["# W2 audi-snow-trail seed-0 OTTER unit: provenance reproduction (osdi/audi_s0_w2_provenance.md)", "",
         f"Reproduction: `{repro.relative_to(EV)}`; frozen (mislabeled): `{UNIT}/{BAD}`. Nothing frozen is modified.", "",
         f"## 1. Verification: {'PASS' if ok else 'FAIL'}", ""] + [f"- {x}" for x in why] + \
        [f"- valid under the W / R / N rules: {info.get('valid')}; node A digests equal the genuine audi seed-0 generation: {info.get('digest_equal_genuine')}; "
         f"equal train seed 1: {info.get('digest_equal_train_s1')}"]
    out = {"repro": str(repro), "verified": ok, "verification": why, "info": info}
    if not ok:
        L += ["", "**The reproduction is not verified: no comparison is made.**"]
    else:
        frozen_u, repro_u = unit_rec(EV / UNIT / BAD), unit_rec(repro)
        genuine_inv = EV / UNIT / INVALID_GENUINE
        keys = ("ttfo_s", "service_s", "bind_call", "rejoin", "rejoin_call", "rejoin_calls", "sustained_calls", "psnr_median_last10", "psnr_final_call", "min_psnr_after_crossing")
        L += ["", "## 2. Unit metrics (OTTER side; the Cold-restart run is genuine and unchanged)", "",
              "| metric | frozen (train seed 1, mislabeled) | reproduction (audi seed 0, verified) |", "|---|---|---|"]
        for k in keys:
            L.append(f"| {k} | {(frozen_u['reuse_dyn'] or {}).get(k)} | {(repro_u['reuse_dyn'] or {}).get(k)} |")
        for k in ("rvc",):
            fr, rp = (frozen_u["reuse_dyn"] or {}).get(k), (repro_u["reuse_dyn"] or {}).get(k)
            L.append(f"| RVC events (cut-induced) | {len(fr or [])} ({sum(1 for e in fr or [] if e['cut_induced'])}) | {len(rp or [])} ({sum(1 for e in rp or [] if e['cut_induced'])}) |")
        L.append(f"\nDescriptive only: the genuine but invalid run `{INVALID_GENUINE}` (NIC rule) - bind 58, first crossing 84, last-10 median 34.9 dB (wrn_report.md section 6).")
        keep = aw.runs_in
        W0 = aw.agg_w(False)
        aw.runs_in = splice(repro)
        try:
            W1 = aw.agg_w(False)
        finally:
            aw.runs_in = keep
        L += ["", "## 3. W verdicts: frozen data vs the audi seed-0 OTTER run replaced by the verified reproduction", "",
              "| criterion | frozen recomputation | corrected | changed |", "|---|---|---|---|"]
        changed = []
        for k in ("W-H1", "W-H2 primary", "W-H2 S1", "W-H2 S2", "W-H3"):
            f0 = W0[k] if isinstance(W0[k], str) else json.dumps({x: W0[k].get(x) for x in ("n", "successes", "share", "verdict")}, default=str)
            f1 = W1[k] if isinstance(W1[k], str) else json.dumps({x: W1[k].get(x) for x in ("n", "successes", "share", "verdict")}, default=str)
            v0 = W0[k] if isinstance(W0[k], str) else W0[k].get("verdict"); v1 = W1[k] if isinstance(W1[k], str) else W1[k].get("verdict")
            ch = str(v0).split(" ")[0] != str(v1).split(" ")[0]
            changed += [k] if ch else []
            L.append(f"| {k} | {f0} | {f1} | {'**CHANGED**' if ch else 'no'} |")
        L.append(f"| W-H1 audi TTFO (workload mean) | {W0['W-H1 per workload TTFO'].get('audi-snow-trail')} | {W1['W-H1 per workload TTFO'].get('audi-snow-trail')} | - |")
        frozen_json = json.load(open(ROOT / "results/evaluation/osdi/wrn_results.json"))["W"]
        same_as_frozen = all(str(frozen_json[k] if isinstance(frozen_json[k], str) else frozen_json[k].get("verdict")) == str(W0[k] if isinstance(W0[k], str) else W0[k].get("verdict"))
                             for k in ("W-H1", "W-H2 primary", "W-H3"))
        L += ["", f"The frozen recomputation reproduces the recorded wrn_results.json verdicts: {same_as_frozen}. Changed verdicts: {changed or 'none'}.",
              "", "## 4. Schedule of the reproduction (VD-3 sensitivity analysis, D2b; the VD-3 confirmation cell keeps the copied schedule)", ""]
        sch = schedule(repro)
        L.append(f"- move call {sch['move_call']}, bind call {sch['bind_call']}, Sink bind at {sch['sink_bind_rel_s']} s after the move")
        out.update({"frozen_unit": frozen_u, "repro_unit": repro_u, "W_frozen_recomputed": W0, "W_corrected": W1, "changed": changed,
                    "frozen_recomputation_matches_record": same_as_frozen, "repro_schedule": sch})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).with_suffix(".md").write_text("\n".join(L) + "\n")
    Path(a.out).with_suffix(".json").write_text(json.dumps(out, indent=1, default=str))
    print("\n".join(L))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
