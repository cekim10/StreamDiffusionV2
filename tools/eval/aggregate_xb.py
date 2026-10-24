#!/usr/bin/env python3
"""Experiment XB aggregation (frozen osdi/expXB/preregistration.md sections 2, 7 and 8; freeze record expXB_freeze.md).

Per scenario and method: the number of valid runs and medians over valid reps of TTFO-local (the final edge), the
delivery gap, remote-served chunks and wall seconds, ESTIMATED remote delivery bytes (H.264 CRF 23 / 28), MEASURED
transmitted bytes, output equivalence after the switchover, and the trajectory at the final edge (first call >= 35 dB,
sustained 10 calls, terminal median). Then XH1a, XH2, XH3 and XH4 by their frozen rules; XH1b and XH5 descriptive.
NOT EVALUABLE: fewer than 3 valid reps of a compared method. No figure of merit combines the notions.

    python tools/eval/aggregate_xb.py [--prefix shk_]     # -> results/evaluation/osdi/expXB/xb_results.{md,json}
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from xb_delivery import delivery_metrics, load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

XB = ("precopy_full", "precopy_sink", "recompute_full", "recompute_win")
LABEL = {"reuse_dyn2": "OTTER", "full": "Full", "split_wait": "Wait-for-Sink", "precopy_full": "P-full", "precopy_sink": "P-sink",
         "recompute_full": "R-full", "recompute_win": "R-win"}
SCEN = ("XB1_dog", "XB1_bfly", "XB2_dog", "XB3_dog", "XB4_dog", "ALT_dog", "ALT_bfly")
EXACT = ("full", "precopy_full", "recompute_full")


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def transmitted_bytes(s: dict, ev: list) -> int | None:
    """MEASURED bytes actually sent on the testbed for the migration (state fragments, fast paths, pre-copy rounds,
    encoded inputs). The output stream is never counted here (it is not transmitted; see the ESTIMATED delivery bytes)."""
    pol = s["policy"]
    if pol.startswith("precopy"):
        return sum(int(e.get("dirty_bytes") or 0) for e in ev if e["event"] == "xb_precopy_round") + \
            sum(int(e.get("final_bytes") or 0) for e in ev if e["event"] == "xb_precopy_switch")
    if pol.startswith("recompute"):
        return int((s.get("inputs") or {}).get("bytes_sent") or 0)
    fg = sum(int(m.get("fg_bytes") or 0) for m in s.get("moves", []))
    full = sum(int(e.get("bytes") or 0) for e in ev if e["event"] == "fg_recv" and e.get("full") in (True, "True"))   # Full migration's state stream
    return int((s.get("bytes") or {}).get("total_sent") or 0) + fg + full


def dest_gpu_seconds(s: dict, ev: list) -> float | None:
    """R-full: destination GPU time spent replaying before it serves = (resume - task start) - time waiting for inputs,
    for the task that switched over."""
    sw = (s.get("switchovers") or [])
    if not sw or not s["policy"].startswith("recompute"):
        return None
    tid = sw[-1]["task"]
    task = next((t for t in s.get("tasks", []) if t["id"] == tid), None)
    res = next((e for e in reversed(ev) if e["event"] == "resume" and e["node"] == sw[-1]["dst"]), None)
    if task is None or res is None or task.get("t_start") is None:
        return None
    t0 = s["t0_wall"] + float(task["t_start"]) if float(task["t_start"]) < 1e8 else float(task["t_start"])
    return float(res["t"]) - t0 - float(res.get("input_wait_s") or 0)


def run_record(d: Path) -> dict:
    s, m, ev = load_run(d)
    pol = s["policy"]
    if pol in XB:
        ok, why = run_validity_xb(s, d)
    else:
        from wrn_validity import run_validity_wrn
        ok, why = run_validity_wrn(s, d, dry=False)
    D = delivery_metrics(s, m, ev)
    eq = D["output_equivalence"][-1] if D["output_equivalence"] else {}
    tr = D["trajectory_final"]
    sw = next((e for e in ev if e["event"] == "xb_precopy_switch"), {})
    sinkless = []
    if pol in ("reuse_dyn2", "split"):
        b = (s.get("final") or {}).get("bind_call")
        fin = s["path"][-1]
        sinkless = [float(r["psnr"]) for r in m if r["owner"] == fin and r.get("psnr") not in ("", None) and b is not None and int(r["call"]) < int(b)]
    est = D["remote_delivery_bytes_ESTIMATED"]
    return {"run": d.name, "policy": pol, "rep": s.get("rep"), "valid": ok, "why": why, "ttfo_local_s": D["ttfo_local_final_s"], "gap_s": D["delivery_gap_s"],
            "remote_chunks": D["remote_chunks"], "remote_wall_s": D["remote_wall_s"], "est_crf23": est["crf23"], "est_crf28": est["crf28"],
            "est_unencoded_remote_chunks": est["remote_chunks_not_encoded"], "tx_bytes": transmitted_bytes(s, ev),
            "out_eq": f"{eq.get('matching')}/{eq.get('checked')}" if eq else None, "terminal_psnr": tr["terminal_median_psnr"], "first35": tr["first_ge35_idx"],
            "sustained10": tr["sustained10_idx"], "sinkless_median_psnr": med(sinkless), "switch_reason": sw.get("reason"),
            "dest_gpu_s": dest_gpu_seconds(s, ev), "rtt_ms": ((s.get("rtt_measured_lan") or {}).get("A-B") or {}).get("median_ms")}


def summarize(recs: list[dict]) -> dict:
    v = [r for r in recs if r["valid"]]
    out = {"n_valid": len(v), "n_runs": len(recs)}
    for k in ("ttfo_local_s", "gap_s", "remote_chunks", "remote_wall_s", "est_crf23", "est_crf28", "tx_bytes", "terminal_psnr", "first35", "sinkless_median_psnr", "dest_gpu_s"):
        out[k] = med([r[k] for r in v])
    out["out_eq"] = [r["out_eq"] for r in v]
    out["switch_reasons"] = sorted({r["switch_reason"] for r in v if r["switch_reason"]})
    out["sustained_runs"] = sum(1 for r in v if r["sustained10"] is not None)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", default="", help="'shk_' to run the code on the shakedown (not evidence)")
    a = ap.parse_args()
    R, runs = {}, {}
    for sc in SCEN:
        root = ROOT / "results/evaluation" / f"expXB_{a.prefix}{sc}"
        if not root.exists():
            continue
        recs = [run_record(d) for d in sorted(root.glob("policy=*")) if (d / "summary.json").exists()]
        runs[sc] = recs
        R[sc] = {pol: summarize([r for r in recs if r["policy"] == pol]) for pol in sorted({r["policy"] for r in recs})}
    NE = lambda *xs: any(x is None or x.get("n_valid", 0) < 3 for x in xs)  # noqa: E731
    H = {}
    # XH1a: XB1, both workloads; TTFO-local(OTTER) <= 0.25 x each exact method's
    rows = []
    for sc in ("XB1_dog", "XB1_bfly"):
        S = R.get(sc, {})
        o = S.get("reuse_dyn2")
        for pol in EXACT:
            x = S.get(pol)
            if NE(o, x):
                rows.append({"scenario": sc, "method": pol, "verdict": "NOT EVALUABLE"}); continue
            ratio = o["ttfo_local_s"] / x["ttfo_local_s"]
            rows.append({"scenario": sc, "method": pol, "otter_s": o["ttfo_local_s"], "method_s": x["ttfo_local_s"], "ratio": ratio, "verdict": ratio <= 0.25})
    H["XH1a"] = {"rows": rows, "verdict": ("NOT EVALUABLE" if any(r["verdict"] == "NOT EVALUABLE" for r in rows) or not rows else ("SUPPORTED" if all(r["verdict"] is True for r in rows) else "NOT SUPPORTED"))}
    # XH2: every P-full run in XB1 ends by the round limit or the non-convergence rule
    pf = [r for sc in ("XB1_dog", "XB1_bfly") for r in runs.get(sc, []) if r["policy"] == "precopy_full" and r["valid"]]
    H["XH2"] = {"runs": len(pf), "reasons": sorted({r["switch_reason"] for r in pf}),
                "verdict": "NOT EVALUABLE" if len(pf) < 6 else ("SUPPORTED" if all(r["switch_reason"] in ("round_limit", "no_shrink") for r in pf) else "NOT SUPPORTED")}
    # XH3: R-full destination GPU-seconds at trigger 120 >= 3 x at trigger 30 (dog)
    a30, a120 = R.get("XB1_dog", {}).get("recompute_full"), R.get("XB2_dog", {}).get("recompute_full")
    if NE(a30, a120) or not (a30 and a120 and a30["dest_gpu_s"] and a120["dest_gpu_s"]):
        H["XH3"] = {"verdict": "NOT EVALUABLE"}
    else:
        rr = a120["dest_gpu_s"] / a30["dest_gpu_s"]
        H["XH3"] = {"t30_s": a30["dest_gpu_s"], "t120_s": a120["dest_gpu_s"], "ratio": rr, "verdict": "SUPPORTED" if rr >= 3 else "NOT SUPPORTED"}
    # XH4: remote-serving seconds of P-sink and R-full >= 5 x OTTER's TTFO-local, at rho 1 (XB3) and rho 2 (XB4)
    rows4 = []
    for sc in ("XB3_dog", "XB4_dog"):
        S = R.get(sc, {}); o = S.get("reuse_dyn2")
        for pol in ("precopy_sink", "recompute_full"):
            x = S.get(pol)
            if NE(o, x):
                rows4.append({"scenario": sc, "method": pol, "verdict": "NOT EVALUABLE"}); continue
            rows4.append({"scenario": sc, "method": pol, "remote_wall_s": x["remote_wall_s"], "otter_ttfo_s": o["ttfo_local_s"],
                          "ratio": x["remote_wall_s"] / o["ttfo_local_s"], "verdict": x["remote_wall_s"] >= 5 * o["ttfo_local_s"]})
    H["XH4"] = {"rows": rows4, "verdict": ("NOT EVALUABLE" if any(r["verdict"] == "NOT EVALUABLE" for r in rows4) or not rows4 else ("SUPPORTED" if all(r["verdict"] is True for r in rows4) else "NOT SUPPORTED"))}
    f = lambda x, n=2: "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))  # noqa: E731
    L = [f"# XB results{' (SHAKEDOWN DATA - code test, not evidence)' if a.prefix else ''}", "",
         "Medians over valid reps. TTFO-local, delivery gap, remote serving, RTT and transmitted bytes are MEASURED; remote delivery bytes are ESTIMATED (H.264 size of remotely served output, never transmitted). WAN / radio latency is not measured.", ""]
    for sc, S in R.items():
        L += [f"## {sc}", "", "| method | valid | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (MB) | transmitted (GB) | output equivalence | first >= 35 dB idx | sustained runs | terminal PSNR | Sink-less median PSNR | switch reasons |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for pol in ("reuse_dyn2", "full", "split_wait", "precopy_full", "precopy_sink", "recompute_full", "recompute_win"):
            x = S.get(pol)
            if not x:
                continue
            L.append(f"| {LABEL[pol]} | {x['n_valid']}/{x['n_runs']} | {f(x['ttfo_local_s'])} | {f(x['gap_s'])} | {f(x['remote_chunks'], 0)} | {f(x['remote_wall_s'], 1)} | "
                     f"{f(x['est_crf23'] and x['est_crf23'] / 1e6, 1)} / {f(x['est_crf28'] and x['est_crf28'] / 1e6, 1)} | {f(x['tx_bytes'] and x['tx_bytes'] / 1e9)} | {x['out_eq']} | "
                     f"{f(x['first35'], 0)} | {x['sustained_runs']} | {f(x['terminal_psnr'], 1)} | {f(x['sinkless_median_psnr'], 1)} | {', '.join(x['switch_reasons']) or '-'} |")
        L.append("")
    L += ["## Hypotheses (frozen rules)", "",
          f"- **XH1a** (TTFO-local OTTER <= 0.25 x each exact method, XB1 both workloads): **{H['XH1a']['verdict']}**"]
    for r in H["XH1a"]["rows"]:
        L.append(f"  - {r['scenario']} vs {LABEL[r['method']]}: " + (f"{f(r.get('otter_s'))} s vs {f(r.get('method_s'))} s, ratio {f(r.get('ratio'), 4)}" if 'ratio' in r else "") + f" -> {r['verdict']}")
    L += [f"- **XH2** (P-full never converges at 1 Gbps): **{H['XH2']['verdict']}** ({H['XH2']['runs']} runs; reasons {H['XH2']['reasons']})",
          f"- **XH3** (R-full destination GPU-seconds at trigger 120 >= 3 x at 30): **{H['XH3']['verdict']}** " + (f"({f(H['XH3'].get('t30_s'), 1)} s -> {f(H['XH3'].get('t120_s'), 1)} s, x{f(H['XH3'].get('ratio'))})" if 'ratio' in H['XH3'] else ""),
          f"- **XH4** (remote-serving seconds of P-sink and R-full >= 5 x OTTER's TTFO-local, rho 1 and 2): **{H['XH4']['verdict']}**"]
    for r in H["XH4"]["rows"]:
        L.append(f"  - {r['scenario']} {LABEL[r['method']]}: " + (f"{f(r.get('remote_wall_s'), 1)} s vs 5 x {f(r.get('otter_ttfo_s'))} s (x{f(r.get('ratio'), 1)})" if 'ratio' in r else "") + f" -> {r['verdict']}")
    L += ["- **XH1b** (hybrid and approximate methods) and **XH5** (OTTER's trajectory cost): descriptive, in the scenario tables above (Sink-less median PSNR, first call >= 35 dB, terminal PSNR)."]
    inval = [(sc, r["run"], r["why"]) for sc, rs in runs.items() for r in rs if not r["valid"]]
    if inval:
        L += ["", "## Invalid runs", ""] + [f"- {sc} {run}: {why}" for sc, run, why in inval]
    out = ROOT / "results/evaluation/osdi/expXB" / (f"_{a.prefix}xb_results" if a.prefix else "xb_results")
    out.with_suffix(".md").write_text("\n".join(L) + "\n")
    out.with_suffix(".json").write_text(json.dumps({"scenarios": R, "hypotheses": H, "runs": runs}, indent=1, default=str))
    print("\n".join(L))


if __name__ == "__main__":
    main()
