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
    def wait_idle(self, what):
        if self.dry:
            return
        t0 = time.time()
        while subprocess.run([self.py, "tools/eval/d0_remote.py", "gpu_idle"], cwd=ROOT).returncode != 0:
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

    def orch(self, experiment: str, args: list[str], node_extra: list[str], what: str):
        """One orchestrator invocation (nodes start once; --skip_done resumes)."""
        self.wait_idle(what)
        cmd = [self.py, "tools/eval/mobility_orchestrate.py", "--experiment", experiment, "--skip_done", "--validity", "wrn", "--bw", self.bw] + args
        if self.dry:
            m = args[args.index("--migration_chunk") + 1] if "--migration_chunk" in args else "30"
            pc = args[args.index("--post_chunks") + 1] if "--post_chunks" in args else "300"
            dry_extra = [x for x in node_extra if x in ("--sink_fp",)] + (["--dry_promote_calls", self.a.dry_promote] if self.a.dry_promote else [])
            self.dry_nodes(["--migration_chunk", m, "--post_chunks", pc] + dry_extra, "--hybrid_net" in args)
            cmd += ["--dry_run", "--nodes", "A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942",
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
    def w1_units(self, units, tag=""):
        """units: [(workload, seed, video_override or None)]; one unit per host at a time; results copied back."""
        out_root = ROOT / "results/evaluation" / ("_dryrun_expW_W1" if self.dry else "expW_W1")
        done = lambda w, s: any((d / "w1_summary.json").exists() for d in out_root.glob(f"{w}_s{s}{('_' + tag) if tag else ''}_2*"))  # noqa: E731
        todo = [u for u in units if not done(u[0], u[1])]
        print(f"[wrn] W1{(' ' + tag) if tag else ''}: {len(todo)} of {len(units)} units to run", flush=True)
        if self.dry:
            for w, s, v in todo:
                cmd = [self.py, "tools/eval/expw_w1.py", "--workload", w, "--seed", str(s), "--dry_run", "--out_root", str(out_root), "--calls", "330"]
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
                cmd = [".venv/bin/python", "tools/eval/expw_w1.py", "--workload", w, "--seed", str(s), "--gpu_id", "0", "--loveu_dir", LOVEU_DIR]
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
                    for d in ag.glob(f"results/evaluation/expW_W1/{w}_s{s}{('_' + tag) if tag else ''}_2*"):
                        loc = ROOT / d; loc.mkdir(parents=True, exist_ok=True)
                        for f in ("w1_calls.csv", "w1_summary.json"):
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


def v_args(c: Ctx, cell: int, reps="3", policies=("reuse_aware_in", "split", "reuse_dyn", "reuse_dyn2")):
    pp, path, deg = V_CELLS[cell]
    a = ["--pp_configs", ",".join(f"{p}:{pp}" for p in policies), "--path", path, "--tm", "1e9", "--lookahead", "4" if c.dry else "10", "--budget", "1",
         "--reps", reps, "--post_chunks", "400", "--max_run_s", "900"]
    if deg:
        kind, node, capv = deg.split(":"); d, mbps = capv.split("=")
        a += ["--cap_events", f"{kind}:{node}:{d}={float(mbps) / 10 if c.dry else mbps}"]
    return a


def do_m3dev(c):
    for cell in (7, 8, 9, 10):
        c.orch(f"m3dev_cell{cell}", n_args(c, cell, reps="1", policies=("reuse_aware_in", "reuse_dyn", "reuse_dyn2")), ["--sink_fp"], f"M3-v2 dev regression N cell {cell} ({N_LABEL[cell]})")


def do_v(c):
    for cell in V_CELLS:
        c.orch(f"expV_cell{cell}", v_args(c, cell), ["--sink_fp"], f"V cell {cell} ({V_LABEL[cell]})")


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
    ap.add_argument("what", choices=["list", "setup", "shakedown", "w1", "w2", "r", "n", "war", "all", "m3dev", "v"])
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--dry_promote", default="", help="dry: calls at which bound fake Sinks change (version-event accounting test)")
    ap.add_argument("--agent_hosts", default=None)
    ap.add_argument("--wait_s", type=int, default=1800)
    ap.add_argument("--py", default=os.environ.get("PY") or (str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable))
    a = ap.parse_args()
    c = Ctx(a)
    try:
        if a.what == "all":
            for f in (do_w1, do_w2, do_r, do_n, do_war):
                f(c)
        else:
            {"list": do_list, "setup": do_setup, "shakedown": do_shakedown, "w1": do_w1, "w2": do_w2, "r": do_r, "n": do_n, "war": do_war, "m3dev": do_m3dev, "v": do_v}[a.what](c)
    finally:
        c.stop_dry()
    if c.failures:
        print("[wrn] FAILED invocations:\n  " + "\n  ".join(c.failures), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
