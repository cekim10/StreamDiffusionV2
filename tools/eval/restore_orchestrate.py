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
from collections import defaultdict, deque
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


def parse_cap_events(spec):
    """'t=20:C:out=62.5' (at 20 s) or 'D>=0.5:C:out=62.5' (when D holds 50 % of s0's Sink): set C's egress cap to 62.5 Mbps."""
    out = []
    for item in (spec or "").split(";"):
        item = item.strip()
        if not item:
            continue
        trig, node, capv = item.split(":")
        d, v = capv.split("=")
        e = {"spec": item, "cap_node": node, "dir": d, "mbps": float(v), "fired": False}
        if trig.startswith("t="):
            e["kind"] = "t"; e["at"] = float(trig[2:])
        else:
            n, frac = trig.split(">=")
            e["kind"] = "progress"; e["node"] = n; e["frac"] = float(frac)
        out.append(e)
    return out


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
        if self.a.cap_events:
            btag += "_ev=" + self.a.cap_events.replace(":", "").replace(";", "+").replace("=", "").replace(">", "ge")
        self.run_id = self.make_run_id(policy, n_sess, mtag, rho, btag, rep, stamp)
        self.rel_dir = f"results/evaluation/{self.a.experiment}/{self.run_id}"
        self.dir = REPO_ROOT / self.rel_dir
        self.dir.mkdir(parents=True, exist_ok=False)
        (self.dir / "git_commit.txt").write_text(git_commit() + "\n")
        self.ev = EventLog(self.dir / "events.csv", "orchestrator")
        self.caps = {(d, n): self.a.cap_mbps * 1e6 for d in ("out", "in") for n in ["A"] + EDGES}
        if self.a.holder_mbps:   # Step 2: every edge's egress (what holders forward with) is capped at B_h
            for e in EDGES:
                self.caps[("out", e)] = self.a.holder_mbps * 1e6
        if getattr(self.a, "source_mbps", 0):
            self.caps[("out", "A")] = self.a.source_mbps * 1e6
        if getattr(self.a, "in_mbps", 0):
            for e in EDGES:
                self.caps[("in", e)] = self.a.in_mbps * 1e6
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
        # E.4: runtime measurement and event-driven re-planning (policy reuse_dyn)
        self.flow_rx = defaultdict(lambda: deque())   # flow id -> (t, bytes) of fragments verified at the destination
        self.known_caps = dict(self.caps)              # what the planner believes (snapshot at plan time, never the live caps)
        self.caps0 = dict(self.caps)                   # initial network caps (validation uses the larger of initial and final)
        self.last_plan_t = {sid: 0.0 for sid in self.sids}
        self.replans = []                              # dicts: decision time, dT, costs, moved fragments, provider from/to
        self.cap_changes = []                          # (t, node, dir, mbps)
        self.cap_events = parse_cap_events(self.a.cap_events)
        self.dyn_last_check = 0.0

    # ---------------- helpers
    def make_run_id(self, policy, n_sess, mtag, rho, btag, rep, stamp):
        return f"policy={policy}_N={n_sess}_moves={mtag}_rho={rho:g}{btag}_rep={rep}_{stamp}"

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

    def start_flow(self, sid, src, dst, fids, reason, keep_order=False, closed=True):
        if not fids and closed:
            return
        self.nflow += 1
        fid_ = f"f{self.nflow}_{sid}_{src}{dst}"
        fl = {"id": fid_, "sid": sid, "src": src, "dst": dst, "left": set(fids), "active": True, "rate": 0.0, "started": False,
              "t_start": time.time(), "t_end": None, "bytes": 0, "cancelled": False, "reason": reason, "n": len(fids)}
        self.flows[fid_] = fl
        self.realloc()
        nd = self.o.node_spec[dst]
        self.node(src).cast("FLOW_START", flow_id=fid_, session=sid, dst=dst, dst_host=nd["host"], dst_port=nd["data"],
                            frag_ids=list(fids) if keep_order else sorted(fids), rate_bps=fl["rate"], closed=closed)
        fl["closed"] = closed
        fl["order"] = list(fids) if keep_order else sorted(fids)
        fl["started"] = True
        self.ev.log("flow_start", flow=fid_, session=sid, src=src, dst=dst, n=len(fids), rate_bps=fl["rate"], reason=reason, closed=closed)
        return fl

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
        self.last_plan_t[sid] = time.time()
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
        elif self.policy in ("reuse_aware", "reuse_aware_in", "reuse_dyn"):
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
                est = lambda c: (load[c] + self.flen) / self.known_caps[("out", c)]  # noqa: E731
                if self.policy in ("reuse_aware_in", "reuse_dyn"):
                    inbound += self.flen
                    hold = min((c for c in opts if c != "A"), key=est)
                    best = "A" if est(hold) > max(est("A"), inbound / self.known_caps[("in", own)]) else hold
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
                self.flow_rx[m.get("flow_id")].append((t, m["bytes"]))
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
                if m["event"] == "flow_add_rejected" and m.get("frag_ids"):   # the flow had finished: carry the fragments in a new flow
                    fl = self.flows.get(m["flow"])
                    if fl:
                        fl["left"] -= set(m["frag_ids"])
                    self.start_flow(m["session"], m["label"], m["dst"], list(m["frag_ids"]), "replan: fragments re-issued after a finished flow rejected FLOW_ADD", keep_order=True)

    # ---------------- E.4: cap events, measurement, event-driven re-planning
    def tick(self, now):
        for evn in self.cap_events:
            if evn.get("fired"):
                continue
            fire = False
            if evn["kind"] == "t":
                fire = now - self.t0 >= evn["at"]
            else:   # progress trigger: node holds >= frac of the Sink for session s0
                fire = len(self.held["s0"][evn["node"]]) >= evn["frac"] * self.nfr()
            if fire:
                evn["fired"] = True
                self.caps[(evn["dir"], evn["cap_node"])] = evn["mbps"] * 1e6   # the network changes; planners are not told
                self.cap_changes.append((now, evn["cap_node"], evn["dir"], evn["mbps"]))
                self.realloc()
                self.ev.log("cap_change", now, node=evn["cap_node"], dir=evn["dir"], mbps=evn["mbps"], trigger=evn["spec"])
        if self.policy == "reuse_dyn" and now - self.dyn_last_check >= self.a.dyn_period:
            self.dyn_last_check = now
            for sid in self.sids:
                self.dyn_check(sid, now)

    def measured_rate(self, flow_id, now):
        """Bytes verified at the destination over the last dyn_window seconds, in bytes/s (None if nothing yet)."""
        q = self.flow_rx.get(flow_id)
        if not q:
            return None
        while q and q[0][0] < now - self.a.dyn_window:
            q.popleft()
        return sum(b for _, b in q) / self.a.dyn_window if q else 0.0

    def dyn_check(self, sid, now):
        own = self.owner[sid]
        if now - self.last_plan_t[sid] < self.a.dyn_warmup:
            return
        act = [fl for fl in self.flows.values() if fl["active"] and fl["sid"] == sid and fl["dst"] == own and fl["left"]]
        if len(act) == 0:
            return
        # current ETA per provider from measured throughput; a provider with no verified bytes in the window counts as stalled
        eta, rate = {}, {}
        for fl in act:
            r = self.measured_rate(fl["id"], now)
            if r is None:
                return   # not enough measurement yet
            rate[fl["src"]] = rate.get(fl["src"], 0.0) + r
        rem = defaultdict(int)
        for fl in act:
            rem[fl["src"]] += len(fl["left"]) * self.flen
        for p_, b in rem.items():
            eta[p_] = b / rate[p_] if rate[p_] > 0 else float("inf")
        q = max(eta, key=eta.get)
        eta_cur = eta[q]
        if eta_cur == float("inf"):
            eta_cur = 1e6
        # capacity estimates: measured throughput for providers now sending to this owner, the known nominal cap otherwise
        cap_est = {}
        for n in ["A"] + EDGES:
            cap_est[n] = rate[n] if n in rate and rate[n] > 0 else self.known_caps[("out", n)]
        qflows = [fl for fl in act if fl["src"] == q]
        head = {next((f for f in fl["order"] if f in fl["left"]), None) for fl in qflows} - {None}   # in flight: let it drain
        movable = set().union(*(fl["left"] for fl in qflows)) - head
        if not movable:
            return
        # re-assign the bottleneck's remaining fragments with the aware rule over estimated capacities; other flows keep their work
        load = {n: 0.0 for n in ["A"] + EDGES}
        for fl in act:
            if fl["src"] != q:
                load[fl["src"]] += len(fl["left"]) * self.flen
        load[q] += len(head) * self.flen
        inbound = sum(len(fl["left"]) for fl in act) * self.flen
        assign = defaultdict(list)
        for f in sorted(movable):
            opts = [c for c in ["A"] + EDGES if c != own and (c == "A" or f in self.held[sid][c])]
            best = min(opts, key=lambda c: ((load[c] + self.flen) / cap_est[c], c == "A"))
            assign[best].append(f); load[best] += self.flen
        eta_new = max((load[n] / cap_est[n] for n in load if load[n] > 0), default=0.0)
        eta_new = max(eta_new, inbound / self.known_caps[("in", own)])
        drain = self.flen / max(rate[q], 1.0) if head else 0.0
        c_switch = self.a.dyn_ctrl + drain
        dT = eta_cur - eta_new
        if dT <= c_switch + self.a.dyn_eps or dT < self.a.dyn_rel * eta_cur or set(assign) == {q}:
            return
        # apply: cancel the bottleneck's flows (their in-flight fragment drains), extend or start the others
        t_dec = time.time()
        bytes_before = sum(fl["bytes"] for fl in qflows)
        for fl in qflows:
            fl["active"] = False; fl["cancelled"] = True; fl["t_end"] = t_dec; fl["draining"] = True; fl["replanned"] = True
            fl["left"] = set(head) & fl["left"]
            self.node(q).cast("FLOW_CANCEL", flow_id=fl["id"])
        self.realloc()
        new_flows = []
        for p_, ids in assign.items():
            ex = next((fl for fl in act if fl["src"] == p_ and fl["active"] and p_ != q), None)
            if ex is not None:
                ex["left"] |= set(ids); ex["n"] += len(ids)
                self.node(p_).cast("FLOW_ADD", flow_id=ex["id"], frag_ids=sorted(ids), closed=True)
                new_flows.append(ex["id"])
            else:
                fl = self.start_flow(sid, p_, own, sorted(ids), f"replan: {len(ids)} fragments moved from {q} (eta {eta_cur:.1f} -> {eta_new:.1f} s)", keep_order=True)
                new_flows.append(fl["id"])
        self.last_plan_t[sid] = t_dec
        rec = {"t_s": self.rel(t_dec), "session": sid, "owner": own, "from": q, "to": {p_: len(ids) for p_, ids in assign.items()},
               "moved_fragments": sum(len(v) for v in assign.values()), "eta_cur_s": eta_cur, "eta_new_s": eta_new, "dT_s": dT,
               "c_switch_s": c_switch, "drain_est_s": drain, "measured_rate_mbps": {n: r * 8 / 1e6 for n, r in rate.items()},
               "cap_est_mbps": {n: v * 8 / 1e6 for n, v in cap_est.items()}, "new_flows": new_flows,
               "cancelled_flows": [fl["id"] for fl in qflows], "cancelled_bytes_before": bytes_before,
               "cap_change_t_s": self.rel(self.cap_changes[-1][0]) if self.cap_changes else None}
        self.replans.append(rec)
        self.ev.log("replan", t_dec, **rec)

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
        slowest = min([self.caps[("out", e)] for e in EDGES] + [e["mbps"] * 1e6 for e in self.cap_events])   # cap events included
        slow = 2 * a.sink_bytes * 8 / slowest
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
            with self.lock:
                self.tick(now)
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
        # E.4 switching costs: detection (cap change -> decision), transition (decision -> first byte from a new provider),
        # drained bytes (from cancelled flows after the decision), duplicates
        dyn = {"replans": self.replans, "n_replans": len(self.replans), "cap_changes": [(self.rel(t), n, d, v) for t, n, d, v in self.cap_changes]}
        for rec in dyn["replans"]:
            t_dec = rec["t_s"]
            rec["detection_delay_s"] = None if rec["cap_change_t_s"] is None else t_dec - rec["cap_change_t_s"]
            firsts = [self.rel(t) for t, s_, d, sid, f, b in self.sent if sid == rec["session"] and d == rec["owner"] and s_ in rec["to"] and self.rel(t) > t_dec]
            rec["transition_delay_s"] = (min(firsts) - t_dec) if firsts else None
            rec["drained_bytes"] = sum(self.flows[i]["bytes"] for i in rec["cancelled_flows"]) - rec["cancelled_bytes_before"]   # what the cancelled flows still sent
        dyn["duplicate_bytes"] = sum(b for *_, b, ok, dup_ in self.recv if dup_)
        summary = {
            "run_id": self.run_id, "policy": self.policy, "prepos": prepos, "dyn": dyn, "N": self.N, "moves": self.moves, "rho": self.rho, "tm_s": self.tm, "rep": self.rep,
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
                           "nodes_same_commit": len({self.node(lb).hello.get("commit") for lb in ["A"] + EDGES} | {git_commit().split()[0]}) == 1,
                           "nic_within_cap": all(v["rx_peak"] is None or v["rx_peak"] <= 1.15 * max(self.caps[("in", lb)], self.caps0[("in", lb)]) / 1e6 for lb, v in nic_rx.items()),
                           "source_nic_within_cap": nic_rx["A"]["tx_peak"] is None or nic_rx["A"]["tx_peak"] <= 1.15 * max(self.caps[("out", "A")], self.caps0[("out", "A")]) / 1e6,
                           # paced payload per node within 1.05 x its egress cap in every 10 s window (exact count at the token bucket);
                           # with cap events the whole-run check uses the larger cap, the post-change pacing is checked from events.csv
                           "paced_egress_within_cap": all((e.get("egress_worst_10s_mbps") or 0) <= 1.05 * max(self.caps[("out", lb)], self.caps0[("out", lb)]) / 1e6 for lb, e in ends.items())},
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


DISSEM_PLANS = ["star", "line", "tree", "multipath", "aware"]


def dissem_assign(plan, nfr, flen, caps):
    """Experiment B: provider of every (fragment, destination) pair for one Sink held at A and needed at B, C, D.
    star: A sends everything. line: A->B->C->D, each node forwards to its successor. tree: A->B, B->{C, D}.
    multipath (butterfly-like): A sends disjoint thirds to B, C, D (fragment f to EDGES[f mod 3]); each node forwards its
    third to the other two. aware: greedy over fragments; for each fragment the destinations are served in order of their
    assigned ingress load (ties rotate with f), each from the eligible provider (A, or a node already scheduled to hold
    the fragment) with the smallest (assigned egress bytes + one fragment) / egress cap -- uses only the caps, the
    planner's own assignments and fragment availability."""
    prov = {}
    if plan == "star":
        for f in range(nfr):
            for d in EDGES:
                prov[(f, d)] = "A"
    elif plan == "line":
        chain = ["A"] + EDGES
        for f in range(nfr):
            for i, d in enumerate(EDGES, start=1):
                prov[(f, d)] = chain[i - 1]
    elif plan == "tree":
        for f in range(nfr):
            prov[(f, "B")] = "A"; prov[(f, "C")] = "B"; prov[(f, "D")] = "B"
    elif plan == "multipath":
        for f in range(nfr):
            own = EDGES[f % 3]
            for d in EDGES:
                prov[(f, d)] = "A" if d == own else own
    elif plan == "aware":
        load = {n: 0.0 for n in ["A"] + EDGES}
        inload = {d: 0.0 for d in EDGES}
        for f in range(nfr):
            will = ["A"]
            for d in sorted(EDGES, key=lambda d: (inload[d], (EDGES.index(d) - f) % 3)):
                cands = [p for p in will if p != d]
                p = min(cands, key=lambda p: ((load[p] + flen) / caps[("out", p)], p == "A"))
                prov[(f, d)] = p; load[p] += flen; inload[d] += flen; will.append(d)
    else:
        raise ValueError(plan)
    return prov


class DissemRun(Run):
    """Experiment B: one Sink (session s0 at A) delivered and verified at every edge, under a fixed plan or the aware
    assignment; forwarders pipeline (FLOW_ADD as fragments are verified)."""

    def __init__(self, o, plan, rep):
        self.plan_name = plan
        super().__init__(o, "dissem_" + plan, 1, 1, 1.0, rep)
        self.done_t = {d: None for d in EDGES}
        self.pend = defaultdict(set)     # (provider, destination) -> fragments still to be added to that flow
        self.fwd_flow = {}               # (provider, destination) -> flow id

    def make_run_id(self, policy, n_sess, mtag, rho, btag, rep, stamp):
        c = self.caps if hasattr(self, "caps") else None
        return f"plan={self.plan_name}_bs={self.a.source_mbps or self.a.cap_mbps:g}_bf={self.a.holder_mbps or self.a.cap_mbps:g}_bin={self.a.in_mbps or self.a.cap_mbps:g}_rep={rep}_{stamp}"

    def plan(self, sid, reason):
        return   # no re-planning in Experiment B

    def handle(self, m):
        k = m.get("kind")
        if k == "NODE_LOST":
            raise RuntimeError(f"node {m['label']} lost: {m.get('error')}")
        nc = self.node(m["label"])
        with self.lock:
            if k == "FRAG_SENT":
                fl = self.flows.get(m["flow_id"])
                self.sent.append((nc.to_orch(m["t_end"]), m["label"], m["dst"], m["session"], m["fragment_id"], m["bytes"]))
                if fl:
                    fl["left"].discard(m["fragment_id"]); fl["bytes"] += m["bytes"]
            elif k == "FRAG_SKIP":
                fl = self.flows.get(m["flow_id"])
                self.skipped["s0"].add(m["fragment_id"])
                if fl:
                    fl["left"].discard(m["fragment_id"]); fl["n_skipped"] = fl.get("n_skipped", 0) + 1
            elif k == "FRAG_RECV":
                f, dst = m["fragment_id"], m["label"]
                t = nc.to_orch(m["t_end"])
                self.recv.append((t, m["src"], dst, "s0", f, m["bytes"], m["ok"], m["dup"]))
                if m["ok"] and not m["dup"]:
                    self.held["s0"][dst].add(f)
                    if len(self.held["s0"][dst]) == self.nfr() and self.done_t[dst] is None:
                        self.done_t[dst] = t; self.ev.log("destination_complete", t, destination=dst)
                    for d in EDGES:   # pipelined forwarding: the verified fragment goes downstream now
                        key = (dst, d)
                        if f in self.pend[key]:
                            self.pend[key].discard(f)
                            fl = self.flows[self.fwd_flow[key]]
                            fl["left"].add(f); fl["n"] += 1
                            self.node(dst).cast("FLOW_ADD", flow_id=fl["id"], frag_ids=[f], closed=not self.pend[key])
                            if not self.pend[key]:
                                fl["closed"] = True
            elif k == "FLOW_DONE":
                fl = self.flows.get(m["flow_id"])
                if fl and fl["active"]:
                    fl["active"] = False; fl["t_end"] = nc.to_orch(m["t"])
                    self.realloc()
            elif k == "SINK_COMPLETE":
                self.ev.log("sink_complete", nc.to_orch(m["t"]), session=m["session"], node=m["label"], digest_ok=m["digest_ok"])
            elif k == "EVENT":
                self.ev.log(m["event"], nc.to_orch(m["t"]), **{x: y for x, y in m.items() if x not in ("kind", "event", "t", "label")})

    def execute(self):
        a = self.a
        print(f"[orch] === {self.run_id} ===", flush=True)
        for lb in ["A"] + EDGES:
            self.node(lb).call("RUN_BEGIN", run_rel=self.rel_dir)
        r = self.node("A").call("SOURCE_SETUP", sessions=["s0"], sink_bytes=a.sink_bytes, frag_bytes=a.frag_bytes, timeout=1800)
        man = r["manifests"]
        self.lens = man["s0"]["lens"]; self.flen = a.frag_bytes
        for e in EDGES:
            self.node(e).call("MANIFESTS", manifests=man, timeout=600)
        self.held["s0"]["A"] = set(range(self.nfr()))
        while not self.o.events.empty():
            self.o.events.get()
        self.t0 = time.time(); self.ev.set_ref(self.t0)
        self.ev.log("start", self.t0, plan=self.plan_name, caps={f"{n}:{d}": v / 1e6 for (d, n), v in self.caps.items()})
        with self.lock:
            self.prov = dissem_assign(self.plan_name, self.nfr(), self.flen, self.caps)
            by = defaultdict(list)
            for (f, d), p in self.prov.items():
                by[(p, d)].append(f)
            for (p, d), fids in sorted(by.items()):
                if p == "A":
                    self.start_flow("s0", "A", d, sorted(fids), f"{self.plan_name}: source -> {d}")
                else:   # open flow; fragments are added as they are verified at p
                    self.pend[(p, d)] = set(fids)
                    fl = self.start_flow("s0", p, d, [], f"{self.plan_name}: {p} forwards to {d} as fragments arrive", keep_order=True, closed=False)
                    fl["n"] = 0; self.fwd_flow[(p, d)] = fl["id"]
            self.ev.log("plan", plan=self.plan_name, flows={f"{p}->{d}": len(v) for (p, d), v in by.items()})
        slowest = min(self.caps.values())
        deadline = self.t0 + 4 * a.sink_bytes * 8 / slowest + 30
        while True:
            try:
                m = self.o.events.get(timeout=0.02)
                self.handle(m)
            except queue.Empty:
                pass
            if all(self.done_t[d] is not None for d in EDGES):
                self.stop_reason = "all destinations complete"; break
            if time.time() >= deadline:
                self.stop_reason = "deadline"; break
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
        return self.finish_dissem(ends, deadline)

    def finish_dissem(self, ends, deadline):
        a = self.a; S = a.sink_bytes
        t_end = min(time.time(), deadline)
        comp = {d: (None if self.done_t[d] is None else self.rel(self.done_t[d])) for d in EDGES}
        fin = [v for v in comp.values() if v is not None]
        tot = sum(b for *_, b in self.sent); src = sum(b for t, s_, d, sid, f, b in self.sent if s_ == "A")
        link = defaultdict(int); egress = defaultdict(int)
        for t, s_, d, sid, f, b in self.sent:
            link[f"{s_}->{d}"] += b; egress[s_] += b
        dup = sum(b for *_, b, ok, dup_ in self.recv if dup_)
        missing = {d: self.nfr() - len(self.held["s0"][d]) for d in EDGES}
        nic = {}
        for lb, e in ends.items():
            rows = [l.split(",") for l in (e.get("network_csv") or "").splitlines()[1:] if l.strip()]
            vals = [float(r[4]) for r in rows if r[4] and float(r[0]) >= self.t0]
            vtx = [float(r[5]) for r in rows if r[5] and float(r[0]) >= self.t0]
            nic[lb] = {"rx_peak": max(vals) if vals else None, "tx_peak": max(vtx) if vtx else None}
        # pipelining check: first forwarded fragment left a forwarder before that forwarder held the whole Sink
        fwd_first = {}
        for t, s_, d, sid, f, b in sorted(self.sent):
            if s_ != "A" and s_ not in fwd_first:
                fwd_first[s_] = self.rel(t)
        pipelined = {p: (comp[p] is None or fwd_first[p] < comp[p]) for p in fwd_first}
        by = defaultdict(int)
        for (f, d), p in self.prov.items():
            by[f"{p}->{d}"] += 1
        summary = {
            "run_id": self.run_id, "plan": self.plan_name, "rep": self.rep, "sink_bytes": S, "frag_bytes": a.frag_bytes,
            "caps_mbps": {f"{n}:{d}": v / 1e6 for (d, n), v in self.caps.items()}, "stop_reason": self.stop_reason, "duration_s": t_end - self.t0,
            "completion_s": comp, "makespan_s": max(fin) if len(fin) == 3 else None, "destinations_complete": len(fin),
            "bytes": {"total_sent": tot, "source_sent": src, "by_link": dict(link), "egress_by_node": dict(egress), "duplicate": dup},
            "normalized": {"total_sinks": tot / S, "source_sinks": src / S, "egress_sinks_by_node": {k: v / S for k, v in egress.items()}},
            "assignment": dict(by), "first_forward_s": fwd_first, "pipelined": pipelined, "missing_fragments": missing,
            "node_stats": {lb: e.get("stats") for lb, e in ends.items()},
            "paced_egress_worst_10s_mbps": {lb: e.get("egress_worst_10s_mbps") for lb, e in ends.items()},
            "nic": nic, "hosts": {lb: self.node(lb).hello.get("host") for lb in ["A"] + EDGES},
            "node_commits": {lb: self.node(lb).hello.get("commit") for lb in ["A"] + EDGES},
            "validation": {"all_fragments_verified": all(ok for *_, ok, dup_ in self.recv),
                           "no_duplicates": dup == 0, "all_destinations_complete": len(fin) == 3,
                           "four_hosts_distinct": len({self.node(lb).hello.get("host") for lb in ["A"] + EDGES}) == 4,
                           "nodes_same_commit": len({self.node(lb).hello.get("commit") for lb in ["A"] + EDGES} | {git_commit().split()[0]}) == 1,
                           "nic_within_cap": all(v["rx_peak"] is None or v["rx_peak"] <= 1.15 * self.caps[("in", lb)] / 1e6 for lb, v in nic.items()),
                           "paced_egress_within_cap": all((e.get("egress_worst_10s_mbps") or 0) <= 1.05 * self.caps[("out", lb)] / 1e6 for lb, e in ends.items()),
                           "forwarders_pipelined": all(pipelined.values()) if pipelined else True},
        }
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
        (self.dir / "config.json").write_text(json.dumps({"args": vars(a), "plan": self.plan_name, "nodes": self.o.node_spec,
                                                          "transport": "tcp+tcp_maxseg+per-flow token bucket, max-min fair per-node caps, FLOW_ADD pipelining"}, indent=1, default=str))
        with open(self.dir / "flows.csv", "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["flow", "src", "dst", "n", "bytes", "t_start_rel", "t_end_rel", "closed_at_start", "reason"])
            for fl in self.flows.values():
                w.writerow([fl["id"], fl["src"], fl["dst"], fl["n"], fl["bytes"], f"{self.rel(fl['t_start']):.3f}", "" if fl["t_end"] is None else f"{self.rel(fl['t_end']):.3f}",
                            fl.get("closed"), fl["reason"]])
        c = summary["completion_s"]
        print(f"[orch] {self.plan_name}: completion B {c['B'] and round(c['B'], 1)} C {c['C'] and round(c['C'], 1)} D {c['D'] and round(c['D'], 1)} s, "
              f"makespan {summary['makespan_s'] and round(summary['makespan_s'], 1)} s, source {src / S:.2f} S, total {tot / S:.2f} S, dup {dup / S:.2f} S, "
              f"pipelined {pipelined}, valid {all(summary['validation'].values())}", flush=True)
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
    p.add_argument("--policies", default="restart,reuse_fixed,reuse_adaptive", help="any of restart,reuse_fixed,reuse_adaptive,reuse_aware,reuse_aware_in,reuse_dyn")
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
    p.add_argument("--dissem", default="", help="Experiment B: dissemination plans to run (star,line,tree,multipath,aware); '' = off")
    p.add_argument("--source_mbps", type=float, default=0.0, help="cap A's egress (0 = cap_mbps)")
    p.add_argument("--in_mbps", type=float, default=0.0, help="cap every edge's ingress (0 = cap_mbps)")
    p.add_argument("--cap_events", default="", help="E.4 network changes, ';'-separated: 't=20:C:out=62.5' or 'D>=0.5:C:out=62.5' (planners are not told)")
    p.add_argument("--dyn_period", type=float, default=0.5, help="reuse_dyn: seconds between re-plan checks")
    p.add_argument("--dyn_window", type=float, default=2.0, help="reuse_dyn: throughput measurement window (s)")
    p.add_argument("--dyn_warmup", type=float, default=2.0, help="reuse_dyn: no re-plan within this time after a move or a re-plan")
    p.add_argument("--dyn_eps", type=float, default=1.0, help="reuse_dyn: hysteresis margin added to the switching cost (s)")
    p.add_argument("--dyn_rel", type=float, default=0.10, help="reuse_dyn: minimum relative ETA improvement")
    p.add_argument("--dyn_ctrl", type=float, default=0.3, help="reuse_dyn: control-plane cost assumed per switch (s, Phase 1 measurement)")
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
        if a.dissem:
            for rep in range(1, a.reps + 1):
                for plan in a.dissem.split(","):
                    tag = f"plan={plan}_bs={a.source_mbps or a.cap_mbps:g}_bf={a.holder_mbps or a.cap_mbps:g}_bin={a.in_mbps or a.cap_mbps:g}_rep={rep}_"
                    done = [d for d in root.glob(tag + "*") if (d / "summary.json").exists()]
                    if done and not a.no_resume:
                        print(f"[orch] skip (done): {done[0].name}", flush=True); continue
                    out.append(DissemRun(o, plan, rep).execute())
            raise SystemExit(0)
        for rep in range(1, a.reps + 1):
            for moves in [int(x) for x in a.moves.split(",")]:
                for rho in [float(x) for x in a.rhos.split(",")]:
                    for n in [int(x) for x in a.sessions.split(",")]:
                        for pol in a.policies.split(","):
                            for pp in prepos_configs(a, rep):
                                mtag = "cont" if moves == 0 else str(moves)
                                btag = (f"_bh={a.holder_mbps:g}" if a.holder_mbps else "") + prepos_tag(pp)
                                if a.cap_events:
                                    btag += "_ev=" + a.cap_events.replace(":", "").replace(";", "+").replace("=", "").replace(">", "ge")
                                done = [d for d in root.glob(f"policy={pol}_N={n}_moves={mtag}_rho={rho:g}{btag}_rep={rep}_*") if (d / "summary.json").exists()]
                                if done and not a.no_resume:
                                    print(f"[orch] skip (done): {done[0].name}", flush=True); continue
                                out.append(Run(o, pol, n, moves, rho, rep, prepos=pp).execute())
    except SystemExit:
        pass
    finally:
        o.shutdown()
    (EVAL_ROOT / a.experiment).mkdir(parents=True, exist_ok=True)
    print(f"[orch] done: {len(out)} runs")


if __name__ == "__main__":
    main()
