#!/usr/bin/env python3
"""Watch GPU availability on the elves hosts through the agents (read-only nvidia-smi probes) and report
when the requested GPU has been idle for a number of consecutive polls. It never touches other users' jobs.

    python tools/eval/gpu_watch.py --hosts B                   # elves-02 GPU 0, poll every 60 s, idle = 3 polls
    python tools/eval/gpu_watch.py --hosts B,C,D --gpu 0 --interval 120 --idle_polls 5
    python tools/eval/gpu_watch.py --hosts B --once             # single status line per host
Exit code 0 when every watched host is idle (useful in a shell chain), 1 on --once with busy GPUs.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents import connect_all, parse_hosts  # noqa: E402

Q_GPU = ["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"]
Q_APPS = ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory,process_name", "--format=csv,noheader,nounits"]
Q_UUID = ["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"]


def probe(agent, gpu: int) -> dict:
    g = agent.exec(Q_GPU)["stdout"].strip().splitlines()
    rows = [[x.strip() for x in l.split(",")] for l in g if l.strip()]
    mine = next((r for r in rows if int(r[0]) == gpu), None)
    uuid = {int(l.split(",")[0]): l.split(",")[1].strip() for l in agent.exec(Q_UUID)["stdout"].strip().splitlines() if l.strip()}
    apps = [[x.strip() for x in l.split(",")] for l in agent.exec(Q_APPS)["stdout"].strip().splitlines() if l.strip()]
    apps_on_gpu = [a for a in apps if a and a[0] == uuid.get(gpu)]
    return {"found": mine is not None, "mem_used_mb": int(mine[1]) if mine else None, "mem_total_mb": int(mine[2]) if mine else None,
            "util_pct": int(mine[3]) if mine else None, "n_procs": len(apps_on_gpu), "procs": [(a[1], a[2]) for a in apps_on_gpu]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hosts", type=str, default="B", help="labels to watch, e.g. B or B,C,D")
    ap.add_argument("--host_map", type=str, default=None, help="A=host[:port],... overrides")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--idle_polls", type=int, default=3)
    ap.add_argument("--mem_idle_mb", type=int, default=600, help="memory.used below this (and no compute processes) counts as idle")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    labels = [x.strip() for x in a.hosts.split(",")]
    agents = connect_all(parse_hosts(a.host_map), labels)
    streak = {lb: 0 for lb in labels}
    while True:
        line = []
        for lb in labels:
            s = probe(agents[lb], a.gpu)
            idle = s["found"] and s["n_procs"] == 0 and (s["mem_used_mb"] or 0) < a.mem_idle_mb
            streak[lb] = streak[lb] + 1 if idle else 0
            line.append(f"{lb}:gpu{a.gpu} {'IDLE' if idle else 'busy'} mem {s['mem_used_mb']}/{s['mem_total_mb']} MB util {s['util_pct']}% procs {s['n_procs']} (idle polls {streak[lb]})")
        print(time.strftime("%H:%M:%S") + "  " + " | ".join(line), flush=True)
        all_idle = all(streak[lb] >= a.idle_polls for lb in labels)
        if a.once:
            sys.exit(0 if all(streak[lb] >= 1 for lb in labels) else 1)
        if all_idle:
            print(f"\a[gpu_watch] {','.join(labels)} gpu{a.gpu} idle for {a.idle_polls} consecutive polls", flush=True)
            sys.exit(0)
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
