#!/usr/bin/env python3
"""Client side of tools/eval/agent.py: a small RPC helper used by the orchestrators."""

from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_MSS, tcp_connect  # noqa: E402

DEFAULT_HOSTS = {"A": "elves-01.be.ucsc.edu", "B": "elves-02.be.ucsc.edu", "C": "elves-03.be.ucsc.edu", "D": "elves-04.be.ucsc.edu"}


def parse_hosts(spec: str | None) -> dict[str, tuple[str, int]]:
    """'A=host[:port],B=host[:port],...' -> {label: (host, port)}; default elves-01..04 on 29900."""
    out = {k: (v, 29900) for k, v in DEFAULT_HOSTS.items()}
    if spec:
        for item in spec.split(","):
            label, hp = item.split("=")
            host, _, port = hp.partition(":")
            out[label] = (host, int(port) if port else 29900)
    return out


class Agent:
    def __init__(self, label: str, host: str, port: int = 29900, mss: int | None = DEFAULT_MSS):
        self.label, self.host, self.port = label, host, port
        self.sock = tcp_connect(host, port, mss, timeout=30)
        self.buf = bytearray()

    def call(self, **req) -> dict:
        self.sock.sendall((json.dumps(req) + "\n").encode())
        while b"\n" not in self.buf:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise ConnectionError(f"agent {self.label} closed")
            self.buf += chunk
        line, _, rest = bytes(self.buf).partition(b"\n"); self.buf[:] = rest
        resp = json.loads(line.decode())
        if not resp.get("ok"):
            raise RuntimeError(f"agent {self.label}@{self.host}: {resp.get('error')}")
        return resp

    def run(self, cmd: list[str], log: str, env: dict | None = None) -> int:
        return self.call(op="run", cmd=cmd, log=log, env=env or {})["pid"]

    def wait(self, pid: int, timeout: float = 3600) -> dict:
        return self.call(op="wait", pid=pid, timeout=timeout)

    def poll(self, pid: int) -> dict:
        return self.call(op="poll", pid=pid)

    def read(self, path: str) -> str:
        return self.call(op="read", path=path)["text"]

    def glob(self, pattern: str) -> list[str]:
        return self.call(op="glob", pattern=pattern)["paths"]

    def mkdir(self, path: str) -> None:
        self.call(op="mkdir", path=path)

    def ping(self) -> dict:
        return self.call(op="ping")

    def exec(self, cmd: list[str], timeout: float = 30) -> dict:
        return self.call(op="exec", cmd=cmd, timeout=timeout)


def connect_all(hosts: dict[str, tuple[str, int]], labels: list[str], mss=DEFAULT_MSS) -> dict[str, Agent]:
    agents = {}
    for lb in labels:
        h, p = hosts[lb]
        agents[lb] = Agent(lb, h, p, mss)
        info = agents[lb].ping()
        print(f"[agents] {lb} = {h}:{p} -> {info['host']} ({info['cwd']})", flush=True)
    return agents


def wait_all(agents_pids: list[tuple[Agent, int]], timeout: float, label: str) -> bool:
    ok = True
    deadline = time.time() + timeout
    for ag, pid in agents_pids:
        r = ag.wait(pid, max(1.0, deadline - time.time()))
        if r.get("timed_out") or r.get("rc") not in (0, None):
            print(f"[agents] {label}: {ag.label} pid {pid} -> rc={r.get('rc')} timed_out={r.get('timed_out')}", flush=True)
            ok = False
            if r.get("timed_out"):
                try:
                    ag.call(op="kill", pid=pid)
                except Exception:  # noqa: BLE001
                    pass
    return ok
