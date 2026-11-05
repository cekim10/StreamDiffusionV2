#!/usr/bin/env python3
"""Cluster-scale simulation of streaming-session migration (osdi/fig_cluster/preregistration.md). SIMULATED, calibrated
from measured single-migration records (tools/sim/calib.py -> osdi/fig_cluster/calibration.json).

Model (every constant from calibration.json; assumptions A1-A9 in the preregistration):
  sites      E edge sites on a grid, G GPU slots each (one session per GPU, as SDV2 on one L40S), uplink egress /
             ingress capacity C each, a non-blocking core; flows share links by weighted max-min (fluid), as the
             testbed's token buckets do; a host-memory budget M per site for retained / staged Sink versions (LRU)
  sessions   closed population N; exponential lifetimes; refresh intensity drawn from Fig. 5's 20 inputs; per-call
             time t_call; a session's age (calls) advances only while it is served
  events     user moves (grid random walk, exponential dwell), site drains (rate, duration), session end / start;
             the target is the user's site if it is up and has a slot, else the session's current site, else the
             nearest site with a slot (load fallback)
  methods    full      stop; transfer the whole state; resume
             pfull     Llumnix-style: rounds S, fS, fS while serving; final fS stopped
             rfull     ServerlessLLM-style: recompute calls 0..a0 while serving; stop; recompute the calls made meanwhile
             base      OTTER without staging: Sink base (full, or a delta against a version the target retained) + input
                       log / patches while serving; replay; readiness = max(start + floor, base done + tail); the last
                       `interruption` seconds before readiness are a stall; the old owner retains the version
             otter     base + staging: at every user move, forward Sink versions from non-owner holders to the candidate
                       sites (k nearest to the user, or every site in the testbed replay), versioned deltas
             naive     base migration + budgeted naive replication: at every user move the owner pushes full Sink copies
                       to the same candidates under the same budget; a copy is usable only if the Sink has not refreshed
                       since it was made
Service states per session: local (served at the user's site), remote (served elsewhere: migration in progress, or
displaced by load / drain), stall (no output).

    python tools/sim/cluster_sim.py validate                     # Fig. 7 fit + Fig. 11 hold-out gate
    python tools/sim/cluster_sim.py sweep --grid smoke           # small sweep (smoke test)
    python tools/sim/cluster_sim.py sweep --grid primary         # preregistered sweep (after the freeze)
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import json
import os
import math
import random
import statistics as st
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/evaluation/osdi/fig_cluster"
# OTTER_CAL selects another calibration file (2026-11-04: long-age check, E9 D5 / user G4); default = the frozen one
CAL = Path(os.environ.get("OTTER_CAL", str(OUT / "calibration.json")))
METHODS = ("full", "pfull", "rfull", "base", "otter", "naive")
STALL_X = (1.0, 2.0, 5.0, 10.0)


# ============================================================================== calibration
class Cal:
    def __init__(self, path=CAL):
        self.p = json.loads(Path(path).read_text())["params"]
        a = self.p["refresh_anchor"]
        self.r_lo, self.r_hi = a["dog"], a["bfly"]

    def _w(self, r):   # interpolation weight of the high-refresh anchor (log refresh intensity, clamped)
        r = min(max(r, self.r_lo), self.r_hi)
        return (math.log(r) - math.log(self.r_lo)) / (math.log(self.r_hi) - math.log(self.r_lo))

    def wl(self, name, r):
        w = self._w(r)
        return (1 - w) * self.p[f"{name}.dog"] + w * self.p[f"{name}.bfly"]

    def delta_bytes(self, r, age_calls):
        """Versioned base bytes against a version `age_calls` old (Fig. 10; linear in age between the measured ages,
        0 at age 0, extrapolated past 240 with the 150-240 slope, capped at the Sink) [A5]."""
        if age_calls <= 0:
            return 0.0
        S = self.p["otter.sink_bytes.dog"]

        def curve(w):
            pts = sorted((int(k), v) for k, v in self.p[f"otter.delta_bytes.{w}"].items())
            pts = [(0, 0.0)] + pts
            for (a0, b0), (a1, b1) in zip(pts, pts[1:]):
                if age_calls <= a1:
                    return b0 + (b1 - b0) * (age_calls - a0) / (a1 - a0)
            (a0, b0), (a1, b1) = pts[-2], pts[-1]
            return b1 + (b1 - b0) / (a1 - a0) * (age_calls - a1)

        w = self._w(r)
        return min(S, (1 - w) * curve("dog") + w * curve("bfly"))


# ============================================================================== event loop + fluid network
class Loop:
    def __init__(self):
        self.q, self.now, self.seq = [], 0.0, itertools.count()

    def at(self, t, fn, *args):
        heapq.heappush(self.q, (t, next(self.seq), fn, args))

    def run(self, t_end):
        while self.q and self.q[0][0] <= t_end:
            t, _, fn, args = heapq.heappop(self.q)
            self.now = t
            fn(*args)
        self.now = t_end


class Flow:
    __slots__ = ("fid", "links", "bits", "cap", "w", "rate", "done", "kind", "alive", "meta")

    def __init__(self, fid, links, bits, cap, w, done, kind):
        self.fid, self.links, self.bits, self.cap, self.w, self.done, self.kind = fid, links, bits, cap, w, done, kind
        self.rate, self.alive, self.meta = 0.0, True, None


class Net:
    """Weighted max-min fair fluid network over per-site egress / ingress links."""

    def __init__(self, loop, caps: dict, stats):
        self.loop, self.caps, self.stats = loop, caps, stats
        self.flows: dict[int, Flow] = {}
        self.ids, self.last, self.token = itertools.count(), 0.0, 0

    def add(self, src, dst, nbytes, done, kind, cap_Bps=None, w=1.0):
        self._advance()
        fid = next(self.ids)
        f = Flow(fid, (("out", src), ("in", dst)), max(nbytes, 0.0) * 8, None if cap_Bps is None else cap_Bps * 8, w, done, kind)
        self.flows[fid] = f
        self._realloc()
        return f

    def cancel(self, f):
        if f is not None and f.alive:
            self._advance()
            f.alive = False
            self.flows.pop(f.fid, None)
            self._realloc()

    def _advance(self):
        now = self.loop.now
        dt = now - self.last
        if dt > 0:
            for f in self.flows.values():
                f.bits -= f.rate * dt
            self.stats.net_interval(self.last, now, self.flows.values(), self.caps)
        self.last = now

    def _realloc(self):
        flows = [f for f in self.flows.values()]
        for f in flows:
            f.rate = 0.0
        resid = dict(self.caps)
        active = [f for f in flows if f.bits > 1e-6]
        for f in flows:
            if f.bits <= 1e-6:
                f.rate = 0.0
        while active:
            wsum = {}
            for f in active:
                for l in f.links:
                    wsum[l] = wsum.get(l, 0.0) + f.w
            x = min(resid[l] / ws for l, ws in wsum.items())
            capped = [f for f in active if f.cap is not None and f.cap / f.w <= x + 1e-12]
            if capped:
                x = min(f.cap / f.w for f in capped)
            sat = {l for l, ws in wsum.items() if resid[l] / ws <= x * (1 + 1e-9)}
            frozen = []
            for f in active:
                if (f.cap is not None and f.cap / f.w <= x * (1 + 1e-9)) or any(l in sat for l in f.links):
                    f.rate = f.w * x if f.cap is None else min(f.w * x, f.cap)
                    frozen.append(f)
            for f in frozen:
                for l in f.links:
                    resid[l] = max(0.0, resid[l] - f.rate)
            fz = set(id(f) for f in frozen)
            active = [f for f in active if id(f) not in fz]
        self.token += 1
        nxt = min(((f.bits / f.rate, f) for f in flows if f.rate > 0 and math.isfinite(f.bits)), default=None, key=lambda z: z[0])
        for f in flows:   # zero-byte flows finish now
            if f.bits <= 1e-6:
                self.loop.at(self.loop.now, self._finish, f, self.token)
        if nxt is not None:
            self.loop.at(self.loop.now + nxt[0], self._tick, self.token)

    def _tick(self, token):
        if token != self.token:
            return
        self._advance()
        done = [f for f in self.flows.values() if f.bits <= 1e-3 * max(1.0, f.rate)]
        for f in done:
            f.alive = False
            self.flows.pop(f.fid, None)
        self._realloc()
        for f in done:
            f.done()

    def _finish(self, f, token):
        if f.alive and f.bits <= 1e-6:
            self._advance()
            f.alive = False
            self.flows.pop(f.fid, None)
            self._realloc()
            f.done()


# ============================================================================== statistics (window [t0, t1])
class Stats:
    def __init__(self, t0, t1, E):
        self.t0, self.t1 = t0, t1
        self.state_t = {"local": 0.0, "remote": 0.0, "stall": 0.0}
        self.stalls, self.readiness, self.bytes = [], [], {}
        self.per_move = []   # (time without local service after a move, reached local service before the next move)
        self.peak_bps, self.bits_total = 0.0, 0.0
        self.util_hist = [0.0] * 21   # link-seconds per 5 % utilization bin
        self.mem_int = [0.0] * E
        self.mem_peak = [0.0] * E
        self.gpu_mig_s = 0.0
        self.migrations = {"started": 0, "completed": 0, "cancelled": 0, "base_delta": 0, "base_full": 0, "base_staged": 0}
        self.blocked_starts = 0
        self.session_s = 0.0

    def clip(self, a, b):
        return max(0.0, min(b, self.t1) - max(a, self.t0))

    def net_interval(self, a, b, flows, caps):
        d = self.clip(a, b)
        if d <= 0:
            return
        tot = 0.0
        use = {}
        for f in flows:
            tot += f.rate
            self.bytes[f.kind] = self.bytes.get(f.kind, 0.0) + f.rate * d / 8
            for l in f.links:
                use[l] = use.get(l, 0.0) + f.rate
        self.peak_bps = max(self.peak_bps, tot)
        self.bits_total += tot * d
        busy = 0
        for l, u in use.items():
            self.util_hist[min(20, int(20 * u / caps[l] + 1e-9))] += d
            busy += 1
        self.util_hist[0] += d * (len(caps) - busy)

    def mem_interval(self, a, b, site, nbytes):
        d = self.clip(a, b)
        if d > 0:
            self.mem_int[site] += nbytes * d
            self.mem_peak[site] = max(self.mem_peak[site], nbytes)

    def util_pct(self, q):
        tot = sum(self.util_hist)
        if tot <= 0:
            return 0.0
        acc = 0.0
        for i, v in enumerate(self.util_hist):
            acc += v
            if acc >= q * tot:
                return min(1.0, i / 20)
        return 1.0


# ============================================================================== cluster
class Store:
    """Retained / staged Sink versions at one site, LRU under a byte budget."""

    def __init__(self, sim, site, budget):
        self.sim, self.site, self.budget = sim, site, budget
        self.entries = {}   # sid -> [version_time, bytes, last_used]
        self.used, self.last = 0.0, 0.0

    def _account(self):
        now = self.sim.loop.now
        self.sim.stats.mem_interval(self.last, now, self.site, self.used)
        self.last = now

    def get(self, sid):
        e = self.entries.get(sid)
        if e:
            e[2] = self.sim.loop.now
        return e

    def put(self, sid, vtime, nbytes):
        if self.budget <= 0 or nbytes > self.budget:
            return False
        self._account()
        if sid in self.entries:
            self.used -= self.entries[sid][1]
        while self.used + nbytes > self.budget and self.entries:
            victim = min(self.entries, key=lambda k: self.entries[k][2])
            self.used -= self.entries.pop(victim)[1]
        self.entries[sid] = [vtime, nbytes, self.sim.loop.now]
        self.used += nbytes
        return True

    def drop(self, sid):
        if sid in self.entries:
            self._account()
            self.used -= self.entries.pop(sid)[1]


class Session:
    def __init__(self, sid, r, user, t_start, age0=0.0):
        self.sid, self.r, self.user, self.t_start, self.age0 = sid, r, user, t_start, age0
        self.owner = None
        self.mig = None
        self.state, self.since = "stall", t_start
        self.gen_s = 0.0          # served time (age advances only while served)
        self.move_t = t_start     # time of the user's latest move (TTFO-local clock)
        self.pending = None       # move time still waiting for local service
        self.refresh = []         # refresh times (naive staleness)
        self.staging = []         # in-flight staging flows of this session
        self.alive = True


class Sim:
    def __init__(self, cfg: dict, cal: Cal, method: str, seed: int):
        self.cfg, self.cal, self.method = cfg, cal, method
        self.rng = random.Random(seed)
        self.loop = Loop()
        E = cfg["E"]
        self.side = cfg.get("grid_w") or int(math.ceil(math.sqrt(E)))
        self.stats = Stats(cfg["T_warm"], cfg["T_end"], E)
        cap = cfg["C_gbps"] * 1e9
        self.net = Net(self.loop, {(d, s): cap for s in range(E) for d in ("out", "in")}, self.stats)
        self.store = [Store(self, s, cfg["M_gb"] * 1e9 if method in ("base", "otter", "naive") else 0.0) for s in range(E)]
        self.slots = [0] * E
        self.draining = [False] * E
        self.sessions: dict[int, Session] = {}
        self.waiting: list[int] = []
        self.displaced: set[int] = set()
        self._retrying = self._retry_again = False
        self.sids = itertools.count()
        self.refresh_pool = list(cal.p["refresh_per_100_calls"].values())

    # ---------------------------------------------------------------- topology
    def xy(self, s):
        return divmod(s, self.side)

    def dist(self, a, b):
        (ya, xa), (yb, xb) = self.xy(a), self.xy(b)
        return abs(ya - yb) + abs(xa - xb)

    def neighbors(self, s):
        y, x = self.xy(s)
        out = []
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (y + dy) * self.side + (x + dx)
            if 0 <= y + dy and 0 <= x + dx < self.side and n < self.cfg["E"]:
                out.append(n)
        return out

    def candidates(self, sess):
        """Staging candidates: k nearest sites to the user (ties by id), excluding the user's site and the owner."""
        k = self.cfg.get("k_stage", 4)
        sites = [s for s in range(self.cfg["E"]) if s not in (sess.user, sess.owner) and not self.draining[s]]
        sites.sort(key=lambda s: (self.dist(s, sess.user), s))
        return sites if k is None else sites[:k]

    # ---------------------------------------------------------------- helpers
    def tc(self, sess):
        return self.cal.wl("t_call_s", sess.r)

    def age(self, sess):
        g = sess.gen_s + ((self.loop.now - sess.since) if sess.state in ("local", "remote") else 0.0)
        return sess.age0 + g / self.tc(sess)

    def set_state(self, sess, st_):
        now = self.loop.now
        if sess.state in ("local", "remote"):
            sess.gen_s += now - sess.since
        if sess.state in self.stats.state_t:
            self.stats.state_t[sess.state] += self.stats.clip(sess.since, now)
        if sess.state == "stall" and st_ != "stall" and now > sess.since:
            if self.stats.t0 <= now <= self.stats.t1 or self.stats.clip(sess.since, now) > 0:
                self.stats.stalls.append(now - sess.since)
        if st_ == "local" and sess.pending is not None:
            if self.stats.t0 <= sess.pending <= self.stats.t1:
                self.stats.per_move.append((now - sess.pending, True))
            sess.pending = None
        sess.state, sess.since = st_, now

    def served_state(self, sess):
        return "local" if sess.owner == sess.user else "remote"

    def feasible(self, s, sess):
        return not self.draining[s] and (self.slots[s] < self.cfg["G"] or s == sess.owner or (sess.mig is not None and sess.mig["dst"] == s))

    def target(self, sess):
        if self.feasible(sess.user, sess):
            return sess.user
        if sess.owner is not None and not self.draining[sess.owner]:
            return sess.owner
        opts = [s for s in range(self.cfg["E"]) if self.feasible(s, sess)]
        return min(opts, key=lambda s: (self.dist(s, sess.user), s)) if opts else None

    # ---------------------------------------------------------------- session life
    def start_session(self, t_first=False):
        sid = next(self.sids)
        r = self.rng.choice(self.refresh_pool)
        user = self.rng.randrange(self.cfg["E"])
        sess = Session(sid, r, user, self.loop.now)
        self.sessions[sid] = sess
        tgt = self.target(sess)
        if tgt is None:
            self.stats.blocked_starts += 1
            self.waiting.append(sid)
        else:
            self.slots[tgt] += 1
            sess.owner = tgt
            self.set_state(sess, self.served_state(sess))
        life = self.rng.expovariate(1 / self.cfg["life_s"])
        self.loop.at(self.loop.now + life, self.end_session, sid)
        self.loop.at(self.loop.now + self.rng.expovariate(1 / self.cfg["dwell_s"]), self.move, sid)
        self.schedule_refresh(sess)

    def schedule_refresh(self, sess):
        rate = sess.r / 100 / self.tc(sess)   # refreshes per served second
        self.loop.at(self.loop.now + self.rng.expovariate(rate), self.on_refresh, sess.sid)

    def on_refresh(self, sid):
        sess = self.sessions.get(sid)
        if sess and sess.alive:
            if sess.state != "stall":
                sess.refresh.append(self.loop.now)
                sess.refresh = sess.refresh[-64:]
            self.schedule_refresh(sess)

    def end_session(self, sid):
        sess = self.sessions.pop(sid, None)
        if sess is None:
            return
        self.set_state(sess, "gone")
        sess.alive = False
        self.cancel_mig(sess, count=False)
        for f in sess.staging:
            self.net.cancel(f)
        for s in self.store:
            s.drop(sid)
        if sess.owner is not None:
            self.slots[sess.owner] -= 1
        if sid in self.waiting:
            self.waiting.remove(sid)
        self.stats.session_s += self.stats.clip(sess.t_start, self.loop.now)
        self.start_session()
        self.retry_waiting()

    def retry_waiting(self):
        if self._retrying:   # re-entered from a migration start / cancel below: the outer pass repeats
            self._retry_again = True
            return
        self._retrying = True
        try:
            self._retry_again = True
            while self._retry_again:
                self._retry_again = False
                self._retry_pass()
        finally:
            self._retrying = False

    def _retry_pass(self):
        # displaced sessions (served away from the user's site for lack of a slot or by a drain) move as soon as it can
        # take them
        for sid in list(self.displaced):
            sess = self.sessions.get(sid)
            if sess is None or sess.owner == sess.user or sess.owner is None:
                self.displaced.discard(sid)
            elif sess.mig is None and self.feasible(sess.user, sess):
                self.displaced.discard(sid)
                self.reconsider(sess)
        for sid in list(self.waiting):
            sess = self.sessions.get(sid)
            if sess is None:
                if sid in self.waiting:
                    self.waiting.remove(sid)
                continue
            if sess.owner is None:
                tgt = self.target(sess)
                if tgt is not None and sid in self.waiting:
                    self.waiting.remove(sid)
                    self.slots[tgt] += 1
                    sess.owner = tgt
                    self.set_state(sess, self.served_state(sess))
            elif sid in self.waiting:
                self.waiting.remove(sid)
                self.reconsider(sess)

    # ---------------------------------------------------------------- mobility / drain
    def move(self, sid):
        sess = self.sessions.get(sid)
        if sess is None:
            return
        nb = self.neighbors(sess.user)
        if sess.pending is not None and self.stats.t0 <= sess.pending <= self.stats.t1:
            self.stats.per_move.append((self.loop.now - sess.pending, False))
        sess.user = self.rng.choice(nb) if nb else sess.user
        sess.move_t = self.loop.now
        sess.pending = self.loop.now if sess.owner != sess.user else None
        self.loop.at(self.loop.now + self.rng.expovariate(1 / self.cfg["dwell_s"]), self.move, sid)
        if sess.owner is not None:
            if sess.state == "local" or sess.state == "remote":
                self.set_state(sess, self.served_state(sess))
            self.reconsider(sess)
            if self.method in ("otter", "naive"):
                self.stage(sess)

    def drain(self, site):
        self.draining[site] = True
        for sess in list(self.sessions.values()):
            if sess.owner == site or (sess.mig and sess.mig["dst"] == site):
                self.reconsider(sess)
        self.loop.at(self.loop.now + self.cfg["drain_s"], self.undrain, site)
        if self.cfg["drain_per_site_h"] > 0:
            self.loop.at(self.loop.now + self.rng.expovariate(self.cfg["drain_per_site_h"] / 3600), self.drain, site)

    def undrain(self, site):
        self.draining[site] = False
        for sess in list(self.sessions.values()):
            if sess.user == site:
                self.reconsider(sess)
        self.retry_waiting()

    # ---------------------------------------------------------------- migration control
    def reconsider(self, sess):
        tgt = self.target(sess)
        if sess.owner is None:   # not placed yet (blocked start): place it when a slot exists
            if tgt is not None:
                if sess.sid in self.waiting:
                    self.waiting.remove(sess.sid)
                self.slots[tgt] += 1
                sess.owner = tgt
                self.set_state(sess, self.served_state(sess))
            elif sess.sid not in self.waiting:
                self.waiting.append(sess.sid)
            return
        if tgt is not None and tgt != sess.user:
            self.displaced.add(sess.sid)
        if tgt is None:
            if sess.sid not in self.waiting:
                self.waiting.append(sess.sid)
            return
        if sess.mig is not None:
            if sess.mig["dst"] == tgt or sess.mig.get("committed"):
                return   # a migration in its stop / switch phase completes; the next one starts at its cutover [A9]
            self.cancel_mig(sess)
        if tgt == sess.owner:
            self.set_state(sess, self.served_state(sess))
            return
        self.start_mig(sess, tgt)

    def cancel_mig(self, sess, count=True):
        m = sess.mig
        if m is None:
            return
        m["alive"] = False
        for f in m["flows"]:
            self.net.cancel(f)
        self.slots[m["dst"]] -= 1
        self.stats.gpu_mig_s += self.stats.clip(m["t0"], self.loop.now)
        if count and self.stats.t0 <= self.loop.now <= self.stats.t1:
            self.stats.migrations["cancelled"] += 1
        sess.mig = None
        if sess.alive and sess.owner is not None:
            self.set_state(sess, self.served_state(sess))
        self.retry_waiting()

    def start_mig(self, sess, dst):
        self.slots[dst] += 1
        m = {"dst": dst, "src": sess.owner, "t0": self.loop.now, "flows": [], "alive": True, "pending": set(), "move_t": sess.move_t}
        sess.mig = m
        if self.stats.t0 <= self.loop.now <= self.stats.t1:
            self.stats.migrations["started"] += 1
        getattr(self, "mig_" + ("otter_like" if self.method in ("base", "otter", "naive") else self.method))(sess, m)

    def _flow(self, sess, m, nbytes, then, kind="migration", cap=None):
        def done():
            if m["alive"]:
                then()
        f = self.net.add(m["src"], m["dst"], nbytes, done, kind, cap)
        m["flows"].append(f)
        return f

    def _timer(self, sess, m, dt, then):
        def fire():
            if m["alive"]:
                then()
        self.loop.at(self.loop.now + max(0.0, dt), fire)

    def cutover(self, sess, m):
        m["alive"] = False
        for f in m["flows"]:
            self.net.cancel(f)
        old = sess.owner
        self.slots[old] -= 1
        sess.owner = m["dst"]
        sess.mig = None
        self.stats.gpu_mig_s += self.stats.clip(m["t0"], self.loop.now)
        if self.stats.t0 <= self.loop.now <= self.stats.t1:
            self.stats.migrations["completed"] += 1
            if sess.owner == sess.user:
                self.stats.readiness.append(self.loop.now - sess.move_t)
        self.set_state(sess, self.served_state(sess))
        if self.method in ("base", "otter", "naive"):
            self.store[old].put(sess.sid, self.loop.now, self.cal.p["otter.sink_bytes.dog"])
            self.store[sess.owner].drop(sess.sid)
        self.retry_waiting()
        if sess.owner != sess.user:
            self.reconsider(sess)

    # Full: stop, transfer the whole state, resume
    def mig_full(self, sess, m):
        self.set_state(sess, "stall")
        S, o = self.cal.wl("full.state_bytes", sess.r), self.cal.wl("full.overhead_s", sess.r)
        self._flow(sess, m, S, lambda: self._timer(sess, m, o, lambda: self.cutover(sess, m)))

    # Llumnix-style pre-copy of the whole state
    def mig_pfull(self, sess, m):
        S, f, e = self.cal.wl("full.state_bytes", sess.r), self.cal.wl("pfull.dirty_fraction", sess.r), self.cal.wl("pfull.efficiency", sess.r)
        o = max(0.0, self.cal.wl("pfull.final_overhead_s", sess.r))
        rounds = [S, f * S, f * S]

        def final():
            m["committed"] = True
            self.set_state(sess, "stall")
            self._flow(sess, m, f * S / e, lambda: self._timer(sess, m, o, lambda: self.cutover(sess, m)))

        def round_(i):
            if i == len(rounds):
                return final()
            self._flow(sess, m, rounds[i] / e, lambda: round_(i + 1))
        round_(0)

    # ServerlessLLM-style recompute from call 0
    def mig_rfull(self, sess, m):
        tc = self.tc(sess)
        a0 = self.age(sess)
        o1, o2 = self.cal.wl("rfull.round1_overhead_s", sess.r), max(0.0, self.cal.wl("rfull.finish_overhead_s", sess.r))
        ib = self.cal.wl("rfull.input_bytes_per_call", sess.r)
        m["pending"] = {"inputs", "compute"}
        t_start = self.loop.now

        def part(name):
            m["pending"].discard(name)
            if not m["pending"]:
                round1 = self.loop.now - t_start
                n = round1 / tc
                m["committed"] = True
                self.set_state(sess, "stall")
                self._flow(sess, m, n * ib, lambda: None)
                self._timer(sess, m, o2 + n * tc, lambda: self.cutover(sess, m))
        self._flow(sess, m, a0 * ib, lambda: part("inputs"))
        self._timer(sess, m, o1 + a0 * tc, lambda: part("compute"))

    # OTTER (base / otter / naive): Sink base + input log, replay, readiness
    def mig_otter_like(self, sess, m):
        r, now = sess.r, self.loop.now
        S = self.cal.p["otter.sink_bytes.dog"]
        e = self.cal.p["otter.efficiency.dog"]    # no-patch efficiency; patches are their own flow [A6]
        held = self.store[m["dst"]].get(sess.sid)
        # an in-flight staging flow of this session into the target completes first and is part of the base [A7]
        inflight = [f for f in sess.staging if f.alive and f.links[1] == ("in", m["dst"])]
        if inflight:
            held = [inflight[0].meta, None, now]
        if held is None:
            nbytes = S
            self.count_base("base_full")
        elif self.method == "naive":
            fresh = not any(t > held[0] for t in sess.refresh)
            nbytes = 0.0 if fresh else S
            self.count_base("base_staged" if fresh else "base_full")
        else:
            nbytes = self.cal.delta_bytes(r, (now - held[0]) / self.tc(sess))
            self.count_base("base_delta" if nbytes < S else "base_full")
        floor, tail, g = self.cal.wl("otter.floor_s", r), self.cal.wl("otter.tail_s", r), self.cal.wl("otter.interruption_s", r)
        ob = self.cal.wl("otter.base_overhead_s", r)
        self._flow(sess, m, float("inf"), lambda: None, kind="patch", cap=self.cal.wl("otter.patch_rate_Bps", r))
        m["pending"] = {"base"} | ({"staged"} if inflight else set())

        def ready():
            t_ready = max(m["t0"] + floor, self.loop.now + tail)
            def switch():
                m["committed"] = True
                self.set_state(sess, "stall")
                self._timer(sess, m, g, lambda: self.cutover(sess, m))
            self._timer(sess, m, t_ready - g - self.loop.now, switch)

        def part(name):
            m["pending"].discard(name)
            if not m["pending"]:
                ready()
        if inflight:
            m["wait_staged"] = inflight[0]
            inflight[0].done = (lambda prev: (lambda: (prev(), part("staged") if m["alive"] else None)))(inflight[0].done)
        self._timer(sess, m, ob, lambda: self._flow(sess, m, nbytes / e, lambda: part("base")))

    def count_base(self, k):
        if self.stats.t0 <= self.loop.now <= self.stats.t1:
            self.stats.migrations[k] += 1

    # ---------------------------------------------------------------- staging (otter: versioned forwarding; naive: full copies)
    def stage(self, sess):
        S = self.cal.p["otter.sink_bytes.dog"]
        e = self.cal.p["otter.efficiency.dog"]
        sess.staging = [f for f in sess.staging if f.alive]
        busy = {f.links[1][1] for f in sess.staging} | set(sess.__dict__.get("stage_dst", set()))
        for c in self.candidates(sess):
            if c in busy:
                continue
            have = self.store[c].get(sess.sid)
            if self.method == "otter":
                holders = [(self.store[h].entries[sess.sid][0], h) for h in range(self.cfg["E"])
                           if h != sess.owner and h != c and sess.sid in self.store[h].entries and not self.draining[h]]
                if not holders:
                    continue
                vt, h = max(holders)
                if have is not None and have[0] >= vt:
                    continue
                nbytes = S if have is None else self.cal.delta_bytes(sess.r, (vt - have[0]) / self.tc(sess))
                src = h
            else:
                if have is not None and not any(t > have[0] for t in sess.refresh):
                    continue
                vt, nbytes, src = self.loop.now, S, sess.owner
            sess.__dict__.setdefault("stage_dst", set()).add(c)
            self._stage_flow(sess, src, c, nbytes / e, vt, S)

    def _stage_flow(self, sess, src, dst, nbits_bytes, vt, S):
        """Staging flows of one session from one holder run one at a time, in plan order (the testbed planner sequences its
        flows, --m3_order) [A8]; a queued copy starts when the previous one from that holder ends."""
        q = sess.__dict__.setdefault("stage_q", {}).setdefault(src, [])

        def launch():
            def done():
                if sess.alive:
                    self.store[dst].put(sess.sid, vt, S)
                    sess.__dict__.get("stage_dst", set()).discard(dst)
                    q.pop(0)
                    if q:
                        q[0]()
            f = self.net.add(src, dst, nbits_bytes, done, "staging")
            f.meta = vt
            sess.staging.append(f)
        q.append(launch)
        if len(q) == 1:
            launch()

    # ---------------------------------------------------------------- run
    def run(self):
        cfg = self.cfg
        for _ in range(cfg["N"]):
            self.start_session()
        for sess in self.sessions.values():   # stagger ages: a session already running for a random part of its life
            sess.age0 = self.rng.expovariate(1 / cfg["life_s"]) / self.tc(sess)
        if cfg["drain_per_site_h"] > 0:
            for s in range(cfg["E"]):
                self.loop.at(self.rng.expovariate(cfg["drain_per_site_h"] / 3600), self.drain, s)
        self.loop.run(cfg["T_end"])
        for sess in list(self.sessions.values()):
            self.set_state(sess, sess.state)
            self.stats.session_s += self.stats.clip(sess.t_start, cfg["T_end"])
        self.net._advance()
        for s in self.store:
            s._account()
        return self.summary()

    def summary(self):
        S = self.stats
        tot = sum(S.state_t.values()) or 1.0
        win = S.t1 - S.t0
        hours = S.session_s / 3600 or 1.0
        out = {"method": self.method, "local_frac": S.state_t["local"] / tot, "remote_frac": S.state_t["remote"] / tot,
               "stall_frac": S.state_t["stall"] / tot,
               "stalls_per_session_h": {str(x): sum(1 for d in S.stalls if d > x) / hours for x in STALL_X},
               "stalled_s_per_session_h": S.state_t["stall"] / hours,   # D4: reported with the counts
               "migrations": S.migrations, "readiness_s": _q(S.readiness),
               "no_local_after_move_s": _q([d for d, _ in S.per_move]),
               "moves_reaching_local": sum(1 for _, ok in S.per_move if ok) / max(1, len(S.per_move)), "moves": len(S.per_move),
               "bytes_per_session_h_gb": {k: v / 1e9 / hours for k, v in S.bytes.items()},
               "peak_gbps": S.peak_bps / 1e9, "mean_gbps": S.bits_total / win / 1e9,
               "link_util_p99": S.util_pct(0.99), "link_util_p50": S.util_pct(0.5),
               "mem_site_mean_gb": sum(S.mem_int) / win / len(S.mem_int) / 1e9, "mem_site_peak_gb": max(S.mem_peak) / 1e9,
               "gpu_mig_s_per_session_h": S.gpu_mig_s / hours, "blocked_starts": S.blocked_starts, "session_h": hours}
        m = S.migrations
        out["reuse_ratio"] = (m["base_delta"] + m["base_staged"]) / max(1, m["base_delta"] + m["base_staged"] + m["base_full"])
        return out


def _q(xs):
    xs = sorted(xs)
    if not xs:
        return {"n": 0}
    pick = lambda p: xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))]  # noqa: E731
    return {"n": len(xs), "p50": pick(0.5), "p90": pick(0.9), "p99": pick(0.99), "mean": sum(xs) / len(xs)}


# ============================================================================== validation (testbed replay)
def replay_testbed(cal: Cal, method: str, wl: str, moves: list[float], horizon=300.0) -> dict:
    """One session on four sites A-D (1 Gbps), owner A, trigger at call 30, user A -> B at 0 then to C, D at `moves`;
    staging candidates = every site other than the user's and the owner (the testbed planner). Per edge change:
    time without local service, truncated at the next change; R_D at the final edge."""
    cfg = {"E": 4, "G": 1, "C_gbps": 1.0, "M_gb": 1e9, "N": 0, "T_warm": 0.0, "T_end": moves[-1] + horizon,
           "life_s": 1e12, "dwell_s": 1e12, "drain_per_site_h": 0, "drain_s": 0, "k_stage": None, "grid_w": 4}
    sim = Sim(cfg, cal, method, 0)
    r = cal.p["refresh_anchor"][wl]
    sess = Session(0, r, 0, 0.0, age0=30.0)
    sim.sessions[0] = sess
    sim.slots[0] = 1
    sess.owner = 0
    sim.set_state(sess, "local")
    sim.schedule_refresh(sess)
    times = [0.0] + moves
    local_at = {}
    orig = sim.cutover

    def cutover(s, m):
        orig(s, m)
        if s.owner == s.user:
            local_at.setdefault(s.user, sim.loop.now)
    sim.cutover = cutover

    def mv(site):
        sess.user, sess.move_t = site, sim.loop.now
        sim.set_state(sess, sim.served_state(sess)) if sess.state != "stall" else None
        sim.reconsider(sess)
        if method in ("otter", "naive"):
            sim.stage(sess)
    for i, t in enumerate(times):
        sim.loop.at(t, mv, i + 1)
    sim.loop.run(cfg["T_end"])
    sim.set_state(sess, sess.state)
    per = []
    for i, t in enumerate(times):
        nxt = times[i + 1] if i + 1 < len(times) else cfg["T_end"]
        la = local_at.get(i + 1)
        ttfo = None if la is None or la > nxt else la - t
        per.append({"edge": "BCD"[i], "ttfo_local_s": ttfo, "without_local_s": (ttfo if ttfo is not None else nxt - t)})
    stalls = sim.stats.stalls
    return {"per_move": per, "N_s": sum(p["without_local_s"] for p in per), "R_D_s": per[-1]["ttfo_local_s"],
            "max_gap_s": max(stalls) if stalls else 0.0}


def validate(cal: Cal, tol_rel=0.15, tol_abs=2.0) -> dict:
    """Gate: every held-out Fig. 11 quantity (per-move TTFO-local where completed, N, R_D) within max(tol_rel x measured,
    tol_abs) for every method / scenario / workload. Fig. 7 (calibration data) is reported as a fit check."""
    osdi = ROOT / "results/evaluation/osdi"
    f11 = json.loads((osdi / "fig11/fig11_results.json").read_text())["cells"]
    f7 = json.loads((osdi / "fig7/fig7_results.json").read_text())["cells"]
    name = {"full": "full", "pfull": "pfull", "rfull": "rfull", "base": "base", "otter": "otter"}
    sc = {"chain": [45.0, 90.0], "cancel": [48.0, 60.0]}
    rows, ok_all = [], True
    for cell, d in f11.items():
        scen, wl = cell.split("|")
        for meth, key in name.items():
            runs = d[key]["runs"]
            sim = replay_testbed(cal, meth, wl, sc[scen])
            meas = {"N_s": st.median(r["N_s"] for r in runs), "R_D_s": st.median(r["R_D_s"] for r in runs)}
            for i in range(3):
                vals = [r["per_move"][i]["ttfo_local_s"] for r in runs]
                if all(v is not None for v in vals):
                    meas[f"ttfo_{'BCD'[i]}"] = st.median(vals)
            for k, mv in meas.items():
                sv = sim[k] if k in sim else sim["per_move"]["BCD".index(k[-1])]["ttfo_local_s"]
                ok = sv is not None and abs(sv - mv) <= max(tol_rel * mv, tol_abs)
                ok_all &= ok
                rows.append({"cell": cell, "method": meth, "quantity": k, "measured": mv, "simulated": sv,
                             "err_rel": None if sv is None else (sv - mv) / mv, "pass": ok})
    fit = []
    for wl in ("dog", "bfly"):
        for meth, key in (("full", "full"), ("pfull", "precopy_full"), ("rfull", "recompute_full"), ("base", "precopy_replay")):
            sim = replay_testbed(cal, meth, wl, [1e5, 2e5], horizon=10)
            mv = f7[wl][key]["ttfo_local_s"]["median"]
            sv = sim["per_move"][0]["ttfo_local_s"]
            fit.append({"workload": wl, "method": meth, "measured": mv, "simulated": sv, "err_rel": (sv - mv) / mv if sv else None})
    return {"gate_pass": ok_all, "tolerance": {"rel": tol_rel, "abs_s": tol_abs}, "rows": rows, "fig7_fit": fit}


# ============================================================================== sweeps
GRIDS = {
    # smoke test: small cluster, short horizon, one seed
    "smoke": {"E": [16], "G": [4], "N": [48], "C_gbps": [1.0, 10.0], "M_gb": [0.0, 16.0], "dwell_s": [60.0, 180.0, 600.0],
              "seeds": [0], "T_end": 5400.0, "T_warm": 1800.0},
    # preregistered primary sweep (DRAFT; D-list): load, link, memory budget, mobility
    "primary": {"E": [16], "G": [8], "N": [32, 64, 96, 120], "C_gbps": [1.0, 10.0, 25.0], "M_gb": [0.0, 8.0, 32.0, 128.0],
                "dwell_s": [60.0, 180.0, 600.0], "seeds": [0, 1, 2], "T_end": 9000.0, "T_warm": 1800.0},
    # scalability extension (osdi/fig_cluster/scaling_protocol.md, DRAFT; not frozen). Same model, calibration and
    # horizon as "primary"; only the swept dimensions differ. Points shared with "primary" must reproduce it exactly.
    # L: load scaling, 128 GPUs (E 16 x G 8), N 16-120 (0.125-0.94 sessions per GPU), at the primary point and at 1 Gbps
    "load": {"E": [16], "G": [8], "N": [16, 32, 48, 64, 80, 96, 112, 120], "C_gbps": [10.0, 1.0], "M_gb": [32.0], "dwell_s": [180.0],
             "seeds": [0, 1, 2, 3, 4], "T_end": 9000.0, "T_warm": 1800.0},
    # S: cluster-size scaling, 16-128 GPUs (256 for the simulator's wall time only), sessions per GPU fixed at 0.5 / 0.94;
    # "points" = (E, G, N) triples instead of a product. scale = sites of 8 GPUs (E 2-32); scale_g4 = sites of 4 GPUs (E 4-64)
    "scale": {"points": [(E, 8, int(r * E * 8)) for E in (2, 4, 8, 16, 32) for r in (0.5, 0.94)],
              "C_gbps": [10.0], "M_gb": [32.0], "dwell_s": [180.0], "seeds": [0, 1, 2, 3, 4], "T_end": 9000.0, "T_warm": 1800.0},
    "scale_g4": {"points": [(E, 4, int(r * E * 4)) for E in (4, 8, 16, 32, 64) for r in (0.5, 0.94)],
                 "C_gbps": [10.0], "M_gb": [32.0], "dwell_s": [180.0], "seeds": [0, 1, 2, 3, 4], "T_end": 9000.0, "T_warm": 1800.0},
}
BASE_CFG = {"life_s": 1200.0, "drain_per_site_h": 0.1, "drain_s": 600.0, "k_stage": 4}


def sweep(grid: str, methods=METHODS, out: Path | None = None) -> list[dict]:
    g = GRIDS[grid]
    cal = Cal()
    keys = ("E", "G", "N", "C_gbps", "M_gb", "dwell_s")
    res = []
    t_wall = time.time()
    if "points" in g:   # (E, G, N) triples x the product of the other dimensions
        combos = [pt + rest for pt in g["points"] for rest in itertools.product(*(g[k] for k in keys[3:]))]
    else:
        combos = list(itertools.product(*(g[k] for k in keys)))
    for combo in combos:
        cfg = dict(BASE_CFG, **dict(zip(keys, combo)), T_end=g["T_end"], T_warm=g["T_warm"])
        for seed in g["seeds"]:
            for meth in methods:
                t0 = time.time()
                s = Sim(cfg, cal, meth, seed).run()
                s.update({"cfg": cfg, "seed": seed, "wall_s": time.time() - t0})
                res.append(s)
                print(f"  {meth:6s} N={cfg['N']:4d} C={cfg['C_gbps']:4g} M={cfg['M_gb']:5g} dwell={cfg['dwell_s']:5g} seed={seed}: "
                      f"local {s['local_frac']:.3f} remote {s['remote_frac']:.3f} stall {s['stall_frac']:.4f}; "
                      f">1s stalls/sess-h {s['stalls_per_session_h']['1.0']:.2f}, stalled {s['stalled_s_per_session_h']:.1f} s/sess-h; readiness p50 {s['readiness_s'].get('p50', float('nan')):.1f} s; "
                      f"peak {s['peak_gbps']:.1f} Gb/s; mem {s['mem_site_mean_gb']:.1f} GB; reuse {s['reuse_ratio']:.2f} [{s['wall_s']:.1f} s]")
    print(f"[sweep {grid}] {len(res)} runs in {time.time() - t_wall:.0f} s")
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"grid": grid, "grid_def": g, "base_cfg": BASE_CFG, "runs": res}, indent=1))
        print(f"-> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["validate", "sweep"])
    ap.add_argument("--grid", default="smoke", choices=list(GRIDS))
    ap.add_argument("--prefix", default="")
    a = ap.parse_args()
    if a.mode == "validate":
        v = validate(Cal())
        for r in v["rows"]:
            sv = "-" if r["simulated"] is None else f"{r['simulated']:7.1f}"
            print(f"  {'ok  ' if r['pass'] else 'MISS'} {r['cell']:12s} {r['method']:6s} {r['quantity']:8s} measured {r['measured']:7.1f} simulated {sv}"
                  + ("" if r["err_rel"] is None else f" ({100 * r['err_rel']:+.0f} %)"))
        for r in v["fig7_fit"]:
            print(f"  fit  fig7 {r['workload']:4s} {r['method']:6s} TTFO measured {r['measured']:6.1f} simulated {r['simulated']:6.1f} ({100 * r['err_rel']:+.0f} %)")
        print(f"[validate] gate {'PASS' if v['gate_pass'] else 'FAIL'}: {sum(r['pass'] for r in v['rows'])} / {len(v['rows'])} within tolerance")
        p = OUT / f"{a.prefix}validation.json"
        p.write_text(json.dumps(v, indent=1))
        print(f"-> {p.relative_to(ROOT)}")
    else:
        sweep(a.grid, out=OUT / f"{a.prefix}sweep_{a.grid}.json")


if __name__ == "__main__":
    main()
