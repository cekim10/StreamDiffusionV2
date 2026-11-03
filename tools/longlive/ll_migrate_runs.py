#!/usr/bin/env python3
"""Runs a LongLive live-migration study from elves-01 through the
per-host agents (tools/eval/agent.py; no ssh between the hosts): two lanes in parallel (source > destination), each
running its job list in order; every job starts the destination, then the source, waits for both, and copies the
destination's JSON and both logs back to elves-01 (results/evaluation/osdi/longlive/<study dir>/). Jobs whose JSON
already exists are skipped (a re-invocation resumes); `report` applies the study's preregistered rules.

  --study m1        osdi/longlive/m1_prereg.md: frozen OTTER M1 (Continuity Replay) with replay horizon W = 96 vs W = 12,
                    LongLive-native recache and Full; 100 post-cutover calls verified (default)
  --study snapshot  osdi/longlive/snapshot_prereg.md (ON HOLD): exact window snapshot + catch-up replay

    elves-01:  python tools/longlive/ll_migrate_runs.py run --dry      # print the job list only
    elves-01:  python tools/longlive/ll_migrate_runs.py run            # all jobs, lanes A>B and C>D
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
STREAMS = [(0, 0), (1, 0), (0, 1), (1, 1)]   # (prompt index, seed), as the ablation
STUDIES = {
    "m1": {"dir": "migrate_m1", "verify": 100,
           "arms": {"otter_w96": ["--method", "replay", "--replay_w", "96", "--k_vae", "12"],
                    "otter_w12": ["--method", "replay", "--replay_w", "12", "--k_vae", "12"],
                    "recache": ["--method", "recache"], "full": ["--method", "full"]}},
    "snapshot": {"dir": "migrate", "verify": 20,
                 "arms": {"snap_k12": ["--method", "snap", "--k_vae", "12"], "snap_k1": ["--method", "snap", "--k_vae", "1"],
                          "full": ["--method", "full"]}},
}
OUT = REL = ARMS = None   # set from --study in main()


def jobs(reps, arms):
    """rep-major, then stream, then arm (arms interleaved so slow drift hits every arm alike)."""
    return [(r, p, s, arm) for r in range(1, reps + 1) for p, s in STREAMS for arm in arms]


def lane_of(i, job, n):
    """Job i of the full list -> lane; rep r shifts by r - 1, so every (arm, stream) runs on each lane once over 2 reps
    and no arm is compared with Full on a different host pair every time."""
    return (i + job[0] - 1) % n


def name(r, p, s, arm, bw):
    return f"{arm}_bw{int(bw)}_p{p}_s{s}_r{r}"


def run_job(ag_src, ag_dst, dst_host, port, job, a):
    from agents import Agent  # noqa: F401
    r, p, s, arm = job
    nm = name(r, p, s, arm, a.bw_mbps)
    common = [*ARMS[arm], "--at", str(a.at), "--verify", str(a.verify), "--bw_mbps", str(a.bw_mbps), "--prompt_idx", str(p),
              "--seed", str(s), "--max_catchup_s", str(a.max_catchup_s)]
    py = ".venv/bin/python"   # with -u below: unbuffered, so a killed process still leaves its log
    pd = ag_dst.run([py, "-u", "tools/longlive/ll_migrate.py", "dst", "--port", str(port), "--out", f"{REL}/{nm}.json", *common],
                    log=f"{REL}/{nm}.dst.log")
    time.sleep(3)
    ps = ag_src.run([py, "-u", "tools/longlive/ll_migrate.py", "src", "--peer", f"{dst_host}:{port}", *common], log=f"{REL}/{nm}.src.log")
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
    alljobs = list(enumerate(jobs(a.reps, a.arms)))
    todo = [(lane_of(i, j, len(lanes)), j) for i, j in alljobs if not (OUT / f"{name(*j, a.bw_mbps)}.json").exists()]
    print(f"[runs] {len(todo)} jobs to run on lanes {lanes} (bw {a.bw_mbps} Mbps)", flush=True)
    if a.dry:
        for ln, j in todo:
            print(f"  lane {lanes[ln]}: {name(*j, a.bw_mbps)}")
        return
    for lb in {x for ln in lanes for x in ln}:
        Agent(lb, *hosts[lb]).mkdir(REL)
    fails = []

    def lane(i, src, dst):
        ag_s, ag_d = Agent(src, *hosts[src]), Agent(dst, *hosts[dst])
        for j in [j for ln, j in todo if ln == i]:
            if not run_job(ag_s, ag_d, hosts[dst][0], 29951 + i, j, a):
                fails.append(name(*j, a.bw_mbps))

    th = [threading.Thread(target=lane, args=(i, *ln)) for i, ln in enumerate(lanes)]
    [t.start() for t in th]
    [t.join() for t in th]
    print(f"[runs] done; failed: {fails or 'none'}", flush=True)


def cmd_report_m1(a):
    """Rules of m1_prereg.md section 5."""
    out = Path(a.out_dir) if a.out_dir else OUT
    runs = {}
    for f in sorted(out.glob("*.json")):
        d = json.loads(f.read_text())
        runs.setdefault(f.name.split("_bw")[0], {}).setdefault((d["args"]["prompt_idx"], d["args"]["seed"]), []).append(d)
    med = lambda xs: st.median(xs) if xs else None  # noqa: E731
    f = lambda x, n=2: "-" if x is None else f"{x:.{n}f}"  # noqa: E731
    L = ["# LongLive M1 (Continuity Replay) cross-model check: results", "",
         "Rules: `m1_prereg.md` section 5. Measured on the testbed; PSNR vs the source's shadow continuation.", ""]
    v = {}
    ALLW = [d for ds in runs.get("otter_w96", {}).values() for d in ds]
    W = [d for d in ALLW if not d["switch_forced"]]   # a catch-up timeout is a migration failure: never aggregated as a migration
    if ALLW:
        r1a = bool(W) and all(d["state_exact"] for d in W)
        r1b = bool(W) and all(d["lat_equal_calls"] == len(d["post_cutover"]) for d in W)
        r1c = bool(W) and all(d["frames_complete"] for d in W)
        r2 = len(W) == len(ALLW)
        per = {}
        for k, ds in runs["otter_w96"].items():
            ds = [d for d in ds if not d["switch_forced"]]
            fu = runs.get("full", {}).get(k, [])
            per[f"p{k[0]}_s{k[1]}"] = {key: (med([d[key] for d in ds]), med([d[key] for d in fu]))
                                       for key in ("max_output_gap_s", "readiness_s", "bytes_until_switch")}
        ok = lambda x: None not in x  # noqa: E731
        n3 = sum(1 for x in per.values() if ok(x["max_output_gap_s"]) and x["max_output_gap_s"][0] < x["max_output_gap_s"][1])
        n4 = sum(1 for x in per.values() if ok(x["readiness_s"]) and x["readiness_s"][0] < x["readiness_s"][1])
        fu_b = [d["bytes_until_switch"] for ds in runs.get("full", {}).values() for d in ds]
        r5 = bool(fu_b) and bool(W) and all(d["bytes_until_switch"] < min(fu_b) for d in W)
        v = {"R1a_generation_state_exact": r1a, "R1b_latents_exact": r1b, "R1c_frames_complete": r1c, "R1": r1a and r1b and r1c,
             "R2_caught_up": r2, "timeouts": len(ALLW) - len(W), "R3_max_gap_lt_full": n3 >= 3, "R3_streams": n3,
             "R4_readiness_lt_full": n4 >= 3, "R4_streams": n4, "R5_bytes_lt_full": r5, "per_stream": per, "runs": len(ALLW)}
        L += [f"**otter_w96 ({len(ALLW)} runs, {len(ALLW) - len(W)} catch-up timeouts = migration failures, excluded below):** "
              f"R1a generation state (sink + window fingerprint) {'HOLDS' if r1a else 'FAILS'}; R1b latents 100 / 100 "
              f"{'HOLDS' if r1b else 'FAILS'}; R1c frames complete {'HOLDS' if r1c else 'FAILS'}; R2 catch-up {'HOLDS' if r2 else 'FAILS'}; "
              f"R3 max output gap < Full {'HOLDS' if n3 >= 3 else 'FAILS'} ({n3} / {len(per)}); R4 readiness < Full "
              f"{'HOLDS' if n4 >= 3 else 'FAILS'} ({n4} / {len(per)}); R5 bytes < Full {'HOLDS' if r5 else 'FAILS'}. "
              "Frame fidelity (first call, W1-W3, frames bit-exact) is reported in the table, not part of R1.", "",
              "| stream | max gap otter_w96 / Full (s) | difference (s) | readiness otter_w96 / Full (s) | difference (s) | bytes otter_w96 / Full (GiB) |",
              "|---|---|---|---|---|---|"]
        for k, x in sorted(per.items()):
            g, r, b = x["max_output_gap_s"], x["readiness_s"], x["bytes_until_switch"]
            L.append(f"| {k} | {f(g[0])} / {f(g[1])} | {f(g[0] - g[1]) if ok(g) else '-'} | {f(r[0])} / {f(r[1])} | "
                     f"{f(r[0] - r[1]) if ok(r) else '-'} | {f(b[0] / 2 ** 30 if b[0] else None)} / {f(b[1] / 2 ** 30 if b[1] else None)} |")
        r134 = v["R1"] and r2 and n3 >= 3 and r5
        reading = ("not applicable (R1 / R2 / R3 / R5 do not all hold; see section 5)" if not r134 else
                   "M1 carries over to LongLive with a longer replay horizon: shorter readiness, a short cutover and fewer bytes than Full "
                   "(one move, 1 Gbps)" if n4 >= 3 else
                   "M1 works on LongLive (exact, continuous, fewer bytes) but is not faster to be ready than Full: functional generality "
                   "of M1 shown, performance generality not")
        v["reading"] = reading
        # readiness components (record only): per-call replay times come from the destination's replay log
        def parts(d):
            rp = d.get("replay") or []
            ctx, dec = [x["dt_s"] for x in rp if not x["decoded"]], [x["dt_s"] for x in rp if x["decoded"]]
            known = d["state_transfer_s"] + d["import_s"] + sum(ctx) + (d.get("vae_rebuild_s") or 0) + sum(dec)
            return {"xfer": d["state_transfer_s"], "import": d["import_s"], "n_ctx": len(ctx), "ctx": sum(ctx),
                    "ctx_call": st.median(ctx) if ctx else None, "vae": d.get("vae_rebuild_s") or 0, "n_dec": len(dec),
                    "dec": sum(dec), "other": d["readiness_s"] - known, "ready": d["readiness_s"]}
        P = [parts(d) for d in W]
        if P:
            m = {k: med([p[k] for p in P]) for k in P[0]}
            fu = [d for ds in runs.get("full", {}).values() for d in ds]
            L += ["", f"**Reading (section 5, as written):** {reading}.", "",
                  "Readiness of otter_w96, medians over its runs (s; measured, destination clock):", "",
                  "| sink transfer | import | context-only replay | VAE rebuild | decode-replay | other | readiness | Full: transfer / import / readiness |",
                  "|---|---|---|---|---|---|---|---|",
                  f"| {f(m['xfer'])} | {f(m['import'])} | {f(m['ctx'])} ({m['n_ctx']:.0f} calls, {f(m['ctx_call'], 3)} s each) | {f(m['vae'])} | "
                  f"{f(m['dec'])} ({m['n_dec']:.0f} calls) | {f(m['other'])} | {f(m['ready'])} | "
                  f"{f(med([d['state_transfer_s'] for d in fu]))} / {f(med([d['import_s'] for d in fu]))} / {f(med([d['readiness_s'] for d in fu]))} |"]
        L.append("")
    L += ["| arm | stream | runs | readiness (s) | max output gap (s) | delivery gap (s) | src interval before / during migration (s) | log copy (ms) | bytes to switch (GiB) | W1 / W2 / W3 PSNR (dB) | first call | frames bit-exact | latents equal | frames complete | timeouts |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        for k, ds in sorted(runs.get(arm, {}).items()):
            pw = [d["psnr_windows"] for d in ds]
            L.append(f"| {arm} | p{k[0]} s{k[1]} | {len(ds)} | {f(med([d['readiness_s'] for d in ds]))} | {f(med([d['max_output_gap_s'] for d in ds]))} | "
                     f"{f(med([d['delivery_gap_s'] for d in ds]))} | {f(med([d['src_call_interval_s']['before'] for d in ds]))} / "
                     f"{f(med([d['src_call_interval_s']['during_migration'] for d in ds if d['src_call_interval_s'].get('during_migration')]))} | "
                     f"{f(med([1e3 * d['src_log_copy_s_median'] for d in ds if d.get('src_log_copy_s_median')]), 1)} | "
                     f"{f(med([d['bytes_until_switch'] / 2 ** 30 for d in ds]))} | "
                     f"{f(med([p['W1'] for p in pw]), 1)} / {f(med([p['W2'] for p in pw]), 1)} / {f(med([p['W3'] for p in pw]), 1)} | "
                     f"{f(med([p['first'] for p in pw]), 1)} | {min(d['frm_equal_calls'] for d in ds)}-{max(d['frm_equal_calls'] for d in ds)} | "
                     f"{min(d['lat_equal_calls'] for d in ds)} / {len(ds[0]['post_cutover'])} | "
                     f"{all(d['frames_complete'] for d in ds)} | {sum(d['switch_forced'] for d in ds)} |")
    (out.parent / "m1_results.md").write_text("\n".join(L) + "\n")
    (out.parent / "m1_results.json").write_text(json.dumps(v, indent=1, default=str))
    print("\n".join(L))


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
    ap.add_argument("--study", choices=list(STUDIES), default="m1")
    ap.add_argument("--arms", type=lambda s: s.split(","), default=None)
    ap.add_argument("--bw_mbps", type=float, default=1000.0)
    ap.add_argument("--at", type=int, default=120)
    ap.add_argument("--verify", type=int, default=None, help="default: the study's")
    ap.add_argument("--max_catchup_s", type=float, default=300.0)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--out_dir", default=None, help="report: directory of run JSONs (default results/.../longlive/migrate)")
    a = ap.parse_args()
    global OUT, REL, ARMS
    S = STUDIES[a.study]
    REL = f"results/evaluation/osdi/longlive/{S['dir']}"
    OUT, ARMS = ROOT / REL, S["arms"]
    a.arms = a.arms or list(ARMS)
    a.verify = a.verify or S["verify"]
    if a.cmd == "run":
        cmd_run(a)
    else:
        (cmd_report_m1 if a.study == "m1" else cmd_report)(a)


if __name__ == "__main__":
    main()
