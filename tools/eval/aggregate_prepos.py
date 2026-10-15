#!/usr/bin/env python3
"""Aggregate Experiment A (pre-positioning) runs under results/evaluation/<experiment>/policy=*_pp=* and compare them
with the fluid model run at each configuration's own caps. Writes summary.csv (per run), summary_by_config.csv
(medians per pre-positioning policy x true destination), criteria.md (pilot go/no-go: T_r and verified bytes within
1 s / 0.05 Sink of the model; forwarding by non-owner holders exercised in every incorrect-prediction run that had
pre-positioned bytes; source bytes never above 1 Sink + one fragment per candidate flow).

    python tools/eval/aggregate_prepos.py --experiment restore_prepos_pilot
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
import restore_model as rm  # noqa: E402

CTRL = 0.3   # control-plane seconds added to model T_r (TOPOLOGY_PLAN D)


def load(root: Path):
    runs, incomplete = [], []
    for d in sorted(root.glob("policy=*")):
        if not (d / "summary.json").exists():
            incomplete.append(d.name); continue
        s = json.load(open(d / "summary.json")); s["dir"] = d.name
        if s.get("prepos"):
            runs.append(s)
    return runs, incomplete


def model_tr(s):
    """Fluid-model T_r and verified-at-move allocation for this run's configuration (its caps, Sink size, probs)."""
    pp = s["prepos"]
    caps = {}
    for k, v in s["caps_mbps"].items():
        node, d = k.split(":"); caps[(d, node)] = v * 1e6
    rm.SINK_BYTES = s["sink_bytes"]; rm.FLEN = s["frag_bytes"]; rm.NFR = -(-s["sink_bytes"] // s["frag_bytes"])
    m = rm.Model(s["policy"], s["N"], 1, s["tm_s"], caps, prepos={"policy": pp["policy"], "probs": pp["probs"], "L": pp["L"], "b": pp["b"],
                                                                 "dest": pp["dest"], "tau": pp["tau"]})
    r = m.run(horizon=pp["L"] + 4 * s["N"] * s["sink_bytes"] * 8 / caps[("in", "B")] + 30)
    return (None if r["t_r"] is None else r["t_r"] + CTRL), r["alloc"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="restore_prepos_pilot")
    ap.add_argument("--allow_loopback", action="store_true")
    a = ap.parse_args()
    root = ROOT / "results/evaluation" / a.experiment
    runs, incomplete = load(root)
    skip = {"four_hosts_distinct"} if a.allow_loopback else set()
    invalid = [r["dir"] for r in runs if not all(v for k, v in r["validation"].items() if k not in skip)]
    S = runs[0]["sink_bytes"]
    rows = []
    for r in runs:
        pp = r["prepos"]; mt, alloc = model_tr(r)
        rows.append({"run": r["dir"], "prepos": pp["policy"], "dest": pp["dest"], "correct": pp["correct"], "draw": pp["draw"], "rep": r["rep"],
                     "L_s": pp["L"], "budget_sinks": pp["b"], "t_r_s": pp["t_r_s"], "model_t_r_s": mt,
                     "verified_at_move": {c: round(v, 3) for c, v in pp["verified_at_move_sinks"].items()},
                     "model_alloc": {c: round(v, 3) for c, v in alloc.items()},
                     "at_chosen": pp["at_chosen_sinks"], "at_nonchosen": pp["at_nonchosen_sinks"],
                     "post_move_source": pp["post_move_source_sinks"], "fwd_nonowner": pp["forwarded_by_nonowner_holders_sinks"],
                     "source_total": r["normalized"]["source_per_session"], "total": r["normalized"]["total_per_session"],
                     "valid": r["dir"] not in invalid})
    with open(root / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
        for x in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in x.items()})
    G = defaultdict(list)
    for x in rows:
        if x["valid"]:
            G[(x["prepos"], x["dest"])].append(x)
    cfg = []
    for (p, d), xs in sorted(G.items()):
        cfg.append({"prepos": p, "dest": d, "n": len(xs), "t_r_median": st.median(x["t_r_s"] for x in xs), "model_t_r": xs[0]["model_t_r_s"],
                    "at_chosen": st.median(x["at_chosen"] for x in xs), "at_nonchosen": st.median(x["at_nonchosen"] for x in xs),
                    "fwd_nonowner": st.median(x["fwd_nonowner"] for x in xs), "post_move_source": st.median(x["post_move_source"] for x in xs),
                    "source_total": st.median(x["source_total"] for x in xs), "total": st.median(x["total"] for x in xs)})
    with open(root / "summary_by_config.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cfg[0].keys())); w.writeheader(); w.writerows(cfg)
    f = lambda v, d=2: "-" if v is None else f"{v:.{d}f}"  # noqa: E731
    out = [f"# Experiment A pilot checks ({a.experiment})", "",
           f"Valid runs {len(runs) - len(invalid)}/{len(runs)}; invalid: {invalid or 'none'}; incomplete: {incomplete or 'none'}", "",
           "## Per run: T_r (move -> all fragments verified at the destination) vs the fluid model at the run's caps", "",
           "| prepos | dest | correct | T_r s | model s | d | verified at move (Sinks) | model alloc | at chosen | at non-chosen | fwd by non-owner holders | post-move source | source total | total |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    fails = []
    for x in rows:
        d = None if x["t_r_s"] is None or x["model_t_r_s"] is None else x["t_r_s"] - x["model_t_r_s"]
        va = " ".join(f"{c}:{v:.2f}" for c, v in x["verified_at_move"].items()); ma = " ".join(f"{c}:{v:.2f}" for c, v in x["model_alloc"].items())
        out.append(f"| {x['prepos']} | {x['dest']} | {x['correct']} | {f(x['t_r_s'])} | {f(x['model_t_r_s'])} | {'-' if d is None else f'{d:+.2f}'} | {va} | {ma} | "
                   f"{f(x['at_chosen'])} | {f(x['at_nonchosen'])} | {f(x['fwd_nonowner'])} | {f(x['post_move_source'])} | {f(x['source_total'])} | {f(x['total'])} |")
        # go/no-go checks (TOPOLOGY_PLAN G step 2)
        if d is None or abs(d) > 1.0:
            fails.append((x["run"], f"T_r off model by {d}"))
        for c, v in x["verified_at_move"].items():
            if abs(v - x["model_alloc"][c]) > 0.05:
                fails.append((x["run"], f"verified at {c} {v:.3f} vs model {x['model_alloc'][c]:.3f}"))
        if x["at_nonchosen"] > 0.02 and x["fwd_nonowner"] < 0.5 * x["at_nonchosen"]:
            fails.append((x["run"], f"non-chosen holders forwarded only {x['fwd_nonowner']:.2f} of {x['at_nonchosen']:.2f} Sink"))
        if x["source_total"] > 1.0 + 3 * runs[0]["frag_bytes"] / S + 0.01:
            fails.append((x["run"], f"source total {x['source_total']:.3f} > 1 Sink"))
    out += ["", "## Go/no-go (pre-registered: T_r and per-candidate verified bytes within 1 s / 0.05 Sink of the model; non-chosen holders forward; source <= 1 Sink)", ""]
    out += [f"- FAIL {r}: {m}" for r, m in fails] or ["- all checks pass: GO"]
    (root / "criteria.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
