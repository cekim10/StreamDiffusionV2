#!/usr/bin/env python3
"""Experiment VC driver (run on elves-01; osdi/expVC/implementation_plan.md sections 5-6). VC runs on host D's GPU 0
(C is the spare: --host C) while XB uses A and B. Frames stay on the VC host's local disk; only small result files
are copied back. Nothing is pulled or committed on the testbed by this script.

    python tools/eval/run_vc.py preflight --frames_dir /local/path      # D: local filesystem, free space, GPU, packages
    python tools/eval/run_vc.py models                                  # D: download DINO / DINOv2 / CLIP once (before XB starts)
    python tools/eval/run_vc.py vc0 --frames_dir /local/path            # D: metric self-test, dog OT-L / COLD-1 / WFS-1 -> G1, G2, G3
    python tools/eval/run_vc.py vd2 --frames_dir /local/path            # after the VD-2 freeze: reconstruction conditions on the VC units
    python tools/eval/run_vc.py vd3 --phase base --frames_dir /local/path   # Phase T (approved separately): seed-1 REF / controls, G1 / G3, distributions, overlap; stops for review
    python tools/eval/run_vc.py vd3 --phase cand --frames_dir /local/path --clips_dir /local/clips   # only after the VD-3 freeze with committed thresholds
    python tools/eval/run_vc.py vd3 --phase key --clips_dir /local/clips    # only after vd3_inspection.md is committed: copies the blind key
    python tools/eval/run_vc.py fetch --inputs dog                      # copy back VC-1 results only (no run)
    python tools/eval/run_vc.py vc1 --frames_dir /local/path            # only after the VC and VD freezes: VD precheck, then VC-1 + VD per input
    add --dry for a local run on the fake runtime (no agent)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))

PY = ".venv/bin/python"
LOG = "results/evaluation/vc_logs"
NONLOCAL = {"nfs", "nfs4", "cifs", "smb3", "smbfs", "fuse.sshfs", "lustre", "gpfs", "beegfs", "ceph", "fuse.ceph", "glusterfs", "tmpfs"}
MIN_FREE_GB = 20
INPUTS = ("dog", "train", "butterfly-feeding-slow-motion", "audi-snow-trail")
VC0 = {"input": "dog", "conditions": "OT-L,COLD-1,WFS-1"}


def agent(a):
    from agents import Agent, parse_hosts

    h, p = parse_hosts(a.agent_hosts)[a.host]
    ag = Agent(a.host, h, p); ag.ping()
    return ag


def sh(ag, cmd, timeout=120):
    r = ag.exec(cmd, timeout=timeout)
    return r.get("rc"), (r.get("stdout") or "").strip(), (r.get("stderr") or "").strip()


def nic_bytes(ag) -> dict:
    _, out, _ = sh(ag, ["cat", "/proc/net/dev"])
    res = {}
    for line in out.splitlines()[2:]:
        name, rest = line.split(":", 1)
        v = rest.split()
        res[name.strip()] = {"rx": int(v[0]), "tx": int(v[8])}
    return res


def preflight(a) -> bool:
    ag = agent(a)
    bad, info = [], {"host": a.host, "agent": ag.ping().get("host")}
    rc, fs, _ = sh(ag, ["findmnt", "-n", "-o", "FSTYPE,SOURCE,TARGET", "-T", a.frames_dir])
    info["frames_fs"] = fs
    if rc != 0 or not fs or fs.split()[0] in NONLOCAL:
        bad.append(f"frames dir {a.frames_dir} is not on a local disk filesystem ({fs or 'findmnt failed'})")
    rc, df, _ = sh(ag, ["df", "-BG", "--output=avail", a.frames_dir])
    try:
        free = int(df.splitlines()[-1].strip().rstrip("G")); info["frames_free_gb"] = free
        if free < MIN_FREE_GB:
            bad.append(f"only {free} GB free at {a.frames_dir} (need {MIN_FREE_GB})")
    except (ValueError, IndexError):
        bad.append(f"df failed for {a.frames_dir}: {df}")
    rc, g, _ = sh(ag, ["nvidia-smi", "-i", "0", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"])
    info["gpu0"] = g
    rc, procs, _ = sh(ag, ["nvidia-smi", "-i", "0", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"])
    info["gpu0_processes"] = procs or "none"
    if procs:
        bad.append(f"GPU 0 of {a.host} busy: {procs}")
    code = ("import importlib, json; out = {}\n"
            "for m in ('torch', 'cv2', 'skimage', 'av', 'open_clip'):\n"
            "    try: out[m] = getattr(importlib.import_module(m), '__version__', 'ok')\n"
            "    except Exception as e: out[m] = 'MISSING ' + repr(e)[:80]\n"
            "print(json.dumps(out))")
    rc, out, err = sh(ag, [PY, "-c", code], timeout=300)
    try:
        info["packages"] = json.loads(out.splitlines()[-1])
    except (ValueError, IndexError):
        info["packages"] = {"error": err[-300:]}
    for m, v in info["packages"].items():
        if str(v).startswith("MISSING"):
            bad.append(f"package {m} missing on {a.host}")
    rc, c, _ = sh(ag, ["git", "rev-parse", "HEAD"]); info["commit"] = c
    loc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if c != loc:
        bad.append(f"{a.host} on {c[:7]}, elves-01 on {loc[:7]}")
    info["problems"] = bad
    (ROOT / "results/evaluation/osdi/expVC/vc_preflight.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))
    print("PREFLIGHT OK" if not bad else "PREFLIGHT FAILED")
    return not bad


def models(a):
    ag = agent(a)
    code = ("import torch, open_clip\n"
            "torch.hub.load('facebookresearch/dino:main', 'dino_vitb16')\n"
            "torch.hub.load('facebookresearch/dinov2', 'dinov2_vitb14')\n"
            "open_clip.create_model_and_transforms('ViT-L-14', pretrained='openai')\n"
            "print('models cached')")
    pid = ag.run([PY, "-c", code], f"{LOG}/vc_models_{a.host}.log")
    rc = ag.wait(pid, timeout=3600).get("rc")
    print(f"[vc] model download on {a.host}: rc {rc} (log {LOG}/vc_models_{a.host}.log on that host)")
    return rc == 0


def remote_run(ag, cmd, log, timeout=4 * 3600) -> int:
    pid = ag.run(cmd, log)
    return ag.wait(pid, timeout=timeout).get("rc")


def copy_back(ag, pattern: str, names=("calls.csv", "summary.json")):
    for d in ag.glob(pattern):
        if Path(d).suffix:   # a file next to the condition directories (metrics.json, ...): not a condition
            continue
        loc = ROOT / d; loc.mkdir(parents=True, exist_ok=True)
        for f in names:
            try:
                (loc / f).write_text(ag.read(f"{d}/{f}"))
            except RuntimeError:
                pass


def vc0(a) -> bool:
    if a.dry:
        py = sys.executable
        out = "results/evaluation/_dryrun_expVC0"
        steps = [[py, "tools/eval/vc_metrics.py", "--selftest", "--embedders", "pixel", "--device", "cpu", "--out", "results/evaluation/osdi/expVC/_dryrun_vc0_metric_selftest.json"],
                 [py, "tools/eval/vc_emulate.py", "--input", VC0["input"], "--only", VC0["conditions"], "--dry_run", "--frames_dir", a.frames_dir, "--out_root", out],
                 [py, "tools/eval/vc_check.py", "--unit", f"{out}/dog_s0", "--g3", "--write"]]
        return all(subprocess.run(s, cwd=ROOT).returncode == 0 for s in steps)
    ag = agent(a)
    if not preflight(a):
        return False
    stamp = time.strftime("%Y%m%d-%H%M%S")
    nic0 = nic_bytes(ag)
    steps = [("metric self-test (DINO, DINOv2, CLIP on a repository clip)", [PY, "tools/eval/vc_metrics.py", "--selftest", "--embedders", "dino,dinov2,clip", "--device", "cuda:0"]),
             ("emulation dog OT-L, COLD-1, WFS-1", [PY, "tools/eval/vc_emulate.py", "--input", VC0["input"], "--only", VC0["conditions"], "--gpu_id", "0",
                                                    "--frames_dir", a.frames_dir, "--out_root", "results/evaluation/expVC0"]),
             ("G1 G2 G3", [PY, "tools/eval/vc_check.py", "--unit", "results/evaluation/expVC0/dog_s0", "--write"])]
    ok = True
    for what, cmd in steps:
        rc = remote_run(ag, cmd, f"{LOG}/vc0_{stamp}_{what.split()[0]}.log")
        print(f"[vc] {what} on {a.host}: rc {rc}", flush=True)
        ok &= rc == 0
        if rc != 0:
            break
    nic1 = nic_bytes(ag)
    copy_back(ag, "results/evaluation/expVC0/dog_s0/*")
    for f in ("vc0_checks.md", "vc0_checks.json", "vc0_metric_selftest.json"):
        try:
            (ROOT / "results/evaluation/osdi/expVC" / f).write_text(ag.read(f"results/evaluation/osdi/expVC/{f}"))
        except RuntimeError:
            pass
    nic = {k: {"rx": nic1[k]["rx"] - nic0[k]["rx"], "tx": nic1[k]["tx"] - nic0[k]["tx"]} for k in nic1 if k in nic0}
    (ROOT / "results/evaluation/osdi/expVC/vc0_isolation.json").write_text(json.dumps({"host": a.host, "nic_bytes_during_vc0": nic, "frames_dir": a.frames_dir}, indent=1))
    print("[vc] NIC bytes on the VC host during VC-0:", {k: v for k, v in nic.items() if v["rx"] or v["tx"]})
    print("[vc] VC-0", "ALL PASS" if ok else "FAILED - VC stops here")
    return ok


def fetch_unit(ag, inp: str, seed: int = 0, checks: str | None = None, root: str = "results/evaluation/expVC"):
    """Copy a VC-1 unit's small results from the VC host (frames stay there)."""
    unit = f"{root}/{inp}_s{seed}"
    bogus = ROOT / unit / "metrics.json"
    if bogus.is_dir() and not any(bogus.iterdir()):
        bogus.rmdir()   # left by the copy bug of 600d5b6 (an empty directory named like the file)
    copy_back(ag, f"{unit}/*")
    try:
        (ROOT / unit / "metrics.json").write_text(ag.read(f"{unit}/metrics.json"))
    except RuntimeError as exc:
        print(f"[vc] {unit}/metrics.json not copied: {exc}", flush=True)
    for suf in (".md", ".json"):
        name = checks or f"vc1_checks_{inp}"
        try:
            (ROOT / f"results/evaluation/osdi/expVC/{name}{suf}").write_text(ag.read(f"results/evaluation/osdi/expVC/{name}{suf}"))
        except RuntimeError as exc:
            print(f"[vc] {name}{suf} not copied: {exc}", flush=True)


def fetch(a) -> bool:
    """Copy back VC-1 results (and the VD precheck) without re-running anything."""
    ag = agent(a)
    try:
        (ROOT / "results/evaluation/osdi/expVD/vd_precheck.json").write_text(ag.read("results/evaluation/osdi/expVD/vd_precheck.json"))
    except RuntimeError as exc:
        print(f"[vc] vd_precheck.json not copied: {exc}", flush=True)
    for inp in [x for x in (a.inputs or "").split(",") if x] or list(INPUTS):
        fetch_unit(ag, inp)
        print(f"[vc] fetched {inp}", flush=True)
    return True


def vc1(a) -> bool:
    """VC-1 + VD in one unit per input (frozen expVC / expVD): VD precheck (dog), then per input the emulation of every
    condition (VC's seven first, then VD's sixteen for dog and butterfly), G3 (+ G1 for dog: the frozen M1 replay must
    still equal the real RD-X run with the VD flag in the code), metrics. Small files are copied back; frames stay."""
    if not a.dry and not ((ROOT / "results/evaluation/osdi/expVC_freeze.md").exists() and (ROOT / "results/evaluation/osdi/expVD_freeze.md").exists()):
        sys.exit("[vc] VC / VD are not frozen (expVC_freeze.md / expVD_freeze.md missing): VC-1 does not run")
    only = [x for x in (a.inputs or "").split(",") if x] or list(INPUTS)
    if a.dry:
        py, out = sys.executable, "results/evaluation/_dryrun_expVC"
        ok = True
        for inp in only:
            for cmd in ([py, "tools/eval/vc_emulate.py", "--input", inp, "--dry_run", "--frames_dir", a.frames_dir, "--out_root", out],
                        [py, "tools/eval/vc_check.py", "--unit", f"{out}/{inp}_s0", "--g3", "--write", "--name", f"vc1_checks_{inp}"],
                        [py, "tools/eval/vc_metrics.py", "--unit", f"{out}/{inp}_s0", "--embedders", "pixel", "--device", "cpu"]):
                ok &= subprocess.run(cmd, cwd=ROOT).returncode == 0
        return ok
    ag = agent(a)
    if not preflight(a):
        return False
    stamp = time.strftime("%Y%m%d-%H%M%S")
    nic0 = nic_bytes(ag)
    ok = True
    if "dog" in only:
        rc = remote_run(ag, [PY, "tools/eval/vd_precheck.py", "--input", "dog", "--gpu_id", "0"], f"{LOG}/vc1_{stamp}_vd_precheck.log", timeout=3600)
        print(f"[vc] VD precheck on {a.host}: rc {rc}", flush=True)
        try:
            (ROOT / "results/evaluation/osdi/expVD/vd_precheck.json").write_text(ag.read("results/evaluation/osdi/expVD/vd_precheck.json"))
        except RuntimeError:
            pass
    for inp in only:
        unit = f"results/evaluation/expVC/{inp}_s0"
        checks = ["--g1", "--g3"] if inp == "dog" else ["--g3"]
        for what, cmd in (("emulation", [PY, "tools/eval/vc_emulate.py", "--input", inp, "--gpu_id", "0", "--frames_dir", a.frames_dir, "--out_root", "results/evaluation/expVC"]),
                          ("checks", [PY, "tools/eval/vc_check.py", "--unit", unit, "--write", "--name", f"vc1_checks_{inp}"] + checks),
                          ("metrics", [PY, "tools/eval/vc_metrics.py", "--unit", unit, "--embedders", "dino,dinov2,clip", "--device", "cuda:0"])):
            rc = remote_run(ag, cmd, f"{LOG}/vc1_{stamp}_{inp}_{what}.log")
            print(f"[vc] {inp} {what} on {a.host}: rc {rc}", flush=True)
            if rc != 0:
                ok = False
                if what != "metrics":
                    break
        fetch_unit(ag, inp)
    nic1 = nic_bytes(ag)
    nic = {k: {"rx": nic1[k]["rx"] - nic0[k]["rx"], "tx": nic1[k]["tx"] - nic0[k]["tx"]} for k in nic1 if k in nic0}
    (ROOT / "results/evaluation/osdi/expVC/vc1_isolation.json").write_text(json.dumps({"host": a.host, "nic_bytes_during_vc1": nic, "frames_dir": a.frames_dir}, indent=1))
    print("[vc] VC-1", "done" if ok else "had failures (see the logs and vc1_checks_*)", "- next on elves-01: aggregate_vc.py, aggregate_vd.py")
    return ok


def vd2_ids(inp: str, with_dr4: bool) -> list[str]:
    sched = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())["inputs"][inp]
    return [c["id"] for c in sched["conditions"] if c["kind"] == "vd2" and (with_dr4 or not c.get("exploratory"))]


def vd2(a) -> bool:
    """Experiment VD-2 (frozen expVD2): the reconstruction conditions on the existing VC units (REF frames reused), then
    G3 and metrics merged into the unit's metrics.json. DR-4 only with --with_dr4 (section-4 trigger)."""
    if not a.dry and not (ROOT / "results/evaluation/osdi/expVD2_freeze.md").exists():
        sys.exit("[vc] VD-2 is not frozen (results/evaluation/osdi/expVD2_freeze.md missing): no run")
    inputs = [x for x in (a.inputs or "").split(",") if x] or ["dog", "butterfly-feeding-slow-motion"]
    if a.dry:
        out, py, ok = "results/evaluation/_dryrun_expVC", sys.executable, True
        for inp in inputs:
            ids = ",".join(vd2_ids(inp, a.with_dr4))
            for cmd in ([py, "tools/eval/vc_emulate.py", "--input", inp, "--dry_run", "--frames_dir", a.frames_dir, "--out_root", out, "--only", ids, "--no_ref_frames"],
                        [py, "tools/eval/vc_check.py", "--unit", f"{out}/{inp}_s0", "--g3", "--write", "--name", f"vd2_checks_{inp}"],
                        [py, "tools/eval/vc_metrics.py", "--unit", f"{out}/{inp}_s0", "--embedders", "pixel", "--device", "cpu", "--only", ids, "--merge"]):
                ok &= subprocess.run(cmd, cwd=ROOT).returncode == 0
        return ok
    ag = agent(a)
    if not preflight(a):
        return False
    stamp = time.strftime("%Y%m%d-%H%M%S")
    nic0 = nic_bytes(ag); ok = True
    for inp in inputs:
        unit = f"results/evaluation/expVC/{inp}_s0"
        ids = ",".join(vd2_ids(inp, a.with_dr4))
        for what, cmd in (("emulation", [PY, "tools/eval/vc_emulate.py", "--input", inp, "--gpu_id", "0", "--frames_dir", a.frames_dir, "--out_root", "results/evaluation/expVC", "--only", ids, "--no_ref_frames", "--skip_done"]),
                          ("checks", [PY, "tools/eval/vc_check.py", "--unit", unit, "--g3", "--write", "--name", f"vd2_checks_{inp}"]),
                          ("metrics", [PY, "tools/eval/vc_metrics.py", "--unit", unit, "--embedders", "dino,dinov2,clip", "--device", "cuda:0", "--only", ids, "--merge"])):
            rc = remote_run(ag, cmd, f"{LOG}/vd2_{stamp}_{inp}_{what}.log")
            print(f"[vc] VD-2 {inp} {what} on {a.host}: rc {rc}", flush=True)
            if rc != 0:
                ok = False
                if what != "metrics":
                    break
        fetch_unit(ag, inp)
        for suf in (".md", ".json"):
            try:
                (ROOT / f"results/evaluation/osdi/expVC/vd2_checks_{inp}{suf}").write_text(ag.read(f"results/evaluation/osdi/expVC/vd2_checks_{inp}{suf}"))
            except RuntimeError:
                pass
    nic1 = nic_bytes(ag)
    nic = {k: {"rx": nic1[k]["rx"] - nic0[k]["rx"], "tx": nic1[k]["tx"] - nic0[k]["tx"]} for k in nic1 if k in nic0}
    (ROOT / "results/evaluation/osdi/expVD2/vd2_isolation.json").write_text(json.dumps({"host": a.host, "nic_bytes_during_vd2": nic, "frames_dir": a.frames_dir}, indent=1))
    print("[vc] VD-2", "done" if ok else "had failures", "- next on elves-01: aggregate_vd2.py")
    return ok


VD3_SEEDS = (0, 1)
VD3_OUT = "results/evaluation/osdi/expVD3"


def vd3_ids(inp: str, seed: int) -> list[str]:
    import vc_schedules as vs

    u = vs.unit_sched(json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text()), f"{inp}_s{seed}")
    return [c["id"] for c in u["conditions"] if c["kind"] == "vd3"]


def committed(path: str) -> bool:
    r = subprocess.run(["git", "log", "-1", "--format=%H", "--", path], cwd=ROOT, capture_output=True, text=True)
    clean = subprocess.run(["git", "status", "--porcelain", "--", path], cwd=ROOT, capture_output=True, text=True).stdout.strip() == ""
    return bool(r.stdout.strip()) and clean


def vd3(a) -> bool:
    """Experiment VD-3 (osdi/expVD3/preregistration.md): three phases with review gates.
    base (Phase T; needs expVD3_phaseT_approval.md, not the freeze): seed-1 units (REF + frozen-M1 OT-1 / OT-L
          controls), G1 (OT-1 vs the real W2 seed-1 run) and G3, metrics, then the Phase T distributions (REF variation,
          measurement noise, cross-seed sensitivity, frozen-M1 context) and the overlap measurement; stops for review.
    cand: only after the freeze (expVD3_freeze.md) with vd3_thresholds.json committed: the six VD-3 conditions on all
          eight units, G3, merged metrics, then the blinded clips and the inspection form. Verdicts wait for the
          recorded inspection.
    key:  only when vd3_inspection.md is committed with STATUS: RECORDED: copies the sealed key."""
    if not a.dry and a.phase in ("base", "overlap") and not (ROOT / "results/evaluation/osdi/expVD3_phaseT_approval.md").exists():
        sys.exit("[vc] Phase T is not approved (results/evaluation/osdi/expVD3_phaseT_approval.md missing): no run")
    if not a.dry and a.phase in ("cand", "key") and not (ROOT / "results/evaluation/osdi/expVD3_freeze.md").exists():
        sys.exit("[vc] VD-3 is not frozen (results/evaluation/osdi/expVD3_freeze.md missing): no candidate run")
    inputs = [x for x in (a.inputs or "").split(",") if x] or list(INPUTS)
    if a.phase == "overlap":   # Phase T's overlap measurement alone (re-run)
        ag = agent(a)
        if not preflight(a):
            return False
        rc = remote_run(ag, [PY, "tools/eval/vd3_overlap.py", "--input", "dog", "--seed", "0", "--schedule", "OT-1", "--reps", "5", "--gpu_id", "0"],
                        f"{LOG}/vd3_{time.strftime('%Y%m%d-%H%M%S')}_overlap.log", timeout=3600)
        print(f"[vc] VD-3 overlap on {a.host}: rc {rc}", flush=True)
        try:
            (ROOT / VD3_OUT / "vd3_overlap.json").write_text(ag.read(f"{VD3_OUT}/vd3_overlap.json"))
        except RuntimeError as exc:
            print(f"[vc] vd3_overlap.json not copied: {exc}"); return False
        return rc == 0
    if a.phase == "key":
        insp = ROOT / VD3_OUT / "vd3_inspection.md"
        if not (insp.exists() and "STATUS: RECORDED" in insp.read_text() and committed(f"{VD3_OUT}/vd3_inspection.md")):
            sys.exit("[vc] vd3_inspection.md is not recorded and committed: the key stays sealed")
        import base64
        import gzip
        import hashlib
        import re

        ag = agent(a)
        # the key lives outside the repository (the agent's read is repository-only): fetched compressed through exec
        r = ag.exec(["bash", "-c", f"gzip -c {a.clips_dir}/sealed/vd3_blind_key.json | base64 -w0"], timeout=60)
        if r.get("rc") != 0:
            sys.exit(f"[vc] key not readable on {a.host}: {r.get('stderr')}")
        kb = gzip.decompress(base64.b64decode(r["stdout"].strip()))
        form = (ROOT / VD3_OUT / "vd3_inspection_form.md").read_text()
        want = re.search(r"SHA-256 `([0-9a-f]{64})`", form).group(1)
        got = hashlib.sha256(kb).hexdigest()
        if got != want:
            sys.exit(f"[vc] key SHA-256 {got[:16]} differs from the form's {want[:16]}: not saved")
        (ROOT / VD3_OUT / "vd3_blind_key.json").write_bytes(kb)
        print("[vc] key copied to", f"{VD3_OUT}/vd3_blind_key.json", f"(SHA-256 {got[:16]} = the form's) - next: aggregate_vd3.py")
        return True
    if a.phase == "cand" and not a.dry and not committed(f"{VD3_OUT}/vd3_thresholds.json"):
        sys.exit("[vc] vd3_thresholds.json is not committed: the thresholds are chosen from the Phase T review and frozen before any candidate runs")
    if a.dry:
        py, out, ok = sys.executable, "results/evaluation/_dryrun_expVC", True
        for inp in inputs:
            for sd in VD3_SEEDS:
                unit = f"{out}/{inp}_s{sd}"
                if a.phase == "base" and sd == 1:
                    steps = [[py, "tools/eval/vc_emulate.py", "--input", inp, "--seed", "1", "--dry_run", "--frames_dir", a.frames_dir, "--out_root", out],
                             [py, "tools/eval/vc_check.py", "--unit", unit, "--g3", "--write", "--name", f"vd3_checks_{inp}_s1"],
                             [py, "tools/eval/vc_metrics.py", "--unit", unit, "--embedders", "pixel", "--device", "cpu"]]
                elif a.phase == "cand":
                    ids = ",".join(vd3_ids(inp, sd))
                    steps = [[py, "tools/eval/vc_emulate.py", "--input", inp, "--seed", str(sd), "--dry_run", "--frames_dir", a.frames_dir, "--out_root", out, "--only", ids, "--no_ref_frames", "--skip_done"],
                             [py, "tools/eval/vc_check.py", "--unit", unit, "--g3", "--write", "--name", f"vd3_checks_{inp}_s{sd}"],
                             [py, "tools/eval/vc_metrics.py", "--unit", unit, "--embedders", "pixel", "--device", "cpu", "--only", ids, "--merge"]]
                else:
                    steps = []
                for cmd in steps:
                    ok &= subprocess.run(cmd, cwd=ROOT).returncode == 0
        if a.phase == "base":
            ok &= subprocess.run([py, "tools/eval/vd3_phaseT.py", "--root", out, "--inputs", ",".join(inputs), "--embedder", "pixel", "--device", "cpu", "--dry"], cwd=ROOT).returncode == 0
            ok &= subprocess.run([py, "tools/eval/vd3_overlap.py", "--dry_run", "--reps", "2"], cwd=ROOT).returncode == 0
        else:
            ok &= subprocess.run([py, "tools/eval/vc_export_clips.py", "--root", out, "--clips_dir", a.clips_dir, "--order_seed", "1", "--inputs", ",".join(inputs),
                                  "--form", f"{VD3_OUT}/_dryrun_vd3_inspection_form.md"], cwd=ROOT).returncode == 0
        return ok
    ag = agent(a)
    if not preflight(a):
        return False
    stamp = time.strftime("%Y%m%d-%H%M%S")
    nic0 = nic_bytes(ag); ok = True
    for inp in inputs:   # the seed-0 REF frames (VC-1) must still be on the VC host's disk
        s0 = json.loads((ROOT / f"results/evaluation/expVC/{inp}_s0/REF/summary.json").read_text())
        rc, _, _ = sh(ag, ["test", "-d", s0["frames"]])
        if rc != 0:
            print(f"[vc] seed-0 REF frames of {inp} missing on {a.host}: {s0['frames']}"); return False
    if a.phase == "base":
        for inp in inputs:
            unit = f"results/evaluation/expVC/{inp}_s1"
            for what, cmd in (("emulation", [PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", "1", "--gpu_id", "0", "--frames_dir", a.frames_dir, "--out_root", "results/evaluation/expVC", "--skip_done"]),
                              ("checks", [PY, "tools/eval/vc_check.py", "--unit", unit, "--g1", "--g1_cond", "OT-1", "--g3", "--write", "--name", f"vd3_checks_{inp}_s1"]),
                              ("metrics", [PY, "tools/eval/vc_metrics.py", "--unit", unit, "--embedders", "dino,dinov2,clip", "--device", "cuda:0"])):
                rc = remote_run(ag, cmd, f"{LOG}/vd3_{stamp}_{inp}_s1_{what}.log")
                print(f"[vc] VD-3 base {inp} s1 {what} on {a.host}: rc {rc}", flush=True)
                if rc != 0:
                    ok = False; break
            fetch_unit(ag, inp, 1, f"vd3_checks_{inp}_s1")
            if not ok:
                break
        if ok:
            for what, cmd in (("phaseT", [PY, "tools/eval/vd3_phaseT.py", "--root", "results/evaluation/expVC", "--embedder", "dino", "--device", "cuda:0"]),
                              ("overlap", [PY, "tools/eval/vd3_overlap.py", "--input", "dog", "--seed", "0", "--schedule", "OT-1", "--reps", "5", "--gpu_id", "0"])):
                rc = remote_run(ag, cmd, f"{LOG}/vd3_{stamp}_{what}.log", timeout=3 * 3600)
                print(f"[vc] VD-3 base {what} on {a.host}: rc {rc}", flush=True)
                ok &= rc == 0
            for f in ("vd3_phaseT.json", "vd3_phaseT.md", "vd3_overlap.json"):
                try:
                    (ROOT / VD3_OUT / f).write_text(ag.read(f"{VD3_OUT}/{f}"))
                except RuntimeError as exc:
                    print(f"[vc] {f} not copied: {exc}"); ok = False
        print("[vc] VD-3 Phase T", "done - push; the distributions (vd3_phaseT.md) are reviewed before any threshold is frozen" if ok else "had failures")
    else:
        for inp in inputs:
            for sd in VD3_SEEDS:
                unit = f"results/evaluation/expVC/{inp}_s{sd}"
                ids = ",".join(vd3_ids(inp, sd))
                for what, cmd in (("emulation", [PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", str(sd), "--gpu_id", "0", "--frames_dir", a.frames_dir, "--out_root", "results/evaluation/expVC", "--only", ids, "--no_ref_frames", "--skip_done"]),
                                  ("checks", [PY, "tools/eval/vc_check.py", "--unit", unit, "--g3", "--write", "--name", f"vd3_checks_{inp}_s{sd}"]),
                                  ("metrics", [PY, "tools/eval/vc_metrics.py", "--unit", unit, "--embedders", "dino,dinov2,clip", "--device", "cuda:0", "--only", ids, "--merge"])):
                    rc = remote_run(ag, cmd, f"{LOG}/vd3_{stamp}_{inp}_s{sd}_{what}.log")
                    print(f"[vc] VD-3 {inp} s{sd} {what} on {a.host}: rc {rc}", flush=True)
                    if rc != 0:
                        ok = False
                        if what != "metrics":
                            break
                fetch_unit(ag, inp, sd, f"vd3_checks_{inp}_s{sd}")
        if ok:
            rc = remote_run(ag, [PY, "tools/eval/vc_export_clips.py", "--root", "results/evaluation/expVC", "--clips_dir", a.clips_dir, "--order_seed", time.strftime("%Y%m%d")],
                            f"{LOG}/vd3_{stamp}_clips.log", timeout=3 * 3600)
            print(f"[vc] VD-3 clips on {a.host}: rc {rc} -> {a.clips_dir} (on {a.host}; never committed)", flush=True)
            try:
                (ROOT / VD3_OUT / "vd3_inspection_form.md").write_text(ag.read(f"{VD3_OUT}/vd3_inspection_form.md"))
            except RuntimeError as exc:
                print(f"[vc] form not copied: {exc}"); ok = False
        print("[vc] VD-3 candidates", "done - next: the blinded inspection (fill vd3_inspection.md, commit), then --phase key, then aggregate_vd3.py" if ok else "had failures")
    nic1 = nic_bytes(ag)
    nic = {k: {"rx": nic1[k]["rx"] - nic0[k]["rx"], "tx": nic1[k]["tx"] - nic0[k]["tx"]} for k in nic1 if k in nic0}
    (ROOT / VD3_OUT / f"vd3_isolation_{a.phase}.json").write_text(json.dumps({"host": a.host, "nic_bytes": nic, "frames_dir": a.frames_dir}, indent=1))
    return ok


VD4_OUT = "results/evaluation/osdi/expVD4"


def vd4_plan(stage: str, gates: dict) -> tuple[dict, list]:
    """{unit: [condition ids]} and the inspection sessions [(name, shown conditions, cells)] of a VD-4 stage
    (preregistration section 5). Stage 2b's cells and stage 3's existence come from the aggregated gates."""
    import aggregate_vd4 as a4

    def plan(cells, names):
        out = {}
        for k in cells:
            unit, ot = k.split("|"); x = ot.split("-")[1]
            out.setdefault(unit, []).extend(f"VD4{x}-{n}" for n in names)
        return out
    if stage == "0":
        return plan(a4.STAGE0, list(a4.STAGE0_NAMES)), []
    if stage == "0r":   # addendum 1b: A1 again on the four stage-0 cells with per-row position logging / verification (own root)
        return plan(a4.STAGE0, ["A1"]), []
    if stage in ("0a", "0a2"):   # addendum 2 / 2a: the corrected (row-wise) A1 on the four stage-0 cells (own root each)
        return plan(a4.STAGE0, ["A1"]), []
    if stage == "0s":   # addendum 1: A1 again on the four stage-0 cells, D and R on one cell (own root; stage-0 results untouched)
        p_ = plan(a4.STAGE0, ["A1"])
        for unit, ids in plan([a4.SUPP_DR_CELL], ["D", "R"]).items():
            p_.setdefault(unit, []).extend(ids)
        return p_, []
    if stage == "1":
        return plan(a4.CONFIRM, ["B0", "DR", "D", "R", "A1"]), [(sn, ["DR", "D", "R", "A1"], cells) for sn, cells in a4.STAGE1_SESSIONS.items()]
    if stage == "2":
        return plan(a4.CONFIRM, ["B0", "S3"]), [("stage2", ["S3"], a4.CONFIRM)]
    if stage == "2b":
        cells = gates.get("stage2b_cells")
        if not cells:
            sys.exit("[vc] stage 2b: stage 2 is not inspected and aggregated yet (vd4_gates.json)")
        p_ = plan(cells, ["B0", "S1", "S2"])
        for unit, ids in plan(a4.SUBSET4, ["A1S1", "A1S2"]).items():   # exploratory, always on the four-cell subset
            p_.setdefault(unit, []).extend(ids)
        return p_, [("stage2b", ["S1", "S2", "A1S1", "A1S2"], sorted(set(cells) | set(a4.SUBSET4)))]
    if stage == "3":
        if not gates.get("stage3_runs"):
            sys.exit("[vc] stage 3 runs only if S3 resolved a P2 phase (vd4_gates.json)")
        return plan(a4.SUBSET4, ["B0", "Q8", "Q4"]), [("stage3", ["Q8", "Q4"], a4.SUBSET4)]
    sys.exit(f"[vc] unknown VD-4 stage {stage}")


def a4_supp_root(a) -> str:
    import aggregate_vd4 as a4

    return f"{a.dry_root}_vd4s" if a.dry else str(a4.SUPP_ROOT.relative_to(ROOT))


def preserve_stage0_a1(root_rel: str, units: dict, exists, read, move) -> list:
    """Stage 1 (addendum 2 / 2a): the stage-0 A1 runs in the main root were produced by the first implementation (row 0's
    deltas on every row). They are preserved under `VD4x-A1.stage0` so that stage 1 re-runs A1 with the validated
    row-wise implementation (vc_emulate's --skip_done would otherwise reuse them). A run that already carries the
    per-row records (`supp.a1_per_layer_row_slot`) is the corrected one and stays. Returns the moved paths."""
    import aggregate_vd4 as a4

    moved = []
    for unit, ids in units.items():
        for cid in ids:
            if not cid.endswith("-A1"):
                continue
            src = f"{root_rel}/{unit}/{cid}"
            if not exists(f"{src}/summary.json"):
                continue
            s = json.loads(read(f"{src}/summary.json"))
            if ((s.get("vd4") or {}).get("supp") or {}).get("a1_per_layer_row_slot"):
                continue
            dst = f"{src}{a4.STAGE0_A1_SUFFIX}"
            if exists(f"{dst}/summary.json"):
                sys.exit(f"[vc] {dst} already exists: refusing to overwrite a preserved stage-0 run")
            move(src, dst); moved.append(dst)
    return moved


def a4_a1_root(a, n: int = 1) -> str:
    import aggregate_vd4 as a4

    return f"{a.dry_root}_vd4a{'' if n == 1 else n}" if a.dry else str((a4.A1_ROOT if n == 1 else a4.A1_ROOT2).relative_to(ROOT))


def a4_rows_root(a) -> str:
    import aggregate_vd4 as a4

    return f"{a.dry_root}_vd4r" if a.dry else str(a4.ROWS_ROOT.relative_to(ROOT))


def vd4(a) -> bool:
    """Experiment VD-4 (osdi/expVD4/preregistration.md): one stage per call; each refuses before the freeze and before
    its gate (vd4_gates.json from aggregate_vd4.py); a stage with an inspection session ends with the blinded clips and
    the form; --phase key copies that session's sealed key once its inspection is committed."""
    gates_p = ROOT / VD4_OUT / ("_dryrun_vd4_gates.json" if a.dry else "vd4_gates.json")
    gates = json.loads(gates_p.read_text()) if gates_p.exists() else {}
    if not a.dry and not (ROOT / "results/evaluation/osdi/expVD4_freeze.md").exists():
        sys.exit("[vc] VD-4 is not frozen (results/evaluation/osdi/expVD4_freeze.md missing): no run")
    if a.stage != "0" and not a.dry and not gates.get("stage0_valid"):
        sys.exit("[vc] stage 0 validity (V0 = REF, B0 = VD-3) has not passed: no further stage")
    if a.stage not in ("0", "0s", "0r") and not a.dry and not gates.get("stage0_supp_valid"):
        sys.exit("[vc] the supplemental stage-0 validation (addendum 1: --stage 0s) has not passed: no further stage")
    if a.stage not in ("0", "0s", "0r", "0a", "0a2") and not a.dry and not gates.get("stage0_rows_valid"):
        sys.exit("[vc] the batch-row position validation (addendum 1b: --stage 0r) has not passed: no further stage")
    if a.stage not in ("0", "0s", "0r", "0a", "0a2") and not a.dry and not gates.get("stage0_a1_rows_valid"):   # addendum 2 replaces the batch_rows_identical requirement
        sys.exit("[vc] the corrected A1 validation (addendum 2a: --stage 0a2) has not passed: no further stage")
    if a.stage == "0a" and not a.dry and ((ROOT / a4_a1_root(a)).exists() or (ROOT / VD4_OUT / "addendum2a.md").exists()):
        sys.exit("[vc] stage 0a ran once (52a1c461; its results are preserved) - the rerun with the corrected reference is --stage 0a2 (addendum 2a)")
    if a.stage == "0a" and not a.dry and not (ROOT / VD4_OUT / "addendum2.md").exists():
        sys.exit("[vc] addendum 2 (results/evaluation/osdi/expVD4/addendum2.md) is missing: no run")
    if a.stage == "0a2" and not a.dry and not (ROOT / VD4_OUT / "addendum2a.md").exists():
        sys.exit("[vc] addendum 2a (results/evaluation/osdi/expVD4/addendum2a.md) is missing: no run")
    if a.stage == "0s" and not a.dry and not (ROOT / VD4_OUT / "addendum1.md").exists():
        sys.exit("[vc] addendum 1 (results/evaluation/osdi/expVD4/addendum1.md) is missing: no run")
    if a.stage == "0r" and not a.dry and not (ROOT / VD4_OUT / "addendum1b.md").exists():
        sys.exit("[vc] addendum 1b (results/evaluation/osdi/expVD4/addendum1b.md) is missing: no run")
    out_rel = {"0s": a4_supp_root(a), "0r": a4_rows_root(a), "0a": a4_a1_root(a), "0a2": a4_a1_root(a, 2)}.get(a.stage, "results/evaluation/expVC" if not a.dry else a.dry_root)
    chk_name = {"0s": "vd4s_checks_", "0r": "vd4r_checks_", "0a": "vd4a_checks_", "0a2": "vd4a2_checks_"}.get(a.stage, "vd4_checks_")
    units, sessions = vd4_plan(a.stage, gates)
    if a.phase == "key":
        names_ = [x[0] for x in sessions]
        if a.session not in names_:
            sys.exit(f"[vc] --session must be one of {names_ or 'none (this stage has no inspection)'}")
        import base64
        import gzip
        import hashlib
        import re

        sname = a.session
        insp = ROOT / VD4_OUT / f"vd4_inspection_{sname}.md"
        if not (insp.exists() and "STATUS: RECORDED" in insp.read_text() and committed(f"{VD4_OUT}/vd4_inspection_{sname}.md")):
            sys.exit(f"[vc] vd4_inspection_{sname}.md is not recorded and committed: the key stays sealed")
        ag = agent(a)
        r = ag.exec(["bash", "-c", f"gzip -c {a.clips_dir}/{sname}/sealed/vd4_{sname}_blind_key.json | base64 -w0"], timeout=60)
        kb = gzip.decompress(base64.b64decode(r["stdout"].strip()))
        want = re.search(r"SHA-256 `([0-9a-f]{64})`", (ROOT / VD4_OUT / f"vd4_inspection_form_{sname}.md").read_text()).group(1)
        if hashlib.sha256(kb).hexdigest() != want:
            sys.exit("[vc] key SHA-256 differs from the form's: not saved")
        (ROOT / VD4_OUT / f"vd4_{sname}_blind_key.json").write_bytes(kb)
        print(f"[vc] {sname} key copied (SHA-256 = the form's) - next: aggregate_vd4.py")
        return True
    if a.dry:
        py, root, ok = sys.executable, out_rel, True
        if a.stage == "1":
            import shutil as sh_

            for m_ in preserve_stage0_a1(root, units, lambda p: (ROOT / p).exists(), lambda p: (ROOT / p).read_text(), lambda s_, d_: sh_.move(ROOT / s_, ROOT / d_)):
                print(f"[vc] stage-0 A1 run preserved as {m_}")
        for unit, ids in units.items():
            inp, sd = unit.rsplit("_s", 1)
            mids = "" if a.stage in ("0", "0s", "0r", "0a", "0a2") else ",".join(i for i in ids if not i.endswith("-V0"))   # stage 0: validity only, no metrics
            steps = [[py, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", a.frames_dir, "--out_root", root, "--only", ",".join(ids), "--no_ref_frames", "--skip_done"],
                     [py, "tools/eval/vc_check.py", "--unit", f"{root}/{unit}", "--g3"]]
            if mids:
                steps.append([py, "tools/eval/vc_metrics.py", "--unit", f"{root}/{unit}", "--embedders", "pixel", "--device", "cpu", "--only", mids, "--merge"])
            for cmd in steps:
                ok &= subprocess.run(cmd, cwd=ROOT).returncode == 0
        for sname, names, cells in sessions:
            ok &= subprocess.run([py, "tools/eval/vd4_export_clips.py", "--root", root, "--session", sname, "--names", ",".join(names), "--cells", ",".join(cells),
                                  "--clips_dir", a.clips_dir, "--order_seed", "1", "--form", f"{VD4_OUT}/_dryrun_vd4_inspection_form_{sname}.md"], cwd=ROOT).returncode == 0
        return ok
    ag = agent(a)
    if not preflight(a):
        return False
    stamp = time.strftime("%Y%m%d-%H%M%S")
    nic0 = nic_bytes(ag); ok = True
    if a.stage == "1":   # preserve the stage-0 A1 runs on the host (where --skip_done decides) and locally (aggregation, git)
        import shutil as sh_

        def r_exists(p):
            return ag.exec(["test", "-e", p], timeout=30).get("rc", 1) == 0

        def r_move(s_, d_):
            r = ag.exec(["mv", s_, d_], timeout=60)
            if r.get("rc", 1) != 0:
                sys.exit(f"[vc] could not preserve {s_} on {a.host}: {r}")
            if (ROOT / s_).exists():
                sh_.move(ROOT / s_, ROOT / d_)
        for m_ in preserve_stage0_a1("results/evaluation/expVC", units, r_exists, lambda p: ag.read(p), r_move):
            print(f"[vc] stage-0 A1 run preserved as {m_} (host and local)", flush=True)
    for unit, ids in units.items():
        inp, sd = unit.rsplit("_s", 1)
        path = f"{out_rel}/{unit}"
        mids = "" if a.stage in ("0", "0s", "0r", "0a", "0a2") else ",".join(i for i in ids if not i.endswith("-V0"))   # stage 0: validity only, no metrics
        steps = [("emulation", [PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--gpu_id", "0", "--frames_dir", a.frames_dir, "--out_root", out_rel, "--only", ",".join(ids), "--no_ref_frames", "--skip_done"]),
                 ("checks", [PY, "tools/eval/vc_check.py", "--unit", path, "--g3", "--write", "--name", f"{chk_name}{unit}"])]
        if mids:
            steps.append(("metrics", [PY, "tools/eval/vc_metrics.py", "--unit", path, "--embedders", "dino,dinov2,clip", "--device", "cuda:0", "--only", mids, "--merge"]))
        for what, cmd in steps:
            rc = remote_run(ag, cmd, f"{LOG}/vd4_{stamp}_{unit}_{what}.log")
            print(f"[vc] VD-4 stage {a.stage} {unit} {what} on {a.host}: rc {rc}", flush=True)
            if rc != 0:
                ok = False
                if what != "metrics":
                    break
        fetch_unit(ag, inp, int(sd), f"{chk_name}{unit}", root=out_rel)
    for sname, names, cells in (sessions if ok else []):
        rc = remote_run(ag, [PY, "tools/eval/vd4_export_clips.py", "--session", sname, "--names", ",".join(names), "--cells", ",".join(cells),
                             "--clips_dir", f"{a.clips_dir}/{sname}", "--order_seed", time.strftime("%Y%m%d")], f"{LOG}/vd4_{stamp}_clips_{sname}.log", timeout=3 * 3600)
        print(f"[vc] VD-4 {sname} clips on {a.host}: rc {rc} -> {a.clips_dir}/{sname} (never committed)", flush=True)
        try:
            (ROOT / VD4_OUT / f"vd4_inspection_form_{sname}.md").write_text(ag.read(f"{VD4_OUT}/vd4_inspection_form_{sname}.md"))
        except RuntimeError as exc:
            print(f"[vc] form not copied: {exc}"); ok = False
    nic1 = nic_bytes(ag)
    nic = {k: {"rx": nic1[k]["rx"] - nic0[k]["rx"], "tx": nic1[k]["tx"] - nic0[k]["tx"]} for k in nic1 if k in nic0}
    (ROOT / VD4_OUT / f"vd4_isolation_stage{a.stage}.json").write_text(json.dumps({"host": a.host, "nic_bytes": nic}, indent=1))
    if ok:
        subprocess.run([sys.executable, "tools/eval/aggregate_vd4.py"], cwd=ROOT)
    print(f"[vc] VD-4 stage {a.stage}", "done" + (f" - next: the blinded inspections {[x[0] for x in sessions]}, then --phase key --session <name>" if sessions else " - gates in vd4_gates.json") if ok else "had failures")
    return ok


VD5_OUT = "results/evaluation/osdi/expVD5"


def vd5_plan() -> tuple[dict, dict]:
    """(reuse-gate units, run units) of VD-5 (preregistration sections 2, 5, 8): the gate re-runs VD-4's B0, R, S3 on
    dog s1 OT-1 in its own root; the run adds RS3 on the 12 confirmation cells and V0 on the visual cells that lack it."""
    import aggregate_vd5 as a5

    gate = {a5.GATE_UNIT: [f"VD41-{n}" for n in a5.GATE_NAMES]}
    run = {}
    for k in a5.CONFIRM:
        unit, ot = k.split("|"); x = ot.split("-")[1]
        run.setdefault(unit, []).append(f"VD5{x}-RS3")
    for k in a5.VISUAL:
        unit, ot = k.split("|"); x = ot.split("-")[1]
        if f"VD4{x}-V0" not in run[unit]:
            run[unit].append(f"VD4{x}-V0")   # VD-4's V0 definition; --skip_done keeps the existing stage-0 V0 runs
    return gate, run


def vd5_gate_eval(root: str, gate_root: str) -> dict:
    import aggregate_vd5 as a5
    import aggregate_vd4 as a4

    runs = {}
    for n in a5.GATE_NAMES:
        new, old = a4.digests(ROOT / gate_root / a5.GATE_UNIT, f"VD41-{n}"), a4.digests(ROOT / root / a5.GATE_UNIT, f"VD41-{n}")
        runs[n] = {"calls": len(new), "stored_calls": len(old), "differing": sum(1 for c in set(new) | set(old) if new.get(c) != old.get(c))}
    return {"runs": runs, "pass": all(r["calls"] > 0 and r["calls"] == r["stored_calls"] and r["differing"] == 0 for r in runs.values())}


def vd5(a) -> bool:
    """Experiment VD-5 (osdi/expVD5/preregistration.md): one call runs the reuse gate (stops if it fails), RS3 on the
    12 cells and the missing V0 runs, checks, metrics, the blinded clips and both forms, and the aggregate.
    --phase key copies the sealed key once BOTH inspection blocks are recorded and committed, block A in an earlier
    commit than block B."""
    import aggregate_vd5 as a5

    if not a.dry and not (ROOT / "results/evaluation/osdi/expVD5_freeze.md").exists():
        sys.exit("[vc] VD-5 is not frozen (results/evaluation/osdi/expVD5_freeze.md missing): no run")
    gate_units, run_units = vd5_plan()
    pre = "_dryrun_" if a.dry else ""
    if a.phase == "key":
        import base64
        import gzip
        import hashlib
        import re

        ia, ib = f"{VD5_OUT}/vd5_inspection_A.md", f"{VD5_OUT}/vd5_inspection_B.md"
        for p_ in (ia, ib):
            if not ((ROOT / p_).exists() and "STATUS: RECORDED" in (ROOT / p_).read_text() and committed(p_)):
                sys.exit(f"[vc] {p_} is not recorded and committed: the key stays sealed")
        ca = subprocess.run(["git", "log", "-1", "--format=%H", "--", ia], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        cb = subprocess.run(["git", "log", "-1", "--format=%H", "--", ib], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if ca == cb or subprocess.run(["git", "merge-base", "--is-ancestor", ca, cb], cwd=ROOT).returncode != 0:
            sys.exit("[vc] block A must be committed in an earlier commit than block B (preregistration section 6): the key stays sealed")
        ag = agent(a)
        r = ag.exec(["bash", "-c", f"gzip -c {a.clips_dir}/sealed/vd5_blind_key.json | base64 -w0"], timeout=60)
        kb = gzip.decompress(base64.b64decode(r["stdout"].strip()))
        want = re.search(r"SHA-256 `([0-9a-f]{64})`", (ROOT / VD5_OUT / "vd5_inspection_form_A.md").read_text()).group(1)
        if hashlib.sha256(kb).hexdigest() != want:
            sys.exit("[vc] key SHA-256 differs from the form's: not saved")
        (ROOT / VD5_OUT / "vd5_blind_key.json").write_bytes(kb)
        print("[vc] VD-5 key copied (SHA-256 = the forms') - next: aggregate_vd5.py")
        return True
    root = a.dry_root if a.dry else "results/evaluation/expVC"
    groot = f"{a.dry_root}_vd5g" if a.dry else str(a5.GATE_ROOT.relative_to(ROOT))
    cells = ",".join(a5.VISUAL)
    if a.dry:
        py, ok = sys.executable, True

        def emulate(unit, ids, out_root, metrics):
            inp, sd = unit.rsplit("_s", 1)
            steps = [[py, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", a.frames_dir, "--out_root", out_root, "--only", ",".join(ids), "--no_ref_frames", "--skip_done"],
                     [py, "tools/eval/vc_check.py", "--unit", f"{out_root}/{unit}", "--g3"]]
            mids = ",".join(i for i in ids if not i.endswith("-V0"))
            if metrics and mids:
                steps.append([py, "tools/eval/vc_metrics.py", "--unit", f"{out_root}/{unit}", "--embedders", "pixel", "--device", "cpu", "--only", mids, "--merge"])
            return all(subprocess.run(cmd, cwd=ROOT).returncode == 0 for cmd in steps)
        for unit, ids in gate_units.items():
            ok &= emulate(unit, ids, groot, False)
        g = vd5_gate_eval(root, groot)
        print(f"[vc] VD-5 reuse gate (dry): {g}")
        if not g["pass"]:
            return False
        for unit, ids in run_units.items():
            ok &= emulate(unit, ids, root, True)
        ok &= subprocess.run([py, "tools/eval/vd5_export_clips.py", "--root", root, "--cells", cells, "--clips_dir", a.clips_dir, "--order_seed", "1",
                              "--form_a", f"{VD5_OUT}/{pre}vd5_inspection_form_A.md", "--form_b", f"{VD5_OUT}/{pre}vd5_inspection_form_B.md"], cwd=ROOT).returncode == 0
        return ok
    ag = agent(a)
    if not preflight(a):
        return False
    stamp = time.strftime("%Y%m%d-%H%M%S")
    nic0 = nic_bytes(ag); ok = True

    def unit_steps(unit, ids, out_root, chk, metrics):
        inp, sd = unit.rsplit("_s", 1)
        steps = [("emulation", [PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--gpu_id", "0", "--frames_dir", a.frames_dir, "--out_root", out_root, "--only", ",".join(ids), "--no_ref_frames", "--skip_done"]),
                 ("checks", [PY, "tools/eval/vc_check.py", "--unit", f"{out_root}/{unit}", "--g3", "--write", "--name", f"{chk}{unit}"])]
        mids = ",".join(i for i in ids if not i.endswith("-V0"))
        if metrics and mids:
            steps.append(("metrics", [PY, "tools/eval/vc_metrics.py", "--unit", f"{out_root}/{unit}", "--embedders", "dino,dinov2,clip", "--device", "cuda:0", "--only", mids, "--merge"]))
        good = True
        for what, cmd in steps:
            rc = remote_run(ag, cmd, f"{LOG}/vd5_{stamp}_{unit}_{what}.log")
            print(f"[vc] VD-5 {unit} {what} on {a.host}: rc {rc}", flush=True)
            if rc != 0:
                good = False
                if what != "metrics":
                    break
        fetch_unit(ag, inp, int(sd), f"{chk}{unit}", root=out_root)
        return good
    # 1. reuse gate: VD-4's B0, R, S3 on dog s1 OT-1 again at this commit, in their own root; output digests must equal the stored runs
    for unit, ids in gate_units.items():
        ok &= unit_steps(unit, ids, groot, "vd5g_checks_", False)
    g = vd5_gate_eval(root, groot)
    (ROOT / VD5_OUT / "vd5_reuse_gate.json").write_text(json.dumps({**g, "host": a.host, "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}, indent=1))
    print(f"[vc] VD-5 reuse gate: {'PASS' if g['pass'] else 'FAIL'} {g['runs']}", flush=True)
    if not (ok and g["pass"]):
        print("[vc] VD-5 stops: the reuse gate failed (preregistration section 5: the controls would have to be re-run; that needs a decision)")
        return False
    # 2. RS3 on the 12 cells and V0 on the visual cells that lack it; checks; metrics
    for unit, ids in run_units.items():
        ok &= unit_steps(unit, ids, root, "vd5_checks_", True)
    # 3. blinded clips and both forms (on the host; clips never committed)
    if ok:
        rc = remote_run(ag, [PY, "tools/eval/vd5_export_clips.py", "--cells", cells, "--clips_dir", a.clips_dir, "--order_seed", time.strftime("%Y%m%d")],
                        f"{LOG}/vd5_{stamp}_clips.log", timeout=3 * 3600)
        print(f"[vc] VD-5 clips on {a.host}: rc {rc} -> {a.clips_dir} (never committed)", flush=True)
        for fn in ("vd5_inspection_form_A.md", "vd5_inspection_form_B.md"):
            try:
                (ROOT / VD5_OUT / fn).write_text(ag.read(f"{VD5_OUT}/{fn}"))
            except RuntimeError as exc:
                print(f"[vc] {fn} not copied: {exc}"); ok = False
    nic1 = nic_bytes(ag)
    nic = {k: {"rx": nic1[k]["rx"] - nic0[k]["rx"], "tx": nic1[k]["tx"] - nic0[k]["tx"]} for k in nic1 if k in nic0}
    (ROOT / VD5_OUT / "vd5_isolation.json").write_text(json.dumps({"host": a.host, "nic_bytes": nic}, indent=1))
    if ok:
        subprocess.run([sys.executable, "tools/eval/aggregate_vd5.py"], cwd=ROOT)
    print("[vc] VD-5", "done - next: block A of the blinded inspection (commit), then block B (commit), then --phase key" if ok else "had failures")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["preflight", "models", "vc0", "vc1", "fetch", "vd2", "vd3", "vd4", "vd5"])
    ap.add_argument("--stage", default="0", help="vd4: 0, 0s (addendum 1), 0r (addendum 1b), 0a (addendum 2), 0a2 (addendum 2a), 1, 2, 2b, 3")
    ap.add_argument("--session", default="", help="vd4 --phase key: the inspection session (stage1a, stage1b, stage2, stage2b, stage3)")
    ap.add_argument("--dry_root", default="results/evaluation/_dryrun_expVC", help="vd4 --dry: the synthetic units' root")
    ap.add_argument("--phase", choices=["base", "overlap", "cand", "key"], default="base", help="vd3: base (Phase T: REF / controls / distributions / overlap), cand, key")
    ap.add_argument("--clips_dir", default=None, help="vd3 cand / key: clips directory on the VC host's local disk (never committed)")
    ap.add_argument("--with_dr4", action="store_true", help="vd2: also run the exploratory DR-4 cells (section-4 trigger)")
    ap.add_argument("--host", default="D")
    ap.add_argument("--frames_dir", default=None)
    ap.add_argument("--agent_hosts", default=None)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--inputs", default="", help="vc1: comma list of inputs (default all four)")
    a = ap.parse_args()
    if a.what in ("preflight", "vc0", "vc1", "vd2") and not a.frames_dir or (a.what in ("vd3", "vd4", "vd5") and a.phase not in ("key",) and not a.frames_dir):
        sys.exit("--frames_dir (a directory on the VC host's local disk, outside the repository) is required")
    if a.what == "vd3" and a.phase in ("cand", "key") and not a.clips_dir:
        sys.exit("--clips_dir (on the VC host's local disk, outside the repository) is required for vd3 cand / key")
    if a.what == "vd4" and not a.clips_dir and (a.phase == "key" or a.stage not in ("0", "0s", "0r", "0a", "0a2")):
        sys.exit("--clips_dir (on the VC host's local disk, outside the repository) is required for vd4 stages with an inspection")
    if a.what == "vd5" and not a.clips_dir:
        sys.exit("--clips_dir (on the VC host's local disk, outside the repository) is required for vd5")
    ok = {"preflight": preflight, "models": models, "vc0": vc0, "vc1": vc1, "fetch": fetch, "vd2": vd2, "vd3": vd3, "vd4": vd4, "vd5": vd5}[a.what](a)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
