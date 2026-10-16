#!/usr/bin/env python3
"""Fluid flow model of the Scenario B / Step 2 restoration harness (no network): predicts makespan and source bytes for
the restoration policies under per-node egress/ingress caps shared max-min fairly. Used to write the pre-registered
predictions and to pick the holder-bandwidth grid; it mirrors restore_orchestrate.py's planning rules at fragment
granularity but moves bytes as a fluid (no TCP, no in-flight drain, no verification cost).

    python tools/eval/restore_model.py --sessions 1,2,4 --holder_mbps 125,250,500,1000 --policies restart,reuse_fixed,reuse_adaptive,reuse_aware
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from restore_orchestrate import EDGES, SINK_BYTES, dissem_assign, maxmin, parse_cap_events  # noqa: E402

FLEN = 4 << 20
NFR = -(-SINK_BYTES // FLEN)   # 412


class Model:
    def __init__(self, policy, n, moves, tm, caps, dt=0.02, prepos=None, cap_events="", dyn=None):
        self.policy, self.N, self.moves, self.tm, self.caps, self.dt = policy, n, moves, tm, dict(caps), dt
        self.pp = prepos
        self.known_caps = dict(caps)            # what planners believe; live cap changes are not revealed
        self.cap_events = parse_cap_events(cap_events)
        self.dyn = {"period": 0.5, "window": 2.0, "warmup": 2.0, "eps": 2.0, "rel": 0.10, "ctrl": 0.3, **(dyn or {})}
        self.last_plan_t = {}; self.replans = []; self.cap_change_t = None; self.dyn_next = 0.0; self.pending_start = []
        self.rate_est = {}   # (sid, node) -> (bytes/s, t): last valid measurement, kept while idle
        self.moves_log = []; self.restored_log = []
        self.sids = [f"s{i}" for i in range(n)]
        self.owner = {s: EDGES[i % 3] for i, s in enumerate(self.sids)}
        if prepos:
            self.owner["s0"] = "A"
        self.move_t = {}
        self.history = {s: [self.owner[s]] for s in self.sids}
        self.held = {s: {e: set() for e in ["A"] + EDGES} for s in self.sids}
        for s in self.sids:
            self.held[s]["A"] = set(range(NFR))
        self.flows = []           # dicts: sid, src, dst, order (list), left (set), prog (bytes into current fragment)
        self.restored = {s: None for s in self.sids}
        self.src_bytes = 0.0
        self.t = 0.0

    def claims(self, sid, dst):
        s = set()
        for fl in self.flows:
            if fl["sid"] == sid and fl["dst"] == dst:
                s |= fl["left"]
        return s

    def cancel(self, sid, keep_dst):
        self.flows = [fl for fl in self.flows if not (fl["sid"] == sid and fl["dst"] != keep_dst)]

    def start(self, sid, src, dst, fids):
        if fids:
            self.flows.append({"sid": sid, "src": src, "dst": dst, "order": list(fids), "left": set(fids), "prog": 0.0})

    def plan(self, sid, reason):
        own = self.owner[sid]
        allf = set(range(NFR))
        self.last_plan_t[sid] = self.t
        if self.policy == "restart":
            self.cancel(sid, keep_dst=own if reason == "flow_done" else None)
            if reason == "move":
                for e in EDGES:
                    self.held[sid][e] = set()
            self.start(sid, "A", own, sorted(allf - self.held[sid][own] - self.claims(sid, own)))
            return
        self.cancel(sid, keep_dst=own)
        missing = allf - self.held[sid][own] - self.claims(sid, own)
        if not missing:
            return
        holders = list(dict.fromkeys(e for e in reversed(self.history[sid][:-1]) if e != own and e != "A"))
        holders += [e for e in EDGES if e != own and e not in holders and self.held[sid][e]]
        assign = defaultdict(list)
        if self.policy == "reuse_fixed":
            for f in sorted(missing):
                assign[next((h for h in holders if f in self.held[sid][h]), "A")].append(f)
        elif self.policy in ("pp_star", "fixed_line", "fixed_tree", "fixed_butterfly"):   # Experiment E fixed plans (same semantics as the harness)
            past = [e for e in self.history[sid][:-1] if e != "A"]
            allowed = [] if self.policy == "pp_star" else ([past[-1]] if self.policy == "fixed_line" and past and past[-1] != own else
                                                           [past[0]] if self.policy == "fixed_tree" and past and past[0] != own else
                                                           list(holders) if self.policy == "fixed_butterfly" else [])
            count = {h: 0 for h in allowed}
            for f in sorted(missing):
                have = [h for h in allowed if f in self.held[sid][h]]
                if have:
                    src = min(have, key=lambda h: (count[h], h)); count[src] += 1; assign[src].append(f)
                else:
                    assign["A"].append(f)
        elif self.policy == "reuse_adaptive":   # the Scenario B rule: probe max-min rate of a new flow, per-session load
            act = [(i, fl["src"], fl["dst"]) for i, fl in enumerate(self.flows)]
            cand = holders + ["A"]
            est = {c: max(1.0, maxmin(act + [("p", c, own)], self.caps)["p"]) for c in cand}
            load = {c: 0 for c in cand}
            for f in sorted(missing):
                opts = [c for c in cand if c == "A" or f in self.held[sid][c]]
                best = min(opts, key=lambda c: ((load[c] + 1) * FLEN / est[c], c == "A"))
                assign[best].append(f); load[best] += 1
        else:   # reuse_aware(_in|dyn): balance providers' egress backlog (all sessions) over their egress caps; unavoidable source fragments first
            cand = holders + ["A"]
            load = {c: 0.0 for c in cand}
            for fl in self.flows:
                if fl["src"] in load:
                    load[fl["src"]] += len(fl["left"]) * FLEN
            only_a = [f for f in sorted(missing) if not any(f in self.held[sid][h] for h in holders)]
            for f in only_a:
                assign["A"].append(f); load["A"] += FLEN
            inbound = sum(len(fl["left"]) * FLEN for fl in self.flows if fl["dst"] == own) + len(only_a) * FLEN
            for f in sorted(set(missing) - set(only_a)):
                opts = [c for c in cand if c == "A" or f in self.held[sid][c]]
                est = lambda c: (load[c] + FLEN) / self.known_caps[("out", c)]  # noqa: E731
                if self.policy in ("reuse_aware_in", "reuse_dyn"):   # H4c: move to the source only past both the source and the ingress bound
                    inbound += FLEN
                    hold = min((c for c in opts if c != "A"), key=est)
                    best = "A" if est(hold) > max(est("A"), inbound / self.known_caps[("in", own)]) else hold
                else:
                    best = min(opts, key=lambda c: (est(c), c == "A"))
                assign[best].append(f); load[best] += FLEN
        for src, ids in assign.items():
            self.start(sid, src, own, ids)

    def prepos_start(self):
        pp, S = self.pp, SINK_BYTES
        order = sorted(EDGES, key=lambda c: -pp["probs"][EDGES.index(c)])
        prob = {c: pp["probs"][EDGES.index(c)] for c in EDGES}
        deliv = {c: pp["L"] * self.caps[("in", c)] / 8 / S for c in EDGES}
        avail = min(pp["b"], pp["L"] * self.caps[("out", "A")] / 8 / S)
        x = {c: 0.0 for c in EDGES}; pol = pp["policy"]
        if pol == "oracle":
            x[pp["dest"]] = min(avail, deliv[pp["dest"]])
        elif pol == "top1":
            x[order[0]] = min(avail, deliv[order[0]])
        elif pol == "greedy":
            rem = avail
            for c in order:
                x[c] = min(rem, deliv[c]); rem -= x[c]
        elif pol == "proportional":
            for c in order:
                x[c] = min(avail * prob[c], deliv[c])
        elif pol == "coverage":
            rem = avail
            for c in order:
                need = max(0.0, 1.0 - (pp["tau"] - 0.3) * self.caps[("in", c)] / 8 / S)
                x[c] = min(need, deliv[c], rem); rem -= x[c]
            for c in order:
                add = min(rem, deliv[c] - x[c]); x[c] += add; rem -= add
        pos = 0
        for c in order:
            n = int(round(x[c] * NFR))
            self.start("s0", "A", c, list(range(pos, pos + n))); pos += n
        self.alloc = x

    def dyn_check(self, sid, rates):
        """Event-driven re-planning with perfect rate measurement (the model's view of 'measured' is the current max-min rate)."""
        own = self.owner[sid]
        if self.t - self.last_plan_t.get(sid, -1e9) < self.dyn["warmup"]:
            return
        act = [(i, fl) for i, fl in enumerate(self.flows) if fl["sid"] == sid and fl["dst"] == own and fl["left"] and not fl.get("draining")]
        if not act:
            return
        rate, rem = {}, {}
        for i, fl in act:
            rate[fl["src"]] = rate.get(fl["src"], 0.0) + rates[i] / 8; rem[fl["src"]] = rem.get(fl["src"], 0) + len(fl["left"]) * FLEN
        eta = {p: (rem[p] / rate[p] if rate[p] > 0 else 1e6) for p in rem}
        q = max(eta, key=eta.get); eta_cur = eta[q]
        for n, r in rate.items():
            if r > 0:
                self.rate_est[(sid, n)] = (r, self.t)
        cap_est = {n: (self.rate_est[(sid, n)][0] if (sid, n) in self.rate_est else self.known_caps[("out", n)]) for n in ["A"] + EDGES}
        qflows = [fl for _, fl in act if fl["src"] == q]
        head = {next((f for f in fl["order"] if f in fl["left"]), None) for fl in qflows} - {None}
        movable = set().union(*(fl["left"] for fl in qflows)) - head
        if not movable:
            return
        load = {n: 0.0 for n in ["A"] + EDGES}
        for _, fl in act:
            if fl["src"] != q:
                load[fl["src"]] += len(fl["left"]) * FLEN
        load[q] += len(head) * FLEN
        inbound = sum(len(fl["left"]) for _, fl in act) * FLEN
        assign = defaultdict(list)
        for f in sorted(movable):
            opts = [c for c in ["A"] + EDGES if c != own and (c == "A" or f in self.held[sid][c])]
            best = min(opts, key=lambda c: ((load[c] + FLEN) / cap_est[c], c == "A"))
            assign[best].append(f); load[best] += FLEN
        eta_new = max(max((load[n] / cap_est[n] for n in load if load[n] > 0), default=0.0), inbound / self.known_caps[("in", own)])
        drain = FLEN / max(rate[q], 1.0) if head else 0.0
        c_switch = self.dyn["ctrl"] + drain
        dT = eta_cur - eta_new
        if dT <= c_switch + max(self.dyn["eps"], self.dyn["rel"] * eta_cur) or set(assign) == {q}:
            return
        for fl in qflows:   # the bottleneck's flows drain their in-flight fragment and end
            fl["left"] = set(head) & fl["left"]; fl["draining"] = True
        for p_, ids in assign.items():
            ex = next((fl for _, fl in act if fl["src"] == p_ and p_ != q), None)
            if ex is not None:
                ex["left"] |= set(ids); ex["order"] = ex["order"] + sorted(ids)
            else:
                self.pending_start.append((self.t + self.dyn["ctrl"], {"sid": sid, "src": p_, "dst": own, "order": sorted(ids), "left": set(ids), "prog": 0.0}))
        self.last_plan_t[sid] = self.t
        self.replans.append({"t": self.t, "from": q, "to": {p_: len(v) for p_, v in assign.items()}, "eta_cur": eta_cur, "eta_new": eta_new, "dT": dT, "c_switch": c_switch,
                             "detection_delay": None if self.cap_change_t is None else self.t - self.cap_change_t})

    def move(self, sid, to=None):
        old = self.owner[sid]
        new = to or EDGES[(EDGES.index(old) + 1) % 3]
        if sid == "s0" and self.pp:
            self.held_at_move = {e: len(self.held[sid][e]) / NFR for e in EDGES}   # verified at each candidate when the move happens
        self.moves_log.append({"t": self.t, "sid": sid, "to": new, "held_at_new": len(self.held[sid][new]) / NFR, "revisit": new in self.history[sid]})
        self.owner[sid] = new; self.history[sid].append(new); self.move_t[sid] = self.t
        self.restored[sid] = None
        self.plan(sid, "move")
        if len(self.held[sid][new]) == NFR:
            self.restored[sid] = self.t

    def run(self, horizon):
        os_ = (self.pp or {}).get("others_start", 0.0) or 0.0
        for s in self.sids:
            if not (os_ and s != "s0"):
                self.plan(s, "start")
        sched = sorted((os_ + self.tm * (k + i / self.N), s, None) for i, s in enumerate(self.sids) if not (self.pp and s == "s0")
                       for k in range(1, (self.moves or 10000) + 1) if os_ + self.tm * (k + i / self.N) <= horizon)
        if os_:
            sched = sorted(sched + [(os_, s, "__start__") for s in self.sids if s != "s0"])
        if self.pp:
            self.prepos_start(); sched = sorted(sched + [(self.pp["L"], "s0", self.pp["dest"])])
        while self.t < horizon:
            while sched and sched[0][0] <= self.t + 1e-9:
                _, s, to = sched.pop(0)
                if to == "__start__":
                    self.plan(s, "start")
                else:
                    self.move(s, to)
            if self.moves and all(self.restored[s] is not None for s in self.sids) and not sched:
                break
            for evn in self.cap_events:   # network changes (planners are not told)
                if not evn.get("fired") and ((evn["kind"] == "t" and self.t >= evn["at"]) or (evn["kind"] == "progress" and len(self.held["s0"][evn["node"]]) >= evn["frac"] * NFR)):
                    evn["fired"] = True; self.caps[(evn["dir"], evn["cap_node"])] = evn["mbps"] * 1e6; self.cap_change_t = self.t
            # delayed starts of re-planned flows (control-plane cost)
            for st_t, fl in list(self.pending_start):
                if self.t >= st_t:
                    self.flows.append(fl); self.pending_start.remove((st_t, fl))
            rates = maxmin([(i, fl["src"], fl["dst"]) for i, fl in enumerate(self.flows)], self.caps)
            if self.policy == "reuse_dyn" and self.t >= self.dyn_next:
                self.dyn_next = self.t + self.dyn["period"]
                for s in self.sids:
                    self.dyn_check(s, rates)
                rates = maxmin([(i, fl["src"], fl["dst"]) for i, fl in enumerate(self.flows)], self.caps)
            done_flows = []
            for i, fl in enumerate(self.flows):
                b = rates[i] / 8 * self.dt
                if fl["src"] == "A":
                    self.src_bytes += b
                fl["prog"] += b
                while fl["left"] and fl["prog"] >= FLEN:
                    fl["prog"] -= FLEN
                    f = next(x for x in fl["order"] if x in fl["left"])
                    fl["left"].discard(f)
                    self.held[fl["sid"]][fl["dst"]].add(f)
                    if fl["dst"] == self.owner[fl["sid"]] and len(self.held[fl["sid"]][fl["dst"]]) == NFR and self.restored[fl["sid"]] is None:
                        self.restored[fl["sid"]] = self.t + self.dt; self.restored_log.append({"t": self.t + self.dt, "sid": fl["sid"], "at": fl["dst"]})
                if not fl["left"]:
                    done_flows.append(fl)
            if done_flows:   # a completed flow needs no re-plan (the orchestrator re-plans only when a provider skipped fragments)
                self.flows = [fl for fl in self.flows if fl not in done_flows]
            self.t += self.dt
        fin = [v for v in self.restored.values() if v is not None]
        out = {"restored": len(fin), "makespan": max(fin) if len(fin) == self.N else None, "source_per_session": self.src_bytes / SINK_BYTES / self.N,
               "replans": self.replans, "cap_change_t": self.cap_change_t, "restored_t": dict(self.restored), "move_t": dict(self.move_t),
               "moves_log": self.moves_log, "restored_log": self.restored_log, "total_sinks": sum(len(fl_) for fl_ in []) }
        if self.pp:
            r0 = self.restored["s0"]; out["t_r"] = None if r0 is None else r0 - self.move_t["s0"]; out["alloc"] = self.alloc
            others = [v for k, v in self.restored.items() if k != "s0"]
            out["others_makespan"] = max(others) if others and None not in others else None
            out["held_at_move"] = getattr(self, "held_at_move", {e: 0.0 for e in EDGES})
        return out


class DissemModel:
    """Experiment B fluid model: one Sink at A to B, C, D under a plan from dissem_assign; forwarders can only send
    fragments they already hold (a stalled flow keeps its max-min share, as the orchestrator counts open flows)."""

    def __init__(self, plan, caps, dt=0.02):
        self.plan, self.caps, self.dt = plan, caps, dt
        self.held = {n: set() for n in ["A"] + EDGES}; self.held["A"] = set(range(NFR))
        prov = dissem_assign(plan, NFR, FLEN, caps)
        by = defaultdict(list)
        for (f, d), p in prov.items():
            by[(p, d)].append(f)
        self.flows = [{"src": p, "dst": d, "order": sorted(fs), "left": set(fs), "prog": 0.0} for (p, d), fs in sorted(by.items())]
        self.src_bytes = 0.0; self.t = 0.0; self.done = {d: None for d in EDGES}

    def run(self, horizon=600.0):
        while self.t < horizon and any(v is None for v in self.done.values()):
            rates = maxmin([(i, fl["src"], fl["dst"]) for i, fl in enumerate(self.flows)], self.caps)
            for i, fl in enumerate(self.flows):
                # a forwarder sends whichever of its assigned fragments it already holds (FLOW_ADD order = arrival order)
                sendable = lambda: next((x for x in fl["order"] if x in fl["left"] and x in self.held[fl["src"]]), None)  # noqa: E731
                if sendable() is None:
                    continue   # nothing sendable yet (pipelining stall; the flow keeps its share, as in the harness)
                b = rates[i] / 8 * self.dt
                if fl["src"] == "A":
                    self.src_bytes += b
                fl["prog"] += b
                while fl["prog"] >= FLEN:
                    head = sendable()
                    if head is None:
                        fl["prog"] = 0.0; break
                    fl["prog"] -= FLEN; fl["left"].discard(head); self.held[fl["dst"]].add(head)
                    if len(self.held[fl["dst"]]) == NFR and self.done[fl["dst"]] is None:
                        self.done[fl["dst"]] = self.t + self.dt
            self.flows = [fl for fl in self.flows if fl["left"]]
            self.t += self.dt
        fin = [v for v in self.done.values() if v is not None]
        tot = sum(len(v) for v in self.held.values()) - NFR   # copies delivered
        return {"completion": dict(self.done), "makespan": max(fin) if len(fin) == 3 else None, "source_sinks": self.src_bytes / SINK_BYTES,
                "total_sinks": tot / NFR}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sessions", default="1,2,4")
    p.add_argument("--holder_mbps", default="125,250,500,1000")
    p.add_argument("--source_mbps", type=float, default=1000)
    p.add_argument("--in_mbps", type=float, default=1000)
    p.add_argument("--policies", default="restart,reuse_fixed,reuse_adaptive,reuse_aware,reuse_aware_in")
    p.add_argument("--moves", type=int, default=1)
    p.add_argument("--ts", type=float, default=14.05)
    p.add_argument("--rho", type=float, default=2)
    p.add_argument("--prepos", default="", help="Experiment A: pre-positioning policies (none,oracle,top1,greedy,proportional,coverage); prints T_r per true destination")
    p.add_argument("--probs", default="0.6,0.3,0.1")
    p.add_argument("--lookahead", type=float, default=10.0)
    p.add_argument("--budget", type=float, default=1.0)
    p.add_argument("--tau", type=float, default=7.5)
    p.add_argument("--restore_policy", default="reuse_aware_in")
    p.add_argument("--ctrl", type=float, default=0.3, help="control-plane seconds added to every predicted T_r")
    p.add_argument("--dissem", default="", help="Experiment B plans (star,line,tree,multipath,aware): per-destination completion under --source_mbps / --holder_mbps / --in_mbps")
    a = p.parse_args()
    if a.dissem:
        print(f"{'plan':>10} | {'B':>7} {'C':>7} {'D':>7} | makespan | source S | total S   (B_s / B_f / B_in Mbps, +{a.ctrl} s control plane)")
        for bh in [float(x) for x in a.holder_mbps.split(",")]:
            caps = {("out", "A"): a.source_mbps * 1e6, ("in", "A"): a.in_mbps * 1e6}
            for e in EDGES:
                caps[("out", e)] = bh * 1e6; caps[("in", e)] = a.in_mbps * 1e6
            print(f"-- B_s {a.source_mbps:g} / B_f {bh:g} / B_in {a.in_mbps:g}")
            for plan in a.dissem.split(","):
                r = DissemModel(plan, caps).run()
                c = {d: (None if v is None else v + a.ctrl) for d, v in r["completion"].items()}
                f = lambda v: "   none" if v is None else f"{v:7.1f}"  # noqa: E731
                print(f"{plan:>10} | {f(c['B'])} {f(c['C'])} {f(c['D'])} | {f(None if r['makespan'] is None else r['makespan'] + a.ctrl)} | {r['source_sinks']:8.2f} | {r['total_sinks']:7.2f}")
        return
    if a.prepos:
        probs = [float(x) for x in a.probs.split(",")]
        print(f"pre-positioning, L={a.lookahead:g} s, b={a.budget:g} Sinks, probs {probs}, restore policy {a.restore_policy}, +{a.ctrl} s control plane")
        print(f"{'policy':>12} | " + " ".join(f"T_r d={c:>1}" for c in EDGES) + " |  mean  miss(>tau)  alloc")
        for n in [int(x) for x in a.sessions.split(",")]:
            for bh in [float(x) for x in a.holder_mbps.split(",")]:
                caps = {("out", "A"): a.source_mbps * 1e6, ("in", "A"): a.in_mbps * 1e6}
                for e in EDGES:
                    caps[("out", e)] = bh * 1e6; caps[("in", e)] = a.in_mbps * 1e6
                print(f"-- N={n}, holder egress {bh:g} Mbps")
                for pol in a.prepos.split(","):
                    tr = {}
                    for d in EDGES:
                        pp = {"policy": pol, "probs": probs, "L": a.lookahead, "b": a.budget, "dest": d, "tau": a.tau}
                        r = Model(a.restore_policy, n, 1, a.ts / a.rho, caps, prepos=pp).run(horizon=a.lookahead + 4 * n * a.ts + 3 * a.ts / a.rho)
                        tr[d] = None if r["t_r"] is None else r["t_r"] + a.ctrl; alloc = r["alloc"]
                    mean = sum(p_ * tr[d] for p_, d in zip(probs, EDGES)); miss = sum(p_ for p_, d in zip(probs, EDGES) if tr[d] > a.tau)
                    print(f"{pol:>12} | " + " ".join(f"{tr[d]:8.2f}" for d in EDGES) + f" | {mean:5.2f}  {miss:4.2f}  " + " ".join(f"{c}:{alloc[c]:.2f}" for c in EDGES))
        return
    pols = a.policies.split(",")
    print(f"{'N':>2} {'B_h':>5} | " + " ".join(f"{pp:>16}" for pp in pols) + "   (makespan s / source Sinks per session)")
    for n in [int(x) for x in a.sessions.split(",")]:
        for bh in [float(x) for x in a.holder_mbps.split(",")]:
            caps = {("out", "A"): a.source_mbps * 1e6, ("in", "A"): a.in_mbps * 1e6}
            for e in EDGES:
                caps[("out", e)] = bh * 1e6; caps[("in", e)] = a.in_mbps * 1e6
            row = []
            for pp in pols:
                r = Model(pp, n, a.moves, a.ts / a.rho, caps).run(horizon=2 * (n * a.ts + a.ts * a.in_mbps / bh) + 3 * a.ts / a.rho)
                ms = "none" if r["makespan"] is None else f"{r['makespan']:.1f}"
                row.append(f"{ms:>8} /{r['source_per_session']:.2f}")
            print(f"{n:>2} {bh:>5.0f} | " + " ".join(f"{x:>16}" for x in row))


if __name__ == "__main__":
    main()
