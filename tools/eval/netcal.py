#!/usr/bin/env python3
"""Phase 0: physical network calibration between elves hosts over the evaluation transport
(plain TCP, MSS-capped). Measures application throughput per flow and aggregate ingress/egress for the
concurrency patterns used later by the routing experiments.

Roles:
  receiver: python tools/eval/netcal.py --role receiver --port 29800 --flows N --out <dir>
  sender  : python tools/eval/netcal.py --role sender --host <receiver> --port 29800 --bytes 1073741824 --out <dir>
Each flow writes one JSON record; tools/eval/run_netcal.sh orchestrates patterns and repetitions and
tools/eval/aggregate_netcal.py builds results/evaluation/network_calibration.csv.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_MSS, MSS_WARNINGS, ResourceSampler, Throttle, effective_mss, host_info, tcp_accept, tcp_connect, tcp_listen, write_json  # noqa: E402

CHUNK = 1 << 20


def recv_flow(conn: socket.socket, idx: int, out: Path, tag: str):
    hdr = conn.recv(16, socket.MSG_WAITALL)
    nbytes, sender_t0 = struct.unpack("!Qd", hdr)
    buf = bytearray(4 << 20)
    got = 0
    t_first = time.time()
    while got < nbytes:
        n = conn.recv_into(buf, min(len(buf), nbytes - got))
        if n == 0:
            break
        got += n
    t_end = time.time()
    conn.sendall(struct.pack("!d", t_end))
    peer = conn.getpeername()[0]
    rec = {"role": "receiver", "flow": idx, "tag": tag, "peer": peer, "host": socket.gethostname(), "bytes": got, "bytes_expected": nbytes,
           "t_first_byte": t_first, "t_end": t_end, "sender_t0_raw": sender_t0, "recv_seconds": t_end - t_first,
           "mbps_app": got * 8 / max(1e-9, t_end - t_first) / 1e6, "mss": effective_mss(conn), "mss_warnings": list(MSS_WARNINGS)}
    write_json(out / f"recv_flow{idx}_{peer}_{int(t_end)}.json", rec)
    print(json.dumps(rec), flush=True)
    conn.close()


def run_receiver(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    write_json(out / "host_info_receiver.json", host_info())
    srv = tcp_listen("0.0.0.0", a.port, a.mss)
    samp = ResourceSampler(out / f"network_receiver_{socket.gethostname()}.csv", socket.gethostname(), None, a.iface)
    samp.start()
    print(f"[netcal] receiver listening on {a.port}, expecting {a.flows} flows, mss={a.mss}", flush=True)
    threads = []
    for i in range(a.flows):
        c = tcp_accept(srv, a.mss)
        th = threading.Thread(target=recv_flow, args=(c, i, out, a.tag)); th.start(); threads.append(th)
    for th in threads:
        th.join()
    samp.finish(); srv.close()
    print("[netcal] receiver done", flush=True)


def run_sender(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    write_json(out / f"host_info_sender_{socket.gethostname()}.json", host_info())
    payload = memoryview(bytearray(os.urandom(CHUNK)))  # incompressible 1 MiB block, reused
    s = tcp_connect(a.host, a.port, a.mss)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8 << 20)
    t0 = time.time()
    s.sendall(struct.pack("!Qd", a.bytes, t0))
    sent = 0
    throttle = Throttle(a.bw_mbps * 1e6) if a.bw_mbps and a.bw_mbps > 0 else None
    while sent < a.bytes:
        n = min(CHUNK, a.bytes - sent)
        if throttle:
            throttle.take(n)
        s.sendall(payload[:n]); sent += n
    t_sent = time.time()
    t_recv_end = struct.unpack("!d", s.recv(8, socket.MSG_WAITALL))[0]
    t_ack = time.time()
    rec = {"role": "sender", "tag": a.tag, "host": socket.gethostname(), "peer": a.host, "bytes": sent, "t0": t0, "t_sent": t_sent, "t_ack": t_ack,
           "send_seconds": t_sent - t0, "ack_seconds": t_ack - t0, "mbps_app_ack": sent * 8 / max(1e-9, t_ack - t0) / 1e6,
           "mss": effective_mss(s), "bw_mbps_cap": a.bw_mbps, "mss_warnings": list(MSS_WARNINGS)}
    write_json(out / f"send_{socket.gethostname()}_to_{a.host}_{int(t0)}.json", rec)
    print(json.dumps(rec), flush=True)
    s.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--role", choices=["receiver", "sender"], required=True)
    p.add_argument("--host", type=str, default=None); p.add_argument("--port", type=int, default=29800)
    p.add_argument("--flows", type=int, default=1, help="receiver: number of concurrent incoming flows to accept")
    p.add_argument("--bytes", type=int, default=1 << 30)
    p.add_argument("--mss", type=int, default=DEFAULT_MSS, help="TCP_MAXSEG cap; 0 = kernel default (expected to stall on the elves path)")
    p.add_argument("--bw_mbps", type=float, default=0.0, help="sender token bucket; 0 = unlimited")
    p.add_argument("--iface", type=str, default=None)
    p.add_argument("--tag", type=str, default="")
    p.add_argument("--out", type=str, required=True)
    a = p.parse_args()
    a.mss = a.mss or None
    run_receiver(a) if a.role == "receiver" else run_sender(a)


if __name__ == "__main__":
    main()
