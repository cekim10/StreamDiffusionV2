#!/usr/bin/env python3
"""Judge the D0 GPU correctness shakedown (results/evaluation/d0_shakedown/) against the pass conditions written in
results/evaluation/osdi/d0/D0_report.md section F before the runs. These are correctness checks, not Experiment D
criteria. Writes results/evaluation/osdi/d0/shakedown_check.md; exits non-zero on any failure.

Conditions: Sink verified and bound with a matching digest; rejoin PSNR mean >= 35 dB; 0 version events; 0 duplicates;
every fragment verified; NIC peaks <= 1.15 x 1 Gbps; event-driven re-plans in the degradation run and not in the
repeated run; incorrect placement shows forwarding from the never-owner candidate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "results/evaluation/d0_shakedown"


def kind(s):
    pp = s["d0"].get("prepos")
    if pp:
        top1 = max(pp["alloc_sinks"], key=pp["alloc_sinks"].get)
        return "placement correct" if s["path"][1] == top1 else "placement incorrect"
    if len(s["path"]) == 2:
        return "single"
    return "degradation" if s["d0"]["cap_changes"] or "_ev=" in s["run_id"] else "repeated"


def main():
    rows, fails = [], []
    exp = ROOT / "results/evaluation" / sys.argv[1] if len(sys.argv) > 1 else EXP   # e.g. d0_shakedown_rerun
    for d in sorted(exp.glob("policy=*"), key=lambda p: p.name[-15:]):
        s = json.load(open(d / "summary.json"))
        v, z, L, c = s["validation"], s["d0"], s["latency_after_final_move_s"], s["continuity"]
        k = kind(s)
        nic = max(list(v["nic_rx_peak_mbps_by_node"].values()) + list(v["nic_tx_peak_mbps_by_node"].values()))
        chk = {
            "bound+digest": L.get("sink_bind") is not None and v["final_sink_digest_matches_source"] and v["all_fragments_verified"],
            "rejoin>=35dB": (c.get("psnr_after_rejoin_mean") or 0) >= 35,
            "version 0": z["version_events"] == 0 and v["version_events_zero"],
            "dup 0": s["bytes"]["duplicate"] == 0,
            "NIC<=1.15cap": nic <= 1.15 * s["bw_mbps"],
            "validation": not [x for x, y in v.items() if y is False],
        }
        if s["policy"] == "reuse_dyn" and k == "degradation":
            chk["replans>0"] = z["n_replans"] > 0
        if s["policy"] == "reuse_dyn" and k == "repeated":
            chk["replans=0"] = z["n_replans"] == 0
        if k == "placement incorrect":
            chk["never-owner fwd"] = z["holder_forwarded_sinks"] > 0
        bad = [x for x, ok in chk.items() if not ok]
        if bad:
            fails.append((d.name, bad))
        x = z["x_verified_at_move"]
        rows.append(f"| {k} | {s['policy']} | {L['first_output']:.2f} | {L['sink_bind']:.2f} | {L['rejoin']:.2f} | {c['psnr_after_rejoin_mean']:.1f} | "
                    f"{z['source_bytes_pre_move_sinks']:.2f} / {z['source_bytes_post_move_sinks']:.2f} / {z['source_bytes_total_sinks']:.2f} | {z['holder_forwarded_sinks']:.2f} | "
                    f"{', '.join(f'{a} {b:.2f}' for a, b in x.items() if b)} | {z['verified_progress_reused'] if z['verified_progress_reused'] is None else round(z['verified_progress_reused'], 3)} | "
                    f"{z['n_replans']} | {nic:.0f} | {'PASS' if not bad else 'FAIL: ' + ', '.join(bad)} |")
    out = ["# D0 GPU correctness shakedown - check", "",
           "Conditions from `D0_report.md` section F (written before the runs). Latencies in seconds after the final move's handoff request.", "",
           "| scenario | policy | first output | Sink bound | rejoin | rejoin PSNR (dB) | source pre / post / total (Sinks) | holder-forwarded | x verified at move | reuse of verified progress | re-plans | NIC peak (Mbps) | verdict |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"] + rows
    out += ["", f"{len(rows)} runs; {len(fails)} failing."]
    p = ROOT / "results/evaluation/osdi/d0" / ("shakedown_check.md" if exp == EXP else f"shakedown_check_{exp.name}.md"); p.write_text("\n".join(out) + "\n")
    print("\n".join(out))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
