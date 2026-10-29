#!/usr/bin/env python3
"""M3-S0 offline staging simulator (osdi/m3s0/preregistration.md). Fluid-flow model of the frozen M1 / M2 migration
path under repeated mobility, with lineage-valid staging of Sink entries at candidate destinations before the move.

Everything the model knows is measured or recorded:
  - the Sink lineage table of the workload (tools/eval/m3s0_dump_events.py): per call, the refreshed entries and the
    shift events; the lineage rule (an entry held with snapshot call s is valid for a base at call t iff it was not
    refreshed in (s, t]; shifts are metadata) was checked against per-block checksums when the table was dumped;
  - the M3-E0 run constants (osdi/m3e0/e0_report.json): move times, log bytes per call, replay catch-up per logged
    call, switch time, cancellation lag, snapshot and base-ready overheads; E9 / E10: the Replay-W readiness floor;
  - per-node caps (1 Gbps egress and ingress, shared max-min as in the harness) with one link-efficiency factor.

Causality: a staging decision at time t uses only the user's edge, the source, the holders and the candidate set known
at t; 'oracle' knowledge names the next edge, 'causal' stages uniformly to every node that is neither the user's edge
nor the source. Ownership moves when a migration's first output happens: the destination becomes the source of later
migrations and the old source becomes a holder (snapshot = the switch call). The source's egress is shared by the live
log, the active migration's base and every staging flow.

    python tools/eval/m3s0_sim.py --all                       # the matrix of the preregistration, report json + md
    python tools/eval/m3s0_sim.py --selftest                  # synthetic lineage table, structural checks
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/evaluation/osdi/m3s0"
E0 = ROOT / "results/evaluation/osdi/m3e0/e0_report.json"
NODES = ["A", "B", "C", "D"]
PATH = ["A", "B", "C", "D"]
META_BYTES = 2_401_488            # full base 1,727,636,688 B minus 180 entries of 9,584,640 B
CAP_BPS = 1e9
ETA = 0.88                        # link efficiency of the paced flows (calibration gate: S0 base time within 15 %)
W = 12                            # Replay-W (frozen M1)
READY_EXTRA_S = 0.6               # readiness beyond the call c0 + W (E9: 8.74 s; E10 butterfly: 8.97 s at c0 = 123, W = 12)
BASE_READY_EXTRA_S = 0.4          # base flow end -> base ready (M3-E0: 0.40-0.44 s)
DT = 0.02
T_S = 14.05
CONFIGS = {"dog_rho1": ("dog", 1), "dog_rho2": ("dog", 2), "bfly_rho1": ("bfly", 1), "bfly_rho2": ("bfly", 2)}
GRAPHS = ("none", "star", "line", "tree", "butterfly", "adaptive", "floor")
KNOWLEDGE = ("oracle", "causal")


# ------------------------------------------------------------------------------------------------ lineage table
class Lineage:
    def __init__(self, J: dict):
        self.n = int(J["n_entries"]); self.S = int(J["sink_slots"]); self.rows = int(J["rows"]); self.L = int(J["layers"])
        self.entry_bytes = 2 * int(J["block_bytes"])
        self.refresh = {int(c): {self.idx(*x) for x in v} for c, v in J["refresh"].items()}
        self.calls = sorted(self.refresh)
        self.period = float(J.get("gen_s_median") or 0.615)

    def idx(self, li, row, slot):
        return (li * self.rows + row) * self.S + slot

    def refreshed_in(self, s: int, t: int) -> set:
        """entries refreshed in calls (s, t] (calls outside the table count as no refresh)"""
        out = set()
        for c in range(s + 1, t + 1):
            out |= self.refresh.get(c, set())
        return out

    def valid(self, held: dict, t: int) -> set:
        """entries of `held` {entry: snapshot call} that are lineage-valid for a base at call t"""
        ok = set()
        for e, s in held.items():
            if s >= t or e not in self.refreshed_in(s, t):
                ok.add(e)
        return ok


def synthetic_lineage(n_entries=180, c_lo=25, c_hi=160, rate=0.1, seed=1) -> dict:
    """self-test table: `rate` refreshed entries per call on average, realignment shifts at 48 / 49, 93 / 94, 138 / 139"""
    import random
    rnd = random.Random(seed)
    refresh, shifts = {}, {}
    L, rows, S = 30, 2, 3
    for c in range(c_lo, c_hi + 1):
        k = sum(1 for _ in range(n_entries) if rnd.random() < rate / n_entries * 1.0) if rate < 1 else int(rate)
        ents = rnd.sample(range(n_entries), min(n_entries, max(0, k) if rate >= 1 else (1 if rnd.random() < rate else 0)))
        refresh[c] = [[e // (rows * S), (e // S) % rows, e % S] for e in ents]
        shifts[c] = [[li, 0 if c % 2 == 0 else 1, s, 1] for li in range(L) for s in range(S)] if c in (48, 49, 93, 94, 138, 139) else []
    return {"n_entries": n_entries, "sink_slots": S, "rows": rows, "layers": L, "block_bytes": 4_792_320, "gen_s_median": 0.615, "refresh": refresh, "shifts": shifts}


# ------------------------------------------------------------------------------------------------ bandwidth
def water_fill(flows, caps, demand):
    """flows: [(id, src, dst)]; caps: {("out"|"in", node): bps}; demand: {id: max bps or None}. Max-min fair rates under
    per-node caps, demand-limited flows frozen at their demand."""
    rate = {f: 0.0 for f, _, _ in flows}
    resid = dict(caps)
    active = {f for f, _, _ in flows}
    while active:
        load = defaultdict(int)
        for f, s, d in flows:
            if f in active:
                load[("out", s)] += 1; load[("in", d)] += 1
        inc = min(resid[k] / n for k, n in load.items())
        for f in active:
            if demand.get(f) is not None:
                inc = min(inc, max(0.0, demand[f] - rate[f]))
        if inc <= 1e-9:
            # every remaining flow is at a saturated node or at its demand
            for f, s, d in flows:
                if f in active and (resid[("out", s)] <= 1e-6 or resid[("in", d)] <= 1e-6 or (demand.get(f) is not None and rate[f] >= demand[f] - 1e-6)):
                    active.discard(f)
            if active and inc <= 1e-9:
                break
            continue
        for f, s, d in flows:
            if f in active:
                rate[f] += inc; resid[("out", s)] -= inc; resid[("in", d)] -= inc
        for f, s, d in flows:
            if f in active and (resid[("out", s)] <= 1e-6 or resid[("in", d)] <= 1e-6 or (demand.get(f) is not None and rate[f] >= demand[f] - 1e-6)):
                active.discard(f)
    return rate


# ------------------------------------------------------------------------------------------------ simulator
class Sim:
    def __init__(self, lin: Lineage, consts: dict, rho: float, graph: str, knowledge: str, sharing: str = "fair", restage: bool = False,
                 retain_partial: bool | None = None, eta: float = ETA):
        self.lin, self.k, self.rho = lin, consts, rho
        self.graph, self.knowledge, self.sharing, self.restage = graph, knowledge, sharing, restage
        self.retain = (graph != "none") if retain_partial is None else retain_partial
        self.caps = {**{("out", n): CAP_BPS * eta for n in NODES}, **{("in", n): CAP_BPS * eta for n in NODES}}
        self.tm = T_S / rho
        self.t = 0.0
        self.source, self.user = "A", "B"
        self.user_idx = 1
        self.held = {n: {} for n in NODES}          # node -> {entry: snapshot call}
        self.flows = {}
        self.nflow = 0
        self.mig = None
        self.migs = []
        self.moves = [{"t": 0.0, "to": "B"}]
        self.pending_cancel = None
        self.ev = []
        self.bytes = defaultdict(float)             # (kind, src, dst) -> bytes
        self.staged_to = defaultdict(float)         # node -> staged bytes received
        self.used_staged = defaultdict(float)       # node -> staged bytes that were valid at its migration
        self.remote_s = 0.0
        self.local_s = 0.0
        self.last_refresh_call = None
        self.done = False

    # -- time / calls
    def call(self, t=None):
        return 30 + int((self.t if t is None else t) / self.lin.period)

    def t_call(self, c):
        return (c - 30) * self.lin.period

    def log(self, event, **d):
        self.ev.append({"t": round(self.t, 3), "event": event, **d})

    # -- flows
    def start_flow(self, kind, src, dst, items, demand=None, task=None):
        """items: list of (entry, snapshot) or ("meta", bytes)"""
        self.nflow += 1
        fid = f"f{self.nflow}_{kind}_{src}{dst}"
        q = deque(items)
        fl = {"id": fid, "kind": kind, "src": src, "dst": dst, "q": q, "cur": None, "left": 0.0, "demand": demand, "task": task, "sent": 0.0, "open": kind == "stage"}
        self.flows[fid] = fl
        self._next_item(fl)
        return fl

    def _next_item(self, fl):
        if fl["q"]:
            it = fl["q"].popleft()
            fl["cur"] = it
            fl["left"] = float(it[1]) if it[0] == "meta" else float(self.lin.entry_bytes)
        else:
            fl["cur"] = None; fl["left"] = 0.0

    def queued_to(self, dst, kind="stage"):
        s = set()
        for fl in self.flows.values():
            if fl["dst"] == dst and fl["kind"] == kind:
                s |= {it[0] for it in fl["q"] if it[0] != "meta"}
                if fl["cur"] is not None and fl["cur"][0] != "meta":
                    s.add(fl["cur"][0])
        return s

    def cancel_flows(self, pred, why):
        for fid in [f for f, fl in self.flows.items() if pred(fl)]:
            fl = self.flows.pop(fid)
            self.log("flow_cancel", flow=fid, kind=fl["kind"], src=fl["src"], dst=fl["dst"], sent_mb=round(fl["sent"] / 1e6, 1), why=why)

    # -- migration
    def start_migration(self, dst):
        c0 = self.call(self.t + self.k["snapshot_s"])
        held = dict(self.held[dst]) if self.retain else {}
        valid = self.lin.valid(held, c0) if self.graph != "floor" else set(range(self.lin.n))
        delta = [e for e in range(self.lin.n) if e not in valid]
        items = [(e, c0) for e in delta] + [("meta", META_BYTES)]
        self.mig = {"id": len(self.migs) + 1, "src": self.source, "dst": dst, "t_start": self.t, "c0": c0, "valid": len(valid), "delta": len(delta),
                    "base_bytes": len(delta) * self.lin.entry_bytes + META_BYTES, "t_base_ready": None, "t_ready": None, "t_first_out": None, "outcome": "open"}
        self.used_staged[dst] += len(valid & set(held)) * self.lin.entry_bytes
        # staging to the destination stops: the migration takes over its ingress
        self.cancel_flows(lambda fl: fl["kind"] == "stage" and fl["dst"] == dst, "destination is now migrating")
        self.mig["base_flow"] = self.start_flow("base", self.source, dst, items, task=self.mig)
        self.mig["log_flow"] = self.start_flow("log", self.source, dst, [("meta", 1e18)], demand=self.k["log_bytes_per_call"] * 8 / self.lin.period, task=self.mig)
        self.migs.append(self.mig)
        self.log("migration_start", id=self.mig["id"], src=self.source, dst=dst, c0=c0, valid_entries=len(valid), delta_entries=len(delta), base_mb=round(self.mig["base_bytes"] / 1e6, 1))

    def cancel_migration(self, why):
        m = self.mig
        if m is None:
            return
        base_sent = m["base_flow"]["sent"]; log_sent = m["log_flow"]["sent"]
        m.update({"outcome": "cancelled", "t_end": self.t, "discarded_bytes": base_sent + log_sent, "base_sent": base_sent, "log_sent": log_sent})
        self.cancel_flows(lambda fl: fl.get("task") is m, why)
        self.log("migration_cancel", id=m["id"], dst=m["dst"], base_sent_mb=round(base_sent / 1e6, 1), log_sent_mb=round(log_sent / 1e6, 1))
        self.mig = None

    def complete_migration(self):
        m = self.mig
        old = self.source
        m.update({"outcome": "completed", "t_end": self.t})
        self.cancel_flows(lambda fl: fl.get("task") is m, "switchover")
        # ownership transition: the destination is the source from now on; the old source keeps its full live Sink as a holder
        self.source = m["dst"]
        self.held[old] = {e: self.call() for e in range(self.lin.n)}
        self.held[self.source] = {}
        self.log("ownership", **{"from": old, "to": self.source, "call": self.call()})
        self.mig = None

    # -- staging policy
    def candidates(self):
        if self.knowledge == "oracle":
            nxt = PATH[self.user_idx + 1] if self.user_idx + 1 < len(PATH) else None
            return [nxt] if nxt and nxt != self.source else []
        return [n for n in NODES if n != self.user and n != self.source]

    def holders(self):
        return [n for n in NODES if n != self.source and self.held[n]]

    def plan_staging(self, why):
        if self.graph in ("none", "floor"):
            return
        cands = self.candidates()
        if not cands:
            return
        src = self.source
        for cand in cands:
            have = set(self.held[cand]) | self.queued_to(cand)
            missing = [e for e in range(self.lin.n) if e not in have]
            if not missing:
                continue
            now_c = self.call()
            if self.graph == "star":
                self._add(src, cand, [(e, None) for e in missing])
            elif self.graph == "line":
                order = cands
                i = order.index(cand)
                if i == 0:
                    self._add(src, cand, [(e, None) for e in missing])
                else:
                    up = order[i - 1]
                    # forward what the upstream candidate holds now; the rest follows as it lands (pipelined, see on_landed)
                    held_up = [(e, self.held[up][e]) for e in missing if e in self.held[up]]
                    self._add(up, cand, held_up)
                    self.pipes = getattr(self, "pipes", {}); self.pipes[up] = cand
            elif self.graph == "tree":
                hubs = sorted(self.holders(), key=lambda n: -len(self.held[n]))
                hub = next((h for h in hubs if h != cand), None)
                if hub is None:
                    self._add(src, cand, [(e, None) for e in missing])
                else:
                    from_hub = [(e, self.held[hub][e]) for e in missing if e in self.held[hub]]
                    rest = [(e, None) for e in missing if e not in self.held[hub]]
                    self._add(hub, cand, from_hub); self._add(src, cand, rest)
            elif self.graph in ("butterfly", "adaptive"):
                provs = [h for h in self.holders() if h != cand]
                count = {p: 0 for p in provs + [src]}
                load = {p: sum(fl["left"] + sum(self.lin.entry_bytes for it in fl["q"] if it[0] != "meta") for fl in self.flows.values() if fl["src"] == p) for p in provs + [src]}
                assign = defaultdict(list)
                for e in missing:
                    have_h = [p for p in provs if e in self.held[p] and e not in self.lin.refreshed_in(self.held[p][e], now_c)]
                    if self.graph == "butterfly":
                        p = min(have_h, key=lambda h: (count[h], h)) if have_h else src
                    else:
                        est = lambda p_: (load[p_] + self.lin.entry_bytes) / self.caps[("out", p_)]  # noqa: E731
                        if have_h:
                            h = min(have_h, key=est)
                            inb = sum(fl["left"] for fl in self.flows.values() if fl["dst"] == cand) + len(assign) * self.lin.entry_bytes
                            p = src if est(h) > max(est(src), inb / self.caps[("in", cand)]) else h
                        else:
                            p = src
                    count[p] += 1; load[p] += self.lin.entry_bytes
                    assign[p].append((e, self.held[p][e] if p != src else None))
                for p, items in assign.items():
                    self._add(p, cand, items)
        self.log("staging_plan", why=why, candidates=cands, flows=len([f for f in self.flows.values() if f["kind"] == "stage"]))

    def _add(self, src, dst, items):
        if not items:
            return
        ex = next((fl for fl in self.flows.values() if fl["kind"] == "stage" and fl["src"] == src and fl["dst"] == dst), None)
        if ex is not None:
            ex["q"].extend(items)
            if ex["cur"] is None:
                self._next_item(ex)
        else:
            self.start_flow("stage", src, dst, items)

    def on_landed(self, fl, entry, snap):
        dst = fl["dst"]
        if dst == self.source:
            return
        self.held[dst][entry] = snap
        if fl["kind"] == "stage":
            self.staged_to[dst] += self.lin.entry_bytes
            down = getattr(self, "pipes", {}).get(dst)
            if self.graph == "line" and down and down in self.candidates() and entry not in self.held[down] and entry not in self.queued_to(down):
                self._add(dst, down, [(entry, snap)])

    # -- main loop
    def run(self, t_max=240.0):
        n_moves = len(PATH) - 2
        next_move = 1
        self.start_migration(self.user)
        self.plan_staging("t0")
        while self.t < t_max:
            # scheduled move
            if next_move <= n_moves and self.t >= next_move * self.tm - 1e-9:
                self.user_idx = next_move + 1; self.user = PATH[self.user_idx]
                self.moves.append({"t": self.t, "to": self.user}); self.log("move", to=self.user, serving=self.source)
                if self.mig is not None and (self.mig["t_ready"] is None or self.t < self.mig["t_ready"]):
                    self.pending_cancel = self.t + self.k["cancel_lag_s"]   # not yet switching: the move cancels it (after the measured lag)
                if self.mig is None and self.user != self.source:
                    self.start_migration(self.user)
                self.plan_staging("move")
                next_move += 1
            if self.pending_cancel is not None and self.t >= self.pending_cancel:
                self.pending_cancel = None
                if self.mig is not None and self.mig["t_ready"] is not None and self.t >= self.mig["t_ready"]:
                    pass   # it reached readiness during the lag: the switch proceeds (as cmd_precopy_cancel joins a switching task)
                else:
                    self.cancel_migration("user moved")
                if self.user != self.source:
                    self.start_migration(self.user)
                self.plan_staging("cancel")
            # refresh events at the source: optional re-staging of the refreshed entries
            c = self.call()
            if self.restage and c != self.last_refresh_call:
                self.last_refresh_call = c
                rf = self.lin.refresh.get(c, set())
                if rf:
                    for cand in self.candidates():
                        for e in rf:
                            if e in self.held[cand] and e not in self.queued_to(cand):
                                self._add(self.source, cand, [(e, None)])
            # bandwidth
            fl_list = [(f, fl["src"], fl["dst"]) for f, fl in self.flows.items() if fl["cur"] is not None]
            demand = {f: self.flows[f]["demand"] for f, _, _ in fl_list}
            if self.sharing == "residual":
                prim = [x for x in fl_list if self.flows[x[0]]["kind"] != "stage"]
                r1 = water_fill(prim, self.caps, demand)
                caps2 = dict(self.caps)
                for f, s, d in prim:
                    caps2[("out", s)] -= r1[f]; caps2[("in", d)] -= r1[f]
                r2 = water_fill([x for x in fl_list if self.flows[x[0]]["kind"] == "stage"], {k: max(0.0, v) for k, v in caps2.items()}, demand)
                rates = {**r1, **r2}
            else:
                rates = water_fill(fl_list, self.caps, demand)
            # advance
            for f, _, _ in fl_list:
                fl = self.flows.get(f)
                if fl is None or fl["cur"] is None:
                    continue
                b = rates[f] / 8 * DT
                if fl["kind"] == "log":
                    fl["sent"] += b; self.bytes[("log", fl["src"], fl["dst"])] += b
                    continue
                while b > 0 and fl["cur"] is not None:
                    take = min(b, fl["left"]); fl["left"] -= take; fl["sent"] += take; b -= take
                    self.bytes[(fl["kind"], fl["src"], fl["dst"])] += take
                    if fl["left"] <= 1e-6:
                        it = fl["cur"]
                        if it[0] != "meta":
                            snap = it[1] if it[1] is not None else self.call()
                            self.on_landed(fl, it[0], snap)
                        self._next_item(fl)
                        if fl["cur"] is None:
                            if fl["kind"] == "base":
                                m = fl["task"]; m["t_base_ready"] = self.t + BASE_READY_EXTRA_S
                            elif fl["kind"] == "stage" and not fl["open"]:
                                pass
            # finished closed flows
            for f in [f for f, fl in self.flows.items() if fl["cur"] is None and fl["kind"] == "stage" and not fl["q"]]:
                fl = self.flows.pop(f); self.log("stage_done", flow=f, src=fl["src"], dst=fl["dst"], mb=round(fl["sent"] / 1e6, 1))
                self.plan_staging("stage_done")
            for f in [f for f, fl in self.flows.items() if fl["cur"] is None and fl["kind"] == "base"]:
                self.flows.pop(f)
            # migration phases
            m = self.mig
            if m is not None and m["t_base_ready"] is not None and m["t_ready"] is None and self.t >= m["t_base_ready"]:
                logged = max(0, self.call(m["t_base_ready"]) - m["c0"])
                m["t_ready"] = max(m["t_base_ready"] + logged * self.k["catchup_per_call_s"], self.t_call(m["c0"] + W) + READY_EXTRA_S)
                m["t_first_out"] = m["t_ready"] + self.k["switch_s"]
                self.log("base_ready", id=m["id"], t_ready=round(m["t_ready"], 2), t_first_out=round(m["t_first_out"], 2))
            if m is not None and m["t_first_out"] is not None and self.t >= m["t_first_out"]:
                self.complete_migration()
                self.plan_staging("ownership")
            # serving accounting
            if self.source == self.user:
                self.local_s += DT
            else:
                self.remote_s += DT
            self.t += DT
            if next_move > n_moves and self.mig is None and self.source == self.user:
                break
            if next_move > n_moves and self.mig is None and self.user != self.source:
                self.start_migration(self.user)
        return self.summary()

    def summary(self):
        tot = sum(self.bytes.values())
        disc = sum(m.get("discarded_bytes", 0.0) for m in self.migs)
        staged = sum(self.staged_to.values())
        wasted = sum(max(0.0, self.staged_to[n] - self.used_staged[n]) for n in NODES)
        comp = [m for m in self.migs if m["outcome"] == "completed"]
        return {"graph": self.graph, "knowledge": self.knowledge, "sharing": self.sharing, "restage": self.restage, "rho": self.rho, "tm": self.tm,
                "remote_s": round(self.remote_s, 2), "local_s": round(self.local_s, 2), "t_end": round(self.t, 2),
                "migrations": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items() if k not in ("base_flow", "log_flow")} for m in self.migs],
                "n_cancelled": sum(1 for m in self.migs if m["outcome"] == "cancelled"), "n_completed": len(comp),
                "final_completed": bool(comp) and comp[-1]["dst"] == PATH[-1],
                "discarded_mb": round(disc / 1e6, 1), "staged_mb": round(staged / 1e6, 1), "wasted_staged_mb": round(wasted / 1e6, 1), "total_mb": round(tot / 1e6, 1),
                "source_bytes_final_mb": round(comp[-1]["base_bytes"] / 1e6, 1) if comp else None,
                "bytes_by_kind_mb": {f"{k}:{s}>{d}": round(v / 1e6, 1) for (k, s, d), v in sorted(self.bytes.items())}}


# ------------------------------------------------------------------------------------------------ driver
def consts_from_e0(name: str) -> dict:
    R = json.load(open(E0))["configs"][name]
    f = R["final"]; t = next(x for x in R["tasks"] if x["task"] == f["task"])
    lags = []
    for tk in R["tasks"]:
        if tk["outcome"] == "cancelled":
            mv = min((x["t"] for x in R["moves"] if x["t"] > tk["t_start"]), default=None)
            if mv is not None:
                lags.append(tk["t_end"] - mv)
    return {"log_bytes_per_call": t["log_bytes"] / t["log_calls"], "catchup_per_call_s": f["replay_catchup_s"] / t["log_calls"],
            "switch_s": f["first_output_s"] - f["readiness_s"], "cancel_lag_s": sum(lags) / len(lags) if lags else 0.5, "snapshot_s": f["round_snapshot_s"],
            "measured": {"remote_s": R["serving"]["remote_wall_s"], "n_cancelled": R["n_cancelled"], "discarded_mb": R["discarded_bytes"] / 1e6,
                         "final_base_send_s": f["base_send_s"], "final_readiness_s": f["readiness_s"], "moves": [m["t"] for m in R["moves"]]}}


def gate(sim_s0: dict, meas: dict) -> dict:
    fin = next((m for m in reversed(sim_s0["migrations"]) if m["outcome"] == "completed"), None)
    bs = (fin["t_base_ready"] - fin["t_start"] - BASE_READY_EXTRA_S) if fin else None
    chk = {"cancellations_equal": sim_s0["n_cancelled"] == meas["n_cancelled"],
           "base_send_within_15pct": bs is not None and abs(bs - meas["final_base_send_s"]) <= 0.15 * meas["final_base_send_s"],
           "remote_within_10pct": abs(sim_s0["remote_s"] - meas["remote_s"]) <= 0.10 * meas["remote_s"],
           "discarded_within_15pct": abs(sim_s0["discarded_mb"] - meas["discarded_mb"]) <= 0.15 * meas["discarded_mb"]}
    return {**chk, "pass": all(chk.values()), "sim_base_send_s": bs, "sim_remote_s": sim_s0["remote_s"], "sim_discarded_mb": sim_s0["discarded_mb"]}


def run_matrix(lin_by_wl: dict, out_dir: Path, rho_filter=None) -> dict:
    rep = {"eta": ETA, "W": W, "ready_extra_s": READY_EXTRA_S, "configs": {}}
    for name, (wl, rho) in CONFIGS.items():
        if rho_filter and rho not in rho_filter:
            continue
        lin = lin_by_wl.get(wl)
        if lin is None:
            rep["configs"][name] = {"error": f"no lineage table for {wl}"}; continue
        k = consts_from_e0(name)
        C = {"consts": {x: y for x, y in k.items() if x != "measured"}, "measured": k["measured"], "runs": {}}
        s0 = Sim(lin, k, rho, "none", "causal").run(); C["runs"]["none"] = s0
        C["gate"] = gate(s0, k["measured"])
        C["runs"]["floor"] = Sim(lin, k, rho, "floor", "oracle").run()
        C["runs"]["none+retain"] = Sim(lin, k, rho, "none", "causal", retain_partial=True).run()
        for g in ("star", "line", "tree", "butterfly", "adaptive"):
            for kn in KNOWLEDGE:
                for sh in ("fair", "residual"):
                    for rs in (False, True):
                        key = f"{g}/{kn}/{sh}/{'fresh' if rs else 'once'}"
                        C["runs"][key] = Sim(lin, k, rho, g, kn, sharing=sh, restage=rs).run()
        rep["configs"][name] = C
    # preregistered rules
    rep["rules"] = rules(rep)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "s0_results.json").write_text(json.dumps(rep, indent=1, default=str))
    (out_dir / "s0_results.md").write_text(render(rep))
    return rep


def rules(rep: dict) -> dict:
    """Section 5 of the preregistration, applied as written. Primary policy: causal / fair / once. Gains are measured
    against the simulated S0 and the simulated floor (every migration a metadata-only delta)."""
    out = {"gate": {}, "feasibility": {}, "e2e": {}, "topology": {}}
    for name, C in rep["configs"].items():
        if "error" in C:
            continue
        rho = CONFIGS[name][1]
        out["gate"][name] = C["gate"]["pass"]
        s0, fl = C["runs"]["none"], C["runs"]["floor"]
        ach = max(0.0, s0["remote_s"] - fl["remote_s"])
        feas, e2e, best_fixed, adapt = {}, {}, None, None
        for key, r in C["runs"].items():
            if "/" not in key:
                continue
            g, kn, sh, rs = key.split("/")
            final = next((m for m in reversed(r["migrations"]) if m["outcome"] == "completed"), None)
            second = next((m for m in r["migrations"] if m["id"] >= 2 and m["outcome"] == "completed"), None)
            # feasibility: at some migration after the first, >= 50 % lineage-valid entries and readiness before the next move
            ok_f = any(m["valid"] >= 0.5 * 180 and m["outcome"] == "completed" and m["t_ready"] is not None and (m["t_ready"] - m["t_start"]) < T_S / rho for m in r["migrations"] if m["id"] >= 2)
            feas[key] = ok_f
            cap = (s0["remote_s"] - r["remote_s"]) / ach if ach > 0 else None
            e2e[key] = {"remote_s": r["remote_s"], "captured_fraction": cap, "discarded_mb": r["discarded_mb"], "wasted_staged_mb": r["wasted_staged_mb"], "total_mb": r["total_mb"],
                        "final_completed": r["final_completed"], "source_bytes_final_mb": r["source_bytes_final_mb"],
                        "pass": bool(cap is not None and cap >= 0.5 and r["discarded_mb"] <= 0.5 * s0["discarded_mb"] and r["total_mb"] <= 1.25 * s0["total_mb"] and r["final_completed"])}
            if kn == "causal" and sh == "fair" and rs == "False":
                pass
        prim = {g: C["runs"][f"{g}/causal/fair/once"] for g in ("star", "line", "tree", "butterfly", "adaptive")}
        fixed = {g: prim[g]["remote_s"] for g in ("star", "line", "tree", "butterfly")}
        bf = min(fixed, key=fixed.get)
        out["topology"][name] = {"best_fixed": bf, "best_fixed_remote_s": fixed[bf], "adaptive_remote_s": prim["adaptive"]["remote_s"],
                                 "adaptive_within_10pct_of_best_fixed": prim["adaptive"]["remote_s"] <= 1.10 * fixed[bf] + 1e-9,
                                 "fixed_beats_adaptive_by_10pct": fixed[bf] <= 0.90 * prim["adaptive"]["remote_s"]}
        out["feasibility"][name] = {"any_graph_causal_primary": any(feas[f"{g}/causal/fair/once"] for g in ("star", "line", "tree", "butterfly", "adaptive")),
                                    "any_graph_oracle": any(feas[f"{g}/oracle/fair/once"] for g in ("star", "line", "tree", "butterfly", "adaptive")), "per_policy": feas}
        out["e2e"][name] = {"achievable_remote_reduction_s": ach, "floor_remote_s": fl["remote_s"], "s0_remote_s": s0["remote_s"],
                            "any_graph_causal_primary_pass": any(e2e[f"{g}/causal/fair/once"]["pass"] for g in ("star", "line", "tree", "butterfly", "adaptive")),
                            "any_graph_oracle_pass": any(e2e[f"{g}/oracle/fair/once"]["pass"] for g in ("star", "line", "tree", "butterfly", "adaptive")), "per_policy": e2e}
    r1 = [n for n in out["gate"] if CONFIGS[n][1] == 1]
    g_ok = all(out["gate"][n] for n in out["gate"])
    F = all(out["feasibility"][n]["any_graph_causal_primary"] for n in r1) if r1 else False
    E = all(out["e2e"][n]["any_graph_causal_primary_pass"] for n in r1) if r1 else False
    Fo = all(out["feasibility"][n]["any_graph_oracle"] for n in r1) if r1 else False
    if not g_ok:
        verdict = "NO VERDICT (model validity gate failed)"
    elif F and E:
        verdict = "GO"
    elif not Fo or not F:
        verdict = "NO-GO (feasibility fails at rho 1 for a workload)"
    else:
        verdict = "CONDITIONAL (feasible, end-to-end gain below the preregistered bounds under the causal policy)"
    out["verdict"] = verdict
    return out


def render(rep: dict) -> str:
    L = [f"# M3-S0 simulation results (eta {rep['eta']}, W {rep['W']})", ""]
    for name, C in rep["configs"].items():
        if "error" in C:
            L += [f"## {name}: {C['error']}", ""]; continue
        L += [f"## {name}", "", f"gate: {C['gate']}", "", "| policy | remote s | local s | cancelled | completed | final | discarded MB | staged MB | wasted MB | total MB | migrations (valid/180, delta MB, ready s) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for key, r in C["runs"].items():
            mig = "; ".join(f"{m['dst']}:{m['valid']}/{m['delta']}:{m['base_bytes'] / 1e6:.0f}MB:{(m['t_ready'] - m['t_start']) if m['t_ready'] else None}" for m in r["migrations"])
            L.append(f"| {key} | {r['remote_s']} | {r['local_s']} | {r['n_cancelled']} | {r['n_completed']} | {r['final_completed']} | {r['discarded_mb']} | {r['staged_mb']} | {r['wasted_staged_mb']} | {r['total_mb']} | {mig} |")
        L.append("")
    L += ["## Rules", "", "```", json.dumps({k: v for k, v in rep["rules"].items() if k != "e2e" and k != "feasibility"}, indent=1, default=str), "```", ""]
    return "\n".join(L)


def selftest():
    lin = Lineage(synthetic_lineage(rate=0.1))
    k = {"log_bytes_per_call": 1.0e6, "catchup_per_call_s": 0.117, "switch_s": 1.9, "cancel_lag_s": 0.5, "snapshot_s": 0.4,
         "measured": {"remote_s": 50.0, "n_cancelled": 2, "discarded_mb": 2795.0, "final_base_send_s": 17.0, "final_readiness_s": 21.6, "moves": [14.05, 28.1]}}
    fails = []

    def check(name, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")
        if not ok:
            fails.append(name)
    s0 = Sim(lin, k, 1, "none", "causal").run()
    check("S0 rho1: two cancellations and a completed final migration", s0["n_cancelled"] == 2 and s0["final_completed"], f"remote {s0['remote_s']} discarded {s0['discarded_mb']}")
    fin = next(m for m in reversed(s0["migrations"]) if m["outcome"] == "completed")
    bs = fin["t_base_ready"] - fin["t_start"] - BASE_READY_EXTRA_S
    check("S0 full base send near 1727.6 MB / (eta x 1 Gbps)", abs(bs - 1727.6e6 * 8 / (ETA * 1e9)) < 1.0, f"{bs:.2f} s")
    g = gate(s0, k["measured"]); check("gate structure computed", "pass" in g, str(g))
    fl = Sim(lin, k, 1, "floor", "oracle").run()
    check("floor: every migration metadata-only, readiness at the Replay-W floor", all(m["delta"] == 0 for m in fl["migrations"]) and fl["remote_s"] < s0["remote_s"], f"remote {fl['remote_s']}")
    fin_f = next(m for m in fl["migrations"] if m["id"] == 2)
    check("floor readiness = t_call(c0 + W) + extra", abs((fin_f["t_ready"] - fin_f["t_start"]) - ((fin_f["c0"] + W - 30) * lin.period + READY_EXTRA_S - fin_f["t_start"])) < 0.05, f"{fin_f['t_ready'] - fin_f['t_start']:.2f}")
    so = Sim(lin, k, 1, "star", "oracle").run()
    check("star/oracle: staged entries make a delta migration (valid > 0) and remote serving drops", any(m["valid"] > 0 for m in so["migrations"]) and so["remote_s"] < s0["remote_s"], f"remote {so['remote_s']} valid {[m['valid'] for m in so['migrations']]}")
    sc = Sim(lin, k, 1, "star", "causal").run()
    check("star/causal: stages to two candidates, wasted staging > 0", sc["staged_mb"] > so["staged_mb"] and sc["wasted_staged_mb"] > 0, f"staged {sc['staged_mb']} wasted {sc['wasted_staged_mb']}")
    bf = Sim(lin, k, 1, "butterfly", "causal").run()
    check("butterfly/causal: some staging bytes come from a holder (not the source)", any(k_.startswith("stage:") and not k_.startswith("stage:A>") for k_ in bf["bytes_by_kind_mb"]), str([k_ for k_ in bf["bytes_by_kind_mb"] if k_.startswith("stage")]))
    ln = Sim(lin, k, 1, "line", "causal").run()
    check("line/causal: the second candidate receives from the first", any(k_.startswith("stage:") and k_[6] != "A" for k_ in ln["bytes_by_kind_mb"]), str([k_ for k_ in ln["bytes_by_kind_mb"] if k_.startswith("stage")]))
    r2 = Sim(lin, k, 2, "floor", "oracle").run()
    check("rho 2: even the floor cannot complete before the next move (Replay-W floor > T_m)", all(m["outcome"] == "cancelled" for m in r2["migrations"] if m["id"] <= 2), f"{[(m['id'], m['outcome']) for m in r2['migrations']]}")
    res = Sim(lin, k, 1, "star", "causal", sharing="residual").run()
    s0b = Sim(lin, k, 1, "star", "causal", sharing="fair").run()
    check("residual sharing never slows the active migration below fair", all(a["t_base_ready"] is None or b["t_base_ready"] is None or a["t_base_ready"] <= b["t_base_ready"] + 1e-6 for a, b in zip(res["migrations"], s0b["migrations"])), "")
    wf = water_fill([("x", "A", "B"), ("y", "A", "C"), ("z", "A", "B")], {("out", "A"): 1.0, ("in", "B"): 1.0, ("in", "C"): 1.0}, {"y": 0.1})
    check("water-fill: demand-limited flow frozen at its demand, rest shared", abs(wf["y"] - 0.1) < 1e-9 and abs(wf["x"] - 0.45) < 1e-9 and abs(wf["z"] - 0.45) < 1e-9, str(wf))
    print("ALL PASS" if not fails else f"FAILED: {fails}")
    sys.exit(1 if fails else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true"); ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--events_dir", default=str(OUT)); ap.add_argument("--out_dir", default=str(OUT))
    ap.add_argument("--rhos", default="", help="restrict to these rhos (comma)")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    lin = {}
    for wl in ("dog", "bfly"):
        p = Path(a.events_dir) / f"events_{wl}.json"
        if p.exists():
            J = json.load(open(p)); lin[wl] = Lineage(J)
            print(f"[S0] {wl}: calls {J['c_lo']}..{J['c_hi']}, lineage rule consistent {J['lineage_rule_check']['fraction']}")
    rep = run_matrix(lin, Path(a.out_dir), rho_filter={int(x) for x in a.rhos.split(",") if x} or None)
    print(json.dumps({"gate": rep["rules"]["gate"], "topology": rep["rules"]["topology"], "verdict": rep["rules"]["verdict"]}, indent=1, default=str))
    for n, C in rep["configs"].items():
        if "error" in C:
            continue
        for key in ("none", "floor", "star/causal/fair/once", "butterfly/causal/fair/once", "adaptive/causal/fair/once", "star/oracle/fair/once", "adaptive/oracle/fair/once"):
            r = C["runs"][key]
            print(f"{n:10s} {key:30s} remote {r['remote_s']:6.1f} local {r['local_s']:6.1f} canc {r['n_cancelled']} comp {r['n_completed']} disc {r['discarded_mb']:7.1f} staged {r['staged_mb']:7.1f} wasted {r['wasted_staged_mb']:7.1f} total {r['total_mb']:7.1f}")


if __name__ == "__main__":
    main()
