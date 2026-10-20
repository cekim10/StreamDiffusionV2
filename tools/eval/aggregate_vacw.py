#!/usr/bin/env python3
"""VACW v0 verdicts (frozen design results/evaluation/osdi/expM2/vacw_v0_design.md, 9137bc9, section 6 / 7; Amendment 1).

Reads results/evaluation/expVA_<workload>_rho<r>/policy=*/summary.json (+ node events) and applies, unchanged:
  exposure   per cell: every valid split_va rep has >= 1 fresh transition whose snapshot differs from its predecessor
  H1a        every split_va run (12): every bind is of the snapshot active at bind time (orchestrator record) and is
             preceded at that node by an ok whole-digest sink_verified of the same version; success 12 / 12
  H1b        every split_va run: single crossing >= 35 dB at the final owner within the run window; success >= 11 / 12
  H2         per evaluable cell (medians over reps): src(split_va) <= src(restart_fresh) - 0.9 x R_avail and
             aggregate(split_va) <= aggregate(restart_fresh) + 0.05 (Sinks); R_avail = median available verified reuse
  H3         per evaluable cell: median bind-ready after the final move, split_va <= restart_fresh + 1.0 s
  GO / CONDITIONAL / NO-GO as section 7.

    python tools/eval/aggregate_vacw.py      # -> results/evaluation/osdi/expM2/vacw_v0_results.{md,json}
"""

from __future__ import annotations

import csv
import glob
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from wrn_validity import run_validity_wrn  # noqa: E402

WORKLOADS = ["dog", "butterfly-feeding-slow-motion"]
RHOS = ["0.5", "1"]
POLS = ["restart_fresh", "split", "split_va"]
REJOIN_DB = 35.0


def node_bind_check(d: Path) -> tuple[bool, list]:
    """Every node's sink_bind is preceded, at that node, by an ok whole-digest sink_verified of the same version. Uses the
    orchestrator's events.csv (node events forwarded as "<node>:<event>", orchestrator clock); on the GPU testbed the
    node-local events.csv stays on each host."""
    ev = list(csv.DictReader(open(d / "events.csv", newline="")))
    out = []
    for b in [e for e in ev if e["event"].endswith(":sink_bind")]:
        lb = b["event"].split(":")[0]; ver = json.loads(b["detail"]).get("sink_version")
        ok = any(e["event"] == f"{lb}:sink_verified" and json.loads(e["detail"]).get("sink_version") == ver and json.loads(e["detail"]).get("ok")
                 and float(e["t_wall"]) <= float(b["t_wall"]) for e in ev)
        out.append((lb, ver, ok))
    return all(x[2] for x in out) and bool(out), out


def psnr_after_bind(d: Path, s: dict) -> dict:
    fin, bc = s["path"][-1], s["final"]["bind_call"]
    rows = [r for r in csv.DictReader(open(d / "metrics.csv", newline="")) if r["owner"] == fin and r["psnr"] not in ("", "None")]
    ps = [(int(r["call"]), float(r["psnr"])) for r in rows if bc is not None and int(r["call"]) >= bc]
    if not ps:
        return {"crossed": False, "max": None}
    v = [p for _, p in ps]
    sustained = any(all(x >= REJOIN_DB for x in v[i:i + 10]) for i in range(len(v) - 9))
    return {"crossed": any(x >= REJOIN_DB for x in v), "max": max(v), "median": st.median(v), "last10_median": st.median(v[-10:]), "sustained10": sustained,
            "n_calls": len(v), "first_call": ps[0][0], "last_call": ps[-1][0]}


def load():
    runs = []
    for w in WORKLOADS:
        for rho in RHOS:
            for d in sorted((ROOT / f"results/evaluation/expVA_{w}_rho{rho}").glob("policy=*")):
                if not (d / "summary.json").exists():
                    continue
                s = json.load(open(d / "summary.json"))
                ok, bad = run_validity_wrn(s, d)
                v = s["vacw"]
                nb_ok, nb = node_bind_check(d)
                runs.append({"w": w, "rho": rho, "policy": s["policy"], "rep": s["rep"], "dir": str(d.relative_to(ROOT)), "valid": ok, "invalid_reasons": bad,
                             "fresh_transitions": v["fresh_transitions"], "fresh_moves": [m["i"] for m in v["per_move"] if m["fresh"]],
                             "dirty_by_snapshot": [x["dirty_frags"] for x in v["snapshots"][1:]],
                             "binds": v["binds"], "binds_intended": all(b["ok"] for b in v["binds"]) and bool(v["binds"]), "node_binds_verified": nb_ok, "node_binds": nb,
                             "bind_ready": s["latency_after_final_move_s"]["sink_bind"], "rejoin_after_move": s["latency_after_final_move_s"]["rejoin"],
                             "src": v["bytes_sinks"]["source_final_snapshot"], "agg": v["bytes_sinks"]["aggregate"], "invalidated": v["bytes_sinks"]["invalidated"],
                             "potential": v["final_snapshot"]["content_reuse_potential"], "available": v["final_snapshot"]["available_verified_reuse"],
                             "realized": v["final_snapshot"]["realized_reuse"], "per_move": v["per_move"], "psnr": psnr_after_bind(d, s),
                             "stop_reason": s["validation"]["stop_reason"]})
    return runs


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def main():
    runs = load()
    va = [r for r in runs if r["policy"] == "split_va" and r["valid"]]
    out = {"n_runs": len(runs), "n_valid": sum(r["valid"] for r in runs), "cells": {}, "runs": runs}
    # H1a / H1b over every split_va run
    h1a_ok = [r for r in va if r["binds_intended"] and r["node_binds_verified"]]
    out["H1a"] = {"n": len(va), "pass": len(h1a_ok), "n_binds": sum(len(r["binds"]) for r in va),
                  "n_fresh_binds": sum(sum(1 for b in r["binds"] for s0 in [r["binds"][0]["intended_version"]] if b["intended_version"] != s0) for r in va),
                  "verdict": "NOT EVALUABLE" if len(va) < 12 else ("SUPPORTED" if len(h1a_ok) == 12 else "NOT SUPPORTED")}
    h1b_ok = [r for r in va if r["psnr"]["crossed"]]
    out["H1b"] = {"n": len(va), "pass": len(h1b_ok), "verdict": "NOT EVALUABLE" if len(va) < 12 else ("SUPPORTED" if len(h1b_ok) >= 11 else "NOT SUPPORTED"),
                  "by_cell": {f"{w} rho {rho}": sum(1 for r in h1b_ok if r["w"] == w and r["rho"] == rho) for w in WORKLOADS for rho in RHOS}}
    evaluable = []
    for w in WORKLOADS:
        for rho in RHOS:
            c = {p: [r for r in runs if r["w"] == w and r["rho"] == rho and r["policy"] == p and r["valid"]] for p in POLS}
            exposed = len(c["split_va"]) >= 1 and all(any(x and x > 0 for x in r["dirty_by_snapshot"]) for r in c["split_va"])
            enough = all(len(c[p]) >= 3 for p in ("split_va", "restart_fresh"))
            cell = {"valid_reps": {p: len(c[p]) for p in POLS}, "exposure": exposed, "fresh_transitions_split_va": [r["fresh_transitions"] for r in c["split_va"]]}
            R = med([r["available"] for r in c["split_va"]])
            s_va, s_rf = med([r["src"] for r in c["split_va"]]), med([r["src"] for r in c["restart_fresh"]])
            a_va, a_rf = med([r["agg"] for r in c["split_va"]]), med([r["agg"] for r in c["restart_fresh"]])
            b_va, b_rf, b_sp = med([r["bind_ready"] for r in c["split_va"]]), med([r["bind_ready"] for r in c["restart_fresh"]]), med([r["bind_ready"] for r in c["split"]])
            cell.update({"R_avail": R, "potential": med([r["potential"] for r in c["split_va"]]), "realized": med([r["realized"] for r in c["split_va"]]),
                         "src": {"split_va": s_va, "restart_fresh": s_rf, "split": med([r["src"] for r in c["split"]])},
                         "agg": {"split_va": a_va, "restart_fresh": a_rf, "split": med([r["agg"] for r in c["split"]])},
                         "bind_ready": {"split_va": b_va, "restart_fresh": b_rf, "split": b_sp},
                         "crossed": {p: sum(r["psnr"]["crossed"] for r in c[p]) for p in POLS},
                         "psnr_max_median": {p: med([r["psnr"]["max"] for r in c[p]]) for p in POLS},
                         "psnr_last10_median": {p: med([r["psnr"].get("last10_median") for r in c[p]]) for p in POLS},
                         "decomposition_final_move_split_va": {k: med([r["per_move"][-1][k] for r in c["split_va"]]) for k in
                                                               ("wait_boundary_s", "fast_path_s", "snapshot_capture_s", "manifest_install_s", "manifest_wait_s", "plan_after_move_s", "restoration_s", "bind_s", "bind_ready_s")},
                         "dirty_frac_per_fresh_move": sorted({round(x / 412, 3) for r in c["split_va"] for x in r["dirty_by_snapshot"] if x is not None})})
            if not enough or not exposed:
                cell["H2"] = cell["H3"] = "NOT EVALUABLE (" + ("no fresh transition" if not exposed else "< 3 valid reps") + ")"
            else:
                evaluable.append(f"{w} rho {rho}")
                thr = s_rf - 0.9 * R
                cell["H2_detail"] = {"src_threshold": thr, "src_ok": s_va <= thr, "agg_ok": a_va <= a_rf + 0.05}
                cell["H2"] = "SUPPORTED" if (s_va <= thr and a_va <= a_rf + 0.05) else "NOT SUPPORTED"
                cell["H3_detail"] = {"threshold": b_rf + 1.0, "delta_s": b_va - b_rf}
                cell["H3"] = "SUPPORTED" if b_va <= b_rf + 1.0 else "NOT SUPPORTED"
            out["cells"][f"{w} rho {rho}"] = cell
    out["evaluable_cells"] = evaluable
    h23 = all(out["cells"][c]["H2"] == "SUPPORTED" and out["cells"][c]["H3"] == "SUPPORTED" for c in evaluable)
    if out["H1a"]["verdict"] != "SUPPORTED":
        dec = "NO-GO (H1a)"
    elif out["H1b"]["verdict"] != "SUPPORTED":
        dec = "NO-GO (H1b <= 10 of 12 with H1a passing)"
    elif h23 and len(evaluable) >= 2:
        dec = "GO" + (" (T_m > T_s regime only)" if all(c.endswith("rho 0.5") for c in evaluable) else "")
    else:
        dec = "CONDITIONAL"
    out["decision"] = dec
    od = ROOT / "results/evaluation/osdi/expM2"
    (od / "vacw_v0_results.json").write_text(json.dumps(out, indent=1, default=str))
    f2 = lambda x, n=2: "-" if x is None else f"{x:.{n}f}"  # noqa: E731
    L = ["# VACW v0 verdicts (generated by tools/eval/aggregate_vacw.py; frozen rules, design 9137bc9)", "",
         f"Runs: {out['n_valid']} / {out['n_runs']} valid. Decision (section 7): **{dec}**.", "",
         f"- H1a: **{out['H1a']['verdict']}** ({out['H1a']['pass']} / {out['H1a']['n']} split_va runs; {out['H1a']['n_binds']} binds, every bind of the snapshot active at bind time and after an ok whole-digest verification of that version)",
         f"- H1b: **{out['H1b']['verdict']}** ({out['H1b']['pass']} / {out['H1b']['n']} split_va runs cross 35 dB; by cell {out['H1b']['by_cell']})", "",
         "| cell | exposure (fresh transitions per split_va rep) | R_avail / potential / realized | source bytes va / rf / split (Sinks) | aggregate va / rf | H2 | bind-ready va / rf / split (s) | H3 | crossed 35 dB (rf / split / va) | PSNR max (median) rf / split / va | dirty fraction per fresh move |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, c in out["cells"].items():
        L.append(f"| {k} | {'yes' if c['exposure'] else 'no'} {c['fresh_transitions_split_va']} | {f2(c['R_avail'], 3)} / {f2(c['potential'], 3)} / {f2(c['realized'], 3)} | "
                 f"{f2(c['src']['split_va'], 3)} / {f2(c['src']['restart_fresh'], 3)} / {f2(c['src']['split'], 3)} | {f2(c['agg']['split_va'])} / {f2(c['agg']['restart_fresh'])} | {c['H2']} | "
                 f"{f2(c['bind_ready']['split_va'])} / {f2(c['bind_ready']['restart_fresh'])} / {f2(c['bind_ready']['split'])} | {c['H3']} | "
                 f"{c['crossed']['restart_fresh']} / {c['crossed']['split']} / {c['crossed']['split_va']} | {f2(c['psnr_max_median']['restart_fresh'], 1)} / {f2(c['psnr_max_median']['split'], 1)} / {f2(c['psnr_max_median']['split_va'], 1)} | {c['dirty_frac_per_fresh_move']} |")
    L += ["", "Final-move decomposition, split_va (medians, s):", ""]
    for k, c in out["cells"].items():
        L.append(f"- {k}: " + ", ".join(f"{a} {f2(b)}" for a, b in c["decomposition_final_move_split_va"].items()))
    (od / "vacw_v0_results.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
