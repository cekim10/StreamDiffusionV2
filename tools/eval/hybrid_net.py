#!/usr/bin/env python3
"""Experiment D scenario E (hybrid GPU/network contention): network-level restoration sessions that run next to one GPU
generation session (tools/eval/mobility_orchestrate.py --hybrid_net N).

The network sessions are the validated Scenario B sessions of tools/eval/restore_orchestrate.py (its Run class, used
unchanged: planning, event handling, event-driven re-planning, accounting) on tools/eval/restore_node.py processes (no
GPU, no model; separate ports on the same four hosts). Only two things differ from a stand-alone restore run:
  - rate allocation: every flow of every session (the GPU session's and the network sessions') is allocated in ONE
    max-min computation over the same per-node caps, so the source A's egress is really shared;
  - schedule: every network session starts at B at the GPU session's first move and moves with it (B -> C -> D), at the
    same instants.
Policy per network session = the GPU session's: restart (M1 only), reuse_fixed (= GPU split, M1 + M2), reuse_aware_in,
reuse_dyn (OTTER event-driven). Results go to <GPU run dir>/net/<restore run id>/ (sessions.csv, flows.csv,
summary.json, node_*/network.csv) and are reported separately from the GPU session.
"""

from __future__ import annotations

import queue
import time
from datetime import datetime
from types import SimpleNamespace

from agents import connect_all, parse_hosts  # noqa: E402
from proto_handoff import send_msg  # noqa: E402
from restore_orchestrate import EDGES as NET_EDGES  # noqa: E402
from restore_orchestrate import Run as RestoreRun  # noqa: E402

NET_POLICY = {"restart": "restart", "split": "reuse_fixed", "reuse_aware_in": "reuse_aware_in", "reuse_dyn": "reuse_dyn"}


class NetOrch:
    """Restore nodes on the four hosts (control/data ports separate from the GPU nodes)."""

    def __init__(self, a, node_spec_gpu):
        self.a = a
        self.node_spec = {lb: {"host": v["host"], "ctl": a.net_ctl_port, "data": a.net_data_port} for lb, v in node_spec_gpu.items()}
        for item in (a.net_nodes or "").split(","):   # explicit host:ctl:data per label (loopback tests)
            if item:
                lb, hp = item.split("="); h, c, d = hp.split(":")
                self.node_spec[lb] = {"host": h, "ctl": int(c), "data": int(d)}
        self.events: queue.Queue = queue.Queue()
        self.nodes = {}

    def launch(self):
        agents = connect_all(parse_hosts(self.a.agent_hosts), ["A"] + NET_EDGES)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for lb in ["A"] + NET_EDGES:   # leftover restore nodes hold the ports
            agents[lb].exec(["pkill", "-f", f"tools/eval/restore_node.py --label {lb} --ctl_port {self.node_spec[lb]['ctl']}"])
        time.sleep(1.0)
        for lb in ["A"] + NET_EDGES:
            nd = self.node_spec[lb]
            cmd = [self.a.py, "tools/eval/restore_node.py", "--label", lb, "--ctl_port", str(nd["ctl"]), "--data_port", str(nd["data"]), "--mss", str(self.a.mss or 0)]
            if self.a.iface:
                cmd += ["--iface", self.a.iface]
            pid = agents[lb].run(cmd, f"results/evaluation/{self.a.experiment}/_launch_logs/net_node_{lb}_{stamp}.log")
            print(f"[orch] launched restore node {lb} on {nd['host']} (pid {pid})", flush=True)

    def connect(self):
        from mobility_orchestrate import NodeConn

        for lb in ["A"] + NET_EDGES:
            nd = self.node_spec[lb]
            self.nodes[lb] = NodeConn(lb, nd["host"], nd["ctl"], self.a.mss, self.events, timeout=120)
            print(f"[orch] restore node {lb} = {self.nodes[lb].hello.get('host')} commit {self.nodes[lb].hello.get('commit', '?')[:7]}", flush=True)

    def shutdown(self):
        for nc in self.nodes.values():
            try:
                send_msg(nc.sock, "SHUTDOWN", {}, b"", None)
            except OSError:
                pass


class NetSessions(RestoreRun):
    def __init__(self, gpu_run, net_orch: NetOrch, n_sess: int):
        ga = gpu_run.a
        rho = gpu_run.rho or 1.0
        net_orch.a = SimpleNamespace(
            experiment=f"{ga.experiment}/{gpu_run.run_id}/net", ts=gpu_run.tm * rho, cap_mbps=gpu_run.bw, holder_mbps=0.0, source_mbps=0.0, in_mbps=0.0,
            caps=ga.caps, cap_events="", dyn_period=ga.dyn_period, dyn_window=ga.dyn_window, dyn_warmup=ga.dyn_warmup, dyn_eps=ga.dyn_eps,
            dyn_rel=ga.dyn_rel, dyn_ctrl=ga.dyn_ctrl, frag_bytes=ga.frag_bytes, sink_bytes=None, others_start=0.0, mss=ga.mss, iface=ga.iface,
            agent_hosts=ga.agent_hosts, py=ga.py, net_ctl_port=ga.net_ctl_port, net_data_port=ga.net_data_port, net_nodes=ga.net_nodes)
        super().__init__(net_orch, NET_POLICY[gpu_run.policy], n_sess, len(gpu_run.edges) - 1, rho, gpu_run.rep)
        self.gpu = gpu_run
        self.caps = gpu_run.caps            # one emulated network: the same per-node caps object as the GPU session
        self.known_caps = dict(self.caps)
        self.caps0 = dict(self.caps)
        for sid in self.sids:               # every network session follows the GPU session: B first, then C, D
            self.owner[sid] = gpu_run.edges[1]; self.history[sid] = [gpu_run.edges[1]]
        self.stop_reason = None

    def realloc(self):
        return self.gpu.joint_realloc()

    def tuples(self):
        return [(f["id"], f["src"], f["dst"]) for f in self.flows.values() if f["active"] or f.get("draining")]

    def prepare(self, sink_bytes: int):
        self.a.sink_bytes = sink_bytes
        for lb in ["A"] + NET_EDGES:
            self.node(lb).call("RUN_BEGIN", run_rel=self.rel_dir)
        r = self.node("A").call("SOURCE_SETUP", sessions=self.sids, sink_bytes=sink_bytes, frag_bytes=self.a.frag_bytes, timeout=1800)
        man = r["manifests"]
        self.lens = man[self.sids[0]]["lens"]; self.flen = self.a.frag_bytes
        for e in NET_EDGES:
            self.node(e).call("MANIFESTS", manifests=man, timeout=600)
        for sid in self.sids:
            self.held[sid]["A"] = set(range(self.nfr()))
        while not self.o.events.empty():
            self.o.events.get()

    def start(self, t0: float):
        self.t0 = t0; self.ev.set_ref(t0)
        self.ev.log("start", t0, policy=self.policy, N=self.N, hybrid_with=self.gpu.run_id, owner=self.gpu.edges[1])
        with self.lock:
            for sid in self.sids:
                self.owner_since[sid] = t0; self.restored_now[sid] = False; self.move_t[sid] = t0
                self.plan(sid, "start")

    def move_all(self, to: str):
        with self.lock:
            for sid in self.sids:
                self.move(sid, to)

    def pump(self, now: float):
        with self.lock:
            self.tick(now)
        while True:
            try:
                m = self.o.events.get_nowait()
            except queue.Empty:
                return
            self.handle(m)

    def all_restored_at(self, edge: str) -> bool:
        return all(self.restored[s] and self.restored[s][-1][1] == edge and self.owner[s] == edge for s in self.sids)

    def end(self, reason: str):
        self.stop_reason = reason
        for fl in list(self.flows.values()):
            if fl["active"]:
                fl["active"] = False; self.node(fl["src"]).cast("FLOW_CANCEL", flow_id=fl["id"])
        time.sleep(1.0)
        while not self.o.events.empty():
            self.handle(self.o.events.get())
        ends = {lb: self.node(lb).call("RUN_END", timeout=300) for lb in ["A"] + NET_EDGES}
        for lb, e in ends.items():
            if e.get("network_csv"):
                (self.dir / f"node_{lb}").mkdir(exist_ok=True)
                (self.dir / f"node_{lb}" / "network.csv").write_text(e["network_csv"])
        return self.finish(ends, time.time())
