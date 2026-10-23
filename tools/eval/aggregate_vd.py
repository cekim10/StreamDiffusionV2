#!/usr/bin/env python3
"""Experiment VD aggregation (osdi/expVD/preregistration.md sections 5-6). Effect sizes first, then verdicts.

Factorial cells per input (dog, butterfly) and schedule (OT-1, OT-L): S = sink slots zero / masked, D = VAE decoder
cache reset / kept, R = recent KV reset / kept. The (zero, reset, reset) cell is VC-1's frozen-M1 condition (OT-1 /
OT-L), read from the same unit. A main effect is the mean over the four cells with the factor on, against the mean over
the four with it off.

Outcomes per cell (from the unit's metrics.json and calls.csv):
- V1 at the reset;
- Sink-less window V4 (global color drift to REF) and E_O / E_R;
- first-4-call E_O / E_R after the reset;
- terminal PSNR (median of calls b + 90 .. b + 99) and the first call >= 35 dB.

    python tools/eval/aggregate_vd.py [--dry]      # -> results/evaluation/osdi/expVD/vd_results.{md,json}
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import rd_metrics as rm  # noqa: E402

INPUTS = ("dog", "butterfly-feeding-slow-motion")
H2_FACTOR = 0.5
H4_DB = 2.0


def cell_id(x: str, m: bool, d: bool, r: bool) -> str:
    if not (m or d or r):
        return f"OT-{x}"
    return f"VD{x}-{'mask' if m else 'zero'}-{'dec' if d else 'nodec'}-{'rec' if r else 'norec'}"


def outcomes(unit: Path, metrics: dict, cid: str) -> dict | None:
    cm = metrics["conditions"].get(cid)
    if cm is None:
        return None
    reset = next((e for e in cm["events"] if e["kind"] == "reset"), {})
    sl, f4 = cm["windows"].get("sinkless") or {}, cm["windows"].get("first_4") or {}
    psnr = {}
    p = unit / cid / "calls.csv"
    if p.exists():
        for r in csv.DictReader(open(p, newline="")):
            psnr[int(r["call"])] = float(r["psnr"]) if r["psnr"] not in ("", "None") else None
    tr = rm.trajectory(psnr, cm["b"]) if psnr else {}
    s = json.loads((unit / cid / "summary.json").read_text()) if (unit / cid / "summary.json").exists() else {}
    return {"v1_reset": reset.get("spike"), "sinkless_v4": sl.get("v4_window_to_ref"), "sinkless_E": sl.get("E_ratio"), "first4_E": f4.get("E_ratio"),
            "terminal_psnr": tr.get("T"), "cross_call": tr.get("cross_call"), "valid": s.get("valid"), "mask_violations": (s.get("vd") or {}).get("mask_violations")}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def main_effect(cells: dict, key: str, factor: int, ratio=False):
    on = [v[key] for k, v in cells.items() if k[factor] and v and v.get(key) is not None]
    off = [v[key] for k, v in cells.items() if not k[factor] and v and v.get(key) is not None]
    if len(on) < 4 or len(off) < 4:
        return None
    a, b = mean(on), mean(off)
    return (a / b) if ratio else (a - b)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--root", default=None)
    a = ap.parse_args()
    root = Path(a.root or ROOT / "results/evaluation" / ("_dryrun_expVC" if a.dry else "expVC"))
    res, L = {"combos": {}}, [f"# VD results{' (DRY RUN - synthetic, not a result)' if a.dry else ''}", ""]
    pre = ROOT / "results/evaluation/osdi/expVD/vd_precheck.json"
    if pre.exists() and not a.dry:
        P = json.loads(pre.read_text()); res["precheck"] = P
        mm, eq = P["mass_on_zero_sink_slots"], P["masked_kernel_equivalence"]
        L += ["## Precheck (mechanism, not visual)", "",
              f"- Softmax mass on the zero-filled sink slots ({P['input']}, calls {P['probed_calls']}): median {mm['median']:.4f}, max {mm['max']:.4f}; "
              f"{mm['blocks_with_median_ge_0.01']} of {mm['n_blocks']} blocks have a median >= 0.01.",
              f"- Masked kernel ({eq['kernel']}) vs SDPA with an explicit mask: max |diff| {eq['max_abs_diff']} over {eq['blocks']} blocks; sink region zero in every probed call: {P['sink_region_zero_all']}.", ""]
    rows = []
    H = {"VD-H1": [], "VD-H2": [], "VD-H3": [], "VD-H4": []}
    for inp in INPUTS:
        unit = root / f"{inp}_s0"
        if not (unit / "metrics.json").exists():
            continue
        M = json.loads((unit / "metrics.json").read_text())
        for x in ("1", "L"):
            cells = {(m, d, r): outcomes(unit, M, cell_id(x, m, d, r)) for m in (False, True) for d in (False, True) for r in (False, True)}
            enc = outcomes(unit, M, f"VD{x}-zero-encdec-norec")
            eff = {"S_sinkless_v4": main_effect(cells, "sinkless_v4", 0), "S_sinkless_E": main_effect(cells, "sinkless_E", 0),
                   "D_v1_ratio": main_effect(cells, "v1_reset", 1, ratio=True), "R_v1_ratio": main_effect(cells, "v1_reset", 2, ratio=True),
                   "R_first4_E": main_effect(cells, "first4_E", 2)}
            dr = {f"D{int(d)}R{int(r)}": mean([cells[(m, d, r)]["v1_reset"] for m in (False, True) if cells[(m, d, r)]]) for d in (False, True) for r in (False, True)}
            res["combos"][f"{inp}|OT-{x}"] = {"cells": {f"{'m' if k[0] else 'z'}{'D' if k[1] else 'd'}{'R' if k[2] else 'r'}": v for k, v in cells.items()},
                                              "encdec": enc, "main_effects": eff, "v1_DxR_mean_over_S": dr}
            H["VD-H1"].append(eff["S_sinkless_v4"] is not None and eff["S_sinkless_E"] is not None and eff["S_sinkless_v4"] < 0 and eff["S_sinkless_E"] < 0)
            H["VD-H2"].append(eff["D_v1_ratio"] is not None and eff["D_v1_ratio"] <= H2_FACTOR)
            H["VD-H3"].append(eff["R_v1_ratio"] is not None and eff["R_first4_E"] is not None and eff["R_v1_ratio"] < 1 and eff["R_first4_E"] < 0)
            if inp.startswith("butterfly"):
                full, ctrl = cells[(True, True, True)], cells[(False, False, False)]
                H["VD-H4"].append(bool(full and ctrl and full["terminal_psnr"] is not None and ctrl["terminal_psnr"] is not None
                                       and abs(full["terminal_psnr"] - ctrl["terminal_psnr"]) <= H4_DB))
            for k, v in cells.items():
                if v:
                    rows.append((inp, x, k, v))
            if enc:
                rows.append((inp, x, "encdec", enc))
    f = lambda v, n=3: "-" if v is None else (f"{v:.{n}f}" if isinstance(v, float) else str(v))  # noqa: E731
    L += ["## Main effects (effect sizes first)", "", "| input | schedule | S: sinkless V4 diff | S: sinkless E diff | D: V1 ratio | R: V1 ratio | R: first-4 E diff | V1 by D x R (mean over S) |",
          "|---|---|---|---|---|---|---|---|"]
    for key, C in res["combos"].items():
        inp, sc = key.split("|"); e = C["main_effects"]
        L.append(f"| {inp} | {sc} | {f(e['S_sinkless_v4'], 2)} | {f(e['S_sinkless_E'])} | {f(e['D_v1_ratio'])} | {f(e['R_v1_ratio'])} | {f(e['R_first4_E'])} | "
                 + ", ".join(f"{k} {f(v, 2)}" for k, v in C["v1_DxR_mean_over_S"].items()) + " |")
    verdict = lambda xs: ("NOT EVALUABLE" if not xs else ("SUPPORTED" if all(xs) else "NOT SUPPORTED"))  # noqa: E731
    L += ["", "## Verdicts (preregistered rules; every input and schedule must agree)", "",
          f"- VD-H1 (masking lowers Sink-less color drift and warp error): **{verdict(H['VD-H1'])}** {H['VD-H1']}",
          f"- VD-H2 (keeping the decoder cache lowers the reset spike by >= 2x): **{verdict(H['VD-H2'])}** {H['VD-H2']}",
          f"- VD-H3 (keeping recent KV lowers the reset spike and first-4 warp error): **{verdict(H['VD-H3'])}** {H['VD-H3']}",
          f"- VD-H4 (butterfly: masked + decoder + recent still within {H4_DB} dB of frozen M1's terminal PSNR): **{verdict(H['VD-H4'])}** {H['VD-H4']}",
          "- VD-H5 (D x R interaction on V1): descriptive, see the table.", "",
          "## Cells", "", "| input | schedule | cell (S D R) | valid | mask violations | V1 reset | Sink-less V4 | Sink-less E | first-4 E | terminal PSNR | first >= 35 dB |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for inp, x, k, v in rows:
        name = k if isinstance(k, str) else f"{'mask' if k[0] else 'zero'} {'dec' if k[1] else '-'} {'rec' if k[2] else '-'}"
        L.append(f"| {inp} | OT-{x} | {name} | {v['valid']} | {v['mask_violations']} | {f(v['v1_reset'], 2)} | {f(v['sinkless_v4'], 2)} | {f(v['sinkless_E'])} | {f(v['first4_E'])} | {f(v['terminal_psnr'], 1)} | {v['cross_call']} |")
    res["verdicts"] = {k: verdict(v) for k, v in H.items()}
    out = ROOT / "results/evaluation/osdi/expVD" / ("_dryrun_vd_results" if a.dry else "vd_results")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".md").write_text("\n".join(L) + "\n"); out.with_suffix(".json").write_text(json.dumps(res, indent=1, default=str))
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
