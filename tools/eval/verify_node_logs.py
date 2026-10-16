#!/usr/bin/env python3
"""Verify recovered per-fragment node logs (results/evaluation/restore_*/<run>/node_{B,C,D}/fragments.csv) against the
run's committed summary, without modifying anything:

    - every recovered file parses and its `recv` rows name this node as `dst`;
    - bytes received at node X (every recv row, verified or not) are <= the bytes the orchestrator recorded as sent on
      links into X (summary bytes.by_link), and the shortfall is at most one fragment per flow into X (fragments in
      flight when a flow was cancelled). Every receipt counts: a policy may send the same fragment to the same node more
      than once (restart under continuous mobility revisits B, C, D and resends the Sink from the start; the node had
      dropped the session, so those repeats are logged ok=True). First version (2026-10-16) counted only the first verified arrival per fragment and
      flagged exactly those runs; distinct verified bytes are still reported.
    - per-run coverage: which of B, C, D logs are present.

Writes results/evaluation/osdi/d0/node_log_recovery.md; exits non-zero if any present file fails.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "results/evaluation"


def main():
    exps = defaultdict(lambda: {"runs": 0, "complete": 0, "files": 0, "fail": 0, "distinct": 0, "repeat": 0})
    fails = []
    for run in sorted(list(EV.glob("restore_*/policy=*")) + list(EV.glob("restore_*/plan=*"))):
        if not (run / "summary.json").exists():
            continue
        exp = run.parent.name
        s = json.load(open(run / "summary.json"))
        by_link = s["bytes"]["by_link"]
        flows = list(csv.DictReader(open(run / "flows.csv"))) if (run / "flows.csv").exists() else []
        frag = s.get("frag_bytes", 4 << 20)
        e = exps[exp]; e["runs"] += 1
        present = 0
        for X in ("B", "C", "D"):
            f = run / f"node_{X}" / "fragments.csv"
            if not f.exists():
                continue
            present += 1; e["files"] += 1
            try:
                rows = [r for r in csv.DictReader(open(f)) if r["event"] == "recv"]
            except Exception as exc:  # noqa: BLE001
                fails.append((run.name, X, f"unreadable: {exc}")); e["fail"] += 1; continue
            if any(r["dst"] != X for r in rows):
                fails.append((run.name, X, "recv rows with another destination")); e["fail"] += 1; continue
            seen = set(); got = sum(int(r["bytes"]) for r in rows)
            for r in rows:
                key = (r["session"], r["fragment_id"])
                if r["ok"] == "True" and key not in seen:
                    seen.add(key); e["distinct"] += int(r["bytes"])
            e["repeat"] += sum(1 for r in rows if r["ok"] != "True")
            sent = sum(v for k, v in by_link.items() if k.endswith("->" + X))
            nflows = sum(1 for fl in flows if fl["dst"] == X)
            if got > sent or sent - got > max(1, nflows) * frag:
                fails.append((run.name, X, f"received {got} vs sent {sent} bytes over {nflows} flows")); e["fail"] += 1
        e["complete"] += present == 3
    out = ["# D0: recovered per-fragment node logs", "",
           "Read-only check of `node_{B,C,D}/fragments.csv` copied back from elves-02..04 (`tools/eval/recover_node_logs.sh`).", "",
           "| experiment | runs | runs with B, C and D logs | files | failing files | distinct verified GiB | repeat or rejected receipts |", "|---|---|---|---|---|---|---|"]
    out += [f"| {k} | {v['runs']} | {v['complete']} | {v['files']} | {v['fail']} | {v['distinct'] / 2**30:.1f} | {v['repeat']} |" for k, v in sorted(exps.items())]
    out += ["", f"Failures: {len(fails)}"] + [f"- {r} node {x}: {m}" for r, x, m in fails[:50]]
    p = EV / "osdi/d0/node_log_recovery.md"; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("\n".join(out) + "\n")
    print("\n".join(out))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
