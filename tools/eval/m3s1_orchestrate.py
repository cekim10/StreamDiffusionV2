#!/usr/bin/env python3
"""M3-S1: network-level validation of lineage-aware progress forwarding (osdi/m3s1/preregistration.md).

Runs the frozen M1 / M2 migration *schedule* on the network-level restoration harness (tools/eval/restore_node.py on
four hosts, no GPU): real TCP transfers of real sizes under the harness's per-node caps, with the generation-side
quantities (call period, Sink lineage, log rate, replay catch-up, readiness floor, switch, cancellation lag) taken
from the recorded M3-E0 runs and the recorded lineage tables (osdi/m3s0/events_<wl>.json). It extends
restore_orchestrate.Run: nodes, flows, rate allocation, event handling and validation are the Scenario B / Full E
machinery, unchanged.

Semantics (the M1 / M2 execution model, not the old fast-path model):
  - the user is at B from t0, moves to C at T_m and to D at 2 T_m (T_m = T_s / rho, T_s 14.05 s);
  - a migration (source -> user's edge) = base flow (the entries not lineage-valid at the destination + the metadata
    fragment; starts after the measured startup latency) + log flow (fragments fed at the measured bytes per call);
  - base complete -> readiness = max(base ready + logged calls x catch-up, t(c0 + W) + 0.6 s) -> first output after the
    measured switch time -> OWNERSHIP: the destination becomes the source of later migrations and serves the user
    locally; the old source keeps its (now frozen) Sink as a holder;
  - a move before readiness cancels the migration after the measured lag; the abandoned destination keeps its verified
    fragments (tagged with their snapshot call) - S0 never reuses them, S1-S3 forward them;
  - staging (S1-S3): holders (abandoned destinations, old sources) forward their lineage-valid fragments to the
    candidate(s) of the next move: S1 one candidate, S2 two candidates, S3 = S2 with the active migration's flows
    prioritized (staging gets the residual capacity). The source never stages. Staging to a node stops when a
    migration to it starts; its staged fragments count as valid at c0 iff their entry was not refreshed since their tag.
  - lineage validity: entry e tagged with snapshot call s is valid for a base at call c0 iff e was not refreshed in
    (s, c0] (lineage rule checked against block checksums, G0 of M3-S0). Shifts are metadata (not modelled as bytes).

    python tools/eval/m3s1_orchestrate.py --launch --workload dog --staging none,S1o,S1c,S2,S3 --orders fwd,rev --rhos 1 --reps 3
    python tools/eval/m3s1_orchestrate.py --nodes "A=127.0.0.1:29851:29852,..." --mss 0 --cap_mbps 100 --scale 13.5 --workload dog --staging S3 ...   # loopback
"""

from __future__ import annotations

import argparse
import csv
import json
import queue
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
from common import EVAL_ROOT, git_commit  # noqa: E402
from restore_orchestrate import EDGES, Orch, Run  # noqa: E402
from restore_planner import maxmin  # noqa: E402

NODES = ["A"] + EDGES
PATH = ["A", "B", "C", "D"]
ENTRY_BYTES = 9_584_640
META_BYTES = 2_401_488
N_ENTRIES = 180
W = 12
READY_EXTRA_S = 0.6
BASE_READY_EXTRA_S = 0.4
E0 = ROOT / "results/evaluation/osdi/m3e0/e0_report.json"
S0DIR = ROOT / "results/evaluation/osdi/m3s0"
WL_TABLE = {"dog": "events_dog.json", "bfly": "events_bfly.json"}
MIN_RATE = 1e3   # a starved flow is paced at 1 kbps (the node treats rate 0 as unshaped)


def consts_from_e0(wl: str, rho: float) -> dict:
    """Generation-side constants of the matching M3-E0 run (measured)."""
    name = f"{wl}_rho{int(rho)}" if rho in (1.0, 2.0) else f"{wl}_rho1"
    R = json.load(open(E0))["configs"][name]
    f = R["final"]; t = next(x for x in R["tasks"] if x["task"] == f["task"])
    lags = []
    for tk in R["tasks"]:
        if tk["outcome"] == "cancelled":
            mv = min((x["t"] for x in R["moves"] if x["t"] > tk["t_start"]), default=None)
            if mv is not None:
                lags.append(tk["t_end"] - mv)
    cal = json.load(open(S0DIR / "calibration.json"))
    return {"log_bytes_per_call": t["log_bytes"] / t["log_calls"], "catchup_per_call_s": f["replay_catchup_s"] / t["log_calls"],
            "switch_s": f["first_output_s"] - f["readiness_s"], "cancel_lag_s": sum(lags) / len(lags) if lags else 0.5, "snapshot_s": f["round_snapshot_s"],
            "h_startup_s": float(cal["h_s"]), "source_run": name}


class Lineage:
    def __init__(self, J: dict):
        self.rows, self.S = int(J["rows"]), int(J["sink_slots"])
        self.refresh = {int(c): {(li * self.rows + row) * self.S + slot for li, row, slot in v} for c, v in J["refresh"].items()}
        self.period = float(J["gen_s_median"])
        self.c_lo, self.c_hi = int(J["c_lo"]), int(J["c_hi"])

    def refreshed_in(self, s: int, t: int) -> set:
        out = set()
        for c in range(s + 1, t + 1):
            out |= self.refresh.get(c, set())
        return out


class M3S1Run(Run):
    def __init__(self, o, a, staging: str, order: str, rho: float, rep: int):
        self.staging, self.order, self.wl = staging, order, a.workload
        super().__init__(o, f"m3s1-{a.workload}-{staging}-{order}", 1, 2, rho, rep)
        self.k = consts_from_e0(a.workload, rho)
        self.lin = Lineage(json.load(open(S0DIR / WL_TABLE[a.workload])))
        self.scale = float(a.scale)
        self.entry_bytes = int(round(ENTRY_BYTES / self.scale)); self.meta_bytes = int(round(META_BYTES / self.scale))
        self.sink_bytes = N_ENTRIES * self.entry_bytes + self.meta_bytes
        self.log_frag = int(round((1 << 20) / self.scale))
        self.log_per_call = self.k["log_bytes_per_call"] / self.scale
        self.sids = ["s0", "lg"]
        self.restored_now["s0"] = False; self.owner_since["s0"] = 0.0
        for sid in ("lg",):
            self.held[sid] = {e: set() for e in NODES}; self.inflight[sid] = defaultdict(set); self.skipped[sid] = set()
            self.last_plan_t[sid] = 0.0; self.restored_now[sid] = False; self.history[sid] = ["A"]; self.owner[sid] = "A"
        self.tag = {n: {} for n in NODES}        # node -> {fragment: snapshot call}
        self.source, self.user, self.user_idx = "A", "B", 1
        self.mig = None; self.migs = []
        self.moves_log = []
        self.pending_cancel = None
        self.log_fid = 0
        self.next_log_feed = None
        self.remote_s = self.local_s = 0.0
        self.last_tick = None
        self.stage_flows = {}                    # (holder, cand) -> flow id
        self.staged_to = defaultdict(int); self.used_staged = defaultdict(int)
        self.base_bytes_by_mig = {}
        self.prio = staging == "S3"

    # ---------------- time / calls
    def call(self, t=None) -> int:
        return 30 + int(((time.time() if t is None else t) - self.t0) / self.lin.period)

    def t_call(self, c: int) -> float:
        return self.t0 + (c - 30) * self.lin.period

    def valid_at(self, node: str, c0: int) -> set:
        out = set()
        for fid, s in self.tag[node].items():
            if fid < N_ENTRIES and fid in self.held["s0"][node] and fid not in self.lin.refreshed_in(s, c0):
                out.add(fid)
        return out

    # ---------------- rate allocation: log flows demand-limited; S3 gives staging the residual
    def realloc(self):
        act = [f for f in self.flows.values() if f["active"] or f.get("draining")]
        caps = dict(self.caps)
        rates = {}
        logs = [f for f in act if f.get("kind") == "log"]
        for f in logs:   # the log's demand: its measured mean rate (bits/s)
            r = min(self.log_per_call * 8 / self.lin.period, caps[("out", f["src"])], caps[("in", f["dst"])])
            rates[f["id"]] = r; caps[("out", f["src"])] -= r; caps[("in", f["dst"])] -= r
        prim = [(f["id"], f["src"], f["dst"]) for f in act if f.get("kind") == "base"]
        stg = [(f["id"], f["src"], f["dst"]) for f in act if f.get("kind") == "stage"]
        if self.prio:
            r1 = maxmin(prim, caps)
            for fid, s, d in prim:
                caps[("out", s)] -= r1[fid]; caps[("in", d)] -= r1[fid]
            r2 = maxmin(stg, {k: max(0.0, v) for k, v in caps.items()})
            rates.update(r1); rates.update(r2)
        else:
            rates.update(maxmin(prim + stg, caps))
        for f in act:
            r = max(MIN_RATE, rates.get(f["id"], 0.0))
            if abs(r - f["rate"]) > 0.01 * max(1.0, f["rate"]):
                f["rate"] = r
                if f["started"]:
                    self.node(f["src"]).cast("FLOW_SET_RATE", flow_id=f["id"], rate_bps=r)
        return rates

    def start_kind(self, kind, sid, src, dst, fids, reason, tags=None, closed=True):
        """Run.start_flow with the flow's kind and fragment tags set BEFORE the rate allocation (the allocation is by kind)."""
        fids = list(fids)
        if not fids and closed:
            return None
        self.nflow += 1
        fid_ = f"f{self.nflow}_{sid}_{src}{dst}"
        fl = {"id": fid_, "sid": sid, "src": src, "dst": dst, "left": set(fids), "active": True, "rate": 0.0, "started": False, "t_start": time.time(), "t_end": None,
              "bytes": 0, "cancelled": False, "reason": reason, "n": len(fids), "kind": kind, "tags": tags or {}, "closed": closed, "order": fids}
        self.flows[fid_] = fl
        self.realloc()
        nd = self.o.node_spec[dst]
        self.node(src).cast("FLOW_START", flow_id=fid_, session=sid, dst=dst, dst_host=nd["host"], dst_port=nd["data"], frag_ids=fids, rate_bps=fl["rate"], closed=closed)
        fl["started"] = True
        self.ev.log("flow_start", flow=fid_, kind=kind, session=sid, src=src, dst=dst, n=len(fids), rate_bps=fl["rate"], reason=reason, closed=closed)
        return fl

    # ---------------- migration lifecycle
    def start_migration(self, dst: str):
        now = time.time()
        c0 = self.call(now + self.k["snapshot_s"])
        valid = self.valid_at(dst, c0) if self.staging != "none" else set()
        delta = [f for f in range(N_ENTRIES) if f not in valid] + [N_ENTRIES]   # + metadata
        self.used_staged[dst] += len(valid & {f for f in self.tag[dst] if self.tag[dst][f] is not None}) * self.entry_bytes
        for key in [k_ for k_ in self.stage_flows if k_[1] == dst]:   # staging to the destination stops
            fl = self.flows.get(self.stage_flows.pop(key))
            if fl and fl["active"]:
                self._cancel(fl, "destination is now migrating")
        m = {"id": len(self.migs) + 1, "src": self.source, "dst": dst, "t_start": now, "c0": c0, "valid": len(valid), "delta": len(delta) - 1,
             "base_bytes": (len(delta) - 1) * self.entry_bytes + self.meta_bytes, "t_base_start": now + self.k["snapshot_s"] + self.k["h_startup_s"],
             "base_started": False, "t_base_ready": None, "t_ready": None, "t_first_out": None, "outcome": "open", "delta_fids": delta, "log_sent": 0, "base_sent": 0}
        self.mig = m; self.migs.append(m)
        # the log is armed at task start (as _rlog_start): an open flow fed every call period
        m["log_flow"] = self.start_kind("log", "lg", self.source, dst, [], f"m{m['id']}: input log", closed=False)
        self.next_log_feed = now + self.lin.period
        self.ev.log("migration_start", now, id=m["id"], src=self.source, dst=dst, c0=c0, valid_entries=len(valid), delta_entries=len(delta) - 1, base_mb=round(m["base_bytes"] / 1e6, 1))

    def start_base(self, m):
        m["base_started"] = True
        m["base_flow"] = self.start_kind("base", "s0", m["src"], m["dst"], m["delta_fids"], f"m{m['id']}: base (delta {m['delta']} entries + meta)", tags={f: m["c0"] for f in m["delta_fids"]})
        self.ev.log("base_start", id=m["id"], fids=len(m["delta_fids"]))

    def feed_log(self, now):
        m = self.mig
        if m is None or m.get("log_flow") is None or not m["log_flow"]["active"]:
            return
        if self.next_log_feed is not None and now >= self.next_log_feed:
            self.next_log_feed += self.lin.period
            n = max(1, int(round(self.log_per_call / self.log_frag)))
            fids = list(range(self.log_fid, self.log_fid + n)); self.log_fid += n
            if self.log_fid > self.nlog:
                return
            fl = m["log_flow"]; fl["left"] |= set(fids); fl["n"] += n
            self.node(fl["src"]).cast("FLOW_ADD", flow_id=fl["id"], frag_ids=fids, closed=False)

    def _cancel(self, fl, why):
        fl["active"] = False; fl["cancelled"] = True; fl["t_end"] = time.time(); fl["draining"] = True
        self.node(fl["src"]).cast("FLOW_CANCEL", flow_id=fl["id"])
        self.ev.log("flow_cancel", flow=fl["id"], kind=fl.get("kind"), src=fl["src"], dst=fl["dst"], sent_mb=round(fl["bytes"] / 1e6, 1), why=why)

    def cancel_migration(self, why):
        m = self.mig
        if m is None:
            return
        m["outcome"] = "cancelled"; m["t_end"] = time.time()
        for key in ("base_flow", "log_flow"):
            fl = m.get(key)
            if fl and fl["active"]:
                self._cancel(fl, why)
        m["base_sent"] = (m.get("base_flow") or {}).get("bytes", 0); m["log_sent"] = (m.get("log_flow") or {}).get("bytes", 0)
        self.ev.log("migration_cancel", id=m["id"], dst=m["dst"], base_sent_mb=round(m["base_sent"] / 1e6, 1), log_sent_mb=round(m["log_sent"] / 1e6, 1))
        self.realloc()
        self.mig = None

    def complete_migration(self):
        m = self.mig
        old = self.source
        m["outcome"] = "completed"; m["t_end"] = time.time()
        m["base_sent"] = (m.get("base_flow") or {}).get("bytes", 0); m["log_sent"] = (m.get("log_flow") or {}).get("bytes", 0)
        fl = m.get("log_flow")
        if fl and fl["active"]:
            self._cancel(fl, "switchover")
        c_sw = self.call()
        self.source = m["dst"]
        self.held["s0"][old] = set(range(N_ENTRIES + 1)); self.tag[old] = {f: c_sw for f in range(N_ENTRIES + 1)}   # the old source's Sink is frozen at the switch
        self.ev.log("ownership", **{"from": old, "to": self.source, "call": c_sw})
        self.mig = None
        self.realloc()

    # ---------------- staging (holders -> candidates)
    def order_nodes(self):
        return NODES if self.order == "fwd" else list(reversed(NODES))

    def candidates(self):
        if self.staging == "none":
            return []
        if self.staging == "S1o":
            nxt = PATH[self.user_idx + 1] if self.user_idx + 1 < len(PATH) else None
            return [nxt] if nxt and nxt != self.source else []
        cands = [n for n in self.order_nodes() if n != self.user and n != self.source]
        return cands[:1] if self.staging == "S1c" else cands

    def holders(self):
        return [n for n in NODES if n != self.source and self.held["s0"][n]]

    def plan_staging(self, why):
        cands = self.candidates()
        if not cands:
            return
        now_c = self.call()
        for cand in cands:
            have = set(self.held["s0"][cand]) | self.claims("s0", cand)
            provs = [h for h in self.holders() if h != cand]
            count = {p: 0 for p in provs}
            assign = defaultdict(list)
            for f in range(N_ENTRIES):
                if f in have:
                    continue
                ok = [p for p in provs if f in self.held["s0"][p] and f in self.tag[p] and f not in self.lin.refreshed_in(self.tag[p][f], now_c)]
                if not ok:
                    continue
                p = min(ok, key=lambda h: (count[h], h)); count[p] += 1; assign[p].append(f)
            for p, fids in assign.items():
                fl = self.start_kind("stage", "s0", p, cand, fids, f"{self.staging}: {p} forwards lineage-valid entries to candidate {cand}", tags={f: self.tag[p][f] for f in fids})
                if fl is not None:
                    self.stage_flows[(p, cand)] = fl["id"]
        self.ev.log("staging_plan", why=why, candidates=cands, holders=self.holders())

    # ---------------- events
    def handle(self, m):
        k = m.get("kind")
        if k == "FRAG_RECV" and m.get("ok") and not m.get("dup"):
            with self.lock:
                fl = self.flows.get(m["flow_id"])
                sid, f, dst = m["session"], int(m["fragment_id"]), m["label"]
                if fl is not None and sid == "s0":
                    self.tag[dst][f] = fl.get("tags", {}).get(f, self.call())
                    if fl.get("kind") == "stage":
                        self.staged_to[dst] += m["bytes"]
        if k == "FLOW_DONE":
            with self.lock:
                fl = self.flows.get(m["flow_id"])
                if fl and fl.get("kind") == "stage":
                    for key in [k_ for k_, v in self.stage_flows.items() if v == fl["id"]]:
                        self.stage_flows.pop(key, None)
        super().handle(m)
        if k == "FRAG_RECV" and m.get("ok"):
            with self.lock:
                mg = self.mig
                if mg is not None and mg["dst"] == m["label"] and m["session"] == "s0" and mg["t_base_ready"] is None and \
                        all(f in self.held["s0"][mg["dst"]] for f in mg["delta_fids"]):
                    t = self.node(m["label"]).to_orch(m["t_end"])
                    mg["t_base_ready"] = t + BASE_READY_EXTRA_S
                    logged = max(0, self.call(mg["t_base_ready"]) - mg["c0"])
                    mg["t_ready"] = max(mg["t_base_ready"] + logged * self.k["catchup_per_call_s"], self.t_call(mg["c0"] + W) + READY_EXTRA_S)
                    mg["t_first_out"] = mg["t_ready"] + self.k["switch_s"]
                    self.ev.log("base_ready", mg["t_base_ready"], id=mg["id"], t_ready_rel=round(self.rel(mg["t_ready"]), 2), t_first_out_rel=round(self.rel(mg["t_first_out"]), 2), logged_calls=logged)
                if m["session"] == "s0" and m.get("dup") is False:
                    fl = self.flows.get(m["flow_id"])
                    if fl is not None and fl.get("kind") == "stage" and not fl["left"]:
                        pass

    def plan(self, sid, reason):
        return   # no Run.plan: migrations and staging are driven by this class

    # ---------------- run
    def execute(self):
        a = self.a
        print(f"[orch] === {self.run_id} (T_m {self.tm:.2f} s, {self.wl}, staging {self.staging}, order {self.order}) ===", flush=True)
        for lb in NODES:
            self.node(lb).call("RUN_BEGIN", run_rel=self.rel_dir)
        r = self.node("A").call("SOURCE_SETUP", sessions=["s0"], sink_bytes=self.sink_bytes, frag_bytes=self.entry_bytes, timeout=1800)
        man = r["manifests"]
        self.lens = man["s0"]["lens"]; self.flen = self.entry_bytes
        assert len(self.lens) == N_ENTRIES + 1, len(self.lens)
        # the log session: every node can send it (a new source after an ownership change feeds the log)
        self.nlog = int(self.log_per_call / self.log_frag + 1) * 400
        lg_bytes = self.nlog * self.log_frag
        for lb in NODES:
            rl = self.node(lb).call("SOURCE_SETUP", sessions=["lg"], sink_bytes=lg_bytes, frag_bytes=self.log_frag, timeout=1800)
        man["lg"] = rl["manifests"]["lg"]
        for e in EDGES:
            self.node(e).call("MANIFESTS", manifests={"s0": man["s0"]}, timeout=600)
        self.held["s0"]["A"] = set(range(N_ENTRIES + 1)); self.tag["A"] = {f: 30 for f in range(N_ENTRIES + 1)}
        while not self.o.events.empty():
            self.o.events.get()
        self.t0 = time.time(); self.ev.set_ref(self.t0)
        self.ev.log("start", self.t0, policy=self.policy, workload=self.wl, staging=self.staging, order=self.order, rho=self.rho, tm=self.tm, scale=self.scale,
                    sink_bytes=self.sink_bytes, entry_bytes=self.entry_bytes, consts=self.k, period=self.lin.period)
        with self.lock:
            self.start_migration("B")
            self.plan_staging("t0")
        n_moves = 2; next_move = 1
        deadline = self.t0 + a.max_run_s
        self.last_tick = self.t0
        final_done_t = None
        while True:
            now = time.time()
            with self.lock:
                if next_move <= n_moves and now >= self.t0 + next_move * self.tm:
                    self.user_idx = next_move + 1; self.user = PATH[self.user_idx]
                    self.moves_log.append((now, self.user)); self.ev.log("move", now, to=self.user, serving=self.source)
                    if self.mig is not None and (self.mig["t_ready"] is None or now < self.mig["t_ready"]):
                        self.pending_cancel = now + self.k["cancel_lag_s"]
                    if self.mig is None and self.user != self.source:
                        self.start_migration(self.user)
                    self.plan_staging("move")
                    next_move += 1
                if self.pending_cancel is not None and now >= self.pending_cancel:
                    self.pending_cancel = None
                    if self.mig is not None and not (self.mig["t_ready"] is not None and now >= self.mig["t_ready"]):
                        self.cancel_migration("user moved")
                        if self.user != self.source:
                            self.start_migration(self.user)
                        self.plan_staging("cancel")
                mg = self.mig
                if mg is not None and not mg["base_started"] and now >= mg["t_base_start"]:
                    self.start_base(mg)
                self.feed_log(now)
                if mg is not None and mg["t_first_out"] is not None and now >= mg["t_first_out"]:
                    self.complete_migration()
                    self.plan_staging("ownership")
                    if next_move > n_moves and self.source == self.user:
                        final_done_t = now
                self.tick(now)
                dt = now - self.last_tick; self.last_tick = now
                if self.source == self.user:
                    self.local_s += dt
                else:
                    self.remote_s += dt
            try:
                msg = self.o.events.get(timeout=0.02)
                self.handle(msg)
            except queue.Empty:
                pass
            if final_done_t is not None and now >= final_done_t + 2.0:
                self.stop_reason = "final migration completed"; break
            if now >= deadline:
                self.stop_reason = "deadline"; break
        for fl in list(self.flows.values()):
            if fl["active"]:
                fl["active"] = False; self.node(fl["src"]).cast("FLOW_CANCEL", flow_id=fl["id"])
        time.sleep(1.0)
        while not self.o.events.empty():
            self.handle(self.o.events.get())
        ends = {lb: self.node(lb).call("RUN_END", timeout=300) for lb in NODES}
        for lb, e in ends.items():
            if e.get("network_csv"):
                (self.dir / f"node_{lb}").mkdir(exist_ok=True)
                (self.dir / f"node_{lb}" / "network.csv").write_text(e["network_csv"])
        return self.finish_m3s1(ends)

    def finish_m3s1(self, ends):
        S = self.sink_bytes
        by = defaultdict(int)
        for fl in self.flows.values():
            by[(fl.get("kind", "?"), fl["src"], fl["dst"])] += fl["bytes"]
        tot = sum(by.values())
        disc = sum(m.get("base_sent", 0) + m.get("log_sent", 0) for m in self.migs if m["outcome"] == "cancelled")
        staged = sum(self.staged_to.values()); wasted = sum(max(0, self.staged_to[n] - self.used_staged[n]) for n in NODES)
        comp = [m for m in self.migs if m["outcome"] == "completed"]
        fin = comp[-1] if comp else None
        nic = {}
        for lb, e in ends.items():
            rows = [l.split(",") for l in (e.get("network_csv") or "").splitlines()[1:] if l.strip()]
            vals = [float(r[4]) for r in rows if r[4] and float(r[0]) >= self.t0]
            vtx = [float(r[5]) for r in rows if r[5] and float(r[0]) >= self.t0]
            nic[lb] = {"rx_peak": max(vals) if vals else None, "tx_peak": max(vtx) if vtx else None}
        migs = []
        for m in self.migs:
            migs.append({k: (round(self.rel(v), 3) if k.startswith("t_") and isinstance(v, float) else v) for k, v in m.items() if k not in ("base_flow", "log_flow", "delta_fids")})
            migs[-1]["readiness_s"] = (m["t_ready"] - m["t_start"]) if m.get("t_ready") else None
            migs[-1]["first_output_s"] = (m["t_first_out"] - m["t_start"]) if m.get("t_first_out") else None
        summary = {
            "run_id": self.run_id, "workload": self.wl, "staging": self.staging, "order": self.order, "rho": self.rho, "tm_s": self.tm, "rep": self.rep, "scale": self.scale,
            "sink_bytes": S, "entry_bytes": self.entry_bytes, "consts": self.k, "stop_reason": self.stop_reason,
            "remote_s": round(self.remote_s, 3), "local_s": round(self.local_s, 3), "moves": [(round(self.rel(t), 3), to) for t, to in self.moves_log],
            "migrations": migs, "n_cancelled": sum(1 for m in self.migs if m["outcome"] == "cancelled"), "n_completed": len(comp),
            "final_completed": bool(fin) and fin["dst"] == PATH[-1],
            "bytes": {"total": tot, "discarded": disc, "staged": staged, "wasted_staged": wasted, "source_bytes_final_base": fin["base_sent"] if fin else None,
                      "by_kind_link": {f"{k}:{s}>{d}": v for (k, s, d), v in sorted(by.items())}},
            "sinks": {"total": tot / S, "discarded": disc / S, "staged": staged / S, "wasted_staged": wasted / S},
            "nic": nic, "hosts": {lb: self.node(lb).hello.get("host") for lb in NODES}, "node_commits": {lb: self.node(lb).hello.get("commit") for lb in NODES},
            "paced_egress_worst_10s_mbps": {lb: e.get("egress_worst_10s_mbps") for lb, e in ends.items()},
            # the `lg` session is set up as held on every node (any node may feed the log after an ownership change), so its receipts are
            # "duplicates" by the node's rule: the duplicate check is over the Sink session only
            "validation": {"all_fragments_verified": all(ok for *_, ok, dup_ in self.recv), "no_duplicates": not any(dup_ for t, s_, d, sid, f, b, ok, dup_ in self.recv if sid == "s0"),
                           "final_completed": bool(fin) and fin["dst"] == PATH[-1], "stop_reason_ok": self.stop_reason == "final migration completed",
                           "four_hosts_distinct": len({self.node(lb).hello.get("host") for lb in NODES}) == 4,
                           "nodes_same_commit": len({self.node(lb).hello.get("commit") for lb in NODES} | {git_commit().split()[0]}) == 1,
                           "nic_within_cap": all(v["rx_peak"] is None or v["rx_peak"] <= 1.15 * self.caps[("in", lb)] / 1e6 for lb, v in nic.items()),
                           "paced_egress_within_cap": all((e.get("egress_worst_10s_mbps") or 0) <= 1.05 * self.caps[("out", lb)] / 1e6 for lb, e in ends.items())},
        }
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
        (self.dir / "config.json").write_text(json.dumps({"args": vars(self.a), "policy": self.policy, "nodes": self.o.node_spec}, indent=1, default=str))
        with open(self.dir / "flows.csv", "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["flow", "kind", "src", "dst", "n", "bytes", "t_start_rel", "t_end_rel", "reason"])
            for fl in self.flows.values():
                w.writerow([fl["id"], fl.get("kind"), fl["src"], fl["dst"], fl["n"], fl["bytes"], f"{self.rel(fl['t_start']):.3f}", "" if fl["t_end"] is None else f"{self.rel(fl['t_end']):.3f}", fl["reason"]])
        print(f"[orch] {self.wl} {self.staging}/{self.order} rho {self.rho:g}: remote {self.remote_s:.1f} s, local {self.local_s:.1f} s, cancelled {summary['n_cancelled']}, "
              f"final {summary['final_completed']} ({fin and round(fin['t_ready'] - fin['t_start'], 1)} s ready, valid {fin and fin['valid']}/180), discarded {disc / S:.2f} S, staged {staged / S:.2f} S, "
              f"wasted {wasted / S:.2f} S, total {tot / S:.2f} S, valid {all(summary['validation'].values())}", flush=True)
        return summary


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nodes", default=None); p.add_argument("--ctl_port", type=int, default=29831); p.add_argument("--data_port", type=int, default=29832)
    p.add_argument("--experiment", default="expM3S1")
    p.add_argument("--workload", choices=("dog", "bfly"), required=True)
    p.add_argument("--staging", default="none,S1o,S1c,S2,S3"); p.add_argument("--orders", default="fwd,rev")
    p.add_argument("--rhos", default="1"); p.add_argument("--reps", type=int, default=3)
    p.add_argument("--ts", type=float, default=14.05); p.add_argument("--cap_mbps", type=float, default=1000.0); p.add_argument("--caps", default="")
    p.add_argument("--scale", type=float, default=1.0, help="divide every byte quantity by this (loopback plumbing tests)")
    p.add_argument("--max_run_s", type=float, default=240.0)
    p.add_argument("--mss", type=int, default=1400); p.add_argument("--iface", default=None); p.add_argument("--launch", action="store_true")
    p.add_argument("--no_resume", action="store_true"); p.add_argument("--agent_hosts", default=None); p.add_argument("--py", default="auto")
    # Run.__init__ reads these
    p.add_argument("--holder_mbps", type=float, default=0.0); p.add_argument("--source_mbps", type=float, default=0.0); p.add_argument("--in_mbps", type=float, default=0.0)
    p.add_argument("--cap_events", default=""); p.add_argument("--sink_bytes", type=int, default=0); p.add_argument("--frag_bytes", type=int, default=0)
    p.add_argument("--dyn_period", type=float, default=0.5); p.add_argument("--dyn_window", type=float, default=2.0); p.add_argument("--dyn_warmup", type=float, default=2.0)
    p.add_argument("--dyn_eps", type=float, default=2.0); p.add_argument("--dyn_rel", type=float, default=0.10); p.add_argument("--dyn_ctrl", type=float, default=0.3)
    p.add_argument("--others_start", type=float, default=0.0)
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
            for rho in [float(x) for x in a.rhos.split(",")]:
                for stg in a.staging.split(","):
                    for order in (a.orders.split(",") if stg not in ("none", "S1o") else ["fwd"]):
                        pol = f"m3s1-{a.workload}-{stg}-{order}"
                        done = [d for d in root.glob(f"policy={pol}_N=1_moves=2_rho={rho:g}_rep={rep}_*") if (d / "summary.json").exists()]
                        if done and not a.no_resume:
                            print(f"[orch] skip (done): {done[0].name}", flush=True); continue
                        out.append(M3S1Run(o, a, stg, order, rho, rep).execute())
    finally:
        o.shutdown()
    print(f"[orch] done: {len(out)} runs")


if __name__ == "__main__":
    main()
