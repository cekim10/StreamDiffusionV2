#!/usr/bin/env python3
"""XB shakedown check (harness only; not evidence; osdi/expXB/preregistration.md section 9).

For every run under results/evaluation/expXB_shk_*: valid under its rules (XB policies: xb_validity; OTTER, Full and
Wait-for-Sink: the W / R / N rules), not cut by max_run_s, the final edge served, and the delivery metrics computable
(TTFO-local, delivery gap, trajectory after the final edge's first chunk). Exactly one run per method and scenario is
expected (27). The verdict is PASS only if every expected run exists and passes.

    python tools/eval/check_xb_shakedown.py [--dry] [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from xb_delivery import delivery_metrics, load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

XB = ("precopy_full", "precopy_sink", "recompute_full", "recompute_win")
EXPECT = {"XB1_dog": 7, "XB1_bfly": 7, "XB2_dog": 3, "XB3_dog": 5, "XB4_dog": 5}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    from wrn_validity import run_validity_wrn
    pre = "_dryrun_" if a.dry else ""
    L = ["# XB shakedown check" + (" (DRY)" if a.dry else ""), "", "| scenario | policy | valid | stop | TTFO-local (s) | delivery gap (s) | remote chunks | first >= 35 dB idx | terminal PSNR | notes |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    bad, n_found = [], {}
    for sc, n in EXPECT.items():
        root = ROOT / "results/evaluation" / f"{pre}expXB_shk_{sc}"
        runs = sorted(d for d in root.glob("policy=*") if (d / "summary.json").exists())
        pols = {}
        for d in runs:
            s = json.load(open(d / "summary.json"))
            pols.setdefault(s["policy"], []).append((d, s))
        n_found[sc] = len(pols)
        if len(pols) != n:
            bad.append(f"{sc}: {len(pols)} methods with a run, expected {n}")
        for pol, lst in sorted(pols.items()):
            d, s = lst[-1]
            ok, why = (run_validity_xb(s, d, dry=a.dry) if pol in XB else run_validity_wrn(s, d, dry=a.dry))
            notes = list(why)
            try:
                S, m, ev = load_run(d)
                if pol not in XB:
                    S = {**S, "path": S.get("path") or S.get("edges")}
                D = delivery_metrics(S, m, ev)
                tt, gap, rc = D["ttfo_local_final_s"], D["delivery_gap_s"], D["remote_chunks"]
                tr = D["trajectory_final"]
                if tt is None:
                    notes.append("no TTFO-local (the final edge delivered nothing)")
            except Exception as exc:  # noqa: BLE001
                tt = gap = rc = None; tr = {}; notes.append(f"delivery metrics failed: {exc!r}")
            stop = (s.get("validation") or {}).get("stop_reason") or s.get("stop_reason")
            passed = ok and not any(x.startswith(("no TTFO", "delivery metrics")) for x in notes)
            if not passed:
                bad.append(f"{sc} {pol}: {'; '.join(notes) or 'invalid'}")
            f = lambda x, k=2: "-" if x is None else (f"{x:.{k}f}" if isinstance(x, float) else str(x))  # noqa: E731
            L.append(f"| {sc} | {pol} | {ok} | {stop} | {f(tt)} | {f(gap)} | {rc} | {f(tr.get('first_ge35_idx'))} | {f(tr.get('terminal_median_psnr'), 1)} | {'; '.join(notes) or '-'} |")
    verdict = "SHAKEDOWN PASS" if not bad else "SHAKEDOWN FAIL"
    L += ["", verdict] + [f"- {b}" for b in bad]
    print("\n".join(L))
    if a.write:
        (ROOT / "results/evaluation/osdi/expXB" / f"{pre}shakedown_check.md").write_text("\n".join(L) + "\n")
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
