#!/usr/bin/env python3
"""Fig. 14 (osdi/fig14/preregistration.md, DRAFT): OTTER's overheads. Applies the preregistered rules.

14a throughput (new runs, tools/eval/fig14_native_track.py): per (workload, variant) the median over reps of the run's
    median upstream per-chunk wall time in the Fig. 8b window (processed 40-159); variants native (upstream unmodified),
    wrap (the patch, no tracking), track (OTTER's M2 + M3 steady-state tracking per call).
    F14-H1  track / native <= 1.01 on both workloads (medians).
    Reported: track / wrap, wrap / native, tracking ms per call; Fig. 8b native and OTTER (host B) for reference.
14a phases (existing runs; descriptive, analysis fixed here, the data predate it):
    transfer  Fig. 7 OTTER runs: the source's per-call time over the migration window (call 30 to the switch) / its own
              uninterrupted reference session's per-call time (node_A baseline_record service_s, calls 40-159); the
              window's maximum call (the round-1 snapshot) reported separately; the destination's replay time per call.
    staging   Fig. 11 OTTER (staging) runs: the owner's per-call time while a staging flow is active (m3_forward_done
              intervals) / outside them, after the first move.
14b memory (new runs, node --mem_log): per node peak process RSS, peak GPU allocated / reserved, retained and staged
    Sink bytes; per run the replay log and switch bytes (events), the Sink size; Chain: cluster-wide staged state (the
    sum over nodes of retained + staged at the run end and its peak). Descriptive.

    python tools/eval/fig14_report.py            # -> results/evaluation/osdi/fig14/fig14_results.{json,md}
    python tools/eval/fig14_report.py --sanity
    python tools/eval/fig14_report.py --prefix _dryrun_ --dry
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/fig14"
WORKLOADS = ("dog", "bfly")
VARIANTS = ("native", "wrap", "track")
H1_BOUND = 1.01
WINDOW = (40, 159)


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def ratio(a, b):
    return (a / b) if (a is not None and b) else None


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---- 14a native ---------------------------------------------------------------------------------------------------
def native(prefix: str) -> dict:
    d = OUT / f"{prefix}native"
    runs = [json.loads(p.read_text()) for p in sorted(d.glob("*.json")) if not p.name.endswith(".tracking.json")] if d.exists() else []
    cells = {}
    for w in WORKLOADS:
        for v in VARIANTS:
            rs = [r for r in runs if r["workload"] == w and r["variant"] == v and r.get("label", "A") == "A" and r.get("rc") == 0
                  and r.get("n_window", 0) >= WINDOW[1] - WINDOW[0] + 1]
            cells[f"{w}|{v}"] = {"n": len(rs), "median_chunk_s": med([r["median_chunk_s"] for r in rs]), "values": [r["median_chunk_s"] for r in rs],
                                 "track_ms": med([(r.get("tracking") or {}).get("track_ms_median") for r in rs]) if v == "track" else None}
    out = {"cells": cells, "ratios": {}}
    for w in WORKLOADS:
        c = lambda v: cells[f"{w}|{v}"]["median_chunk_s"]  # noqa: E731
        out["ratios"][w] = {"track/native": ratio(c("track"), c("native")), "track/wrap": ratio(c("track"), c("wrap")), "wrap/native": ratio(c("wrap"), c("native"))}
    out["H1"] = {w: (out["ratios"][w]["track/native"] is not None and out["ratios"][w]["track/native"] <= H1_BOUND) for w in WORKLOADS}
    out["F14-H1"] = all(out["H1"].values()) and all(cells[f"{w}|{v}"]["n"] for w in WORKLOADS for v in ("native", "track"))
    for w in WORKLOADS:   # host B native, re-measured in the same session: the baseline of the integrated configuration
        rs = [r for r in runs if r["workload"] == w and r["variant"] == "native" and r.get("label") == "B" and r.get("rc") == 0
              and r.get("n_window", 0) >= WINDOW[1] - WINDOW[0] + 1]
        cells[f"{w}|native_B"] = {"n": len(rs), "median_chunk_s": med([r["median_chunk_s"] for r in rs]), "values": [r["median_chunk_s"] for r in rs]}
    f8 = EVAL / "osdi/fig8/fig8_results.json"
    out["fig8b_reference"] = json.loads(f8.read_text()).get("8b") if f8.exists() else None
    return out


def integrated(prefix: str, dry: bool, nat: dict) -> dict:
    """OTTER integrated (the full harness with M1 + M2 + M3, Fig. 8b's configuration, one migration A -> B): B's
    steady-state per-call time (generation + tracking) after the cutover vs native on B, and A's uninterrupted harness
    reference session (no OTTER code) vs native on A; same session, each against its own host's native."""
    import fig8_report as f8r
    out = {"cells": {}, "ratios": {}}
    for w in WORKLOADS:
        runs = [f8r.otter_run(d, dry) for d in sorted((EVAL / f"{prefix}expF14_int_{w}").glob("policy=*")) if (d / "summary.json").exists()]
        ok = [r for r in runs if r["valid"]]
        refA = []
        for r in ok:
            br = EVAL / f"{prefix}expF14_int_{w}" / r["run"] / "node_A/baseline_record.json"
            if br.exists():
                refA.append(med([x.get("service_s") for x in json.loads(br.read_text()) if WINDOW[0] <= int(x.get("call", -1)) <= WINDOW[1]]))
        c = {"n_runs": len(runs), "n_valid": len(ok), "invalid_why": [r["validity_why"] for r in runs if not r["valid"]],
             "otter_B_per_call_s": med([r["median_per_call_s"] for r in ok]), "otter_B_gen_s": med([r["median_gen_s"] for r in ok]),
             "otter_B_track_ms": med([r["median_track_ms"] for r in ok]), "harness_A_ref_s": med(refA)}
        out["cells"][w] = c
        nb, na = nat["cells"].get(f"{w}|native_B", {}).get("median_chunk_s"), nat["cells"].get(f"{w}|native", {}).get("median_chunk_s")
        out["ratios"][w] = {"integrated_B/native_B": ratio(c["otter_B_per_call_s"], nb), "harness_A/native_A": ratio(c["harness_A_ref_s"], na),
                            "tracking_only_A/native_A": nat["ratios"][w]["track/native"]}
    return out


# ---- 14a phases (existing runs) -----------------------------------------------------------------------------------
def events(d: Path) -> list[tuple[str, float, dict]]:
    return [(r["event"], float(r["t_wall"]), json.loads(r["detail"]) if r.get("detail") else {}) for r in csv.DictReader(open(d / "events.csv", newline=""))]


def transfer_phase(d: Path) -> dict | None:
    s = json.load(open(d / "summary.json"))
    m = list(csv.DictReader(open(d / "metrics.csv", newline="")))
    sw = next((e for e in events(d) if e[0] == "A:xb_precopy_switch"), None)
    br = d / "node_A/baseline_record.json"
    if sw is None or not br.exists():
        return None
    c_sw = int(sw[2].get("call"))
    win = [fnum(r["chunk_s"]) for r in m if r["owner"] == "A" and 30 <= int(r["call"]) < c_sw]
    base = [x.get("service_s") for x in json.loads(br.read_text()) if WINDOW[0] <= int(x.get("call", -1)) <= WINDOW[1]]
    rep = [e[2].get("replay_s") for e in events(d) if e[0] == "B:replay_applied"]
    b = med(base)
    return {"run": d.name, "switch_call": c_sw, "src_window_median_s": med(win), "src_window_max_s": max([x for x in win if x is not None], default=None),
            "src_reference_median_s": b, "src_ratio": ratio(med(win), b), "dst_replay_s_median": med(rep), "n_replayed": len(rep)}


def staging_phase(d: Path) -> dict | None:
    s = json.load(open(d / "summary.json"))
    t0 = s.get("t0_wall")
    ev = events(d)
    iv = [(t - e.get("s", 0.0), t) for n, t, e in ev if n.endswith(":m3_forward_done") and e.get("s") is not None]
    moves = [mv.get("t_req") for mv in s.get("moves", []) if mv.get("t_req") is not None]
    if t0 is None or not iv:
        return None
    first_move = min(moves) if moves else 0.0
    inside, outside = [], []
    for r in csv.DictReader(open(d / "metrics.csv", newline="")):
        t, cs = fnum(r["t_out_rel"]), fnum(r["chunk_s"])
        if t is None or cs is None or t < first_move or str(r.get("missing")) in ("True", "true"):
            continue
        (inside if any(a - t0 <= t <= b - t0 for a, b in iv) else outside).append(cs)
    return {"run": d.name, "n_inside": len(inside), "n_outside": len(outside), "inside_median_s": med(inside), "outside_median_s": med(outside),
            "ratio": ratio(med(inside), med(outside)), "staging_flows": len(iv)}


def phases() -> dict:
    tr = [{**x, "workload": w} for w in WORKLOADS for d in sorted((EVAL / f"expF7_{w}").glob("policy=precopy_replay*")) if (x := transfer_phase(d))]
    sg = [{**x, "workload": w} for w in WORKLOADS for d in sorted((EVAL / f"expF11_chain_{w}").glob("policy=precopy_replay*m3*")) if (x := staging_phase(d))]
    return {"transfer": tr, "staging": sg,
            "transfer_ratio_median": med([x["src_ratio"] for x in tr]), "staging_ratio_median": med([x["ratio"] for x in sg])}


# ---- 14b memory ---------------------------------------------------------------------------------------------------
def memory_run(d: Path) -> dict:
    s = json.load(open(d / "summary.json"))
    ev = events(d)
    nodes = {}
    for p in sorted(d.glob("node_*/memory.csv")):
        lb = p.parent.name[5:]
        rows = list(csv.DictReader(open(p, newline="")))
        col = lambda k: [fnum(r[k]) for r in rows if fnum(r[k]) is not None]  # noqa: E731
        rss = col("rss_mb")
        nodes[lb] = {"rss_first_mb": rss[0] if rss else None, "rss_peak_mb": max(rss, default=None), "gpu_alloc_peak_mb": max(col("gpu_alloc_mb"), default=None),
                     "gpu_reserved_peak_mb": max(col("gpu_reserved_mb"), default=None), "retained_peak_mb": max(col("retained_mb"), default=0.0),
                     "staged_peak_mb": max(col("staged_mb"), default=0.0), "retained_end_mb": (col("retained_mb") or [0.0])[-1],
                     "staged_end_mb": (col("staged_mb") or [0.0])[-1], "n_samples": len(rows),
                     "node_end_peak": (s.get("node_end") or {}).get(lb, {}).get("peak_allocated_mb") if isinstance(s.get("node_end"), dict) else None}
        nodes[lb]["rss_increase_mb"] = (nodes[lb]["rss_peak_mb"] - nodes[lb]["rss_first_mb"]) if rss else None
    sink = next((e.get("sink_nbytes") for n, _, e in ev if n.endswith(":source_prepared")), None)
    # the source's GPU allocation while it serves without any migration state (samples before source_prepared;
    # memory audit 2026-11-03: the transfer snapshot adds a full serialized state on top of this)
    t_prep = next((t for n, t, _ in ev if n.endswith(":source_prepared")), None)
    src_rows = list(csv.DictReader(open(d / "node_A/memory.csv", newline=""))) if (d / "node_A/memory.csv").exists() else []
    serving = [fnum(r["gpu_alloc_mb"]) for r in src_rows if t_prep is not None and float(r["t_wall"]) < t_prep - 1.0]
    serving = [x for x in serving if x is not None][1:]   # the first sample precedes the session's allocation
    sw = [e for n, _, e in ev if n.endswith(":xb_precopy_switch")]
    return {"run": d.name, "rep": s.get("rep"), "path": s.get("path"), "sink_mb": (sink or 0) / 2 ** 20, "nodes": nodes, "src_serving_alloc_mb": med(serving),
            "log_mb": sum(int(e.get("log_bytes") or 0) for e in sw) / 2 ** 20, "switch_mb": sum(int(e.get("final_bytes") or 0) for e in sw) / 2 ** 20,
            "cluster_held_end_mb": sum(n["retained_end_mb"] + n["staged_end_mb"] for n in nodes.values()),
            "cluster_held_peak_mb": sum(n["retained_peak_mb"] + n["staged_peak_mb"] for n in nodes.values())}


def memory(prefix: str) -> dict:
    out = {}
    for scen in ("single", "chain"):
        for w in WORKLOADS:
            base = EVAL / f"{prefix}expF14_mem_{scen}_{w}"
            out[f"{scen}|{w}"] = [memory_run(d) for d in sorted(base.glob("policy=*")) if (d / "summary.json").exists()] if base.exists() else []
    return out


def fmt(x, n=1):
    return "-" if x is None else f"{x:.{n}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--sanity", action="store_true")
    a = ap.parse_args()
    nat = native(a.prefix)
    integ = integrated(a.prefix, a.dry, nat)
    ph = phases() if not a.dry else {"transfer": [], "staging": [], "transfer_ratio_median": None, "staging_ratio_median": None}
    mem = memory(a.prefix)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{a.prefix}fig14_results.json").write_text(json.dumps({"native": nat, "integrated": integ, "phases": ph, "memory": mem}, indent=1, default=str))
    L = ["# Fig. 14 results", "", "Rules: `preregistration.md`. 14a native: medians over reps of each run's median per-chunk time (upstream profile, "
         "processed 40-159).", "", f"F14-H1 {'SUPPORTED' if nat['F14-H1'] else 'NOT SUPPORTED'} (track / native <= {H1_BOUND}): {nat['H1']}", "",
         "| workload | native (s) | wrap (s) | track (s) | track / native | track / wrap | wrap / native | tracking (ms / call) |", "|---|---|---|---|---|---|---|---|"]
    for w in WORKLOADS:
        c, r = nat["cells"], nat["ratios"][w]
        L.append(f"| {w} | {fmt(c[w + '|native']['median_chunk_s'], 4)} (n {c[w + '|native']['n']}) | {fmt(c[w + '|wrap']['median_chunk_s'], 4)} | "
                 f"{fmt(c[w + '|track']['median_chunk_s'], 4)} | {fmt(r['track/native'], 4)} | {fmt(r['track/wrap'], 4)} | {fmt(r['wrap/native'], 4)} | "
                 f"{fmt(c[w + '|track']['track_ms'], 2)} |")
    L += ["", "**Three configurations, each against its own host's native (same session; tracking-only does not stand for OTTER's "
          "whole cost):**", "", "| workload | tracking-only A / native A | OTTER integrated B / native B | harness without OTTER A / native A | "
          "integrated B per call (s): generation + tracking (ms) | valid integrated runs |", "|---|---|---|---|---|---|"]
    for w in WORKLOADS:
        r, c = integ["ratios"][w], integ["cells"][w]
        L.append(f"| {w} | {fmt(r['tracking_only_A/native_A'], 4)} | {fmt(r['integrated_B/native_B'], 4)} | {fmt(r['harness_A/native_A'], 4)} | "
                 f"{fmt(c['otter_B_per_call_s'], 4)} = {fmt(c['otter_B_gen_s'], 4)} + {fmt(c['otter_B_track_ms'], 2)} | {c['n_valid']} / {c['n_runs']} |")
    L += ["", f"14a phases (existing runs, descriptive): source during transfer / its reference {fmt(ph['transfer_ratio_median'], 3)} "
          f"(n {len(ph['transfer'])}); owner during staging / outside {fmt(ph['staging_ratio_median'], 3)} (n {len(ph['staging'])}).", "",
          "## 14b memory (measured, node --mem_log)", "", "| run | node | RSS first / peak (MB) | GPU alloc / reserved peak (MB) | retained peak (MB) | staged peak (MB) |",
          "|---|---|---|---|---|---|"]
    for k, runs in mem.items():
        for r in runs:
            for lb, n in r["nodes"].items():
                L.append(f"| {k} rep {r['rep']} | {lb} | {fmt(n['rss_first_mb'])} / {fmt(n['rss_peak_mb'])} | {fmt(n['gpu_alloc_peak_mb'])} / {fmt(n['gpu_reserved_peak_mb'])} | "
                         f"{fmt(n['retained_peak_mb'])} | {fmt(n['staged_peak_mb'])} |")
            L.append(f"| {k} rep {r['rep']} | cluster | Sink {fmt(r['sink_mb'])} MB; log {fmt(r['log_mb'])} MB; switch {fmt(r['switch_mb'])} MB | | "
                     f"held end {fmt(r['cluster_held_end_mb'])} | held peak {fmt(r['cluster_held_peak_mb'])} |")
    (OUT / f"{a.prefix}fig14_results.md").write_text("\n".join(L) + "\n")
    print("\n".join(L if a.sanity else L[:5]))


if __name__ == "__main__":
    main()
