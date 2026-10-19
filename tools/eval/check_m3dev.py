#!/usr/bin/env python3
"""M3-v2 GPU regression check on Experiment N cells 7-10 (results/evaluation/osdi/expN/m3v2_design.md section 6).
Development data: passing is a prerequisite for the freeze, never evidence. Writes osdi/expN/m3v2_gpu_regression.md.

    python tools/eval/check_m3dev.py            # results/evaluation/m3dev_cell{7..10}
    python tools/eval/check_m3dev.py --dry      # loopback dirs (_dryrun__m3v2_cell*), plumbing only
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
from wrn_validity import run_validity_wrn  # noqa: E402

LABEL = {7: "incorrect x 0", 8: "incorrect x src", 9: "incorrect x hold", 10: "incorrect x in"}


def load(pattern):
    out = {}
    for d in sorted(glob.glob(pattern)):
        p = Path(d)
        if (p / "summary.json").exists():
            s = json.load(open(p / "summary.json"))
            out[s["policy"]] = (p, s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--tag", default="", help="round tag used with run_wrn.py m3dev --tag")
    a = ap.parse_args()
    tag = f"_{a.tag}" if a.tag else ""
    rows, allok = [], True
    for cell in (7, 8, 9, 10):
        runs = load(str(ROOT / "results/evaluation" / (f"_dryrun__m3v2_cell{cell}" if a.dry else f"m3dev{tag}_cell{cell}") / "policy=*"))
        if not {"reuse_aware_in", "reuse_dyn2"} <= set(runs):
            rows.append((cell, False, f"runs present: {sorted(runs)}")); allok = False; continue
        am, v2 = runs["reuse_aware_in"][1], runs["reuse_dyn2"][1]
        v1 = runs.get("reuse_dyn", (None, None))[1]
        b = lambda s: s["latency_after_final_move_s"]["continuity_ready"]  # noqa: E731
        B = lambda s: s["d0"]["source_bytes_total_sinks"]  # noqa: E731
        rp = v2["d0"]["replans"]
        n_rp, n_probe = len(rp), sum(1 for r in rp if r.get("probe"))
        ok_valid, why = run_validity_wrn(v2, runs["reuse_dyn2"][0], dry=a.dry)
        trig = v2["wrn"].get("progress_trigger") or {}
        ok_trig = cell == 7 or (trig.get("t_rel") is not None and trig.get("verified_of_S_at_trigger", -1) >= math.ceil((trig.get("s_size") or 0) / 2))
        ok_rec = all(("I_est_mbps" in r and "c_est_mbps" in r and "probe" in r) for r in rp)
        if cell == 7:
            cond = n_rp == 0 and B(v2) <= B(am) + 0.02 and abs(b(v2) - b(am)) <= 1.0
        elif cell == 8:
            cond = n_rp == 0 and abs(b(v2) - b(am)) <= 1.0 and B(v2) <= B(am) + 0.02
        elif cell == 9:
            cond = n_rp <= 2 and b(v2) <= 0.5 * b(am) and (v2.get("bytes") or {}).get("duplicate", 0) == 0
        else:
            cond = n_rp <= 1 and B(v2) <= B(am) + 0.05 and abs(b(v2) - b(am)) <= 1.0
        ok = cond and ok_valid and ok_trig and ok_rec
        allok &= ok
        rows.append((cell, ok, f"v2: bind {b(v2):.2f} s, B_src {B(v2):.3f}, re-plans {n_rp} (probes {n_probe}), valid {ok_valid} {why}; "
                    f"at moves: bind {b(am):.2f}, B_src {B(am):.3f}; v1: " + (f"bind {b(v1):.2f}, B_src {B(v1):.3f}, re-plans {len(v1['d0']['replans'])}" if v1 else "-")
                    + f"; trigger ok {ok_trig}; records ok {ok_rec}; v2 re-plans: " + "; ".join(f"+{r['t_s'] - v2['t_final_move_rel_s']:.1f}s {r.get('from')}->{r['to']}{' probe' if r.get('probe') else ''} eta {r['eta_cur_s']:.1f}->{r['eta_new_s']:.1f} I {r.get('I_est_mbps', 0):.0f} c {({k: round(v) for k, v in (r.get('c_est_mbps') or {}).items() if k in 'AB'})}" for r in rp)))
    L = [f"# M3-v2 GPU regression on N cells 7-10 ({'LOOPBACK' if a.dry else 'GPU'}; development data, not evidence)", "", "| cell | pass | detail |", "|---|---|---|"]
    L += [f"| {c} {LABEL[c]} | {'PASS' if ok else '**FAIL**'} | {d} |" for c, ok, d in rows]
    L += ["", f"Overall: {'PASS' if allok else 'FAIL'}"]
    out = ROOT / "results/evaluation/osdi/expN" / (("_dryrun_" if a.dry else "") + f"m3v2_gpu_regression{tag}.md")
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()
