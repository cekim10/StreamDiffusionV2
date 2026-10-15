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
from restore_orchestrate import EDGES, SINK_BYTES, maxmin  # noqa: E402

FLEN = 4 << 20
NFR = -(-SINK_BYTES // FLEN)   # 412


class Model:
    def __init__(self, policy, n, moves, tm, caps, dt=0.02):
        self.policy, self.N, self.moves, self.tm, self.caps, self.dt = policy, n, moves, tm, caps, dt
        self.sids = [f"s{i}" for i in range(n)]
        self.owner = {s: EDGES[i % 3] for i, s in enumerate(self.sids)}
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
        holders = list(dict.fromkeys(e for e in reversed(self.history[sid][:-1]) if e != own))
        assign = defaultdict(list)
        if self.policy == "reuse_fixed":
            for f in sorted(missing):
                assign[next((h for h in holders if f in self.held[sid][h]), "A")].append(f)
        elif self.policy == "reuse_adaptive":   # the Scenario B rule: probe max-min rate of a new flow, per-session load
            act = [(i, fl["src"], fl["dst"]) for i, fl in enumerate(self.flows)]
            cand = holders + ["A"]
            est = {c: max(1.0, maxmin(act + [("p", c, own)], self.caps)["p"]) for c in cand}
            load = {c: 0 for c in cand}
            for f in sorted(missing):
                opts = [c for c in cand if c == "A" or f in self.held[sid][c]]
                best = min(opts, key=lambda c: ((load[c] + 1) * FLEN / est[c], c == "A"))
                assign[best].append(f); load[best] += 1
        else:   # reuse_aware: balance providers' egress backlog (all sessions) over their egress caps; unavoidable source fragments first
            cand = holders + ["A"]
            load = {c: 0.0 for c in cand}
            for fl in self.flows:
                if fl["src"] in load:
                    load[fl["src"]] += len(fl["left"]) * FLEN
            only_a = [f for f in sorted(missing) if not any(f in self.held[sid][h] for h in holders)]
            for f in only_a:
                assign["A"].append(f); load["A"] += FLEN
            for f in sorted(set(missing) - set(only_a)):
                opts = [c for c in cand if c == "A" or f in self.held[sid][c]]
                best = min(opts, key=lambda c: ((load[c] + FLEN) / self.caps[("out", c)], c == "A"))
                assign[best].append(f); load[best] += FLEN
        for src, ids in assign.items():
            self.start(sid, src, own, ids)

    def move(self, sid):
        old = self.owner[sid]
        new = EDGES[(EDGES.index(old) + 1) % 3]
        self.owner[sid] = new; self.history[sid].append(new)
        self.restored[sid] = None
        self.plan(sid, "move")
        if len(self.held[sid][new]) == NFR:
            self.restored[sid] = self.t

    def run(self, horizon):
        for s in self.sids:
            self.plan(s, "start")
        sched = sorted((self.tm * (k + i / self.N), s) for i, s in enumerate(self.sids) for k in range(1, (self.moves or 10000) + 1)
                       if self.tm * (k + i / self.N) <= horizon)
        while self.t < horizon:
            while sched and sched[0][0] <= self.t + 1e-9:
                self.move(sched.pop(0)[1])
            if self.moves and all(self.restored[s] is not None for s in self.sids) and not sched:
                break
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
                        self.restored[fl["sid"]] = self.t + self.dt
                if not fl["left"]:
                    done_flows.append(fl)
            if done_flows:
                self.flows = [fl for fl in self.flows if fl not in done_flows]
                for fl in done_flows:
                    if fl["sid"] not in [d["sid"] for d in done_flows[:done_flows.index(fl)]]:
                        self.plan(fl["sid"], "flow_done")
            self.t += self.dt
        fin = [v for v in self.restored.values() if v is not None]
        return {"restored": len(fin), "makespan": max(fin) if len(fin) == self.N else None, "source_per_session": self.src_bytes / SINK_BYTES / self.N}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sessions", default="1,2,4")
    p.add_argument("--holder_mbps", default="125,250,500,1000")
    p.add_argument("--source_mbps", type=float, default=1000)
    p.add_argument("--in_mbps", type=float, default=1000)
    p.add_argument("--policies", default="restart,reuse_fixed,reuse_adaptive,reuse_aware")
    p.add_argument("--moves", type=int, default=1)
    p.add_argument("--ts", type=float, default=14.05)
    p.add_argument("--rho", type=float, default=2)
    a = p.parse_args()
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
