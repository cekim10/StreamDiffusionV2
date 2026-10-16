#!/usr/bin/env python3
"""Equivalence test for the shared restoration planner (tools/eval/restore_planner.py).

The planner code was moved out of restore_orchestrate.py. This test loads the pre-refactor orchestrator from git
(default commit e345ccd, which produced every network-level result) and the current one, drives both through the same
randomized states, and requires identical decisions:

    plan()          every policy (restart, reuse_fixed, reuse_adaptive, reuse_aware, reuse_aware_in, reuse_dyn, pp_star,
                    fixed_line, fixed_tree, fixed_butterfly): the exact (provider, destination, ordered fragment list) of
                    every flow started, and the flows cancelled
    dyn_check()     the re-plan decision (bottleneck, moved fragments per provider, ETAs, switching cost, margin),
                    the FLOW_ADD / FLOW_CANCEL commands, and the persistent rate-estimate store
    prepos_start()  the allocation and the fragment sets per candidate
    dissem_assign() every (fragment, destination) provider
    fluid model     restore_model predictions at a few configurations (it imports maxmin / parse_cap_events / dissem_assign)

    python tools/eval/test_restore_planner.py [--ref e345ccd] [--n 4000]
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import random
import subprocess
import sys
import tempfile
import types
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "tools", ROOT / "tools" / "eval"):
    sys.path.insert(0, str(p))

POLICIES = ["restart", "reuse_fixed", "reuse_adaptive", "reuse_aware", "reuse_aware_in", "reuse_dyn",
            "pp_star", "fixed_line", "fixed_tree", "fixed_butterfly"]
EDGES = ["B", "C", "D"]
CAPS = [62.5e6, 125e6, 250e6, 500e6, 1000e6]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Recorder:
    def __init__(self):
        self.calls = []

    def node(self, lb):
        rec = self

        class N:
            def cast(self, kind, **kw):
                rec.calls.append(("cast", lb, kind, tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in kw.items() if k != "flow_id"))))

            def call(self, kind, **kw):
                rec.calls.append(("call", lb, kind))
                return {}
        return N()


def make_run(mod, state, rec):
    run = object.__new__(mod.Run)
    for k, v in copy.deepcopy(state).items():
        setattr(run, k, v)
    run.node = rec.node
    run.realloc = lambda: None
    run.ev = types.SimpleNamespace(log=lambda *a, **k: None)
    run.lens = [state["flen"]] * state["nfr_"]
    started = []

    def start_flow(sid, src, dst, fids, reason, keep_order=False, closed=True):
        if not fids and closed:
            return None
        started.append((sid, src, dst, list(fids) if keep_order else sorted(fids)))
        run.nflow = getattr(run, "nflow", 0) + 1
        fl = {"id": f"new{run.nflow}", "sid": sid, "src": src, "dst": dst, "left": set(fids), "active": True, "order": list(fids), "n": len(fids),
              "bytes": 0, "rate": 0.0, "started": True, "t_start": 0.0, "t_end": None, "cancelled": False, "reason": reason}
        run.flows[fl["id"]] = fl
        return fl
    run.start_flow = start_flow
    run._started = started
    return run


def random_state(rng, policy, nfr=40):
    sids = [f"s{i}" for i in range(rng.choice([1, 1, 2, 4]))]
    sid = rng.choice(sids)
    own = rng.choice(EDGES)
    hist_len = rng.randint(1, 5)
    history = []
    cur = rng.choice(EDGES + (["A"] if rng.random() < 0.3 else []))
    for _ in range(hist_len - 1):
        history.append(cur); cur = rng.choice([e for e in EDGES if e != cur] or EDGES)
    history.append(own)
    history[-1] = own
    held = {s: {e: set() for e in ["A"] + EDGES} for s in sids}
    inflight = {s: defaultdict(set) for s in sids}
    skipped = {s: set() for s in sids}
    for s in sids:
        held[s]["A"] = set(range(nfr))
        for e in EDGES:
            if rng.random() < 0.7:
                held[s][e] = set(rng.sample(range(nfr), rng.randint(0, nfr)))
            if rng.random() < 0.4:
                inflight[s][e] = set(rng.sample(range(nfr), rng.randint(0, 6)))
        if rng.random() < 0.3:
            skipped[s] = set(rng.sample(range(nfr), rng.randint(0, 5)))
    flows = {}
    for i in range(rng.randint(0, 7)):
        s_ = rng.choice(sids); src = rng.choice(["A"] + EDGES); dst = rng.choice([e for e in EDGES if e != src])
        left = set(rng.sample(range(nfr), rng.randint(0, 12)))
        order = list(left); rng.shuffle(order)
        active = rng.random() < 0.7
        flows[f"f{i}"] = {"id": f"f{i}", "sid": s_, "src": src, "dst": dst, "left": left, "order": order + [x for x in range(nfr) if x not in left][:2],
                          "active": active, "draining": (not active) and rng.random() < 0.6, "n": len(left), "bytes": rng.randint(0, 10) * 4194304,
                          "rate": 0.0, "started": True, "t_start": 0.0, "t_end": None, "cancelled": not active, "reason": "x"}
    caps = {(d, n): rng.choice(CAPS) for d in ("out", "in") for n in ["A"] + EDGES}
    known = dict(caps) if rng.random() < 0.6 else {(d, n): rng.choice(CAPS) for d in ("out", "in") for n in ["A"] + EDGES}
    owner = {s: rng.choice(EDGES) for s in sids}; owner[sid] = own
    hist = {s: [owner[s]] for s in sids}; hist[sid] = history
    return sid, {"policy": policy, "N": len(sids), "sids": sids, "owner": owner, "history": hist, "held": held, "inflight": inflight, "skipped": skipped,
                 "flows": flows, "nflow": 0, "caps": caps, "known_caps": known, "flen": 4 << 20, "nfr_": nfr, "last_plan_t": {s: 0.0 for s in sids},
                 "t0": 0.0, "rate_est": {}, "cap_changes": [], "replans": [], "move_t": {s: None for s in sids}, "restored_now": {s: False for s in sids},
                 "restored": defaultdict(list), "owner_since": {}, "flow_rx": defaultdict(deque),
                 "a": types.SimpleNamespace(dyn_warmup=2.0, dyn_window=2.0, dyn_period=0.5, dyn_eps=2.0, dyn_rel=0.10, dyn_ctrl=0.3, sink_bytes=nfr * (4 << 20))}


def compare_plan(old, new, n, rng):
    diffs = 0
    for i in range(n):
        policy = POLICIES[i % len(POLICIES)]
        sid, st = random_state(rng, policy)
        reason = rng.choice(["move", "start", "flow_done"])
        out = []
        for mod in (old, new):
            rec = Recorder(); run = make_run(mod, st, rec)
            run.plan(sid, reason)
            flows_after = {k: (v["active"], v.get("draining"), tuple(sorted(v["left"]))) for k, v in run.flows.items() if not k.startswith("new")}
            out.append((sorted(run._started), sorted(rec.calls), flows_after, {e: sorted(v) for e, v in run.held[sid].items()}))
        if out[0] != out[1]:
            diffs += 1
            if diffs <= 3:
                print(f"  plan diff ({policy}, {reason}): old {out[0][0]} new {out[1][0]}")
    return diffs


def compare_dyn(old, new, n, rng):
    diffs = fired = 0
    for i in range(n):
        sid, st = random_state(rng, "reuse_dyn")
        own = st["owner"][sid]
        # active flows to the owner with measurement history
        st["flows"] = {}
        for j, src in enumerate(rng.sample(["A"] + [e for e in EDGES if e != own], rng.randint(1, 3))):
            left = set(rng.sample(range(st["nfr_"]), rng.randint(1, 30)))
            order = sorted(left); rng.shuffle(order)
            if src != "A":
                st["held"][sid][src] |= left
            st["flows"][f"f{j}"] = {"id": f"f{j}", "sid": sid, "src": src, "dst": own, "left": left, "order": order, "active": True, "n": len(left),
                                    "bytes": 0, "rate": 0.0, "started": True, "t_start": 0.0, "t_end": None, "cancelled": False, "reason": "x"}
            st["flow_rx"][f"f{j}"] = deque((9.0 + 0.01 * k, 4194304) for k in range(rng.choice([0, 1, 3, 10, 40])))
        if rng.random() < 0.5:
            st["rate_est"] = {(sid, rng.choice(["A"] + EDGES)): (rng.choice(CAPS) / 8, rng.uniform(0, 10))}
        out = []
        for mod in (old, new):
            rec = Recorder(); run = make_run(mod, st, rec)
            run.dyn_check(sid, 10.0)
            reps = [{k: v for k, v in r.items() if k not in ("t_s", "new_flows", "cancelled_flows")} for r in run.replans]
            out.append((reps, sorted(rec.calls), sorted(run._started), sorted(run.rate_est.items())))
        fired += bool(out[1][0])
        if out[0] != out[1]:
            diffs += 1
            if diffs <= 3:
                print(f"  dyn diff: old {out[0][0]} new {out[1][0]}")
    return diffs, fired


def compare_prepos(old, new, n, rng):
    diffs = 0
    for i in range(n):
        sid, st = random_state(rng, "reuse_aware_in")
        st["pp"] = {"policy": rng.choice(["none", "oracle", "top1", "greedy", "proportional", "coverage"]), "probs": rng.choice([[0.6, 0.3, 0.1], [0.3, 0.6, 0.1], [0.34, 0.33, 0.33]]),
                    "L": rng.choice([2, 5, 10, 20]), "b": rng.choice([0, 0.5, 1, 2]), "dest": rng.choice(EDGES), "tau": 7.5, "draw": 0}
        st["a"].sink_bytes = rng.choice([64 << 20, 1725236640])
        st["nfr_"] = -(-st["a"].sink_bytes // st["flen"])
        out = []
        for mod in (old, new):
            rec = Recorder(); run = make_run(mod, st, rec)
            run.prepos_start()
            out.append((sorted(run._started), run.pp_alloc, run.pp_frag))
        if out[0] != out[1]:
            diffs += 1
    return diffs


def compare_dissem(old, new, n, rng):
    import restore_planner as rp
    diffs = 0
    for i in range(n):
        caps = {(d, x): rng.choice(CAPS) for d in ("out", "in") for x in ["A"] + EDGES}
        for plan in rp.DISSEM_PLANS:
            nfr = rng.choice([16, 40, 412])
            if old.dissem_assign(plan, nfr, 4 << 20, caps) != new.dissem_assign(plan, nfr, 4 << 20, caps, EDGES):
                diffs += 1
    return diffs


def check_model():
    """Fluid-model predictions recorded in TOPOLOGY_PLAN.md before runs must be reproduced unchanged."""
    import restore_model as rm
    caps = {("out", "A"): 1e9, ("in", "A"): 1e9}
    for e in EDGES:
        caps[("out", e)] = 125e6; caps[("in", e)] = 1e9
    got = {p: rm.Model(p, 2, 1, 7.025, caps).run(horizon=600) for p in ("restart", "reuse_fixed", "reuse_aware_in")}
    # Step 1 model table (TOPOLOGY_PLAN E.5, N=2, B_h=125): raw makespans (that table adds no control-plane allowance)
    expect = {"restart": (36.5, 1.32), "reuse_fixed": (50.8, 1.00), "reuse_aware_in": (31.3, 1.11)}
    bad = {p: (round(got[p]["makespan"], 1), round(got[p]["source_per_session"], 2)) for p in expect
           if abs(got[p]["makespan"] - expect[p][0]) > 0.15 or abs(got[p]["source_per_session"] - expect[p][1]) > 0.011}
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="e345ccd")
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    src = subprocess.check_output(["git", "show", f"{a.ref}:tools/eval/restore_orchestrate.py"], cwd=ROOT, text=True)
    tmp = Path(tempfile.mkdtemp()) / "restore_orchestrate_ref.py"
    tmp.write_text(src)
    old = load_module("restore_orchestrate_ref", tmp)
    new = load_module("restore_orchestrate_new", ROOT / "tools/eval/restore_orchestrate.py")
    rng = random.Random(a.seed)
    print(f"reference {a.ref} vs working tree; {a.n} random states per check")
    d_plan = compare_plan(old, new, a.n, rng); print(f"plan(): {d_plan} differing of {a.n} (all {len(POLICIES)} policies, reasons move/start/flow_done)")
    d_dyn, fired = compare_dyn(old, new, a.n, rng); print(f"dyn_check(): {d_dyn} differing of {a.n} ({fired} states triggered a re-plan)")
    d_pp = compare_prepos(old, new, a.n // 4, rng); print(f"prepos_start(): {d_pp} differing of {a.n // 4}")
    d_dis = compare_dissem(old, new, a.n // 20, rng); print(f"dissem_assign(): {d_dis} differing of {a.n // 20 * 5}")
    bad = check_model(); print(f"fluid model: {'unchanged' if not bad else 'CHANGED ' + str(bad)}")
    ok = not (d_plan or d_dyn or d_pp or d_dis or bad)
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
