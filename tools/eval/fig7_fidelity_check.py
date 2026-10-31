#!/usr/bin/env python3
"""Fig. 7 butterfly fidelity check (existing logs only, no new runs): does an OTTER run's Sink refresh / realignment
schedule after the cutover follow the uninterrupted reference, and does that separate the low-terminal-PSNR runs?

Per run: B's first generation call (cutover), the calls at which the Sink slot positions (`sink_slot_pos`, metrics.csv)
differ from the Full rep 1 run of the same workload (bit-exact to the uninterrupted reference on every call), the
schedule of slot changes on both sides, and the PSNR summary (first call, min / median over 24 calls, terminal median of
the last 10 calls).

    python tools/eval/fig7_fidelity_check.py     # -> results/evaluation/osdi/fig7/fidelity_check.json
"""

from __future__ import annotations

import csv
import glob
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "results/evaluation"


def load(d):
    return {int(x["call"]): x for x in csv.DictReader(open(Path(d) / "metrics.csv"))}


def changes(rows, calls):
    out, prev = [], None
    for c in calls:
        p = rows[c]["sink_slot_pos"]
        if p != prev:
            out.append([c, json.loads(p)])
            prev = p
    return out


def main():
    rec = {}
    for w in ("dog", "bfly"):
        ref = load(sorted(glob.glob(str(EVAL / f"expF7_{w}/policy=full_*rep=1_*")))[0])
        assert all(float(r["psnr"]) == 99.0 for r in ref.values())   # Full rep 1 is bit-exact to the reference
        for d in sorted(glob.glob(str(EVAL / f"expF7_{w}/policy=precopy_replay*"))):
            R = load(d)
            rep = int(d.split("rep=")[1].split("_")[0])
            b = sorted(c for c in R if R[c]["owner"] == "B")
            common = [c for c in b if c in ref]
            diff = [c for c in common if R[c]["sink_slot_pos"] != ref[c]["sink_slot_pos"]]
            ps = [float(R[c]["psnr"]) for c in b]
            ev = list(csv.DictReader(open(Path(d) / "events.csv")))
            log_calls = next(json.loads(e["detail"])["log_calls"] for e in ev if e["event"] == "A:xb_precopy_switch")
            rec[f"{w}_rep{rep}"] = dict(
                log_calls=log_calls, b_first_call=b[0], slot_pos_differs_calls=len(diff), first_differing_call=diff[0] if diff else None,
                b_schedule=changes(R, b), ref_schedule=changes(ref, common),
                psnr_first=ps[0], psnr_min24=min(ps[:24]), psnr_med24=st.median(ps[:24]), psnr_terminal=st.median(ps[-10:]))
            r = rec[f"{w}_rep{rep}"]
            print(f"{w} rep {rep}: log {log_calls} calls, B from call {b[0]}, slot positions differ from the reference on "
                  f"{len(diff)} calls{f' from call {diff[0]}' if diff else ''}; PSNR first {ps[0]:.1f}, terminal {r['psnr_terminal']:.1f}")
            if diff:
                print(f"   B   schedule {r['b_schedule']}\n   ref schedule {r['ref_schedule']}")
    out = EVAL / "osdi/fig7/fidelity_check.json"
    json.dump(rec, open(out, "w"), indent=1)
    print(f"-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
