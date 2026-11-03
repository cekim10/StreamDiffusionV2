#!/usr/bin/env python3
"""Concurrency pilot report (osdi/concurrency/pilot_protocol.md; DRAFT, not frozen; no hypothesis is tested).

Per session run (expCONC_<cond>_<method>_s<1|2>): the Fig. 7 record (validity, TTFO-local, max. output gap, bytes;
fig7_report.run_record), the trigger time on the host clock, the migration window (trigger -> first local output),
served calls per second inside it (the source makes its first 30 calls before the trigger without serving them, so the
reference for this rate is C1's), the destination's peak 10 s NIC receive rate (the
host's NIC: on a shared host it includes the other session) and node memory peaks (--mem_log). Per pair: the trigger
offset and the overlap of the two migration windows (the pilot checks that the windows really overlap). Every
two-session value is shown next to C1 (S1 alone, same method) as an absolute difference.

    python tools/eval/conc_report.py [--prefix _dryrun_ --dry]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import fig7_report as f7  # noqa: E402
from fig12_report import peak_rx_mbps  # noqa: E402

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/concurrency"
NAME = re.compile(r"^(?P<pre>_dryrun_)?expCONC_(?P<cond>[A-Za-z0-9]+)_(?P<m>[a-z_]+)_s(?P<s>[12])$")
LABEL = {"full": "Full", "recompute_full": "R-full", "precopy_replay": "OTTER"}


def trigger_wall(d: Path):
    for r in csv.DictReader(open(d / "events.csv", newline="")):
        if r["event"].endswith("migration_start"):
            return float(r["t_wall"])
    return None


def mem_peaks(d: Path):
    out = {}
    for p in sorted(d.glob("node_*/memory.csv")):
        rows = list(csv.DictReader(open(p, newline="")))
        num = lambda k: [float(r[k]) for r in rows if r.get(k) not in ("", None)]  # noqa: E731
        out[p.parent.name[5:]] = {"rss_peak_gb": max(num("rss_mb"), default=0) / 1024, "gpu_reserved_peak_gb": max(num("gpu_reserved_mb"), default=0) / 1024}
    return out


def record(d: Path, dry: bool):
    r = f7.run_record(d, dry)
    s, m, _ = f7.load_run(d)
    t_trig = trigger_wall(d)
    ttfo = r["ttfo_local_s"]
    win = (0.0, ttfo) if ttfo is not None else None
    ts = []   # every served call's output time, including before the trigger (delivered_rows keeps t >= 0 only)
    for x in m:
        try:
            if str(x.get("missing")) not in ("True", "true"):
                ts.append(float(x["t_out_rel"]))
        except (TypeError, ValueError):
            pass
    rate = lambda a, b: (sum(1 for t in ts if a <= t < b) / (b - a)) if b > a else None  # noqa: E731
    return {**{k: r[k] for k in ("run", "policy", "valid", "validity_why", "failed", "ttfo_local_s", "delivery_gap_s", "tx_bytes")},
            "trigger_wall": t_trig, "window_wall": None if (win is None or t_trig is None) else (t_trig + win[0], t_trig + win[1]),
            "calls_per_s_window": rate(*win) if win else None,
            "peak_rx_mbps_B": None if dry else peak_rx_mbps(d, "B"), "mem": mem_peaks(d), "barrier": s.get("barrier")}


def collect(prefix, dry):
    out = {}
    for d in sorted(EVAL.glob(f"{prefix}expCONC_*")):
        g = NAME.match(d.name)
        if not g:
            continue
        for rd in sorted(d.glob("policy=*")):
            if (rd / "summary.json").exists():
                out.setdefault((g["cond"], g["m"]), {}).setdefault(int(g["s"]), []).append(record(rd, dry))
    return out


def overlap(a, b):
    if not a or not b:
        return None
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def f(x, n=2):
    return "-" if x is None else f"{x:.{n}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", default=""); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    C = collect(a.prefix, a.dry)
    L = ["# Concurrency pilot (measured; pilot, not a hypothesis test)", "", "Protocol: `pilot_protocol.md`. One run per session; "
         "C1 = S1 alone. Window = trigger -> first local output. NIC = the destination host's peak 10 s receive rate.", "",
         "| cond | method | session | valid | TTFO-local (s) | gap (s) | bytes (GB) | served calls/s in window | dest. NIC peak (Mbps) | GPU reserved / RSS peak A, B (GB) | vs C1: TTFO / gap (s) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    pairs = []
    for (cond, m), ss in sorted(C.items()):
        base = (C.get(("C1", m)) or {}).get(1, [None])[-1]
        for s, rs in sorted(ss.items()):
            r = rs[-1]
            mm = r["mem"]
            mem = ", ".join(f"{f(mm.get(lb, {}).get('gpu_reserved_peak_gb'), 1)} / {f(mm.get(lb, {}).get('rss_peak_gb'), 1)}" for lb in ("A", "B"))
            dt = "" if (cond == "C1" or base is None or None in (r["ttfo_local_s"], base["ttfo_local_s"])) else \
                f"{r['ttfo_local_s'] - base['ttfo_local_s']:+.2f} / {r['delivery_gap_s'] - base['delivery_gap_s']:+.2f}"
            L.append(f"| {cond} | {LABEL.get(m, m)} | S{s} | {r['valid']} {r['validity_why'] or ''} | {f(r['ttfo_local_s'])} | {f(r['delivery_gap_s'])} | "
                     f"{f((r['tx_bytes'] or 0) / 1e9, 3)} | {f(r['calls_per_s_window'])} | {f(r['peak_rx_mbps_B'], 0)} | {mem} | {dt} |")
        if 1 in ss and 2 in ss:
            r1, r2 = ss[1][-1], ss[2][-1]
            off = None if None in (r1["trigger_wall"], r2["trigger_wall"]) else r2["trigger_wall"] - r1["trigger_wall"]
            ov = overlap(r1["window_wall"], r2["window_wall"])
            short = min((r["ttfo_local_s"] for r in (r1, r2) if r["ttfo_local_s"] is not None), default=None)
            pairs.append({"cond": cond, "method": m, "trigger_offset_s": off, "window_overlap_s": ov, "overlap_share_of_shorter": (ov / short) if (ov is not None and short) else None,
                          "both_completed": not r1["failed"] and not r2["failed"], "both_valid": r1["valid"] and r2["valid"]})
    L += ["", "| cond | method | trigger offset S2 - S1 (s) | window overlap (s) | overlap / shorter window | both completed | both valid |", "|---|---|---|---|---|---|---|"]
    for p in pairs:
        L.append(f"| {p['cond']} | {LABEL.get(p['method'], p['method'])} | {f(p['trigger_offset_s'], 3)} | {f(p['window_overlap_s'])} | {f(p['overlap_share_of_shorter'])} | "
                 f"{p['both_completed']} | {p['both_valid']} |")
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{a.prefix}conc_pilot_results"
    (OUT / f"{stem}.json").write_text(json.dumps({"runs": {f"{c}|{m}": ss for (c, m), ss in C.items()}, "pairs": pairs}, indent=1, default=str))
    (OUT / f"{stem}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
