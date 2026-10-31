#!/usr/bin/env python3
"""Fig. 8 (osdi/fig8/preregistration.md): applies the preregistered rules as written.

8a  continuity, re-analysis of the 40 Fig. 7 runs: per run the delivery intervals after the trigger (the Fig. 7 delivery
    log), T_ref = their median, stalls = intervals > 1.5 x T_ref, cumulative stall time S(t) = sum of (interval - T_ref)
    over the stalls up to t. F8-H1: median total stall(OTTER) <= 0.25 x the smallest baseline median, each workload.
8b  steady-state throughput on host B: native StreamDiffusionV2 (upstream inference.py, per-chunk wall time, chunks
    40-159) vs OTTER with M2 + M3 tracking (expF8 runs: B's generation time + its tracking time per call, from the
    switch + 10 calls to the run's end). F8-H2: median OTTER time per call <= 1.03 x median native, each workload.

    python tools/eval/fig8_report.py                 # -> results/evaluation/osdi/fig8/fig8_results.{json,md}
    python tools/eval/fig8_report.py --sanity        # per-run detail of whatever exists so far
    python tools/eval/fig8_report.py --prefix _dryrun_ --dry
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
from fig7_report import c1, delivered_rows, run_record, summary_stats  # noqa: E402
from xb_delivery import load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/fig8"
NATIVE = OUT / "native"
WORKLOADS = {"dog": "Low-refresh", "bfly": "High-refresh"}
METHODS = ("full", "precopy_full", "recompute_full", "precopy_replay")
LABEL = {"full": "Full", "precopy_full": "Llumnix-style", "recompute_full": "ServerlessLLM-style", "precopy_replay": "OTTER"}
BASELINES = METHODS[:3]
N_REPS = 5
STALL_X = 1.5          # a stall: interval > 1.5 x T_ref
H1_RATIO = 0.25
H2_RATIO = 1.03
SETTLE = 10            # B's steady window starts 10 calls after its first call
NATIVE_WINDOW = 120    # chunks 40-159
BUSY_PREFIX = ("xb_task", "xb_precopy", "replay_", "flow", "frag", "m3_", "staging", "migration")   # event names of migration / staging work


# ---------------------------------------------------------------- 8a
def stalls(rows):
    ts = [0.0] + [r["t"] for r in rows]
    iv = [(a, b, b - a) for a, b in zip(ts, ts[1:])]
    t_ref = st.median(x for _, _, x in iv)
    S, curve, out = 0.0, [[0.0, 0.0]], []
    for a, b, x in iv:
        if x > STALL_X * t_ref:
            S += x - t_ref
            out.append({"t_start": a, "t_end": b, "interval_s": x, "excess_s": x - t_ref})
            curve.append([b, S])
    curve.append([ts[-1], S])
    return {"t_ref_s": t_ref, "total_stall_s": S, "n_stalls": len(out), "stalls": out, "curve": curve, "t_end_s": ts[-1],
            "max_interval_s": max(x for _, _, x in iv)}


def panel_a(prefix, dry):
    res, verdict = {}, {}
    for w in WORKLOADS:
        cells = {m: [] for m in METHODS}
        for d in sorted((EVAL / f"{prefix}expF7_{w}").glob("policy=*")):
            if not (d / "summary.json").exists():
                continue
            rec = run_record(d, dry)
            s, m, _ = load_run(d)
            sa = stalls(delivered_rows(s, m))
            assert abs(sa["max_interval_s"] - rec["delivery_gap_s"]) < 1e-6, (d, sa["max_interval_s"], rec["delivery_gap_s"])   # same log as Fig. 7
            cells[rec["policy"]].append({"run": d.name, "rep": rec["rep"], "valid": rec["valid"], **sa})
        res[w] = {mth: {"n_valid": sum(r["valid"] for r in rs), "n_runs": len(rs),
                        "total_stall_s": summary_stats([r["total_stall_s"] for r in rs if r["valid"]]),
                        "n_stalls": summary_stats([r["n_stalls"] for r in rs if r["valid"]]),
                        "t_ref_s": summary_stats([r["t_ref_s"] for r in rs if r["valid"]]), "runs": rs} for mth, rs in cells.items()}
        ok = all(res[w][mth]["n_valid"] >= N_REPS for mth in METHODS)
        if ok:
            best = min(res[w][b]["total_stall_s"]["median"] for b in BASELINES)
            ratio = res[w]["precopy_replay"]["total_stall_s"]["median"] / best
            verdict[w] = {"evaluable": True, "ratio": ratio, "holds": ratio <= H1_RATIO}
        else:
            verdict[w] = {"evaluable": False}
    h1 = all(v.get("holds") for v in verdict.values()) if all(v["evaluable"] for v in verdict.values()) else None
    return res, verdict, h1


# ---------------------------------------------------------------- 8b
def native_cells():
    out = {}
    for w in WORKLOADS:
        for lb in ("A", "B"):
            rs = []
            for f in sorted(NATIVE.glob(f"{lb}_{w}_rep*.json")):
                r = json.loads(f.read_text())
                why = []
                if r.get("rc") != 0:
                    why.append(f"rc {r.get('rc')}")
                if r.get("n_window") != NATIVE_WINDOW:
                    why.append(f"{r.get('n_window')} window chunks")
                if not (r.get("input") or {}).get("equal") or (r.get("input") or {}).get("loader_equal") is not True:
                    why.append("looped input not verified")
                if "L40S" not in str(r.get("gpu")):
                    why.append(f"gpu {r.get('gpu')}")
                rs.append({"rep": r["rep"], "valid": not why, "why": why, "median_chunk_s": r.get("median_chunk_s"), "commit": r.get("commit"),
                           "upstream_average_fps": r.get("upstream_average_fps")})
            out[(w, lb)] = rs
    return out


def otter_run(d: Path, dry: bool):
    s, m, ev = load_run(d)
    ok, why = run_validity_xb(s, d, dry=dry)
    rows = delivered_rows(s, m)
    C1 = c1(s, ev, rows)
    B = sorted((r for r in m if r["owner"] == "B" and r.get("chunk_s") not in ("", None)), key=lambda r: int(r["call"]))
    win = B[SETTLE:]
    gen = [float(r["chunk_s"]) for r in win]
    trk = [float(r["track_ms"]) / 1e3 if r.get("track_ms") not in ("", None) else None for r in win]
    if any(x is None for x in trk):
        why = why + ["track_ms missing"]
    trk = [x or 0.0 for x in trk]
    c0 = int(win[0]["call"]) if win else None
    # no migration or staging work inside the window: no migration / staging event after the window's first output
    t0 = min((float(r["t_out_rel"]) for r in win), default=None)
    after = set()
    for e in csv.DictReader(open(d / "events.csv", newline="")):
        try:
            tr = float(e["t_rel"])
        except (TypeError, ValueError):
            continue
        if t0 is not None and tr > t0:
            after.add(e["event"].split(":", 1)[-1])
    busy = sorted(n for n in after if n.startswith(BUSY_PREFIX))
    if busy:
        why = why + [f"migration / staging events in the window: {busy}"]
    per = [g + t for g, t in zip(gen, trk)]
    return {"run": d.name, "rep": s.get("rep"), "valid": ok and C1["pass"] and bool(win) and not why, "validity_why": why, "c1_pass": C1["pass"],
            "window_calls": [c0, int(win[-1]["call"])] if win else None, "n_window": len(win),
            "median_gen_s": st.median(gen) if gen else None, "median_track_ms": st.median(trk) * 1e3 if trk else None,
            "max_track_ms": max(trk) * 1e3 if trk else None, "median_per_call_s": st.median(per) if per else None, "events_in_window": sorted(after)}


def panel_b(prefix, dry):
    nat = native_cells()
    res, verdict = {}, {}
    for w in WORKLOADS:
        ot = [otter_run(d, dry) for d in sorted((EVAL / f"{prefix}expF8_{w}").glob("policy=precopy_replay*")) if (d / "summary.json").exists()]
        nb = nat[(w, "B")]
        cell = {"native_B": summary_stats([r["median_chunk_s"] for r in nb if r["valid"]]),
                "native_A": summary_stats([r["median_chunk_s"] for r in nat[(w, "A")] if r["valid"]]),
                "otter_per_call": summary_stats([r["median_per_call_s"] for r in ot if r["valid"]]),
                "otter_gen": summary_stats([r["median_gen_s"] for r in ot if r["valid"]]),
                "otter_track_ms": summary_stats([r["median_track_ms"] for r in ot if r["valid"]]),
                "native_runs": {"A": nat[(w, "A")], "B": nb}, "otter_runs": ot}
        res[w] = cell
        if cell["native_B"]["n"] >= N_REPS and cell["otter_per_call"]["n"] >= N_REPS:
            ratio = cell["otter_per_call"]["median"] / cell["native_B"]["median"]
            verdict[w] = {"evaluable": True, "ratio": ratio, "holds": ratio <= H2_RATIO,
                          "fps_native": 4 / cell["native_B"]["median"], "fps_otter": 4 / cell["otter_per_call"]["median"]}
        else:
            verdict[w] = {"evaluable": False, "n_native_B": cell["native_B"]["n"], "n_otter": cell["otter_per_call"]["n"]}
    h2 = all(v.get("holds") for v in verdict.values()) if all(v["evaluable"] for v in verdict.values()) else None
    return res, verdict, h2


def f(x, n=3):
    return "-" if x is None else f"{x:.{n}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--sanity", action="store_true")
    a = ap.parse_args()
    A, va, h1 = panel_a(a.prefix, a.dry)
    B, vb, h2 = panel_b(a.prefix, a.dry)
    if a.sanity:
        for w in WORKLOADS:
            for mth in METHODS:
                for r in A[w][mth]["runs"]:
                    print(f"8a {w} {LABEL[mth]} rep {r['rep']}: valid {r['valid']} T_ref {f(r['t_ref_s'])} total stall {f(r['total_stall_s'], 2)} s in {r['n_stalls']} stalls "
                          + ", ".join(f"{x['interval_s']:.2f}@{x['t_start']:.1f}" for x in r["stalls"]))
            for lb in ("A", "B"):
                for r in B[w]["native_runs"][lb]:
                    print(f"8b {w} native {lb} rep {r['rep']}: valid {r['valid']} {r['why']} median chunk {f(r['median_chunk_s'], 4)} s (upstream avg fps {r['upstream_average_fps']})")
            for r in B[w]["otter_runs"]:
                print(f"8b {w} OTTER rep {r['rep']}: valid {r['valid']} {r['validity_why']} C1 {r['c1_pass']} window {r['window_calls']} gen {f(r['median_gen_s'], 4)} s "
                      f"+ track {f(r['median_track_ms'], 3)} ms (max {f(r['max_track_ms'], 2)}) = {f(r['median_per_call_s'], 4)} s")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    stem = OUT / f"{a.prefix}fig8_results"
    rec = {"8a": {w: {m: {k: v for k, v in c.items()} for m, c in A[w].items()} for w in WORKLOADS}, "8a_verdict": va, "F8_H1": h1,
           "8b": B, "8b_verdict": vb, "F8_H2": h2}
    stem.with_suffix(".json").write_text(json.dumps(rec, indent=1, default=str))
    L = ["# Fig. 8 results" + (" (dry run)" if a.dry else ""), "",
         f"**F8-H1 (total stall): {'SUPPORTED' if h1 else 'NOT SUPPORTED' if h1 is False else 'NOT EVALUABLE'}. "
         f"F8-H2 (native performance): {'SUPPORTED' if h2 else 'NOT SUPPORTED' if h2 is False else 'NOT EVALUABLE'}.**", ""]
    for w in WORKLOADS:
        L += [f"## {WORKLOADS[w]} ({w})", "", "| method | valid / runs | total stall (s) | stalls | T_ref (s) |", "|---|---|---|---|---|"]
        for mth in METHODS:
            c = A[w][mth]; x = c["total_stall_s"]
            L.append(f"| {LABEL[mth]} | {c['n_valid']} / {c['n_runs']} | {f(x['median'], 2)} [{f(x['q1'], 2)}-{f(x['q3'], 2)}] | {f(c['n_stalls']['median'], 0)} | {f(c['t_ref_s']['median'])} |")
        v = va[w]
        L += ["", f"F8-H1 ratio {f(v.get('ratio'))} -> {v.get('holds')}", ""]
        c = B[w]; v = vb[w]
        L += ["| 8b | n | per call (s) | frames/s |", "|---|---|---|---|"]
        for k, lab in (("native_A", "native, host A"), ("native_B", "native, host B"), ("otter_gen", "OTTER generation, B"), ("otter_per_call", "OTTER generation + tracking, B")):
            x = c[k]
            L.append(f"| {lab} | {x['n']} | {f(x['median'], 4)} [{f(x['q1'], 4)}-{f(x['q3'], 4)}] | {f(4 / x['median'] if x['median'] else None, 2)} |")
        L += ["", f"OTTER tracking per call: median {f(c['otter_track_ms']['median'], 3)} ms. F8-H2 ratio {f(v.get('ratio'), 4)} -> {v.get('holds')}", ""]
    stem.with_suffix(".md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
