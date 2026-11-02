#!/usr/bin/env python3
"""Runs the LongLive migration feasibility experiment (osdi/longlive/snapshot_prereg.md) from elves-01 through the
per-host agents (tools/eval/agent.py; no ssh between the hosts): two lanes in parallel (source > destination), each
running its job list in order; every job starts the destination, then the source, waits for both, and copies the
destination's JSON and both logs back to elves-01 (results/evaluation/osdi/longlive/migrate/). Jobs whose JSON already
exists are skipped (a re-invocation resumes); `report` applies the preregistered rules.

    elves-01:  python tools/longlive/ll_migrate_runs.py run            # all jobs, lanes A>B and C>D
    elves-01:  python tools/longlive/ll_migrate_runs.py run --dry      # print the job list only
    any:       python tools/longlive/ll_migrate_runs.py report
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
OUT = ROOT / "results/evaluation/osdi/longlive/migrate"
REL = "results/evaluation/osdi/longlive/migrate"
STREAMS = [(0, 0), (1, 0), (0, 1), (1, 1)]   # (prompt index, seed), as the ablation
ARMS = {"snap_k12": ["--method", "snap", "--k_vae", "12"], "snap_k1": ["--method", "snap", "--k_vae", "1"], "full": ["--method", "full"]}


def jobs(reps, arms):
    """rep-major, then stream, then arm (arms interleaved so slow drift hits every arm alike)."""
    return [(r, p, s, arm) for r in range(1, reps + 1) for p, s in STREAMS for arm in arms]


def name(r, p, s, arm, bw):
    return f"{arm}_bw{int(bw)}_p{p}_s{s}_r{r}"


def run_job(ag_src, ag_dst, dst_host, port, job, a):
    from agents import Agent  # noqa: F401
    r, p, s, arm = job
    nm = name(r, p, s, arm, a.bw_mbps)
    common = [*ARMS[arm], "--at", str(a.at), "--verify", str(a.verify), "--bw_mbps", str(a.bw_mbps), "--prompt_idx", str(p),
              "--seed", str(s), "--max_catchup_s", str(a.max_catchup_s)]
    py = ".venv/bin/python"
    pd = ag_dst.run([py, "tools/longlive/ll_migrate.py", "dst", "--port", str(port), "--out", f"{REL}/{nm}.json", *common],
                    log=f"{REL}/{nm}.dst.log")
    time.sleep(3)
    ps = ag_src.run([py, "tools/longlive/ll_migrate.py", "src", "--peer", f"{dst_host}:{port}", *common], log=f"{REL}/{nm}.src.log")
    rs, rd = ag_src.wait(ps, 3600), ag_dst.wait(pd, 3600)
    ok = rs.get("rc") == 0 and rd.get("rc") == 0
    OUT.mkdir(parents=True, exist_ok=True)
    for ag, suf in ((ag_dst, ".json"), (ag_dst, ".dst.log"), (ag_src, ".src.log")):
        try:
            (OUT / f"{nm}{suf}").write_text(ag.read(f"{REL}/{nm}{suf}"))
        except Exception as exc:  # noqa: BLE001
            print(f"[runs] {nm}: could not copy {suf} ({exc})", flush=True)
    print(f"[runs] {nm} on {ag_src.label}>{ag_dst.label}: {'ok' if ok else 'FAILED src rc ' + str(rs.get('rc')) + ' dst rc ' + str(rd.get('rc'))}", flush=True)
    return ok


def cmd_run(a):
    from agents import Agent, parse_hosts
    hosts = parse_hosts(None)
    lanes = [tuple(x.split(">")) for x in a.lanes.split(",")]
    todo = [j for j in jobs(a.reps, a.arms) if not (OUT / f"{name(*j, a.bw_mbps)}.json").exists()]
    print(f"[runs] {len(todo)} jobs to run on lanes {lanes} (bw {a.bw_mbps} Mbps)", flush=True)
    if a.dry:
        for i, j in enumerate(todo):
            print(f"  lane {lanes[i % len(lanes)]}: {name(*j, a.bw_mbps)}")
        return
    for lb in {x for ln in lanes for x in ln}:
        Agent(lb, *hosts[lb]).mkdir(REL)
    fails = []

    def lane(i, src, dst):
        ag_s, ag_d = Agent(src, *hosts[src]), Agent(dst, *hosts[dst])
        for j in todo[i::len(lanes)]:
            if not run_job(ag_s, ag_d, hosts[dst][0], 29951 + i, j, a):
                fails.append(name(*j, a.bw_mbps))

    th = [threading.Thread(target=lane, args=(i, *ln)) for i, ln in enumerate(lanes)]
    [t.start() for t in th]
    [t.join() for t in th]
    print(f"[runs] done; failed: {fails or 'none'}", flush=True)


def cmd_report(a):
    """Rules of snapshot_prereg.md section 5."""
    out = Path(a.out_dir) if a.out_dir else OUT
    runs = {}
    for f in sorted(out.glob("*.json")):
        d = json.loads(f.read_text())
        arm = f.name.split("_bw")[0]
        p, s = d["args"]["prompt_idx"], d["args"]["seed"]
        runs.setdefault(arm, {}).setdefault((p, s), []).append(d)
    med = lambda xs: st.median(xs) if xs else None  # noqa: E731
    L = ["# LongLive migration feasibility: results", "", "Rules: `snapshot_prereg.md` section 5. Measured on the testbed.", ""]
    verdict = {}
    for arm in [x for x in ARMS if x.startswith("snap")]:
        R = [d for ds in runs.get(arm, {}).values() for d in ds]
        if not R:
            continue
        q1 = all(d["state_exact"] and d["lat_equal_calls"] == len(d["post_cutover"]) and d["frames_complete"] for d in R)
        q2 = all(not d["switch_forced"] for d in R)
        per = {}
        for k, ds in runs[arm].items():
            fu = runs.get("full", {}).get(k, [])
            per[f"p{k[0]}_s{k[1]}"] = {"gap": (med([d["delivery_gap_s"] for d in ds]), med([d["delivery_gap_s"] for d in fu])),
                                       "readiness": (med([d["readiness_s"] for d in ds]), med([d["readiness_s"] for d in fu]))}
        q3n = sum(1 for v in per.values() if None not in v["gap"] and v["gap"][0] < v["gap"][1])
        verdict[arm] = {"Q1_exact_recovery": q1, "Q2_caught_up": q2, "Q3_gap_lt_full": q3n >= 3, "Q3_streams": q3n,
                        "per_stream": per, "runs": len(R)}
        L += [f"## {arm} ({len(R)} runs)", "",
              f"Q1 exact state recovery (state, 20 latents, frames complete): {'HOLDS' if q1 else 'FAILS'}; "
              f"Q2 catch-up (no forced switch): {'HOLDS' if q2 else 'FAILS'}; "
              f"Q3 delivery gap < Full: {'HOLDS' if q3n >= 3 else 'FAILS'} ({q3n} / {len(per)} streams). Readiness reported only.", "",
              "| stream | readiness (s) | Full readiness (s) | gap (s) | Full gap (s) | TTFO (s) | src interval before / during (s) | export stall (s) | replayed | frames equal | first-call PSNR |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, ds in sorted(runs[arm].items()):
            fu = runs.get("full", {}).get(k, [])
            f = lambda xs: "-" if xs is None else f"{xs:.2f}"  # noqa: E731
            L.append(f"| p{k[0]} s{k[1]} | {f(med([d['readiness_s'] for d in ds]))} | {f(med([d['readiness_s'] for d in fu]))} | "
                     f"{f(med([d['delivery_gap_s'] for d in ds]))} | {f(med([d['delivery_gap_s'] for d in fu]))} | {f(med([d['ttfo_s'] for d in ds]))} | "
                     f"{f(med([d['src_call_interval_s']['before'] for d in ds]))} / {f(med([d['src_call_interval_s']['during_state_send'] for d in ds if d['src_call_interval_s']['during_state_send']]))} | "
                     f"{f(med([d['src_export_stall_s'] for d in ds]))} | {med([d['replayed_calls'] for d in ds])} | "
                     f"{min(d['frm_equal_calls'] for d in ds)}-{max(d['frm_equal_calls'] for d in ds)} / {len(ds[0]['post_cutover'])} | "
                     f"{f(med([d['first_call_psnr_vs_shadow'] for d in ds if d['first_call_psnr_vs_shadow'] is not None]))} |")
        L.append("")
    FU = [d for ds in runs.get("full", {}).values() for d in ds]
    if FU:
        L += [f"Full ({len(FU)} runs): state exact {all(d['state_exact'] for d in FU)}, post-cutover latents equal "
              f"{all(d['lat_equal_calls'] == len(d['post_cutover']) for d in FU)}, frames complete {all(d['frames_complete'] for d in FU)}", ""]
    (out.parent / "migrate_results.md").write_text("\n".join(L) + "\n")
    (out.parent / "migrate_results.json").write_text(json.dumps(verdict, indent=1, default=str))
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("--lanes", default="A>B,C>D", help="source>destination agent labels, one lane per pair")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--arms", type=lambda s: s.split(","), default=list(ARMS))
    ap.add_argument("--bw_mbps", type=float, default=1000.0)
    ap.add_argument("--at", type=int, default=120)
    ap.add_argument("--verify", type=int, default=20)
    ap.add_argument("--max_catchup_s", type=float, default=300.0)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--out_dir", default=None, help="report: directory of run JSONs (default results/.../longlive/migrate)")
    a = ap.parse_args()
    (cmd_run if a.cmd == "run" else cmd_report)(a)


if __name__ == "__main__":
    main()
