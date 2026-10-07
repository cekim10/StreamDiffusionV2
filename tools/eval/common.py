#!/usr/bin/env python3
"""Shared evaluation infrastructure: run directories, provenance, MSS-capped TCP, clock sync, resource sampling.

Transport policy (all experiments, all baselines): plain TCP with an explicit MSS cap (`TCP_MAXSEG`, default
1400 bytes) set on the listening and the connecting socket BEFORE accept/connect, plus TCP_NODELAY. The
elves path drops 9000-byte frames while the NICs advertise MTU 9200, so uncapped TCP can PMTU-blackhole;
capping the MSS keeps every segment <= 1500 bytes on the wire. No RDMA/RoCE. Phase 0 verifies the cap.

Timestamps: every host logs `time.time()` (wall) and `time.monotonic()`; a connection-time ping-pong
(NTP-style, N rounds, min-RTT sample) estimates the peer's wall-clock offset so the destination can map
source events into its own clock. Raw and corrected values are both recorded.
"""

from __future__ import annotations

import csv
import json
import os
import platform
import socket
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = REPO_ROOT / "results/evaluation"
DEFAULT_MSS = 1400


# ----------------------------------------------------------------------------- provenance
def git_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--short"], cwd=REPO_ROOT, text=True).strip()
        return out + (" (dirty)" if dirty else "")
    except Exception as exc:  # noqa: BLE001
        return f"unknown: {exc}"


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text()
    except Exception:  # noqa: BLE001
        return None


def nic_info() -> list[dict]:
    """Interfaces with MTU and (if available) link speed, from sysfs."""
    out = []
    base = Path("/sys/class/net")
    if not base.exists():
        return out
    for d in sorted(base.iterdir()):
        try:
            mtu = int((d / "mtu").read_text().strip())
            speed = (d / "speed").read_text().strip() if (d / "speed").exists() else None
            state = (d / "operstate").read_text().strip()
            out.append({"iface": d.name, "mtu": mtu, "speed_mbps": speed, "state": state})
        except Exception:  # noqa: BLE001
            continue
    return out


def host_info(gpu_id: int | None = None) -> dict:
    info = {"hostname": socket.gethostname(), "fqdn": socket.getfqdn(), "platform": platform.platform(), "python": platform.python_version(),
            "cpu_count": os.cpu_count(), "nics": nic_info(), "time_utc": datetime.utcnow().isoformat() + "Z"}
    mem = _read("/proc/meminfo")
    if mem:
        for line in mem.splitlines()[:3]:
            k, v = line.split(":"); info[f"meminfo_{k.strip()}"] = v.strip()
    try:
        info["nvidia_smi"] = subprocess.check_output(["nvidia-smi", "--query-gpu=index,name,memory.total,driver_version", "--format=csv,noheader"], text=True).strip()
    except Exception:  # noqa: BLE001
        info["nvidia_smi"] = None
    try:
        import torch  # noqa: WPS433

        info["torch"] = torch.__version__; info["cuda"] = torch.version.cuda
        if gpu_id is not None and torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(gpu_id)
    except Exception:  # noqa: BLE001
        pass
    try:
        info["tcp_congestion_control"] = _read("/proc/sys/net/ipv4/tcp_congestion_control").strip()
        info["tcp_mtu_probing"] = _read("/proc/sys/net/ipv4/tcp_mtu_probing").strip()
    except Exception:  # noqa: BLE001
        pass
    return info


# ----------------------------------------------------------------------------- run directories
def run_dir(experiment: str, **tags) -> Path:
    """results/evaluation/<experiment>/<k=v>_..._<timestamp>/ ; never reused (timestamp + counter)."""
    parts = [f"{k}={str(v).replace('/', '_')}" for k, v in tags.items() if v is not None]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = EVAL_ROOT / experiment
    base.mkdir(parents=True, exist_ok=True)
    name = "_".join(parts + [stamp])
    d = base / name
    i = 1
    while d.exists():
        d = base / f"{name}-{i}"; i += 1
    d.mkdir(parents=True)
    (d / "git_commit.txt").write_text(git_commit() + "\n")
    return d


def write_json(path: Path, obj) -> None:
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


class CsvLog:
    """Append-only CSV with a fixed header; flushes every row (crash-safe)."""

    def __init__(self, path: Path, fields: list[str]):
        self.path, self.fields = path, fields
        new = not path.exists()
        self.fh = open(path, "a", newline="")
        self.w = csv.DictWriter(self.fh, fieldnames=fields, extrasaction="ignore")
        if new:
            self.w.writeheader(); self.fh.flush()

    def row(self, **kw):
        self.w.writerow({k: kw.get(k, "") for k in self.fields}); self.fh.flush()

    def close(self):
        self.fh.close()


class EventLog(CsvLog):
    """events.csv: wall time, monotonic time, time relative to a reference, host, event, detail(json)."""

    def __init__(self, path: Path, host: str, t_ref_wall: float | None = None):
        super().__init__(path, ["t_wall", "t_mono", "t_rel", "host", "event", "detail"])
        self.host, self.t_ref = host, t_ref_wall

    def set_ref(self, t_ref_wall: float):
        self.t_ref = t_ref_wall

    def log(self, event: str, t_wall: float | None = None, **detail):
        t_wall = time.time() if t_wall is None else t_wall
        self.row(t_wall=f"{t_wall:.6f}", t_mono=f"{time.monotonic():.6f}", t_rel=f"{(t_wall - self.t_ref):.6f}" if self.t_ref else "",
                 host=self.host, event=event, detail=json.dumps(detail, default=str))
        return t_wall


# ----------------------------------------------------------------------------- sender-side shaping
class Throttle:
    """Token bucket releasing bytes at `bw_bps` (application-level traffic shaping; identical for every policy)."""

    def __init__(self, bw_bps: float, burst_bytes: int = 1 << 20):
        self.rate = float(bw_bps) / 8.0
        self.burst = burst_bytes
        self.tokens = float(burst_bytes)
        self.t = time.perf_counter()

    def take(self, n: int):
        if self.rate <= 0:
            return
        while True:
            now = time.perf_counter()
            self.tokens = min(self.burst, self.tokens + (now - self.t) * self.rate)
            self.t = now
            if self.tokens >= n:
                self.tokens -= n
                return
            time.sleep(min(0.01, (n - self.tokens) / self.rate))


# ----------------------------------------------------------------------------- MSS-capped TCP
MSS_WARNINGS: list[str] = []


def _set_mss(s: socket.socket, mss: int | None, where: str) -> bool:
    """Apply TCP_MAXSEG. Linux accepts it on listening/unconnected/connected sockets; macOS rejects it on
    listening sockets (local tests only). Failures are recorded, never silently ignored."""
    if not mss:
        return False
    try:
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG, int(mss))
        return True
    except OSError as exc:
        MSS_WARNINGS.append(f"TCP_MAXSEG={mss} not applied on {where}: {exc}")
        return False


def tcp_listen(host: str, port: int, mss: int | None = DEFAULT_MSS, backlog: int = 8) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _set_mss(s, mss, "listening socket")  # inherited by accepted sockets on Linux
    s.bind((host, port)); s.listen(backlog)
    return s


def tcp_accept(srv: socket.socket, mss: int | None = DEFAULT_MSS) -> socket.socket:
    c, _ = srv.accept()
    c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    _set_mss(c, mss, "accepted socket")
    return c


def tcp_connect(host: str, port: int, mss: int | None = DEFAULT_MSS, timeout: float = 600.0, retry_s: float = 1.0) -> socket.socket:
    deadline = time.time() + timeout
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _set_mss(s, mss, "connecting socket")  # must be set before connect
        try:
            s.connect((host, port))
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return s
        except OSError:
            s.close()
            if time.time() > deadline:
                raise
            time.sleep(retry_s)


def effective_mss(sock: socket.socket) -> int | None:
    try:
        return sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG)
    except OSError:
        return None


# ----------------------------------------------------------------------------- clock sync (NTP-style over the control socket)
def _send_line(sock, obj):
    sock.sendall((json.dumps(obj) + "\n").encode())


def _recv_line(sock, buf: bytearray):
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    line, _, rest = bytes(buf).partition(b"\n")
    buf[:] = rest
    return json.loads(line.decode())


def clock_sync_client(sock: socket.socket, rounds: int = 25) -> dict:
    """Estimate offset = peer_wall - my_wall using the minimum-RTT sample. Peer must run clock_sync_server."""
    buf = bytearray()
    samples = []
    for i in range(rounds):
        t0 = time.time(); _send_line(sock, {"i": i, "t0": t0})
        r = _recv_line(sock, buf); t3 = time.time()
        t1, t2 = r["t1"], r["t2"]
        rtt = (t3 - t0) - (t2 - t1)
        off = ((t1 - t0) + (t2 - t3)) / 2
        samples.append((rtt, off))
    _send_line(sock, {"done": True})
    rtt_min, off_best = min(samples)
    return {"offset_s": off_best, "rtt_min_s": rtt_min, "rtt_median_s": sorted(s[0] for s in samples)[len(samples) // 2], "rounds": rounds}


def clock_sync_server(sock: socket.socket) -> None:
    buf = bytearray()
    while True:
        r = _recv_line(sock, buf); t1 = time.time()
        if r.get("done"):
            return
        _send_line(sock, {"i": r["i"], "t1": t1, "t2": time.time()})


# ----------------------------------------------------------------------------- resource sampling
def _cpu_times():
    line = _read("/proc/stat")
    if not line:
        return None
    f = line.splitlines()[0].split()
    vals = list(map(int, f[1:]))
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return sum(vals), idle


def _net_bytes(iface: str | None):
    txt = _read("/proc/net/dev")
    if not txt:
        return None
    rx = tx = 0
    for line in txt.splitlines()[2:]:
        name, rest = line.split(":", 1)
        name = name.strip()
        if name == "lo" or (iface and name != iface):
            continue
        f = rest.split()
        rx += int(f[0]); tx += int(f[8])
    return rx, tx


def _gpu_query(gpu_id: int | None):
    try:
        out = subprocess.check_output(["nvidia-smi", f"--id={gpu_id if gpu_id is not None else 0}", "--query-gpu=utilization.gpu,utilization.memory,memory.used",
                                       "--format=csv,noheader,nounits"], text=True, timeout=2).strip().split(",")
        return [float(x) for x in out]
    except Exception:  # noqa: BLE001
        return [None, None, None]


class ResourceSampler(threading.Thread):
    """1 Hz samples of CPU %, host memory, NIC rx/tx rate, GPU util/mem -> network.csv (also serves as the utilization log)."""

    def __init__(self, path: Path, host: str, gpu_id: int | None = None, iface: str | None = None, period: float = 1.0):
        super().__init__(daemon=True)
        self.log = CsvLog(path, ["t_wall", "host", "cpu_pct", "mem_used_kb", "net_rx_mbps", "net_tx_mbps", "gpu_util_pct", "gpu_mem_util_pct", "gpu_mem_used_mb"])
        self.host, self.gpu_id, self.iface, self.period = host, gpu_id, iface, period
        self.stop = threading.Event()

    def run(self):
        prev_cpu, prev_net, prev_t = _cpu_times(), _net_bytes(self.iface), time.time()
        while not self.stop.wait(self.period):
            cpu, net, t = _cpu_times(), _net_bytes(self.iface), time.time()
            cpu_pct = ""
            if cpu and prev_cpu and cpu[0] != prev_cpu[0]:
                cpu_pct = f"{100.0 * (1 - (cpu[1] - prev_cpu[1]) / (cpu[0] - prev_cpu[0])):.1f}"
            rx = tx = ""
            if net and prev_net:
                dt = max(1e-6, t - prev_t)
                rx = f"{(net[0] - prev_net[0]) * 8 / dt / 1e6:.1f}"; tx = f"{(net[1] - prev_net[1]) * 8 / dt / 1e6:.1f}"
            mem = _read("/proc/meminfo")
            mem_used = ""
            if mem:
                kv = {l.split(":")[0]: int(l.split()[1]) for l in mem.splitlines()[:3]}
                mem_used = kv.get("MemTotal", 0) - kv.get("MemAvailable", 0)
            g = _gpu_query(self.gpu_id)
            self.log.row(t_wall=f"{t:.3f}", host=self.host, cpu_pct=cpu_pct, mem_used_kb=mem_used, net_rx_mbps=rx, net_tx_mbps=tx,
                         gpu_util_pct=g[0] if g[0] is not None else "", gpu_mem_util_pct=g[1] if g[1] is not None else "", gpu_mem_used_mb=g[2] if g[2] is not None else "")
            prev_cpu, prev_net, prev_t = cpu, net, t
        self.log.close()

    def finish(self):
        self.stop.set(); self.join(timeout=5)
