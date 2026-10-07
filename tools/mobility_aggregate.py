#!/usr/bin/env python3
"""Summarize repeated-mobility runs: continuity-ready time at the final edge, wasted and total traffic,
execution-state lag, continuity windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else float("nan")


def f(v, nd=1):
    if v is None or (isinstance(v, float) and v != v):
        return "-"
    return f"{v:.{nd}f}" if isinstance(v, float) else str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=str, default="results/state_migration/mobility/mobility_results.json")
    args = ap.parse_args()
    path = Path(args.results)
    res = json.load(open(path))
    S = res[0]["service_s"]
    bw = res[0]["bw_mbps"]
    sink_mb = max(v for r in res for k, v in r["bytes"].items() if k.startswith("A->")) / 2**20  # one full copy on one link
    t_s = sink_mb * 2**20 * 8 / (bw * 1e6)
    L = [f"# Repeated mobility: sink routing policy x mobility interval x hops ({bw:g} Mbps per link, sink <= {sink_mb:.0f} MB, link time T_s = {t_s:.1f} s, S = {S * 1e3:.0f} ms/chunk)\n",
         "Times in seconds after the A->B handoff. moves = when execution left each edge. ready = when the true sink bound at each edge. "
         "ready_final_after_last_move = readiness at the final edge minus the last move time. "
         "wasted = segments stranded on edges execution had already left. total = all link traffic (A->edge real, edge->edge emulated at the same per-link bandwidth; "
         "split gives the new edge two independent ingress links). lag = hops between the execution edge and the last edge with a bound sink, averaged over calls.\n",
         "| policy | hops | T_m | ingress | rho | moves at | ready | ready_final | after last move | traffic by link (MB) | wasted MB | total MB | lag mean / max | PSNR before final bind | PSNR final bind+8.. | PSNR last 8 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(res, key=lambda r: (r["hops"], r["t_m"], r.get("ingress_mult") or 99, r["policy"])):
        calls = r["calls"]
        final = r["edges"][-1]
        bF = r["bound_call"].get(final)
        moves = ", ".join(f"{m['from']}->{m['to']} {m['t']:.1f}" for m in r["moves"])
        ready = ", ".join(f"{e} {t:.1f}" for e, t in r["ready"].items()) or "-"
        last_move = r["moves"][-1]["t"] if r["moves"] else 0.0
        rf = r.get("t_ready_final")
        pre = mean([x["psnr"] for x in calls if bF is None or x["call"] < bF])
        post = mean([x["psnr"] for x in calls if bF is not None and x["call"] >= bF + 8])
        last = mean([x["psnr"] for x in calls[-8:]])
        links = ", ".join(f"{k} {v / 2**20:.0f}" for k, v in r["bytes"].items() if k != "fast")
        ing = r.get("ingress_mult"); ing_s = f"{ing:g}x" if ing else "unlim"
        L.append(f"| {r['policy']} | {r['hops']} | {r['t_m']:g} | {ing_s} | {t_s / r['t_m']:.1f} | {moves} | {ready} | {f(rf)} | {f((rf - last_move) if rf is not None else None)} | {links} | "
                 f"{r['wasted_mb']:.0f} | {r['total_mb']:.0f} | {r['lag_mean']:.2f} / {r['lag_max']} | {f(pre)} | {f(post)} | {f(last)} |")
    L.append("\nReading guide: rho = T_s / T_m. rho < 1: the sink reaches an edge before execution leaves it and the policies should converge. rho > 1: restart wastes what reached obsolete edges and resets the clock at each move; relay accumulates one link time per hop; split keeps delivered segments moving and uses the direct link for the remainder; direct is the oracle.")
    out = path.with_name("mobility_summary.md")
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L)); print(f"\n-> {out}")


if __name__ == "__main__":
    main()
