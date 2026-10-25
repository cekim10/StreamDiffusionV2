#!/usr/bin/env python3
"""Experiment VC driver (run on elves-01; osdi/expVC/implementation_plan.md sections 5-6). VC runs on host D's GPU 0
(C is the spare: --host C) while XB uses A and B. Frames stay on the VC host's local disk; only small result files
are copied back. Nothing is pulled or committed on the testbed by this script.

    python tools/eval/run_vc.py preflight --frames_dir /local/path      # D: local filesystem, free space, GPU, packages
    python tools/eval/run_vc.py models                                  # D: download DINO / DINOv2 / CLIP once (before XB starts)
    python tools/eval/run_vc.py vc0 --frames_dir /local/path            # D: metric self-test, dog OT-L / COLD-1 / WFS-1 -> G1, G2, G3
    python tools/eval/run_vc.py vd2 --frames_dir /local/path            # after the VD-2 freeze: reconstruction conditions on the VC units
    python tools/eval/run_vc.py vd3 --phase base --frames_dir /local/path   # after the VD-3 freeze: seed-1 REF / controls, G1 / G3, tolerances, overlap; stops for review
    python tools/eval/run_vc.py vd3 --phase cand --frames_dir /local/path --clips_dir /local/clips   # only after the tolerances are committed
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


def fetch_unit(ag, inp: str, seed: int = 0, checks: str | None = None):
    """Copy a VC-1 unit's small results from the VC host (frames stay there)."""
    unit = f"results/evaluation/expVC/{inp}_s{seed}"
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
    base: seed-1 units (REF + frozen-M1 OT-1 / OT-L controls), G1 (OT-1 vs the real W2 seed-1 run) and G3, metrics,
          then the REF-only tolerances and the overlap measurement; stops so the tolerances are reviewed and committed.
    cand: only when vd3_tolerances.json is committed: the six VD-3 conditions on all eight units, G3, merged metrics,
          then the blinded clips and the inspection form. Verdicts wait for the recorded inspection.
    key:  only when vd3_inspection.md is committed with STATUS: RECORDED: copies the sealed key."""
    if not a.dry and not (ROOT / "results/evaluation/osdi/expVD3_freeze.md").exists():
        sys.exit("[vc] VD-3 is not frozen (results/evaluation/osdi/expVD3_freeze.md missing): no run")
    inputs = [x for x in (a.inputs or "").split(",") if x] or list(INPUTS)
    if a.phase == "key":
        insp = ROOT / VD3_OUT / "vd3_inspection.md"
        if not (insp.exists() and "STATUS: RECORDED" in insp.read_text() and committed(f"{VD3_OUT}/vd3_inspection.md")):
            sys.exit("[vc] vd3_inspection.md is not recorded and committed: the key stays sealed")
        ag = agent(a)
        (ROOT / VD3_OUT / "vd3_blind_key.json").write_bytes(ag.read(f"{a.clips_dir}/sealed/vd3_blind_key.json").encode())
        print("[vc] key copied to", f"{VD3_OUT}/vd3_blind_key.json", "- next: aggregate_vd3.py")
        return True
    if a.phase == "cand" and not a.dry and not committed(f"{VD3_OUT}/vd3_tolerances.json"):
        sys.exit("[vc] vd3_tolerances.json is not committed: the tolerances are fixed and reviewed before any candidate runs")
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
            ok &= subprocess.run([py, "tools/eval/vd3_tolerances.py", "--root", out, "--inputs", ",".join(inputs), "--embedder", "pixel", "--device", "cpu", "--dry"], cwd=ROOT).returncode == 0
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
            for what, cmd in (("tolerances", [PY, "tools/eval/vd3_tolerances.py", "--root", "results/evaluation/expVC", "--embedder", "dino", "--device", "cuda:0"]),
                              ("overlap", [PY, "tools/eval/vd3_overlap.py", "--input", "dog", "--seed", "0", "--schedule", "OT-1", "--reps", "5", "--gpu_id", "0"])):
                rc = remote_run(ag, cmd, f"{LOG}/vd3_{stamp}_{what}.log", timeout=3 * 3600)
                print(f"[vc] VD-3 base {what} on {a.host}: rc {rc}", flush=True)
                ok &= rc == 0
            for f in ("vd3_tolerances.json", "vd3_tolerances.md", "vd3_overlap.json"):
                try:
                    (ROOT / VD3_OUT / f).write_text(ag.read(f"{VD3_OUT}/{f}"))
                except RuntimeError as exc:
                    print(f"[vc] {f} not copied: {exc}"); ok = False
        print("[vc] VD-3 base", "done - review vd3_tolerances.md (and commit it) before --phase cand" if ok else "had failures")
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["preflight", "models", "vc0", "vc1", "fetch", "vd2", "vd3"])
    ap.add_argument("--phase", choices=["base", "cand", "key"], default="base", help="vd3: base (REF / controls / tolerances / overlap), cand, key")
    ap.add_argument("--clips_dir", default=None, help="vd3 cand / key: clips directory on the VC host's local disk (never committed)")
    ap.add_argument("--with_dr4", action="store_true", help="vd2: also run the exploratory DR-4 cells (section-4 trigger)")
    ap.add_argument("--host", default="D")
    ap.add_argument("--frames_dir", default=None)
    ap.add_argument("--agent_hosts", default=None)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--inputs", default="", help="vc1: comma list of inputs (default all four)")
    a = ap.parse_args()
    if a.what in ("preflight", "vc0", "vc1", "vd2") and not a.frames_dir or (a.what == "vd3" and a.phase != "key" and not a.frames_dir):
        sys.exit("--frames_dir (a directory on the VC host's local disk, outside the repository) is required")
    if a.what == "vd3" and a.phase in ("cand", "key") and not a.clips_dir:
        sys.exit("--clips_dir (on the VC host's local disk, outside the repository) is required for vd3 cand / key")
    ok = {"preflight": preflight, "models": models, "vc0": vc0, "vc1": vc1, "fetch": fetch, "vd2": vd2, "vd3": vd3}[a.what](a)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
