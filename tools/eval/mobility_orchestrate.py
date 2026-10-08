#!/usr/bin/env python3
"""Phase 3 orchestrator: physical repeated mobility A -> B -> C -> D with Progress-Aware Continuity Routing.

Runs on any host that reaches the four nodes (tools/eval/mobility_node.py, one per physical host). Drives
the schedule (execution handoffs every T_m), decides Sink fragment routing per policy, allocates per-flow
rates so that no node's emulated egress or ingress exceeds the link bandwidth (max-min fair; the physical
NIC enforces ~9.4 Gbps for native runs), and writes one run directory per (policy, bw, rho, rep):
config.json, events.csv (all nodes, orchestrator clock), fragments.csv, metrics.csv, p_current.csv,
flows.csv, trace.txt, summary.json, host_info.json, git_commit.txt, node_X/network.csv.

Policies (sink routing; execution always moves A -> B -> C -> D):
    restart     cancel progress toward an obsolete owner; the source re-sends the whole Sink to the new owner
    relay       store-and-forward along the execution path: A->B complete, then B->C, then C->D
    relay_pipe  same path, but a node forwards fragments as soon as it holds them
    split       Ours: completed fragments stay valid wherever they are; every holder execution has left sends
                the fragments the new owner lacks (one claim per fragment), the source sends only the rest
    direct      oracle lower bound: the source sends to the final owner from time zero

    python tools/eval/mobility_orchestrate.py --measure_ts --bws 1000 2500 5000 native        # Step 1
    python tools/eval/mobility_orchestrate.py --bw 1000 --ts 14.2 --rhos 2 --policies all      # shakedown
    python tools/eval/mobility_orchestrate.py --dry_run --nodes A=127.0.0.1:29811:29812,...     # protocol test
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT, REPO_ROOT / "tools", REPO_ROOT / "tools" / "eval"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

from agents import connect_all, parse_hosts  # noqa: E402
from common import DEFAULT_MSS, EVAL_ROOT, CsvLog, EventLog, clock_sync_client, git_commit  # noqa: E402
from proto_handoff import MB, recv_msg, send_msg  # noqa: E402

EDGES = ["A", "B", "C", "D"]
POLICIES = ["restart", "relay", "relay_pipe", "split", "direct"]
POLICY_LABEL = {"restart": "Restart", "relay": "Relay", "relay_pipe": "Pipelined Relay", "split": "Ours (Progress-Aware Continuity Routing)", "direct": "Oracle Direct"}
REJOIN_DB = 35.0


def parse_nodes(spec: str | None, dry: bool) -> dict[str, dict]:
    default_hosts = {"A": "elves-01.be.ucsc.edu", "B": "elves-02.be.ucsc.edu", "C": "elves-03.be.ucsc.edu", "D": "elves-04.be.ucsc.edu"}
    out = {lb: {"host": default_hosts[lb], "ctl": 29811, "data": 29812} for lb in EDGES}
    if spec:
        for item in spec.split(","):
            lb, hp = item.split("=")
            parts = hp.split(":")
            out[lb] = {"host": parts[0], "ctl": int(parts[1]) if len(parts) > 1 else 29811, "data": int(parts[2]) if len(parts) > 2 else 29812}
    return out


# ----------------------------------------------------------------------------- node connection
class NodeConn:
    def __init__(self, label: str, host: str, port: int, mss, events: queue.Queue, timeout: float):
        from common import tcp_connect

        self.label, self.host, self.port = label, host, port
        self.sock = tcp_connect(host, port, mss, timeout=timeout, retry_s=5.0)
        self.sync = clock_sync_client(self.sock)
        self.off = self.sync["offset_s"]  # node_wall ~= orch_wall + off
        self.events = events
        self.lock = threading.Lock()
        self.pending: dict[int, dict] = {}
        self.n = 0
        hello, _ = recv_msg(self.sock)
        assert hello["kind"] == "HELLO", hello
        self.hello = hello
        threading.Thread(target=self._reader, daemon=True).start()

    def to_orch(self, t):
        return None if t is None else t - self.off

    def _reader(self):
        while True:
            try:
                hdr, _ = recv_msg(self.sock)
            except (ConnectionError, OSError) as exc:
                self.events.put({"kind": "NODE_LOST", "label": self.label, "error": repr(exc)}); return
            if hdr["kind"] == "REPLY":
                with self.lock:
                    w = self.pending.pop(hdr.get("cmd_id"), None)
                if w is not None:
                    w["resp"] = hdr; w["ev"].set()
            else:
                self.events.put(hdr)

    def cast(self, kind: str, **fields) -> dict:
        with self.lock:
            self.n += 1; cid = f"{self.label}{self.n}"
            w = {"ev": threading.Event(), "resp": None}; self.pending[cid] = w
            send_msg(self.sock, kind, {"cmd_id": cid, **fields}, b"", None)
        return w

    def call(self, kind: str, timeout: float = 600.0, **fields) -> dict:
        w = self.cast(kind, **fields)
        if not w["ev"].wait(timeout):
            raise TimeoutError(f"{self.label}: {kind} timed out after {timeout}s")
        r = w["resp"]
        if not r.get("ok"):
            raise RuntimeError(f"{self.label}: {kind} failed: {r.get('error')}")
        return r


# ----------------------------------------------------------------------------- rate allocation
def maxmin_rates(flows: list[tuple[str, str, str]], cap_bps: float) -> dict[str, float]:
    """Progressive filling: every active flow (id, src, dst) gets the max-min fair rate under per-node egress
    and ingress caps of `cap_bps`. Shared ingress at a destination is therefore divided among its senders;
    multiple senders never create extra destination bandwidth."""
    if cap_bps <= 0 or not flows:
        return {f: 0.0 for f, _, _ in flows}
    rate = {f: 0.0 for f, _, _ in flows}
    frozen = set()
    cap = defaultdict(lambda: cap_bps)  # ("out", node) / ("in", node) residual
    while len(frozen) < len(flows):
        active = [(f, s, d) for f, s, d in flows if f not in frozen]
        load = defaultdict(int)
        for f, s, d in active:
            load[("out", s)] += 1; load[("in", d)] += 1
        inc = min(cap[k] / n for k, n in load.items() if n > 0)
        for f, s, d in active:
            rate[f] += inc
        for k, n in load.items():
            cap[k] -= inc * n
        for f, s, d in active:
            if cap[("out", s)] <= 1e-6 or cap[("in", d)] <= 1e-6:
                frozen.add(f)
    return rate


# ----------------------------------------------------------------------------- one run
class Run:
    def __init__(self, orch, policy: str, bw_mbps: float, tm: float, rho, rep: int, hops: int):
        self.o = orch; self.a = orch.a
        self.policy, self.bw, self.tm, self.rho, self.rep = policy, bw_mbps, tm, rho, rep
        self.edges = EDGES[:hops + 1]
        self.final = self.edges[-1]
        bw_tag = "native" if bw_mbps <= 0 else f"{bw_mbps:g}"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rho_tag = "none" if rho is None else f"{rho:g}"
        self.run_id = f"policy={policy}_bw={bw_tag}_rho={rho_tag}_tm={tm if tm < 1e8 else 'inf'}_rep={rep}_{stamp}"
        self.rel = f"results/evaluation/{self.a.experiment}/{self.run_id}"
        self.dir = REPO_ROOT / self.rel
        self.dir.mkdir(parents=True, exist_ok=False)
        (self.dir / "git_commit.txt").write_text(git_commit() + "\n")
        self.ev = EventLog(self.dir / "events.csv", "orchestrator")
        self.frag_csv = CsvLog(self.dir / "fragments.csv", ["t_rel", "event", "session_id", "sink_version", "fragment_id", "src", "dst", "bytes", "flow", "ok", "dup", "classification"])
        self.metric_csv = CsvLog(self.dir / "metrics.csv", ["call", "t_out_rel", "owner", "owner_idx", "chunk_s", "psnr", "ssim", "missing", "sink_bound", "lag_hops", "gpu_mem_alloc_mb", "sink_slot_pos"])
        self.pcur_csv = CsvLog(self.dir / "p_current.csv", ["t_rel", "owner", "p_current", "held_A", "held_B", "held_C", "held_D"])
        self.flow_csv = CsvLog(self.dir / "flows.csv", ["flow", "src", "dst", "t_start_rel", "t_end_rel", "n_frags", "bytes", "rate_bps_last", "cancelled", "reason"])
        self.trace = open(self.dir / "trace.txt", "w")
        # routing state
        self.holders: dict[str, set] = {e: set() for e in EDGES}   # the policy's view of reusable progress
        self.physical: dict[str, set] = {e: set() for e in EDGES}  # what each node physically holds (verified)
        self.flows: dict[str, dict] = {}
        self.nflow = 0
        self.in_flight: dict[str, set] = defaultdict(set)  # dst -> fragments sent (FRAG_SENT) but not yet confirmed (FRAG_RECV)
        self.n_cancelled = 0
        self.owner_idx = 0
        self.moves: list[dict] = []
        self.sent: list[dict] = []       # FRAG_SENT records (orch clock)
        self.recv: list[dict] = []       # FRAG_RECV records
        self.metrics: list[dict] = []
        self.node_events: list[dict] = []
        self.bound: dict[str, float] = {}
        self.t0 = None
        self.manifest = None
        self.stop_reason = None

    # ---------------- helpers
    @property
    def owner(self):
        return self.edges[self.owner_idx]

    def node(self, lb) -> NodeConn:
        return self.o.nodes[lb]

    def rel_t(self, t):
        return None if t is None else t - self.t0

    def log(self, msg):
        line = f"[orch] {msg}"
        print(line, flush=True); self.trace.write(line + "\n"); self.trace.flush()

    def pct(self):
        n = len(self.manifest["frags"])
        return {e: 100.0 * len(self.holders[e]) / n for e in self.edges}

    def trace_state(self, title: str, decision: str = ""):
        act = [f"{f['src']}->{f['dst']} ({len(f['queue_left'])} left, {f['rate_bps'] / 1e6:.0f} Mbps)" for f in self.flows.values() if f["active"]]
        n = len(self.manifest["frags"])
        held = ", ".join(f"{e}: {p:5.1f}%" + (f" (phys {100.0 * len(self.physical[e]) / n:.1f}%)" if len(self.physical[e]) != len(self.holders[e]) else "") for e, p in self.pct().items())
        self.log(f"t={self.rel_t(time.time()):7.2f}s {title}\n        held   {held}\n        active {', '.join(act) if act else '-'}" + (f"\n        next   {decision}" if decision else ""))

    def p_current_row(self, t=None):
        t = time.time() if t is None else t
        n = len(self.manifest["frags"])
        self.pcur_csv.row(t_rel=f"{self.rel_t(t):.4f}", owner=self.owner, p_current=f"{len(self.holders[self.owner]) / n:.4f}", **{f"held_{e}": len(self.holders.get(e, ())) for e in EDGES})

    # ---------------- flows
    def start_flow(self, src: str, dst: str, frag_ids: list[int], closed: bool, reason: str):
        if not frag_ids and closed:
            return None
        self.nflow += 1
        fid = f"f{self.nflow}_{src}{dst}"
        nd = self.o.node_spec[dst]
        fl = {"id": fid, "src": src, "dst": dst, "queued": set(frag_ids), "queue_left": set(frag_ids), "closed": closed, "active": True, "rate_bps": 0.0,
              "t_start": time.time(), "t_end": None, "bytes": 0, "n_sent": 0, "cancelled": False, "reason": reason}
        self.flows[fid] = fl
        act = [(f["id"], f["src"], f["dst"]) for f in self.flows.values() if f["active"]]
        fl["rate_bps"] = maxmin_rates(act, self.bw * 1e6)[fid]
        self.node(src).call("FLOW_START", flow_id=fid, dst=dst, dst_host=nd["host"], dst_port=nd["data"], frag_ids=sorted(frag_ids), closed=closed, rate_bps=fl["rate_bps"])
        self.ev.log("flow_start", flow=fid, src=src, dst=dst, n=len(frag_ids), closed=closed, rate_bps=fl["rate_bps"], reason=reason)
        self.realloc()
        return fl

    def add_to_flow(self, fl: dict, frag_ids: list[int], closed: bool):
        new = [x for x in frag_ids if x not in fl["queued"]]
        if not new and (closed == fl["closed"]):
            return
        fl["queued"].update(new); fl["queue_left"].update(new); fl["closed"] = closed
        self.node(fl["src"]).call("FLOW_ADD", flow_id=fl["id"], frag_ids=sorted(new), closed=closed)

    def cancel_flow(self, fl: dict, reason: str):
        if not fl["active"]:
            return
        r = self.node(fl["src"]).call("FLOW_CANCEL", flow_id=fl["id"])
        fl["active"] = False; fl["cancelled"] = True; fl["t_end"] = time.time(); self.n_cancelled += 1
        self.ev.log("flow_cancel", flow=fl["id"], src=fl["src"], dst=fl["dst"], sent=len(r.get("sent", [])), left=len(fl["queue_left"]), reason=reason)
        self.realloc()

    def end_flow(self, fl: dict):
        fl["active"] = False; fl["t_end"] = time.time()
        self.realloc()

    def realloc(self):
        """Re-run the max-min allocation over the active flows and push every changed rate to its sender."""
        act = [(f["id"], f["src"], f["dst"]) for f in self.flows.values() if f["active"]]
        rates = maxmin_rates(act, self.bw * 1e6)
        for f_id, _, _ in act:
            fl = self.flows[f_id]
            if abs(rates[f_id] - fl["rate_bps"]) > 0.01 * max(1.0, fl["rate_bps"]):
                fl["rate_bps"] = rates[f_id]
                self.node(fl["src"]).call("FLOW_SET_RATE", flow_id=f_id, rate_bps=rates[f_id])
                self.ev.log("flow_rate", flow=f_id, rate_bps=rates[f_id])

    def active_claims(self, dst: str) -> set:
        s = set(self.in_flight.get(dst, set()))
        for f in self.flows.values():
            if f["active"] and f["dst"] == dst:
                s |= f["queue_left"]
        return s

    # ---------------- policy planning
    def plan(self, reason: str):
        pol, n_all = self.policy, set(range(len(self.manifest["frags"])))
        owner = self.owner
        decision = []
        if pol == "direct":
            if reason == "start":
                self.start_flow("A", self.final, sorted(n_all), True, "oracle: source -> final owner from t0")
                decision.append(f"A->{self.final} all {len(n_all)} fragments (oracle knows the final owner)")
        elif pol == "restart":
            for fl in list(self.flows.values()):
                if fl["active"] and fl["dst"] != owner:
                    self.cancel_flow(fl, "owner moved: obsolete transfer cancelled")
                    # progress at the abandoned owner is discarded by this policy
                    self.holders[fl["dst"]] = set(); decision.append(f"discard progress at {fl['dst']}")
            missing = n_all - self.holders[owner] - self.active_claims(owner)
            if missing and owner != "A":
                self.start_flow("A", owner, sorted(missing), True, "restart: source re-sends everything to the new owner")
                decision.append(f"A->{owner} {len(missing)} fragments from scratch")
        elif pol in ("relay", "relay_pipe"):
            if reason == "start":
                self.start_flow("A", "B", sorted(n_all), True, "relay: source -> first owner")
                decision.append("A->B all fragments (chain starts)")
            for i, x in enumerate(self.edges[1:-1], start=1):  # B, C
                succ = self.edges[i + 1]
                if self.owner_idx <= i:
                    continue  # execution has not left x yet
                held = self.holders[x]
                complete = len(held) == len(n_all)
                existing = next((f for f in self.flows.values() if f["src"] == x and f["dst"] == succ), None)
                if pol == "relay":
                    if complete and existing is None:
                        self.start_flow(x, succ, sorted(n_all - self.holders[succ]), True, "relay: whole Sink held, forward to successor")
                        decision.append(f"{x}->{succ} store-and-forward of the whole Sink")
                else:
                    todo = sorted(held - self.holders[succ])
                    if existing is None:
                        if todo or not complete:
                            self.start_flow(x, succ, todo, complete, "pipelined relay: forward held fragments to successor")
                            decision.append(f"{x}->{succ} pipelined ({len(todo)} held now, more as they arrive)")
                    elif existing["active"]:
                        self.add_to_flow(existing, todo, complete)
        elif pol == "split":
            if reason == "start":
                self.start_flow("A", "B", sorted(n_all), True, "source -> first owner")
                decision.append("A->B all fragments")
            else:
                for fl in list(self.flows.values()):
                    if fl["active"] and fl["dst"] != owner:
                        self.cancel_flow(fl, "owner moved: retarget remaining fragments (progress kept)")
                missing = n_all - self.holders[owner] - self.active_claims(owner)
                if missing:
                    assign: dict[str, list[int]] = defaultdict(list)
                    for f in sorted(missing):
                        # prefer the most recent holder execution has left (its progress is reused); the source sends the rest
                        src = next((e for e in reversed(self.edges[:self.owner_idx]) if e != "A" and f in self.holders[e]), "A")
                        assign[src].append(f)
                    for src, ids in assign.items():
                        self.start_flow(src, owner, ids, True, "progress-aware: " + ("reuse fragments already delivered" if src != "A" else "source sends only what no other holder has"))
                        mb = len(ids) * self.manifest["frag_bytes"] / MB
                        decision.append(f"{src}->{owner} {len(ids)} fragments ({mb:.0f} MiB){' already delivered to ' + src + ', reused' if src != 'A' else ' not yet anywhere else'}")
        return "; ".join(decision)

    # ---------------- event handling
    def handle(self, m: dict):
        kind = m.get("kind")
        lb = m.get("label")
        if kind == "NODE_LOST":
            raise RuntimeError(f"node {lb} lost: {m.get('error')}")
        nc = self.node(lb)
        if kind == "EVENT":
            t = nc.to_orch(m["t"])
            det = dict(m.get("detail") or {})
            for k in ("t_send_src", "t_go_src", "t_recv_start"):
                if k in det and det[k] is not None:
                    det[k] = self.rel_t(nc.to_orch(det[k]))
            self.ev.log(f"{lb}:{m['event']}", t, **det)
            self.node_events.append({"node": lb, "event": m["event"], "t": t, **det})
            if m["event"] == "sink_bind":
                self.bound[lb] = t
            return
        if kind == "METRIC":
            t = nc.to_orch(m["t_out"])
            lag = EDGES.index(lb) - max([EDGES.index(e) for e in self.bound] + [0])
            row = {"call": m["call"], "t_out_rel": self.rel_t(t), "owner": lb, "owner_idx": EDGES.index(lb), "chunk_s": m["chunk_s"], "psnr": m["psnr"], "ssim": m["ssim"], "missing": m["missing"],
                   "sink_bound": m["sink_bound"], "lag_hops": lag, "gpu_mem_alloc_mb": m["gpu_mem_alloc_mb"], "sink_slot_pos": m["sink_slot_pos"]}
            self.metrics.append(row)
            self.metric_csv.row(**{k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()})
            return
        if kind == "FRAG_SENT":
            rec = {"t_start": nc.to_orch(m["t_start"]), "t_end": nc.to_orch(m["t_end"]), "src": lb, "dst": m["dst"], "fid": m["fragment_id"], "bytes": m["bytes"], "flow": m["flow_id"]}
            self.sent.append(rec)
            self.in_flight[m["dst"]].add(m["fragment_id"])
            fl = self.flows.get(m["flow_id"])
            if fl:
                fl["queue_left"].discard(m["fragment_id"]); fl["bytes"] += m["bytes"]; fl["n_sent"] += 1
                if fl["closed"] and not fl["queue_left"] and fl["active"]:
                    self.end_flow(fl)
                    self.ev.log("flow_done", flow=fl["id"], src=fl["src"], dst=fl["dst"], bytes=fl["bytes"])
                    self.plan("flow_done")
            return
        if kind == "FRAG_RECV":
            rec = {"t_start": nc.to_orch(m["t_start"]), "t_end": nc.to_orch(m["t_end"]), "src": m["src"], "dst": lb, "fid": m["fragment_id"], "bytes": m["bytes"], "flow": m["flow_id"],
                   "ok": bool(m["ok"]), "dup": bool(m["dup"]), "rejected": m.get("rejected")}
            self.recv.append(rec)
            self.in_flight[lb].discard(m["fragment_id"])
            if rec["ok"] and not rec["dup"]:
                self.holders[lb].add(m["fragment_id"]); self.physical[lb].add(m["fragment_id"])
                if lb == self.owner:
                    self.p_current_row(rec["t_end"])
                if self.policy != "direct":
                    self.plan("frag")
            return

    def drain(self, budget_s: float = 0.0):
        t_end = time.time() + budget_s
        while True:
            try:
                m = self.o.events.get(timeout=max(0.0, t_end - time.time()) if budget_s > 0 else 0.0)
            except queue.Empty:
                return
            self.handle(m)
            if budget_s <= 0 and self.o.events.empty():
                return

    # ---------------- schedule
    def handoff(self, frm: str, to: str, i: int):
        nd = self.o.node_spec[to]
        t_req = time.time()
        r = self.node(frm).call("EXEC_HANDOFF", to=to, to_host=nd["host"], to_port=nd["data"], timeout=120)
        self.owner_idx = i
        mv = {"i": i, "from": frm, "to": to, "t_req": t_req, "t_stop": self.node(frm).to_orch(r["t_stop"]), "t_fg_sent": self.node(frm).to_orch(r["t_fg_sent"]), "call": r["call"], "fg_bytes": r["fg_bytes"]}
        self.moves.append(mv)
        self.ev.log("move", t_req, **{k: (self.rel_t(v) if k.startswith("t_") else v) for k, v in mv.items()})
        self.p_current_row(t_req)
        return mv

    def execute(self):
        o, a = self.o, self.a
        policy = self.policy
        self.log(f"=== run {self.run_id}: {POLICY_LABEL[policy]}, bw {self.bw or 'native'} Mbps, T_m {self.tm if self.tm < 1e8 else 'inf'} s, rho {self.rho}, path {'->'.join(self.edges)} ===")
        session_id = self.run_id
        for lb in self.edges:
            self.node(lb).call("RUN_BEGIN", run_id=self.run_id, run_rel=self.rel, session_id=session_id, t0=None)
        prep = self.node("A").call("SOURCE_PREP", M=a.migration_chunk, frag_bytes=a.frag_bytes, timeout=900)
        self.manifest = prep["manifest"]
        self.holders = {e: set() for e in EDGES}; self.holders["A"] = set(range(len(self.manifest["frags"])))
        self.physical = {e: set() for e in EDGES}; self.physical["A"] = set(self.holders["A"])
        for lb in self.edges[1:]:
            self.node(lb).call("MANIFEST", manifest=self.manifest, timeout=600)
        self.drain(0.5)
        # ---- migration start
        self.t0 = time.time(); self.ev.set_ref(self.t0)
        self.ev.log("migration_start", self.t0, policy=policy, bw_mbps=self.bw, tm=self.tm, rho=self.rho, sink_version=self.manifest["sink_version"], sink_nbytes=self.manifest["nbytes"], n_frags=len(self.manifest["frags"]))
        self.handoff("A", "B", 1)
        d = self.plan("start")
        self.trace_state("move A->B (migration start)", d)
        n_moves = len(self.edges) - 2
        next_move = 1
        final_move_t = self.t0 if n_moves == 0 else None
        t_rejoin_final = None
        stop_at = None
        deadline = self.t0 + a.max_run_s
        last_pcur = 0.0
        while True:
            self.drain(0.05)
            now = time.time()
            if now - last_pcur >= 1.0:
                self.p_current_row(now); last_pcur = now
            if next_move <= n_moves and now >= self.t0 + next_move * self.tm:
                frm, to = self.edges[next_move], self.edges[next_move + 1]
                self.handoff(frm, to, next_move + 1)
                d = self.plan("move")
                self.trace_state(f"move {frm}->{to}" + (" (final move)" if next_move == n_moves else ""), d)
                if next_move == n_moves:
                    final_move_t = time.time()
                next_move += 1
            # end conditions: rejoin at the final owner + tail calls, or deadline
            if final_move_t is not None and t_rejoin_final is None:
                rj = next((e for e in self.node_events if e["node"] == self.final and e["event"] == "rejoin"), None)
                if rj:
                    t_rejoin_final = rj["t"]; stop_at = time.time() + a.tail_calls * max(0.3, self.node(self.final).hello.get("service_s") or 0.55)
            if stop_at is not None and now >= stop_at:
                self.stop_reason = "rejoin+tail"; break
            if now >= deadline:
                self.stop_reason = "deadline"; break
            if any(e["event"] == "window_exhausted" for e in self.node_events):
                self.stop_reason = "window_exhausted"; break
        self.node(self.owner).call("EXEC_STOP")
        self.drain(1.0)
        for fl in list(self.flows.values()):
            if fl["active"]:
                self.cancel_flow(fl, "run end")
        self.drain(1.0)
        ends = {lb: self.node(lb).call("RUN_END", timeout=300) for lb in self.edges}
        self.drain(0.5)
        for lb, e in ends.items():
            if e.get("network_csv"):
                (self.dir / f"node_{lb}").mkdir(exist_ok=True)
                (self.dir / f"node_{lb}" / "network.csv").write_text(e["network_csv"])
        self.trace_state("run end", f"stop reason: {self.stop_reason}")
        return self.finish(prep, ends, final_move_t)

    # ---------------- accounting
    def finish(self, prep, ends, final_move_t):
        a = self.a
        man = self.manifest
        S = man["nbytes"]
        fin = self.final
        # classification of every delivered fragment
        sent_from = defaultdict(list)
        for s in self.sent:
            sent_from[(s["src"], s["fid"])].append(s["t_start"])
        useful = wasted = dup = 0
        for r in self.recv:
            cls = "rejected" if r["rejected"] else ("duplicate" if r["dup"] or not r["ok"] else None)
            if cls is None:
                forwarded_later = any(t > r["t_end"] - 1e-3 for t in sent_from.get((r["dst"], r["fid"]), []))
                cls = "useful" if (r["dst"] == fin or forwarded_later) else "wasted"
            if cls == "useful":
                useful += r["bytes"]
            elif cls == "wasted":
                wasted += r["bytes"]
            else:
                dup += r["bytes"]
            self.frag_csv.row(t_rel=f"{self.rel_t(r['t_end']):.4f}", event="recv", session_id=self.run_id, sink_version=man["sink_version"], fragment_id=r["fid"], src=r["src"], dst=r["dst"], bytes=r["bytes"], flow=r["flow"], ok=r["ok"], dup=r["dup"], classification=cls)
        for s in self.sent:
            self.frag_csv.row(t_rel=f"{self.rel_t(s['t_end']):.4f}", event="sent", session_id=self.run_id, sink_version=man["sink_version"], fragment_id=s["fid"], src=s["src"], dst=s["dst"], bytes=s["bytes"], flow=s["flow"], ok="", dup="", classification="")
        total_sent = sum(s["bytes"] for s in self.sent)
        total_recv = sum(r["bytes"] for r in self.recv)
        in_transit_lost = max(0, total_sent - total_recv)  # bytes on the wire when a flow was cancelled (never completed)
        wasted_total = wasted + in_transit_lost
        link_bytes = defaultdict(int); link_t0 = {}; link_t1 = {}
        for s in self.sent:
            k = f"{s['src']}->{s['dst']}"; link_bytes[k] += s["bytes"]
            link_t0[k] = min(link_t0.get(k, s["t_start"]), s["t_start"]); link_t1[k] = max(link_t1.get(k, s["t_end"]), s["t_end"])
        link_mbps = {k: link_bytes[k] * 8 / max(1e-6, link_t1[k] - link_t0[k]) / 1e6 for k in link_bytes}

        def peak_node_rate(recs, key):
            bins = defaultdict(lambda: defaultdict(int))
            for r in recs:
                bins[r[key]][int(r["t_end"] - self.t0)] += r["bytes"]
            return {n: max(b.values()) * 8 / 1e6 for n, b in bins.items()}  # Mbps over 1 s bins

        ingress_peak = peak_node_rate([r for r in self.recv if r["ok"]], "dst"); egress_peak = peak_node_rate(self.sent, "src")
        nic_rx_peak, nic_tx_peak = {}, {}
        for lb, e in ends.items():
            txt = e.get("network_csv") or ""
            rows_ = [l.split(",") for l in txt.splitlines()[1:] if l.strip()]
            win = [r_ for r_ in rows_ if float(r_[0]) >= self.t0]
            rx = [float(r_[4]) for r_ in win if r_[4]]; tx = [float(r_[5]) for r_ in win if r_[5]]
            nic_rx_peak[lb] = max(rx) if rx else None; nic_tx_peak[lb] = max(tx) if tx else None
        ev_final = [e for e in self.node_events if e["node"] == fin]
        t_complete = next((e["t"] for e in ev_final if e["event"] == "sink_complete"), None)
        t_verified = next((e["t"] for e in ev_final if e["event"] == "sink_verified"), None)
        t_bind = next((e["t"] for e in ev_final if e["event"] == "sink_bind"), None)
        t_rejoin = next((e["t"] for e in ev_final if e["event"] == "rejoin"), None)
        bind_call = next((e.get("call") for e in ev_final if e["event"] == "sink_bind"), None)
        rows_final = [m for m in self.metrics if m["owner"] == fin]
        t_first_bound_out = next((self.t0 + m["t_out_rel"] for m in rows_final if m["sink_bound"] and not m["missing"]), None)
        t_first_out_final = next((self.t0 + m["t_out_rel"] for m in rows_final if not m["missing"]), None)
        after8 = [m["psnr"] for m in rows_final if bind_call is not None and m["call"] >= bind_call + 8 and m["psnr"] is not None]
        rejoin_call = next((e.get("call") for e in ev_final if e["event"] == "rejoin"), None)
        after_rejoin = [m["psnr"] for m in rows_final if rejoin_call is not None and m["call"] >= rejoin_call and m["psnr"] is not None]
        ssim8 = [m["ssim"] for m in rows_final if bind_call is not None and m["call"] >= bind_call + 8 and m["ssim"] is not None]
        gap = [m["psnr"] for m in self.metrics if (bind_call is None or m["call"] < bind_call) and m["psnr"] is not None]
        first_sent = min((s["t_start"] for s in self.sent), default=None)
        tfm = final_move_t
        lat = lambda t: None if (t is None or tfm is None) else t - tfm  # noqa: E731
        for fl in self.flows.values():
            self.flow_csv.row(flow=fl["id"], src=fl["src"], dst=fl["dst"], t_start_rel=f"{self.rel_t(fl['t_start']):.4f}", t_end_rel="" if fl["t_end"] is None else f"{self.rel_t(fl['t_end']):.4f}",
                              n_frags=fl["n_sent"], bytes=fl["bytes"], rate_bps_last=f"{fl['rate_bps']:.0f}", cancelled=fl["cancelled"], reason=fl["reason"])
        # validation
        owners_seq = ["A"] + [m["to"] for m in self.moves]
        hosts = {lb: self.node(lb).hello.get("host") for lb in self.edges}
        resume_ts = {e["node"]: e["t"] for e in self.node_events if e["event"] == "resume"}
        single_owner = all(m["t_stop"] <= resume_ts.get(m["to"], float("inf")) for m in self.moves)
        links_used = sorted(link_bytes)
        chain_links = {f"{self.edges[i]}->{self.edges[i + 1]}" for i in range(len(self.edges) - 1)}
        reused_bytes = sum(s["bytes"] for s in self.sent if s["src"] != "A")
        first_fwd = {}
        for s in self.sent:
            if s["src"] != "A":
                first_fwd[s["src"]] = min(first_fwd.get(s["src"], s["t_start"]), s["t_start"])
        complete_t = {e["node"]: e["t"] for e in self.node_events if e["event"] == "sink_complete"}
        fwd_before_complete = {n: (n not in complete_t or t < complete_t[n]) for n, t in first_fwd.items()}
        validation = {
            "four_hosts_distinct": len(set(hosts.values())) == len(self.edges),
            "owner_sequence": owners_seq, "ownership_changed": owners_seq == self.edges,
            "single_owner": single_owner,
            # restart: only the source ever sends and nothing delivered to an abandoned owner is reused
            "restart_discarded_progress": None if self.policy != "restart" else (all(s["src"] == "A" for s in self.sent) and reused_bytes == 0),
            "relay_path_only_chain_links": None if self.policy not in ("relay", "relay_pipe") else all(k in chain_links for k in links_used),
            # meaningful only when the first hop was still incomplete at the first move (T_m < T_s)
            "relay_pipe_forwarded_before_complete": None if (self.policy != "relay_pipe" or ("B" in complete_t and self.moves[1:] and complete_t["B"] <= self.moves[1]["t_req"])) else (any(fwd_before_complete.values()) if fwd_before_complete else False),
            "ours_reused_fragments": None if self.policy != "split" else reused_bytes > 0,
            "oracle_direct_only": None if self.policy != "direct" else links_used == [f"A->{fin}"],
            "all_fragments_verified": all(r["ok"] for r in self.recv if not r["dup"]) and ends[fin].get("sink_verified") is True,
            "sink_version_consistent": not any(r["rejected"] for r in self.recv),
            "final_sink_digest_matches_source": ends[fin].get("sink_verified"),
            "ingress_peak_mbps_max": max(ingress_peak.values()) if ingress_peak else 0.0,
            "ingress_within_physical_cap": (max(ingress_peak.values()) if ingress_peak else 0.0) <= a.physical_cap_mbps * 1.05,
            "ingress_within_emulated_cap": None if self.bw <= 0 else (max(ingress_peak.values()) if ingress_peak else 0.0) <= self.bw * 1.15,
            # kernel NIC counters (network.csv, 1 s): the shaping must show up on the wire, not only in the orchestrator's bookkeeping
            "nic_rx_peak_mbps_by_node": nic_rx_peak, "nic_tx_peak_mbps_by_node": nic_tx_peak,
            "nic_ingress_within_emulated_cap": None if self.bw <= 0 else all(v is None or v <= self.bw * 1.15 for v in nic_rx_peak.values()),
            "continuity_comparable_to_phase1": (float(np.mean(after_rejoin)) >= 35.0) if after_rejoin else None,
            "stop_reason": self.stop_reason,
        }
        summary = {
            "run_id": self.run_id, "policy": self.policy, "policy_label": POLICY_LABEL[self.policy], "bw_mbps": self.bw, "tm_s": self.tm, "rho": self.rho, "rep": self.rep, "path": self.edges, "hosts": hosts,
            "sink_bytes": S, "n_frags": len(man["frags"]), "frag_bytes": man["frag_bytes"], "sink_version": man["sink_version"],
            "t_final_move_rel_s": self.rel_t(tfm), "moves": [{k: (self.rel_t(v) if k.startswith("t_") else v) for k, v in m.items()} for m in self.moves],
            "transfer_start_rel_s": self.rel_t(first_sent),
            "final": {"sink_complete_rel_s": self.rel_t(t_complete), "sink_verified_rel_s": self.rel_t(t_verified), "sink_bind_rel_s": self.rel_t(t_bind), "first_output_rel_s": self.rel_t(t_first_out_final),
                      "first_bound_output_rel_s": self.rel_t(t_first_bound_out), "rejoin_rel_s": self.rel_t(t_rejoin), "bind_call": bind_call},
            "latency_after_final_move_s": {"first_output": lat(t_first_out_final), "sink_received": lat(t_complete), "sink_verified": lat(t_verified), "sink_bind": lat(t_bind),
                                           "continuity_ready": lat(t_first_bound_out), "rejoin": lat(t_rejoin)},
            "bytes": {"total_sent": total_sent, "total_received": total_recv, "useful": useful, "wasted_delivered": wasted, "wasted_in_transit": in_transit_lost, "wasted": wasted_total, "duplicate": dup,
                      "by_link": dict(link_bytes), "by_src": {e: sum(v for k, v in link_bytes.items() if k.startswith(e + "->")) for e in self.edges},
                      "reused_from_non_source": reused_bytes},
            "normalized": {"total_traffic": total_sent / S, "waste": wasted_total / S, "useful": useful / S, "duplicate": dup / S},
            "throughput_mbps": {"by_link": link_mbps, "ingress_peak_by_node": ingress_peak, "egress_peak_by_node": egress_peak},
            "continuity": {"psnr_after_rejoin_mean": float(np.mean(after_rejoin)) if after_rejoin else None, "psnr_after_bind_8_mean": float(np.mean(after8)) if after8 else None, "psnr_after_bind_8_min": float(np.min(after8)) if after8 else None,
                           "ssim_after_bind_8_mean": float(np.mean(ssim8)) if ssim8 else None, "psnr_gap_mean": float(np.mean(gap)) if gap else None,
                           "rejoin_calls_after_bind": next((e.get("calls_after_bind") for e in ev_final if e["event"] == "rejoin"), None),
                           "lag_hops_mean": float(np.mean([m["lag_hops"] for m in self.metrics])) if self.metrics else None, "lag_hops_max": max((m["lag_hops"] for m in self.metrics), default=None),
                           "missing_chunks": sum(1 for m in self.metrics if m["missing"]), "n_chunks": len(self.metrics)},
            "held_at_end": {e: len(self.holders[e]) for e in self.edges}, "physically_held_at_end": {e: len(self.physical[e]) for e in self.edges}, "node_end": {lb: {k: v for k, v in e.items() if k != "network_csv"} for lb, e in ends.items()},
            "source_prep": {k: v for k, v in prep.items() if k != "manifest"}, "validation": validation,
        }
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
        (self.dir / "config.json").write_text(json.dumps({"experiment": a.experiment, "policy": self.policy, "bw_mbps": self.bw, "tm_s": self.tm, "rho": self.rho, "rep": self.rep, "path": self.edges,
                                                          "frag_bytes": a.frag_bytes, "migration_chunk": a.migration_chunk, "tail_calls": a.tail_calls, "max_run_s": a.max_run_s, "mss": a.mss,
                                                          "transport": "tcp+tcp_maxseg+per-flow token bucket; per-node egress/ingress caps = link bw (max-min fair)", "nodes": self.o.node_spec,
                                                          "args": vars(a)}, indent=1, default=str))
        (self.dir / "host_info.json").write_text(json.dumps({lb: {"hello": {k: v for k, v in self.node(lb).hello.items() if k != "kind"}, "clock_sync": self.node(lb).sync} for lb in self.edges}, indent=1, default=str))
        self.frag_csv.close(); self.metric_csv.close(); self.pcur_csv.close(); self.flow_csv.close()
        L = summary["latency_after_final_move_s"]
        self.log(f"{POLICY_LABEL[self.policy]} @ {self.bw or 'native'} Mbps rho {self.rho}: after final move: first output {L['first_output'] and round(L['first_output'], 2)} s, "
                 f"Sink received {L['sink_received'] and round(L['sink_received'], 2)} s, bound {L['sink_bind'] and round(L['sink_bind'], 2)} s, continuity-ready {L['continuity_ready'] and round(L['continuity_ready'], 2)} s, "
                 f"rejoin {L['rejoin'] and round(L['rejoin'], 2)} s | traffic {total_sent / S:.2f}x, waste {wasted_total / S:.2f}x, reused {reused_bytes / MB:.0f} MiB | "
                 f"PSNR after bind {summary['continuity']['psnr_after_bind_8_mean'] and round(summary['continuity']['psnr_after_bind_8_mean'], 1)} dB | ingress peak {validation['ingress_peak_mbps_max']:.0f} Mbps")
        self.trace.close()
        return summary


# ----------------------------------------------------------------------------- orchestrator
class Orchestrator:
    def __init__(self, a):
        self.a = a
        self.node_spec = parse_nodes(a.nodes, a.dry_run)
        self.events: queue.Queue = queue.Queue()
        self.nodes: dict[str, NodeConn] = {}
        self.agent_pids = {}

    def launch(self):
        hosts = parse_hosts(self.a.agent_hosts)
        labels = EDGES[:self.a.hops + 1]
        agents = connect_all(hosts, labels)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        gpus = dict(item.split("=") for item in self.a.gpus.split(","))
        for lb in labels:
            nd = self.node_spec[lb]
            cmd = [self.a.py, "tools/eval/mobility_node.py", "--label", lb, "--gpu_id", gpus.get(lb, "0"), "--ctl_port", str(nd["ctl"]), "--data_port", str(nd["data"]), "--mss", str(self.a.mss or 0),
                   "--migration_chunk", str(self.a.migration_chunk), "--post_chunks", str(self.a.post_chunks)]
            if self.a.iface:
                cmd += ["--iface", self.a.iface]
            cmd += self.a.node_extra.split()
            pid = agents[lb].run(cmd, f"results/evaluation/{self.a.experiment}/_launch_logs/node_{lb}_{stamp}.log")
            self.agent_pids[lb] = (agents[lb], pid)
            print(f"[orch] launched node {lb} on {nd['host']} (pid {pid})", flush=True)

    def connect(self):
        labels = EDGES[:self.a.hops + 1]
        for lb in labels:
            nd = self.node_spec[lb]
            print(f"[orch] connecting to node {lb} at {nd['host']}:{nd['ctl']} (waits for model load + baseline) ...", flush=True)
            self.nodes[lb] = NodeConn(lb, nd["host"], nd["ctl"], self.a.mss, self.events, timeout=self.a.connect_timeout)
            h = self.nodes[lb].hello
            print(f"[orch] node {lb} = {h.get('host')} service {h.get('service_s') and round(h['service_s'] * 1e3)} ms/chunk, mss {h.get('mss_effective')}, clock offset {self.nodes[lb].off * 1e3:+.2f} ms, dry_run={h.get('dry_run')}", flush=True)
            if h.get("dry_run") and not self.a.dry_run:
                raise SystemExit(f"node {lb} is a dry-run node; refusing to record results")

    def shutdown(self):
        for nc in self.nodes.values():
            try:
                send_msg(nc.sock, "SHUTDOWN", {}, b"", None)
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nodes", type=str, default=None, help="A=host[:ctl_port[:data_port]],... (default elves-01..04, 29811/29812)")
    ap.add_argument("--hops", type=int, default=3, help="3 = A->B->C->D")
    ap.add_argument("--experiment", type=str, default="repeated_mobility")
    ap.add_argument("--policies", type=str, default="all", help="comma list of restart,relay,relay_pipe,split,direct or 'all'")
    ap.add_argument("--bw", type=float, default=1000.0, help="link bandwidth in Mbps (0 = native, unshaped)")
    ap.add_argument("--ts", type=float, default=None, help="measured Sink transfer-ready time T_s at --bw (from --measure_ts); T_m = T_s / rho")
    ap.add_argument("--rhos", type=str, default="2", help="comma list of rho = T_s / T_m")
    ap.add_argument("--tm", type=str, default=None, help="explicit comma list of T_m in seconds (overrides --rhos)")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--frag_bytes", type=int, default=4 << 20)
    ap.add_argument("--migration_chunk", type=int, default=30)
    ap.add_argument("--post_chunks", type=int, default=220)
    ap.add_argument("--tail_calls", type=int, default=12, help="calls to keep generating at the final owner after rejoin")
    ap.add_argument("--max_run_s", type=float, default=600.0)
    ap.add_argument("--physical_cap_mbps", type=float, default=9400.0, help="Phase 0 measured single-NIC capacity (validation only)")
    ap.add_argument("--mss", type=int, default=DEFAULT_MSS)
    ap.add_argument("--iface", type=str, default=None)
    ap.add_argument("--measure_ts", action="store_true", help="Step 1: single transfer A->B (no moves) per bandwidth in --bws; reports T_s")
    ap.add_argument("--bws", type=str, default="1000 2500 5000 native")
    ap.add_argument("--launch", action="store_true", help="start the node processes through the per-host agents")
    ap.add_argument("--agent_hosts", type=str, default=None)
    ap.add_argument("--gpus", type=str, default="A=0,B=0,C=0,D=0")
    ap.add_argument("--py", type=str, default="auto")
    ap.add_argument("--node_extra", type=str, default="")
    ap.add_argument("--connect_timeout", type=float, default=2400.0)
    ap.add_argument("--keep_nodes", action="store_true", help="leave node processes running at the end")
    ap.add_argument("--dry_run", action="store_true", help="protocol test against dry-run nodes; results go to results/evaluation/_dryrun_<experiment>")
    a = ap.parse_args()
    a.mss = a.mss or None
    if a.dry_run:
        a.experiment = "_dryrun_" + a.experiment
    o = Orchestrator(a)
    if a.launch:
        o.launch()
    o.connect()
    results = []
    try:
        if a.measure_ts:
            out = []
            for bw_s in a.bws.split():
                bw = 0.0 if bw_s == "native" else float(bw_s)
                for rep in range(1, a.reps + 1):
                    r = Run(o, "restart", bw, 1e9, None, rep, hops=1)
                    s = r.execute(); results.append(s)
                    F = s["final"]
                    ts = (F["sink_verified_rel_s"] - s["transfer_start_rel_s"]) if F["sink_verified_rel_s"] is not None else None
                    out.append({"bw_mbps": bw, "rep": rep, "Ts_verified_s": ts, "transfer_start_rel_s": s["transfer_start_rel_s"], "last_byte_rel_s": F["sink_complete_rel_s"], "verified_rel_s": F["sink_verified_rel_s"],
                                "bind_rel_s": F["sink_bind_rel_s"], "first_bound_output_rel_s": F["first_bound_output_rel_s"], "rejoin_rel_s": F["rejoin_rel_s"], "sink_bytes": s["sink_bytes"], "run_id": s["run_id"]})
            tsdir = EVAL_ROOT / a.experiment / "_ts_measurement"; tsdir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            (tsdir / f"ts_{stamp}.json").write_text(json.dumps(out, indent=1))
            print("\nbw_mbps rep  Ts(verified)  start  last_byte  verified  bind  first_bound_out  rejoin   (s since migration start)")
            for x in out:
                f = lambda v: "   -  " if v is None else f"{v:6.2f}"  # noqa: E731
                print(f"{x['bw_mbps'] or 'native':>7} {x['rep']:3d}  {f(x['Ts_verified_s'])}       {f(x['transfer_start_rel_s'])} {f(x['last_byte_rel_s'])}  {f(x['verified_rel_s'])} {f(x['bind_rel_s'])}  {f(x['first_bound_output_rel_s'])}      {f(x['rejoin_rel_s'])}")
            print(f"-> {tsdir}")
        else:
            pols = POLICIES if a.policies == "all" else [p for p in a.policies.split(",") if p]
            if a.tm:
                tms = [(float(x), None if not a.ts else a.ts / float(x)) for x in a.tm.split(",")]
            else:
                assert a.ts, "--ts (measured T_s) is required to derive T_m from rho"
                tms = [(a.ts / float(r), float(r)) for r in a.rhos.split(",")]
            for rep in range(1, a.reps + 1):
                for tm, rho in tms:
                    for pol in pols:
                        r = Run(o, pol, a.bw, tm, rho, rep, hops=a.hops)
                        results.append(r.execute())
            (EVAL_ROOT / a.experiment).mkdir(parents=True, exist_ok=True)
    finally:
        if not a.keep_nodes:
            o.shutdown()
    print(f"[orch] done: {len(results)} runs under results/evaluation/{a.experiment}/")


if __name__ == "__main__":
    main()
