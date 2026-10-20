#!/usr/bin/env python3
"""Experiment RD CPU / dry validation (preregistration frozen f850072): schedules, Phase 0 transcription against the frozen
real runs, the emulation runner's withheld-Sink rule on the fake runtime, outcome functions, and (when OpenCV is
importable) the no-reference metrics on synthetic frames.

    python tools/eval/test_rd.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import numpy as np  # noqa: E402

import rd_metrics as rm  # noqa: E402
import rd_schedule as rs  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  [ok] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAILS.append(msg)


def schedules():
    print("- schedules (section 3 / 6)")
    allc = [c for w in rs.PHASE1_WORKLOADS for c in rs.phase1(w)]
    check(len(allc) == 100, f"Phase 1 = {len(allc)} runs (frozen: 100)")
    check(all(not rs.validate(c) for c in allc + rs.phase0()), "every schedule passes the structural checks")
    d = {c["id"]: c for c in rs.phase1("dog")}
    exp = {"b155_r1_d0": ([155], [155]), "b155_r1_d10": ([145], [155]), "b155_r1_d100": ([55], [155]), "b155_r3c_d75": ([80, 105, 130], [155]),
           "b155_r3c_d25": ([130, 138, 147], [155]), "b155_r3e_d75": ([30, 80, 130], [55, 105, 155]), "b155_r3e_d0": ([105, 130, 155], [105, 130, 155]),
           "b175_r1_d100": ([75], [175]), "b175_r3e_d75": ([50, 100, 150], [75, 125, 175])}
    for k, (r, b) in exp.items():
        check(d[k]["resets"] == r and d[k]["binds"] == b, f"{k}: resets {d[k]['resets']}, binds {d[k]['binds']}")
    check(all(len(rs.sinkless_calls(c)) == c["d"] for c in allc), "Sink-less calls == d in every condition (reset count never changes d)")
    check(all(min(c["resets"]) >= 30 and c["end"] == c["anchor"] + 99 for c in allc), "every reset at or after call 30; horizon b .. b + 99")


def phase0_transcription():
    print("- Phase 0 targets vs the frozen real runs")
    from aggregate_rd import real_run
    for t in rs.PHASE0:
        r = real_run(t["target"])
        check(r["resets"] == t["resets"] and r["binds"] == t["binds"], f"{t['id']}: real moves {r['resets']} binds {r['binds']} ({r['dir']})")


def runner_dry():
    print("- emulation runner on the fake runtime (withheld-Sink rule)")
    for p in (0, 1):
        shutil.rmtree(ROOT / f"results/evaluation/_dryrun_expRD_phase{p}", ignore_errors=True)
    # bound fake Sinks change at these calls, so fresh (withheld at a bound reset) and trigger Sinks differ
    promo = "60,110,140,160"
    for w, ph in (("dog", 1), ("butterfly-feeding-slow-motion", 0), ("dog", 0)):
        r = subprocess.run([sys.executable, "tools/eval/rd_emulate.py", "--workload", w, "--phase", str(ph), "--dry_run", "--dry_promote_calls", promo], cwd=ROOT, capture_output=True, text=True)
        check(r.returncode == 0, f"rd_emulate {w} phase {ph} exit {r.returncode} {r.stderr[-300:]}")
    S = {}
    for d in (ROOT / "results/evaluation").glob("_dryrun_expRD_phase*/*/*"):
        s = json.load(open(d / "summary.json")); S[s["condition"]["id"]] = s
    check(len([k for k in S if k.startswith("b")]) == 25 and len([k for k in S if k.startswith("P0")]) == 5, f"{len(S)} condition runs written (25 dog Phase 1 + 5 Phase 0)")
    check(all(s["valid"] for s in S.values()), "every dry run valid (schedule realized, withheld rule, no missing call)")
    for k, s in S.items():
        ops = [(e["op"], e.get("sink")) for e in s["events"] if e["op"] != "bind"]
        st_ = s["condition"]["structure"]
        if st_ == "r3c":
            ok = ops == [("episode_open", "packed"), ("reset_inside_episode", "kept"), ("reset_inside_episode", "kept")] and s["bound_sink"][-1]["packed_at"] == s["condition"]["resets"][0]
            check(ok, f"{k}: Sink packed once at {s['condition']['resets'][0]}, kept through two resets, that Sink bound")
        elif st_ == "r3e":
            check(ops == [("episode_open", "packed")] * 3 and [b["packed_at"] for b in s["bound_sink"]] == s["condition"]["resets"], f"{k}: one Sink packed per episode, each bound at its episode's bind")
    p3, p4 = S["P0-3_VA_bfly_rho0.5_split"], S["P0-4_VA_bfly_rho0.5_restart_fresh"]
    check(len({b["sha"] for b in p3["bound_sink"]}) == 1 and [e.get("sink") for e in p3["events"] if e["op"] == "episode_open"] == ["packed", "trigger", "trigger"],
          "P0-3 (stale): the trigger Sink is rebound in all three episodes")
    check(len({b["sha"] for b in p4["bound_sink"]}) == 3, "P0-4 (fresh): three different Sinks (each packed from the bound session at its reset)")


def outcomes():
    print("- outcome functions (section 5.1)")
    ps = {c: (20.0 if c < 110 else 36.0) for c in range(100, 200)}
    t = rm.trajectory(ps, 100)
    check(t["crossed"] and t["cross_call"] == 110 and t["sustained"] and t["sustain_call"] == 110 and t["T"] == 36.0, f"step trajectory {t}")
    ps2 = {c: (36.0 if c % 2 else 20.0) for c in range(100, 200)}
    t2 = rm.trajectory(ps2, 100)
    check(t2["crossed"] and not t2["sustained"], "alternating PSNR: crossing without sustained recovery")
    t3 = rm.trajectory(ps, 100, calls=set(range(100, 125)))
    check(t3["n"] == 25 and t3["T"] == 36.0, "restricted common-call window uses its own last 10 calls")


def metrics():
    print("- no-reference metrics (section 5.2)")
    try:
        import cv2  # noqa: F401
    except ImportError:
        print("  [skip] OpenCV not importable here (run with an OpenCV environment)"); return
    rng = np.random.default_rng(0)
    base = (rng.random((140, 220)) * 255).astype(np.uint8)
    import cv2
    base = cv2.GaussianBlur(base, (0, 0), 3)
    I = [np.roll(base, 2 * k, axis=1)[10:130, 6:214] for k in range(24)]   # input: rightward motion, 2 px / frame
    O_same = [x.copy() for x in I]
    O_static = [I[0].copy() for _ in I]
    O_noisy = [np.clip(x.astype(int) + rng.integers(-40, 40, x.shape), 0, 255).astype(np.uint8) for x in I]
    seq = lambda O: [{"call": c, "O": O[4 * c:4 * c + 4], "R": I[4 * c:4 * c + 4], "I": I[4 * c:4 * c + 4]} for c in range(6)]  # noqa: E731
    win = {"all": set(range(6))}
    a = rm.no_reference(seq(O_same), win, [("bind", 3)])["all"]
    check(abs(a["E_ratio"] - 1.0) < 1e-6 and a["band"] == "comparable" and abs(a["motion_ratio"] - 1) < 1e-6, f"output = reference: ratio {a['E_ratio']:.3f}, comparable")
    s_ = rm.no_reference(seq(O_static), win, [])["all"]
    check(s_["possibly_static"] and s_["motion_ratio"] < 0.5, f"static output flagged (motion ratio {s_['motion_ratio']:.2f}; E ratio {s_['E_ratio']:.2f}, band '{s_['band']}')")
    n_ = rm.no_reference(seq(O_noisy), win, [])["all"]
    check(n_["E_ratio"] > 1.25 and n_["band"] == "less consistent with input motion", f"flickering output: ratio {n_['E_ratio']:.2f}")
    e = rm.no_reference(seq(O_same), win, [("bind", 3)])["event_spikes"][0]
    check(e["spike_O"] is not None and abs(e["spike_O"] - e["spike_R"]) < 1e-6, f"event spike computed at a call boundary (O {e['spike_O']:.2f} = R)")


if __name__ == "__main__":
    schedules(); phase0_transcription(); runner_dry(); outcomes(); metrics()
    print("\nALL PASS" if not FAILS else f"\nFAILURES ({len(FAILS)}):\n  " + "\n  ".join(FAILS))
    sys.exit(1 if FAILS else 0)
