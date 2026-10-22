"""Run validity for the XB re-implemented baselines (pre-copy / recompute; osdi/expXB/preregistration.md section 8).

A run is valid iff: every node on one commit; GPU 0 idle before the run (GPU runs); pre-copy: every switchover's state
verified against the source's digests at the boundary (recompute: at least one switchover, every node's uint8 input
history reproduces its runtime input, and with a lossless codec every replay's decoded inputs are bit-exact; lossy codecs
are sensitivity runs whose trajectory is judged on the outputs by the aggregator); the final edge ended up serving; the run was not cut by max_run_s; and
every node's NIC receive rate stayed within 1.15 x the emulated cap in every 10 s window (shaped runs).
"""

from __future__ import annotations

import csv
import statistics as st
from pathlib import Path


def nic_ok(run_dir: Path, s: dict, cap_mbps: float) -> tuple[bool, list[str]]:
    bad = []
    for lb in s.get("hosts", {}):
        p = Path(run_dir) / f"node_{lb}" / "network.csv"
        if not p.exists():
            continue
        rows = [r for r in csv.DictReader(open(p, newline="")) if r.get("net_rx_mbps")]
        v = [float(r["net_rx_mbps"]) for r in rows if float(r["t_wall"]) >= s.get("t0_wall", 0)]
        for i in range(max(0, len(v) - 9)):
            m = st.mean(v[i:i + 10])
            if m > 1.15 * cap_mbps:
                bad.append(f"NIC {lb} rx 10 s mean {m:.0f} Mbps > 1.15 x {cap_mbps:g}"); break
    return not bad, bad


def run_validity_xb(s: dict, run_dir: Path | str | None = None, dry: bool = False) -> tuple[bool, list[str]]:
    v = s.get("validation", {})
    bad = []
    if v.get("nodes_same_commit") is not True:
        bad.append("nodes on different commits")
    if not dry and v.get("gpu0_idle_before_run") is not True:
        bad.append("GPU 0 not idle before the run")
    if str(s.get("policy", "")).startswith("precopy"):
        # pre-copy moves state: every switchover's components must match the source's digests at the boundary
        if v.get("switchovers_verified") is not True:
            bad.append("a switchover was not verified (or none happened)")
    else:
        # recompute moves inputs, not state: its trajectory is judged on the outputs (aggregator); here only the inputs
        if not v.get("n_switchovers"):
            bad.append("no switchover happened")
        if v.get("input_check") is not True:
            bad.append("a node's uint8 input history does not reproduce its runtime input")
        if v.get("codec_lossless") and v.get("inputs_exact_at_switchovers") is not True:
            bad.append("lossless input codec but a replay's decoded inputs were not bit-exact")
    if v.get("codecs_ok") is not True:
        bad.append("a node lacks FFV1 (bit-exact round trip) or libx264")
    if v.get("final_edge_served") is not True:
        bad.append("the final edge never served")
    if str(v.get("stop_reason", "")).startswith("deadline"):
        bad.append("cut by max_run_s")
    bw = s.get("bw_mbps") or 0
    if bw > 0 and run_dir is not None and not dry:
        ok, why = nic_ok(Path(run_dir), s, bw)
        bad += why
    return not bad, bad
