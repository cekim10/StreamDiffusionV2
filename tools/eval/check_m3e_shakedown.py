#!/usr/bin/env python3
"""M3E shakedown check (harness / configuration only; no hypothesis is judged). One run per policy per scenario in
results/evaluation/expM3E_shk_S*/. Pass = every check passes in all 16 runs.

    python tools/eval/check_m3e_shakedown.py [--dry]   # -> results/evaluation/osdi/expM3E/shakedown_check.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from aggregate_m3e import SCEN, extra  # noqa: E402
from aggregate_wrn import run_rec  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    rows, fails = [], []
    for sc, (_, pols) in SCEN.items():
        root = ROOT / "results/evaluation" / f"{'_dryrun_' if a.dry else ''}expM3E_shk_{sc}"
        for p in pols:
            ds = sorted(d for d in root.glob(f"policy={p}_bw*") if (d / "summary.json").exists())
            if not ds:
                fails.append(f"{sc} {p}: no run"); rows.append((sc, p, "MISSING", {})); continue
            r = run_rec(ds[-1], a.dry); s = r["s"]; x = extra(r)
            args = json.load(open(ds[-1] / "config.json"))["args"]
            ck = {"valid (W / R / N rules)": r["valid"],
                  "completed (not deadline / window)": x["stop"] not in ("deadline", "window_exhausted") and not str(x["stop"]).startswith("deadline"),
                  "bind observed": not r["bind"].censored,
                  "applicable (no promotion before final bind)": bool(r["applicable"]),
                  "path A,B,C,D at rho 2": s["path"] == ["A", "B", "C", "D"] and s.get("rho") == 2.0,
                  "TTFO recorded": x["ttfo"] is not None,
                  "chunk service move->bind measurable": x["chunk_s_move_to_bind"] is not None,
                  "no duplicate bytes": x["dup_bytes"] == 0}
            if sc in ("S2", "S3", "S5"):
                ck["cap event fired exactly once"] = x["cap_fired"] == 1
            if sc == "S1":
                net = (s.get("hybrid") or {}).get("network_summary") or {}
                ck["3 network sessions, all restored"] = (s.get("hybrid") or {}).get("n_network_sessions") == 3 and net.get("restored_sessions") == 3
            if p == "reuse_dyn2":
                ck[f"probe size {1 if a.dry else 4}"] = int(args.get("dyn_probe", 0)) == (1 if a.dry else 4) and x["probe_frags_max"] <= (1 if a.dry else 4)
            bad = [k for k, v in ck.items() if not v]
            fails += [f"{sc} {p}: {k} ({r['why'] if k.startswith('valid') else ''})" for k in bad]
            rows.append((sc, p, "PASS" if not bad else "FAIL " + "; ".join(bad), {"dir": ds[-1].name, "bind": repr(r["bind"]), "ttfo": x["ttfo"], "B_source": r["B_source"],
                                                                                   "replans": r["replans"], "probes": x["probes"], "cap": x["cap_fired"], "stop": x["stop"]}))
    L = [f"# M3E shakedown check{' (DRY RUN)' if a.dry else ''}", "", f"**{'PASS' if not fails else 'FAIL'}** ({len(rows) - len([r for r in rows if r[2] != 'PASS'])} / {len(rows)} runs)", "",
         "| scenario | policy | result | details |", "|---|---|---|---|"] + [f"| {sc} | {p} | {res} | {det} |" for sc, p, res, det in rows]
    od = ROOT / "results/evaluation/osdi/expM3E"
    (od / f"{'_dryrun_' if a.dry else ''}shakedown_check.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
