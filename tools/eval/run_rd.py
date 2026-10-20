#!/usr/bin/env python3
"""Experiment RD driver (preregistration frozen f850072). Run on elves-01 (host A); B / C / D through their agents.

    python tools/eval/run_rd.py preflight      # agents, one commit, GPU 0 idle, OpenCV, workload files on every host
    python tools/eval/run_rd.py phase0         # Phase 0 fidelity replay + gate (exit 2 if the gate fails)
    python tools/eval/run_rd.py phase1         # Phase 1 (refuses unless the Phase 0 gate passed) + aggregation
    python tools/eval/run_rd.py all            # preflight -> phase0 -> gate -> phase1 -> aggregation; stops at a failed gate
    python tools/eval/run_rd.py all --dry      # the same on the local fake runtime (gate not meaningful; continues)

Phase 2 (real migration) is not part of this driver.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import rd_schedule as rs  # noqa: E402

LOVEU_DIR = "data/loveu_tgve_2023"
PY = ".venv/bin/python"
PHASE0_HOSTS = {"A": ("butterfly-feeding-slow-motion", ["P0-1_W2_bfly", "P0-2_VA_bfly_rho1_split"]), "B": ("butterfly-feeding-slow-motion", ["P0-3_VA_bfly_rho0.5_split"]),
                "C": ("butterfly-feeding-slow-motion", ["P0-4_VA_bfly_rho0.5_restart_fresh"]), "D": ("dog", ["P0-5_VA_dog_rho1_split"])}
PHASE1_HOSTS = {"A": "butterfly-feeding-slow-motion", "B": "audi-snow-trail", "C": "train", "D": "dog"}
MAX_RERUNS = 2   # followup_common.md section 3
LOG = "results/evaluation/wrn_logs"


def agents(spec):
    from agents import Agent, parse_hosts
    return {lb: Agent(lb, *hp) for lb, hp in parse_hosts(spec).items() if lb in "ABCD"}


def preflight(a) -> bool:
    if a.dry:
        print("[rd] preflight skipped (dry)"); return True
    bad = []
    r = subprocess.run([sys.executable, "tools/eval/d0_remote.py", "gpu_idle"], cwd=ROOT)
    if r.returncode != 0:
        bad.append("GPU 0 not idle on all hosts or repos on different commits (d0_remote gpu_idle)")
    for lb, ag in agents(a.agent_hosts).items():
        try:
            cv = ag.exec([PY, "-c", "import cv2; print(cv2.__version__)"], timeout=60)
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{lb}: agent unreachable ({exc})"); continue
        if cv.get("rc") != 0:
            bad.append(f"{lb}: OpenCV not importable in {PY} (frozen D4; installing opencv-python-headless needs the user's approval)")
        else:
            print(f"[rd] {lb}: OpenCV {cv['stdout'].strip()}")
        for w in set([PHASE1_HOSTS[lb], PHASE0_HOSTS[lb][0]]):
            if w in ("dog", "train"):
                continue
            ls = ag.exec(["ls", f"{LOVEU_DIR}/{w}.mp4"], timeout=30)
            if ls.get("rc") != 0:
                bad.append(f"{lb}: {LOVEU_DIR}/{w}.mp4 missing")
    print("[rd] preflight: " + ("OK" if not bad else "FAILED\n  " + "\n  ".join(bad)), flush=True)
    return not bad


def run_units(a, phase, plan: dict, extra: dict | None = None) -> None:
    """plan: {host: (workload, [condition ids] or None)}; one process per host; results copied back to A; invalid
    conditions re-run (<= 2 times)."""
    if a.dry:
        for lb, (w, ids) in plan.items():
            cmd = [sys.executable, "tools/eval/rd_emulate.py", "--workload", w, "--phase", str(phase), "--dry_run"] + (["--only", ",".join(ids)] if ids else []) + list((extra or {}).get(w, []))
            subprocess.run(cmd, cwd=ROOT, check=True)
        return
    ags = agents(a.agent_hosts)
    root = f"results/evaluation/expRD_phase{phase}"

    def one(lb, w, ids, attempt):
        ag = ags[lb]
        cmd = [PY, "tools/eval/rd_emulate.py", "--workload", w, "--phase", str(phase), "--gpu_id", "0", "--loveu_dir", LOVEU_DIR] + (["--only", ",".join(ids)] if ids else []) + list((extra or {}).get(w, []))
        pid = ag.run(cmd, f"{LOG}/rd_phase{phase}_{w}_{lb}{'_rerun' + str(attempt) if attempt else ''}.log")
        rc = ag.wait(pid, timeout=4 * 3600).get("rc")
        print(f"[rd] phase {phase} {w} on {lb}{' re-run ' + str(attempt) if attempt else ''}: rc {rc}", flush=True)
        if lb != "A":
            for d in ag.glob(f"{root}/{w}_s{rs.SEED}/*"):
                loc = ROOT / d
                if (loc / "summary.json").exists():
                    continue
                loc.mkdir(parents=True, exist_ok=True)
                for f in ("calls.csv", "summary.json"):
                    try:
                        (loc / f).write_text(ag.read(f"{d}/{f}"))
                    except RuntimeError as exc:
                        print(f"[rd] copy {d}/{f} from {lb}: {exc}", flush=True)

    def worker(lb, w, ids):
        one(lb, w, ids, 0)
        for attempt in (1, 2)[:MAX_RERUNS]:
            want = ids or [c["id"] for c in (rs.phase0(w) if str(phase) == "0" else rs.phase1(w))]
            done = {}
            for p in (ROOT / root / f"{w}_s{rs.SEED}").glob("*/summary.json"):
                s = json.load(open(p)); done[s["condition"]["id"]] = done.get(s["condition"]["id"], False) or bool(s.get("valid"))
            redo = [i for i in want if not done.get(i)]
            if not redo:
                return
            one(lb, w, redo, attempt)

    th = [threading.Thread(target=worker, args=(lb, w, ids)) for lb, (w, ids) in plan.items()]
    for t in th:
        t.start()
    for t in th:
        t.join()


RDX_HOSTS = {"A": "butterfly-feeding-slow-motion", "B": "audi-snow-trail", "C": "dog"}


def rdx(a):
    """RD-X (osdi/expRD/followup_rdx.md, exploratory): 6 real one-hop runs at 320 Mbps, then one emulation replay per
    run with its realized schedule, then the comparison table."""
    import run_wrn
    c = run_wrn.Ctx(argparse.Namespace(dry=a.dry, py=sys.executable if a.dry else PY, agent_hosts=a.agent_hosts, wait_s=1800, dry_promote="", tag="", cells=""))
    c.bw = "32" if a.dry else "320"   # dry: 64 MB fake Sink, the same ~80 Sink-less calls as 1.6 GB at 320 Mbps
    args = ["--policies", "split", "--hops", "1", "--tm", "1e9", "--reps", "1" if a.dry else "2", "--migration_chunk", "80", "--post_chunks", "200",
            "--horizon_calls", "190", "--max_run_s", "600"]
    for w in rs.RDX_WORKLOADS:
        c.orch(f"expRDX_{w}", args, run_wrn.node_extra(w, rs.SEED), f"RD-X {w} one hop {c.bw} Mbps")
    plan, extra = {}, {}
    for lb, w in RDX_HOSTS.items():
        conds = []
        for d in sorted((ROOT / "results/evaluation" / f"{'_dryrun_' if a.dry else ''}expRDX_{w}").glob("policy=split_*")):
            s = json.load(open(d / "summary.json"))
            if s["final"]["bind_call"] is None:
                print(f"[rd] RD-X {d.name}: no bind observed; no replay", flush=True); continue
            conds.append(rs.replay_from_run(s, f"RX_{w}_rep{s['rep']}"))
        if conds:
            plan[lb] = (w, [x["id"] for x in conds]); extra[w] = ["--replay_json", json.dumps(conds)]
    run_units(a, "x", plan, extra)
    subprocess.run([sys.executable, "tools/eval/aggregate_rd.py", "rdx"] + (["--dry"] if a.dry else []), cwd=ROOT, check=False)


def phase0(a) -> bool:
    run_units(a, 0, {lb: v for lb, v in PHASE0_HOSTS.items()})
    r = subprocess.run([sys.executable, "tools/eval/aggregate_rd.py", "phase0"] + (["--dry"] if a.dry else []), cwd=ROOT)
    return r.returncode == 0


def phase1(a):
    if not a.dry:
        g = ROOT / "results/evaluation/osdi/expRD/phase0_gate.json"
        if not g.exists() or json.load(open(g)).get("gate") != "PASS":
            sys.exit("[rd] Phase 1 refused: the Phase 0 gate has not passed (results/evaluation/osdi/expRD/phase0_gate.json)")
    run_units(a, 1, {lb: (w, None) for lb, w in PHASE1_HOSTS.items()})
    subprocess.run([sys.executable, "tools/eval/aggregate_rd.py", "phase1"] + (["--dry"] if a.dry else []), cwd=ROOT, check=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["preflight", "phase0", "phase1", "all", "rdx"])
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--agent_hosts", default=None)
    a = ap.parse_args()
    if a.what == "preflight":
        sys.exit(0 if preflight(a) else 1)
    if a.what == "rdx":
        if not preflight(a):
            sys.exit(1)
        rdx(a); return
    if a.what in ("phase0", "all"):
        if not preflight(a):
            sys.exit(1)
        ok = phase0(a)
        if not ok and not a.dry:
            sys.exit("[rd] STOP S1: the Phase 0 fidelity gate failed; Phase 1 not started (results/evaluation/osdi/expRD/phase0_gate.md)")
        if a.what == "phase0":
            return
    if a.what in ("phase1", "all"):
        if a.what == "phase1" and not preflight(a):
            sys.exit(1)
        phase1(a)


if __name__ == "__main__":
    main()
