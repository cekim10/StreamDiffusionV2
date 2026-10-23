#!/usr/bin/env python3
"""Experiment VC aggregation (preregistration draft 3 section 6; VC-0 decision of 2026-10-22 on V5 analysis).

Frame-level values are averaged within a call, and calls are averaged within a window. Confidence intervals use a
moving block bootstrap over calls, to respect temporal dependence. The parameters are fixed here before any VC-1
result: block length 5 calls (20 frames; sensitivity 3 and 10), 10,000 resamples, seed 0, percentile 95 % interval.
A 10-call window holds only two blocks, so its interval is reported but is not informative. Effect sizes are reported
before verdicts. Nothing generalizes beyond the tested inputs and seed 0.

    python tools/eval/aggregate_vc.py [--dry]     # -> results/evaluation/osdi/expVC/vc_results.{md,json}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BLOCK, BLOCKS_SENS, B, SEED = 5, (3, 10), 10_000, 0
H1_E, H1_M = 1.10, (0.90, 1.10)


def block_boot(cols: list[np.ndarray], stat, L: int = BLOCK, b: int = B, seed: int = SEED) -> tuple[float, float] | None:
    """Moving block bootstrap over the call axis of aligned 1-D arrays `cols`; `stat(*resampled cols)` -> float."""
    n = len(cols[0])
    if n < 2:
        return None
    L = min(L, n)
    rng = np.random.default_rng(seed)
    starts = np.arange(n - L + 1)
    nb = int(np.ceil(n / L))
    vals = np.empty(b)
    for i in range(b):
        idx = np.concatenate([np.arange(s, s + L) for s in rng.choice(starts, nb)])[:n]
        vals[i] = stat(*[c[idx] for c in cols])
    lo, hi = np.nanpercentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def series(per_call: dict, calls: list[int], key: str) -> np.ndarray:
    return np.array([np.nan if per_call[str(c)].get(key) is None else per_call[str(c)][key] for c in calls], dtype=float)


def window_calls(cm: dict, name: str) -> list[int]:
    w = cm["windows"].get(name)
    if not w:
        return []
    return [c for c in range(w["calls"][0], w["calls"][1] + 1) if str(c) in cm["per_call"]]


def ratio_with_ci(pc, calls, a, b_):
    x, y = series(pc, calls, a), series(pc, calls, b_)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    if len(x) < 2 or y.mean() <= 0:
        return {"value": None}
    f = lambda u, v: u.mean() / v.mean() if v.mean() > 0 else np.nan  # noqa: E731
    return {"value": float(x.mean() / y.mean()), "ci95": block_boot([x, y], f), "ci95_sens": {L: block_boot([x, y], f, L) for L in BLOCKS_SENS}, "n_calls": int(len(x))}


def paired_diff(pc, calls, k_o, k_r, all_calls):
    """OTTER - REF at the same calls (mean, block-bootstrap CI), REF's own band (P5-P95 of the 10-call-window means over
    the condition's span) and the effect size (mean O - REF median) / (P95 - P5)."""
    o, r = series(pc, calls, k_o), series(pc, calls, k_r)
    ok = ~(np.isnan(o) | np.isnan(r))
    o, r = o[ok], r[ok]
    if len(o) < 2:
        return {"diff": None}
    d = o - r
    rs = series(pc, all_calls, k_r)
    wins = [np.nanmean(rs[i:i + 10]) for i in range(0, len(rs) - 9)]
    p5, p50, p95 = (np.nanpercentile(wins, [5, 50, 95]) if wins else (np.nan,) * 3)
    eff = (o.mean() - p50) / (p95 - p5) if (p95 - p5) > 0 else None
    return {"diff": float(d.mean()), "ci95": block_boot([d], lambda u: u.mean()), "ci95_sens": {L: block_boot([d], lambda u: u.mean(), L) for L in BLOCKS_SENS},
            "o_mean": float(o.mean()), "ref_mean_same_calls": float(r.mean()), "ref_band_p5_p95": [float(p5), float(p95)], "ref_window_median": float(p50),
            "effect_size": None if eff is None else float(eff), "inside_ref_band": bool(p5 <= o.mean() <= p95), "n_calls": int(len(o))}


def analyze_unit(unit: Path) -> dict:
    m = json.loads((unit / "metrics.json").read_text())
    embs = m["embedders"]
    out = {"ref_spike_P99": m["ref_spike_P99"], "ref_playback": m.get("REF_playback"), "conditions": {}}
    for cid, cm in m["conditions"].items():
        if cid.startswith("VD"):
            continue   # Experiment VD conditions are aggregated by aggregate_vd.py, never here
        pc = cm["per_call"]
        allc = sorted(int(c) for c in pc)
        r = {"windows": {}, "events": cm["events"], "playback": cm.get("playback"), "unpaired_calls": cm.get("unpaired_calls")}
        for wn in ("pre", "sinkless", "post_bind_20", "last_10"):
            cs = window_calls(cm, wn)
            if not cs:
                continue
            w = {"calls": [cs[0], cs[-1]], "E_ratio": ratio_with_ci(pc, cs, "eO", "eR"), "motion_ratio": ratio_with_ci(pc, cs, "dO", "dR"),
                 "v4_window_to_ref": cm["windows"][wn]["v4_window_to_ref"], "v4_drift_vs_pre": paired_diff(pc, cs, "v4_pre", "v4_pre_ref", allc)}
            for n in embs:
                if n == "pixel":
                    continue
                w[f"v5a_{n}"] = paired_diff(pc, cs, f"v5a_{n}", f"v5a_{n}_ref", allc)
                w[f"v5a_vbench_{n}"] = paired_diff(pc, cs, f"v5a_vbench_{n}", f"v5a_vbench_{n}_ref", allc)
            if "clip" in embs:
                w["v5b_clip"] = paired_diff(pc, cs, "v5b", "v5b_ref", allc)
            if "pixel" in embs:
                w["v5a_pixel"] = paired_diff(pc, cs, "v5a_pixel", "v5a_pixel_ref", allc)
            r["windows"][wn] = w
        out["conditions"][cid] = r
    return out


def hypotheses(units: dict) -> dict:
    H = {"VC-H1": {}, "VC-H2": {}, "VC-H3": {}}
    for inp, U in units.items():
        C = U["conditions"]
        rows = []
        for cid in ("OT-1", "OT-L", "OT-R"):
            if cid not in C:
                continue
            for wn in ("post_bind_20", "last_10"):
                w = C[cid]["windows"].get(wn, {})
                e, mo = (w.get("E_ratio") or {}).get("value"), (w.get("motion_ratio") or {}).get("value")
                ok = e is not None and mo is not None and e <= H1_E and H1_M[0] <= mo <= H1_M[1]
                rows.append({"condition": cid, "window": wn, "E_ratio": e, "E_ci95": (w.get("E_ratio") or {}).get("ci95"), "motion_ratio": mo,
                             "motion_ci95": (w.get("motion_ratio") or {}).get("ci95"), "within": ok})
        H["VC-H1"][inp] = {"rows": rows, "supported": bool(rows) and all(x["within"] for x in rows)}
        pairs = []
        for ot, cold in (("OT-1", "COLD-1"), ("OT-L", "COLD-L")):
            if ot in C and cold in C:
                so = next((e for e in C[ot]["events"] if e["kind"] == "reset"), {})
                sc = next((e for e in C[cold]["events"] if e["kind"] == "cold_emit"), {})
                ratio = (so["spike"] / sc["spike"]) if (so.get("spike") and sc.get("spike")) else None
                pairs.append({"pair": f"{ot} vs {cold}", "ratio_OT_over_COLD": ratio, "OT_spike": so.get("spike"), "COLD_spike": sc.get("spike"), "COLD_across_gap": sc.get("across_gap"),
                              "OT_pct_rank_in_REF": so.get("pct_rank_in_ref"), "COLD_pct_rank_in_REF": sc.get("pct_rank_in_ref"), "REF_P99": U["ref_spike_P99"],
                              "OT_le_COLD": ratio is not None and ratio <= 1.0})
        H["VC-H2"][inp] = {"pairs": pairs, "supported": bool(pairs) and all(p["OT_le_COLD"] for p in pairs)}
        H["VC-H3"][inp] = {cid: (C[cid]["windows"].get("sinkless") or {}).get("E_ratio") for cid in ("OT-1", "OT-L", "OT-R") if cid in C}
    return H


def fmt(x, n=3):
    return "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--root", default=None)
    a = ap.parse_args()
    root = Path(a.root or ROOT / "results/evaluation" / ("_dryrun_expVC" if a.dry else "expVC"))
    units = {u.name.rsplit("_s", 1)[0]: analyze_unit(u) for u in sorted(root.glob("*_s0")) if (u / "metrics.json").exists()}
    H = hypotheses(units)
    L = [f"# VC results{' (DRY RUN - synthetic frames, not a result)' if a.dry else ''}", "",
         f"Block bootstrap over calls: block {BLOCK} calls (sensitivity {BLOCKS_SENS}), {B} resamples, seed {SEED}. Tested inputs and seed 0 only.", "",
         "## VC-H1 post-bind motion consistency (effect sizes, then verdict; claim limited to motion consistency after the bind)", "",
         "| input | condition | window | E_O / E_R [95 % CI] | motion ratio [95 % CI] | within 1.10 / [0.90, 1.10] |", "|---|---|---|---|---|---|"]
    for inp, h in H["VC-H1"].items():
        for r in h["rows"]:
            L.append(f"| {inp} | {r['condition']} | {r['window']} | {fmt(r['E_ratio'])} {r['E_ci95'] and [round(x, 3) for x in r['E_ci95']]} | {fmt(r['motion_ratio'])} {r['motion_ci95'] and [round(x, 3) for x in r['motion_ci95']]} | {r['within']} |")
        L.append(f"| {inp} | **verdict** | | | | **{'supported' if h['supported'] else 'not supported'}** |")
    L += ["", "## VC-H2 reset discontinuity, OTTER vs COLD (ratio first; REF P99 and percentile ranks are descriptive context, not perceptual thresholds)", "",
          "| input | pair | V1 OT / V1 COLD | V1 OT | V1 COLD (across the skipped call) | OT pct rank in REF | COLD pct rank in REF | REF P99 | OT <= COLD |", "|---|---|---|---|---|---|---|---|---|"]
    for inp, h in H["VC-H2"].items():
        for p in h["pairs"]:
            L.append(f"| {inp} | {p['pair']} | {fmt(p['ratio_OT_over_COLD'])} | {fmt(p['OT_spike'], 2)} | {fmt(p['COLD_spike'], 2)} | {fmt(p['OT_pct_rank_in_REF'], 1)} | {fmt(p['COLD_pct_rank_in_REF'], 1)} | {fmt(p['REF_P99'], 2)} | {p['OT_le_COLD']} |")
    L += ["", "## Descriptive: V4 global color drift, V5a content similarity, V5b prompt alignment (OTTER - REF at the same calls; REF band = P5-P95 of REF's 10-call windows)", ""]
    for inp, U in units.items():
        for cid, r in U["conditions"].items():
            for wn, w in r["windows"].items():
                if wn == "pre":
                    continue
                parts = [f"V4 to REF {fmt(w['v4_window_to_ref'], 2)}"]
                for key, v in w.items():
                    if key.startswith(("v5", "v4_drift")) and isinstance(v, dict) and v.get("diff") is not None:
                        parts.append(f"{key} diff {fmt(v['diff'])} {v['ci95'] and [round(x, 3) for x in v['ci95']]} band {[round(x, 3) for x in v['ref_band_p5_p95']]} eff {fmt(v['effect_size'], 2)}")
                L.append(f"- {inp} {cid} {wn}: " + "; ".join(parts))
    L += ["", "## Playback (last-frame-hold playback model; rate matched to the measured delivery cadence; the 16 fps variant is in the json)", "",
          "| input | condition | timeline | stalls (>= 1 frame) | total stall (s) | total lateness (s) | longest freeze (s) | resume jumps |", "|---|---|---|---|---|---|---|---|"]
    for inp, U in units.items():
        rp = (U.get("ref_playback") or {}).get("rate_matched") or {}
        L.append(f"| {inp} | REF | derived | {rp.get('n_stalls')} | {fmt(rp.get('total_stall_s'), 2)} | {fmt(rp.get('total_lateness_s'), 2)} | {fmt(rp.get('longest_stall_s'), 2)} | - |")
        for cid, r in U["conditions"].items():
            p = (r.get("playback") or {}).get("rate_matched") or {}
            L.append(f"| {inp} | {cid} | {(r.get('playback') or {}).get('timeline_kind')} | {p.get('n_stalls')} | {fmt(p.get('total_stall_s'), 2)} | {fmt(p.get('total_lateness_s'), 2)} | {fmt(p.get('longest_stall_s'), 2)} | {[x and round(x, 1) for x in p.get('resume_jumps', [])][:4]} |")
    out = ROOT / "results/evaluation/osdi/expVC" / ("_dryrun_vc_results" if a.dry else "vc_results")
    out.with_suffix(".md").write_text("\n".join(L) + "\n")
    out.with_suffix(".json").write_text(json.dumps({"units": units, "hypotheses": H, "bootstrap": {"block": BLOCK, "sensitivity": BLOCKS_SENS, "B": B, "seed": SEED}}, indent=1, default=str))
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
