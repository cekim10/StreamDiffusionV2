#!/usr/bin/env python3
"""Aggregate generalization runs (results/state_migration/gen/<video>_s<seed>_k<k>/) into one table
and check the three temporal-semantics claims per run.

Claims (PSNR vs the run's own bit-exact baseline; 99 = identical):
  IMMEDIATE  in-flight row: losing it costs >= 6 dB long-term vs transferring it (k >= 2 only)
             (xfer_sink+meta+inflight M+16.. minus xfer_sink+meta M+16..)
  DURABLE    sink: without it the destination never rejoins (xfer_meta+inflight M+16.. < 25 dB) and
             a sink swapped in 8 chunks late rejoins within 8 calls to >= 30 dB (ph_zero_8 / ph_local_8)
  EPHEMERAL  recent KV and VAE caches: dropping them heals to >= 35 dB long-term
             (drop_kv_recent, drop_vae_all M+16..)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load_run(d: Path) -> dict | None:
    sj = d / "ablation_summary.json"
    st = d / "ablation_static.json"
    if not sj.exists() or not st.exists():
        return None
    with open(sj) as fh:
        summ = json.load(fh)
    with open(st) as fh:
        static = json.load(fh)
    return {"dir": d.name, "root": d.parent, "per": summ["per_config"], "floor": summ.get("floor_psnr"), "static": static}


def g(per: dict, cfg: str, key: str):
    v = per.get(cfg, {}).get(key)
    return None if v is None else float(v)


def fmt(v, nd=1):
    return "-" if v is None or v != v else f"{v:.{nd}f}"


def rejoin_calls(run: dict, cfg: str, D: int, tau: float = 30.0):
    """Recompute rejoin from the raw CSV (first call >= M+D whose mean PSNR >= tau)."""
    raw = run["root"] / run["dir"] / "ablation_raw.csv"
    if not raw.exists():
        return None
    import csv

    per = {}
    with open(raw) as fh:
        for r in csv.DictReader(fh):
            if r["config"] == cfg and r["psnr"]:
                per.setdefault(int(r["rel_call"]), []).append(float(r["psnr"]))
    for rc in sorted(per):
        if rc >= D and sum(per[rc]) / len(per[rc]) >= tau:
            return rc - D
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=str, default="results/state_migration/gen")
    args = ap.parse_args()
    root = Path(args.root)
    runs = [r for r in (load_run(d) for d in sorted(root.iterdir()) if d.is_dir()) if r]
    if not runs:
        raise SystemExit("no runs found")

    L = ["# Generalization of temporal-semantics claims across video x seed x k\n",
         "PSNR in dB vs each run's own baseline (bit-exact = 99). Columns: proposed policy = sink + meta + in-flight; "
         "no-inflight = sink + meta; no-sink = meta + in-flight.\n",
         "| run | floor | k | policy M+0..7 | policy M+16.. | no-inflight M+16.. | no-sink M+16.. | drop_kv_recent M+16.. | drop_vae_all M+16.. | drop_inflight M+0 | ph_zero_8 gap / rejoin / late | ph_local_8 gap / rejoin / late | ph_localrefresh late | IMMEDIATE | DURABLE | EPHEMERAL |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    tally = {"IMMEDIATE": [0, 0], "DURABLE": [0, 0], "EPHEMERAL": [0, 0]}
    for run in runs:
        per = run["per"]
        k = int(run["static"]["k"])
        pol_e = g(per, "xfer_sink+meta+inflight", "psnr_M0_7")
        pol_l = g(per, "xfer_sink+meta+inflight", "psnr_M16_end")
        noinf = g(per, "xfer_sink+meta", "psnr_M16_end")
        nosink = g(per, "xfer_meta+inflight", "psnr_M16_end")
        dkr = g(per, "drop_kv_recent", "psnr_M16_end")
        dva = g(per, "drop_vae_all", "psnr_M16_end")
        dinf0 = g(per, "drop_inflight", "psnr_M0")
        z_gap, z_late = g(per, "ph_zero_8", "psnr_M0_7"), g(per, "ph_zero_8", "psnr_M16_end")
        l_gap, l_late = g(per, "ph_local_8", "psnr_M0_7"), g(per, "ph_local_8", "psnr_M16_end")
        z_rej, l_rej = rejoin_calls(run, "ph_zero_8", 8), rejoin_calls(run, "ph_local_8", 8)
        lr_late = g(per, "ph_localrefresh", "psnr_M16_end")

        if k < 2 or pol_l is None or noinf is None:
            imm = "n/a (k=1)" if k < 2 else "-"
        else:
            ok = (pol_l - noinf) >= 6.0
            imm = "PASS" if ok else "FAIL"
            tally["IMMEDIATE"][0 if ok else 1] += 1
        if nosink is None or z_late is None:
            dur = "-"
        else:
            ok = nosink < 25.0 and ((z_rej is not None and z_rej <= 8) or (l_rej is not None and l_rej <= 8))
            dur = "PASS" if ok else "FAIL"
            tally["DURABLE"][0 if ok else 1] += 1
        if dkr is None or dva is None:
            eph = "-"
        else:
            ok = dkr >= 35.0 and dva >= 35.0
            eph = "PASS" if ok else "FAIL"
            tally["EPHEMERAL"][0 if ok else 1] += 1
        L.append(f"| {run['dir']} | {fmt(run['floor'])} | {k} | {fmt(pol_e)} | {fmt(pol_l)} | {fmt(noinf)} | {fmt(nosink)} | {fmt(dkr)} | {fmt(dva)} | {fmt(dinf0)} | "
                 f"{fmt(z_gap)} / {z_rej} / {fmt(z_late)} | {fmt(l_gap)} / {l_rej} / {fmt(l_late)} | {fmt(lr_late)} | {imm} | {dur} | {eph} |")
    L.append("")
    L.append("Tally (pass/fail): " + ", ".join(f"{k2} {v[0]}/{v[0] + v[1]}" for k2, v in tally.items()))
    L.append("\nThresholds: IMMEDIATE >= 6 dB gain from the in-flight row; DURABLE no-sink < 25 dB and rejoin <= 8 calls after an 8-chunk-late sink; EPHEMERAL >= 35 dB after dropping recent KV and after dropping VAE caches. Runs whose floor is not 99 are not bit-exact and should be inspected.")
    out = root / "summary.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
