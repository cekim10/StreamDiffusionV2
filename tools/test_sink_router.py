#!/usr/bin/env python3
"""Offline simulation of the sink routing policies (no GPU, no sockets). Runs the real SinkRouter with
scaled-down time: a 1.6 GB sink of 30 segments at '1 Gbps' takes 13.8 s of link time; here time runs 100x
faster. Checks the qualitative expectations before any server run:
    restart : ready at final = last move + T_s ; wasted grows with moves
    relay   : chain, ready at final ~ hops * T_s ; no waste
    relay_pipe : ready at final ~ T_s + (hops-1) * segment time ; traffic hops * sink
    split   : ready at final ~ max(T_s, ...) close to direct ; no waste ; traffic < relay_pipe
    direct  : ready at final = T_s (oracle)
Usage: python tools/test_sink_router.py
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sink_router import POLICIES, SinkRouter  # noqa: E402

SCALE = 100.0  # simulated seconds per real second
SEG = 55 * 1024 * 1024
L = 30
BW = 1e9
T_SEG = SEG * 8 / BW  # 0.46 s simulated per segment
T_S = L * T_SEG       # 13.8 s


class Clock:
    def __init__(self):
        self.t0 = time.perf_counter()

    def now(self):
        return (time.perf_counter() - self.t0) * SCALE

    def sleep(self, s):
        time.sleep(s / SCALE)


def source_thread(router: SinkRouter, final_edge: str, clock: Clock, log: dict):
    """Mimics run_source: streams segments at BW to the policy's target, reacting to moves."""
    policy = router.policy
    sent_by_dest = {}

    def send(dest, seg):
        clock.sleep(T_SEG)
        router.deliver(dest, seg, SEG)
        sent_by_dest[dest] = sent_by_dest.get(dest, 0) + SEG

    if policy == "direct":
        for s in range(L):
            send(final_edge, s)
    elif policy in ("relay", "relay_pipe"):
        for s in range(L):
            send("B", s)
    elif policy == "restart":
        while True:
            dest = router.node; seen_idx = router.idx
            s = 0; aborted = False
            while s < L:
                if router.idx != seen_idx:
                    aborted = True; break
                send(dest, s); s += 1
            if aborted:
                continue
            if dest == final_edge:
                break
            while router.idx == seen_idx and not router.stop:  # wait for the next move
                clock.sleep(0.05)
            if router.stop:
                break
    elif policy == "split":
        s = 0
        while s < L:
            send(router.node, s); s += 1
    log["source_bytes_by_dest"] = sent_by_dest


def run(policy: str, hops: int, t_m: float) -> dict:
    edges = [chr(ord("A") + i) for i in range(1, hops + 1)]
    final = edges[-1]
    clock = Clock()
    router = SinkRouter(policy, edges, L, SEG, BW, now=clock.now, sleep=clock.sleep)
    router.start()
    log = {}
    th = threading.Thread(target=source_thread, args=(router, final, clock, log), daemon=True)
    th.start()
    ready = {}
    moves = []
    horizon = 80.0
    while clock.now() < horizon:
        if router.idx < hops - 1 and clock.now() >= t_m * (router.idx + 1):
            old, new = router.move(); moves.append((old, new, round(clock.now(), 1)))
        node = router.node
        if node not in ready and router.ready(node):
            ready[node] = round(clock.now(), 1)
        if final in ready and (policy != "restart" or not th.is_alive()):
            break
        clock.sleep(0.1)
    router.finish(); th.join(timeout=2)
    return {"policy": policy, "hops": hops, "t_m": t_m, "moves": moves, "ready": ready,
            "ready_final": ready.get(final), "wasted_mb": router.wasted_bytes(final, log.get("source_bytes_by_dest")) / 2**20,
            "traffic_mb": {k: round(v / 2**20) for k, v in router.bytes.items()}, "total_mb": round(sum(router.bytes.values()) / 2**20)}


def main():
    rows = []
    for hops, t_m in ((3, 2.0), (2, 24.0)):
        for pol in POLICIES:
            r = run(pol, hops, t_m); rows.append(r)
            print(f"{pol:10s} hops={hops} T_m={t_m:g}: moves {r['moves']} ready {r['ready']} final {r['ready_final']} wasted {r['wasted_mb']:.0f} MB total {r['total_mb']} MB links {r['traffic_mb']}")
    by = {(r["policy"], r["hops"], r["t_m"]): r for r in rows}
    # hops=3, T_m=2 expectations (simulated seconds; T_s = 13.8)
    d, s, rp, rl, rs = (by[(p, 3, 2.0)] for p in ("direct", "split", "relay_pipe", "relay", "restart"))
    assert d["ready_final"] is not None and abs(d["ready_final"] - T_S) < 1.5, d
    assert s["ready_final"] is not None and s["ready_final"] <= d["ready_final"] + 1.5, ("split should match direct", s)
    assert s["wasted_mb"] == 0 and rp["wasted_mb"] == 0 and rl["wasted_mb"] == 0
    assert rp["ready_final"] is not None and rp["ready_final"] < rl["ready_final"] if rl["ready_final"] else True
    assert rl["ready_final"] is not None and rl["ready_final"] > 2.5 * T_S, ("relay chain should accumulate ~3 T_s", rl)
    assert rs["ready_final"] is not None and rs["ready_final"] > d["ready_final"] + 2 and rs["wasted_mb"] > 0, rs
    assert s["total_mb"] < rp["total_mb"], ("split should use less traffic than pipelined relay", s["total_mb"], rp["total_mb"])
    # hops=2, T_m=24 (rho < 1): B ready before the move for every non-direct policy; relay then forwards once
    for p in ("relay", "relay_pipe", "split", "restart"):
        r = by[(p, 2, 24.0)]
        assert r["ready"].get("B") is not None and r["ready"]["B"] < 24.0, (p, r)
    assert by[("relay", 2, 24.0)]["ready_final"] is not None and by[("relay", 2, 24.0)]["ready_final"] < 24 + T_S + 3.0  # +3 s: sleep overhead at 100x time scale
    print("\nSINK ROUTER SIM OK")


if __name__ == "__main__":
    main()
