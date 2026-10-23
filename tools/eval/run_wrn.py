#!/usr/bin/env python3
"""W / R / N driver (frozen plan: results/evaluation/osdi/followup_prereg_freeze.md). Run on elves-01 from the repo root.

    python tools/eval/run_wrn.py list                 # matrices, runs, time estimate
    python tools/eval/run_wrn.py setup                # every host: official LOVEU archive -> SHA-256 check -> prepare -> W-AR variants
    python tools/eval/run_wrn.py shakedown            # GPU shakedown (followup_shakedown_conditions.md), then:
    python tools/eval/check_wrn_shakedown.py
    python tools/eval/run_wrn.py w1                   # 40 W1 units, one per host at a time on the four GPU 0s
    python tools/eval/run_wrn.py w2                   # 40 W2 invocations (OTTER event-driven + Cold restart, M = 34, horizon 100)
    python tools/eval/run_wrn.py r                    # R: c = 0 and c = 3 (hybrid), 5 rho x 3 policies x 3 reps
    python tools/eval/run_wrn.py n                    # N: 10 cells x 3 policies x 3 reps
    python tools/eval/run_wrn.py war                  # W-AR (exploratory)
    python tools/eval/run_wrn.py all                  # w1, w2, r, n, war in the frozen order
    python tools/eval/run_wrn.py m3dev                # M3-v2 development regression: N cells 7-10, at-moves / v1 / v2, 1 rep (not evidence)
    python tools/eval/run_wrn.py v                    # Experiment V holdout (M3-v2 plan): cells V1-V8 x 4 policies x 3 reps
    python tools/eval/run_wrn.py a                    # Experiment A (M1 recent-KV handoff): 5 workloads x 2 seeds x n in {0,1,2,3}, native bandwidth
    python tools/eval/run_wrn.py xb_gate              # XB real-GPU exactness gate: P-full, R-full (--xb_verify_state) x dog, butterfly; then check_xb_gate.py
    python tools/eval/run_wrn.py xb_cal               # XB calibration grid (27 runs, A and B only); then aggregate_xb_cal.py
    python tools/eval/run_wrn.py xb_cal_rep           # 2 repeats of each selected setting (8 runs); then aggregate_xb_cal.py (jitter rule)
    python tools/eval/run_wrn.py xb_cal_ext           # D-cal-1: round limits 1 and 2 for R-full and P-sink (4 runs); then aggregate_xb_cal.py and xb_cal_rep
    python tools/eval/run_wrn.py xb_cal_jitter        # only if aggregate_xb_cal.py flags a method: 2 more runs per setting of that method
    python tools/eval/run_wrn.py xb_shk               # after the freeze: shakedown, one run per method and scenario (27); then check_xb_shakedown.py
    python tools/eval/run_wrn.py xb_main              # after the shakedown review: 81 runs + ALT (--cells XB1,XB2,XB3,XB4,ALT)
    python tools/eval/run_wrn.py xb_lossy             # D5 lossy-input sensitivity (8 runs) - only after the XB freeze
    add --dry for the loopback protocol test (fake nodes on 127.0.0.1, scaled bandwidth; never reported)

Orchestrator invocations use --skip_done --validity wrn, so a re-start resumes and invalid runs get at most 2 re-runs.
Before every GPU invocation GPU 0 must be idle on all hosts and the repos on one commit (tools/eval/d0_remote.py gpu_idle).
Nothing here changes M1 / M2 / M3.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))

TS = 14.05
LOVEU_DIR = "data/loveu_tgve_2023"
ZIP = f"{LOVEU_DIR}/_archive/loveu-tgve-2023.zip"
URL = "https://drive.usercontent.google.com/download?id=1D7ZVm66IwlKhS6UINoDgFiFJp_mLIQ0W&export=download&confirm=t"
REPO = {"dog": ("examples/original.mp4", "examples/prompt.txt"), "bird": ("examples/bird.mp4", "examples/bird_prompt.txt"),
        "boxing": ("examples/boxing.mp4", "examples/boxing_prompt.txt"), "train": ("examples/train.mp4", "examples/train_prompt.txt")}
# N cells (expN/preregistration.md section 3): id -> (placement, path, degradation spec or None)
N_CELLS = {1: ("none", "A,B", None), 2: ("none", "A,B", "A:out"), 3: ("none", "A,B", "B:in"),
           4: ("top1", "A,B", None), 5: ("top1", "A,B", "A:out"), 6: ("top1", "A,B", "B:in"),
           7: ("top1", "A,C", None), 8: ("top1", "A,C", "A:out"), 9: ("top1", "A,C", "B:out"), 10: ("top1", "A,C", "C:in")}
# Experiment V (M3-v2 holdout, expN/m3v2_holdout_plan.md): id -> (placement, path, degradation spec or None)
V_CELLS = {1: ("proportional", "A,C", None), 2: ("proportional", "A,C", "frac0.25:B:out=125"), 3: ("proportional", "A,C", "frac0.75:C:in=250"),
           4: ("top1", "A,C", "frac0.25:B:out=250"), 5: ("top1", "A,C", "frac0.75:B:out=31.25"), 6: ("top1", "A,C", "frac0.25:C:in=125"),
           7: ("top1", "A,C", "frac0.75:A:out=250"), 8: ("none", "A,B", "frac0.25:B:in=31.25")}
V_LABEL = {1: "proportional x 0", 2: "proportional x holder 125 @0.25", 3: "proportional x ingress 250 @0.75", 4: "incorrect x holder 250 @0.25",
           5: "incorrect x holder 31.25 @0.75", 6: "incorrect x ingress 125 @0.25", 7: "incorrect x source 250 @0.75", 8: "none x ingress 31.25 @0.25"}
N_LABEL = {1: "none x 0", 2: "none x src", 3: "none x in", 4: "correct x 0", 5: "correct x src", 6: "correct x in",
           7: "incorrect x 0", 8: "incorrect x src", 9: "incorrect x hold", 10: "incorrect x in"}


def loveu():
    return list(csv.DictReader(open(ROOT / "results/evaluation/osdi/expW/loveu_selection.csv", newline="")))


def workloads():
    return list(REPO) + [r["video_id"] for r in loveu()]


def paths(w: str, variant: bool = False):
    if w in REPO:
        return REPO[w]
    r = next(x for x in loveu() if x["video_id"] == w)
    v = f"{LOVEU_DIR}/war/{w}__war.mp4" if variant else f"{LOVEU_DIR}/{w}.mp4"
    return v, f"{LOVEU_DIR}/{w}__{r['prompt_type']}.txt"


def war_units():
    import math
    sel = loveu()
    out = []
    for frames in ("32", "128"):
        g = sorted((r for r in sel if r["frames"] == frames), key=lambda r: (float(r["motion_score"]), r["video_id"]))
        out += [g[math.floor((j + 0.5) * len(g) / 2)]["video_id"] for j in range(2)]
    return out


class Ctx:
    def __init__(self, a):
        self.a = a
        self.dry = a.dry
        self.py = a.py
        self.bw = "100" if a.dry else "1000"
        self.ts = "5.4" if a.dry else str(TS)
        self.deg = "6.25" if a.dry else "62.5"
        self.log = ROOT / "results/evaluation" / ("_dryrun_wrn_logs" if a.dry else "wrn_logs")
        self.log.mkdir(parents=True, exist_ok=True)
        self.stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.procs = []
        self.failures = []

    # ---------------- GPU / loopback orchestrator invocations
    def wait_idle(self, what, hosts: str = ""):
        """GPU 0 idle on `hosts` (default all four; XB one-hop invocations pass "A,B" so a VC unit on D does not block
        them) and all four repos on one commit. A preflight only: run validity rules are unchanged."""
        if self.dry:
            return
        t0 = time.time()
        while subprocess.run([self.py, "tools/eval/d0_remote.py", "gpu_idle"] + (["--hosts", hosts] if hosts else []), cwd=ROOT).returncode != 0:
            if time.time() - t0 > self.a.wait_s:
                sys.exit(f"[wrn] GPU 0 not idle / commits differ after {self.a.wait_s} s; stopping before {what}")
            time.sleep(60)

    def dry_nodes(self, node_args: list[str], hybrid: bool):
        self.stop_dry()
        for i, lb in enumerate("ABCD"):
            self.procs.append(subprocess.Popen([self.py, "tools/eval/mobility_node.py", "--label", lb, "--bind", "127.0.0.1", "--ctl_port", str(29911 + 10 * i),
                                                "--data_port", str(29912 + 10 * i), "--mss", "0", "--dry_run", "--dry_sink_mb", "64", "--dry_service_s", "0.2"] + node_args,
                                               cwd=ROOT, stdout=open(self.log / f"dry_node_{lb}.log", "a"), stderr=subprocess.STDOUT))
            if hybrid:
                self.procs.append(subprocess.Popen([self.py, "tools/eval/restore_node.py", "--label", lb, "--bind", "127.0.0.1", "--ctl_port", str(29951 + 10 * i),
                                                    "--data_port", str(29952 + 10 * i), "--mss", "0"], cwd=ROOT, stdout=open(self.log / f"dry_net_{lb}.log", "a"), stderr=subprocess.STDOUT))
        time.sleep(2)

    def stop_dry(self):
        for p in self.procs:
            p.send_signal(signal.SIGTERM)
        for p in self.procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        self.procs = []

    def already_done(self, experiment: str, args: list[str]) -> bool:
        """Single-configuration invocations (W2: --policies without --rhos / --pp_configs): skip the whole invocation,
        including the node start, when every policy already has `reps` valid runs (the orchestrator's --skip_done only
        checks after the nodes are up, ~2 min of model load per invocation)."""
        if "--policies" not in args or "--rhos" in args or "--pp_configs" in args or any(x.startswith("--xb") for x in args):
            return False
        pols = args[args.index("--policies") + 1].split(",")
        reps = int(args[args.index("--reps") + 1]) if "--reps" in args else 1
        root = ROOT / "results/evaluation" / (("_dryrun_" if self.dry else "") + experiment)
        from wrn_validity import run_validity_wrn
        for pol in pols:
            n = 0
            for d in root.glob(f"policy={pol}_*"):
                try:
                    if run_validity_wrn(json.load(open(d / "summary.json")), d, dry=self.dry)[0]:
                        n += 1
                except (OSError, ValueError, KeyError):
                    pass
            if n < reps:
                return False
        return True

    def orch(self, experiment: str, args: list[str], node_extra: list[str], what: str):
        """One orchestrator invocation (nodes start once; --skip_done resumes)."""
        if self.already_done(experiment, args):
            print(f"[wrn] skip {what}: every policy already has its valid runs", flush=True)
            return 0
        hops = int(args[args.index("--hops") + 1]) if "--hops" in args else 3
        # XB invocations use only the labels of their path (one hop: A and B); every other experiment keeps the four-host check
        self.wait_idle(what, ",".join("ABCD"[:hops + 1]) if any(x.startswith("--xb") for x in args) or ("--policies" in args and any(p in args[args.index("--policies") + 1] for p in ("precopy", "recompute", "split_wait"))) else "")
        cmd = [self.py, "tools/eval/mobility_orchestrate.py", "--experiment", experiment, "--skip_done", "--validity", "wrn", "--bw", self.bw] + args
        if self.dry:
            m = args[args.index("--migration_chunk") + 1] if "--migration_chunk" in args else "30"
            pc = args[args.index("--post_chunks") + 1] if "--post_chunks" in args else "300"
            dry_extra = [x for x in node_extra if x in ("--sink_fp",)] + (["--dry_promote_calls", self.a.dry_promote] if self.a.dry_promote else [])
            if "--recent_slots" in node_extra:
                i = node_extra.index("--recent_slots"); dry_extra += node_extra[i:i + 2]
            self.dry_nodes(["--migration_chunk", m, "--post_chunks", pc] + dry_extra, "--hybrid_net" in args)
            cmd += ["--dyn_probe", "1",   # 16-fragment fake Sink: a 4-fragment probe would be a quarter of it
                    "--dry_run", "--nodes", "A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942",
                    "--net_nodes", "A=127.0.0.1:29951:29952,B=127.0.0.1:29961:29962,C=127.0.0.1:29971:29972,D=127.0.0.1:29981:29982", "--mss", "0"]
        else:
            # "=" form: a value that starts with "--" and has no space (e.g. "--sink_fp") would otherwise be parsed as an option
            cmd += ["--launch", "--node_extra=" + " ".join(node_extra)]
        print(f"[wrn] === {what}", flush=True)
        with open(self.log / f"wrn_{self.stamp}.log", "a") as fh:
            fh.write(f"\n=== {datetime.now().isoformat()} {what}: {shlex.join(cmd)}\n"); fh.flush()
            r = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
        if self.dry:
            self.stop_dry()
        print(f"[wrn] {what}: exit {r.returncode}", flush=True)
        if r.returncode != 0:
            self.failures.append(f"{what}: exit {r.returncode}")
        return r.returncode

    # ---------------- W1 on the hosts' GPU 0 (agents) or locally (dry)
    def w1_units(self, units, tag="", root="expW_W1", extra=()):
        """units: [(workload, seed, video_override or None)]; one unit per host at a time; results copied back."""
        out_root = ROOT / "results/evaluation" / (("_dryrun_" if self.dry else "") + root)
        done = lambda w, s: any((d / "w1_summary.json").exists() for d in out_root.glob(f"{w}_s{s}{('_' + tag) if tag else ''}_2*"))  # noqa: E731
        todo = [u for u in units if not done(u[0], u[1])]
        print(f"[wrn] W1{(' ' + tag) if tag else ''}: {len(todo)} of {len(units)} units to run", flush=True)
        if self.dry:
            for w, s, v in todo:
                cmd = [self.py, "tools/eval/expw_w1.py", "--workload", w, "--seed", str(s), "--dry_run", "--out_root", str(out_root), "--calls", "330"] + list(extra)
                if tag:
                    cmd += ["--tag", tag]
                subprocess.run(cmd, cwd=ROOT, check=False)
            return
        self.wait_idle("W1")
        from agents import Agent, parse_hosts
        hosts = parse_hosts(self.a.agent_hosts)
        queue_ = list(todo)
        lock = threading.Lock()

        def worker(lb):
            ag = Agent(lb, *hosts[lb])
            while True:
                with lock:
                    if not queue_:
                        return
                    w, s, v = queue_.pop(0)
                cmd = [".venv/bin/python", "tools/eval/expw_w1.py", "--workload", w, "--seed", str(s), "--gpu_id", "0", "--loveu_dir", LOVEU_DIR, "--out_root", str(out_root)] + list(extra)
                if v:
                    cmd += ["--video_path", v]
                if tag:
                    cmd += ["--tag", tag]
                logrel = f"results/evaluation/wrn_logs/w1_{w}_s{s}{('_' + tag) if tag else ''}_{lb}.log"
                pid = ag.run(cmd, logrel)
                rc = ag.wait(pid, timeout=3600).get("rc")
                print(f"[wrn] W1 {w} s{s} on {lb}: rc {rc}", flush=True)
                if rc != 0:
                    with lock:
                        self.failures.append(f"W1 {w} s{s} on {lb}: rc {rc}")
                if lb != "A":   # copy the result back to elves-01 (text files)
                    for d in ag.glob(f"results/evaluation/{root}/{w}_s{s}{('_' + tag) if tag else ''}_2*"):
                        loc = ROOT / d; loc.mkdir(parents=True, exist_ok=True)
                        for f in ("w1_calls.csv", "w1_summary.json", "w1_blocks.csv"):
                            try:
                                (loc / f).write_text(ag.read(f"{d}/{f}"))
                            except RuntimeError as exc:
                                print(f"[wrn] copy {d}/{f} from {lb}: {exc}", flush=True)

        th = [threading.Thread(target=worker, args=(lb,)) for lb in "ABCD"]
        for t in th:
            t.start()
        for t in th:
            t.join()

    def w1_on(self, lb: str, w: str, s: int):
        """Shakedown: one W1 unit on a given host (the W2 destination B, for W-b / W-c)."""
        if self.dry:
            return self.w1_units([(w, s, None)])
        from agents import Agent, parse_hosts
        ag = Agent(lb, *parse_hosts(self.a.agent_hosts)[lb])
        pid = ag.run([".venv/bin/python", "tools/eval/expw_w1.py", "--workload", w, "--seed", str(s), "--gpu_id", "0", "--loveu_dir", LOVEU_DIR, "--tag", "shk"],
                     f"results/evaluation/wrn_logs/shk_w1_{w}_s{s}_{lb}.log")
        rc = ag.wait(pid, timeout=3600).get("rc")
        print(f"[wrn] shakedown W1 {w} s{s} on {lb}: rc {rc}", flush=True)
        if rc != 0:
            self.failures.append(f"shakedown W1 on {lb}: rc {rc}")
        for d in ag.glob(f"results/evaluation/expW_W1/{w}_s{s}_shk_2*"):
            loc = ROOT / d; loc.mkdir(parents=True, exist_ok=True)
            for f in ("w1_calls.csv", "w1_summary.json"):
                (loc / f).write_text(ag.read(f"{d}/{f}"))


# ---------------- plans
def w2_args(c: Ctx):
    return ["--policies", "reuse_dyn,cold", "--hops", "1", "--tm", "1e9", "--reps", "1", "--migration_chunk", "34", "--post_chunks", "130",
            "--horizon_calls", "100", "--max_run_s", "600"]


def node_extra(w, s, variant=False):
    v, p = paths(w, variant)
    return ["--video_path", v, "--prompt_file_path", p, "--seed", str(s), "--sink_fp"]


def r_args(c: Ctx, contention: int, rhos="0.5,1,2,4,8", reps="3", policies="restart,split,reuse_dyn"):
    return ["--policies", policies, "--hops", "3", "--ts", c.ts, "--rhos", rhos, "--reps", reps, "--post_chunks", "300", "--max_run_s", "600"] + \
        (["--hybrid_net", "3"] if contention else [])


def n_args(c: Ctx, cell: int, reps="3", policies=("reuse_aware_in", "reuse_dyn", "split")):
    pp, path, deg = N_CELLS[cell]
    a = ["--pp_configs", ",".join(f"{p}:{pp}" for p in policies), "--path", path, "--tm", "1e9", "--lookahead", "4" if c.dry else "10", "--budget", "1",
         "--reps", reps, "--post_chunks", "400", "--max_run_s", "900"]
    if deg:
        node, d = deg.split(":")
        a += ["--cap_events", f"half:{node}:{d}={c.deg}"]
    return a


V_POST = {8: ("800", "1200")}   # amendment 1 (2026-10-20): V8 needs ~330 s of restoration through the 31.25 Mbps ingress


def v_args(c: Ctx, cell: int, reps="3", policies=("reuse_aware_in", "split", "reuse_dyn", "reuse_dyn2")):
    pp, path, deg = V_CELLS[cell]
    post, mx = V_POST.get(cell, ("400", "900"))
    a = ["--pp_configs", ",".join(f"{p}:{pp}" for p in policies), "--path", path, "--tm", "1e9", "--lookahead", "4" if c.dry else "10", "--budget", "1",
         "--reps", reps, "--post_chunks", post, "--max_run_s", mx]
    if deg:
        kind, node, capv = deg.split(":"); d, mbps = capv.split("=")
        a += ["--cap_events", f"{kind}:{node}:{d}={float(mbps) / 10 if c.dry else mbps}"]
    return a


A_WORKLOADS = ["dog", "audi-snow-trail", "butterfly-feeding-slow-motion", "circus-ball-act", "train"]   # osdi/m1m2_followup.md Task A rule

VACW_WORKLOADS = ["dog", "butterfly-feeding-slow-motion"]   # expM2/vacw_v0_design.md section 6: refresh-light / refresh-heavy, seed 0
VACW_POLICIES = "restart_fresh,split,split_va"


def vacw_args(c: Ctx, rho: str, reps="3"):
    return ["--policies", VACW_POLICIES, "--hops", "3", "--ts", c.ts, "--rhos", rho, "--reps", reps, "--migration_chunk", "30", "--post_chunks", "300", "--max_run_s", "600"]


M3E_POL = {"S1": "restart,split,reuse_dyn2", "S2": "restart,split,reuse_dyn2,reuse_aware_in", "S3": "restart,split,reuse_dyn2",
           "S4": "restart,split,reuse_dyn2", "S5": "restart,split,reuse_dyn2"}   # osdi/expM3E/preregistration.md (frozen abf74d6)


def m3e_args(c: Ctx, sc: str, reps: str):
    """A -> B -> C -> D at rho 2, 1 Gbps, dog seed 0, trigger at chunk 30; M3-v2 probe 4 (dry: 1, set by orch())."""
    a = ["--policies", M3E_POL[sc], "--hops", "3", "--ts", c.ts, "--rhos", "2", "--reps", reps, "--migration_chunk", "30", "--post_chunks", "400", "--max_run_s", "600"]
    if not c.dry:
        a += ["--dyn_probe", "4"]
    if sc == "S1":
        a += ["--hybrid_net", "3"]
    cap = {"S2": f"D>=0.5:C:out={c.deg}", "S3": f"D>=0.5:D:in={c.deg}", "S5": f"D>=0.5:A:out={c.deg}"}.get(sc)
    if cap:
        a += ["--cap_events", cap]
    return a


def do_m3e(c, shakedown=False):
    """M3E: five scenarios (S1 contention, S2 holder bottleneck, S3 ingress bottleneck, S4 no change, S5 source bottleneck);
    shakedown = one rep per policy per scenario (expM3E_shk_S*), not evidence."""
    only = [x for x in (c.a.cells or "").split(",") if x]   # re-runs: --cells S3 limits the invocation to those scenarios
    for sc in ("S4", "S2", "S3", "S5", "S1"):
        if only and sc not in only:
            continue
        exp = f"expM3E_{'shk_' if shakedown else ''}{sc}"
        c.orch(exp, m3e_args(c, sc, "1" if shakedown else "3"), node_extra("dog", 0), f"M3E {'shakedown ' if shakedown else ''}{sc}")


WX_WL = {"bfly": "butterfly-feeding-slow-motion", "audi": "audi-snow-trail", "train": "train"}   # osdi/expWX/preregistration.md (frozen a181126)
WX_CFG = {"X1": ("1", "restart,split", None, False), "X2": ("4", "restart,split", None, False),
          "X3": ("2", "restart,split,reuse_dyn2", None, False), "X4": ("2", "restart,split,reuse_dyn2", None, True),
          "X5": ("2", "restart,split,reuse_dyn2,reuse_aware_in", "C:out", False), "X6": ("2", "split,reuse_dyn2", "D:in", False)}


def wx_args(c: Ctx, x: str, reps: str):
    rho, pols, cap, hybrid = WX_CFG[x]
    a = ["--policies", pols, "--hops", "3", "--ts", c.ts, "--rhos", rho, "--reps", reps, "--migration_chunk", "30", "--post_chunks", "400", "--max_run_s", "600"]
    if not c.dry:
        a += ["--dyn_probe", "4"]
    if hybrid:
        a += ["--hybrid_net", "3"]
    if cap:
        node, d = cap.split(":")
        a += ["--cap_events", f"D>=0.5:{node}:{d}={c.deg}"]
    return a


def do_wx(c, shakedown=False):
    """WX: X1-X6 on butterfly / audi-snow-trail / train (seed 0); shakedown = X3 and X5, one rep per policy.
    --cells filters configurations (X1..X6) and / or workloads (bfly, audi, train) for re-runs."""
    only = {x for x in (c.a.cells or "").split(",") if x}
    for ws, w in WX_WL.items():
        for x in (("X3", "X5") if shakedown else ("X3", "X5", "X6", "X4", "X1", "X2")):
            if only and not ({x, ws} & only):
                continue
            if only and any(k in WX_CFG for k in only) and x not in only:
                continue
            if only and any(k in WX_WL for k in only) and ws not in only:
                continue
            c.orch(f"expWX_{'shk_' if shakedown else ''}{ws}_{x}", wx_args(c, x, "1" if shakedown else "3"), node_extra(w, 0), f"WX {'shakedown ' if shakedown else ''}{ws} {x}")


XB_WL = {"dog": "dog", "bfly": "butterfly-feeding-slow-motion"}   # osdi/expXB/preregistration.md (draft; XB1 workloads)
XB_GRID = {"precopy_full": ";".join(f"thr={t}:rl={r}" for t in (16, 64, 256) for r in (3, 6, 10)),
           "precopy_sink": ";".join(f"thr={t}:rl={r}" for t in (16, 64, 256) for r in (3, 6, 10)),
           "recompute_full": ";".join(f"lag={g}:rl={r}" for g in (1, 2) for r in (3, 6, 10)),
           "recompute_win": "W=1;W=3;W=6"}


def xb_node_extra(w):
    v, p = paths(w)
    return ["--video_path", v, "--prompt_file_path", p, "--seed", "0"]


def xb_args(c: Ctx, policies: str, reps="1", rep_start="1"):
    """XB1: single move A -> B at trigger chunk 30, 1 Gbps. Pre-copy rounds and R-full replay keep the source generating
    for up to ~10 min, so those methods need a long reference window."""
    long_ = any(p in policies for p in ("precopy", "recompute_full"))
    post = "1500" if (c.dry or long_) else "400"
    mx = "600" if c.dry else ("1800" if long_ else "900")
    return ["--policies", policies, "--hops", "1", "--tm", "1e9", "--reps", reps, "--rep_start", rep_start, "--migration_chunk", "30", "--post_chunks", post,
            "--max_run_s", mx, "--xb_horizon", "20" if c.dry else "100"]


def xb_selection(c: Ctx) -> dict:
    p = ROOT / "results/evaluation/osdi/expXB" / ("_dryrun_calibration_selection.json" if c.dry else "calibration_selection.json")
    if not p.exists():
        sys.exit(f"[wrn] {p} missing: run tools/eval/aggregate_xb_cal.py{' --dry' if c.dry else ''} first")
    return json.loads(p.read_text())


def do_xb_gate(c):
    for ws, w in XB_WL.items():
        c.orch(f"expXB_gate_{ws}", xb_args(c, "precopy_full,recompute_full") + ["--xb_verify_state"], xb_node_extra(w), f"XB exactness gate {ws}")


def do_xb_cal(c):
    only = {x for x in (c.a.cells or "").split(",") if x}
    for pol, grid in XB_GRID.items():
        if only and pol not in only:
            continue
        c.orch("expXB_cal", xb_args(c, pol) + ["--xb_grid", grid], xb_node_extra("dog"), f"XB calibration {pol} ({grid.count(';') + 1} settings)")


XB_GRID_EXT = {"recompute_full": "lag=1:rl=1;lag=1:rl=2", "precopy_sink": "thr=16:rl=1;thr=16:rl=2"}   # calibration_review.md D-cal-1


def _xb_rep_tag(pol: str, setting: str) -> str:
    kv = dict(x.split("=") for x in setting.split(":"))
    if pol.startswith("precopy"):
        return f"_thr={float(kv['thr']):g}_rl={kv['rl']}_rep="
    if pol == "recompute_full":
        return f"_lag={kv['lag']}_rl={kv['rl']}_rep="
    return f"_W={kv['W']}_rep="


def _xb_has_valid(c: Ctx, pol: str, setting: str, reps) -> bool:
    from xb_validity import run_validity_xb
    root = ROOT / "results/evaluation" / (("_dryrun_" if c.dry else "") + "expXB_cal")
    tag = _xb_rep_tag(pol, setting)
    for r in reps:
        ok = False
        for d in root.glob(f"policy={pol}_*{tag}{r}_*"):
            try:
                ok = ok or run_validity_xb(json.load(open(d / "summary.json")), d, dry=c.dry)[0]
            except (OSError, ValueError, KeyError):
                pass
        if not ok:
            return False
    return True


def do_xb_cal_rep(c):
    """Repeats 2 and 3 of each selected setting; a method whose selected setting already has them starts no nodes."""
    for pol, x in xb_selection(c).items():
        if not x.get("selected"):
            continue
        if _xb_has_valid(c, pol, x["selected"], (2, 3)):
            print(f"[wrn] skip XB calibration repeats {pol} {x['selected']}: repeats 2 and 3 exist", flush=True); continue
        c.orch("expXB_cal", xb_args(c, pol, reps="2", rep_start="2") + ["--xb_grid", x["selected"]], xb_node_extra("dog"), f"XB calibration repeats {pol} {x['selected']}")


def do_xb_cal_ext(c):
    """calibration_review.md D-cal-1 (pre-freeze): round limits 1 and 2 for R-full and P-sink, whose optimum lay at the
    grid's lower edge (round limit 3). Same setting, rules and selection; rep 1."""
    for pol, grid in XB_GRID_EXT.items():
        c.orch("expXB_cal", xb_args(c, pol) + ["--xb_grid", grid], xb_node_extra("dog"), f"XB calibration extension {pol} ({grid})")


def do_xb_cal_jitter(c):
    for pol, x in xb_selection(c).items():
        if x.get("jitter_recalibrate"):
            c.orch("expXB_cal", xb_args(c, pol, reps="2", rep_start="2") + ["--xb_grid", XB_GRID[pol]], xb_node_extra("dog"), f"XB jitter re-calibration {pol}")


XB_METHODS_ALL = "reuse_dyn2,full,split_wait,precopy_full,precopy_sink,recompute_full,recompute_win"   # XB1: all seven
XB_METHODS_MOB = "reuse_dyn2,full,split_wait,precopy_sink,recompute_full"                            # XB2 subset below; XB3 / XB4
XB_SCEN = {   # osdi/expXB/preregistration.md section 5 (frozen settings from calibration_selection.json)
    "XB1": {"workloads": ("dog", "bfly"), "policies": XB_METHODS_ALL, "hops": "1", "M": "30", "move": ["--tm", "1e9"], "horizon": "130"},
    "XB2": {"workloads": ("dog",), "policies": "reuse_dyn2,precopy_sink,recompute_full", "hops": "1", "M": "120", "move": ["--tm", "1e9"], "horizon": "130"},
    "XB3": {"workloads": ("dog",), "policies": XB_METHODS_MOB, "hops": "3", "M": "30", "move": ["--rhos", "1"], "horizon": "180"},
    "XB4": {"workloads": ("dog",), "policies": XB_METHODS_MOB, "hops": "3", "M": "30", "move": ["--rhos", "2"], "horizon": "180"},
}


def xb_frozen_settings(c: Ctx) -> str:
    return ";".join(f"{pol}@{x['selected']}" for pol, x in xb_selection(c).items() if x.get("selected"))


def xb_main_args(c: Ctx, sc: str, reps: str, policies: str | None = None) -> list[str]:
    S = XB_SCEN[sc]
    hz = "20" if c.dry else "100"
    a = ["--policies", policies or S["policies"], "--hops", S["hops"], "--reps", reps, "--migration_chunk", S["M"], "--post_chunks", "1500",
         "--max_run_s", "900" if c.dry else "2400", "--xb_horizon", hz, "--horizon_calls", "40" if c.dry else S["horizon"]] + S["move"]
    if "--rhos" in S["move"]:
        a += ["--ts", c.ts]
    if not c.dry:
        a += ["--dyn_probe", "4"]
    return a


def _xb_frozen_guard(c: Ctx):
    if not c.dry and not (ROOT / "results/evaluation/osdi/expXB_freeze.md").exists():
        sys.exit("[wrn] XB is not frozen (results/evaluation/osdi/expXB_freeze.md missing): no shakedown or main sweep")


def do_xb_main(c, shakedown=False):
    """XB shakedown (one run per method and scenario, 27 runs; not evidence) or main sweep (81 runs) and, as cell ALT,
    the rule-4 alternative settings in XB1 (3 methods x 2 workloads x 3 reps). --cells XB1,XB2,XB3,XB4,ALT filters;
    XB3 / XB4 need GPU 0 on all four hosts."""
    _xb_frozen_guard(c)
    only = {x for x in (c.a.cells or "").split(",") if x}
    frozen = xb_frozen_settings(c)
    reps = "1" if shakedown else "3"
    for sc in ("XB1", "XB2", "XB3", "XB4"):
        if only and sc not in only:
            continue
        for ws in XB_SCEN[sc]["workloads"]:
            w = XB_WL[ws]
            c.orch(f"expXB_{'shk_' if shakedown else ''}{sc}_{ws}", xb_main_args(c, sc, reps) + ["--xb_policy_settings", frozen], xb_node_extra(w),
                   f"XB {'shakedown ' if shakedown else ''}{sc} {ws}")
    if not shakedown and (not only or "ALT" in only):
        # rule-4 alternatives: one invocation per workload (one node start), each method with its own alternative setting
        alt = {pol: x["alternative_min_gap"] for pol, x in xb_selection(c).items() if x.get("alternative_differs") and x.get("alternative_min_gap")}
        if alt:
            for ws in XB_SCEN["XB1"]["workloads"]:
                c.orch(f"expXB_ALT_{ws}", xb_main_args(c, "XB1", reps, ",".join(alt)) + ["--xb_policy_settings", ";".join(f"{p}@{v}" for p, v in alt.items())],
                       xb_node_extra(XB_WL[ws]), f"XB rule-4 alternatives {ws}: {alt}")


def do_xb_lossy(c):
    """D5 (approved 2026-10-22): XB1, dog and butterfly, R-full and R-win at their selected settings, H.264 CRF 23 and 28,
    1 rep each = 8 runs; descriptive sensitivity, never exact recomputation. Only after the XB freeze."""
    if not c.dry and not (ROOT / "results/evaluation/osdi/expXB_freeze.md").exists():
        sys.exit("[wrn] XB is not frozen (results/evaluation/osdi/expXB_freeze.md missing): the lossy-input runs come after the freeze")
    sel = xb_selection(c)
    for ws, w in XB_WL.items():
        for pol in ("recompute_full", "recompute_win"):
            grid = ";".join(f"{sel[pol]['selected']}:codec={cd}" for cd in ("h264_crf23", "h264_crf28"))
            c.orch(f"expXB_lossy_{ws}", xb_args(c, pol) + ["--xb_grid", grid], xb_node_extra(w), f"XB lossy inputs {ws} {pol}")


def do_vacw(c):
    """VACW v0 (frozen 9137bc9): A -> B -> C -> D, rho {0.5, 1}, 1 Gbps, dog / butterfly seed 0, 3 policies x 3 reps = 36 runs."""
    tag = f"_{c.a.tag}" if c.a.tag else ""
    for w in VACW_WORKLOADS:
        for rho in ("0.5", "1"):
            c.orch(f"expVA{tag}_{w}_rho{rho}", vacw_args(c, rho), node_extra(w, 0), f"VACW v0{tag} {w} rho {rho}")


def do_a(c):
    """Experiment A: OTTER event-driven, single move at M = 34, horizon 100 calls, native bandwidth, recent_slots n."""
    for w in A_WORKLOADS:
        for seed in (0, 1):
            args = ["--policies", "reuse_dyn", "--hops", "1", "--tm", "1e9", "--reps", "1", "--migration_chunk", "34", "--post_chunks", "130",
                    "--horizon_calls", "100", "--max_run_s", "600", "--recent_slots", "0,1,2,3"]
            c.bw = "0"   # native (unshaped)
            c.orch(f"expA_{w}_s{seed}", args, node_extra(w, seed), f"A {w} seed {seed} (recent_slots 0-3)")
            c.bw = "100" if c.dry else "1000"


def do_b(c):
    """Task B: W1-style runs with per-call block checksums on the 10 Task-A units (results/evaluation/expW_B)."""
    c.w1_units([(w, s, None) for w in A_WORKLOADS for s in (0, 1)], root="expW_B", extra=("--block_ck",))


def do_m3dev(c):
    tag = f"_{c.a.tag}" if c.a.tag else ""
    for cell in (7, 8, 9, 10):
        c.orch(f"m3dev{tag}_cell{cell}", n_args(c, cell, reps="1", policies=("reuse_aware_in", "reuse_dyn", "reuse_dyn2")), ["--sink_fp"], f"M3-v2 dev regression{tag} N cell {cell} ({N_LABEL[cell]})")


def do_v(c):
    cells = [int(x) for x in c.a.cells.split(",")] if c.a.cells else list(V_CELLS)
    tag = f"_{c.a.tag}" if c.a.tag else ""
    for cell in cells:
        c.orch(f"expV{tag}_cell{cell}", v_args(c, cell), ["--sink_fp"], f"V{tag} cell {cell} ({V_LABEL[cell]})")


def do_w1(c):
    c.w1_units([(w, s, None) for w in workloads() for s in (0, 1)])


def do_w2(c):
    for w in workloads():
        for s in (0, 1):
            c.orch(f"expW_W2_{w}_s{s}", w2_args(c), node_extra(w, s), f"W2 {w} seed {s}")


def do_r(c):
    c.orch("expR_c0", r_args(c, 0), ["--sink_fp"], "R c = 0")
    c.orch("expR_c3", r_args(c, 3), ["--sink_fp"], "R c = 3 (hybrid)")


def do_n(c):
    for cell in N_CELLS:
        c.orch(f"expN_cell{cell}", n_args(c, cell), ["--sink_fp"], f"N cell {cell} ({N_LABEL[cell]})")


def do_war(c):
    units = war_units()
    c.w1_units([(w, 0, f"{LOVEU_DIR}/war/{w}__war.mp4") for w in units], tag="war")
    for w in units:
        c.orch(f"expW_WAR_{w}_s0", w2_args(c), node_extra(w, 0, variant=True), f"W-AR W2 {w}")


def do_shakedown(c):
    c.w1_on("B", "mbike-trick", 0)
    c.orch("shk_W2_mbike-trick_s0", w2_args(c), node_extra("mbike-trick", 0), "shakedown W2 mbike-trick s0")
    c.orch("shk_R", r_args(c, 3, rhos="0.5", reps="1"), ["--sink_fp"], "shakedown R rho 0.5 c = 3")
    c.orch("shk_N_cell9", n_args(c, 9, reps="1", policies=("reuse_aware_in", "reuse_dyn")), ["--sink_fp"], "shakedown N cell 9")


def do_setup(c):
    if c.dry:
        print("[wrn] setup is a testbed step (no dry mode)"); return
    from agents import Agent, parse_hosts
    hosts = parse_hosts(c.a.agent_hosts)
    script = (f"set -e; mkdir -p {LOVEU_DIR}/_archive; test -f {ZIP} || curl -sL -o {ZIP} '{URL}'; "
              f".venv/bin/python -I tools/eval/expw_loveu.py prepare --zip {ZIP} --out {LOVEU_DIR}; "
              f".venv/bin/python -I tools/eval/expw_war_variant.py --src {LOVEU_DIR} --out {LOVEU_DIR}/war")
    pids = {}
    for lb in "ABCD":
        ag = Agent(lb, *hosts[lb])
        pids[lb] = (ag, ag.run(["bash", "-c", script], f"results/evaluation/wrn_logs/setup_{lb}.log"))
    for lb, (ag, pid) in pids.items():
        print(f"[wrn] setup {lb}: rc {ag.wait(pid, timeout=1800).get('rc')} (log results/evaluation/wrn_logs/setup_{lb}.log on that host)", flush=True)


def do_list(c):
    n_w = len(workloads())
    print(f"W1 {n_w * 2} runs; W2 {n_w * 2 * 2} runs ({n_w * 2} invocations); R 90 runs (2 invocations); N 90 runs (10 invocations); W-AR 12 runs; total 312")
    print("N cells:", {k: N_LABEL[k] for k in N_CELLS})
    print("W-AR videos:", war_units())
    print("estimate ~19 h (W1 ~1 h in parallel, W2 ~6 h, R ~4.5 h, N ~6 h, W-AR ~1 h) + shakedown ~1 h")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["list", "setup", "shakedown", "w1", "w2", "r", "n", "war", "all", "m3dev", "v", "a", "b", "vacw", "m3e_shk", "m3e", "wx_shk", "wx",
                                       "xb_gate", "xb_cal", "xb_cal_rep", "xb_cal_ext", "xb_cal_jitter", "xb_lossy", "xb_shk", "xb_main"])
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--dry_promote", default="", help="dry: calls at which bound fake Sinks change (version-event accounting test)")
    ap.add_argument("--agent_hosts", default=None)
    ap.add_argument("--wait_s", type=int, default=1800)
    ap.add_argument("--tag", default="", help="m3dev: round tag (m3dev_<tag>_cell*); v: amendment tag (expV_<tag>_cell*); earlier runs are kept")
    ap.add_argument("--cells", default="", help="v: comma list of V cells to run (default all); m3e / m3e_shk: comma list of scenarios (S1..S5) for re-runs")
    ap.add_argument("--py", default=os.environ.get("PY") or (str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable))
    a = ap.parse_args()
    c = Ctx(a)
    try:
        if a.what == "all":
            for f in (do_w1, do_w2, do_r, do_n, do_war):
                f(c)
        else:
            {"list": do_list, "setup": do_setup, "shakedown": do_shakedown, "w1": do_w1, "w2": do_w2, "r": do_r, "n": do_n, "war": do_war, "m3dev": do_m3dev, "v": do_v, "a": do_a, "b": do_b, "vacw": do_vacw, "m3e_shk": lambda c: do_m3e(c, True), "m3e": do_m3e, "wx_shk": lambda c: do_wx(c, True), "wx": do_wx,
             "xb_gate": do_xb_gate, "xb_cal": do_xb_cal, "xb_cal_rep": do_xb_cal_rep, "xb_cal_ext": do_xb_cal_ext, "xb_cal_jitter": do_xb_cal_jitter, "xb_lossy": do_xb_lossy,
             "xb_shk": lambda c: do_xb_main(c, True), "xb_main": do_xb_main}[a.what](c)
    finally:
        c.stop_dry()
    if c.failures:
        print("[wrn] FAILED invocations:\n  " + "\n  ".join(c.failures), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
