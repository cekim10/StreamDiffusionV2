#!/usr/bin/env python3
"""Fig. 9 descriptive (not preregistered; existing runs only): where each step's B starts and its per-call PSNR over B's
first 24 calls (median over the 5 reps per call). Explains F9-H3: the steps start B at different calls, so "B's first 24
calls" cover different segments of the video.

    python tools/eval/fig9_early_psnr.py   # -> results/evaluation/osdi/fig9/early_psnr.json
"""

from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from fig9_report import EVAL, LABEL, OUT, STEPS, WORKLOADS, delivered_rows, step_of  # noqa: E402
from xb_delivery import load_run  # noqa: E402


def main():
    res = {}
    for w in WORKLOADS:
        per = {k: [] for k in STEPS}
        for exp in (f"expF9_{w}", f"expF7_{w}"):
            for d in sorted((EVAL / exp).glob("policy=*")):
                s, m, ev = load_run(d)
                k = step_of(d, s["policy"])
                if k not in STEPS or (exp.startswith("expF9") and k == "otter"):
                    continue
                rows = sorted((r for r in delivered_rows(s, m) if r["owner"] == "B" and r["psnr"] is not None), key=lambda r: r["call"])
                per[k].append({"rep": s.get("rep"), "first_b_call": rows[0]["call"], "psnr": [r["psnr"] for r in rows[:24]]})
        res[w] = {k: {"label": LABEL[k], "first_b_calls": sorted(x["first_b_call"] for x in rs),
                      "per_call_median": [st.median(x["psnr"][i] for x in rs) for i in range(24)],
                      "median_calls_1_8": st.median(v for x in rs for v in x["psnr"][:8]),
                      "median_calls_9_24": st.median(v for x in rs for v in x["psnr"][8:])} for k, rs in per.items()}
    (OUT / "early_psnr.json").write_text(json.dumps(res, indent=1))
    for w, c in res.items():
        for k, x in c.items():
            print(f"{w:4s} {x['label']:20s} first B call {x['first_b_calls']}  k1-8 {[round(v, 1) for v in x['per_call_median'][:8]]}  "
                  f"median k1-8 {x['median_calls_1_8']:.1f}  k9-24 {x['median_calls_9_24']:.1f}")


if __name__ == "__main__":
    main()
