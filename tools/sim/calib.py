#!/usr/bin/env python3
"""Cluster-scale simulation (osdi/fig_cluster/preregistration.md): model parameters from measured records.

Every parameter is computed here from a committed testbed record (path given per parameter); nothing is typed in.
The calibration set is Figs. 5, 7, 8, 9 (via 7) and 10 (single migrations, A -> B, 1 Gbps); Fig. 11 (repeated moves,
Chain / Cancel, staging) is held out for the validation gate (tools/sim/cluster_sim.py validate).

    python tools/sim/calib.py      # -> results/evaluation/osdi/fig_cluster/calibration.json
"""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OSDI = ROOT / "results/evaluation/osdi"
OUT = OSDI / "fig_cluster/calibration.json"
GB = 1e9
BW_CAL = 1e9            # Figs. 7 / 10 shaping, bits/s (--bw 1000)
WORKLOADS = ("dog", "bfly")


def med(x):
    return x["median"]


def load(rel):
    return json.loads((OSDI / rel).read_text())


def build() -> dict:
    f7, f8, f10 = load("fig7/fig7_results.json")["cells"], load("fig8/fig8_results.json"), load("fig10/fig10_results.json")["cells"]
    m123 = json.loads((ROOT / "results/state_migration/figures/background/m123/m123_figures.data.json").read_text())
    P, src = {}, {}

    def put(name, value, source, how):
        P[name] = value
        src[name] = {"source": source, "derivation": how}

    # ---- per-call generation time (Fig. 8b, OTTER per call on B, median of 5 rep medians, per workload)
    for w in WORKLOADS:
        put(f"t_call_s.{w}", med(f8["8b"][w]["otter_per_call"]), "osdi/fig8/fig8_results.json 8b.<w>.otter_per_call",
            "median time per call (generation + tracking), OTTER on host B")
    # ---- Full: stop, transfer the whole state, resume (Fig. 7)
    for w in WORKLOADS:
        c = f7[w]["full"]
        S = med(c["tx_gb"]) * GB
        put(f"full.state_bytes.{w}", S, "osdi/fig7/fig7_results.json cells.<w>.full.tx_gb", "median transferred bytes")
        put(f"full.overhead_s.{w}", med(c["delivery_gap_s"]) - S * 8 / BW_CAL, "same, delivery_gap_s",
            "gap - state bytes / 1 Gbps (the rest of the stop-and-copy, not link-bound)")
    # ---- P-full (Llumnix-style): rounds S, fS, fS (no-shrink rule stops at the 3rd), final copy fS (Fig. 7; XB / Fig. 9:
    #      3 rounds, no convergence)
    for w in WORKLOADS:
        c, S = f7[w]["precopy_full"], P[f"full.state_bytes.{w}"]
        tx = med(c["tx_gb"]) * GB
        f = (tx / S - 1) / 3
        put(f"pfull.dirty_fraction.{w}", f, "osdi/fig7/fig7_results.json cells.<w>.precopy_full.tx_gb",
            "tx = S (1 + 3 f): rounds S, fS, fS and a final stop-and-copy fS")
        pre = S * (1 + 2 * f)
        put(f"pfull.efficiency.{w}", pre * 8 / BW_CAL / med(c["remote_wall_s"]), "same, remote_wall_s",
            "pre-copy bytes / 1 Gbps / remote-served time (achieved fraction of the link)")
        put(f"pfull.final_overhead_s.{w}", med(c["delivery_gap_s"]) - f * S * 8 / (BW_CAL * P[f"pfull.efficiency.{w}"]), "same, delivery_gap_s",
            "gap - final bytes at the achieved rate")
    # ---- R-full (ServerlessLLM-style): round 1 recomputes calls 0..a0 while the source serves; then the source stops and the
    #      destination recomputes the calls made meanwhile (Fig. 7, a0 = 30, replay time per call = t_call [assumption A3])
    for w in WORKLOADS:
        c, tc = f7[w]["recompute_full"], P[f"t_call_s.{w}"]
        a0 = 30
        rem, gap = med(c["remote_wall_s"]), med(c["delivery_gap_s"])
        put(f"rfull.round1_overhead_s.{w}", rem - a0 * tc, "osdi/fig7/fig7_results.json cells.<w>.recompute_full.remote_wall_s",
            "remote - a0 t_call (a0 = 30, --migration_chunk 30)")
        put(f"rfull.finish_overhead_s.{w}", gap - (rem / tc) * tc, "same, delivery_gap_s", "gap - (calls made during round 1) t_call")
        calls = a0 + rem / tc
        put(f"rfull.input_bytes_per_call.{w}", med(c["tx_gb"]) * GB / calls, "same, tx_gb", "encoded input bytes / calls sent (a0 + round 1 calls)")
    # ---- OTTER (Fig. 10: Full arm = first migration with a full Sink base; Versioned arm = base delta vs a retained version)
    for w in WORKLOADS:
        full = [f10[f"{w}|{a}"]["full"] for a in (10, 60, 150, 240)]
        ver = {a: f10[f"{w}|{a}"]["ver"] for a in (10, 60, 150, 240)}
        Sb = med(full[0]["base_bytes"])
        put(f"otter.sink_bytes.{w}", Sb, "osdi/fig10/fig10_results.json cells.<w>|10.full.base_bytes", "Sink base bytes (full)")
        br_full = st.median(med(x["base_ready_s"]) for x in full)
        b_ver, br_ver = med(ver[10]["base_bytes"]), med(ver[10]["base_ready_s"])
        eff = (Sb - b_ver) * 8 / BW_CAL / (br_full - br_ver)
        put(f"otter.efficiency.{w}", eff, "osdi/fig10/fig10_results.json cells.<w>|*.full / ver.base_ready_s",
            "(full base - age-10 delta) / 1 Gbps / (base ready full - base ready age-10 versioned)")
        put(f"otter.base_overhead_s.{w}", br_ver - b_ver * 8 / (BW_CAL * eff), "same", "base ready (age-10 versioned) - its bytes at the achieved rate")
        put(f"otter.tail_s.{w}", st.median(med(x["readiness_s"]) - med(x["base_ready_s"]) for x in full), "same, full arm",
            "readiness - base ready (replay catch-up after a long base), median over ages")
        put(f"otter.floor_s.{w}", st.median(med(v["readiness_s"]) for v in ver.values()), "same, ver arm",
            "readiness with a small base (replay-window bound), median over ages")
        put(f"otter.interruption_s.{w}", st.median(med(x["interruption_s"]) for x in full + list(ver.values())), "same, interruption_s",
            "cutover interruption, median over arms and ages")
        put(f"otter.delta_bytes.{w}", {a: med(v["base_bytes"]) for a, v in ver.items()}, "same, ver.base_bytes",
            "versioned base bytes vs version age (calls since the retained version)")
        tx = med(f7[w]["precopy_replay"]["tx_gb"]) * GB
        dur = med(f7[w]["precopy_replay"]["ttfo_local_s"])
        put(f"otter.patch_rate_Bps.{w}", max(0.0, tx - Sb) / dur, "osdi/fig7/fig7_results.json cells.<w>.precopy_replay.tx_gb",
            "(bytes - Sink base) / TTFO-local: input log + Sink refresh patches per second of migration")
    # ---- refresh intensity per input (Fig. 5), used to place a session between the two calibrated workloads
    ref = {x["key"]: x["refresh_per_100_calls"] for x in m123["fig5_inputs"]}
    put("refresh_per_100_calls", ref, "results/state_migration/figures/background/m123/m123_figures.data.json fig5_inputs",
        "Sink refreshes per 100 calls, seed 0, 20 inputs")
    put("refresh_anchor", {"dog": ref["dog"], "bfly": ref["bfly"]}, "same", "the two calibrated workloads")
    put("chunk_frames", 4, "configs/wan_causal_dmd_v2v.yaml (4 output frames per call); fig8_results 8b_verdict fps x t_call",
        "frames per call")
    return {"params": P, "sources": src,
            "note": "calibration set: Figs. 5, 7, 8, 10 (single migrations at 1 Gbps); Fig. 11 is held out for validation"}


def main():
    c = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(c, indent=1))
    for k, v in c["params"].items():
        if not isinstance(v, dict):
            print(f"  {k:34s} {v:.6g}")
    print(f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
