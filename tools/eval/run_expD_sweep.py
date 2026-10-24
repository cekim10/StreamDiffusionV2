#!/usr/bin/env python3
"""Experiment D sweep driver (preregistration v3 section 9): every in-repo configuration, 3 reps, on elves-01..04 GPU 0.
External C/R is not run (blocked on this testbed). Do not start without explicit approval.

Each step is one orchestrator invocation (the nodes start once per invocation: ~4 min of model load + baseline) with
--skip_done, so a re-start resumes: a configuration + rep with a valid run (tools/eval/expD_validity.py) is skipped and
an invalid or missing one is (re-)run. Before every invocation GPU 0 must be idle on all four hosts and the four repos
on one commit (tools/eval/d0_remote.py gpu_idle), waiting up to --wait_s. Afterwards run the aggregator; if it lists
scenario A configurations with IQR > 10 % of the median, `--extra` runs their reps 4-5.

    python tools/eval/run_expD_sweep.py --list                 # the plan: steps, runs, time estimate
    python tools/eval/run_expD_sweep.py                        # everything (~8 h)
    python tools/eval/run_expD_sweep.py --only B,F             # some scenarios
    python tools/eval/run_expD_sweep.py --extra                # scenario A reps 4-5 from osdi/expD/expD_extra_reps.json
    python tools/eval/run_expD_sweep.py --dry                  # loopback protocol test (fake nodes, 100 Mbps)
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TS = 14.05
CD = "split:none,split:top1,reuse_dyn:top1,reuse_dyn:oracle"   # scenarios C, D: M1 + M2 (no placement), M1 + M2 + top-1, Full OTTER, oracle
GEN = [("bird", 0), ("bird", 1), ("boxing", 0), ("boxing", 1)]


def plan(dry: bool):
    ts = 5.4 if dry else TS
    bw = "100" if dry else "1000"
    steps = [
        ("A", "A 1 Gbps: Full migration, Cold restart, M1 only, OTTER event-driven", 12, ["--policies", "full,cold,restart,reuse_dyn", "--hops", "1", "--tm", "1e9", "--bw", bw]),
        ("A", "A native: same four", 12, ["--policies", "full,cold,restart,reuse_dyn", "--hops", "1", "--tm", "1e9", "--bw", "0"]),
        ("A", "A 1 Gbps: OTTER cold destination", 3, ["--policies", "reuse_dyn", "--hops", "1", "--tm", "1e9", "--bw", bw, "--cold_dest"]),
        ("A", "A native: OTTER cold destination", 3, ["--policies", "reuse_dyn", "--hops", "1", "--tm", "1e9", "--bw", "0", "--cold_dest"]),
        ("B", "B rho 2, 4: six policies", 36, ["--policies", "full,cold,restart,split,reuse_aware_in,reuse_dyn", "--hops", "3", "--ts", str(ts), "--rhos", "2,4", "--bw", bw]),
        ("C", "C correct placement (A -> B)", 12, ["--pp_configs", CD, "--path", "A,B", "--tm", "1e9", "--lookahead", "4" if dry else "10", "--budget", "1", "--bw", bw]),
        ("D", "D incorrect placement (A -> C)", 12, ["--pp_configs", CD, "--path", "A,C", "--tm", "1e9", "--lookahead", "4" if dry else "10", "--budget", "1", "--bw", bw]),
        ("E", "E hybrid: one GPU session + three network sessions", 9, ["--policies", "restart,split,reuse_dyn", "--hops", "3", "--ts", str(ts), "--rhos", "2", "--hybrid_net", "3", "--bw", bw]),
        ("F", "F degradation: C egress -> 62.5 Mbps at D 50 %", 12, ["--policies", "reuse_dyn,reuse_aware_in,split,restart", "--hops", "3", "--ts", str(ts), "--rhos", "2", "--bw", bw,
                                                                       "--cap_events", "D>=0.5:C:out=" + ("6.25" if dry else "62.5")]),
        ("G", "G revisit A -> B -> C -> D -> B", 12, ["--policies", "restart,split,reuse_aware_in,reuse_dyn", "--path", "A,B,C,D,B", "--ts", str(ts), "--rhos", "2", "--bw", bw]),
    ]
    for clip, seed in GEN:
        steps.append((f"Agen_{clip}_s{seed}", f"A generalization {clip} seed {seed}: OTTER event-driven, Full migration", 6,
                      ["--policies", "reuse_dyn,full", "--hops", "1", "--tm", "1e9", "--bw", bw,
                       "--node_extra", f"--video_path examples/{clip}.mp4 --prompt_file_path examples/{clip}_prompt.txt --seed {seed}"]))
    steps.append(("G9", "G9 steady state: 3 x 200 chunks, unmodified vs OTTER enabled (elves-01 GPU 0)", 0, None))
    return steps


EXTRA_ARGS = {   # scenario A configuration label -> orchestrator arguments (for reps 4-5)
    "Full migration": ["--policies", "full"], "Cold restart": ["--policies", "cold"], "M1 only": ["--policies", "restart"],
    "OTTER event-driven": ["--policies", "reuse_dyn"], "OTTER cold destination": ["--policies", "reuse_dyn", "--cold_dest"]}


class Dry:
    """Loopback protocol test: fake mobility nodes (and restore nodes for E) on 127.0.0.1 per step."""
    NODES = "A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942"
    NET = "A=127.0.0.1:29951:29952,B=127.0.0.1:29961:29962,C=127.0.0.1:29971:29972,D=127.0.0.1:29981:29982"

    def __init__(self, py, logd):
        self.py, self.logd, self.procs = py, Path(logd), []
        self.logd.mkdir(parents=True, exist_ok=True)

    def start(self, args):
        self.stop()
        skip = {"B"} if "--cold_dest" in args else set()
        for i, lb in enumerate("ABCD"):
            if lb not in skip:
                self.procs.append(subprocess.Popen([self.py, "tools/eval/mobility_node.py", "--label", lb, "--bind", "127.0.0.1", "--ctl_port", str(29911 + 10 * i), "--data_port", str(29912 + 10 * i),
                                                    "--mss", "0", "--dry_run", "--dry_sink_mb", "64", "--dry_service_s", "0.2", "--post_chunks", "400"],
                                                   cwd=ROOT, stdout=open(self.logd / f"node_{lb}.log", "w"), stderr=subprocess.STDOUT))
            if "--hybrid_net" in args:
                self.procs.append(subprocess.Popen([self.py, "tools/eval/restore_node.py", "--label", lb, "--bind", "127.0.0.1", "--ctl_port", str(29951 + 10 * i),
                                                    "--data_port", str(29952 + 10 * i), "--mss", "0"], cwd=ROOT, stdout=open(self.logd / f"net_{lb}.log", "w"), stderr=subprocess.STDOUT))
        time.sleep(2)

    def stop(self):
        for p in self.procs:
            p.send_signal(signal.SIGTERM)
        for p in self.procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        self.procs = []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", default="", help="comma list of scenarios (A, B, C, D, E, F, G, Agen, G9)")
    ap.add_argument("--extra", action="store_true", help="scenario A reps 4-5 for the configurations in osdi/expD/expD_extra_reps.json")
    ap.add_argument("--repro", action="store_true", help="EXEC_START reproduction (approved 2026-10-24): scenarios C and D with the corrected code, same configurations, results under expDR_C / expDR_D (the frozen expD_C / expD_D stay unchanged)")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--wait_s", type=int, default=1800)
    ap.add_argument("--py", default=os.environ.get("PY") or (str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable))
    a = ap.parse_args()
    steps = plan(a.dry)
    if a.repro:
        a.only = a.only or "C,D"
    if a.only:
        want = set(a.only.split(","))
        steps = [s for s in steps if s[0] in want or (s[0].startswith("Agen") and "Agen" in want)]
    if a.extra:
        rows = json.load(open(ROOT / "results/evaluation/osdi/expD" / ("expD_extra_reps_dryrun_expD.json" if a.dry else "expD_extra_reps.json")))
        steps = []
        for r in rows:
            base = EXTRA_ARGS[r["label"]] + ["--hops", "1", "--tm", "1e9", "--bw", "0" if not r["bw"] else ("100" if a.dry else "1000")]
            steps.append(("A", f"A extra reps 4-5: {r['label']} @ {r['bw'] or 'native'}", 2, base + ["--rep_start", "4", "--reps", "2"]))
    n_runs = sum(s[2] for s in steps)
    n_inv = sum(1 for s in steps if s[3] is not None)
    print(f"[sweep] {len(steps)} steps, {n_runs} runs (+ G9) in {n_inv} orchestrator invocations; estimated {n_inv * 4 / 60 + n_runs * 2.5 / 60 + 0.4:.1f} h "
          f"(4 min node start per invocation, ~2.5 min per run, G9 ~25 min)")
    for s in steps:
        print(f"  {s[0]:>14}  {s[2]:3d} runs  {s[1]}")
    if a.list:
        return
    exp_prefix = "expDR" if a.repro else "expD"
    prefix = ("_dryrun_" if a.dry else "") + exp_prefix   # the orchestrator adds _dryrun_ to the experiment in dry mode
    log = ROOT / "results/evaluation" / (prefix + "_sweep_logs"); log.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dry = Dry(a.py, log / "dry_nodes") if a.dry else None
    for scen, desc, nr, args in steps:
        print(f"[sweep] === {scen}: {desc}", flush=True)
        if not a.dry:
            t0 = time.time()
            while subprocess.run([a.py, "tools/eval/d0_remote.py", "gpu_idle"], cwd=ROOT).returncode != 0:
                if time.time() - t0 > a.wait_s:
                    sys.exit(f"[sweep] GPU 0 not idle / commits differ after {a.wait_s} s; stopping before {scen}")
                time.sleep(60)
        if args is None:   # G9 runs on this host (elves-01), GPU 0
            cmd = [a.py, "tools/eval/steady_state.py", "--reps", "1" if a.dry else "3", "--chunks", "20" if a.dry else "200"] + (["--dry_run", "--dry_service_s", "0.05"] if a.dry else [])
        else:
            cmd = [a.py, "tools/eval/mobility_orchestrate.py", "--experiment", f"{exp_prefix}_{scen}", "--skip_done", "--post_chunks", "400" if a.dry else "300"] + args
            if "--reps" not in args:
                cmd += ["--reps", "1" if a.dry else "3"]
            if a.dry:
                cmd += ["--dry_run", "--nodes", Dry.NODES, "--net_nodes", Dry.NET, "--mss", "0", "--tail_calls", "4", "--max_run_s", "200", "--cold_tail_calls", "20",
                        "--dry_node_args", "--dry_sink_mb 64 --dry_service_s 0.2"]
                if "--node_extra" in cmd:   # dry nodes ignore the workload: drop the flag and its value
                    i = cmd.index("--node_extra"); del cmd[i:i + 2]
                dry.start(args)
            else:
                cmd += ["--launch"]
        with open(log / f"sweep_{stamp}.log", "a") as fh:
            fh.write(f"\n=== {datetime.now().isoformat()} {scen}: {shlex.join(cmd)}\n"); fh.flush()
            r = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if dry:
            dry.stop()
        print(f"[sweep] {scen}: exit {r.returncode} (log {log.relative_to(ROOT)}/sweep_{stamp}.log)", flush=True)
        if r.returncode != 0:
            print(f"[sweep] step {scen} failed; the next steps continue, and a re-start resumes it", flush=True)
    print(f"[sweep] done. Next: {a.py} tools/eval/aggregate_expD.py" + (" --prefix _dryrun_expD" if a.dry else ""), flush=True)


if __name__ == "__main__":
    main()
