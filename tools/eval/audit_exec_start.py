#!/usr/bin/env python3
"""EXEC_START impact audit (2026-10-23; read-only: no frozen log or result is modified).

EXEC_START tells the source node A, after SOURCE_PREP, to start generating. The orchestrator calls it in three places:
placement lookahead (`prepos`: the source should keep generating for L seconds while it places fragments), cold
destination (`cold_destination`: the source should keep generating while the destination process boots), and XB's
execute_xb (fixed in 0b034dd with `source_bound`). Static cause: A's run state after SOURCE_PREP is "Sink verified,
not bound", so the first loop iteration of _generate calls _unpack_sink -> GpuRuntime.unpack ->
unpack_into_snapshot(snap=None) (A was never provisioned as a receiver) -> TypeError in a daemon thread.

Per run (every non-dry run directory with a summary.json), from independent records:
- the orchestrator's delivered-chunk log (metrics.csv): chunks from A at or after t0;
- node events relayed into events.csv: A:exec_start (the call was made), A:first_output (A produced output);
- the move call versus the trigger call (a generating source advances about L / 0.56 s calls before the move);
- t_move - t0 (the window length).
Also a related design property (not the bug): the source's chunk-boundary wait at each OTTER handoff,
moves[i].t_stop - t_req, first move versus later moves.

    python tools/eval/audit_exec_start.py     # -> results/evaluation/osdi/exec_start_audit.{md,json}
"""

from __future__ import annotations

import csv
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "results/evaluation"
XB = ("precopy_full", "precopy_sink", "recompute_full", "recompute_win")
FIX_COMMIT = "0b034dd"


def commit_of(d: Path) -> str:
    try:
        return (d / "git_commit.txt").read_text().split()[0][:7]
    except (OSError, IndexError):
        return "?"


def ancestors_of_fix() -> set:
    import subprocess
    out = subprocess.run(["git", "rev-list", f"{FIX_COMMIT}^"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    return {c[:7] for c in out}


def path_of(name: str, s: dict, commit: str, before_fix: set) -> str | None:
    if s.get("policy") in XB or s.get("policy") == "split_wait":
        if s.get("policy") in XB:
            return "xb_before_fix" if commit in before_fix else "xb_fixed"
        return None
    if "_pp=" in name or s.get("prepos"):
        return "placement_window"
    if "colddest" in name or s.get("cold_destination"):
        return "cold_destination"
    return None


def main():
    before_fix = ancestors_of_fix()
    rows, waits = [], defaultdict(list)
    for d in sorted(EV.glob("*/policy=*")):
        if d.parent.name.startswith("_dryrun_") or not (d / "summary.json").exists():
            continue
        try:
            s = json.load(open(d / "summary.json"))
        except ValueError:
            continue
        commit = commit_of(d)
        p = path_of(d.name, s, commit, before_fix)
        # related design property: chunk-boundary wait at OTTER handoffs (all OTTER-style runs with moves)
        if s.get("policy") in ("reuse_dyn2", "reuse_dyn", "split", "restart", "reuse_aware_in") and isinstance(s.get("moves"), list):
            for mv in s["moves"]:
                if mv.get("t_stop") is not None and mv.get("t_req") is not None:
                    waits["first" if mv.get("i", 1) == 1 else "later"].append(float(mv["t_stop"]) - float(mv["t_req"]))
        if p is None:
            continue
        if p == "placement_window" and not (d / "metrics.csv").exists():
            p = "network_only_harness"   # restore_* (restore_node.py): fragment transport only, no model generation; not applicable
        a_chunks, a_calls = 0, []
        try:
            for r in csv.DictReader(open(d / "metrics.csv", newline="")):
                if r["owner"] == "A" and r.get("t_out_rel") not in (None, "") and float(r["t_out_rel"]) >= 0 and r.get("missing") not in ("True", "true"):
                    a_chunks += 1; a_calls.append(int(r["call"]))
        except OSError:
            pass
        ev = {"exec_start": False, "first_output_A": False}
        try:
            for r in csv.DictReader(open(d / "events.csv", newline="")):
                if r["event"] == "A:exec_start":
                    ev["exec_start"] = True
                elif r["event"] == "A:first_output":
                    ev["first_output_A"] = True
        except OSError:
            pass
        mv0 = s["moves"][0] if isinstance(s.get("moves"), list) and s["moves"] else {}
        pp = s.get("prepos") or {}
        trig = s.get("migration_chunk")
        if trig is None and (d / "config.json").exists():
            try:
                cfg = json.load(open(d / "config.json"))
                trig = (cfg.get("args") or {}).get("migration_chunk", cfg.get("migration_chunk"))
            except (ValueError, AttributeError):
                trig = None
        rows.append({"experiment": d.parent.name, "run": d.name, "path": p, "commit": commit, "policy": s.get("policy"),
                     "exec_start_event": ev["exec_start"], "A_first_output_event": ev["first_output_A"], "A_chunks_after_t0": a_chunks,
                     "A_calls": [min(a_calls), max(a_calls)] if a_calls else None, "trigger_call": trig, "move_call": mv0.get("call"),
                     "window_s": pp.get("L") if isinstance(pp, dict) else None})
    by = defaultdict(list)
    for r in rows:
        by[(r["experiment"], r["path"])].append(r)
    L = ["# EXEC_START impact audit - execution evidence (2026-10-23)", "",
         "Read-only scan of every non-dry run directory. 'A chunks' = chunks the source delivered at or after the trigger (orchestrator metrics log).",
         "A generating source advances about L / 0.56 s calls before the move; a dead one leaves the move at the trigger call.", "",
         "| experiment | path | runs | exec_start event | A first_output event | runs with 0 A chunks | move call == trigger call | window L (s) |",
         "|---|---|---|---|---|---|---|---|"]
    for (exp, p), rs in sorted(by.items()):
        same = sum(1 for r in rs if r["move_call"] is not None and r["trigger_call"] is not None and int(r["move_call"]) == int(r["trigger_call"]))
        Ls = sorted({r["window_s"] for r in rs if r["window_s"] is not None})
        L.append(f"| {exp} | {p} | {len(rs)} | {sum(r['exec_start_event'] for r in rs)} | {sum(r['A_first_output_event'] for r in rs)} | "
                 f"{sum(1 for r in rs if r['A_chunks_after_t0'] == 0)} | {same} | {Ls or '-'} |")
    aff = [r for r in rows if r["path"] in ("placement_window", "cold_destination", "xb_before_fix")]
    na = [r for r in rows if r["path"] == "network_only_harness"]
    fixed = [r for r in rows if r["path"] == "xb_fixed"]
    L += ["", f"Affected paths: {len(aff)} runs; source delivered 0 chunks after the trigger in {sum(1 for r in aff if r['A_chunks_after_t0'] == 0)}.",
          f"Not applicable (network-only harness, no model generation): {len(na)} runs ({', '.join(sorted({r['experiment'] for r in na}))}).",
          f"XB after the fix ({FIX_COMMIT}): {len(fixed)} runs; source delivered chunks in {sum(1 for r in fixed if r['A_chunks_after_t0'] > 0)} "
          f"(pre-copy / recompute keep the source generating; R-win stops it within ~1-2 chunks).", "",
          "## Related design property (not the bug): chunk-boundary wait at OTTER handoffs", "",
          "A handoff waits for the generating owner to finish its current chunk. At the first move the source has just finished SOURCE_PREP and is idle at a boundary.",
          "At later moves the owner is generating. Values are moves[i].t_stop - t_req over every OTTER-style run with moves:", ""]
    for k in ("first", "later"):
        v = waits[k]
        if v:
            L.append(f"- {k} moves: n = {len(v)}, median {st.median(v):.3f} s, P90 {sorted(v)[int(0.9 * (len(v) - 1))]:.3f} s, max {max(v):.3f} s")
    out = ROOT / "results/evaluation/osdi/exec_start_audit"
    out.with_suffix(".md").write_text("\n".join(L) + "\n")
    out.with_suffix(".json").write_text(json.dumps({"rows": rows, "boundary_wait_s": {k: v for k, v in waits.items()}}, indent=1))
    print("\n".join(L))


if __name__ == "__main__":
    main()
