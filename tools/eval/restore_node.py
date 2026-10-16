#!/usr/bin/env python3
"""Network-level restoration node for Experiment 3 Scenario B (source-egress contention, many sessions).

No GPU and no model: this isolates Sink delivery from generation. Each session's Sink is a byte string of the
measured Sink size (1,725,236,640 B by default), split into fixed-size fragments exactly as in the GPU harness
(tools/eval/mobility_node.py), sent over the same MSS-capped TCP with the same framing, per-flow token buckets and
per-fragment SHA-256 verification. Fragment contents are deterministic pseudo-random bytes derived from
(session id, fragment id), so a holder can forward a fragment it verified without keeping 1.6 GiB per session in RAM:
the bytes on the wire are exactly the bytes it received. A fragment counts as held only after its SHA-256 matched the
source's digest; whole-Sink completion is all fragments verified (the Sink digest is the hash of the fragment hashes).

    python tools/eval/restore_node.py --label B --ctl_port 29831 --data_port 29832
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import struct
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "tools", REPO_ROOT / "tools" / "eval"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

from common import DEFAULT_MSS, MSS_WARNINGS, CsvLog, ResourceSampler, Throttle, clock_sync_server, effective_mss, host_info, tcp_accept, tcp_connect, tcp_listen  # noqa: E402
from proto_handoff import recv_exact, recv_msg, send_msg  # noqa: E402

POOL = ThreadPoolExecutor(max_workers=16)


class CountingThrottle(Throttle):
    """Per-flow token bucket that starts empty (no initial burst) and counts every paced byte into the node's
    0.25 s egress histogram, so the node's payload egress rate can be checked against its cap exactly."""

    def __init__(self, bw_bps, hist, lock):
        super().__init__(bw_bps)
        self.tokens = 0.0
        self.hist, self.hlock = hist, lock

    def take(self, n):
        super().take(n)
        k = int(time.time() * 4)
        with self.hlock:
            self.hist[k] = self.hist.get(k, 0) + n
MANIFEST_CACHE: dict = {}


def frag_bytes(sid: str, fid: int, n: int) -> bytes:
    seed = int.from_bytes(hashlib.sha256(f"{sid}/{fid}".encode()).digest()[:8], "little")
    return np.random.Generator(np.random.PCG64(seed)).bytes(n)


def frag_table(nbytes: int, fbytes: int) -> list[int]:
    lens, off = [], 0
    while off < nbytes:
        lens.append(min(fbytes, nbytes - off)); off += lens[-1]
    return lens


def _git_commit():
    try:
        import subprocess
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


class Node:
    def __init__(self, a):
        self.a, self.label, self.me = a, a.label, socket.gethostname()
        self.lock = threading.Lock()
        self.ctl = None
        self.ctl_lock = threading.Lock()
        self.sess: dict[str, dict] = {}       # sid -> {"lens", "hashes", "have": set, "complete_t"}
        self.flows: dict[str, dict] = {}
        # Commands run in separate threads, so a rate update or cancel can arrive before its FLOW_START.
        # Keep them and apply at start instead of dropping them (dropping let flows exceed their max-min share).
        self.pending_rate: dict[str, float] = {}
        self.pending_cancel: set = set()
        self.pending_add: dict[str, list] = {}   # FLOW_ADD that arrived before its FLOW_START
        self.stats = {"rate_before_start": 0, "cancel_before_start": 0, "add_before_start": 0}
        self.egress_hist: dict[int, int] = {}
        self.hist_lock = threading.Lock()
        self.run_dir = None
        self.frag_log = None
        self.sampler = None
        self.data_srv = tcp_listen(a.bind, a.data_port, a.mss)
        threading.Thread(target=self._accept_loop, daemon=True).start()

    # ---------------- control
    def send(self, kind, **f):
        with self.ctl_lock:
            send_msg(self.ctl, kind, {"label": self.label, **f}, b"", None)

    def serve(self):
        srv = tcp_listen(self.a.bind, self.a.ctl_port, self.a.mss)
        print(f"[{self.label}] {self.me}: control {self.a.ctl_port}, data {self.a.data_port}", flush=True)
        while True:
            self.ctl = tcp_accept(srv, self.a.mss)
            clock_sync_server(self.ctl)
            self.send("HELLO", host=self.me, host_info=host_info(None), mss_effective=effective_mss(self.ctl), mss_warnings=list(MSS_WARNINGS), pid=os.getpid(),
                      commit=_git_commit())
            try:
                while True:
                    hdr, _ = recv_msg(self.ctl)
                    if hdr["kind"] == "SHUTDOWN":
                        return
                    threading.Thread(target=self._dispatch, args=(hdr,), daemon=True).start()
            except (ConnectionError, OSError) as exc:
                print(f"[{self.label}] control lost: {exc}", flush=True)

    def _dispatch(self, hdr):
        try:
            out = getattr(self, "cmd_" + hdr["kind"].lower())(hdr) or {}
            self.send("REPLY", cmd_id=hdr.get("cmd_id"), ok=True, **out)
        except Exception as exc:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            self.send("REPLY", cmd_id=hdr.get("cmd_id"), ok=False, error=repr(exc))

    # ---------------- commands
    def cmd_run_begin(self, h):
        for fl in list(self.flows.values()):
            fl["cancel"] = True
        self.flows, self.sess = {}, {}
        self.pending_rate, self.pending_cancel, self.pending_add = {}, set(), {}
        self.stats = {"rate_before_start": 0, "cancel_before_start": 0, "add_before_start": 0}
        self.egress_hist = {}
        self.run_dir = REPO_ROOT / h["run_rel"] / f"node_{self.label}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.frag_log = CsvLog(self.run_dir / "fragments.csv", ["t", "event", "session", "fragment_id", "src", "dst", "bytes", "flow", "ok"])
        self.sampler = ResourceSampler(self.run_dir / "network.csv", self.me, None, self.a.iface)
        self.sampler.start()
        return {}

    def cmd_source_setup(self, h):
        """Source: create the sessions' fragment tables and digests (hash every fragment of every session)."""
        t0 = time.time()
        out = {}
        for sid in h["sessions"]:
            lens = frag_table(int(h["sink_bytes"]), int(h["frag_bytes"]))
            key = (sid, int(h["sink_bytes"]), int(h["frag_bytes"]))
            if key not in MANIFEST_CACHE:   # contents are deterministic in (session, fragment): hash once per process
                futs = [POOL.submit(lambda s=sid, i=i, n=n: hashlib.sha256(frag_bytes(s, i, n)).hexdigest()) for i, n in enumerate(lens)]
                MANIFEST_CACHE[key] = [f.result() for f in futs]
            hashes = MANIFEST_CACHE[key]
            digest = hashlib.sha256("".join(hashes).encode()).hexdigest()
            self.sess[sid] = {"lens": lens, "hashes": hashes, "have": set(range(len(lens))), "complete_t": t0, "digest": digest}
            out[sid] = {"lens": lens, "hashes": hashes, "digest": digest}
        return {"manifests": out, "setup_s": time.time() - t0}

    def cmd_manifests(self, h):
        for sid, m in h["manifests"].items():
            self.sess[sid] = {"lens": m["lens"], "hashes": m["hashes"], "digest": m["digest"], "have": set(), "complete_t": None}
        return {}

    def cmd_drop(self, h):
        """Restart semantics: forget a session's fragments at this node (the bytes are abandoned, not reused)."""
        with self.lock:
            s = self.sess.get(h["session"])
            if s is not None and self.label != "A":
                s["have"] = set(); s["complete_t"] = None
        return {}

    def cmd_flow_start(self, h):
        with self.lock:
            if h["flow_id"] in self.pending_cancel:
                self.pending_cancel.discard(h["flow_id"])
                self.send("FLOW_DONE", flow_id=h["flow_id"], session=h["session"], cancelled=True, sent=0, bytes=0, t=time.time())
                return {"cancelled_before_start": True}
            if h["flow_id"] in self.pending_rate:
                h["rate_bps"] = self.pending_rate.pop(h["flow_id"])
        # an open flow (closed=False) keeps its connection and waits for FLOW_ADD: fragments are forwarded as they are
        # verified here, which is what pipelined forwarding needs
        fl = {"id": h["flow_id"], "sid": h["session"], "dst": h["dst"], "host": h["dst_host"], "port": int(h["dst_port"]),
              "queue": list(h["frag_ids"]), "cancel": False, "closed": bool(h.get("closed", True)), "cond": threading.Condition(),
              "throttle": CountingThrottle(float(h["rate_bps"]), self.egress_hist, self.hist_lock) if float(h["rate_bps"]) > 0 else None,
              "lock": threading.Lock(), "sent": 0, "bytes": 0}
        with self.lock:
            for ids, closed in self.pending_add.pop(fl["id"], []):
                fl["queue"].extend(ids); fl["closed"] = fl["closed"] or closed
            self.flows[fl["id"]] = fl
        fl["thread"] = threading.Thread(target=self._sender, args=(fl,), daemon=True)
        fl["thread"].start()
        return {}

    def cmd_flow_add(self, h):
        """Append fragments to a running flow (and close it when closed=True); kept if the flow has not started yet."""
        with self.lock:
            fl = self.flows.get(h["flow_id"])
            if fl is None:
                self.pending_add.setdefault(h["flow_id"], []).append((list(h.get("frag_ids", [])), bool(h.get("closed", False))))
                self.stats["add_before_start"] += 1
                return {"pending": True}
        if not fl["thread"].is_alive():   # the flow already finished: the orchestrator must start a new flow for these fragments
            self.send("EVENT", event="flow_add_rejected", t=time.time(), flow=fl["id"], session=fl["sid"], dst=fl["dst"], frag_ids=list(h.get("frag_ids", [])))
            return {"rejected": True}
        with fl["cond"]:
            fl["queue"].extend(int(x) for x in h.get("frag_ids", []))
            if h.get("closed"):
                fl["closed"] = True
            fl["cond"].notify_all()
        return {}

    def cmd_flow_set_rate(self, h):
        with self.lock:
            fl = self.flows.get(h["flow_id"])
            if fl is None:
                self.pending_rate[h["flow_id"]] = float(h["rate_bps"]); self.stats["rate_before_start"] += 1
                return {"pending": True}
        rate = float(h["rate_bps"])
        with fl["lock"]:
            if fl["throttle"] is None:
                fl["throttle"] = CountingThrottle(rate, self.egress_hist, self.hist_lock) if rate > 0 else None
            else:
                fl["throttle"].rate = rate / 8.0
        return {}

    def cmd_flow_cancel(self, h):
        with self.lock:
            fl = self.flows.get(h["flow_id"])
            if fl is None:
                self.pending_cancel.add(h["flow_id"]); self.stats["cancel_before_start"] += 1
                return {"pending": True}
        fl["cancel"] = True
        fl["thread"].join(timeout=30)
        return {"sent": fl["sent"], "bytes": fl["bytes"]}

    def cmd_run_end(self, h):
        for fl in list(self.flows.values()):
            fl["cancel"] = True
        for fl in list(self.flows.values()):
            fl["thread"].join(timeout=30)
        if self.sampler:
            self.sampler.finish()
        if self.frag_log:
            self.frag_log.close()
        net = (self.run_dir / "network.csv").read_text() if self.run_dir and (self.run_dir / "network.csv").exists() else ""
        held = {sid: len(s["have"]) for sid, s in self.sess.items()}
        self.sess, self.flows = {}, {}
        hist = dict(self.egress_hist)
        def worst(nbins):  # worst window of nbins x 0.25 s of paced payload egress, Mbps
            if not hist:
                return 0.0
            ks = sorted(hist)
            return max(sum(hist.get(k + i, 0) for i in range(nbins)) * 8 / 1e6 / (nbins / 4) for k in range(ks[0], ks[-1] + 1))
        # Bytes are paced in 1 MiB chunks, so a 1 s window can over-count by about one chunk per active flow (8.4 Mbit);
        # the 10 s window bounds that quantization error to under 1 Mbps per flow and is the one validated.
        return {"held": held, "network_csv": net, "stats": dict(self.stats), "egress_worst_1s_mbps": worst(4), "egress_worst_10s_mbps": worst(40),
                "egress_hist_qs": {str(k): v for k, v in hist.items()}}

    # ---------------- data plane
    def _sender(self, fl):
        s = self.sess[fl["sid"]]
        try:
            conn = tcp_connect(fl["host"], fl["port"], self.a.mss, timeout=60)
        except Exception as exc:  # noqa: BLE001
            self.send("EVENT", event="flow_connect_failed", t=time.time(), flow=fl["id"], error=repr(exc)); return
        t_conn = time.time()
        self.send("EVENT", event="flow_connected", t=t_conn, flow=fl["id"])
        while not fl["cancel"]:
            with fl["cond"]:
                while not fl["queue"] and not fl["closed"] and not fl["cancel"]:
                    fl["cond"].wait(0.05)
                if not fl["queue"]:
                    break
                fid = int(fl["queue"].pop(0))
            with self.lock:
                held = fid in s["have"]
            if not held:
                self.send("FRAG_SKIP", flow_id=fl["id"], session=fl["sid"], fragment_id=fid, t=time.time()); continue
            n = s["lens"][fid]
            payload = frag_bytes(fl["sid"], fid, n)
            with fl["lock"]:
                thr = fl["throttle"]
            t0 = time.time()
            send_msg(conn, "FRAG", {"session": fl["sid"], "fragment_id": fid, "length": n, "sha256": s["hashes"][fid], "holder": self.label, "flow_id": fl["id"]}, payload, thr)
            t1 = time.time()
            fl["sent"] += 1; fl["bytes"] += n
            self.frag_log.row(t=f"{t1:.6f}", event="sent", session=fl["sid"], fragment_id=fid, src=self.label, dst=fl["dst"], bytes=n, flow=fl["id"], ok="")
            self.send("FRAG_SENT", flow_id=fl["id"], session=fl["sid"], fragment_id=fid, dst=fl["dst"], bytes=n, t_start=t0, t_end=t1)
        try:
            send_msg(conn, "FLOW_END", {"flow_id": fl["id"]}, b"", None); conn.close()
        except OSError:
            pass
        self.send("FLOW_DONE", flow_id=fl["id"], session=fl["sid"], cancelled=fl["cancel"], sent=fl["sent"], bytes=fl["bytes"], t=time.time())

    def _accept_loop(self):
        while True:
            c = tcp_accept(self.data_srv, self.a.mss)
            threading.Thread(target=self._receiver, args=(c,), daemon=True).start()

    def _receiver(self, conn):
        buf = bytearray(64 << 20)
        try:
            while True:
                hl, pl = struct.unpack("!QQ", bytes(recv_exact(conn, 16)))
                hdr = json.loads(bytes(recv_exact(conn, hl)).decode())
                if hdr["kind"] == "FLOW_END":
                    break
                t0 = time.time()
                view = recv_exact(conn, pl, buf)
                t1 = time.time()
                sid, fid = hdr["session"], int(hdr["fragment_id"])
                s = self.sess.get(sid)
                ok = s is not None and hashlib.sha256(view).hexdigest() == s["hashes"][fid] == hdr["sha256"]
                dup = False
                complete = False
                if ok:
                    with self.lock:
                        dup = fid in s["have"]
                        s["have"].add(fid)
                        if not dup and len(s["have"]) == len(s["lens"]) and s["complete_t"] is None:
                            s["complete_t"] = t1; complete = True
                self.frag_log.row(t=f"{t1:.6f}", event="recv", session=sid, fragment_id=fid, src=hdr["holder"], dst=self.label, bytes=pl, flow=hdr["flow_id"], ok=ok and not dup)
                self.send("FRAG_RECV", session=sid, fragment_id=fid, src=hdr["holder"], flow_id=hdr["flow_id"], bytes=pl, t_start=t0, t_end=t1, ok=ok, dup=dup)
                if complete:
                    # Sink digest = hash of the fragment hashes; every fragment was verified on arrival
                    d = hashlib.sha256("".join(s["hashes"]).encode()).hexdigest()
                    self.send("SINK_COMPLETE", session=sid, t=t1, digest_ok=d == s["digest"])
        except (ConnectionError, OSError):
            pass
        finally:
            conn.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--label", required=True)
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--ctl_port", type=int, default=29831)
    p.add_argument("--data_port", type=int, default=29832)
    p.add_argument("--mss", type=int, default=DEFAULT_MSS)
    p.add_argument("--iface", default=None)
    a = p.parse_args()
    a.mss = a.mss or None
    Node(a).serve()


if __name__ == "__main__":
    main()
