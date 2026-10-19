#!/usr/bin/env python3
"""W / R / N run validity (results/evaluation/osdi/followup_common.md section 3).

Same checks as Experiment D (tools/eval/expD_validity.py) with two differences fixed in the W / R / N freeze:
  - a run that ends without a rejoin, or by `deadline` / `window_exhausted`, is NOT invalid: it is kept and its times are
    right-censored (summary["wrn"]["termination"]);
  - NIC peaks and paced egress are judged against the cap **in force**: a link degraded by a cap event is judged against
    the degraded cap after the change (1 s NIC-sample grace; 10 s egress windows that start after the change).
Owner-side Sink promotions are applicability (summary["wrn"]["applicable_single_version"]), not validity.
ExpD's validity module is not changed.

    from wrn_validity import run_validity_wrn
    ok, reasons = run_validity_wrn(summary, run_dir, dry=False)
"""

from __future__ import annotations

import csv
from pathlib import Path

PHYSICAL_MBPS = 9400.0


def _nic_samples(run_dir: Path, node: str):
    p = run_dir / f"node_{node}" / "network.csv"
    if not p.exists():
        return []
    with open(p, newline="") as fh:
        return [(float(r["t_wall"]), float(r["net_rx_mbps"]) if r["net_rx_mbps"] else None, float(r["net_tx_mbps"]) if r["net_tx_mbps"] else None)
                for r in csv.DictReader(fh)]


def _sent_rows(run_dir: Path):
    p = run_dir / "fragments.csv"
    if not p.exists():
        return []
    with open(p, newline="") as fh:
        return [(float(r["t_rel"]), r["src"], int(r["bytes"])) for r in csv.DictReader(fh) if r["event"] == "sent"]


def run_validity_wrn(s: dict, run_dir: Path | str | None = None, dry: bool = False) -> tuple[bool, list[str]]:
    v = s.get("validation", {})
    mode = (s.get("execution_state") or {}).get("mode", "fast")
    term = (s.get("wrn") or {}).get("termination") or {}
    censored_ok = bool(term.get("timed_out")) or not term.get("sink_verified", True)
    bad = []
    if mode == "fast":
        # a censored run (restoration not finished) cannot have all fragments verified; it stays valid as censored
        if v.get("all_fragments_verified") is not True and not censored_ok:
            bad.append("fragments not all verified")
        if v.get("final_sink_digest_matches_source") is not True and not censored_ok:
            bad.append("final Sink digest")
        if v.get("sink_version_consistent") is False:
            bad.append("fragment version rejected")
    elif mode == "cold":
        if v.get("cold_no_state_transferred") is not True:
            bad.append("cold restart sent state")
    if v.get("version_events_zero") is not True:
        bad.append("Sink-version (fragment) events")
    bw = s.get("bw_mbps", 0) or 0
    cap = bw if bw > 0 else PHYSICAL_MBPS
    nic = [x for d in (v.get("nic_rx_peak_mbps_by_node") or {}, v.get("nic_tx_peak_mbps_by_node") or {}) for x in d.values() if x is not None]
    if not dry and (not nic or max(nic) > 1.15 * cap):
        bad.append("NIC peak > 1.15 x cap" if nic else "no NIC counters")
    if v.get("paced_egress_10s_within_cap") is False:
        bad.append("paced egress > 1.05 x cap (10 s)")
    # cap in force after a cap change (N): degraded node/direction
    changes = (s.get("d0") or {}).get("cap_changes") or []
    if changes and run_dir is not None:
        rd = Path(run_dir)
        for (t_rel, node, d, mbps) in changes:
            if not dry:
                samples = _nic_samples(rd, node)
                # network.csv t_wall is the node's clock; the run's t0 on that clock is recorded per run
                t0_node = (s.get("wrn") or {}).get("t0_wall_by_node", {}).get(node)
                if t0_node is not None:
                    # followup_common.md Amendment 1: a degraded link is judged on 10 s windows of the 1 s NIC samples (one 4 MiB
                    # fragment is 33 Mbps in a 1 s sample, more than the 1.15 x 62.5 Mbps tolerance; over 10 s it is 5 %)
                    idx = 1 if d == "in" else 2
                    late = [(x[0], x[idx]) for x in samples if x[idx] is not None and x[0] >= t0_node + t_rel + 1.0]
                    for i in range(len(late)):
                        win = [v for t, v in late[i:] if t - late[i][0] < 10.0]
                        if len(win) >= 9 and sum(win) / len(win) > 1.15 * mbps:
                            bad.append(f"NIC {node} {d} 10 s mean > 1.15 x degraded cap after the change"); break
            if d == "out":
                # rows carry the send-completion time: a fragment counts against the degraded cap only if it could have been
                # sent entirely after the change (completion >= change + its transmission time at the degraded cap), so a
                # fragment already on the wire at the change is not charged to the new cap
                ts = sorted((t, b) for t, src, b in _sent_rows(rd) if src == node and t >= t_rel + b * 8 / (mbps * 1e6))
                # rate over (t_i, t_j], t_j - t_i >= 10 s: bytes completed after t_i divided by t_j - t_i (the fragment completing
                # at t_i was transmitted before the window; counting it would over-estimate by a whole fragment)
                j, acc = 0, 0
                for i in range(len(ts)):
                    if i > 0:
                        acc -= ts[i][1]   # acc = bytes of fragments (i, j]
                    while j + 1 < len(ts) and ts[j][0] - ts[i][0] < 10.0:
                        j += 1; acc += ts[j][1]
                    if j <= i or ts[j][0] - ts[i][0] < 10.0:
                        break
                    if acc * 8 / (ts[j][0] - ts[i][0]) / 1e6 > 1.05 * mbps:
                        bad.append(f"paced egress {node} > 1.05 x degraded cap (10 s)"); break
    if v.get("four_hosts_distinct") is not True and not dry:
        bad.append("hosts not distinct")
    if v.get("nodes_same_commit") is not True:
        bad.append("nodes on different commits")
    if v.get("gpu0_idle_before_run") is not True and not dry:
        bad.append("GPU 0 not idle before the run")
    c = s.get("continuity", {})
    if c.get("n_chunks", 0) and c.get("psnr_gap_mean") is None and c.get("psnr_after_bind_8_mean") is None and c.get("psnr_after_rejoin_mean") is None:
        bad.append("no reference PSNR")
    h = s.get("hybrid")
    if h:
        nv = (h.get("network_summary") or {}).get("validation") or {}
        if not nv.get("paced_egress_within_cap"):
            bad.append("network sessions not paced within cap")
    return (not bad), bad
