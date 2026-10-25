#!/usr/bin/env python3
"""Frozen vs provenance-corrected W / R / N aggregate (osdi/audi_s0_w2_provenance.md): every differing field of
wrn_results.json, every changed w2_table row, and the counts the paper cites (crossing, sustained, crossing but never
sustained, last-10 median < 35 dB). Run after `aggregate_wrn.py --corrected`.

    python tools/eval/diff_wrn_corrected.py      # -> results/evaluation/osdi/expW/audi_s0_corrected_aggregate.md
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
O = ROOT / "results/evaluation/osdi"


def walk(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            yield from walk(a.get(k), b.get(k), f"{path}/{k}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            yield from walk(x, y, f"{path}[{i}]")
    elif a != b:
        yield path, a, b


def counts(t):
    none = lambda v: v in ("", "None")  # noqa: E731
    cross = [r for r in t if r["rejoin"] == "True"]
    return {"units": len(t), "crossing": len(cross), "sustained": sum(1 for r in t if not none(r["sustained_calls"])),
            "crossing_never_sustained": sum(1 for r in cross if none(r["sustained_calls"])),
            "last10_median_below_35": sum(1 for r in t if not none(r["psnr_median_last10"]) and float(r["psnr_median_last10"]) < 35),
            "crossing_and_last10_below_35 (the paper's '9 units')": sum(1 for r in cross if not none(r["psnr_median_last10"]) and float(r["psnr_median_last10"]) < 35)}


def verdicts(d, prefix=""):
    out = {}
    for k, v in (d.items() if isinstance(d, dict) else []):
        if isinstance(v, str) and any(w in v for w in ("SUPPORTED", "NOT EVALUABLE", "GO")):
            out[prefix + k] = v
        elif isinstance(v, dict):
            if isinstance(v.get("verdict"), str):
                out[prefix + k] = v["verdict"]
            out.update(verdicts(v, prefix + k + "/"))
    return out


def main():
    F, C = json.load(open(O / "wrn_results.json")), json.load(open(O / "corrected_wrn_results.json"))
    ft, ct = list(csv.DictReader(open(O / "w2_table.csv"))), list(csv.DictReader(open(O / "corrected_w2_table.csv")))
    diffs = list(walk(F, C))
    vf, vc = verdicts(F), verdicts(C)
    vch = [k for k in sorted(set(vf) | set(vc)) if vf.get(k) != vc.get(k)]
    L = ["# W / R / N aggregate: frozen vs provenance-corrected (audi-snow-trail seed-0 OTTER run = verified reproduction)", "",
         "Frozen outputs (`wrn_results.*`, `w2_table.csv`) are unchanged; the corrected set is `corrected_wrn_results.*`, `corrected_w2_table.csv` "
         "(`aggregate_wrn.py --corrected`). No figure script reads W / R / N outputs.", "",
         f"- Verdicts compared: {len(vf)} (W, R, N, V, A); **changed: {vch or 'none'}**",
         f"- Differing result fields: {len(diffs)}"] + [f"  - `{p}`: {a} -> {b}" for p, a, b in diffs]
    L += ["", "## Changed W2 unit rows", ""]
    for a, b in zip(ft, ct):
        ch = {k: (a[k], b[k]) for k in a if a[k] != b[k] and k != "rvc_events"}
        if ch or a.get("rvc_events") != b.get("rvc_events"):
            L.append(f"- {a['workload']} seed {a['seed']}: " + "; ".join(f"{k} {x} -> {y}" for k, (x, y) in ch.items())
                     + (f"; RVC events {len(json.loads(a['rvc_events'] or 'null') or [])} -> {len(json.loads(b['rvc_events'] or 'null') or [])}" if a.get("rvc_events") != b.get("rvc_events") else ""))
    cf, cc = counts(ft), counts(ct)
    L += ["", "## Counts cited in the paper (computed the same way on both sets)", "", "| count | frozen | corrected |", "|---|---|---|"]
    L += [f"| {k} | {cf[k]} | {cc[k]} |" for k in cf]
    L += ["", f"**Aggregate conclusions changed: {'yes - ' + ', '.join(vch) if vch else 'no'}.**"]
    (O / "expW" / "audi_s0_corrected_aggregate.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
