#!/usr/bin/env python3
"""Per-host experiment agent (stdlib only). Replaces ssh orchestration on the elves data network, where
inter-host ssh fails at key exchange because the path drops >1500-byte frames; the agent's control
connection is MSS-capped TCP like every other evaluation socket.

Start once per host (inside tmux), from the repo root:
    python tools/eval/agent.py --port 29900
Protocol: newline-delimited JSON requests on one connection per client; responses are JSON lines.
    {"op":"ping"}                                    -> {"ok":true,"host":...,"cwd":...}
    {"op":"run","cmd":[...],"log":"rel/path.log"}    -> {"ok":true,"pid":N}       (cwd = repo root; env inherited)
    {"op":"poll","pid":N}                            -> {"ok":true,"running":bool,"rc":int|null}
    {"op":"wait","pid":N,"timeout":S}                -> {"ok":true,"rc":int|null,"timed_out":bool}
    {"op":"kill","pid":N}                            -> {"ok":true}
    {"op":"read","path":"rel/path"}                  -> {"ok":true,"text":...}  (text files, <= 50 MB)
    {"op":"glob","pattern":"rel/glob"}               -> {"ok":true,"paths":[...]}
    {"op":"mkdir","path":"rel/dir"}                  -> {"ok":true}
Only paths under the repo root are accepted; commands run as the agent's user.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_MSS, REPO_ROOT, tcp_accept, tcp_listen  # noqa: E402

PROCS: dict[int, subprocess.Popen] = {}
LOCK = threading.Lock()


def safe_path(rel: str) -> Path:
    p = (REPO_ROOT / rel).resolve()
    if REPO_ROOT not in p.parents and p != REPO_ROOT:
        raise ValueError(f"path outside repo root: {rel}")
    return p


def handle(req: dict) -> dict:
    op = req.get("op")
    if op == "ping":
        return {"ok": True, "host": socket.gethostname(), "cwd": str(REPO_ROOT), "python": sys.executable, "t": time.time()}
    if op == "run":
        log = safe_path(req["log"]) if req.get("log") else None
        if log:
            log.parent.mkdir(parents=True, exist_ok=True)
        fh = open(log, "ab") if log else subprocess.DEVNULL
        env = dict(os.environ); env.update(req.get("env") or {})
        cmd = list(req["cmd"])
        # interpreter resolution: "python"/"auto", or a venv path that does not exist on this host -> the agent's own python
        if cmd and (cmd[0] in ("python", "auto") or ("/" in cmd[0] and not os.path.exists(os.path.join(REPO_ROOT, cmd[0])) and not os.path.exists(cmd[0]))):
            cmd[0] = sys.executable
        p = subprocess.Popen(cmd, cwd=str(REPO_ROOT), stdout=fh, stderr=subprocess.STDOUT, env=env)
        with LOCK:
            PROCS[p.pid] = p
        return {"ok": True, "pid": p.pid}
    if op in ("poll", "wait", "kill"):
        p = PROCS.get(int(req["pid"]))
        if p is None:
            return {"ok": False, "error": "unknown pid"}
        if op == "poll":
            rc = p.poll(); return {"ok": True, "running": rc is None, "rc": rc}
        if op == "kill":
            p.kill(); return {"ok": True}
        try:
            rc = p.wait(timeout=float(req.get("timeout", 3600))); return {"ok": True, "rc": rc, "timed_out": False}
        except subprocess.TimeoutExpired:
            return {"ok": True, "rc": None, "timed_out": True}
    if op == "read":
        p = safe_path(req["path"])
        if p.stat().st_size > 50 << 20:
            return {"ok": False, "error": "file too large"}
        return {"ok": True, "text": p.read_text(errors="replace")}
    if op == "glob":
        return {"ok": True, "paths": sorted(str(x.relative_to(REPO_ROOT)) for x in REPO_ROOT.glob(req["pattern"]))}
    if op == "mkdir":
        safe_path(req["path"]).mkdir(parents=True, exist_ok=True); return {"ok": True}
    return {"ok": False, "error": f"unknown op {op}"}


def serve_conn(conn: socket.socket):
    buf = bytearray()
    try:
        while True:
            while b"\n" not in buf:
                chunk = conn.recv(65536)
                if not chunk:
                    return
                buf += chunk
            line, _, rest = bytes(buf).partition(b"\n"); buf[:] = rest
            try:
                resp = handle(json.loads(line.decode()))
            except Exception as exc:  # noqa: BLE001
                resp = {"ok": False, "error": repr(exc)}
            conn.sendall((json.dumps(resp) + "\n").encode())
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bind", type=str, default="0.0.0.0"); ap.add_argument("--port", type=int, default=29900)
    ap.add_argument("--mss", type=int, default=DEFAULT_MSS)
    a = ap.parse_args()
    srv = tcp_listen(a.bind, a.port, a.mss or None)
    print(f"[agent] {socket.gethostname()} listening on {a.bind}:{a.port} (repo {REPO_ROOT}, mss {a.mss})", flush=True)
    while True:
        c = tcp_accept(srv, a.mss or None)
        threading.Thread(target=serve_conn, args=(c,), daemon=True).start()


if __name__ == "__main__":
    main()
