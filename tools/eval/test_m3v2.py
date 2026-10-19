#!/usr/bin/env python3
"""M3-v2 unit and replay tests (CPU only). Development data: the frozen Experiment N traces (cells 7-10); passing them is a
regression check, not evidence (results/evaluation/osdi/expN/m3_root_cause.md).

    python tools/eval/test_m3v2.py
"""

from __future__ import annotations

import csv
import glob
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
from restore_planner import SOURCE, bps_to_Bps, dyn_decide_v2, fluid_eta, update_bottlenecks  # noqa: E402

MiB = 1 << 20
FLEN = 4 * MiB
WINDOW, CTRL, EPS, REL, WARMUP, PERIOD = 2.0, 0.3, 2.0, 0.10, 2.0, 0.5
NODES = ["A", "B", "C", "D"]
FAILS = []


def check(name, cond, detail=""):
    print(f"  [{'ok' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        FAILS.append(name)


def test_units():
    print("units")
    check("1 Gbps -> 125 MB/s", abs(bps_to_Bps(1e9) - 125e6) < 1e-6)
    check("62.5 Mbps -> 7.8125 MB/s", abs(bps_to_Bps(62.5e6) - 7812500.0) < 1e-6)
    check("one 4 MiB fragment per 2 s window = 2.097 MB/s = 16.78 Mbps", abs(FLEN / WINDOW * 8 / 1e6 - 16.777216) < 1e-6)


def test_fluid():
    print("fluid ETA")
    Bps = bps_to_Bps
    c = {"A": Bps(1e9), "B": Bps(1e9)}
    # shared 1 Gbps ingress: any split of 352 fragments takes the same time
    t1 = fluid_eta({"A": 100 * FLEN, "B": 252 * FLEN}, c, Bps(1e9), "C")
    t2 = fluid_eta({"A": 176 * FLEN, "B": 176 * FLEN}, c, Bps(1e9), "C")
    t3 = fluid_eta({"B": 352 * FLEN}, c, Bps(1e9), "C")
    check("shared ingress: split-independent", abs(t1 - t2) < 1e-6 and abs(t1 - t3) < 1e-6, f"{t1:.2f} {t2:.2f} {t3:.2f} s (expect {352 * FLEN / Bps(1e9):.2f})")
    # holder B capped at 62.5 Mbps: moving its load to A helps
    c2 = {"A": Bps(1e9), "B": Bps(62.5e6)}
    tb = fluid_eta({"B": 300 * FLEN}, c2, Bps(1e9), "C"); ta = fluid_eta({"A": 300 * FLEN}, c2, Bps(1e9), "C")
    check("provider-limited holder: moving helps", tb > 150 and ta < 11, f"{tb:.1f} -> {ta:.1f} s")
    # max-min with a finishing provider: B at 62.5 and A at 1 Gbps sharing a 1 Gbps ingress
    t = fluid_eta({"A": 100 * FLEN, "B": 10 * FLEN}, c2, Bps(1e9), "C")
    check("fluid: B (10 fragments at 62.5 Mbps) is the long pole, A finishes at 937 Mbps", 5.2 < t < 5.5, f"{t:.2f} s (expect 5.37)")


def test_estimator():
    print("bottleneck estimator")
    Bps = bps_to_Bps
    nom = {n: Bps(1e9) for n in NODES}
    res = FLEN / WINDOW
    st = {}
    ub = lambda st_, r_, t_: update_bottlenecks(st_, r_, nom, Bps(1e9), res, now=t_, window=WINDOW, flen=FLEN)  # noqa: E731
    ub(st, {"A": Bps(486.5e6), "B": Bps(486.5e6)}, 10.0)
    check("balanced shares on a full ingress: no provider limited, I stays ~1 Gbps", st["I_est"] > Bps(950e6) and st["c_est"]["A"] == nom["A"], f"I {st['I_est'] * 8 / 1e6:.0f} Mbps")
    ub(st, {"A": Bps(937e6), "B": Bps(62e6)}, 12.5)
    check("B drops in one window only: not yet attributed (transient)", st["c_est"]["B"] == nom["B"])
    ub(st, {"A": Bps(937e6), "B": Bps(62e6)}, 13.0)
    check("B drops while A rises, two windows: B provider-limited", st["c_est"]["B"] < Bps(70e6) and st["c_est"]["A"] >= Bps(930e6), f"c_B {st['c_est']['B'] * 8 / 1e6:.0f} Mbps")
    st2 = {}
    ub(st2, {"A": Bps(486.5e6), "B": Bps(486.5e6)}, 10.0)
    for i in range(12):
        ub(st2, {"A": Bps(16.8e6), "B": Bps(33.6e6)}, 12.5 + 0.5 * i)
    check("both drop together (quantized 1 vs 2 fragments): ingress-limited, no provider limited", st2["I_est"] < Bps(60e6) and st2["c_est"]["A"] == nom["A"] and st2["c_est"]["B"] == nom["B"],
          f"I {st2['I_est'] * 8 / 1e6:.1f} Mbps, c_A {st2['c_est']['A'] * 8 / 1e6:.0f}")
    for i in range(12):
        ub(st2, {"A": Bps(33.6e6), "B": Bps(16.8e6)}, 19.0 + 0.5 * i)
    check("flipped quantization: still no provider limited", st2["c_est"]["A"] == nom["A"] and st2["c_est"]["B"] == nom["B"])


def decide(state, act, rate, held, now, nom_in=1e9):
    nom_out = {n: bps_to_Bps(1e9) for n in NODES}
    return dyn_decide_v2(own="C", act=act, rate=rate, state=state, now=now, held=held, nom_out=nom_out, nom_in=bps_to_Bps(nom_in), flen=FLEN, nodes=NODES,
                         window=WINDOW, ctrl=CTRL, eps=EPS, rel=REL)


def test_decisions():
    print("decisions (synthetic)")
    Bps = bps_to_Bps
    held = {"A": set(range(412)), "B": set(range(299)), "C": set(), "D": set()}
    act = [{"src": "B", "left": set(range(30, 299)), "order": list(range(30, 299))}, {"src": "A", "left": set(range(330, 412)), "order": list(range(330, 412))}]
    st = {}
    d = decide(st, act, {"A": Bps(486.5e6), "B": Bps(486.5e6)}, held, 12.3)
    check("cell-7 situation (shared ingress, balanced): no re-plan", d is None)
    # holder degraded: B 62 Mbps, A 937
    decide(st, act, {"A": Bps(937e6), "B": Bps(62e6)}, held, 17.9)
    d = decide(st, act, {"A": Bps(937e6), "B": Bps(62e6)}, held, 18.4)
    check("cell-9 situation (holder egress degraded): one joint move of (almost all) B's movable fragments to A, balanced by capacity", d is not None and set(d["assign"]) == {"A"} and len(d["assign"]["A"]) >= 240 and d["eta_new"] < 14,
          f"{None if d is None else (dict((k, len(v)) for k, v in d['assign'].items()), round(d['eta_cur'], 1), round(d['eta_new'], 1))}")
    # after the move: B keeps only its head; next window B 62, A 937 -> nothing to move back
    act2 = [{"src": "B", "left": {30}, "order": [30]}, {"src": "A", "left": set(range(31, 299)) | set(range(330, 412)), "order": list(range(31, 299)) + list(range(330, 412))}]
    d = decide(st, act2, {"A": Bps(937e6), "B": Bps(62e6)}, held, 20.4)
    check("after the move: no further re-plan", d is None)
    # ingress degraded to 62.5 and shared: quantized rates flip between windows
    st3 = {}
    decide(st3, act, {"A": Bps(486.5e6), "B": Bps(486.5e6)}, held, 12.3)
    n_re = 0
    for i, r in enumerate([(16.8, 33.6), (33.6, 33.6), (16.8, 33.6), (33.6, 16.8), (16.8, 33.6), (33.6, 16.8)]):
        d = decide(st3, act, {"A": Bps(r[0] * 1e6), "B": Bps(r[1] * 1e6)}, held, 19.4 + 2.5 * i)
        n_re += d is not None
    check("cell-10 situation (ingress degraded, quantized flips): no re-plan over 6 windows", n_re == 0, f"re-plans {n_re}, I_est {st3['I_est'] * 8 / 1e6:.1f} Mbps")
    # source degraded (cell 8): A 62, B 937 -> move A's fragments that B holds to B; fragments only A holds stay
    st4 = {}
    decide(st4, act, {"A": Bps(486.5e6), "B": Bps(486.5e6)}, held, 12.3)
    decide(st4, act, {"A": Bps(62e6), "B": Bps(937e6)}, held, 17.9)
    d = decide(st4, act, {"A": Bps(62e6), "B": Bps(937e6)}, held, 18.4)
    only_a = set(range(330, 412)) - held["B"]
    check("cell-8 situation (source degraded): nothing movable to B (A's fragments are held only by A) -> no re-plan", d is None, f"only-A fragments {len(only_a)}")
    act5 = [{"src": "B", "left": set(range(30, 200)), "order": list(range(30, 200))}, {"src": "A", "left": set(range(200, 299)), "order": list(range(200, 299))}]
    d = decide(st4, act5, {"A": Bps(62e6), "B": Bps(937e6)}, held, 20.4)
    check("source degraded while A sends fragments B also holds: move (almost all of) them to B, none the other way", d is not None and set(d["assign"]) == {"B"} and len(d["assign"]["B"]) >= 80, f"{None if d is None else dict((k, len(v)) for k, v in d['assign'].items())}")


def test_probe_cycle():
    print("probe cycle (single-provider ambiguity)")
    Bps = bps_to_Bps
    held = {"A": set(range(412)), "B": set(range(299)), "C": set(), "D": set()}
    actB = [{"src": "B", "left": set(range(30, 299)), "order": list(range(30, 299))}]
    # cell-9 shape: A finished, B alone steady at 62 Mbps while I_est is the nominal 1 Gbps
    st = {}
    for i in range(6):
        d = decide(st, actB, {"B": Bps(62e6)}, held, 20.0 + 0.5 * i)
        if d is not None:
            break
    check("B alone below the ingress estimate: a probe of 4 fragments to A", d is not None and d["probe"] and set(d["assign"]) == {"A"} and len(d["assign"]["A"]) == 4 and d["probe_provider"] == "B", f"{None if d is None else (d['probe'], dict((k, len(v)) for k, v in d['assign'].items()))}")
    st["probe_pending"] = {"provider": "B", "flow": "fx", "t": 23.0}
    d2 = decide(st, actB, {"B": Bps(62e6)}, held, 23.5)
    check("while the probe is pending: no decision", d2 is None)
    st["probe_pending"] = None; st["probe_result"] = {"provider": "B", "rate": Bps(937e6), "duration_s": 0.14, "bytes": 4 * FLEN}
    act2 = [{"src": "B", "left": set(range(30, 295)), "order": list(range(30, 295))}]
    d3 = decide(st, act2, {"B": Bps(62e6)}, held, 24.0)
    check("probe delivered at 937 Mbps (>> B's 62): confirmed, the rest moves to A in one decision", d3 is not None and not d3["probe"] and set(d3["assign"]) == {"A"} and len(d3["assign"]["A"]) >= 240, f"{None if d3 is None else (d3['probe'], dict((k, len(v)) for k, v in d3['assign'].items()), round(d3['eta_cur'], 1), round(d3['eta_new'], 1))}")
    # cell-10 shape: ingress degraded to 62.5; B alone measures ~45; the probe shares the ingress (rate ~30)
    st = {}
    for i in range(6):
        d = decide(st, actB, {"B": Bps(45e6)}, held, 20.0 + 0.5 * i)
        if d is not None:
            break
    check("B alone at 45 Mbps: a probe", d is not None and d["probe"])
    st["probe_pending"] = None; st["probe_result"] = {"provider": "B", "rate": Bps(30e6), "duration_s": 4.5, "bytes": 4 * FLEN}
    n_dec = 0
    for i in range(20):
        d = decide(st, act2, {"B": Bps(45e6)}, held, 25.0 + 0.5 * i)
        n_dec += d is not None
    check("probe only shared the rate: withdrawn, I_est ~ 75 Mbps, no further decision over 20 checks", n_dec == 0 and st["I_est"] < Bps(90e6) and st["c_est"]["B"] == Bps(1e9), f"decisions {n_dec}, I_est {st['I_est'] * 8 / 1e6:.0f} Mbps, c_B {st['c_est']['B'] * 8 / 1e6:.0f}")
    # confirmed provider whose re-started flow has not delivered yet (measured rate 0): the decision is not blocked
    st5 = {}
    for i in range(6):
        d = decide(st5, actB, {"B": Bps(62e6)}, held, 20.0 + 0.5 * i)
        if d is not None:
            break
    st5["probe_pending"] = None; st5["probe_result"] = {"provider": "B", "rate": Bps(937e6), "duration_s": 0.14, "bytes": 4 * FLEN}
    d5 = decide(st5, act2, {"B": 0.0}, held, 24.0)
    check("confirmed B with a re-started flow at measured rate 0: full move still decided (drain from the capacity estimate)", d5 is not None and not d5["probe"] and set(d5["assign"]) == {"A"}, f"{None if d5 is None else (d5['c_switch'], dict((k, len(v)) for k, v in d5['assign'].items()))}")
    # ingress recovers: B alone now at 500 Mbps -> I_est rises (upward revision), later a real drop may be probed again
    for i in range(6):
        decide(st, act2, {"B": Bps(500e6)}, held, 40.0 + 0.5 * i)
    check("ingress recovery raises I_est and unblocks", st["I_est"] > Bps(400e6) and "B" not in st["withdrawn"], f"I_est {st['I_est'] * 8 / 1e6:.0f}, withdrawn {st['withdrawn']}")


def replay_cell(cell: int):
    """Replay a frozen run's measurement stream (orchestrator fragments.csv recv rows at the destination) through v2.
    The stream of the **at-moves** run (reuse_aware_in, which never re-plans) is exactly what v2 observes as long as v2 has
    not re-planned either, so the replay is faithful for the whole run where v2 makes no decision (cells 7, 10) and up to
    v2's first decision otherwise (cells 8, 9). Returns v2's decisions and v1's first re-plan time (for information)."""
    am = sorted(glob.glob(str(ROOT / f"results/evaluation/expN_cell{cell}/policy=reuse_aware_in_*rep=1_*")))[-1] + "/"
    v1 = sorted(glob.glob(str(ROOT / f"results/evaluation/expN_cell{cell}/policy=reuse_dyn_*rep=1_*")))[-1] + "/"
    s = json.load(open(am + "summary.json")); s1 = json.load(open(v1 + "summary.json"))
    rows = [r for r in csv.DictReader(open(am + "fragments.csv")) if r["event"] == "recv" and r["ok"] == "True"]
    t_move = s["t_final_move_rel_s"]
    held = {"A": set(range(412)), "B": {int(r["fragment_id"]) for r in rows if r["dst"] == "B" and float(r["t_rel"]) <= t_move}, "C": set(), "D": set()}
    recv = [(float(r["t_rel"]), r["src"], int(r["fragment_id"]), int(r["bytes"])) for r in rows if r["dst"] == "C"]
    flows = {}
    for r in csv.DictReader(open(am + "events.csv")):
        if r["event"] == "flow_start":
            det = json.loads(r["detail"])
            if det.get("dst") == "C" and abs(float(r["t_rel"]) - t_move) < 0.5:
                flows[det["src"]] = det["n"]
    # the source's flow takes the last n_A of the fragments B does not hold (the first ones are in flight to B and are
    # forwarded by B once they land: "late"); everything else is B's
    not_held = sorted(set(range(412)) - held["B"])
    left = {"A": set(not_held[len(not_held) - flows.get("A", 0):]) if flows.get("A", 0) else set()}
    left["B"] = set(range(412)) - left["A"]
    verified, rx = set(), {"A": deque(), "B": deque()}
    st, last_plan, decisions = {}, t_move, []
    t = t_move + WARMUP
    end = s["latency_after_final_move_s"]["sink_verified"] + t_move
    cap_t = s["d0"]["cap_changes"][0][0] if s["d0"]["cap_changes"] else None
    while t < end:
        for tr, src, f, b in recv:
            if tr <= t and f not in verified:
                verified.add(f); rx[src].append((tr, b)); left[src].discard(f)
        rate, act = {}, []
        for src in ("A", "B"):
            while rx[src] and rx[src][0][0] < t - WINDOW:
                rx[src].popleft()
            if left[src]:
                rate[src] = sum(b for _, b in rx[src]) / WINDOW
                act.append({"src": src, "left": set(left[src]), "order": sorted(left[src])})
        if act and t - last_plan >= WARMUP:
            dd = decide(st, act, rate, held, t)
            if dd is not None:
                decisions.append({"t_after_move": round(t - t_move, 2), "after_change": None if cap_t is None else round(t - cap_t, 2), "to": {k: len(v) for k, v in dd["assign"].items()},
                                  "eta": (round(dd["eta_cur"], 1), round(dd["eta_new"], 1)), "I_est_mbps": round(dd["I_est"] * 8 / 1e6), "c_est_mbps": {k: round(v * 8 / 1e6) for k, v in dd["c_est"].items() if k in ("A", "B")}})
                break   # the stream is no longer faithful after a v2 decision
        t += PERIOD
    v1_first = s1["d0"]["replans"][0]["t_s"] - t_move if s1["d0"]["replans"] else None
    return decisions, v1_first, (None if cap_t is None else cap_t - t_move)


def test_replay():
    print("replay of the frozen at-moves streams (development data)")
    expect = {7: "none", 8: "none", 9: "first decision after the change: a probe of <= 4 fragments to A (single-provider evidence)", 10: "none, or a single probe of <= 4 fragments (single-provider ambiguity)"}
    for cell in (7, 8, 9, 10):
        try:
            dec, v1_first, chg = replay_cell(cell)
        except (IndexError, FileNotFoundError) as e:
            print(f"  [skip] cell {cell}: {e}"); continue
        if cell == 9:
            ok = len(dec) == 1 and set(dec[0]["to"]) == {"A"} and dec[0]["after_change"] > 0 and dec[0]["to"]["A"] <= 4
        elif cell == 10:
            ok = not dec or (len(dec) == 1 and set(dec[0]["to"]) == {"A"} and dec[0]["to"]["A"] <= 4)
        else:
            ok = not dec
        check(f"cell {cell}: expected {expect[cell]}", ok, f"v2 {dec}; change at +{chg}; v1 first re-plan at +{v1_first and round(v1_first, 1)} s")




if __name__ == "__main__":
    test_units(); test_fluid(); test_estimator(); test_decisions(); test_probe_cycle(); test_replay()
    print("FAILED:" if FAILS else "ALL PASS", FAILS)
    sys.exit(1 if FAILS else 0)
