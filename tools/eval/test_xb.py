#!/usr/bin/env python3
"""XB loopback tests (fake runtime, 4 local nodes): protocol, switchover verification and owner transitions of the
re-implemented baselines, single move and repeated mobility (rho 2: tasks cancelled and retargeted on moves).

    python tools/eval/test_xb.py
"""

from __future__ import annotations

import csv
import json
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from xb_validity import run_validity_xb  # noqa: E402

PY = sys.executable
NODES = "A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942"
FAILS = []


def check(cond, msg):
    print(("  [ok] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAILS.append(msg)


def start_nodes():
    procs = []
    for i, lb in enumerate("ABCD"):
        procs.append(subprocess.Popen([PY, "tools/eval/mobility_node.py", "--label", lb, "--bind", "127.0.0.1", "--ctl_port", str(29911 + 10 * i), "--data_port", str(29912 + 10 * i),
                                       "--mss", "0", "--dry_run", "--dry_sink_mb", "64", "--dry_service_s", "0.2", "--migration_chunk", "30", "--post_chunks", "1500"],
                                      cwd=ROOT, stdout=open(f"/tmp/xbtest_node_{lb}.log", "w"), stderr=subprocess.STDOUT))
    time.sleep(2)
    return procs


def stop(procs):
    for p in procs:
        p.send_signal(signal.SIGTERM)
    for p in procs:
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()


def run(exp, policies, hops, tm, extra=()):
    shutil.rmtree(ROOT / "results/evaluation" / ("_dryrun_" + exp), ignore_errors=True)
    procs = start_nodes()
    try:
        r = subprocess.run([PY, "tools/eval/mobility_orchestrate.py", "--experiment", exp, "--dry_run", "--nodes", NODES, "--mss", "0", "--bw", "100", "--hops", str(hops),
                            "--tm", str(tm), "--policies", policies, "--reps", "1", "--migration_chunk", "30", "--post_chunks", "1500", "--max_run_s", "400",
                            "--xb_horizon", "20", "--dyn_probe", "1"] + list(extra), cwd=ROOT, capture_output=True, text=True, timeout=3000)
    finally:
        stop(procs)
    check(r.returncode == 0, f"{exp}: orchestrator exit {r.returncode} {r.stderr[-400:]}")
    return {json.load(open(d / "summary.json"))["policy"]: d for d in sorted((ROOT / "results/evaluation" / ("_dryrun_" + exp)).glob("policy=*")) if (d / "summary.json").exists()}


def events(d):
    return [dict(r, detail=json.loads(r["detail"]) if r["detail"] else {}) for r in csv.DictReader(open(d / "events.csv", newline=""))]


def metrics(d):
    return [r for r in csv.DictReader(open(d / "metrics.csv", newline=""))]


def first_after_switch(d, s):
    sw = s["switchovers"][-1]
    rows = [m for m in metrics(d) if m["owner"] == sw["dst"] and int(m["call"]) >= int(sw["call"])]
    return rows[0] if rows else None


def main():
    print("- single move A -> B (fake runtime, 100 Mbps)")
    R = run("_xbtest_single", "precopy_full,precopy_sink,recompute_full,recompute_win,split_wait", 1, "1e9")
    for pol in ("precopy_full", "precopy_sink", "recompute_full", "recompute_win"):
        d = R.get(pol)
        check(d is not None, f"{pol}: run written")
        if d is None:
            continue
        s = json.load(open(d / "summary.json"))
        ok, why = run_validity_xb(s, d, dry=True)
        check(ok, f"{pol}: valid {why}; switchovers {s['validation']['n_switchovers']}")
        m = metrics(d)
        src_after = [r for r in m if r["owner"] == "A" and float(r["t_out_rel"]) > 0]
        check(len(src_after) > 0, f"{pol}: the source kept serving after the trigger ({len(src_after)} chunks from A)")
        f = first_after_switch(d, s)
        ev = events(d)
        if pol.startswith("precopy"):
            ver = [e for e in ev if e["event"] == "B:xb_switch_verified"]
            comps = set(ver[-1]["detail"]["components_ok"]) if ver else set()
            want = {"inflight", "meta", "recent", "sink", "vae"} if pol == "precopy_full" else {"sink", "inflight", "meta"}
            check(bool(ver) and ver[-1]["detail"]["ok"] and comps == want, f"{pol}: switchover verified for {sorted(comps)}")
            rounds = [e for e in ev if e["event"] == "A:xb_precopy_round"]
            sw = [e for e in ev if e["event"] == "A:xb_precopy_switch"]
            check(len(rounds) >= 1 and bool(sw), f"{pol}: {len(rounds)} rounds, dirty {[e['detail']['dirty_bytes'] >> 20 for e in rounds]} MiB, switch reason {sw[-1]['detail']['reason'] if sw else None}")
            if pol == "precopy_full":
                check(f is not None and float(f["psnr"]) >= 99, f"precopy_full: first chunk after switchover bit-exact in the fake runtime (psnr {f and f['psnr']})")
                check(sw and sw[-1]["detail"]["reason"] in ("no_shrink", "round_limit"), "precopy_full: does not converge by threshold (recent / VAE rewritten every call in the fake runtime too)")
            else:
                check(f is not None and 40 <= float(f["psnr"]) < 99, f"precopy_sink: Sink bound, not a full-state restore (psnr {f and f['psnr']})")
        else:
            check(f is not None, f"{pol}: destination resumed")
            if pol == "recompute_full":
                check(f is not None and float(f["psnr"]) >= 99, f"recompute_full: exact replay in the fake runtime (psnr {f and f['psnr']})")
                rr = [e for e in ev if e["event"] == "B:xb_recompute_round"]
                check(len(rr) >= 1, f"recompute_full: {len(rr)} replay rounds")
            else:
                check(f is not None and float(f["psnr"]) < 30, f"recompute_win: approximate (psnr {f and f['psnr']})")
            inp = [e for e in ev if e["event"] == "B:xb_inputs_received"]
            check(sum(e["detail"]["bytes"] for e in inp) > 0, f"{pol}: input history transferred ({sum(e['detail']['bytes'] for e in inp) >> 20} MiB)")
            I = s["inputs"]
            check(I["codec"] == "ffv1" and 0 < I["bytes_sent"] < I["raw_bytes"], f"{pol}: FFV1 bytes {I['bytes_sent'] >> 20} MiB < raw {I['raw_bytes'] >> 20} MiB")
            check(all(x["inputs_exact"] for x in I["switchovers"]) and s["validation"]["input_check"], f"{pol}: decoded inputs bit-exact at the switchover; input check on every node")
            sw = s["switchovers"][-1]; call = int(sw["call"])
            rng = next(iter(I["tasks"].values()))["frame_ranges"]
            if pol == "recompute_full":
                check(rng[0][0] == 0 and rng[-1][1] == 5 + 4 * call and all(rng[i][1] == rng[i + 1][0] for i in range(len(rng) - 1)),
                      f"recompute_full: contiguous frames 0 .. {5 + 4 * call} for resume at call {call} ({len(rng)} parts)")
            else:
                need_lo = 5 + 4 * (call - 3) - 1
                check(min(a for a, b in rng) <= need_lo and max(b for a, b in rng) == 5 + 4 * call, f"recompute_win: window frames [{need_lo}, {5 + 4 * call}) covered by {rng}")
            check(I["enc_cpu_s"] > 0 and I["decode_cpu_s"] > 0, f"{pol}: encode {I['enc_cpu_s']:.2f} s, decode {I['decode_cpu_s']:.2f} s CPU recorded")
    for pol in ("precopy_full", "precopy_sink", "recompute_full", "recompute_win"):
        d = R.get(pol)
        if d is None:
            continue
        s = json.load(open(d / "summary.json")); D = s["delivery"]
        est = D["remote_delivery_bytes_ESTIMATED"]
        check(D["remote_chunks"] > 0 and est["crf23"] > est["crf28"] > 0 and est["remote_chunks_not_encoded"] == 0,
              f"{pol}: {D['remote_chunks']} remote-served chunks ({D['remote_wall_s']:.1f} s wall), estimated delivery bytes CRF 23 {est['crf23'] >> 10} KiB / CRF 28 {est['crf28'] >> 10} KiB")
        check(D["ttfo_local_final_s"] is not None and D["delivery_gap_s"] is not None and s["rtt_measured_lan"].get("A-B", {}).get("median_ms") is not None,
              f"{pol}: TTFO-local {D['ttfo_local_final_s']:.2f} s, delivery gap {D['delivery_gap_s']:.2f} s, LAN RTT A-B {s['rtt_measured_lan']['A-B']['median_ms']:.2f} ms")
        if pol in ("precopy_full", "recompute_full"):
            eq = D["output_equivalence"][-1]
            check(eq["checked"] > 0 and eq["matching"] == eq["checked"], f"{pol}: output equivalence after switchover {eq['matching']} / {eq['checked']} calls")
    d = R.get("split_wait")
    if d is not None:
        ev = events(d); m = metrics(d)
        bind = [e for e in ev if e["event"] == "B:sink_bind"]
        bcall = bind[0]["detail"]["call"] if bind else None
        before = [r for r in m if r["owner"] == "B" and bcall is not None and int(r["call"]) < bcall]
        check(bool(bind) and not before, f"split_wait: no Sink-less generation at B (bind at call {bcall}, {len(before)} chunks before it)")
    print("- exactness gate (R-full state digests vs the source at the stop boundary; P-full digests + output equivalence)")
    RG = run("_xbtest_gate", "precopy_full,recompute_full", 1, "1e9", ["--xb_verify_state"])
    for pol, d in RG.items():
        s = json.load(open(d / "summary.json"))
        ok, why = run_validity_xb(s, d, dry=True)
        check(ok and s["xb_params"]["verify_state"], f"gate {pol}: valid {why}")
        if pol == "recompute_full":
            check(s["validation"].get("recompute_state_verified") is True, "gate recompute_full: replayed state digests == source digests (dry: protocol only)")
        r = subprocess.run([PY, "tools/eval/check_xb_gate.py", "--root", str(d.parent)], cwd=ROOT, capture_output=True, text=True)
        check(r.returncode == 0 and "PASS" in r.stdout, f"gate checker on {pol}: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]}")
    print("- lossy input sensitivity (H.264 CRF 23), single move")
    R3 = run("_xbtest_lossy", "recompute_full,recompute_win", 1, "1e9", ["--xb_codec", "h264_crf23"])
    for pol, d in R3.items():
        s = json.load(open(d / "summary.json"))
        ok, why = run_validity_xb(s, d, dry=True)
        I = s["inputs"]
        check(ok and not I["lossless"] and "codec=h264_crf23" in d.name, f"{pol} CRF 23: valid as a sensitivity run {why}")
        check(not any(x["inputs_exact"] for x in I["switchovers"]) and all(t["min_psnr"] is not None for t in I["tasks"].values()),
              f"{pol} CRF 23: inputs not bit-exact (min PSNR {[t['min_psnr'] and round(t['min_psnr'], 1) for t in I['tasks'].values()]})")
        check(I["bytes_sent"] * 20 < I["raw_bytes"], f"{pol} CRF 23: {I['bytes_sent'] >> 10} KiB vs raw {I['raw_bytes'] >> 20} MiB")
    print("- repeated mobility A -> B -> C -> D, rho 2 (T_m 2.7 s; tasks cancelled and retargeted)")
    R2 = run("_xbtest_rho2", "precopy_sink,recompute_full,precopy_full", 3, "2.7")
    for pol, d in R2.items():
        s = json.load(open(d / "summary.json"))
        ok, why = run_validity_xb(s, d, dry=True)
        outcomes = [t["outcome"] for t in s["tasks"]]
        check(ok and s["validation"]["final_edge_served"], f"{pol}: valid {why}; task outcomes {outcomes}; final owner D")
        check("cancelled" in outcomes, f"{pol}: at least one task cancelled by a move")
        check(all(sw["dst"] in ("B", "C", "D") for sw in s["switchovers"]) and s["switchovers"][-1]["dst"] == "D", f"{pol}: switchovers {[(sw['dst'], sw['call']) for sw in s['switchovers']]}")
        if pol == "recompute_full":
            I = s["inputs"]
            starts = [t["frame_ranges"][0][0] for t in I["tasks"].values()]
            check(all(x == 0 for x in starts), f"recompute_full rho 2: every target receives the history from frame 0 (no reuse across targets): {starts}")
            check(I["bytes_abandoned_targets"] > 0, f"recompute_full rho 2: bytes to abandoned targets counted ({I['bytes_abandoned_targets'] >> 20} MiB of {I['bytes_sent'] >> 20} MiB)")
    print("\nALL PASS" if not FAILS else f"\nFAILURES ({len(FAILS)}):\n  " + "\n  ".join(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
