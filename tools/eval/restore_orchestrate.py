#!/usr/bin/env python3
"""Experiment 3 Scenario B: many sessions restore their Sinks through one shared source (network level, no GPU).

N sessions share the original source A. Session i lives on the edges B, C, D: it starts at edge [B, C, D][i % 3] and
moves to the next edge in that cycle every T_m (moves are staggered by T_m * i / N so they do not happen in lockstep).
    --moves 1        one move per session, then it stays (the "previous holder -> final destination" case)
    --moves 0        moves continue until the end of the run (continuous mobility over the three edges)
Per-node caps: every node's egress and ingress are capped (default 1 Gbps each, A egress included), and all flows of all
sessions share them max-min fairly; caps are pushed to each sender's per-flow token bucket. Physical NIC is ~9.4 Gbps.

Policies (decided per session at every move; the Sink content and fragment table are identical across policies):
    restart        cancel the session's flows, forget fragments at every edge, source A sends the whole Sink to the new edge
    reuse_fixed    holders keep verified fragments; the newest holder of each missing fragment sends it, A sends the rest
    reuse_adaptive same holders, but each missing fragment goes to the provider (any holder or A) with the earliest
                   estimated finish time, estimated from the provider's queued bytes and its current max-min rate
    reuse_aware    same holders; a held fragment goes to the source only when every holder of it would finish later
                   than the source, estimating each provider's finish as its whole egress backlog over its egress cap
    reuse_aware_in reuse_aware with the H4c correction: the held fragment moves to the source only if its best holder
                   would also finish after the owner's ingress bound (bytes headed to the owner / its ingress cap)

Restoration of a session at an edge = all fragments verified there while it is the session's owner ("bound").
Outputs one run directory per (policy, N, moves, rho, rep) under results/evaluation/restore_contention/ with
config.json, events.csv, flows.csv, sessions.csv (per session: first restoration time, restorations, coverage),
source_egress.csv (1 s bins), node_*/network.csv (kernel NIC counters), summary.json.

    python tools/eval/restore_orchestrate.py --launch --sessions 1,2,4,8 --policies restart,reuse_fixed,reuse_adaptive --moves 1,0 --reps 3
"""

from __future__ import annotations

import argparse
import csv
import json
import queue
import statistics as st
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "tools", REPO_ROOT / "tools" / "eval"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from agents import connect_all, parse_hosts  # noqa: E402
from common import DEFAULT_MSS, EVAL_ROOT, EventLog, git_commit  # noqa: E402
from mobility_orchestrate import NodeConn, parse_nodes  # noqa: E402
from proto_handoff import send_msg  # noqa: E402

EDGES = ["B", "C", "D"]
SINK_BYTES = 1725236640


def prepos_tag(pp):
    return (f"_pp={pp['policy']}_L={pp['L']:g}_b={pp['b']:g}_d={pp['dest']}_k={pp['draw']}" + (f"_os={pp['others_start']:g}" if pp.get("others_start") else "")) if pp else ""


def maxmin(flows, caps):
    """flows: [(id, src, dst)]; caps: {("out"|"in", node): bps}. Max-min fair rates under per-node caps."""
    rate = {f: 0.0 for f, _, _ in flows}
    if not flows:
        return rate
    resid = dict(caps)
    frozen = set()
    while len(frozen) < len(flows):
        act = [(f, s, d) for f, s, d in flows if f not in frozen]
        load = defaultdict(int)
        for _, s, d in act:
            load[("out", s)] += 1; load[("in", d)] += 1
        inc = min(resid[k] / n for k, n in load.items())
        for f, _, _ in act:
            rate[f] += inc
        for k, n in load.items():
            resid[k] -= inc * n
        for f, s, d in act:
            if resid[("out", s)] <= 1e-3 or resid[("in", d)] <= 1e-3:
                frozen.add(f)
    return rate


class Run:
    def __init__(self, o, policy, n_sess, moves, rho, rep, prepos=None):
        self.o, self.a = o, o.a
        self.policy, self.N, self.moves, self.rho, self.rep = policy, n_sess, moves, rho, rep
        self.pp = prepos   # Experiment A: {"policy", "probs", "L", "b", "dest", "draw", "tau"} for session s0, else None
        self.tm = self.a.ts / rho
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        mtag = "cont" if moves == 0 else str(moves)
        btag = f"_bh={self.a.holder_mbps:g}" if self.a.holder_mbps else ""
        btag += prepos_tag(prepos)
        self.run_id = f"policy={policy}_N={n_sess}_moves={mtag}_rho={rho:g}{btag}_rep={rep}_{stamp}"
        self.rel_dir = f"results/evaluation/{self.a.experiment}/{self.run_id}"
        self.dir = REPO_ROOT / self.rel_dir
        self.dir.mkdir(parents=True, exist_ok=False)
        (self.dir / "git_commit.txt").write_text(git_commit() + "\n")
        self.ev = EventLog(self.dir / "events.csv", "orchestrator")
        self.caps = {(d, n): self.a.cap_mbps * 1e6 for d in ("out", "in") for n in ["A"] + EDGES}
        if self.a.holder_mbps:   # Step 2: every edge's egress (what holders forward with) is capped at B_h
            for e in EDGES:
                self.caps[("out", e)] = self.a.holder_mbps * 1e6
        for item in (self.a.caps or "").split(","):
            if item:
                k, v = item.split("=")
                node, d = k.split(":")
                self.caps[(d, node)] = float(v) * 1e6
        self.sids = [f"s{i}" for i in range(n_sess)]
        self.owner = {sid: EDGES[i % 3] for i, sid in enumerate(self.sids)}
        if self.pp:
            self.owner["s0"] = "A"   # the pre-positioned session executes at the source until its move
        self.history = {sid: [self.owner[sid]] for sid in self.sids}   # owners in order
        self.move_t = {sid: None for sid in self.sids}
        self.held = {sid: {e: set() for e in ["A"] + EDGES} for sid in self.sids}
        self.inflight = {sid: defaultdict(set) for sid in self.sids}  # dst -> fids sent, not yet received
        self.skipped = {sid: set() for sid in self.sids}               # fragments a holder was asked for before it had them
        self.flows: dict[str, dict] = {}
        self.nflow = 0
        self.restored: dict[str, list] = defaultdict(list)            # sid -> [(t, edge)] restorations while owner
        self.owner_since = {}
        self.restored_now = {}                                         # sid -> current owner already restored?
        self.sent = []
        self.recv = []
        self.lock = threading.RLock()

    # ---------------- helpers
    def node(self, lb):
        return self.o.nodes[lb]

    def rel(self, t):
        return t - self.t0

    def nfr(self):
        return len(self.lens)

    def realloc(self):
        act = [(f["id"], f["src"], f["dst"]) for f in self.flows.values() if f["active"] or f.get("draining")]
        rates = maxmin(act, self.caps)
        for fid, _, _ in act:
            fl = self.flows[fid]
            if abs(rates[fid] - fl["rate"]) > 0.01 * max(1.0, fl["rate"]):
                fl["rate"] = rates[fid]
                if fl["started"]:
                    self.node(fl["src"]).cast("FLOW_SET_RATE", flow_id=fid, rate_bps=rates[fid])
        return rates

    def start_flow(self, sid, src, dst, fids, reason, keep_order=False):
        if not fids:
            return
        self.nflow += 1
        fid_ = f"f{self.nflow}_{sid}_{src}{dst}"
        fl = {"id": fid_, "sid": sid, "src": src, "dst": dst, "left": set(fids), "active": True, "rate": 0.0, "started": False,
              "t_start": time.time(), "t_end": None, "bytes": 0, "cancelled": False, "reason": reason, "n": len(fids)}
        self.flows[fid_] = fl
        self.realloc()
        nd = self.o.node_spec[dst]
        self.node(src).cast("FLOW_START", flow_id=fid_, session=sid, dst=dst, dst_host=nd["host"], dst_port=nd["data"],
                            frag_ids=list(fids) if keep_order else sorted(fids), rate_bps=fl["rate"])
        fl["order"] = list(fids) if keep_order else sorted(fids)
        fl["started"] = True
        self.ev.log("flow_start", flow=fid_, session=sid, src=src, dst=dst, n=len(fids), rate_bps=fl["rate"], reason=reason)

    def cancel_flows(self, sid, keep_dst=None):
        for fl in list(self.flows.values()):
            if fl["active"] and fl["sid"] == sid and fl["dst"] != keep_dst:
                fl["active"] = False; fl["cancelled"] = True; fl["t_end"] = time.time()
                fl["draining"] = True   # its in-flight fragment still uses bandwidth until the sender reports FLOW_DONE
                self.node(fl["src"]).cast("FLOW_CANCEL", flow_id=fl["id"])
                self.ev.log("flow_cancel", flow=fl["id"], session=sid, left=len(fl["left"]))
        self.realloc()

    def claims(self, sid, dst):
        s = set(self.inflight[sid][dst])
        for fl in self.flows.values():
            if fl["active"] and fl["sid"] == sid and fl["dst"] == dst:
                s |= fl["left"]
        return s

    # ---------------- policy
    def plan(self, sid, reason):
        own = self.owner[sid]
        allf = set(range(self.nfr()))
        if self.policy == "restart":
            self.cancel_flows(sid, keep_dst=own if reason == "flow_done" else None)
            if reason == "move":
                for e in EDGES:
                    self.held[sid][e] = set()
                    self.node(e).cast("DROP", session=sid)
            missing = allf - self.held[sid][own] - self.claims(sid, own)
            self.start_flow(sid, "A", own, missing, "restart: source sends the whole Sink to the new owner")
            return
        self.cancel_flows(sid, keep_dst=own)
        missing = allf - self.held[sid][own] - self.claims(sid, own)
        if not missing:
            return
        holders = [e for e in reversed(self.history[sid][:-1]) if e != own and e != "A"]   # the source is never a "holder"
        holders = list(dict.fromkeys(holders))  # newest first, unique
        holders += [e for e in EDGES if e != own and e not in holders and self.held[sid][e]]   # pre-positioned, never-owner holders
        # fragments already on their way to a holder (sent, or the one a draining flow is finishing) will be held
        # there shortly: let that holder forward them (queued last) instead of asking the source to send them again
        soon = {h: set(self.inflight[sid][h]) for h in holders}
        for fl in self.flows.values():
            if fl.get("draining") and fl["sid"] == sid and fl["dst"] in soon and fl["left"]:
                soon[fl["dst"]].add(next(f for f in fl["order"] if f in fl["left"]))
        assign = defaultdict(list)
        late = defaultdict(list)
        if self.policy == "reuse_fixed":
            for f in sorted(missing):
                src = next((h for h in holders if f in self.held[sid][h]), None)
                if src is None:
                    src = next((h for h in holders if f in soon[h]), None) if f not in self.skipped[sid] else None
                    if src is not None:
                        late[src].append(f); continue
                    src = "A"
                assign[src].append(f)
        elif self.policy in ("reuse_aware", "reuse_aware_in"):
            # bottleneck-aware: each provider's finish estimate is its whole egress backlog (every session's queued bytes)
            # plus what this plan adds, over its egress cap. Fragments only A holds go to A first, so held fragments see
            # A's true queue; a held fragment then goes to A only when every holder of it would finish later than A.
            cand = holders + ["A"]
            load = {c: 0.0 for c in cand}
            for fl in self.flows.values():
                if fl["src"] in load:
                    if fl["active"]:
                        load[fl["src"]] += len(fl["left"]) * self.flen
                    elif fl.get("draining") and fl["left"]:
                        load[fl["src"]] += self.flen   # a cancelled flow only finishes its in-flight fragment
            rest = []
            for f in sorted(missing):
                inbound = next((h for h in holders if f in soon[h] and f not in self.held[sid][h]), None) if f not in self.skipped[sid] else None
                if inbound is not None and not any(f in self.held[sid][h] for h in holders):
                    late[inbound].append(f); continue
                if not any(f in self.held[sid][h] for h in holders):
                    assign["A"].append(f); load["A"] += self.flen
                else:
                    rest.append(f)
            # reuse_aware_in (H4c correction): the owner's ingress bounds every provider, so a held fragment moves to the
            # source only when its best holder would finish after both the source and the ingress bound
            inbound = sum(len(fl["left"]) * self.flen for fl in self.flows.values() if fl["active"] and fl["dst"] == own)
            inbound += sum(len(v) for v in assign.values()) * self.flen
            for f in rest:
                opts = [c for c in cand if c == "A" or f in self.held[sid][c]]
                est = lambda c: (load[c] + self.flen) / self.caps[("out", c)]  # noqa: E731
                if self.policy == "reuse_aware_in":
                    inbound += self.flen
                    hold = min((c for c in opts if c != "A"), key=est)
                    best = "A" if est(hold) > max(est("A"), inbound / self.caps[("in", own)]) else hold
                else:
                    best = min(opts, key=lambda c: (est(c), c == "A"))  # ties: prefer a holder
                assign[best].append(f); load[best] += self.flen
        else:  # reuse_adaptive: earliest estimated finish per fragment, given current queues and max-min rates
            act = [(fl["id"], fl["src"], fl["dst"]) for fl in self.flows.values() if fl["active"] or fl.get("draining")]
            cand = holders + ["A"]
            # estimated rate of a new flow provider -> own if it were added now
            est = {}
            for c in cand:
                probe = act + [("__probe__", c, own)]
                est[c] = max(1.0, maxmin(probe, self.caps)["__probe__"])
            load = {c: 0 for c in cand}
            for f in sorted(missing):
                inbound = next((h for h in holders if f in soon[h] and f not in self.held[sid][h]), None) if f not in self.skipped[sid] else None
                if inbound is not None and not any(f in self.held[sid][h] for h in holders):
                    late[inbound].append(f); continue
                opts = [c for c in cand if c == "A" or f in self.held[sid][c]]
                best = min(opts, key=lambda c: ((load[c] + 1) * self.flen * 8 / est[c], c == "A"))  # ties: prefer a holder
                assign[best].append(f); load[best] += 1
        for src in set(assign) | set(late):
            ids = assign.get(src, []) + late.get(src, [])   # in-flight fragments last: they arrive while the rest is sent
            self.start_flow(sid, src, own, ids, f"{self.policy}: {'reuse fragments held at ' + src if src != 'A' else 'source sends the rest'}",
                            keep_order=True)

    # ---------------- events
    def handle(self, m):
        k = m.get("kind")
        if k == "NODE_LOST":
            raise RuntimeError(f"node {m['label']} lost: {m.get('error')}")
        nc = self.node(m["label"])
        with self.lock:
            if k == "FRAG_SENT":
                fl = self.flows.get(m["flow_id"])
                self.sent.append((nc.to_orch(m["t_end"]), m["label"], m["dst"], m["session"], m["fragment_id"], m["bytes"]))
                self.inflight[m["session"]][m["dst"]].add(m["fragment_id"])
                if fl:
                    fl["left"].discard(m["fragment_id"]); fl["bytes"] += m["bytes"]
            elif k == "FRAG_SKIP":
                fl = self.flows.get(m["flow_id"])
                self.skipped[m["session"]].add(m["fragment_id"])
                if fl:
                    fl["left"].discard(m["fragment_id"]); fl["n_skipped"] = fl.get("n_skipped", 0) + 1
            elif k == "FRAG_RECV":
                sid, f, dst = m["session"], m["fragment_id"], m["label"]
                t = nc.to_orch(m["t_end"])
                self.recv.append((t, m["src"], dst, sid, f, m["bytes"], m["ok"], m["dup"]))
                self.inflight[sid][dst].discard(f)
                if m["ok"]:
                    self.held[sid][dst].add(f)
                    self.skipped[sid].discard(f)   # it has landed: holders may forward it again
                    if dst == self.owner[sid] and len(self.held[sid][dst]) == self.nfr() and not self.restored_now[sid]:
                        self.restored_now[sid] = True
                        self.restored[sid].append((t, dst))
                        self.ev.log("restored", t, session=sid, edge=dst)
            elif k == "FLOW_DONE":
                fl = self.flows.get(m["flow_id"])
                if fl and fl.get("draining"):
                    fl["draining"] = False; fl["t_drained"] = nc.to_orch(m["t"])
                    self.realloc()
                if fl and fl["active"]:
                    fl["active"] = False; fl["t_end"] = nc.to_orch(m["t"])
                    self.realloc()
                    if (fl["left"] or fl.get("n_skipped")) and not m.get("cancelled"):
                        self.plan(fl["sid"], "flow_done")   # fragments the provider did not hold: re-plan them
            elif k == "SINK_COMPLETE":
                self.ev.log("sink_complete", nc.to_orch(m["t"]), session=m["session"], node=m["label"], digest_ok=m["digest_ok"])
            elif k == "EVENT":
                self.ev.log(m["event"], nc.to_orch(m["t"]), **{x: y for x, y in m.items() if x not in ("kind", "event", "t", "label")})

    def move(self, sid, to=None):
        old = self.owner[sid]
        new = to or EDGES[(EDGES.index(old) + 1) % 3] if old in EDGES else to
        self.owner[sid] = new
        self.move_t[sid] = time.time()
        self.history[sid].append(new)
        self.owner_since[sid] = time.time()
        self.restored_now[sid] = False
        self.ev.log("move", session=sid, frm=old, to=new)
        self.plan(sid, "move")   # restart forgets every edge's fragments here, so only reuse can restore immediately
        if len(self.held[sid][new]) == self.nfr():
            self.restored_now[sid] = True
            self.restored[sid].append((time.time(), new)); self.ev.log("restored", session=sid, edge=new, immediate=True)

    # ---------------- Experiment A: pre-positioning before s0's move
    def prepos_start(self):
        pp, a, S = self.pp, self.a, self.a.sink_bytes
        order = sorted(EDGES, key=lambda c: -pp["probs"][EDGES.index(c)])          # candidates by probability, descending
        prob = {c: pp["probs"][EDGES.index(c)] for c in EDGES}
        deliv = {c: pp["L"] * self.caps[("in", c)] / 8 / S for c in EDGES}         # Sinks each candidate's ingress admits in L
        avail = min(pp["b"], pp["L"] * self.caps[("out", "A")] / 8 / S)           # budget, or what the source can send in L
        x = {c: 0.0 for c in EDGES}
        pol = pp["policy"]
        if pol == "oracle":
            x[pp["dest"]] = min(avail, deliv[pp["dest"]])
        elif pol == "top1":
            x[order[0]] = min(avail, deliv[order[0]])
        elif pol == "greedy":
            rem = avail
            for c in order:
                x[c] = min(rem, deliv[c]); rem -= x[c]
        elif pol == "proportional":   # probability-proportional share of the affordable amount (TOPOLOGY_PLAN D.1)
            for c in order:
                x[c] = min(avail * prob[c], deliv[c])
        elif pol == "coverage":       # give each candidate enough for T_r <= tau, in probability order, then greedy
            rem = avail
            for c in order:
                need = max(0.0, 1.0 - (pp["tau"] - 0.3) * self.caps[("in", c)] / 8 / S)
                x[c] = min(need, deliv[c], rem); rem -= x[c]
            for c in order:
                add = min(rem, deliv[c] - x[c]); x[c] += add; rem -= add
        elif pol != "none":
            raise ValueError(pol)
        # disjoint fragment sets, so fragments at a non-chosen candidate can still be forwarded to the true destination
        pool = list(range(self.nfr())); pos = 0
        self.pp_frag = {}
        for c in order:
            n = int(round(x[c] * self.nfr()))
            self.pp_frag[c] = pool[pos:pos + n]; pos += n
            self.start_flow("s0", "A", c, self.pp_frag[c], f"prepos {pol}: speculative fragments to candidate {c}")
        self.pp_alloc = x
        self.ev.log("prepos", policy=pol, dest=pp["dest"], L=pp["L"], budget=pp["b"], avail_sinks=avail,
                    alloc_sinks={c: round(v, 4) for c, v in x.items()}, frags={c: len(v) for c, v in self.pp_frag.items()})

    # ---------------- run
    def execute(self):
        a = self.a
        print(f"[orch] === {self.run_id} (T_m {self.tm:.2f} s) ===", flush=True)
        for lb in ["A"] + EDGES:
            self.node(lb).call("RUN_BEGIN", run_rel=self.rel_dir)
        r = self.node("A").call("SOURCE_SETUP", sessions=self.sids, sink_bytes=a.sink_bytes, frag_bytes=a.frag_bytes, timeout=1800)
        man = r["manifests"]
        self.lens = man[self.sids[0]]["lens"]; self.flen = a.frag_bytes
        for e in EDGES:
            self.node(e).call("MANIFESTS", manifests=man, timeout=600)
        for sid in self.sids:
            self.held[sid]["A"] = set(range(self.nfr()))
        while not self.o.events.empty():
            self.o.events.get()
        self.t0 = time.time(); self.ev.set_ref(self.t0)
        self.ev.log("start", self.t0, policy=self.policy, N=self.N, moves=self.moves, rho=self.rho, tm=self.tm)
        ostart = self.a.others_start if self.pp else 0.0   # A3: other sessions begin restoring at t0 + others_start
        with self.lock:
            for sid in self.sids:
                self.owner_since[sid] = self.t0
                self.restored_now[sid] = False
                if not (ostart and sid != "s0"):
                    self.plan(sid, "start")
        if self.pp:
            with self.lock:
                self.prepos_start()
            if ostart:
                self.ev.log("others_start_scheduled", t=self.t0 + ostart, sessions=[x for x in self.sids if x != "s0"])
        # move schedule (staggered); entries (t, sid, explicit destination or None = next edge in the cycle)
        sched = []
        horizon = a.horizon_factor * self.N * a.ts + 2 * self.tm if self.moves == 0 else None
        for i, sid in enumerate(self.sids):
            if self.pp and sid == "s0":
                sched.append((self.t0 + self.pp["L"], sid, self.pp["dest"])); continue
            if ostart:
                sched.append((self.t0 + ostart, sid, "__start__"))
            k = 1
            while True:
                t = self.t0 + ostart + self.tm * (k + i / self.N)
                if self.moves and k > self.moves:
                    break
                if horizon is not None and t > self.t0 + horizon:
                    break
                sched.append((t, sid, None)); k += 1
                if k > 10000:
                    break
        sched.sort()
        # single-move deadline: generous enough for a slow holder to forward its share (2 Sinks at the slowest edge egress)
        slow = 2 * a.sink_bytes * 8 / min(self.caps[("out", e)] for e in EDGES)
        deadline = self.t0 + (horizon if horizon is not None else max(a.deadline_factor * self.N * a.ts, slow) + 3 * self.tm)
        last_bin = 0
        while True:
            now = time.time()
            while sched and sched[0][0] <= now:
                _, sid, to = sched.pop(0)
                with self.lock:
                    if to == "__start__":
                        self.owner_since[sid] = time.time(); self.ev.log("session_start", session=sid, edge=self.owner[sid]); self.plan(sid, "start")
                    else:
                        self.move(sid, to)
            try:
                m = self.o.events.get(timeout=0.02)
                self.handle(m)
            except queue.Empty:
                pass
            done = self.moves and all(self.restored[s] and self.restored[s][-1][1] == self.owner[s] for s in self.sids) and not sched
            if done or now >= deadline:
                self.stop_reason = "all restored" if done else "horizon" if self.moves == 0 else "deadline"
                break
        for fl in list(self.flows.values()):
            if fl["active"]:
                fl["active"] = False; self.node(fl["src"]).cast("FLOW_CANCEL", flow_id=fl["id"])
        time.sleep(1.0)
        while not self.o.events.empty():
            self.handle(self.o.events.get())
        ends = {lb: self.node(lb).call("RUN_END", timeout=300) for lb in ["A"] + EDGES}
        for lb, e in ends.items():
            if e.get("network_csv"):
                (self.dir / f"node_{lb}").mkdir(exist_ok=True)
                (self.dir / f"node_{lb}" / "network.csv").write_text(e["network_csv"])
        return self.finish(ends, deadline)

    def finish(self, ends, deadline):
        a = self.a
        S = a.sink_bytes
        t_end = min(time.time(), deadline)
        per = []
        for sid in self.sids:
            rs = self.restored[sid]
            first = self.rel(rs[0][0]) if rs else None
            # coverage: share of [t0, t_end] during which the current owner holds the whole Sink
            mt = self.move_t[sid]
            t_r = next((self.rel(t) - self.rel(mt) for t, e in rs if mt is not None and t >= mt and e == self.owner[sid]), None)
            per.append({"session": sid, "first_restored_s": first, "restorations": len(rs), "move_s": None if mt is None else self.rel(mt), "t_r_s": t_r})
        # coverage from the event log (moves and restorations)
        evs = list(csv.DictReader(open(self.dir / "events.csv")))
        for row in per:
            sid = row["session"]
            moves = sorted(float(e["t_rel"]) for e in evs if e["event"] == "move" and json.loads(e["detail"]).get("session") == sid)
            rest = sorted(float(e["t_rel"]) for e in evs if e["event"] == "restored" and json.loads(e["detail"]).get("session") == sid)
            bounds = [0.0] + moves + [t_end - self.t0]
            covered = 0.0
            for lo, hi in zip(bounds, bounds[1:]):
                r = next((t for t in rest if lo - 1e-6 <= t <= hi), None)
                if r is not None:
                    covered += hi - r
            row["coverage"] = covered / max(1e-9, t_end - self.t0)
        with open(self.dir / "sessions.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["session", "first_restored_s", "restorations", "move_s", "t_r_s", "coverage"]); w.writeheader(); w.writerows(per)
        tot = sum(b for *_, b in self.sent)
        src = sum(b for t, s, d, sid, f, b in self.sent if s == "A")
        link = defaultdict(int)
        for t, s, d, sid, f, b in self.sent:
            link[f"{s}->{d}"] += b
        bins = defaultdict(int)
        for t, s, d, sid, f, b in self.sent:
            if s == "A":
                bins[int(t - self.t0)] += b
        with open(self.dir / "source_egress.csv", "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["t_s", "mbps"])
            for k in range(0, int(t_end - self.t0) + 1):
                w.writerow([k, f"{bins.get(k, 0) * 8 / 1e6:.1f}"])
        # bytes delivered to an edge for a session but never used: never part of a restoration there and never forwarded
        used = set()
        for sid in self.sids:
            for t, e in self.restored[sid]:
                used.add((sid, e))
        fwd = {(sid, s, f) for t, s, d, sid, f, b in self.sent if s != "A"}
        unused = sum(b for t, s, d, sid, f, b, ok, dup in self.recv if ok and not dup and (sid, d) not in used and (sid, d, f) not in fwd)
        dup = sum(b for t, s, d, sid, f, b, ok, dup_ in self.recv if dup_)
        firsts = [r["first_restored_s"] for r in per]
        fin = [x for x in firsts if x is not None]
        nic_rx = {}
        for lb, e in ends.items():
            rows = [l.split(",") for l in (e.get("network_csv") or "").splitlines()[1:] if l.strip()]
            vals = [float(r[4]) for r in rows if r[4] and float(r[0]) >= self.t0]
            vtx = [float(r[5]) for r in rows if r[5] and float(r[0]) >= self.t0]
            nic_rx[lb] = {"rx_peak": max(vals) if vals else None, "tx_peak": max(vtx) if vtx else None}
        prepos = None
        if self.pp:
            mt = self.move_t["s0"]
            sent0 = [(t, s_, d, f, b) for t, s_, d, sid, f, b in self.sent if sid == "s0"]
            recv0 = [(t, s_, d, f, b) for t, s_, d, sid, f, b, ok, dup_ in self.recv if sid == "s0" and ok and not dup_]
            at_move = {c: sum(b for t, s_, d, f, b in recv0 if d == c and t <= mt) / S for c in EDGES}
            others = [r for r in per if r["session"] != "s0"]
            prepos = {**{k: v for k, v in self.pp.items()}, "top1": max(EDGES, key=lambda c: self.pp["probs"][EDGES.index(c)]),
                      "others_first_restored_s": [r["first_restored_s"] for r in others],
                      "others_makespan_s": max((r["first_restored_s"] for r in others), default=None) if others and all(r["first_restored_s"] is not None for r in others) else None,
                      "correct": self.pp["dest"] == max(EDGES, key=lambda c: self.pp["probs"][EDGES.index(c)]),
                      "alloc_sinks": self.pp_alloc, "frags": {c: len(v) for c, v in self.pp_frag.items()},
                      "sent_before_move_sinks": {c: sum(b for t, s_, d, f, b in sent0 if s_ == "A" and d == c and t <= mt) / S for c in EDGES},
                      "verified_at_move_sinks": at_move, "at_chosen_sinks": at_move[self.pp["dest"]],
                      "at_nonchosen_sinks": sum(v for c, v in at_move.items() if c != self.pp["dest"]),
                      "post_move_source_sinks": sum(b for t, s_, d, f, b in sent0 if s_ == "A" and t > mt) / S,
                      "forwarded_by_nonowner_holders_sinks": sum(b for t, s_, d, f, b in sent0 if s_ != "A" and s_ not in self.history["s0"][:-1]) / S,
                      "forwarded_by_past_owners_sinks": sum(b for t, s_, d, f, b in sent0 if s_ != "A" and s_ in self.history["s0"][:-1]) / S,
                      "move_s": self.rel(mt), "t_r_s": per[0]["t_r_s"]}
        summary = {
            "run_id": self.run_id, "policy": self.policy, "prepos": prepos, "N": self.N, "moves": self.moves, "rho": self.rho, "tm_s": self.tm, "rep": self.rep,
            "sink_bytes": S, "frag_bytes": a.frag_bytes, "caps_mbps": {f"{n}:{d}": v / 1e6 for (d, n), v in self.caps.items()},
            "stop_reason": self.stop_reason, "duration_s": t_end - self.t0,
            "restored_sessions": len(fin), "first_restored": {"median": st.median(fin) if fin else None, "max": max(fin) if fin else None,
                                                             "all": firsts},
            "makespan_s": max(fin) if len(fin) == self.N else None,
            "coverage_mean": st.mean(r["coverage"] for r in per),
            "bytes": {"total_sent": tot, "source_sent": src, "by_link": dict(link), "unused": unused, "duplicate": dup},
            "normalized": {"total_per_session": tot / S / self.N, "source_per_session": src / S / self.N, "unused_per_session": unused / S / self.N},
            "node_stats": {lb: e.get("stats") for lb, e in ends.items()},
            "paced_egress_worst_1s_mbps": {lb: e.get("egress_worst_1s_mbps") for lb, e in ends.items()},
            "paced_egress_worst_10s_mbps": {lb: e.get("egress_worst_10s_mbps") for lb, e in ends.items()},
            "nic": nic_rx, "hosts": {lb: self.node(lb).hello.get("host") for lb in ["A"] + EDGES},
            "validation": {"all_fragments_verified": all(ok for *_, ok, dup in self.recv),
                           "four_hosts_distinct": len({self.node(lb).hello.get("host") for lb in ["A"] + EDGES}) == 4,
                           "nic_within_cap": all(v["rx_peak"] is None or v["rx_peak"] <= 1.15 * self.caps[("in", lb)] / 1e6 for lb, v in nic_rx.items()),
                           "source_nic_within_cap": nic_rx["A"]["tx_peak"] is None or nic_rx["A"]["tx_peak"] <= 1.15 * self.caps[("out", "A")] / 1e6,
                           # paced payload per node within 1.05 x its egress cap in every 10 s window (exact count at the token bucket)
                           "paced_egress_within_cap": all((e.get("egress_worst_10s_mbps") or 0) <= 1.05 * self.caps[("out", lb)] / 1e6 for lb, e in ends.items())},
        }
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
        (self.dir / "config.json").write_text(json.dumps({"args": vars(a), "policy": self.policy, "N": self.N, "moves": self.moves, "rho": self.rho, "tm_s": self.tm,
                                                          "nodes": self.o.node_spec, "transport": "tcp+tcp_maxseg+per-flow token bucket, max-min fair per-node caps"}, indent=1, default=str))
        with open(self.dir / "flows.csv", "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["flow", "session", "src", "dst", "n", "bytes", "t_start_rel", "t_end_rel", "cancelled", "drain_s", "reason"])
            for fl in self.flows.values():
                w.writerow([fl["id"], fl["sid"], fl["src"], fl["dst"], fl["n"], fl["bytes"], f"{self.rel(fl['t_start']):.3f}",
                            "" if fl["t_end"] is None else f"{self.rel(fl['t_end']):.3f}", fl["cancelled"],
                            f"{fl['t_drained'] - fl['t_end']:.3f}" if fl.get("t_drained") and fl["t_end"] else "", fl["reason"]])
        ms = summary["makespan_s"]
        if prepos:
            print(f"[orch] prepos {prepos['policy']} dest={prepos['dest']} ({'correct' if prepos['correct'] else 'incorrect'}): T_r {prepos['t_r_s'] and round(prepos['t_r_s'], 2)} s, "
                  f"verified at move {{{', '.join(f'{c}:{v:.2f}' for c, v in prepos['verified_at_move_sinks'].items())}}} S, post-move source {prepos['post_move_source_sinks']:.2f} S, "
                  f"forwarded by non-owner holders {prepos['forwarded_by_nonowner_holders_sinks']:.2f} S", flush=True)
        print(f"[orch] {self.policy} N={self.N} moves={self.moves or 'cont'} rho={self.rho:g}: restored {len(fin)}/{self.N}, median first {summary['first_restored']['median'] and round(summary['first_restored']['median'], 1)} s, "
              f"makespan {ms and round(ms, 1)} s, coverage {summary['coverage_mean']:.2f}, source {src / S:.2f} S, total {tot / S:.2f} S, unused {unused / S:.2f} S | "
              f"A tx peak {nic_rx['A']['tx_peak']} Mbps, valid {all(v for v in summary['validation'].values())}", flush=True)
        return summary


class Orch:
    def __init__(self, a):
        self.a = a
        spec = parse_nodes(a.nodes, False)
        self.node_spec = {lb: {"host": v["host"], "ctl": a.ctl_port if not a.nodes else v["ctl"], "data": a.data_port if not a.nodes else v["data"]} for lb, v in spec.items()}
        self.events: queue.Queue = queue.Queue()
        self.nodes = {}

    def launch(self):
        agents = connect_all(parse_hosts(self.a.agent_hosts), ["A"] + EDGES)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for lb in ["A"] + EDGES:   # stop restore nodes left over from an interrupted run (they hold the ports)
            r = agents[lb].exec(["pkill", "-f", "tools/eval/restore_node.py"])
            if r.get("rc") == 0:
                print(f"[orch] stopped a leftover restore node on {lb}", flush=True)
        time.sleep(1.0)
        for lb in ["A"] + EDGES:
            nd = self.node_spec[lb]
            cmd = [self.a.py, "tools/eval/restore_node.py", "--label", lb, "--ctl_port", str(nd["ctl"]), "--data_port", str(nd["data"]), "--mss", str(self.a.mss or 0)]
            if self.a.iface:
                cmd += ["--iface", self.a.iface]
            pid = agents[lb].run(cmd, f"results/evaluation/{self.a.experiment}/_launch_logs/node_{lb}_{stamp}.log")
            print(f"[orch] launched restore node {lb} on {nd['host']} (pid {pid})", flush=True)

    def connect(self):
        for lb in ["A"] + EDGES:
            nd = self.node_spec[lb]
            self.nodes[lb] = NodeConn(lb, nd["host"], nd["ctl"], self.a.mss, self.events, timeout=120)
            print(f"[orch] node {lb} = {self.nodes[lb].hello.get('host')} mss {self.nodes[lb].hello.get('mss_effective')} offset {self.nodes[lb].off * 1e3:+.2f} ms", flush=True)

    def shutdown(self):
        for nc in self.nodes.values():
            try:
                send_msg(nc.sock, "SHUTDOWN", {}, b"", None)
            except OSError:
                pass


def prepos_configs(a, rep):
    """Experiment A configurations for one rep: one per (pre-positioning policy, destination draw); [None] when off."""
    if not a.prepos:
        return [None]
    import random
    probs = [float(x) for x in a.probs.split(",")]
    out = []
    for pol in a.prepos.split(","):
        for k in range(a.draws):
            if a.dests:
                ds = a.dests.split(","); dest = ds[k % len(ds)]
            else:
                dest = random.Random(1000 * rep + k).choices(EDGES, weights=probs)[0]
            out.append({"policy": pol, "probs": probs, "L": a.lookahead, "b": a.budget, "dest": dest, "draw": k, "tau": a.tau, "others_start": a.others_start})
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nodes", default=None, help="A=host[:ctl[:data]],B=...,C=...,D=... (default elves-01..04)")
    p.add_argument("--ctl_port", type=int, default=29831)
    p.add_argument("--data_port", type=int, default=29832)
    p.add_argument("--experiment", default="restore_contention_v2")  # v1 (restore_contention) lost early rate updates; kept for reference
    p.add_argument("--policies", default="restart,reuse_fixed,reuse_adaptive", help="any of restart,reuse_fixed,reuse_adaptive,reuse_aware,reuse_aware_in")
    p.add_argument("--sessions", default="1,2,4,8")
    p.add_argument("--moves", default="1,0", help="1 = one move then stay; 0 = continuous mobility until the horizon")
    p.add_argument("--rhos", default="2")
    p.add_argument("--ts", type=float, default=14.05, help="measured single-session Sink transfer time at 1 Gbps (Phase 1)")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--sink_bytes", type=int, default=SINK_BYTES)
    p.add_argument("--frag_bytes", type=int, default=4 << 20)
    p.add_argument("--cap_mbps", type=float, default=1000.0, help="default per-node egress and ingress cap")
    p.add_argument("--caps", default="", help="overrides, e.g. 'B:out=250,D:in=4000'")
    p.add_argument("--holder_mbps", type=float, default=0.0, help="Step 2: cap every edge's egress at this (0 = cap_mbps); tagged bh= in run ids")
    p.add_argument("--prepos", default="", help="Experiment A: pre-positioning policies for session s0 (none,oracle,top1,greedy,proportional,coverage); '' = off")
    p.add_argument("--probs", default="0.6,0.3,0.1", help="predicted destination probabilities for B,C,D")
    p.add_argument("--lookahead", type=float, default=10.0, help="seconds between the start of pre-positioning and s0's move")
    p.add_argument("--budget", type=float, default=1.0, help="pre-positioning budget in Sinks")
    p.add_argument("--dests", default="", help="deterministic true destinations, e.g. B,C,D (draw i uses the i-th, cyclic); '' = seeded draw from --probs")
    p.add_argument("--draws", type=int, default=1, help="destination draws per (prepos policy, rep)")
    p.add_argument("--tau", type=float, default=7.5, help="tail-coverage target T_r in seconds")
    p.add_argument("--others_start", type=float, default=0.0, help="A3: seconds after t0 at which sessions other than s0 start restoring (0 = at t0)")
    p.add_argument("--horizon_factor", type=float, default=2.0, help="continuous mode: run for factor * N * T_s + 2 T_m")
    p.add_argument("--deadline_factor", type=float, default=2.0, help="single-move mode: give up after factor * N * T_s + 3 T_m")
    p.add_argument("--mss", type=int, default=DEFAULT_MSS)
    p.add_argument("--iface", default=None)
    p.add_argument("--launch", action="store_true")
    p.add_argument("--no_resume", action="store_true", help="re-run configurations that already have a completed run directory")
    p.add_argument("--agent_hosts", default=None)
    p.add_argument("--py", default="auto")
    a = p.parse_args()
    a.mss = a.mss or None
    o = Orch(a)
    if a.launch:
        o.launch()
    o.connect()
    out = []
    try:
        root = EVAL_ROOT / a.experiment
        for rep in range(1, a.reps + 1):
            for moves in [int(x) for x in a.moves.split(",")]:
                for rho in [float(x) for x in a.rhos.split(",")]:
                    for n in [int(x) for x in a.sessions.split(",")]:
                        for pol in a.policies.split(","):
                            for pp in prepos_configs(a, rep):
                                mtag = "cont" if moves == 0 else str(moves)
                                btag = (f"_bh={a.holder_mbps:g}" if a.holder_mbps else "") + prepos_tag(pp)
                                done = [d for d in root.glob(f"policy={pol}_N={n}_moves={mtag}_rho={rho:g}{btag}_rep={rep}_*") if (d / "summary.json").exists()]
                                if done and not a.no_resume:
                                    print(f"[orch] skip (done): {done[0].name}", flush=True); continue
                                out.append(Run(o, pol, n, moves, rho, rep, prepos=pp).execute())
    finally:
        o.shutdown()
    (EVAL_ROOT / a.experiment).mkdir(parents=True, exist_ok=True)
    print(f"[orch] done: {len(out)} runs")


if __name__ == "__main__":
    main()
