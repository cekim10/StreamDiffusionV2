#!/usr/bin/env python3
"""Rate coordinator for concurrent sessions (osdi/concurrency/pilot_protocol.md, stage 2; P1 / P2 approved 2026-11-03).

One process on elves-01. Every orchestrator started with `--coord HOST:PORT` registers each transfer it starts (XB
pre-copy task, recompute input stream, Full state transfer, M3 forward) with its source and destination **site** (a
host: every node on a host shares that host's link) and gets its rate. The coordinator runs ONE max-min allocation over
the active flows of all sessions under per-site egress / ingress caps (`restore_planner.maxmin`, the allocation the
orchestrator already uses), so two sessions on one host really share its emulated link. Orchestrators poll their
flows' rates and push changes to their senders. Nothing about the methods changes: only who computes the rates.

Log (JSON lines, --log): every open / close with the full allocation after it, each site's allocated sum and a
`cap_ok` flag (sum <= cap at every allocation: verification 1 of the protocol), so flow overlap and sharing can be
reconstructed exactly (C4 flow-overlap evidence).

    elves-01:  python tools/eval/rate_coord.py serve --port 29960 --cap_mbps 1000 --log results/evaluation/osdi/concurrency/coord_<id>.jsonl
    any:       python tools/eval/rate_coord.py selftest
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from restore_planner import maxmin  # noqa: E402


def maxmin_demand(flows, caps, demand):
    """Max-min with per-flow demand ceilings (water-filling). A flow in `demand` stops at its demand; the others share
    what is left. With no demands this is `restore_planner.maxmin` itself (same code path, same rates)."""
    if not any(f in demand for f, _, _ in flows):
        return maxmin(flows, caps)
    rate = {f: 0.0 for f, _, _ in flows}
    resid = dict(caps)
    frozen = set()
    while len(frozen) < len(flows):
        act = [(f, s, d) for f, s, d in flows if f not in frozen]
        load = {}
        for _, s, d in act:
            load[("out", s)] = load.get(("out", s), 0) + 1; load[("in", d)] = load.get(("in", d), 0) + 1
        inc = min(resid[k] / n for k, n in load.items())
        dm = [demand[f] - rate[f] for f, _, _ in act if f in demand]
        if dm:
            inc = min(inc, min(dm))
        for f, _, _ in act:
            rate[f] += inc
        for k, n in load.items():
            resid[k] -= inc * n
        for f, s, d in act:
            if resid[("out", s)] <= 1e-3 or resid[("in", d)] <= 1e-3 or (f in demand and rate[f] >= demand[f] - 1e-3):
                frozen.add(f)
    return rate


def pacer_rates(flows, caps, acc, demand):
    """Sender pacer rates. A flow without a demand is paced at its accounted max-min rate. A flow with a demand (a
    transfer whose bulk is sent and that only streams its small tail: replay log, refresh patches, between input parts)
    is accounted at its demand but paced at the residual capacity of its path (cap minus the other flows' accounted
    rates), so a lone tail flow keeps the whole cap exactly as today, and a tail never holds capacity it does not use."""
    out = dict(acc)
    for f, s, d in flows:
        if f in demand:
            o = sum(acc[g] for g, s2, _ in flows if g != f and s2 == s)
            i = sum(acc[g] for g, _, d2 in flows if g != f and d2 == d)
            out[f] = max(acc[f], min(caps[("out", s)] - o, caps[("in", d)] - i))
    return out


class Coordinator:
    def __init__(self, cap_bps: float, log: Path | None = None):
        self.cap = float(cap_bps)
        self.flows: dict[str, dict] = {}     # global id "session/flow" -> {session, id, src, dst, kind, t_open}
        self.rates: dict[str, float] = {}   # pacer rates (what senders use)
        self.acc: dict[str, float] = {}     # accounted rates (what the cap check sums); = rates for flows without a demand
        self.version = 0
        self.lock = threading.Lock()
        self.logf = open(log, "a") if log else None
        self.n_violations = 0

    def _caps(self):
        sites = {f["src"] for f in self.flows.values()} | {f["dst"] for f in self.flows.values()}
        return {(d, s): self.cap for s in sites for d in ("out", "in")}

    def _alloc(self, op: str, gid: str):
        fl = [(g, f["src"], f["dst"]) for g, f in self.flows.items()]
        dem = {g: f["demand_bps"] for g, f in self.flows.items() if f.get("demand_bps") is not None}
        caps = self._caps()
        self.acc = maxmin_demand(fl, caps, dem) if self.flows else {}
        self.rates = pacer_rates(fl, caps, self.acc, dem) if self.flows else {}
        self.version += 1
        load = {}
        for g, f in self.flows.items():
            for k in (("out", f["src"]), ("in", f["dst"])):
                load[k] = load.get(k, 0.0) + self.acc[g]
        ok = all(v <= self.cap * (1 + 1e-9) + 1.0 for v in load.values())
        self.n_violations += not ok
        if self.logf:
            self.logf.write(json.dumps({"t": time.time(), "op": op, "flow": gid, "version": self.version, "cap_bps": self.cap, "cap_ok": ok,
                                        "flows": {g: {**self.flows[g], "rate_bps": self.rates[g], "acc_bps": self.acc[g]} for g in self.flows},
                                        "site_load_bps": {f"{d}:{s}": v for (d, s), v in load.items()}}) + "\n")
            self.logf.flush()

    def handle(self, req: dict) -> dict:
        op = req.get("op")
        with self.lock:
            if op == "hello":
                if abs(float(req["cap_bps"]) - self.cap) > 1.0:
                    return {"ok": False, "error": f"cap mismatch: coordinator {self.cap:.0f} bps, session {req['cap_bps']}"}
                return {"ok": True, "cap_bps": self.cap}
            if op == "open":
                gid = f"{req['session']}/{req['id']}"
                self.flows[gid] = {"session": req["session"], "id": req["id"], "src": req["src"], "dst": req["dst"], "kind": req.get("kind"),
                                   "t_open": time.time(), "demand_bps": None}
                self._alloc("open", gid)
                return {"ok": True, "rate_bps": self.rates[gid], "version": self.version}
            if op == "demand":   # work-conserving registration: a demand (bps) = bulk sent, tail only; None = bulk again
                gid = f"{req['session']}/{req['id']}"
                if gid not in self.flows:
                    return {"ok": False, "error": f"unknown flow {gid}"}
                d = req.get("demand_bps")
                self.flows[gid]["demand_bps"] = None if d is None else float(d)
                self._alloc("tail" if d is not None else "bulk", gid)
                return {"ok": True, "rate_bps": self.rates[gid], "version": self.version}
            if op == "close":
                gid = f"{req['session']}/{req['id']}"
                if self.flows.pop(gid, None) is not None:
                    self._alloc("close", gid)
                return {"ok": True, "version": self.version}
            if op == "rates":
                s = req["session"]
                return {"ok": True, "version": self.version, "rates": {f["id"]: self.rates[g] for g, f in self.flows.items() if f["session"] == s}}
            if op == "status":
                return {"ok": True, "version": self.version, "n_flows": len(self.flows), "violations": self.n_violations}
        return {"ok": False, "error": f"unknown op {op}"}


def serve(a):
    co = Coordinator(a.cap_mbps * 1e6, Path(a.log) if a.log else None)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((a.bind, a.port)); srv.listen(16)
    print(f"[coord] serving on {a.bind}:{a.port}, cap {a.cap_mbps:g} Mbps per site and direction, log {a.log or '-'}", flush=True)

    def conn_loop(c):
        f = c.makefile("rwb")
        try:
            for line in f:
                out = co.handle(json.loads(line))
                f.write((json.dumps(out) + "\n").encode()); f.flush()
        except (OSError, ValueError):
            pass
        finally:
            c.close()
    while True:
        c, _ = srv.accept()
        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=conn_loop, args=(c,), daemon=True).start()


class CoordClient:
    """Orchestrator side: one connection, synchronous requests."""

    def __init__(self, addr: str, session: str, cap_bps: float):
        host, port = addr.rsplit(":", 1)
        self.sock = socket.create_connection((host, int(port)), timeout=30)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.f = self.sock.makefile("rwb")
        self.session = session
        self.lock = threading.Lock()
        r = self.req(op="hello", cap_bps=cap_bps)
        if not r.get("ok"):
            raise SystemExit(f"[coord] {r.get('error')}")

    def req(self, **kw) -> dict:
        with self.lock:
            self.f.write((json.dumps({"session": self.session, **kw}) + "\n").encode()); self.f.flush()
            return json.loads(self.f.readline())

    def open(self, fid, src, dst, kind) -> float:
        return float(self.req(op="open", id=fid, src=src, dst=dst, kind=kind)["rate_bps"])

    def close(self, fid):
        self.req(op="close", id=fid)

    def demand(self, fid, demand_bps) -> float:
        return float(self.req(op="demand", id=fid, demand_bps=demand_bps)["rate_bps"])

    def rates(self) -> tuple[int, dict]:
        r = self.req(op="rates")
        return r["version"], r["rates"]


def selftest():
    """Shared-cap and equivalence checks on synthetic flow sets (no network)."""
    cap = 1e9
    co = Coordinator(cap)
    ok = True
    # one session, one flow: the whole cap (= today's static XB rate min(out cap, in cap))
    r = co.handle({"op": "open", "session": "s1", "id": "x1", "src": "h1", "dst": "h3", "kind": "precopy"})["rate_bps"]
    ok &= abs(r - cap) < 1; print(f"  {'ok' if abs(r - cap) < 1 else 'FAIL'} single flow gets the cap ({r / 1e6:.0f} Mbps)")
    # a second session on the same source and destination sites: half each, sum = cap
    co.handle({"op": "open", "session": "s2", "id": "x1", "src": "h1", "dst": "h3", "kind": "precopy"})
    rs = {**{f"s1/{k}": v for k, v in co.handle({"op": "rates", "session": "s1"})["rates"].items()},
          **{f"s2/{k}": v for k, v in co.handle({"op": "rates", "session": "s2"})["rates"].items()}}
    good = all(abs(v - cap / 2) < 1 for v in rs.values())
    ok &= good; print(f"  {'ok' if good else 'FAIL'} two sessions sharing h1 egress / h3 ingress: {[round(v / 1e6) for v in rs.values()]} Mbps")
    # a third flow on another destination from the shared source: egress h1 split three ways, max-min
    co.handle({"op": "open", "session": "s2", "id": "m3f1", "src": "h1", "dst": "h4", "kind": "m3"})
    st_ = co.handle({"op": "status", "session": "s1"})
    good = st_["violations"] == 0
    ok &= good; print(f"  {'ok' if good else 'FAIL'} site sums never above the cap ({st_['violations']} violations)")
    # close: the remaining flows get the freed share back
    co.handle({"op": "close", "session": "s2", "id": "x1"}); co.handle({"op": "close", "session": "s2", "id": "m3f1"})
    r = co.handle({"op": "rates", "session": "s1"})["rates"]["x1"]
    good = abs(r - cap) < 1
    ok &= good; print(f"  {'ok' if good else 'FAIL'} after the others close, the remaining flow gets the cap back ({r / 1e6:.0f} Mbps)")
    # work-conserving registration (formal design F1): a flow whose bulk is sent only reserves its tail demand
    co = Coordinator(cap)
    for sess in ("s1", "s2"):
        co.handle({"op": "open", "session": sess, "id": "x1", "src": "h1", "dst": "h3", "kind": "precopy"})
    r2 = co.handle({"op": "demand", "session": "s1", "id": "x1", "demand_bps": 100e6})["rate_bps"]
    r_s2 = co.handle({"op": "rates", "session": "s2"})["rates"]["x1"]
    good = abs(r_s2 - 900e6) < 1 and abs(r2 - 100e6) < 1 and co.n_violations == 0
    ok &= good; print(f"  {'ok' if good else 'FAIL'} s1 in its tail (demand 100 Mbps): s2 {r_s2 / 1e6:.0f} Mbps, s1 paced {r2 / 1e6:.0f} Mbps, accounted sum <= cap")
    co.handle({"op": "close", "session": "s2", "id": "x1"})
    r1 = co.handle({"op": "rates", "session": "s1"})["rates"]["x1"]
    good = abs(r1 - cap) < 1
    ok &= good; print(f"  {'ok' if good else 'FAIL'} a lone tail flow is paced at the whole cap, as today ({r1 / 1e6:.0f} Mbps)")
    co.handle({"op": "open", "session": "s2", "id": "x2", "src": "h1", "dst": "h3", "kind": "precopy"})
    r_b = co.handle({"op": "demand", "session": "s1", "id": "x1", "demand_bps": None})["rate_bps"]
    r_s2 = co.handle({"op": "rates", "session": "s2"})["rates"]["x2"]
    good = abs(r_b - cap / 2) < 1 and abs(r_s2 - cap / 2) < 1
    ok &= good; print(f"  {'ok' if good else 'FAIL'} back to bulk (new round / input part): {r_b / 1e6:.0f} / {r_s2 / 1e6:.0f} Mbps")
    fl = [("a", "h1", "h3"), ("b", "h1", "h4"), ("c", "h2", "h3")]
    caps = {(d, h): cap for h in ("h1", "h2", "h3", "h4") for d in ("out", "in")}
    good = maxmin_demand(fl, caps, {}) == maxmin(fl, caps)
    ok &= good; print(f"  {'ok' if good else 'FAIL'} without demands the allocation is restore_planner.maxmin exactly")
    print("ALL PASS" if ok else "FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--bind", default="127.0.0.1"); s.add_argument("--port", type=int, default=29960)
    s.add_argument("--cap_mbps", type=float, default=1000.0); s.add_argument("--log", default="")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "serve":
        serve(a)
    else:
        sys.exit(0 if selftest() else 1)


if __name__ == "__main__":
    main()
