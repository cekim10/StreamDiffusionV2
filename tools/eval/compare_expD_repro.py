#!/usr/bin/env python3
"""EXEC_START reproduction of ExpD C / D (approved 2026-10-24): compare the frozen runs (expD_C, expD_D; untouched) with
the reproduction under the corrected code (expDR_C, expDR_D). Writes osdi/expD/expD_repro_report.md and .json.

Per run: validity (the frozen expD rules, unchanged), the source's chunks between the trigger and the move, the move
call, the chunk-boundary wait at the handoff, and the execution-event order (A:exec_start < A:first_output < move
request < A:exec_stop / handoff). Per configuration: medians of bind-ready, TTFO, x_dest / x_top, B_source, B_post,
B_fwd (the aggregator's record() definitions), original vs reproduced. G4 / G5 verdicts from aggregate_expD.py run on
each prefix (expD_results.json, expD_results_expDR.json).

    python tools/eval/aggregate_expD.py --prefix expDR && python tools/eval/compare_expD_repro.py
"""

from __future__ import annotations

import csv
import json
import statistics as st
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
EV = ROOT / "results/evaluation"
from aggregate_expD import record  # noqa: E402

KEYS = ("bind", "ttfo", "x_dest", "x_top", "src", "post", "fwd", "rejoin_calls")


def events_order(d: Path) -> dict:
    t = {}
    for r in csv.DictReader(open(d / "events.csv", newline="")):
        if r["event"] in ("A:exec_start", "A:first_output", "move", "A:exec_stop") and r["event"] not in t:
            t[r["event"]] = float(r["t_wall"])
    order_ok = ("A:exec_start" in t and "A:first_output" in t and "move" in t and t["A:exec_start"] <= t["A:first_output"] <= t["move"]
                and ("A:exec_stop" not in t or t["move"] <= t["A:exec_stop"]))
    return {"has": sorted(t), "order_ok": order_ok,
            "first_output_after_exec_start_s": (t["A:first_output"] - t["A:exec_start"]) if ("A:first_output" in t and "A:exec_start" in t) else None}


def runs(prefix: str, scen: str) -> list[dict]:
    out = []
    for d in sorted((EV / f"{prefix}_{scen}").glob("policy=*")) if (EV / f"{prefix}_{scen}").exists() else []:
        rec = record(d, scen, False)
        if not rec:
            continue
        s = json.load(open(d / "summary.json"))
        mv = (s.get("moves") or [{}])[0]
        rec.update({"run": d.name, "commit": (d / "git_commit.txt").read_text().split()[0][:7] if (d / "git_commit.txt").exists() else "?",
                    "source_chunks_before_move": (s.get("validation") or {}).get("source_chunks_before_move"),
                    "move_call": mv.get("call"), "wait_boundary_s": (mv.get("t_stop") - mv.get("t_req")) if (mv.get("t_stop") is not None and mv.get("t_req") is not None) else None,
                    "events": events_order(d)})
        if rec["source_chunks_before_move"] is None:   # frozen runs predate the field: count from metrics.csv
            n = 0
            for r in csv.DictReader(open(d / "metrics.csv", newline="")):
                if r["owner"] == "A" and r.get("t_out_rel") not in ("", None) and 0 <= float(r["t_out_rel"]) <= float(mv.get("t_req") or 0):
                    n += 1
            rec["source_chunks_before_move"] = n
        out.append(rec)
    return out


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def main():
    f = lambda x, n=3: "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))  # noqa: E731
    verd = {}
    for prefix in ("expD", "expDR"):
        p = ROOT / "results/evaluation/osdi/expD" / ("expD_results.json" if prefix == "expD" else "expD_results_expDR.json")
        if p.exists():
            verd[prefix] = {v["criterion"]: (v["verdict"], v["detail"]) for v in json.load(open(p))["verdicts"]}
    L = ["# ExpD C / D reproduction under the corrected EXEC_START code (2026-10-24)", "",
         "Frozen runs: `expD_C`, `expD_D` (commit 656dde6, source idle during the placement window). Reproduction: `expDR_C`, `expDR_D` "
         "(same configurations: `--pp_configs split:none,split:top1,reuse_dyn:top1,reuse_dyn:oracle`, lookahead 10 s, budget 1, 1 Gbps, trigger 30, 3 reps). "
         "Validity: the frozen expD rules, unchanged. Nothing in the frozen directories is modified.", ""]
    out = {}
    for scen in ("C", "D"):
        o, r = runs("expD", scen), runs("expDR", scen)
        out[scen] = {"orig": o, "repro": r}
        L += [f"## Scenario {scen}", "", f"Reproduction commits: {sorted({x['commit'] for x in r}) or 'none yet'}; runs {len(r)} (valid {sum(1 for x in r if x['valid'])}), "
              f"source chunks before the move: original {sorted({x['source_chunks_before_move'] for x in o})}, reproduction {sorted({x['source_chunks_before_move'] for x in r})}; "
              f"move call: original {sorted({x['move_call'] for x in o})}, reproduction {sorted({x['move_call'] for x in r})}; "
              f"event order ok in reproduction: {sum(1 for x in r if x['events']['order_ok'])} / {len(r)}; "
              f"boundary wait at the handoff: original median {f(med([x['wait_boundary_s'] for x in o]))} s, reproduction {f(med([x['wait_boundary_s'] for x in r]))} s", "",
              "| configuration | reps valid orig / repro | bind-ready s | TTFO s | x (dest / top) | B_source | B_post | B_fwd | rejoin calls |", "|---|---|---|---|---|---|---|---|---|"]
        labels = sorted({x["label"] for x in o} | {x["label"] for x in r})
        for lab in labels:
            vo = [x for x in o if x["label"] == lab and x["valid"]]; vr = [x for x in r if x["label"] == lab and x["valid"]]
            cell = lambda k: f"{f(med([x.get(k) for x in vo]))} -> {f(med([x.get(k) for x in vr]))}"  # noqa: E731
            xk = "x_dest" if scen == "C" else "x_top"
            L.append(f"| {lab} | {len(vo)} / {len(vr)} | {cell('bind')} | {cell('ttfo')} | {cell(xk)} | {cell('src')} | {cell('post')} | {cell('fwd')} | {cell('rejoin_calls')} |")
        L.append("")
    L += ["## Verdicts (frozen rules, applied to each set by aggregate_expD.py)", ""]
    for g in ("G4", "G5"):
        a_ = verd.get("expD", {}).get(g); b_ = verd.get("expDR", {}).get(g)
        L.append(f"- **{g}**: frozen {a_[0] if a_ else '-'} ({a_[1] if a_ else ''}); reproduction {b_[0] if b_ else 'not aggregated yet'} ({b_[1] if b_ else ''})"
                 + (" -> **CHANGED**" if (a_ and b_ and a_[0] != b_[0]) else ""))
    L += ["", "Changed conclusions, if any, are listed above; the frozen verdicts stay as recorded, and the choice of which set the paper cites is made after this report is reviewed."]
    (ROOT / "results/evaluation/osdi/expD/expD_repro_report.md").write_text("\n".join(L) + "\n")
    (ROOT / "results/evaluation/osdi/expD/expD_repro_report.json").write_text(json.dumps({"runs": out, "verdicts": verd}, indent=1, default=str))
    print("\n".join(L))


if __name__ == "__main__":
    main()
