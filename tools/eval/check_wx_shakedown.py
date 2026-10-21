#!/usr/bin/env python3
"""WX shakedown check (harness / configuration only): X3 and X5, one run per policy, each workload (21 runs).

    python tools/eval/check_wx_shakedown.py [--dry]   # -> results/evaluation/osdi/expWX/shakedown_check.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from aggregate_m3e import extra  # noqa: E402
from aggregate_wrn import run_rec  # noqa: E402
from aggregate_wx import CFG, WL  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    rows, fails = [], []
    for ws, w in WL.items():
        for x in ("X3", "X5"):
            pols, cap, rho = CFG[x]
            root = ROOT / "results/evaluation" / f"{'_dryrun_' if a.dry else ''}expWX_shk_{ws}_{x}"
            for p in pols:
                ds = sorted(d for d in root.glob(f"policy={p}_bw*") if (d / "summary.json").exists())
                if not ds:
                    fails.append(f"{ws} {x} {p}: no run"); rows.append((ws, x, p, "MISSING", {})); continue
                r = run_rec(ds[-1], a.dry); s = r["s"]; e = extra(r)
                args = json.load(open(ds[-1] / "config.json"))["args"]
                # completed = not cut by max_run_s; ending by the call window is expected where the final owner never
                # reaches 35 dB (refresh-heavy inputs after three moves; RD) and is recorded, not failed (2026-10-21)
                ck = {"valid (W / R / N rules)": r["valid"], "completed (not deadline)": not str(e["stop"]).startswith("deadline"),
                      "bind observed": not r["bind"].censored, "applicable": bool(r["applicable"]), "path A,B,C,D at rho 2": s["path"] == ["A", "B", "C", "D"] and s.get("rho") == rho,
                      "workload video": Path(args.get("node_extra", "")).name != "" and (w in args.get("node_extra", "") or (w == "train" and "train.mp4" in args.get("node_extra", ""))),
                      "TTFO recorded": e["ttfo"] is not None, "chunk service measurable": e["chunk_s_move_to_bind"] is not None, "no duplicate bytes": e["dup_bytes"] == 0}
                if a.dry:
                    ck.pop("workload video")
                if cap:
                    ck["cap event fired exactly once"] = e["cap_fired"] == 1
                if p == "reuse_dyn2":
                    ck["probe size"] = int(args.get("dyn_probe", 0)) == (1 if a.dry else 4)
                bad = [k for k, v in ck.items() if not v]
                fails += [f"{ws} {x} {p}: {k} {r['why'] if k.startswith('valid') else ''}" for k in bad]
                rows.append((ws, x, p, "PASS" if not bad else "FAIL " + "; ".join(bad), {"bind": repr(r["bind"]), "B_source": r["B_source"], "replans": r["replans"], "applicable": r["applicable"], "stop": e["stop"],
                                                                            "rejoin": (s.get("wrn") or {}).get("termination", {}).get("rejoin_observed")}))
    L = [f"# WX shakedown check{' (DRY RUN)' if a.dry else ''}", "", f"**{'PASS' if not fails else 'FAIL'}** ({sum(1 for r in rows if r[3] == 'PASS')} / {len(rows)} runs)", "",
         "| workload | config | policy | result | details |", "|---|---|---|---|---|"] + [f"| {ws} | {x} | {p} | {res} | {det} |" for ws, x, p, res, det in rows]
    od = ROOT / "results/evaluation/osdi/expWX"
    (od / f"{'_dryrun_' if a.dry else ''}shakedown_check.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
