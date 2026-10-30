#!/usr/bin/env python3
"""Run the Fig. 5 Sink characterization (run_sink_char.sh) on elves-02..04 through the experiment agents (port 29900),
since ssh between the testbed hosts is not available. Run on elves-01; shard 0 runs on elves-01 itself.

    start    launch shard 1 / 2 / 3 of 4 on B / C / D (GPU 0); pids saved to results/evaluation/osdi/sinkchar/_remote_pids.json
    status   running / exit code and the last log lines of each shard
    fetch    copy every events_*.json from B / C / D into results/evaluation/osdi/sinkchar/ (never overwrites a differing file)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d0_remote import agents  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = "results/evaluation/osdi/sinkchar"
PIDS = ROOT / OUT / "_remote_pids.json"
SHARD = {"B": 1, "C": 2, "D": 3}


def log_of(lb: str) -> str:
    return f"{OUT}/_logs/shard{SHARD[lb]}_{lb}.log"


def start(a):
    pids = json.loads(PIDS.read_text()) if PIDS.exists() else {}
    for lb, ag in agents(tuple(SHARD), a.agent_hosts).items():
        py = ag.ping()["python"]
        pid = ag.run(["bash", "tools/eval/run_sink_char.sh", str(SHARD[lb]), "4"], log=log_of(lb), env={"PY": py})
        pids[lb] = pid
        print(f"{lb}: shard {SHARD[lb]} started, pid {pid}, PY {py}, log {log_of(lb)}")
    PIDS.parent.mkdir(parents=True, exist_ok=True)
    PIDS.write_text(json.dumps(pids))


def status(a):
    pids = json.loads(PIDS.read_text()) if PIDS.exists() else {}
    for lb, ag in agents(tuple(SHARD), a.agent_hosts).items():
        st = ag.poll(pids[lb]) if lb in pids else {"running": None, "rc": None}
        try:
            tail = [ln for ln in ag.read(log_of(lb)).splitlines() if ln.startswith("[SINKCHAR]")]
        except Exception as exc:  # noqa: BLE001
            tail = [f"(no log: {exc})"]
        done = len(ag.glob(f"{OUT}/events_*.json"))
        print(f"{lb} shard {SHARD[lb]}: {'running' if st['running'] else 'finished rc=' + str(st['rc'])} | events files {done} | "
              + " / ".join(tail[-3:]))


def fetch(a):
    for lb, ag in agents(tuple(SHARD), a.agent_hosts).items():
        new = same = diff = 0
        for rel in ag.glob(f"{OUT}/events_*.json"):
            txt, dst = ag.read(rel), ROOT / rel
            if dst.exists():
                if dst.read_text() == txt:
                    same += 1
                else:
                    diff += 1; print(f"  {lb}: {rel} differs from the local copy; left untouched")
                continue
            dst.write_text(txt); new += 1
        print(f"{lb}: copied {new}, identical {same}, differing {diff}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent_hosts", default=None)
    ap.add_argument("cmd", choices=["start", "status", "fetch"])
    a = ap.parse_args()
    {"start": start, "status": status, "fetch": fetch}[a.cmd](a)


if __name__ == "__main__":
    main()
