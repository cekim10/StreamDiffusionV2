#!/usr/bin/env python3
"""D0 helpers that reach elves-02..04 through the per-host experiment agents (tools/eval/agent.py, port 29900)
instead of ssh, which is not available between the testbed hosts. Run on elves-01.

    status                 agent reachability, repo commit and GPU 0 processes on every host
    gpu_idle               exit 1 unless GPU 0 has no compute process on all four hosts and all repos are on one commit
    pull                   git pull --ff-only on the hosts whose repo is behind (no other git operation)
    probe NAME SCRIPT      run a read-only bash probe on elves-02..04, write results/evaluation/osdi/d0/NAME/<host>.txt
    recover                copy back node_{B,C,D}/fragments.csv of restore_* runs; never overwrites a local file
    codecs                 XB preflight on all four hosts: PyAV, FFV1 bit-exact round trip, libx264 (exit 1 if any fails);
                           writes results/evaluation/osdi/expXB/codec_hosts.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents import Agent, parse_hosts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REMOTE = ("B", "C", "D")


def agents(labels, spec=None):
    hosts = parse_hosts(spec)
    out = {}
    for lb in labels:
        h, p = hosts[lb]
        try:
            out[lb] = Agent(lb, h, p)
            out[lb].ping()
        except Exception as exc:  # noqa: BLE001
            print(f"[d0] {lb} {h}:{p}: agent not reachable ({exc}); start it there with tools/eval/start_agent.sh", flush=True)
    return out


def sh(ag, cmd, timeout=30):
    try:
        return ag.exec(cmd, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return {"rc": -1, "stdout": "", "stderr": str(exc)}


def host_of(ag):
    return ag.ping()["host"].split(".")[0]


def status(a):
    for lb, ag in agents(("A",) + REMOTE, a.agent_hosts).items():
        c = sh(ag, ["git", "log", "--oneline", "-1"])["stdout"].strip()
        d = sh(ag, ["git", "status", "--porcelain", "--untracked-files=no"])["stdout"].strip()
        g = sh(ag, ["nvidia-smi", "-i", "0", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"])
        g = g["stdout"].strip() if g["rc"] == 0 else f"nvidia-smi failed: {g['stderr'].strip()[-120:]}"
        print(f"{lb} {host_of(ag)}: {c} | tracked changes: {len(d.splitlines()) if d else 0} | GPU 0 processes: {g or 'none'}")


def gpu_idle(a):
    ags = agents(("A",) + REMOTE, a.agent_hosts)
    bad, commits = [], set()
    for lb, ag in ags.items():
        commits.add(sh(ag, ["git", "rev-parse", "HEAD"])["stdout"].strip())
        g = sh(ag, ["nvidia-smi", "-i", "0", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"])
        if g["rc"] != 0 or g["stdout"].strip():
            bad.append(f"{lb} {host_of(ag)} GPU 0: {g['stdout'].strip() or g['stderr'].strip()}")
    if len(ags) < 4:
        bad.append("not all four agents reachable")
    if len(commits) != 1:
        bad.append(f"repos on different commits: {sorted(c[:7] for c in commits)}")
    print("\n".join(bad) if bad else "GPU 0 idle on all four hosts; one commit")
    sys.exit(1 if bad else 0)


def pull(a):
    for lb, ag in agents(REMOTE, a.agent_hosts).items():
        r = sh(ag, ["git", "pull", "--ff-only"], timeout=180)
        c = sh(ag, ["git", "log", "--oneline", "-1"])["stdout"].strip()
        print(f"{lb} {host_of(ag)}: rc={r['rc']} {r['stdout'].strip().splitlines()[-1] if r['stdout'].strip() else ''} {r['stderr'].strip()[-300:]} -> {c}")


def probe(a):
    out = ROOT / "results/evaluation/osdi/d0" / a.name
    out.mkdir(parents=True, exist_ok=True)
    for lb, ag in agents(REMOTE, a.agent_hosts).items():
        h = host_of(ag)
        r = sh(ag, ["bash", "-c", a.script], timeout=300)
        (out / f"{h}.txt").write_text(r["stdout"] + (("\n## stderr\n" + r["stderr"]) if r["stderr"].strip() else ""))
        print(f"wrote {out.relative_to(ROOT)}/{h}.txt (via agent {lb}, rc {r['rc']})")


def recover(a):
    for lb, ag in agents(REMOTE, a.agent_hosts).items():
        new = kept = 0
        for rel in ag.glob(f"results/evaluation/restore_*/*/node_{lb}/fragments.csv"):
            dst = ROOT / rel
            if dst.exists():
                kept += 1; continue
            if not dst.parent.parent.exists():   # only runs that exist (committed) locally
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(ag.read(rel))
            new += 1
        print(f"node {lb} ({host_of(ag)}): copied {new}, already present {kept}")


def codecs(a):
    import json

    code = ("import json, sys; sys.path.insert(0, 'tools/eval'); import mobility_node as mn; "
            "print(json.dumps(mn.codec_support()))")
    res, bad = {}, []
    for lb, ag in agents(("A",) + REMOTE, a.agent_hosts).items():
        r = sh(ag, [".venv/bin/python", "-c", code], timeout=300)
        try:
            v = json.loads(r["stdout"].strip().splitlines()[-1])
        except (ValueError, IndexError):
            v = {"error": (r["stderr"] or r["stdout"]).strip()[-400:]}
        v["host"] = host_of(ag); res[lb] = v
        ok = v.get("ffv1_roundtrip") is True and v.get("libx264") is True
        print(f"{lb} {v['host']}: {'OK' if ok else 'FAIL'} {v}")
        if not ok:
            bad.append(lb)
    if len(res) < 4:
        bad.append("not all four agents reachable")
    (ROOT / "results/evaluation/osdi/expXB/codec_hosts.json").write_text(json.dumps(res, indent=1))
    print("codecs OK on all four hosts" if not bad else f"codec check FAILED: {bad}")
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent_hosts", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status"); sub.add_parser("gpu_idle"); sub.add_parser("pull"); sub.add_parser("recover"); sub.add_parser("codecs")
    p = sub.add_parser("probe"); p.add_argument("name"); p.add_argument("script")
    a = ap.parse_args()
    {"status": status, "gpu_idle": gpu_idle, "pull": pull, "probe": probe, "recover": recover, "codecs": codecs}[a.cmd](a)


if __name__ == "__main__":
    main()
