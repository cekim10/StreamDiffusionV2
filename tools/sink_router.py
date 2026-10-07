#!/usr/bin/env python3
"""Continuity-state (sink) routing model shared by the mobility prototype and its offline simulator.

The sink is a set of segments. Each edge holds a subset. Execution lives on one edge at a time and moves
along the path A -> B -> C -> ... Links carry one segment at a time at a fixed bandwidth. Policies decide
who forwards what to whom:
    restart    : only the source streams, always to the current edge, restarting from segment 0 at each move
    relay      : source streams to B; an edge forwards to its successor once it holds every segment
    relay_pipe : source streams to B; an edge forwards each segment to its successor as soon as it holds it
    split      : source streams the not-yet-sent segments to the current edge; every edge execution has left
                 forwards the segments it holds that the current edge lacks (claims prevent duplicates)
    direct     : source streams to the final edge (oracle)
The router is driven by a clock (`now`) and a sleeper (`sleep`) so the same code runs in real time inside
the destination process and in a fast offline simulation (tools/test_sink_router.py).
"""

from __future__ import annotations

import threading
import time

EDGE_NAMES = "ABCDEFGH"
POLICIES = ("restart", "relay", "relay_pipe", "split", "direct")


class Ingress:
    """Shared receive capacity of one edge: concurrent incoming flows get processor-sharing of `cap_bps`,
    each also bounded by its own link rate. cap_bps=None means every link is independent (unlimited ingress).
    A flow that is already paced by its sender's link (the real TCP stream from the source) only pays the
    EXTRA delay caused by sharing; emulated flows pay the full link time."""

    def __init__(self, cap_bps, link_bps: float, sleep):
        self.cap, self.link, self.sleep = cap_bps, link_bps, sleep
        self.lock = threading.Lock()
        self.active: set = set()

    def set_active(self, flow: str, on: bool):
        with self.lock:
            (self.active.add if on else self.active.discard)(flow)

    def rate(self) -> float:
        with self.lock:
            share = max(1, len(self.active))
        return self.link if self.cap is None else min(self.link, self.cap / share)

    def take(self, flow: str, nbytes: int, already_paced: bool = False, chunk: int = 16 << 20):
        remaining = nbytes
        self.set_active(flow, True)
        try:
            while remaining > 0:
                n = min(chunk, remaining)
                r = self.rate()
                t = n * 8 / r - (n * 8 / self.link if already_paced else 0.0)
                if t > 0:
                    self.sleep(t)
                remaining -= n
        finally:
            if not already_paced:
                self.set_active(flow, False)  # a sender-paced flow stays active until the caller says otherwise


class SinkRouter:
    def __init__(self, policy: str, edges: list[str], n_segments: int, seg_bytes: int, bw_bps: float,
                 now=time.time, sleep=time.sleep, on_bytes=None, ingress_mult=None):
        assert policy in POLICIES, policy
        self.policy, self.edges, self.L = policy, list(edges), n_segments
        self.seg_bytes, self.bw = seg_bytes, bw_bps
        self.now, self.sleep = now, sleep
        self.on_bytes = on_bytes or (lambda link, n: None)
        self.ingress_mult = ingress_mult
        self.ingress = {e: Ingress(None if ingress_mult is None else ingress_mult * bw_bps, bw_bps, sleep) for e in edges}
        self.lock = threading.Lock()
        self.holders = {e: set() for e in edges}
        self.claimed: dict[str, set] = {}
        self.idx = 0  # execution is on edges[idx]
        self.stop = False
        self.bytes: dict[str, int] = {}
        self.threads = [threading.Thread(target=self._forwarder, args=(e,), daemon=True) for e in edges]

    # ---- execution side
    @property
    def node(self):
        return self.edges[self.idx]

    def start(self):
        for t in self.threads:
            t.start()

    def move(self):
        """Execution moves to the next edge. Returns (old, new). restart drops the obsolete copy."""
        with self.lock:
            old = self.node
            self.idx += 1
            if self.policy == "restart":
                self.holders[old] = set()
            return old, self.node

    def source_take(self, dest: str, nbytes: int, already_paced: bool = False):
        """Pace the source's flow into `dest` through that edge's shared ingress (sleeps). With
        already_paced=True only the sharing penalty is applied and the flow stays marked active at `dest`
        until source_done()/source_switch() is called."""
        for e, ing in self.ingress.items():
            if e != dest:
                ing.set_active("A->" + e, False)
        if dest in self.ingress:
            self.ingress[dest].take("A->" + dest, nbytes, already_paced=already_paced)

    def source_done(self):
        for e, ing in self.ingress.items():
            ing.set_active("A->" + e, False)

    def deliver(self, dest: str, seg: int, nbytes: int):
        """A segment arrived from the source at `dest`."""
        with self.lock:
            if dest in self.holders:
                self.holders[dest].add(seg)
        self._account(f"A->{dest}", nbytes)

    def ready(self, edge: str | None = None) -> bool:
        edge = edge or self.node
        with self.lock:
            return len(self.holders[edge]) == self.L

    def finish(self):
        self.stop = True

    # ---- source side helpers (what the source should stream next, given the policy)
    def source_target(self, final_edge: str) -> str:
        return final_edge if self.policy == "direct" else ("B" if self.policy in ("relay", "relay_pipe") else self.node)

    # ---- forwarding
    def _account(self, link, n):
        self.bytes[link] = self.bytes.get(link, 0) + n
        self.on_bytes(link, n)

    def _target(self, holder: str):
        hi = self.edges.index(holder)
        if self.idx <= hi:
            return None
        if self.policy == "split":
            return self.node  # every edge execution has left forwards what it still holds to the current edge
        if self.policy in ("relay", "relay_pipe"):
            return self.edges[hi + 1]
        return None  # restart / direct never forward

    def _forwarder(self, holder: str):
        while not self.stop:
            tgt = self._target(holder)
            with self.lock:
                if tgt is None:
                    todo = []
                else:
                    complete = len(self.holders[holder]) == self.L
                    allowed = self.policy in ("relay_pipe", "split") or (self.policy == "relay" and complete)
                    todo = sorted(self.holders[holder] - self.holders[tgt] - self.claimed.setdefault(tgt, set())) if allowed else []
                if todo:
                    seg = todo[0]; self.claimed[tgt].add(seg)
            if not todo:
                self.sleep(0.01); continue
            self.ingress[tgt].take(f"{holder}->{tgt}", self.seg_bytes)  # link time, shared ingress at the target
            with self.lock:
                self.holders[tgt].add(seg); self.claimed[tgt].discard(seg)
            self._account(f"{holder}->{tgt}", self.seg_bytes)

    # ---- accounting
    def wasted_bytes(self, final_edge: str, source_bytes_by_dest: dict | None = None) -> int:
        obsolete = [e for e in self.edges if e != final_edge]
        if self.policy == "restart":
            src = source_bytes_by_dest or {k[3:]: v for k, v in self.bytes.items() if k.startswith("A->")}
            return sum(v for d, v in src.items() if d in obsolete)
        forwarded_from = {k.split("->")[0] for k in self.bytes if "->" in k and not k.startswith("A->")}
        with self.lock:
            return sum(len(self.holders[e]) for e in obsolete if e not in forwarded_from) * self.seg_bytes
