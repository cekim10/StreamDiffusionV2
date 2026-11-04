#!/usr/bin/env python3
"""Tail-aware rate allocation check (osdi/concurrency/formal_design.md F1; user requirements 1-3, 2026-11-04).

For each session (run directory) and each pre-copy flow:
  1. tail entry: the flow leaves the max-min share (coord_demand) within 0.5 s after its last round's send ended;
  2. achieved vs allocated: between consecutive re-rates inside the round's send, the sender's pacer released
     bytes / seconds (node `coord_rate_applied.pacer_sent_bytes`; the last interval ends at the tail re-rate, which the
     orchestrator applies at once) is within 10 % of the rate in force, for intervals of >= 1 s;
  3. hand-back: when the other session's flow enters its tail and then closes, this flow is re-rated upward
     (500 -> cap - tail -> cap on one shared link) and achieves it.
From the coordinator log: accounted sums <= cap at every allocation (cap_ok), and the rate sequence of each flow.

    python tools/eval/check_wc.py --coord_log LOG RUN_DIR_S1 RUN_DIR_S2
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def evs(run_dir):
    pol = sorted(Path(run_dir).glob("policy=*"))
    if not pol:
        sys.exit(f"no policy=* run under {run_dir}")
    out = []
    for r in csv.DictReader(open(pol[-1] / "events.csv", newline="")):
        out.append((float(r["t_wall"]), r["event"], json.loads(r["detail"]) if r["detail"] else {}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coord_log", required=True)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--tol", type=float, default=0.10)
    ap.add_argument("--min_s", type=float, default=1.0)
    ap.add_argument("--nic_cap_mbps", type=float, default=0.0, help="testbed: also apply the stage-2 NIC rule (burst 1.15 x, 10 s 1.05 x) to every node's host NIC, and give the source host's measured egress in each checked interval")
    a = ap.parse_args()
    ok = True
    nic = {}
    if a.nic_cap_mbps > 0:
        from conc_report import link_check, nic_series
        for run in a.runs:
            pol = sorted(Path(run).glob("policy=*"))[-1]
            for k, ser in nic_series(pol).items():
                nic.setdefault(k, ser)
        for k, ser in sorted(nic.items()):
            c = link_check(ser, a.nic_cap_mbps)
            ok &= c["ok"]
            print(f"  {'ok' if c['ok'] else 'FAIL'} NIC {k}: burst {c['burst_x']:.3f} x, 10 s {c['sustained_x']:.3f} x cap ({c['n_coarse']} coarse samples)")
    L = [json.loads(x) for x in open(a.coord_log)]
    cap_bad = sum(1 for x in L if not x["cap_ok"])
    ok &= cap_bad == 0
    print(f"  {'ok' if cap_bad == 0 else 'FAIL'} coordinator: {len(L)} allocations, accounted sum > cap in {cap_bad}")
    t0 = L[0]["t"]
    seq = {}
    for x in L:
        for g, f in x["flows"].items():
            s = seq.setdefault(g, [])
            r = round(f["rate_bps"] / 1e6)
            if not s or s[-1][1] != r:
                s.append((round(x["t"] - t0, 2), r, "tail" if f.get("demand_bps") is not None else "bulk"))
    for g, s in seq.items():
        print(f"     {g.split('/')[0][-24:]}/{g.split('/')[-1]}: " + " -> ".join(f"{r} ({ph}, {t} s)" for t, r, ph in s))
    for run in a.runs:
        E = evs(run)
        name = Path(run).name
        rounds = [(t, d) for t, e, d in E if e.endswith("xb_precopy_round")]
        dem = [(t, d) for t, e, d in E if e == "coord_demand"]
        opens = [(t, d) for t, e, d in E if e == "coord_open"]
        rates = [(t, d) for t, e, d in E if e.endswith("coord_rate_applied") and d.get("flow_kind") == "precopy"]
        for (t_end, rd) in rounds:
            fid = rd.get("task")
            t_start = t_end - rd["send_s"]
            d_tail = [t for t, d in dem if d.get("flow") == fid and d.get("demand_bps") is not None]
            lat = (d_tail[0] - t_end) if d_tail else None
            good = lat is not None and -0.05 <= lat <= 0.5
            ok &= good
            print(f"  {'ok' if good else 'FAIL'} {name} {fid}: tail registered {'-' if lat is None else f'{lat:.2f} s'} after the round's send ended")
            r0 = next((d["rate_bps"] for t, d in opens if d.get("flow") == fid), None)
            pts = [(t_start, 0, r0)] + [(t, d.get("pacer_sent_bytes", 0), d["rate_bps"]) for t, d in rates if d.get("id") == fid and t_start < t < t_end]
            # end point: the pacer's bytes at the tail re-rate (applied right after the round's send ended); fallback: the
            # round's payload bytes (excludes the log and headers, so it understates the last interval)
            after = [(t, d.get("pacer_sent_bytes", 0)) for t, d in rates if d.get("id") == fid and t_end <= t <= t_end + 0.5]
            pts.append((after[0][0], after[0][1], None) if after else (t_end, rd["dirty_bytes"], None))
            for (ta, sa, ra), (tb, sb, _) in zip(pts, pts[1:]):
                dt = tb - ta
                if dt < a.min_s or ra is None:
                    print(f"     {name} {fid}: {ta - t_start:5.2f}-{tb - t_start:5.2f} s at {ra and ra / 1e6:.0f} Mbps: {dt:.2f} s, not checked (< {a.min_s} s)")
                    continue
                ach = (sb - sa) * 8 / dt
                good = abs(ach - ra) <= a.tol * ra
                ok &= good
                host_tx = ""
                if nic:   # the source host's measured egress (all sessions) over the interval, for the record
                    src = [k for k in nic if k.endswith(":tx") and k.split(":")[0] in str(next((d.get("src_site") for t, d in opens if d.get("flow") == fid), ""))]
                    if src:
                        v = [m for t, dtt, m in nic[src[0]] if ta + 1 <= t <= tb]
                        host_tx = f"; host {src[0]} {sum(v) / len(v):.0f} Mbps measured" if v else ""
                print(f"  {'ok' if good else 'FAIL'} {name} {fid}: {ta - t_start:5.2f}-{tb - t_start:5.2f} s allocated {ra / 1e6:.0f} Mbps, achieved {ach / 1e6:.0f} Mbps{host_tx}")
    # tail record (user, 2026-11-04; record only, no pass / fail): what each tail sent, how close it came to its
    # reservation, and what the other sessions' bulk flows achieved meanwhile (pacer_sample every --coord_sample_s)
    flows = {}
    for run in a.runs:
        E = evs(run)
        name = Path(run).name
        for t, e, d in E:
            if e.endswith("pacer_sample") or e.endswith("coord_rate_applied"):
                if "pacer_sent_bytes" in d:
                    flows.setdefault((name, d.get("id")), {"s": []})["s"].append((t, d["pacer_sent_bytes"]))
            elif e == "coord_demand" and d.get("demand_bps") is not None:
                flows.setdefault((name, d.get("flow")), {"s": []}).setdefault("tail", (t, d["demand_bps"]))
            elif e == "coord_close":
                flows.setdefault((name, d.get("flow")), {"s": []})["close"] = t
    print("  tail record (record only):")
    for (name, fid), f in flows.items():
        if "tail" not in f:
            continue
        t0, T = f["tail"]
        t1 = f.get("close", float("inf"))
        s = sorted(x for x in f["s"] if t0 - 0.3 <= x[0] <= t1)
        if len(s) < 2:
            print(f"     {name} {fid}: tail {t0:.1f}-{t1:.1f}: fewer than 2 pacer samples")
            continue
        iv = [((tb - ta), (sb - sa) * 8 / (tb - ta)) for (ta, sa), (tb, sb) in zip(s, s[1:]) if tb - ta >= 0.3]
        at_T = sum(dt for dt, r in iv if r >= 0.95 * T)
        tb = s[-1][1] - s[0][1]
        others = []
        for (n2, f2), g in flows.items():
            if (n2, f2) == (name, fid):
                continue
            ts = g.get("tail", (float("inf"),))[0]
            w0, w1 = max(t0, s[0][0]), min(t1, ts, s[-1][0])   # the other flow's bulk part inside this tail
            ss = sorted(x for x in g["s"] if w0 - 0.3 <= x[0] <= w1 + 0.3)
            if len(ss) >= 2 and ss[-1][0] - ss[0][0] >= 1.0:
                others.append(f"{n2[-6:]}/{f2} {(ss[-1][1] - ss[0][1]) * 8 / (ss[-1][0] - ss[0][0]) / 1e6:.0f} Mbps over {ss[-1][0] - ss[0][0]:.1f} s")
        print(f"     {name} {fid}: tail {s[-1][0] - s[0][0]:.1f} s, {tb / 1e6:.1f} MB, mean {tb * 8 / max(s[-1][0] - s[0][0], 1e-9) / 1e6:.1f} Mbps, "
              f"max {max((r for _, r in iv), default=0) / 1e6:.1f} Mbps over >= 0.3 s, reservation {T / 1e6:.0f} Mbps, at >= 95 % of it {at_T:.1f} s"
              + (f"; meanwhile bulk {', '.join(others)}" if others else ""))
    print("ALL PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
