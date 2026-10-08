#!/usr/bin/env python3
"""Phase 0 orchestration through per-host agents (no ssh). Run from any host that can reach the agents.

    python tools/eval/netcal_orchestrate.py --reps 5                       # patterns 1-5, 1 GiB per flow, MSS 1400
    python tools/eval/netcal_orchestrate.py --patterns 2 --reps 1 --mss 0 --timeout 120   # control: kernel MSS
    python tools/eval/netcal_orchestrate.py --hosts A=127.0.0.1:29901,B=127.0.0.1:29902,...   # local test

Patterns: 1 A->D, 2 A->B, 3 A->B & A->C, 4 A->D & B->D, 5 A->D & B->D & C->D.
Receivers are started first; senders target the receiving host's data IP. Every flow's JSON record is
pulled back through the agents into results/evaluation/network_calibration/<run>/<pattern>/rep<k>/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents import connect_all, parse_hosts, wait_all  # noqa: E402
from common import EVAL_ROOT, REPO_ROOT, git_commit  # noqa: E402

PATTERNS = {
    1: ("p1_A_to_D", [("A", "D")]),
    2: ("p2_A_to_B", [("A", "B")]),
    3: ("p3_A_to_B_and_C", [("A", "B"), ("A", "C")]),
    4: ("p4_A_B_to_D", [("A", "D"), ("B", "D")]),
    5: ("p5_A_B_C_to_D", [("A", "D"), ("B", "D"), ("C", "D")]),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hosts", type=str, default=None, help="A=host[:agent_port],...")
    ap.add_argument("--patterns", type=str, default="1 2 3 4 5")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--bytes", type=int, default=1 << 30)
    ap.add_argument("--mss", type=int, default=1400)
    ap.add_argument("--port", type=int, default=29800, help="data port for netcal receivers")
    ap.add_argument("--py", type=str, default=".venv/bin/python", help="python on the remote hosts (relative to repo root or absolute)")
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--iface", type=str, default=None)
    a = ap.parse_args()
    hosts = parse_hosts(a.hosts)
    pats = [int(x) for x in a.patterns.split()]
    labels = sorted({lb for p in pats for pair in PATTERNS[p][1] for lb in pair})
    agents = connect_all(hosts, labels)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run = f"mss={a.mss}_bytes={a.bytes}_{stamp}"
    local_root = EVAL_ROOT / "network_calibration" / run
    local_root.mkdir(parents=True, exist_ok=True)
    (local_root / "git_commit.txt").write_text(git_commit() + "\n")
    (local_root / "config.json").write_text(json.dumps({"hosts": hosts, "patterns": pats, "reps": a.reps, "bytes": a.bytes, "mss": a.mss, "port": a.port}, indent=1))
    rel_root = f"results/evaluation/network_calibration/{run}"
    for p in pats:
        name, pairs = PATTERNS[p]
        receivers = {}
        for s, d in pairs:
            receivers[d] = receivers.get(d, 0) + 1
        for rep in range(1, a.reps + 1):
            rel = f"{rel_root}/{name}/rep{rep}"
            print(f"[netcal] {name} rep {rep}: {' '.join(f'{s}->{d}' for s, d in pairs)}", flush=True)
            for lb in labels:
                agents[lb].mkdir(rel)
            rpids = []
            for d, nflows in receivers.items():
                cmd = [a.py, "tools/eval/netcal.py", "--role", "receiver", "--port", str(a.port + p), "--flows", str(nflows), "--mss", str(a.mss), "--tag", name, "--out", rel]
                if a.iface:
                    cmd += ["--iface", a.iface]
                rpids.append((agents[d], agents[d].run(cmd, f"{rel}/receiver_{d}.log")))
            time.sleep(2.0)
            spids = []
            for s, d in pairs:
                cmd = [a.py, "tools/eval/netcal.py", "--role", "sender", "--host", hosts[d][0], "--port", str(a.port + p), "--bytes", str(a.bytes), "--mss", str(a.mss), "--tag", name, "--out", rel]
                spids.append((agents[s], agents[s].run(cmd, f"{rel}/sender_{s}_to_{d}.log")))
            ok = wait_all(spids, a.timeout, f"{name} rep{rep} senders") & wait_all(rpids, a.timeout + 30, f"{name} rep{rep} receivers")
            # pull every record and log back
            (local_root / name / f"rep{rep}").mkdir(parents=True, exist_ok=True)
            for lb in labels:
                for path in agents[lb].glob(f"{rel}/*"):
                    try:
                        (local_root / name / f"rep{rep}" / Path(path).name).write_text(agents[lb].read(path))
                    except Exception as exc:  # noqa: BLE001
                        print(f"[netcal] could not read {lb}:{path}: {exc}", flush=True)
            if not ok:
                print(f"[netcal] {name} rep {rep}: FAILED or timed out (see logs under {local_root / name / f'rep{rep}'})", flush=True)
            time.sleep(1.0)
    print(f"[netcal] done -> {local_root}")
    import subprocess

    subprocess.run([sys.executable, str(REPO_ROOT / "tools/eval/aggregate_netcal.py"), "--root", str(EVAL_ROOT / "network_calibration")], check=False)


if __name__ == "__main__":
    main()
