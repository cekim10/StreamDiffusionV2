#!/usr/bin/env python3
"""Aggregate Phase 3 runs (results/evaluation/repeated_mobility/policy=*/summary.json) into
summary_runs.csv (one row per run) and summary_by_policy_rho.csv (median / p25 / p75 per policy, bw, rho),
and print the shakedown table with the validation checks. No expected numbers anywhere."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

FIELDS = ["run_id", "policy", "bw_mbps", "rho", "tm_s", "rep", "sink_bytes", "n_frags",
          "t_final_move_rel_s", "lat_first_output_s", "lat_sink_received_s", "lat_sink_verified_s", "lat_sink_bind_s", "lat_continuity_ready_s", "lat_rejoin_s",
          "total_sent_bytes", "useful_bytes", "wasted_bytes", "duplicate_bytes", "norm_traffic", "norm_waste", "norm_useful", "reused_bytes", "bytes_from_source",
          "psnr_after_rejoin", "psnr_after_bind_8", "ssim_after_bind_8", "psnr_gap", "rejoin_calls_after_bind", "lag_mean", "lag_max", "missing_chunks",
          "ingress_peak_mbps", "egress_peak_mbps", "validation_failed", "stop_reason", "run_dir"]
AGG = ["lat_continuity_ready_s", "lat_sink_bind_s", "lat_rejoin_s", "lat_first_output_s", "norm_traffic", "norm_waste", "psnr_after_rejoin", "lag_mean", "ingress_peak_mbps"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=str, default="results/evaluation/repeated_mobility")
    a = ap.parse_args()
    root = Path(a.root)
    rows = []
    for d in sorted(root.glob("policy=*")):
        f = d / "summary.json"
        if not f.exists():
            print(f"[agg] {d.name}: no summary.json (incomplete run), skipped"); continue
        s = json.load(open(f))
        L, B, N, C, T, V = s["latency_after_final_move_s"], s["bytes"], s["normalized"], s["continuity"], s["throughput_mbps"], s["validation"]
        failed = [k for k, v in V.items() if v is False and k not in ("four_hosts_distinct",) or (k == "four_hosts_distinct" and v is False and len(set(s["hosts"].values())) > 1)]
        rows.append({"run_id": s["run_id"], "policy": s["policy"], "bw_mbps": "native" if not s["bw_mbps"] else f"{s['bw_mbps']:g}", "rho": "" if s["rho"] is None else f"{s['rho']:g}", "tm_s": s["tm_s"], "rep": s["rep"],
                     "sink_bytes": s["sink_bytes"], "n_frags": s["n_frags"], "t_final_move_rel_s": s["t_final_move_rel_s"],
                     "lat_first_output_s": L["first_output"], "lat_sink_received_s": L["sink_received"], "lat_sink_verified_s": L["sink_verified"], "lat_sink_bind_s": L["sink_bind"],
                     "lat_continuity_ready_s": L["continuity_ready"], "lat_rejoin_s": L["rejoin"],
                     "total_sent_bytes": B["total_sent"], "useful_bytes": B["useful"], "wasted_bytes": B["wasted"], "duplicate_bytes": B["duplicate"], "norm_traffic": N["total_traffic"], "norm_waste": N["waste"], "norm_useful": N["useful"],
                     "reused_bytes": B["reused_from_non_source"], "bytes_from_source": B["by_src"].get("A"),
                     "psnr_after_rejoin": C.get("psnr_after_rejoin_mean"), "psnr_after_bind_8": C["psnr_after_bind_8_mean"], "ssim_after_bind_8": C["ssim_after_bind_8_mean"], "psnr_gap": C["psnr_gap_mean"],
                     "rejoin_calls_after_bind": C["rejoin_calls_after_bind"], "lag_mean": C["lag_hops_mean"], "lag_max": C["lag_hops_max"], "missing_chunks": C["missing_chunks"],
                     "ingress_peak_mbps": V.get("ingress_peak_mbps_max"), "egress_peak_mbps": max(T["egress_peak_by_node"].values()) if T["egress_peak_by_node"] else None,
                     "validation_failed": "|".join(failed), "stop_reason": V.get("stop_reason"), "run_dir": str(d)})
    if not rows:
        print("[agg] no runs"); return
    with open(root / "summary_runs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["policy"], r["bw_mbps"], r["rho"])].append(r)
    with open(root / "summary_by_policy_rho.csv", "w", newline="") as fh:
        hdr = ["policy", "bw_mbps", "rho", "n"] + [f"{k}_{q}" for k in AGG for q in ("median", "p25", "p75")]
        w = csv.writer(fh); w.writerow(hdr)
        for (pol, bw, rho), lst in sorted(groups.items(), key=lambda kv: (kv[0][1], float(kv[0][2] or 0), kv[0][0])):
            out = [pol, bw, rho, len(lst)]
            for k in AGG:
                v = [float(x[k]) for x in lst if x[k] not in (None, "")]
                out += [f"{np.median(v):.4f}", f"{np.percentile(v, 25):.4f}", f"{np.percentile(v, 75):.4f}"] if v else ["", "", ""]
            w.writerow(out)
    # shakedown table
    fmt = lambda v, p=2: "-" if v in (None, "") else f"{float(v):.{p}f}"  # noqa: E731
    print("| policy | bw | rho | T_m | first out | Sink recv | bound | cont.-ready | rejoin | traffic x | waste x | reused MiB | from A MiB | PSNR post-rejoin | lag mean | ingress peak Mbps | validation |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['policy']} | {r['bw_mbps']} | {r['rho'] or '-'} | {fmt(r['tm_s'], 1) if r['tm_s'] < 1e8 else 'inf'} | {fmt(r['lat_first_output_s'])} | {fmt(r['lat_sink_received_s'])} | {fmt(r['lat_sink_bind_s'])} | "
              f"{fmt(r['lat_continuity_ready_s'])} | {fmt(r['lat_rejoin_s'])} | {fmt(r['norm_traffic'])} | {fmt(r['norm_waste'])} | {r['reused_bytes'] / 2**20:.0f} | {(r['bytes_from_source'] or 0) / 2**20:.0f} | "
              f"{fmt(r['psnr_after_rejoin'], 1)} | {fmt(r['lag_mean'])} | {fmt(r['ingress_peak_mbps'], 0)} | {r['validation_failed'] or 'ok'} |")
    print(f"-> {root / 'summary_runs.csv'}, {root / 'summary_by_policy_rho.csv'}")


if __name__ == "__main__":
    main()
