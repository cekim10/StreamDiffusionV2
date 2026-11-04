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
NAME = re.compile(r"^(?P<pre>_dryrun_)?expCONC_(?P<cond>C1|C2|C3a|C3b|C4_(?:m3|nom3)_(?:alone|conc)|dry|drycoord)_(?P<m>[a-z_]+)_s(?P<s>[12])$")
HEADER_FACTOR = (1388 + 66) / 1388   # NIC / payload at MSS 1,388 (fig7_report)
CAP_MBPS = 1000.0
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
            "peak_rx_mbps_B": None if dry else peak_rx_mbps(d, "B"), "mem": mem_peaks(d), "barrier": s.get("barrier"),
            "nic": None if dry else nic_check(d), "coord": s.get("coord"),
            # condition-aware validity inputs (user 2026-11-03; judged in condition_validity)
            "validity_non_nic": [w for w in (r["validity_why"] or []) if not str(w).startswith("NIC ")],
            "bw_mbps": configured_mbps(d),
            "sends": sends(d), "nic_series": None if dry else nic_series(d)}


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


def nic_check(d: Path):
    """Verification 1, measured part: every node's host NIC (both sessions' traffic on a shared host) against the cap
    after the header factor: the largest 1 s sample (a burst up to 1.15 x is reported) and the largest 10 s mean
    (above 1.05 x = sustained excess)."""
    out = {}
    lim = CAP_MBPS * HEADER_FACTOR
    for p in sorted(d.glob("node_*/network.csv")):
        rows = list(csv.DictReader(open(p, newline="")))
        host = rows[0]["host"] if rows else p.parent.name
        for k in ("net_tx_mbps", "net_rx_mbps"):
            v = [float(r[k]) for r in rows if r.get(k)]
            m10 = max((sum(v[i:i + 10]) / 10 for i in range(max(1, len(v) - 9))), default=0.0) if len(v) >= 10 else (max(v) if v else 0.0)
            out[f"{host}:{k[4:6]}"] = {"peak_1s_x_cap": max(v, default=0.0) / lim, "peak_10s_x_cap": m10 / lim}
    return out


SAMPLE_OK_S = 1.5   # a NIC sample longer than this cannot resolve a 1 s burst (reported as coarse)
BURST_X, SUSTAINED_X, WINDOW_S = 1.15, 1.05, 10.0   # the stage-2 verification-1 rule, applied to each condition's host cap


def short(h):
    return str(h).split(".")[0]


def configured_mbps(d: Path):
    """The session's emulated link rate: config.json bw_mbps (Full) or the orchestrator's --bw (args.bw, XB policies)."""
    c = json.load(open(d / "config.json")) if (d / "config.json").exists() else {}
    v = c.get("bw_mbps", (c.get("args") or {}).get("bw"))
    return None if v is None else float(v)


def sends(d: Path):
    """Every payload transfer of the session from its events: Full state sends, pre-copy rounds, R-full input parts, M3
    forwards (bytes, seconds, completion, source and destination hosts)."""
    nodes = json.load(open(d / "config.json")).get("nodes") or {}
    host = lambda lb: short((nodes.get(lb) or {}).get("host", lb))  # noqa: E731
    ev = list(csv.DictReader(open(d / "events.csv", newline="")))
    det = lambda e: json.loads(e["detail"]) if e.get("detail", "").startswith("{") else {}  # noqa: E731
    task_dst = {det(e).get("id"): det(e).get("dst") for e in ev if e["event"] == "xb_task_start"}
    starts = {det(e).get("xfer"): det(e) for e in ev if e["event"].endswith(":full_send_start")}
    out = []
    for e in ev:
        lb, _, name = e["event"].partition(":")
        x = det(e)
        if name == "full_send_end":
            st0 = starts.get(x.get("xfer"), {})
            out.append({"kind": "full", "src": host(lb), "dst": host(x.get("to")), "bytes": x.get("bytes"), "s": float(e["t_wall"]) - x["t_start"],
                        "completed": bool(x.get("completed")) and not x.get("cancelled") and x.get("error") is None and x.get("bytes") == st0.get("state_bytes"),
                        "rate_set_bps": st0.get("rate_bps")})
        elif name == "xb_precopy_round":
            out.append({"kind": "precopy", "src": host(lb), "dst": host(task_dst.get(x.get("task"))), "bytes": x.get("dirty_bytes"), "s": x.get("send_s"), "completed": True})
        elif name == "xb_inputs_sent":
            dst = next((det(t).get("dst") for t in ev if t["event"] == "xb_task_start" and det(t).get("id") == x.get("task")), None)
            out.append({"kind": "inputs", "src": host(lb), "dst": host(dst), "bytes": x.get("bytes"), "s": x.get("send_s"), "completed": True})
        elif name == "m3_forward_done":
            out.append({"kind": "m3_forward", "src": host(lb), "dst": host(x.get("to")), "bytes": x.get("bytes"), "s": x.get("s"),
                        "completed": x.get("error") is None and not x.get("cancelled"), "cancelled": bool(x.get("cancelled"))})
    n_start = sum(e["event"] == "xb_task_start" for e in ev); n_done = sum(e["event"] == "xb_task_done" for e in ev)
    return {"list": out, "xb_tasks_started": n_start, "xb_tasks_done": n_done}


def nic_series(d: Path):
    """Per host NIC direction: (t_end, interval s, Mbps) samples (ResourceSampler: byte-counter delta / actual interval)."""
    out = {}
    for p in sorted(d.glob("node_*/network.csv")):
        rows = list(csv.DictReader(open(p, newline="")))
        for k in ("net_tx_mbps", "net_rx_mbps"):
            ser, prev = [], None
            for r in rows:
                t = float(r["t_wall"])
                if prev is not None and r.get(k):
                    ser.append((t, t - prev, float(r[k])))
                prev = t
            out[f"{short(rows[0]['host']) if rows else p.parent.name}:{k[4:6]}"] = ser
    return out


def link_check(ser, cap_mbps):
    """Burst: the largest sample of <= SAMPLE_OK_S against BURST_X x cap; sustained: the largest time-weighted mean over
    consecutive samples spanning >= WINDOW_S against SUSTAINED_X x cap (cap after the header factor)."""
    lim = cap_mbps * HEADER_FACTOR
    fine = [v for _, dt, v in ser if dt <= SAMPLE_OK_S]
    coarse = [(dt, v) for _, dt, v in ser if dt > SAMPLE_OK_S]
    best = 0.0
    for i in range(len(ser)):
        b = span = 0.0
        for _, dt, v in ser[i:]:
            b += v * dt; span += dt
            if span >= WINDOW_S:
                best = max(best, b / span); break
    burst, sus = max(fine, default=0.0) / lim, best / lim
    return {"cap_mbps": cap_mbps, "burst_x": burst, "sustained_x": sus, "n_samples": len(ser), "n_coarse": len(coarse),
            "max_coarse_s": max((dt for dt, _ in coarse), default=0.0), "ok": burst <= BURST_X and sus <= SUSTAINED_X}


def shared_cap(cond):
    return cond in ("C3b", "drycoord") or cond.startswith("C4")


def condition_validity(cond, ss):
    """condition_valid (user 2026-11-03): the original `valid` is kept unchanged; this replaces only its host-NIC rule,
    which assumes one session per host NIC, by the condition's own host cap, and adds per-session checks.
    Host cap per NIC direction: C1 / C2 / C3a (each session shaped to its own 1 Gbps) = cap x the number of the
    condition's sessions whose transfers use that direction (a C2 host carries one session, a C3a source / destination
    two); C3b / C4 (one coordinated shared link) = cap. Per session: the configured rate is the cap (C3b / C4: and the
    coordinator was used), every transfer completed (Full: all bytes of the state; pre-copy / R-full: every task done),
    every transfer's mean payload rate <= SUSTAINED_X x cap (<= BURST_X x cap if shorter than 1 s), and every other
    original validity condition holds."""
    use = {}
    for s, rs in ss.items():
        for x in rs[-1]["sends"]["list"]:
            use.setdefault(f"{x['src']}:tx", set()).add(s); use.setdefault(f"{x['dst']}:rx", set()).add(s)
    for s, rs in ss.items():
        r = rs[-1]
        why, links = list(r["validity_non_nic"]), {}
        if r["failed"]:
            why.append("run failed")
        if r["bw_mbps"] != CAP_MBPS:
            why.append(f"configured rate {r['bw_mbps']} Mbps != {CAP_MBPS:g}")
        if shared_cap(cond) and not r.get("coord"):
            why.append("shared-cap condition without the coordinator")
        sd = r["sends"]
        if not sd["list"]:
            why.append("no transfer recorded")
        if sd["xb_tasks_started"] != sd["xb_tasks_done"]:
            why.append(f"xb tasks done {sd['xb_tasks_done']} / started {sd['xb_tasks_started']}")
        for x in sd["list"]:
            if not x["completed"] and not x.get("cancelled"):
                why.append(f"{x['kind']} {x['src']}->{x['dst']} not completed")
            if x.get("s") and x["s"] > 0 and x.get("bytes"):
                mbps = x["bytes"] * 8 / x["s"] / 1e6
                x["rate_mbps"] = mbps
                if mbps > (SUSTAINED_X if x["s"] >= 1 else BURST_X) * CAP_MBPS:
                    why.append(f"{x['kind']} {x['src']}->{x['dst']} {mbps:.0f} Mbps > cap")
        for k, ser in (r["nic_series"] or {}).items():
            n = 1 if shared_cap(cond) else max(1, len(use.get(k, ())))
            c = link_check(ser, n * CAP_MBPS)
            c["sessions_on_link"] = len(use.get(k, ()))
            links[k] = c
            if not c["ok"]:
                why.append(f"NIC {k} burst {c['burst_x']:.2f} / sustained {c['sustained_x']:.2f} x {n} cap")
        r["condition_valid"], r["condition_why"], r["condition_links"] = not why, why, links


def coord_analysis(log: Path):
    """From the coordinator log: allocation-level cap compliance and, between consecutive allocations, the seconds in
    which flows of different sessions shared a site link (by kind pair) and in which a shared flow was held below the cap."""
    ents = [json.loads(x) for x in open(log) if x.strip()]
    if not ents:
        return None
    shared, held, pairs = 0.0, 0.0, {}
    for a, b in zip(ents, ents[1:]):
        dt = b["t"] - a["t"]
        links = {}
        for g, f in a["flows"].items():
            for k in (f"out:{f['src']}", f"in:{f['dst']}"):
                links.setdefault(k, []).append(f)
        sh = [fl for fl in links.values() if len({f["session"] for f in fl}) >= 2]
        if sh:
            shared += dt
            if any(f["rate_bps"] < a["cap_bps"] - 1 for fl in sh for f in fl):
                held += dt
            for kinds in {" + ".join(sorted({f"{f['session'].split('/')[0][-2:]}:{f['kind']}" for f in fl})) for fl in sh}:
                pairs[kinds] = pairs.get(kinds, 0.0) + dt   # once per interval and kind combination (not per link)
    loads = [v for e in ents for v in e["site_load_bps"].values()]
    return {"entries": len(ents), "cap_ok_all": all(e["cap_ok"] for e in ents), "max_site_load_x_cap": max(loads, default=0.0) / ents[0]["cap_bps"],
            "shared_link_s": shared, "shared_and_held_below_cap_s": held, "shared_by_kinds_s": pairs,
            "flows": sorted({(g, f["kind"]) for e in ents for g, f in e["flows"].items()})}


def overlap(a, b):
    if not a or not b:
        return None
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def f(x, n=2):
    return "-" if x is None else f"{x:.{n}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", default=""); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--coord_log", action="append", default=[], help="coordinator logs to analyze (default: osdi/concurrency/coord_*.jsonl)")
    a = ap.parse_args()
    C = collect(a.prefix, a.dry)
    for (cond, _), ss in C.items():
        if not a.dry:
            condition_validity(cond, ss)
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
    if not a.dry:
        L += ["", "Condition-aware validity (`condition_valid`; the original `valid` above is unchanged). Host cap: C1 / C2 / C3a = 1 Gbps x the "
              "sessions on that NIC direction, each shaped to its own emulated 1 Gbps link (C3a: two independent links on one physical NIC, not a "
              "shared link); C3b / C4 = one shared 1 Gbps. Burst = largest sample of <= 1.5 s (1.03 s typical) <= 1.15 x; sustained = largest "
              "time-weighted mean over >= 10 s <= 1.05 x (after the header factor). Per session: configured rate, completion, per-transfer rate.", "",
              "| cond | method | session | condition_valid | NIC links used (host:dir, sessions, burst / sustained x host cap) | transfers (Mbps payload) | coarse samples (max s) | reasons |",
              "|---|---|---|---|---|---|---|---|"]
        for (c, m), ss in sorted(C.items()):
            for s, rs in sorted(ss.items()):
                r = rs[-1]
                lk = r.get("condition_links") or {}
                used = ", ".join(f"{k} {v['sessions_on_link']}: {v['burst_x']:.3f} / {v['sustained_x']:.3f} x {v['cap_mbps'] / 1000:g}" for k, v in sorted(lk.items()) if v["sessions_on_link"])
                tr = ", ".join(f"{x['kind']} {x.get('rate_mbps', 0):.0f}" for x in r["sends"]["list"])
                co = f"{sum(v['n_coarse'] for v in lk.values())} ({max((v['max_coarse_s'] for v in lk.values()), default=0):.1f})"
                L.append(f"| {c} | {LABEL.get(m, m)} | S{s} | {r.get('condition_valid')} | {used} | {tr} | {co} | {'; '.join(r.get('condition_why') or []) or '-'} |")
    nic = [(c, m, s, k, v) for (c, m), ss in sorted(C.items()) for s, rs in ss.items() for k, v in ((rs[-1].get("nic") or {}).items())]
    if nic:
        L += ["", "Verification 1, measured (host NIC / cap after the header factor; burst 1 s <= 1.15, sustained 10 s <= 1.05):", "",
              "| cond | method | session | host:dir | peak 1 s | peak 10 s mean | ok |", "|---|---|---|---|---|---|---|"]
        for c, m, s, k, v in nic:
            if c in ("C3b",) or c.startswith("C4"):
                L.append(f"| {c} | {LABEL.get(m, m)} | S{s} | {k} | {v['peak_1s_x_cap']:.2f} | {v['peak_10s_x_cap']:.2f} | "
                         f"{v['peak_1s_x_cap'] <= 1.15 and v['peak_10s_x_cap'] <= 1.05} |")
    logs = [Path(x) for x in a.coord_log] or sorted(OUT.glob("coord_*.jsonl"))
    coords = {str(p.name): coord_analysis(p) for p in logs}
    if coords:
        L += ["", "Coordinator logs (verification 1 at the allocation level; flow overlap between sessions):", "",
              "| log | allocations | all sums <= cap | max site load / cap | shared-link s | shared and held below cap s | shared by kinds (s) |", "|---|---|---|---|---|---|---|"]
        for n, c in coords.items():
            if c:
                L.append(f"| {n} | {c['entries']} | {c['cap_ok_all']} | {c['max_site_load_x_cap']:.3f} | {c['shared_link_s']:.1f} | {c['shared_and_held_below_cap_s']:.1f} | "
                         f"{', '.join(f'{k} {v:.1f}' for k, v in c['shared_by_kinds_s'].items()) or '-'} |")
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{a.prefix}conc_pilot_results"
    (OUT / f"{stem}.json").write_text(json.dumps({"runs": {f"{c}|{m}": ss for (c, m), ss in C.items()}, "pairs": pairs, "coord_logs": coords}, indent=1, default=str))
    (OUT / f"{stem}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
