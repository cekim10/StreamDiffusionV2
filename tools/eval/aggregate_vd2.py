#!/usr/bin/env python3
"""Experiment VD-2 aggregation (osdi/expVD2/preregistration.md sections 4-5). Effect sizes and costs first, then
verdicts; DR-4 is reported as exploratory and enters no verdict.

Reads the VC unit (metrics.json with the VD-2 conditions merged, calls.csv, summary.json). Control = the frozen-M1
VC-1 condition (OT-1 / OT-L) of the same unit.

    python tools/eval/aggregate_vd2.py [--dry] [--root DIR]    # -> results/evaluation/osdi/expVD2/vd2_results.{md,json}
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import rd_metrics as rm  # noqa: E402
from aggregate_vc import paired_diff, series, window_calls  # noqa: E402

INPUTS = ("dog", "butterfly-feeding-slow-motion")
CELLS = ("DR1", "DR2", "RP1", "TSin", "TSout", "DR2+TSout", "RP1+TSout", "DR4")
LAT_BYTES = 16 * 60 * 104 * 2          # one latent frame, bf16 (the pipeline's [16, 60, 104] latent)
CHUNK_RAW_BYTES = 5 * 3 * 480 * 832   # RP-1: the seed frames of one chunk (raw upper bound; FFV1 is ~1/3)
COST_LIMIT = {"DR1": 1.0, "DR2": 1.0, "DR4": 1.0, "TSin": 1.0, "TSout": 1.0, "RP1": 1.5, "DR2+TSout": 1.5, "RP1+TSout": 1.5}
BYTES_LIMIT = {"DR1": 1e6, "DR2": 1e6, "DR4": 1e6, "TSin": 1e6, "TSout": 1e6, "RP1": 6e6, "DR2+TSout": 1e6, "RP1+TSout": 6e6}
PREFERRED_S = 0.3


def bytes_added(name: str) -> int:
    b = 0
    if name.startswith("DR"):
        b += int(name[2:].split("+")[0]) * LAT_BYTES
    if "TSout" in name:
        b += 2 * LAT_BYTES
    if "RP1" in name:
        b += CHUNK_RAW_BYTES
    return b


def mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and np.isnan(x))]
    return float(np.mean(xs)) if xs else None


def cell(unit: Path, M: dict, cid: str) -> dict | None:
    cm = M["conditions"].get(cid)
    if cm is None:
        return None
    pc = cm["per_call"]; allc = sorted(int(c) for c in pc)
    ev = {e["kind"]: e for e in cm["events"]}
    sl, f4, pb = window_calls(cm, "sinkless"), window_calls(cm, "first_4"), window_calls(cm, "post_bind_20")
    psnr = {}
    if (unit / cid / "calls.csv").exists():
        for r in csv.DictReader(open(unit / cid / "calls.csv", newline="")):
            psnr[int(r["call"])] = float(r["psnr"]) if r["psnr"] not in ("", "None") else None
    tr = rm.trajectory(psnr, cm["b"]) if psnr else {}
    s = json.loads((unit / cid / "summary.json").read_text()) if (unit / cid / "summary.json").exists() else {}
    v2 = s.get("vd2") or {}
    pbd = paired_diff(pc, pb, "v5a_dino", "v5a_dino_ref", allc) if pb else {}
    sld = paired_diff(pc, sl, "v5a_dino", "v5a_dino_ref", allc) if sl else {}
    return {"valid": s.get("valid"), "v1_reset": (ev.get("reset") or {}).get("spike"), "v1_bind": (ev.get("bind") or {}).get("spike"),
            "sl_dino": mean(series(pc, sl, "v5a_dino")) if sl else None, "sl_dino_ref": mean(series(pc, sl, "v5a_dino_ref")) if sl else None,
            "sl_band": sld.get("ref_band_p5_p95"), "sl_dE": (cm["windows"].get("sinkless") or {}).get("v4_window_to_ref"),
            "sl_E": (cm["windows"].get("sinkless") or {}).get("E_ratio"), "f4_E": (cm["windows"].get("first_4") or {}).get("E_ratio"),
            "pb_dino_diff": pbd.get("diff"), "pb_band_width": (pbd["ref_band_p5_p95"][1] - pbd["ref_band_p5_p95"][0]) if pbd.get("ref_band_p5_p95") else None,
            "pb_dE": (cm["windows"].get("post_bind_20") or {}).get("v4_window_to_ref"),
            "terminal_psnr": tr.get("T"), "cross_call": tr.get("cross_call"), "cost_s": (v2.get("cost_s") or {}).get("total_serial_s"), "cost_parts": v2.get("cost_s"),
            "fidelity": {k: v for k, v in (v2.get("fidelity") or {}).items() if k != "per_layer"} if v2.get("fidelity") else None,
            "fidelity_layers": (v2.get("fidelity") or {}).get("per_layer"), "latent_shapes": v2.get("latent_shapes"), "dr_short": v2.get("dr_short")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--root", default=None)
    a = ap.parse_args()
    root = Path(a.root or ROOT / "results/evaluation" / ("_dryrun_expVC" if a.dry else "expVC"))
    R, H = {}, {k: [] for k in ("H1", "H2", "H3", "H4", "H5", "H6")}
    f = lambda x, n=3: "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))  # noqa: E731
    L = [f"# VD-2 results{' (DRY RUN - synthetic, not a result)' if a.dry else ''}", "",
         "Effect sizes and costs first. Control = frozen M1 (VC-1's OT-1 / OT-L). DINO = content similarity to the 16 pre-move calls; 'closed' = fraction of the gap between frozen M1 and REF closed in the Sink-less window; 'in band' = inside REF's own P5-P95 (preservation, descriptive). Costs are serial GPU seconds at the destination (upper bound on the TTFO increase) and bytes added to the fast path (RP-1 as a raw upper bound).", ""]
    n_inputs = 0
    for inp in INPUTS:
        unit = root / f"{inp}_s0"
        if not (unit / "metrics.json").exists():
            continue
        n_inputs += 1
        M = json.loads((unit / "metrics.json").read_text())
        p99 = M.get("ref_spike_P99")
        for x in ("1", "L"):
            ctrl = cell(unit, M, f"OT-{x}")
            if ctrl is None:
                continue
            cells = {name: cell(unit, M, f"VD2{x}-{name}") for name in CELLS}
            R[f"{inp}|OT-{x}"] = {"control": ctrl, "cells": cells, "ref_P99": p99}
            L += [f"## {inp} OT-{x} (REF V1 P99 {f(p99, 2)}; control: V1 reset {f(ctrl['v1_reset'], 2)}, bind {f(ctrl['v1_bind'], 2)}, Sink-less DINO {f(ctrl['sl_dino'])} vs REF {f(ctrl['sl_dino_ref'])} band {ctrl['sl_band'] and [round(b, 3) for b in ctrl['sl_band']]}, dE {f(ctrl['sl_dE'], 2)}, terminal {f(ctrl['terminal_psnr'], 1)} dB, first >= 35 dB {ctrl['cross_call']})", "",
                  "| cell | valid | V1 reset (x ctrl) | V1 bind (x ctrl) | Sink-less DINO | closed | in band | Sink-less dE | first-4 E | post-bind DINO diff | post-bind dE | terminal PSNR | first >= 35 | cost s (pref <= 0.3) | bytes | DR fidelity (median / worst rel) |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for name, v in cells.items():
                if v is None:
                    continue
                gap = (ctrl["sl_dino_ref"] - ctrl["sl_dino"]) if (ctrl["sl_dino"] is not None and ctrl["sl_dino_ref"] is not None) else None
                closed = ((v["sl_dino"] - ctrl["sl_dino"]) / gap) if (gap and v["sl_dino"] is not None) else None
                inband = (v["sl_band"] is not None and v["sl_dino"] is not None and v["sl_band"][0] <= v["sl_dino"] <= v["sl_band"][1])
                v.update({"closed": closed, "in_band": inband, "bytes": bytes_added(name)})
                fid = v["fidelity"] or {}
                L.append(f"| {name}{' (exploratory)' if name == 'DR4' else ''} | {v['valid']} | {f(v['v1_reset'], 2)} ({f(v['v1_reset'] / ctrl['v1_reset'] if v['v1_reset'] and ctrl['v1_reset'] else None, 2)}) | "
                         f"{f(v['v1_bind'], 2)} ({f(v['v1_bind'] / ctrl['v1_bind'] if v['v1_bind'] and ctrl['v1_bind'] else None, 2)}) | {f(v['sl_dino'])} | {f(closed, 2)} | {inband} | {f(v['sl_dE'], 2)} | {f(v['f4_E'])} | "
                         f"{f(v['pb_dino_diff'])} | {f(v['pb_dE'], 2)} | {f(v['terminal_psnr'], 1)} | {v['cross_call']} | {f(v['cost_s'])} | {v['bytes'] / 1e6:.2f} MB | "
                         f"{f(fid.get('median_rel_fro'))} / {f(fid.get('worst_rel_fro'))} (layer {fid.get('worst_layer')}) |")
            L.append("")
            # verdict inputs (every input and schedule must agree)
            dr2, rp1, tsi, tso = cells["DR2"], cells["RP1"], cells["TSin"], cells["TSout"]
            ok = lambda v: v is not None and v.get("valid")  # noqa: E731
            H["H1"].append(ok(dr2) and dr2["v1_reset"] is not None and ctrl["v1_reset"] and dr2["v1_reset"] <= 0.5 * ctrl["v1_reset"] and p99 is not None and dr2["v1_reset"] <= p99 + 1.0)
            H["H2"].append(ok(rp1) and rp1["v1_reset"] is not None and ctrl["v1_reset"] and rp1["v1_reset"] <= 0.5 * ctrl["v1_reset"] and rp1["f4_E"] is not None and ctrl["f4_E"] is not None and rp1["f4_E"] < ctrl["f4_E"])
            H["H3"].append(ok(tso) and tso.get("closed") is not None and tso["closed"] >= 0.5 and tso["sl_dE"] is not None and ctrl["sl_dE"] is not None and tso["sl_dE"] < ctrl["sl_dE"])
            H["H4"].append(ok(tso) and ok(tsi) and tso["sl_dino"] is not None and tsi["sl_dino"] is not None and tso["sl_dino"] > tsi["sl_dino"])
            h5 = []
            for name in ("TSin", "TSout", "DR2+TSout", "RP1+TSout"):
                v = cells[name]
                if not ok(v):
                    h5.append(False); continue
                traj = (abs((v["terminal_psnr"] or -99) - (ctrl["terminal_psnr"] or 0)) <= 1.0) if inp.startswith("butterfly") else \
                       (v["cross_call"] is not None and ctrl["cross_call"] is not None and v["cross_call"] <= ctrl["cross_call"] + 5)
                bind_ok = v["v1_bind"] is not None and ctrl["v1_bind"] is not None and v["v1_bind"] <= 2 * ctrl["v1_bind"]
                pb_ok = (v["pb_dino_diff"] is not None and ctrl["pb_dino_diff"] is not None and v["pb_band_width"] is not None and v["pb_dino_diff"] >= ctrl["pb_dino_diff"] - v["pb_band_width"]
                         and v["pb_dE"] is not None and ctrl["pb_dE"] is not None and v["pb_dE"] <= ctrl["pb_dE"] + 0.5)
                h5.append(bool(traj and bind_ok and pb_ok))
            H["H5"].append(all(h5))
            H["H6"].append(all(ok(cells[n]) and cells[n]["cost_s"] is not None and cells[n]["cost_s"] <= COST_LIMIT[n] and cells[n]["bytes"] <= BYTES_LIMIT[n] for n in CELLS if n != "DR4"))
    need = 2 * len(INPUTS)

    def verdict(xs):
        if n_inputs < len(INPUTS) or len(xs) < need:
            return "PENDING" if any(xs) or not xs else "NOT SUPPORTED"
        return "SUPPORTED" if all(xs) else "NOT SUPPORTED"
    V = {k: verdict(v) for k, v in H.items()}
    L += ["## Verdicts (preregistered rules; every input and schedule must agree)", "",
          f"- VD2-H1 (DR-2 halves the reset jump and lands within REF P99 + 1): **{V['H1']}** {H['H1']}",
          f"- VD2-H2 (RP-1 halves the reset jump and lowers first-4 warp error): **{V['H2']}** {H['H2']}",
          f"- VD2-H3 (TS-out closes >= 50 % of the Sink-less content gap and lowers color drift; improvement only): **{V['H3']}** {H['H3']}",
          f"- VD2-H4 (TS-out preserves identity better than TS-in): **{V['H4']}** {H['H4']}",
          f"- VD2-H5 (temporary Sinks keep the exact bind and the post-bind stream): **{V['H5']}** {H['H5']}",
          f"- VD2-H6 (costs within limits; preferred <= 0.3 s reported per cell): **{V['H6']}** {H['H6']}",
          "- Preservation (descriptive): see 'in band' per cell. A 50 % closure is not continuity preservation.",
          "- DR-4: exploratory, excluded from every verdict."]
    out = ROOT / "results/evaluation/osdi/expVD2" / ("_dryrun_vd2_results" if a.dry else "vd2_results")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".md").write_text("\n".join(L) + "\n"); out.with_suffix(".json").write_text(json.dumps({"combos": R, "H": H, "verdicts": V}, indent=1, default=str))
    print("\n".join(L[-9:]))


if __name__ == "__main__":
    main()
