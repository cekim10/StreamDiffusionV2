#!/usr/bin/env python3
"""Fig. 12a (osdi/fig12/preregistration.md, DRAFT): bandwidth sensitivity of one migration, the Fig. 7 protocol at
0.25 / 0.5 / 1 / 2.5 Gbps and native. Applies the preregistered rules.

Per run: the Fig. 7 record (fig7_report.run_record: validity, C1, TTFO-local, delivery gap, bytes, cutover), plus for
OTTER the readiness decomposition from its events (seconds after migration_start):
  sink     the Sink base is on the destination        (A:replay_base_sent)
  caught   the replay has caught up with the source   (B:replay_caught_up)
  first    the destination's first output             (B:first_output)
  sink_share = sink / first: the share of the time to the destination's first output spent moving the Sink.
Per (workload, bandwidth, method): medians [IQR] over valid reps.

F12-H1  OTTER median delivery gap <= 2.5 s at every bandwidth, both workloads.
F12-H2  OTTER median sink_share >= 0.5 at 0.25, 0.5 and 1 Gbps, both workloads (the Sink transfer is the bottleneck of
        readiness there). Reported, not tested: B* = the lowest bandwidth whose median sink_share < 0.5 ("none" if none).
F12-H3  OTTER median gap < every baseline's median gap at every bandwidth, both workloads. Reported: the ratio OTTER /
        best baseline per bandwidth; the benefit-shrink region = bandwidths with ratio > 0.5.
Exploratory: TTFO-local OTTER vs ServerlessLLM-style per bandwidth (a crossover is predicted at low bandwidth).

    python tools/eval/fig12_report.py [--with_fig7]       # -> results/evaluation/osdi/fig12/fig12_results.{json,md}
    python tools/eval/fig12_report.py --sanity
    python tools/eval/fig12_report.py --prefix _dryrun_ --dry
"""

from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import fig7_report as f7  # noqa: E402

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/fig12"
WORKLOADS = f7.WORKLOADS
METHODS, LABEL, BASELINES = f7.METHODS, f7.LABEL, f7.BASELINES
BWS = (250, 500, 1000, 2500, 0)          # Mbps; 0 = native
H2_BWS = (250, 500, 1000)
GAP_BOUND, SHARE, SHRINK = 2.5, 0.5, 0.5
NAME = re.compile(r"^(?:_dryrun_)?expF12_(?P<w>[a-z]+)_bw(?P<bw>\d+)$")


def bw_label(bw: int) -> str:
    return "native" if bw == 0 else f"{bw / 1000:g} Gbps"


def otter_breakdown(d: Path) -> dict:
    import csv

    ev = [(r["event"], float(r["t_wall"])) for r in csv.DictReader(open(d / "events.csv", newline=""))]

    def t(name):
        return next((tw for e, tw in ev if e == name), None)
    t0 = t("migration_start")
    if t0 is None:
        return {}
    x = {k: (None if v is None else v - t0) for k, v in
         {"sink_s": t("A:replay_base_sent"), "caught_s": t("B:replay_caught_up"), "first_s": t("B:first_output")}.items()}
    x["sink_share"] = (x["sink_s"] / x["first_s"]) if (x["sink_s"] is not None and x["first_s"]) else None
    return x


def peak_rx_mbps(d: Path, label: str = "B") -> float | None:
    """The destination's highest 10 s mean NIC receive rate during the run: the achieved link throughput (the only
    measure of 'native', which has no cap)."""
    import csv
    p = d / f"node_{label}" / "network.csv"
    if not p.exists():
        return None
    v = [float(r["net_rx_mbps"]) for r in csv.DictReader(open(p, newline="")) if r.get("net_rx_mbps")]
    return max((st.mean(v[i:i + 10]) for i in range(max(1, len(v) - 9))), default=None) if v else None


def records(prefix: str, dry: bool, with_fig7: bool) -> list[dict]:
    out = []
    for base in sorted(EVAL.glob(f"{prefix}expF12_*")):
        g = NAME.match(base.name)
        if not g:
            continue
        for d in sorted(base.glob("policy=*")):
            if (d / "summary.json").exists():
                r = f7.run_record(d, dry)
                r.update(workload=g["w"], bw=int(g["bw"]), source="fig12", peak_rx_mbps=peak_rx_mbps(d))
                if r["policy"] == "precopy_replay":
                    r["breakdown"] = otter_breakdown(d)
                out.append(r)
    if with_fig7 and not prefix:   # D4: the Fig. 7 runs as the 1 Gbps cell
        for w in WORKLOADS:
            for d in sorted((EVAL / f"expF7_{w}").glob("policy=*")):
                if (d / "summary.json").exists():
                    r = f7.run_record(d, dry)
                    r.update(workload=w, bw=1000, source="fig7")
                    if r["policy"] == "precopy_replay":
                        r["breakdown"] = otter_breakdown(d)
                    out.append(r)
    return out


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def stats(xs):
    xs = [x for x in xs if x is not None]
    return {"median": med(xs), "q1": f7.q(xs, 0.25), "q3": f7.q(xs, 0.75), "n": len(xs), "values": xs}


def analyze(recs: list[dict]) -> dict:
    cells = {}
    for w in WORKLOADS:
        for bw in BWS:
            for p in METHODS:
                rs = [r for r in recs if r["workload"] == w and r["bw"] == bw and r["policy"] == p]
                ok = [r for r in rs if r["valid"] and not r["failed"]]
                c = {"n_runs": len(rs), "n_valid": len(ok), "sources": sorted({r["source"] for r in rs}),
                     **{k: stats([r[k] for r in ok]) for k in ("ttfo_local_s", "delivery_gap_s", "cutover_interruption_s")},
                     "tx_gb": stats([(r["tx_bytes"] or 0) / 1e9 for r in ok]),
                     "peak_rx_mbps": stats([r.get("peak_rx_mbps") for r in ok]),
                     "pfull_round_limit": sum(1 for r in ok if r["bytes"].get("switch_reason") == "round_limit") if p == "precopy_full" else None}
                if p == "precopy_replay":
                    c["breakdown"] = {k: stats([(r.get("breakdown") or {}).get(k) for r in ok]) for k in ("sink_s", "caught_s", "first_s", "sink_share")}
                cells[f"{w}|{bw}|{p}"] = c
    def cm(w, bw, p, k):
        return cells[f"{w}|{bw}|{p}"][k]["median"]
    v = {"H1": {}, "H2": {}, "H3": {}, "B_star": {}, "ratio": {}, "shrink": {}, "ttfo_vs_rfull": {}}
    for w in WORKLOADS:
        gaps = {bw: cm(w, bw, "precopy_replay", "delivery_gap_s") for bw in BWS}
        v["H1"][w] = all(g is not None and g <= GAP_BOUND for g in gaps.values())
        shares = {bw: cells[f"{w}|{bw}|precopy_replay"]["breakdown"]["sink_share"]["median"] for bw in BWS}
        v["H2"][w] = all(shares[b] is not None and shares[b] >= SHARE for b in H2_BWS)
        order = sorted(BWS, key=lambda b: 1e9 if b == 0 else b)
        v["B_star"][w] = next((bw_label(b) for b in order if shares[b] is not None and shares[b] < SHARE), "none")
        ok3 = True
        for bw in BWS:
            base = [cm(w, bw, p, "delivery_gap_s") for p in BASELINES]
            o = gaps[bw]
            if o is None or any(b is None for b in base):
                ok3 = False; v["ratio"][f"{w}|{bw}"] = None; continue
            ok3 = ok3 and all(o < b for b in base)
            v["ratio"][f"{w}|{bw}"] = o / min(base)
            ot, rt = cm(w, bw, "precopy_replay", "ttfo_local_s"), cm(w, bw, "recompute_full", "ttfo_local_s")
            v["ttfo_vs_rfull"][f"{w}|{bw}"] = (ot / rt) if (ot and rt) else None
        v["H3"][w] = ok3
        v["shrink"][w] = [bw_label(b) for b in BWS if (v["ratio"].get(f"{w}|{b}") or 0) > SHRINK]
    v["F12-H1"] = all(v["H1"].values()); v["F12-H2"] = all(v["H2"].values()); v["F12-H3"] = all(v["H3"].values())
    return {"cells": cells, "verdicts": v}


def fmt(x, n=2):
    return "-" if x is None else f"{x:.{n}f}"


def write(res: dict, recs, prefix: str):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{prefix}fig12_results.json").write_text(json.dumps({**res, "runs": recs}, indent=1, default=str))
    v = res["verdicts"]
    L = ["# Fig. 12a results", "", "Rules: `preregistration.md`. Medians [IQR] over valid reps.", "",
         f"F12-H1 {'SUPPORTED' if v['F12-H1'] else 'NOT SUPPORTED'} {v['H1']}; F12-H2 {'SUPPORTED' if v['F12-H2'] else 'NOT SUPPORTED'} {v['H2']}; "
         f"F12-H3 {'SUPPORTED' if v['F12-H3'] else 'NOT SUPPORTED'} {v['H3']}; B* {v['B_star']}; benefit-shrink region {v['shrink']}", ""]
    for w in WORKLOADS:
        L += [f"## {WORKLOADS[w]} ({w})", "", "| bandwidth | method | valid / runs | TTFO-local (s) | gap (s) | bytes (GB) | peak 10 s rx at B (Gbps) | OTTER sink / first (s), share |",
              "|---|---|---|---|---|---|---|---|"]
        for bw in BWS:
            for p in METHODS:
                c = res["cells"][f"{w}|{bw}|{p}"]
                b = c.get("breakdown") or {}
                bd = (f"{fmt(b['sink_s']['median'], 1)} / {fmt(b['first_s']['median'], 1)}, {fmt(b['sink_share']['median'])}") if b else ""
                rl = f" (round limit {c['pfull_round_limit']})" if c.get("pfull_round_limit") else ""
                L.append(f"| {bw_label(bw)} | {LABEL[p]}{rl} | {c['n_valid']} / {c['n_runs']} | {fmt(c['ttfo_local_s']['median'], 1)} | "
                         f"{fmt(c['delivery_gap_s']['median'])} | {fmt(c['tx_gb']['median'])} | "
                         f"{fmt((c['peak_rx_mbps']['median'] or 0) / 1e3 if c['peak_rx_mbps']['median'] else None)} | {bd} |")
        L += ["", "Gap ratio OTTER / best baseline: " + ", ".join(f"{bw_label(b)} {fmt(v['ratio'].get(f'{w}|{b}'), 3)}" for b in BWS),
              "TTFO-local OTTER / ServerlessLLM-style (exploratory): " + ", ".join(f"{bw_label(b)} {fmt(v['ttfo_vs_rfull'].get(f'{w}|{b}'), 2)}" for b in BWS), ""]
    (OUT / f"{prefix}fig12_results.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:5]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--sanity", action="store_true")
    ap.add_argument("--with_fig7", action="store_true", help="D4: count the Fig. 7 runs as the 1 Gbps cell")
    a = ap.parse_args()
    recs = records(a.prefix, a.dry, a.with_fig7)
    if a.sanity:
        for r in recs:
            b = r.get("breakdown") or {}
            print(f"== {r['workload']} {bw_label(r['bw'])} {r['policy']} rep {r['rep']} ({r['source']}): valid {r['valid']} {r['validity_why'][:3]}")
            print(f"   TTFO-local {fmt(r['ttfo_local_s'])} | gap {fmt(r['delivery_gap_s'])} | bytes {fmt((r['tx_bytes'] or 0) / 1e9, 3)} GB | "
                  f"C1 {r['c1']['pass']}" + (f" | sink {fmt(b.get('sink_s'))} caught {fmt(b.get('caught_s'))} first {fmt(b.get('first_s'))} share {fmt(b.get('sink_share'))}" if b else ""))
    write(analyze(recs), recs, a.prefix)


if __name__ == "__main__":
    main()
