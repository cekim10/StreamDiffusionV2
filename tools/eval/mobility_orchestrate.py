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
    reuse_aware_in  OTTER at moves: bottleneck-aware fragment assignment from tools/eval/restore_planner.py (D0)
    reuse_dyn       OTTER event-driven: reuse_aware_in + re-planning on measured throughput (E-pilot v2 thresholds)
    full            Full migration (Experiment D): stop, transfer every state component (6.02 GiB), resume; no Sink flows.
                    Under repeated mobility a move that comes before the transfer completed redirects it: the node that
                    still holds the complete state (the last owner that generated) cancels the transfer (the partial
                    state at the abandoned destination is discarded) and sends the whole state to the new destination.
    cold            Cold restart (Experiment D): no state; every new owner restarts from the prompt (Phase 1 `cold`).
D0 options: --caps / --cap_events (per-node caps, changes the planners are not told about), --path (explicit owner
sequence; revisits such as A,B,C,D,B allowed), --prepos (placement window before the move, the source keeps
generating), decode timestamps per chunk. Experiment D: --cold_dest (OTTER cold destination: the destination node
process is started after the trigger), --hybrid_net N (scenario E: N network-level sessions share the source's egress,
tools/eval/hybrid_net.py).

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
from collections import defaultdict, deque
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
from restore_planner import assign_providers, dyn_decide, holder_order, parse_cap_events, prepos_alloc  # noqa: E402
from restore_planner import maxmin as maxmin_caps  # noqa: E402

EDGES = ["A", "B", "C", "D"]
POLICIES = ["restart", "relay", "relay_pipe", "split", "direct"]
POLICY_LABEL = {"restart": "Restart", "relay": "Relay", "relay_pipe": "Pipelined Relay", "split": "Reuse, fixed routing (holders forward; source sends the rest)", "direct": "Oracle Direct",
                "reuse_aware_in": "OTTER at moves (bottleneck-aware assignment, shared planner)", "reuse_dyn": "OTTER event-driven (shared planner, E-pilot v2 thresholds)",
                "full": "Full migration (stop, transfer all state, resume)", "cold": "Cold restart (fresh caches from the prompt)"}
AWARE = ("reuse_aware_in", "reuse_dyn")
EXEC_MODE = {"full": "full", "cold": "cold"}   # every other policy: "fast" (M1)
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
    def __init__(self, label: str, host: str, port: int, mss, events: queue.Queue, timeout: float, retry_s: float = 5.0):
        from common import tcp_connect

        self.label, self.host, self.port = label, host, port
        self.sock = tcp_connect(host, port, mss, timeout=timeout, retry_s=retry_s)
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
    def __init__(self, orch, policy: str, bw_mbps: float, tm: float, rho, rep: int, hops: int, path=None, prepos=None):
        self.o = orch; self.a = orch.a
        self.policy, self.bw, self.tm, self.rho, self.rep = policy, bw_mbps, tm, rho, rep
        self.edges = list(path) if path else EDGES[:hops + 1]
        assert self.edges[0] == "A" and "A" not in self.edges[1:] and all(x != y for x, y in zip(self.edges, self.edges[1:])), \
            "path must start at A, never return to A, and change owner at every move (revisits of B, C, D are allowed)"
        self.final = self.edges[-1]
        self.revisit = len(set(self.edges)) < len(self.edges)
        self.mode = EXEC_MODE.get(policy, "fast")
        self.cold_dest = bool(orch.a.cold_dest)
        assert not self.cold_dest or (len(self.edges) == 2 and policy not in EXEC_MODE), "--cold_dest: single move, an OTTER/M1-family policy"
        assert not (orch.a.hybrid_net and (policy not in ("restart", "split", "reuse_aware_in", "reuse_dyn") or bw_mbps <= 0)), "--hybrid_net: M1-family policy on a shaped network"
        self.net = None
        self.running = "A"          # the node currently generating (or about to: it holds the execution)
        self.state_holder = None    # full: the node holding the packed complete state while it is in transit
        self.state_xfers: dict[str, dict] = {}
        self.nxfer = 0
        self.holder_snaps: list = []   # (move index, {node: held set}) after each move's plan (verified progress retained)
        self.drop_epoch: dict[str, int] = {}
        self.cold_info = {}
        self.pp = prepos   # {"policy", "probs" (B, C, D), "L", "b", "dest", "tau"} or None
        self.candidates = [e for e in EDGES if e != "A"] if prepos else []
        self.nodes_used = list(dict.fromkeys(self.edges + self.candidates))
        bw_tag = "native" if bw_mbps <= 0 else f"{bw_mbps:g}"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rho_tag = "none" if rho is None else f"{rho:g}"
        tags = ("" if not path else "_path=" + "".join(self.edges)) + ("" if not prepos else f"_pp={prepos['policy']}_L={prepos['L']:g}_b={prepos['b']:g}") \
            + ("" if not self.a.cap_events else "_ev=" + self.a.cap_events.replace(":", "").replace(";", "+").replace("=", "").replace(">", "ge")) \
            + ("_colddest" if self.a.cold_dest else "") + (f"_hybrid={self.a.hybrid_net}" if self.a.hybrid_net else "")
        self.run_id = f"policy={policy}_bw={bw_tag}_rho={rho_tag}_tm={tm if tm < 1e8 else 'inf'}{tags}_rep={rep}_{stamp}"
        # per-node caps (D0): the emulated network; planners only see known_caps (never the live caps)
        if bw_mbps > 0:
            self.caps = {(d, n): bw_mbps * 1e6 for d in ("out", "in") for n in EDGES}
            for item in (self.a.caps or "").split(","):
                if item:
                    k, v = item.split("="); node, d = k.split(":"); self.caps[(d, node)] = float(v) * 1e6
        else:
            self.caps = None   # unshaped
        self.known_caps = dict(self.caps) if self.caps else {(d, n): self.a.physical_cap_mbps * 1e6 for d in ("out", "in") for n in EDGES}
        self.caps0 = dict(self.caps) if self.caps else None
        self.cap_events = parse_cap_events(self.a.cap_events)
        self.cap_changes = []
        self.flow_rx: dict[str, deque] = defaultdict(deque)   # flow id -> (t, bytes) verified at the destination
        self.rate_est: dict = {}
        self.last_plan_t = 0.0
        self.dyn_last = 0.0
        self.replans: list[dict] = []
        self.pp_alloc = self.pp_frag = None
        self.rel = f"results/evaluation/{self.a.experiment}/{self.run_id}"
        self.dir = REPO_ROOT / self.rel
        self.dir.mkdir(parents=True, exist_ok=False)
        (self.dir / "git_commit.txt").write_text(git_commit() + "\n")
        self.ev = EventLog(self.dir / "events.csv", "orchestrator")
        self.frag_csv = CsvLog(self.dir / "fragments.csv", ["t_rel", "event", "session_id", "sink_version", "fragment_id", "src", "dst", "bytes", "flow", "ok", "dup", "classification"])
        self.metric_csv = CsvLog(self.dir / "metrics.csv", ["call", "t_out_rel", "owner", "owner_idx", "chunk_s", "psnr", "ssim", "missing", "sink_bound", "lag_hops", "gpu_mem_alloc_mb", "sink_slot_pos", "t_decode_rel", "n_frames"])
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
    def rates(self, act):
        if self.net is not None:   # scenario E: the network sessions' flows share the same caps in one allocation
            return maxmin_caps(act + self.net.tuples(), self.caps)
        if self.caps:
            return maxmin_caps(act, self.caps)
        return maxmin_rates(act, self.bw * 1e6)   # bw <= 0: unshaped (all zero = no token bucket)

    def joint_realloc(self):
        """Scenario E: one max-min allocation over the GPU session's and the network sessions' flows."""
        act = [(f["id"], f["src"], f["dst"]) for f in self.flows.values() if f["active"]]
        rates = self.rates(act)
        for f_id, _, _ in act:
            fl = self.flows[f_id]
            if abs(rates[f_id] - fl["rate_bps"]) > 0.01 * max(1.0, fl["rate_bps"]):
                fl["rate_bps"] = rates[f_id]
                self.node(fl["src"]).call("FLOW_SET_RATE", flow_id=f_id, rate_bps=rates[f_id])
                self.ev.log("flow_rate", flow=f_id, rate_bps=rates[f_id])
        for f_id, _, _ in self.net.tuples():
            fl = self.net.flows[f_id]
            if abs(rates[f_id] - fl["rate"]) > 0.01 * max(1.0, fl["rate"]):
                fl["rate"] = rates[f_id]
                if fl["started"]:
                    self.net.node(fl["src"]).cast("FLOW_SET_RATE", flow_id=f_id, rate_bps=rates[f_id])
        return rates

    def start_flow(self, src: str, dst: str, frag_ids: list[int], closed: bool, reason: str, keep_order: bool = False):
        if not frag_ids and closed:
            return None
        self.nflow += 1
        fid = f"f{self.nflow}_{src}{dst}"
        nd = self.o.node_spec[dst]
        order = list(frag_ids) if keep_order else sorted(frag_ids)
        fl = {"id": fid, "src": src, "dst": dst, "queued": set(frag_ids), "queue_left": set(frag_ids), "closed": closed, "active": True, "rate_bps": 0.0,
              "t_start": time.time(), "t_end": None, "bytes": 0, "n_sent": 0, "cancelled": False, "reason": reason, "order": order}
        self.flows[fid] = fl
        act = [(f["id"], f["src"], f["dst"]) for f in self.flows.values() if f["active"]]
        fl["rate_bps"] = self.rates(act)[fid]
        self.node(src).call("FLOW_START", flow_id=fid, dst=dst, dst_host=nd["host"], dst_port=nd["data"], frag_ids=order, closed=closed, rate_bps=fl["rate_bps"])
        self.ev.log("flow_start", flow=fid, src=src, dst=dst, n=len(frag_ids), closed=closed, rate_bps=fl["rate_bps"], reason=reason)
        self.realloc()
        return fl

    def add_to_flow(self, fl: dict, frag_ids: list[int], closed: bool):
        new = [x for x in frag_ids if x not in fl["queued"]]
        if not new and (closed == fl["closed"]):
            return
        fl["queued"].update(new); fl["queue_left"].update(new); fl["closed"] = closed; fl.setdefault("order", []).extend(sorted(new))
        self.node(fl["src"]).call("FLOW_ADD", flow_id=fl["id"], frag_ids=sorted(new), closed=closed)

    def cancel_flow(self, fl: dict, reason: str):
        if not fl["active"]:
            return
        r = self.node(fl["src"]).call("FLOW_CANCEL", flow_id=fl["id"])
        fl["active"] = False; fl["cancelled"] = True; fl["t_end"] = time.time(); self.n_cancelled += 1
        fl["sent_by_node"] = set(r.get("sent", []))
        self.ev.log("flow_cancel", flow=fl["id"], src=fl["src"], dst=fl["dst"], sent=len(r.get("sent", [])), left=len(fl["queue_left"]), reason=reason)
        self.realloc()

    def end_flow(self, fl: dict):
        fl["active"] = False; fl["t_end"] = time.time()
        self.realloc()

    def realloc(self):
        """Re-run the max-min allocation over the active flows and push every changed rate to its sender."""
        if self.net is not None:
            self.joint_realloc(); return
        act = [(f["id"], f["src"], f["dst"]) for f in self.flows.values() if f["active"]]
        rates = self.rates(act)
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
        if self.policy in AWARE:
            return self.plan_aware(reason)
        pol, n_all = self.policy, set(range(len(self.manifest["frags"])))
        owner = self.owner
        decision = []
        if pol in EXEC_MODE:
            return ""   # full: the Sink travels inside the full state; cold: no Sink is restored
        if pol == "direct":
            if reason == "start":
                self.start_flow("A", self.final, sorted(n_all), True, "oracle: source -> final owner from t0")
                decision.append(f"A->{self.final} all {len(n_all)} fragments (oracle knows the final owner)")
        elif pol == "restart":
            cancelled = defaultdict(list)
            for fl in list(self.flows.values()):
                if fl["active"] and fl["dst"] != owner:
                    self.cancel_flow(fl, "owner moved: obsolete transfer cancelled")
                    cancelled[fl["dst"]].append(fl["id"])
            if reason == "move":
                # M1 only: progress at every abandoned owner is discarded, at the node too (a revisited owner starts empty)
                for e in dict.fromkeys(self.edges[1:self.owner_idx]):
                    if e != owner and (self.holders[e] or self.physical[e] or cancelled.get(e)):
                        rd = self.node(e).call("SINK_DROP", flows=cancelled.get(e, []))
                        self.drop_epoch[e] = rd["epoch"]
                        self.holders[e] = set(); self.physical[e] = set(); decision.append(f"discard progress at {e}")
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
            if reason == "start" and not self.pp and owner == "B":   # Phase 1 path, unchanged
                self.start_flow("A", "B", sorted(n_all), True, "source -> first owner")
                decision.append("A->B all fragments")
            else:
                # every other trigger (moves, arrivals, flow ends) as in Phase 1; (Experiment D) also a first move to another
                # edge or after placement
                for fl in list(self.flows.values()):
                    if fl["active"] and fl["dst"] != owner:
                        self.cancel_flow(fl, "owner moved: retarget remaining fragments (progress kept)")
                missing = n_all - self.holders[owner] - self.active_claims(owner)
                if missing:
                    assign: dict[str, list[int]] = defaultdict(list)
                    # prefer the most recent holder execution has left (its progress is reused), then a holder that was never
                    # an owner (pre-positioned fragments; the network-level reuse_fixed holder order); the source sends the rest.
                    # Without placement only past owners hold fragments, so this is the Phase 1 rule.
                    order = holder_order(self.edges[:self.owner_idx + 1], owner, self.holders, [e for e in EDGES if e != "A"])
                    for f in sorted(missing):
                        src = next((e for e in order if f in self.holders[e]), "A")
                        assign[src].append(f)
                    for src, ids in assign.items():
                        self.start_flow(src, owner, ids, True, "progress-aware: " + ("reuse fragments already delivered" if src != "A" else "source sends only what no other holder has"))
                        mb = len(ids) * self.manifest["frag_bytes"] / MB
                        decision.append(f"{src}->{owner} {len(ids)} fragments ({mb:.0f} MiB){' already delivered to ' + src + ', reused' if src != 'A' else ' not yet anywhere else'}")
        return "; ".join(decision)

    def plan_aware(self, reason: str):
        """OTTER at moves / event-driven: provider assignment by the shared planner (tools/eval/restore_planner.py) at
        the start, at moves, and when a flow ends with fragments still missing at the owner (same triggers as the
        network harness). Per-fragment arrivals do not re-plan."""
        if reason not in ("start", "move", "flow_done"):
            return ""
        owner, flen = self.owner, self.manifest["frag_bytes"]
        n_all = set(range(len(self.manifest["frags"])))
        for fl in list(self.flows.values()):
            if fl["active"] and fl["dst"] != owner:
                self.cancel_flow(fl, "owner moved: retarget remaining fragments (progress kept)")
        missing = n_all - self.holders[owner] - self.active_claims(owner)
        self.last_plan_t = time.time()
        if not missing:
            return ""
        history = self.edges[:self.owner_idx + 1]
        held = {e: self.holders.get(e, set()) for e in EDGES}
        holders = holder_order(history, owner, held, [e for e in EDGES if e != "A"])
        soon = {h: set(self.in_flight.get(h, set())) - held[h] for h in holders}
        backlog = defaultdict(float)
        for fl in self.flows.values():
            if fl["active"]:
                backlog[fl["src"]] += len(fl["queue_left"]) * flen
        inbound = sum(len(fl["queue_left"]) * flen for fl in self.flows.values() if fl["active"] and fl["dst"] == owner)
        assign, late = assign_providers(self.policy, missing=missing, own=owner, holders=holders, held=held, soon=soon, skipped=set(),
                                        backlog=backlog, inbound_bytes=inbound, known_caps=self.known_caps, flen=flen, history=history)
        decision = []
        for src in sorted(set(assign) | set(late)):
            ids = assign.get(src, []) + late.get(src, [])
            self.start_flow(src, owner, ids, True, f"{self.policy}: " + ("reuse fragments held at " + src if src != "A" else "source sends the rest"), keep_order=True)
            decision.append(f"{src}->{owner} {len(ids)} fragments")
        return "; ".join(decision)

    def tick(self, now: float):
        """Cap events (the emulated network changes; planners are not told) and event-driven re-planning checks."""
        n = len(self.manifest["frags"])
        for evn in self.cap_events:
            if evn.get("fired") or not self.caps:
                continue
            fire = (now - self.t0 >= evn["at"]) if evn["kind"] == "t" else (len(self.holders.get(evn["node"], ())) >= evn["frac"] * n)
            if fire:
                evn["fired"] = True
                self.caps[(evn["dir"], evn["cap_node"])] = evn["mbps"] * 1e6
                self.cap_changes.append((now, evn["cap_node"], evn["dir"], evn["mbps"]))
                self.ev.log("cap_change", now, node=evn["cap_node"], dir=evn["dir"], mbps=evn["mbps"], trigger=evn["spec"])
                self.realloc()
        if self.policy == "reuse_dyn" and now - self.dyn_last >= self.a.dyn_period:
            self.dyn_last = now
            self.dyn_check(now)
        if self.net is not None and self.net.t0 is not None:
            self.net.pump(now)

    def dyn_check(self, now: float):
        a, owner, flen = self.a, self.owner, self.manifest["frag_bytes"]
        if now - self.last_plan_t < a.dyn_warmup:
            return
        act = [fl for fl in self.flows.values() if fl["active"] and fl["dst"] == owner and fl["queue_left"]]
        if not act:
            return
        rate = {}
        for fl in act:
            q = self.flow_rx.get(fl["id"])
            if not q:
                return   # not enough measurement yet
            while q and q[0][0] < now - a.dyn_window:
                q.popleft()
            rate[fl["src"]] = rate.get(fl["src"], 0.0) + (sum(b for _, b in q) / a.dyn_window if q else 0.0)
        view = [{"src": fl["src"], "left": fl["queue_left"], "order": [f for f in fl["order"] if f in fl["queue_left"]] or sorted(fl["queue_left"]), "fl": fl} for fl in act]
        held = {e: self.holders.get(e, set()) for e in EDGES}
        d = dyn_decide(sid="s0", own=owner, act=view, rate=rate, rate_est=self.rate_est, now=now, held=held, known_caps=self.known_caps, flen=flen,
                       nodes=list(EDGES), window=a.dyn_window, ctrl=a.dyn_ctrl, eps=a.dyn_eps, rel=a.dyn_rel)
        if d is None:
            return
        t_dec = time.time()
        q = d["q"]
        for v in d["qflows"]:
            fl = v["fl"]
            self.cancel_flow(fl, f"replan: bottleneck {q} (eta {d['eta_cur']:.1f} -> {d['eta_new']:.1f} s)")
            # fragments the sender reports as sent (its FRAG_SENT may still be queued here) are in flight, not unclaimed
            for f in fl.get("sent_by_node", set()) & fl["queue_left"]:
                fl["queue_left"].discard(f); self.in_flight[fl["dst"]].add(f)
        new_flows = []
        for p_, ids in d["assign"].items():
            ex = next((fl for fl in self.flows.values() if fl["active"] and fl["src"] == p_ and fl["dst"] == owner and p_ != q), None)
            if ex is not None:
                self.add_to_flow(ex, ids, True); new_flows.append(ex["id"])
            else:
                fl = self.start_flow(p_, owner, sorted(ids), True, f"replan: {len(ids)} fragments moved from {q}", keep_order=True)
                new_flows.append(fl["id"] if fl else None)
        self.last_plan_t = t_dec
        rec = {"t_s": self.rel_t(t_dec), "owner": owner, "from": q, "to": {p_: len(v) for p_, v in d["assign"].items()}, "moved_fragments": sum(len(v) for v in d["assign"].values()),
               "eta_cur_s": d["eta_cur"], "eta_new_s": d["eta_new"], "dT_s": d["dT"], "c_switch_s": d["c_switch"], "margin_s": d["margin"],
               "measured_rate_mbps": {k: v * 8 / 1e6 for k, v in rate.items()}, "cap_est_mbps": {k: v * 8 / 1e6 for k, v in d["cap_est"].items()}, "cap_est_stale": d["stale"],
               "cap_change_t_s": self.rel_t(self.cap_changes[-1][0]) if self.cap_changes else None, "new_flows": new_flows}
        self.replans.append(rec)
        self.ev.log("replan", t_dec, **rec)
        # a cancelled flow may stop before its head fragment: assign anything still unclaimed by the same rules
        self.plan_aware("flow_done")

    def prepos_start(self):
        """Placement before the move (M3): the source sends the allocation to the candidates while it keeps generating."""
        caps = self.caps or self.known_caps
        x, frags, avail, order = prepos_alloc(self.pp, caps, self.manifest["nbytes"], len(self.manifest["frags"]), self.candidates)
        self.pp_alloc, self.pp_frag = x, frags
        for c in order:
            if frags[c]:
                self.start_flow("A", c, frags[c], True, f"prepos {self.pp['policy']}: speculative fragments to candidate {c}")
        self.ev.log("prepos", policy=self.pp["policy"], dest=self.pp["dest"], L=self.pp["L"], budget=self.pp["b"], avail_sinks=avail,
                    alloc_sinks={c: round(v, 4) for c, v in x.items()}, frags={c: len(v) for c, v in frags.items()})

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
            if m["event"] == "full_send_end" and det.get("t_start") is not None:
                det["t_start"] = nc.to_orch(det["t_start"])
            self.ev.log(f"{lb}:{m['event']}", t, **det)
            self.node_events.append({"node": lb, "event": m["event"], "t": t, **det})
            if m["event"] == "sink_bind":
                self.bound[lb] = t
            if m["event"] == "resume":
                self.running = lb
            if m["event"] in ("full_send_start", "full_send_end") and det.get("xfer") in self.state_xfers:
                self.state_xfers[det["xfer"]].update({"t_start": det.get("t_start", t)} if m["event"] == "full_send_start" else
                                                     {"t_end": t, "bytes": det.get("bytes"), "completed": det.get("completed"), "cancelled": det.get("cancelled")})
            if self.policy in AWARE and self.manifest is not None and self.t0 is not None:
                fl = self.flows.get(det.get("flow"))
                if m["event"] == "flow_skip_not_held" and fl is not None:
                    # the holder did not have it yet: release the claim so the next plan can assign it again
                    fl["queue_left"].discard(det.get("fragment_id")); fl["n_skipped"] = fl.get("n_skipped", 0) + 1
                if m["event"] == "flow_end":
                    if fl is not None and fl["active"]:
                        self.end_flow(fl)
                    self.plan_aware("flow_done")
            return
        if kind == "METRIC":
            t = nc.to_orch(m["t_out"])
            lag = EDGES.index(lb) - max([EDGES.index(e) for e in self.bound] + [0])
            row = {"call": m["call"], "t_out_rel": self.rel_t(t), "owner": lb, "owner_idx": EDGES.index(lb), "chunk_s": m["chunk_s"], "psnr": m["psnr"], "ssim": m["ssim"], "missing": m["missing"],
                   "sink_bound": m["sink_bound"], "lag_hops": lag, "gpu_mem_alloc_mb": m["gpu_mem_alloc_mb"], "sink_slot_pos": m["sink_slot_pos"],
                   "t_decode_rel": self.rel_t(nc.to_orch(m.get("t_decode"))) if m.get("t_decode") else None, "n_frames": m.get("n_frames")}
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
                   "ok": bool(m["ok"]), "dup": bool(m["dup"]), "rejected": m.get("rejected"), "discarded": bool(m.get("discarded"))}
            self.recv.append(rec)
            self.in_flight[lb].discard(m["fragment_id"])
            if m.get("epoch", 0) < self.drop_epoch.get(lb, 0):
                rec["discarded"] = True   # verified there before the node dropped the session's fragments
            if rec["discarded"]:
                return   # M1 only: arrived at an owner after it was abandoned and dropped; never held
            if rec["ok"] and not rec["dup"]:
                self.flow_rx[m["flow_id"]].append((rec["t_end"], m["bytes"]))
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
        if self.mode == "full":
            mv = self.full_handoff(frm, to, i, t_req)
        else:
            r = self.node(frm).call("EXEC_HANDOFF", to=to, to_host=nd["host"], to_port=nd["data"], mode=self.mode, timeout=120)
            mv = {"i": i, "from": frm, "to": to, "t_req": t_req, "t_stop": self.node(frm).to_orch(r["t_stop"]), "t_fg_sent": self.node(frm).to_orch(r["t_fg_sent"]),
                  "call": r["call"], "fg_bytes": r["fg_bytes"], "mode": self.mode}
            self.running = None
        self.owner_idx = i
        self.moves.append(mv)
        self.ev.log("move", t_req, **{k: (self.rel_t(v) if k.startswith("t_") else v) for k, v in mv.items()})
        self.p_current_row(t_req)
        return mv

    def full_handoff(self, frm: str, to: str, i: int, t_req: float) -> dict:
        """Full migration. If `frm` is generating, it stops, packs the whole state and sends it to `to`. If the state is
        still in transit (the user moved on before it arrived), the node holding the packed state cancels that transfer
        and sends the whole state again to `to` (the partial copy at the abandoned destination is discarded)."""
        nd = self.o.node_spec[to]
        self.drain()
        rate = 0.0
        self.nxfer += 1; xid = f"x{self.nxfer}"
        redirect = self.running != frm
        if redirect:
            holder = self.state_holder
            c = self.node(holder).call("FULL_CANCEL", timeout=60)
            if c.get("completed"):
                # the transfer finished just before this move: wait for the destination to resume, then hand off from it
                t_wait = time.time() + 60
                while self.running != frm and time.time() < t_wait:
                    self.drain(0.05)
                redirect = self.running != frm
        if not redirect:
            if self.caps:
                rate = min(self.caps[("out", frm)], self.caps[("in", to)])
            self.state_xfers[xid] = {"xfer": xid, "src": frm, "dst": to, "move": i, "t_req": t_req}
            r = self.node(frm).call("EXEC_HANDOFF", to=to, to_host=nd["host"], to_port=nd["data"], mode="full", xfer=xid, rate_bps=rate, timeout=300)
            self.state_holder = frm; self.running = None
            self.state_xfers[xid]["state_bytes"] = self.packed_bytes = r["state_bytes"]
            return {"i": i, "from": frm, "to": to, "t_req": t_req, "t_stop": self.node(frm).to_orch(r["t_stop"]), "t_fg_sent": None, "t_packed": self.node(frm).to_orch(r["t_packed"]),
                    "call": r["call"], "fg_bytes": 0, "mode": "full", "state_from": frm, "redirect": False, "xfer": xid}
        holder = self.state_holder
        if self.caps:
            rate = min(self.caps[("out", holder)], self.caps[("in", to)])
        self.state_xfers[xid] = {"xfer": xid, "src": holder, "dst": to, "move": i, "t_req": t_req, "state_bytes": self.packed_bytes}
        self.node(holder).call("FULL_SEND", to=to, to_host=nd["host"], to_port=nd["data"], xfer=xid, rate_bps=rate, timeout=60)
        return {"i": i, "from": frm, "to": to, "t_req": t_req, "t_stop": t_req, "t_fg_sent": None, "call": None, "fg_bytes": 0, "mode": "full",
                "state_from": holder, "redirect": True, "xfer": xid}

    def execute(self):
        o, a = self.o, self.a
        policy = self.policy
        self.log(f"=== run {self.run_id}: {POLICY_LABEL[policy]}, bw {self.bw or 'native'} Mbps, T_m {self.tm if self.tm < 1e8 else 'inf'} s, rho {self.rho}, path {'->'.join(self.edges)} ===")
        session_id = self.run_id
        cold = self.edges[1] if self.cold_dest else None
        warm = [lb for lb in self.nodes_used if lb != cold]
        if cold:
            self.o.check_reference(cold)
        self.gpu0_before = self.o.gpu0_state(self.nodes_used)   # prereg run validity: GPU 0 idle (others < 1 GiB) before the run
        for lb in warm:
            self.node(lb).call("RUN_BEGIN", run_id=self.run_id, run_rel=self.rel, session_id=session_id, t0=None)
        prep = self.node("A").call("SOURCE_PREP", M=a.migration_chunk, frag_bytes=a.frag_bytes, timeout=900)
        self.manifest = prep["manifest"]
        self.holders = {e: set() for e in EDGES}; self.holders["A"] = set(range(len(self.manifest["frags"])))
        self.physical = {e: set() for e in EDGES}; self.physical["A"] = set(self.holders["A"])
        for lb in warm[1:]:
            self.node(lb).call("MANIFEST", manifest=self.manifest, timeout=600)
        if a.hybrid_net:
            from hybrid_net import NetSessions

            self.net = NetSessions(self, self.o.net, a.hybrid_net)
            self.net.prepare(self.manifest["nbytes"])
        self.drain(0.5)
        # ---- migration start
        self.t0 = time.time(); self.ev.set_ref(self.t0)
        self.ev.log("migration_start", self.t0, policy=policy, bw_mbps=self.bw, tm=self.tm, rho=self.rho, sink_version=self.manifest["sink_version"], sink_nbytes=self.manifest["nbytes"], n_frags=len(self.manifest["frags"]),
                    path=self.edges, prepos=self.pp, cap_events=a.cap_events, caps_mbps=None if not self.caps else {f"{n}:{d}": v / 1e6 for (d, n), v in self.caps.items()})
        if self.pp:
            # placement window: the source keeps generating while it places fragments at the candidates; the move to the
            # true destination happens L seconds after the trigger
            self.node("A").call("EXEC_START")
            self.prepos_start()
            t_move = self.t0 + self.pp["L"]
            while time.time() < t_move:
                self.drain(0.05); self.tick(time.time())
        if cold:
            # OTTER cold destination: the destination process does not exist at the trigger; the source keeps generating
            # while the destination starts, loads the weights, initializes CUDA and provisions its buffers (all timed)
            self.node("A").call("EXEC_START")
            ci = self.cold_info
            ci["t_launch"] = time.time()
            ci["pid"] = self.o.start_node(cold, cold_start=True, tag=self.run_id)
            self.o.connect_one(cold)
            ci["t_hello"] = time.time()
            h = self.node(cold).hello
            ci.update({"t_process_start": self.node(cold).to_orch(h.get("t_main")), "t_runtime_ready": self.node(cold).to_orch(h.get("t_runtime_ready")),
                       "t_listen": self.node(cold).to_orch(h.get("t_listen")), "reference": h.get("reference")})
            self.node(cold).call("RUN_BEGIN", run_id=self.run_id, run_rel=self.rel, session_id=session_id, t0=None)
            self.node(cold).call("MANIFEST", manifest=self.manifest, timeout=600)
            ci["t_ready"] = time.time()
            self.drain(0.05)
        self.handoff("A", self.edges[1], 1)
        d = self.plan("start")
        if self.net is not None:
            self.net.start(self.moves[-1]["t_req"])
        self.holder_snaps.append((1, {e: set(v) for e, v in self.holders.items()}))
        self.trace_state(f"move A->{self.edges[1]} (first move)", d)
        n_moves = len(self.edges) - 2
        next_move = 1
        # the move boundary is the handoff request (not the end of the post-move planning RPCs)
        final_move_t = self.moves[-1]["t_req"] if n_moves == 0 else None
        t_rejoin_final = None
        stop_at = None
        deadline = self.t0 + a.max_run_s
        last_pcur = 0.0
        while True:
            self.drain(0.05)
            now = time.time()
            self.tick(now)
            if now - last_pcur >= 1.0:
                self.p_current_row(now); last_pcur = now
            if next_move <= n_moves and now >= self.t0 + next_move * self.tm:
                frm, to = self.edges[next_move], self.edges[next_move + 1]
                self.handoff(frm, to, next_move + 1)
                d = self.plan("move")
                if self.net is not None:
                    self.net.move_all(to)
                self.holder_snaps.append((next_move + 1, {e: set(v) for e, v in self.holders.items()}))
                self.trace_state(f"move {frm}->{to}" + (" (final move)" if next_move == n_moves else ""), d)
                if next_move == n_moves:
                    final_move_t = self.moves[-1]["t_req"]
                next_move += 1
            # end conditions: rejoin at the final owner + tail calls (cold restart never rejoins: its first output at the
            # final owner + cold_tail_calls), or deadline; scenario E also waits for the network sessions (bounded)
            svc = max(0.3, self.node(self.final).hello.get("service_s") or 0.55)
            if final_move_t is not None and t_rejoin_final is None:
                key = "first_output" if self.mode == "cold" else "rejoin"
                rj = next((e for e in self.node_events if e["node"] == self.final and e["event"] == key and e["t"] >= final_move_t - 1e-3), None)
                if rj:
                    t_rejoin_final = rj["t"]; stop_at = time.time() + (a.cold_tail_calls if self.mode == "cold" else a.tail_calls) * svc
            if stop_at is not None and now >= stop_at:
                if self.net is None or self.net.all_restored_at(self.final) or now >= stop_at + a.net_grace_s:
                    self.stop_reason = "rejoin+tail" if self.net is None or self.net.all_restored_at(self.final) else "rejoin+tail; network sessions not all restored"
                    break
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
        ends = {lb: self.node(lb).call("RUN_END", timeout=300) for lb in self.nodes_used}
        self.drain(0.5)
        if self.net is not None:
            self.net_summary = self.net.end(self.stop_reason)

        for lb, e in ends.items():
            if e.get("network_csv"):
                (self.dir / f"node_{lb}").mkdir(exist_ok=True)
                (self.dir / f"node_{lb}" / "network.csv").write_text(e["network_csv"])
        self.trace_state("run end", f"stop reason: {self.stop_reason}")
        summary = self.finish(prep, ends, final_move_t)
        if cold:
            self.o.stop_node(cold, self.cold_info["pid"])   # a fresh destination process for every cold-destination run
        return summary

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
            cls = "rejected" if r["rejected"] else ("duplicate" if r["dup"] or not r["ok"] else ("wasted" if r.get("discarded") else None))
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
        # the final ownership only (a revisited final owner may have bound / produced output during an earlier visit)
        tfm0 = (final_move_t if final_move_t is not None else self.t0) - 1e-3
        ev_final = [e for e in self.node_events if e["node"] == fin and (e["event"] in ("sink_complete", "sink_verified") or e["t"] >= tfm0)]
        t_complete = next((e["t"] for e in ev_final if e["event"] == "sink_complete"), None)
        t_verified = next((e["t"] for e in ev_final if e["event"] == "sink_verified"), None)
        t_bind = next((e["t"] for e in ev_final if e["event"] == "sink_bind"), None)
        t_rejoin = next((e["t"] for e in ev_final if e["event"] == "rejoin"), None)
        bind_call = next((e.get("call") for e in ev_final if e["event"] == "sink_bind"), None)
        rows_final = [m for m in self.metrics if m["owner"] == fin and self.t0 + m["t_out_rel"] >= tfm0]
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
        hosts = {lb: self.node(lb).hello.get("host") for lb in self.nodes_used}
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
        st_evs = [e for e in self.node_events if e["event"] == "full_state_verified"]
        fin_full = next((e for e in reversed(st_evs) if e["node"] == fin), None)
        validation = {
            "four_hosts_distinct": len(set(hosts.values())) == len(self.nodes_used),
            "owner_sequence": owners_seq, "ownership_changed": owners_seq == self.edges,
            "single_owner": single_owner,
            # restart: only the source ever sends and nothing delivered to an abandoned owner is reused
            "restart_discarded_progress": None if self.policy != "restart" else (all(s["src"] == "A" for s in self.sent) and reused_bytes == 0),
            "relay_path_only_chain_links": None if self.policy not in ("relay", "relay_pipe") else all(k in chain_links for k in links_used),
            # meaningful only when the first hop was still incomplete at the first move (T_m < T_s)
            "relay_pipe_forwarded_before_complete": None if (self.policy != "relay_pipe" or ("B" in complete_t and self.moves[1:] and complete_t["B"] <= self.moves[1]["t_req"])) else (any(fwd_before_complete.values()) if fwd_before_complete else False),
            "ours_reused_fragments": None if self.policy != "split" else reused_bytes > 0,
            "oracle_direct_only": None if self.policy != "direct" else links_used == [f"A->{fin}"],
            # full / cold restore no Sink fragments (not applicable); full checks its state digests below
            "all_fragments_verified": None if self.mode != "fast" else (all(r["ok"] for r in self.recv if not r["dup"]) and ends[fin].get("sink_verified") is True),
            "sink_version_consistent": not any(r["rejected"] for r in self.recv),
            "final_sink_digest_matches_source": ends[fin].get("sink_verified") if self.mode == "fast" else (fin_full.get("sink_digest_matches_manifest") if (self.mode == "full" and fin_full) else None),
            "full_state_digests_ok": None if self.mode != "full" else (bool(fin_full) and bool(fin_full.get("all_ok"))),
            "full_bit_exact_after_resume": None if self.mode != "full" else (bool(rows_final) and all((m["psnr"] or 0) >= 99 for m in rows_final if not m["missing"])),
            "cold_no_state_transferred": None if self.mode != "cold" else (not self.sent and all(m["fg_bytes"] == 0 for m in self.moves) and not self.state_xfers),
            "nodes_same_commit": len({self.node(lb).hello.get("commit") for lb in self.nodes_used if lb in self.o.nodes} | {git_commit().split()[0]}) == 1,
            "ingress_peak_mbps_max": max(ingress_peak.values()) if ingress_peak else 0.0,
            "ingress_within_physical_cap": (max(ingress_peak.values()) if ingress_peak else 0.0) <= a.physical_cap_mbps * 1.05,
            "ingress_within_emulated_cap": None if self.bw <= 0 else (max(ingress_peak.values()) if ingress_peak else 0.0) <= self.bw * 1.15,
            # kernel NIC counters (network.csv, 1 s): the shaping must show up on the wire, not only in the orchestrator's bookkeeping
            "nic_rx_peak_mbps_by_node": nic_rx_peak, "nic_tx_peak_mbps_by_node": nic_tx_peak,
            "nic_ingress_within_emulated_cap": None if self.bw <= 0 else all(v is None or v <= self.bw * 1.15 for v in nic_rx_peak.values()),
            "continuity_comparable_to_phase1": (float(np.mean(after_rejoin)) >= 35.0) if after_rejoin else None,
            "stop_reason": self.stop_reason,
        }
        # ---- D0 accounting (preregistration v3, section 6)
        t_mv = tfm if tfm is not None else self.t0
        src_pre = sum(s["bytes"] for s in self.sent if s["src"] == "A" and s["t_start"] < t_mv)
        src_post = sum(s["bytes"] for s in self.sent if s["src"] == "A" and s["t_start"] >= t_mv)
        ok_first = [r for r in self.recv if r["ok"] and not r["dup"]]
        b_fwd = sum(r["bytes"] for r in ok_first if r["dst"] == fin and r["src"] != "A")
        abandoned = [e for e in self.edges[1:-1]]
        verified_at = {e: {r["fid"] for r in ok_first if r["dst"] == e} for e in self.nodes_used if e != "A"}
        V = set().union(*(verified_at[e] for e in abandoned)) if abandoned else set()
        reused = {r["fid"] for r in ok_first if r["dst"] == fin and r["src"] in abandoned} & V
        # retained: fragments verified at an owner before it was abandoned that the policy still holds there at the end
        t_left = {m_["from"]: m_["t_req"] for m_ in self.moves}
        retained = {}
        for k_, m_ in enumerate(self.moves):
            e = m_["from"]
            if e == "A" or e not in abandoned:
                continue
            # verified at e when it was abandoned (move k_), still held there at the next move (or at the end)
            before = {r["fid"] for r in ok_first if r["dst"] == e and r["t_end"] <= m_["t_req"]}
            nxt = next((snap for idx, snap in self.holder_snaps if idx == m_["i"] + 1), None)
            still = (nxt or self.holders).get(e, set())
            retained[e] = (len(before & still) / len(before)) if before else None
        x_at_move = {e: len({r["fid"] for r in ok_first if r["dst"] == e and r["t_end"] <= t_mv}) / len(man["frags"]) for e in self.nodes_used if e != "A"}
        version_events = sum(1 for e in self.node_events if e["event"] in ("fragment_rejected_version", "sink_version_mismatch")) + sum(1 for r in self.recv if r["rejected"])
        d0 = {"t_move_final_rel_s": self.rel_t(t_mv),
              "source_bytes_pre_move_sinks": src_pre / S, "source_bytes_post_move_sinks": src_post / S, "source_bytes_total_sinks": (src_pre + src_post) / S,
              "holder_forwarded_sinks": b_fwd / S, "aggregate_network_sinks": total_sent / S,
              "x_verified_at_move": x_at_move,
              "verified_progress_retained": retained,
              "verified_progress_reused": (len(reused) / len(V)) if V else None, "verified_at_abandoned_owners": len(V),
              "version_events": version_events, "replans": self.replans, "n_replans": len(self.replans),
              "cap_changes": [(self.rel_t(t), n, d, v) for t, n, d, v in self.cap_changes], "prepos": None if not self.pp else {**self.pp, "alloc_sinks": self.pp_alloc, "frags": {c: len(v) for c, v in (self.pp_frag or {}).items()}},
              "decode_rows": sum(1 for m in self.metrics if m.get("t_decode_rel") is not None)}
        validation["version_events_zero"] = version_events == 0
        # prereg run validity: GPU 0 idle before the run (others < 1 GiB; our idle node may be resident), paced payload egress
        # per node <= 1.05 x its cap in every 10 s window (fragments; a full-state transfer is one token bucket at the cap)
        g0 = getattr(self, "gpu0_before", None)
        validation["gpu0_before_run"] = g0
        validation["gpu0_idle_before_run"] = None if g0 is None else all("error" not in v and v["others_mib"] < 1024 and v["util_pct"] <= 5 for v in g0.values())
        pace = {}
        for src in {x["src"] for x in self.sent}:
            ts = sorted((x["t_end"], x["bytes"]) for x in self.sent if x["src"] == src)
            worst, j, acc = 0.0, 0, 0
            for i_, (t_, b_) in enumerate(ts):
                acc += b_
                while ts[j][0] < t_ - 10.0:
                    acc -= ts[j][1]; j += 1
                if t_ - ts[0][0] >= 10.0:
                    worst = max(worst, acc * 8 / 10 / 1e6)
            pace[src] = worst
        validation["paced_egress_worst_10s_mbps"] = pace
        validation["paced_egress_10s_within_cap"] = None if not self.caps else all(
            w <= 1.05 * max(self.caps[("out", n)], (self.caps0 or self.caps)[("out", n)]) / 1e6 for n, w in pace.items())
        # ---- Experiment D: per-move timing (from each move's trigger), execution-state bytes, revisit, cold destination
        per_move = []
        for k_, m_ in enumerate(self.moves):
            lo, hi = m_["t_req"], (self.moves[k_ + 1]["t_req"] if k_ + 1 < len(self.moves) else float("inf"))
            dst = m_["to"]
            inwin = lambda ev: next((e["t"] for e in self.node_events if e["node"] == dst and e["event"] == ev and lo - 1e-3 <= e["t"] < hi), None)  # noqa: E731
            fo = next((self.t0 + m["t_out_rel"] for m in self.metrics if m["owner"] == dst and not m["missing"] and lo - 1e-3 <= self.t0 + m["t_out_rel"] < hi), None)
            rel = lambda t: None if t is None else t - lo  # noqa: E731
            xf = self.state_xfers.get(m_.get("xfer")) if m_.get("xfer") else None
            per_move.append({"i": m_["i"], "from": m_["from"], "to": dst, "t_req_rel_s": self.rel_t(lo), "resume_s": rel(inwin("resume")), "first_output_s": rel(fo),
                             "sink_bind_s": rel(inwin("sink_bind")), "rejoin_s": rel(inwin("rejoin")), "fg_bytes": m_["fg_bytes"],
                             "state_transfer": None if not xf else {"src": xf["src"], "bytes": xf.get("bytes"), "completed": xf.get("completed"), "cancelled": xf.get("cancelled"),
                                                                     "start_s": rel(xf.get("t_start")), "end_s": rel(xf.get("t_end")), "redirect": m_.get("redirect")}})
        st_bytes = sum((x.get("bytes") or 0) for x in self.state_xfers.values())
        st_link = defaultdict(int)
        for x in self.state_xfers.values():
            st_link[f"{x['src']}->{x['dst']}"] += x.get("bytes") or 0
        fg_total = sum(m_["fg_bytes"] or 0 for m_ in self.moves)
        aborted = sum(e.get("bytes") or 0 for e in self.node_events if e["event"] == "full_recv_aborted")
        execution_state = {"mode": self.mode, "fg_bytes_total": fg_total, "state_transfer_bytes_total": st_bytes, "state_transfer_bytes_by_link": dict(st_link),
                           "state_transfers": list(self.state_xfers.values()), "state_bytes_completed": sum((x.get("bytes") or 0) for x in self.state_xfers.values() if x.get("completed")),
                           "state_bytes_cancelled": sum((x.get("bytes") or 0) for x in self.state_xfers.values() if not x.get("completed")), "partial_state_discarded_at_receivers": aborted,
                           "full_state_verified": [{k: v for k, v in e.items() if k in ("node", "xfer", "all_ok", "sink_digest_matches_manifest")} for e in st_evs],
                           "packed_state_bytes": next((x.get("state_bytes") for x in self.state_xfers.values() if x.get("state_bytes")), None)}
        d0["execution_state_bytes_sinks"] = (st_bytes + fg_total) / S
        d0["aggregate_network_incl_state_sinks"] = (total_sent + st_bytes + fg_total) / S
        revisit = None
        if self.revisit:
            first_left = next((m_["t_req"] for m_ in self.moves if m_["from"] == fin), None)
            v_before = {r["fid"] for r in ok_first if r["dst"] == fin and first_left is not None and r["t_end"] <= first_left}
            snap_ret = next((snap for idx, snap in self.holder_snaps if idx == len(self.moves)), None)
            revisit = {"final_owner": fin, "verified_before_leaving": len(v_before) / len(man["frags"]),
                       "held_on_return_policy_view": len((snap_ret or {}).get(fin, set())) / len(man["frags"]) if snap_ret is not None else None,
                       "verified_before_leaving_still_held_on_return": (len(v_before & (snap_ret or {}).get(fin, set())) / len(v_before)) if v_before and snap_ret is not None else None,
                       "fragments_received_again_after_return": sum(1 for r in ok_first if r["dst"] == fin and r["fid"] in v_before and tfm is not None and r["t_end"] > tfm),
                       "sink_drops": [e for e in self.node_events if e["event"] == "sink_dropped"]}
        cold_dest = None
        if self.cold_dest:
            ci = self.cold_info
            fr = lambda t: None if t is None else t - self.t0  # noqa: E731
            ttfo = next((self.t0 + m["t_out_rel"] for m in rows_final if not m["missing"]), None)
            cold_dest = {"timed_from": "trigger (t0)", "process_launch_s": fr(ci.get("t_launch")), "process_start_s": fr(ci.get("t_process_start")),
                         "runtime_ready_s": fr(ci.get("t_runtime_ready")), "listening_s": fr(ci.get("t_listen")), "connected_s": fr(ci.get("t_hello")),
                         "provisioned_s": fr(ci.get("t_ready")), "handoff_request_s": fr(final_move_t), "ttfo_s": fr(ttfo), "sink_verified_s": fr(t_verified),
                         "sink_bind_s": fr(t_bind), "first_bound_output_s": fr(t_first_bound_out), "rejoin_s": fr(t_rejoin), "reference": ci.get("reference"),
                         "source_kept_generating": True}
        summary = {
            "d0": d0, "per_move": per_move, "gpu_peak_mem_mb": {lb: {k: e.get(k) for k in ("peak_allocated_mb", "peak_reserved_mb")} for lb, e in ends.items()}, "execution_state": execution_state, "revisit": revisit, "cold_destination": cold_dest,
            "hybrid": None if self.net is None else {"n_network_sessions": self.net.N, "network_policy": self.net.policy, "network_run_dir": str(self.net.dir.relative_to(REPO_ROOT)),
                                                     "network_summary": {k: self.net_summary.get(k) for k in ("restored_sessions", "first_restored", "makespan_s", "bytes", "normalized", "validation", "stop_reason")},
                                                     "network_sessions": [dict(r) for r in __import__("csv").DictReader(open(self.net.dir / "sessions.csv"))]},
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
        (self.dir / "host_info.json").write_text(json.dumps({lb: {"hello": {k: v for k, v in self.node(lb).hello.items() if k != "kind"}, "clock_sync": self.node(lb).sync} for lb in self.nodes_used}, indent=1, default=str))
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
        self.agents = {}
        self.net = None
        self.cold_label = "B" if a.cold_dest else None   # --cold_dest: the destination is started after each trigger

    def labels(self):
        return EDGES[:self.a.hops + 1]

    def agent(self, lb):
        if lb not in self.agents:
            self.agents.update(connect_all(parse_hosts(self.a.agent_hosts), [lb]))
        return self.agents[lb]

    def node_cmd(self, lb, cold_start=False):
        nd = self.node_spec[lb]
        gpus = dict(item.split("=") for item in self.a.gpus.split(","))
        cmd = [self.a.py, "tools/eval/mobility_node.py", "--label", lb, "--gpu_id", gpus.get(lb, "0"), "--ctl_port", str(nd["ctl"]), "--data_port", str(nd["data"]), "--mss", str(self.a.mss or 0),
               "--migration_chunk", str(self.a.migration_chunk), "--post_chunks", str(self.a.post_chunks)]
        if self.a.iface:
            cmd += ["--iface", self.a.iface]
        if cold_start:
            cmd += ["--cold_start"]
        return cmd + self.a.node_extra.split()

    def launch(self):
        labels = [lb for lb in self.labels() if lb != self.cold_label]
        self.agents.update(connect_all(parse_hosts(self.a.agent_hosts), labels))
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for lb in labels:
            pid = self.agents[lb].run(self.node_cmd(lb), f"results/evaluation/{self.a.experiment}/_launch_logs/node_{lb}_{stamp}.log", env={"PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
            self.agent_pids[lb] = (self.agents[lb], pid)
            print(f"[orch] launched node {lb} on {self.node_spec[lb]['host']} (pid {pid})", flush=True)
        if self.a.hybrid_net:
            from hybrid_net import NetOrch

            self.net = NetOrch(self.a, self.node_spec)
            self.net.launch()

    def connect(self):
        for lb in self.labels():
            if lb != self.cold_label:
                self.connect_one(lb)
        if self.a.hybrid_net:
            if self.net is None:
                from hybrid_net import NetOrch

                self.net = NetOrch(self.a, self.node_spec)
            self.net.connect()

    def connect_one(self, lb):
        nd = self.node_spec[lb]
        print(f"[orch] connecting to node {lb} at {nd['host']}:{nd['ctl']} (waits for model load{'' if lb == self.cold_label else ' + baseline'}) ...", flush=True)
        # the cold destination is timed from the trigger: poll its control port every 20 ms, not every 5 s
        self.nodes[lb] = NodeConn(lb, nd["host"], nd["ctl"], self.a.mss, self.events, timeout=self.a.connect_timeout, retry_s=0.02 if lb == self.cold_label else 5.0)
        h = self.nodes[lb].hello
        print(f"[orch] node {lb} = {h.get('host')} service {h.get('service_s') and round(h['service_s'] * 1e3)} ms/chunk, mss {h.get('mss_effective')}, clock offset {self.nodes[lb].off * 1e3:+.2f} ms, "
              f"dry_run={h.get('dry_run')}, commit {(h.get('commit') or '?')[:7]}", flush=True)
        if h.get("dry_run") and not self.a.dry_run:
            raise SystemExit(f"node {lb} is a dry-run node; refusing to record results")

    # ---- OTTER cold destination: one fresh destination process per run
    def check_reference(self, lb):
        if self.a.dry_run:
            return
        ag = self.agent(lb)
        hits = ag.glob(f"results/evaluation/_reference_cache/*_M{self.a.migration_chunk}_N{self.a.post_chunks}_*.npz")
        host = ag.ping()["host"].split(".")[0]
        if not [h for h in hits if Path(h).name.startswith(host + "_")]:
            raise SystemExit(f"--cold_dest: no reference cache on {host} for M={self.a.migration_chunk}, N={self.a.post_chunks}; run one warm run with the same --post_chunks first")

    def gpu0_state(self, labels):
        """GPU 0 on every host just before a run: utilization and memory used by processes other than our own node."""
        if self.a.dry_run:
            return None
        out = {}
        for lb in labels:
            try:
                ag = self.agent(lb)
                own = {self.nodes[lb].hello.get("pid")} if lb in self.nodes else set()
                gpu = dict(item.split("=") for item in self.a.gpus.split(",")).get(lb, "0")
                util = ag.exec(["nvidia-smi", "-i", gpu, "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"])["stdout"].strip()
                apps = ag.exec(["nvidia-smi", "-i", gpu, "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"])["stdout"].strip()
                others = [ln.split(",") for ln in apps.splitlines() if ln.strip() and int(ln.split(",")[0]) not in own]
                u, mem = (float(x) for x in util.split(","))
                out[lb] = {"util_pct": u, "mem_used_mib": mem, "others_mib": sum(float(x[1]) for x in others), "others": [x[0].strip() for x in others]}
            except Exception as exc:  # noqa: BLE001
                out[lb] = {"error": repr(exc)}
        return out

    def start_node(self, lb, cold_start=False, tag=""):
        cmd = self.node_cmd(lb, cold_start=cold_start)
        if self.a.dry_run and not self.a.launch:   # local protocol test: start the dry-run node here
            import subprocess

            nd = self.node_spec[lb]
            cmd = [sys.executable] + cmd[1:] + ["--bind", nd["host"], "--dry_run"] + self.a.dry_node_args.split()
            logp = REPO_ROOT / f"results/evaluation/{self.a.experiment}/_launch_logs/node_{lb}_{tag}.log"; logp.parent.mkdir(parents=True, exist_ok=True)
            pr = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=open(logp, "w"), stderr=subprocess.STDOUT)
            self.agent_pids[lb] = (None, pr)
            return pr.pid
        pid = self.agent(lb).run(cmd, f"results/evaluation/{self.a.experiment}/_launch_logs/node_{lb}_{tag}.log", env={"PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
        self.agent_pids[lb] = (self.agent(lb), pid)
        return pid

    def stop_node(self, lb, pid):
        nc = self.nodes.pop(lb, None)
        if nc is not None:
            try:
                send_msg(nc.sock, "SHUTDOWN", {}, b"", None)
            except OSError:
                pass
        ag, h = self.agent_pids.get(lb, (None, None))
        if ag is None and h is not None:
            h.wait(timeout=120)
        elif ag is not None:
            r = ag.wait(pid, timeout=180)
            if r.get("timed_out"):
                ag.call(op="kill", pid=pid)

    def shutdown(self):
        for nc in self.nodes.values():
            try:
                send_msg(nc.sock, "SHUTDOWN", {}, b"", None)
            except OSError:
                pass
        if self.net is not None:
            self.net.shutdown()


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
    # D0 (shared planner integration)
    ap.add_argument("--path", type=str, default="", help="explicit owner sequence, e.g. A,C (overrides --hops); no revisits")
    ap.add_argument("--caps", type=str, default="", help="per-node cap overrides in Mbps, e.g. 'C:out=62.5'")
    ap.add_argument("--cap_events", type=str, default="", help="'t=20:C:out=62.5' or 'D>=0.5:C:out=62.5' (planners are not told)")
    ap.add_argument("--dyn_period", type=float, default=0.5); ap.add_argument("--dyn_window", type=float, default=2.0)
    ap.add_argument("--dyn_warmup", type=float, default=2.0); ap.add_argument("--dyn_eps", type=float, default=2.0)
    ap.add_argument("--dyn_rel", type=float, default=0.10); ap.add_argument("--dyn_ctrl", type=float, default=0.3)
    ap.add_argument("--prepos", type=str, default="", help="placement policy before the move (none, oracle, top1, greedy, proportional, coverage); needs --path A,<dest>")
    ap.add_argument("--probs", type=str, default="0.6,0.3,0.1", help="predicted probabilities for B, C, D")
    ap.add_argument("--lookahead", type=float, default=10.0)
    ap.add_argument("--budget", type=float, default=1.0)
    # Experiment D
    ap.add_argument("--cold_dest", action="store_true", help="OTTER cold destination (scenario A sensitivity): start node B after the trigger")
    ap.add_argument("--cold_tail_calls", type=int, default=60, help="cold restart: calls to keep generating at the final owner after its first output")
    ap.add_argument("--hybrid_net", type=int, default=0, help="scenario E: number of network-level restoration sessions next to the GPU session")
    ap.add_argument("--net_ctl_port", type=int, default=29831); ap.add_argument("--net_data_port", type=int, default=29832)
    ap.add_argument("--net_nodes", type=str, default="", help="scenario E: restore-node addresses A=host:ctl:data,... (default: the GPU hosts on --net_ctl_port/--net_data_port)")
    ap.add_argument("--net_grace_s", type=float, default=120.0, help="scenario E: after the GPU session's end condition, wait at most this long for the network sessions")
    ap.add_argument("--dry_node_args", type=str, default="--dry_sink_mb 64 --dry_service_s 0.2", help="dry run: arguments for a node this orchestrator starts itself (--cold_dest)")
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
                        path = [x for x in a.path.split(",") if x] or None
                        pp = None
                        if a.prepos:
                            assert path and len(path) == 2, "--prepos needs --path A,<dest>"
                            pp = {"policy": a.prepos, "probs": [float(x) for x in a.probs.split(",")], "L": a.lookahead, "b": a.budget, "dest": path[1], "tau": 7.5}
                        r = Run(o, pol, a.bw, tm, rho, rep, hops=a.hops, path=path, prepos=pp)
                        results.append(r.execute())
            (EVAL_ROOT / a.experiment).mkdir(parents=True, exist_ok=True)
    finally:
        if not a.keep_nodes:
            o.shutdown()
    print(f"[orch] done: {len(results)} runs under results/evaluation/{a.experiment}/")


if __name__ == "__main__":
    main()
