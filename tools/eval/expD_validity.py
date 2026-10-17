#!/usr/bin/env python3
"""Experiment D run validity (preregistration v3 section 7, "Run validity"), shared by the aggregator
(tools/eval/aggregate_expD.py) and the orchestrator's --skip_done (a configuration counts as done only with a valid run).

A run is valid when: its Sink (or, for Full migration, every state component) is verified and the final digest matches
the source's; no Sink-version event; NIC peaks <= 1.15 x the cap (unshaped: the 9.4 Gbps NIC); paced payload egress
<= 1.05 x cap in every 10 s window (shaped runs); the hosts are distinct and on one commit; GPU 0 was idle before the
run; the reference was available (a PSNR value at the final owner); the run ended by its end condition (not the
deadline or the generation window). Scenario E also needs its network sessions verified and paced within cap.
"""

from __future__ import annotations

PHYSICAL_MBPS = 9400.0


def run_validity(s: dict, dry: bool = False) -> tuple[bool, list[str]]:
    """dry: loopback protocol test (no NIC counters, one host, no GPU): those three checks are skipped."""
    v = s.get("validation", {})
    mode = (s.get("execution_state") or {}).get("mode", "fast")
    bad = []
    if mode == "fast":
        if v.get("all_fragments_verified") is not True:
            bad.append("fragments not all verified")
        if v.get("final_sink_digest_matches_source") is not True:
            bad.append("final Sink digest")
    elif mode == "full":
        if v.get("full_state_digests_ok") is not True:
            bad.append("full-state digests")
        if v.get("final_sink_digest_matches_source") is not True:
            bad.append("Sink component digest")
    elif mode == "cold":
        if v.get("cold_no_state_transferred") is not True:
            bad.append("cold restart sent state")
    if v.get("version_events_zero") is not True:
        bad.append("Sink-version events")
    cap = s["bw_mbps"] if s.get("bw_mbps", 0) > 0 else PHYSICAL_MBPS
    nic = [x for d in (v.get("nic_rx_peak_mbps_by_node") or {}, v.get("nic_tx_peak_mbps_by_node") or {}) for x in d.values() if x is not None]
    if not dry and (not nic or max(nic) > 1.15 * cap):
        bad.append("NIC peak > 1.15 x cap" if nic else "no NIC counters")
    if v.get("paced_egress_10s_within_cap") is False:
        bad.append("paced egress > 1.05 x cap (10 s)")
    if v.get("four_hosts_distinct") is not True and not dry:
        bad.append("hosts not distinct")
    if v.get("nodes_same_commit") is not True:
        bad.append("nodes on different commits")
    if v.get("gpu0_idle_before_run") is not True and not dry:
        bad.append("GPU 0 not idle before the run")
    c = s.get("continuity", {})
    if mode == "cold":
        if c.get("psnr_gap_mean") is None:
            bad.append("no reference PSNR")
    elif c.get("psnr_after_rejoin_mean") is None:
        bad.append("no rejoin / no reference PSNR")
    if str(v.get("stop_reason", "")).startswith(("deadline", "window_exhausted")):
        bad.append(f"stopped by {v.get('stop_reason')}")
    h = s.get("hybrid")
    if h:
        nv = (h.get("network_summary") or {}).get("validation") or {}
        if not nv.get("all_fragments_verified") or not nv.get("paced_egress_within_cap"):
            bad.append("network sessions not verified / not paced within cap")
    return (not bad), bad
