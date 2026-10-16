#!/usr/bin/env python3
"""Compare the shared-planner loopback regression (results/evaluation/_regress_planner/<group>/) with the pre-refactor
loopback runs of the same configurations (results/evaluation/_dryrun_{reg,prepos,a3,dissem,e2,fe}/).

Runs are paired by their configuration tag (run id without the timestamp, plus the cap-event spec). For each pair:
restoration outcome (sessions restored), T_r / first restoration (tolerance 0.5 s + 5 %), source and total bytes
(max(0.02 Sink, 1.5 fragments)), duplicates, fragments per link (provider -> destination; 3 fragments, since which fragments a holder
has at a move depends on loopback timing), number of re-plans (exact) and the re-planned provider (exact).
Writes results/evaluation/_regress_planner/comparison.md and exits non-zero on any failure.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "results/evaluation"
OLD = {"reg": "_dryrun_reg", "prepos": "_dryrun_prepos", "a3": "_dryrun_a3", "dissem": "_dryrun_dissem", "e2": "_dryrun_e2", "fe": "_dryrun_fe"}


def tag(d: Path):
    name = re.sub(r"_\d{8}-\d{6}$", "", d.name)
    try:
        ev = json.load(open(d / "config.json"))["args"].get("cap_events", "")
        caps = json.load(open(d / "config.json"))["args"].get("caps", "")
    except Exception:  # noqa: BLE001
        ev = caps = ""
    return f"{name}|{ev}|{caps}"


def info(d: Path):
    s = json.load(open(d / "summary.json"))
    nfr = -(-s["sink_bytes"] // s.get("frag_bytes", 4 << 20))
    links = defaultdict(int)
    for r in csv.DictReader(open(d / "flows.csv")):
        n = int(r.get("n") or 0)
        b = int(r.get("bytes") or 0)
        links[f"{r['src']}->{r['dst']}"] += round(b / s.get("frag_bytes", 4 << 20)) if b else 0
    if "plan" in s:   # dissemination
        return {"t": s["makespan_s"], "restored": s["destinations_complete"], "source": s["normalized"]["source_sinks"], "total": s["normalized"]["total_sinks"],
                "dup": s["bytes"]["duplicate"], "links": dict(links), "replans": 0, "replan_from": [], "nfr": nfr}
    t = (s.get("prepos") or {}).get("t_r_s")
    if t is None:
        sess = list(csv.DictReader(open(d / "sessions.csv")))
        trs = [float(x["t_r_s"]) for x in sess if x.get("t_r_s")]
        t = max(trs) if trs else s["first_restored"]["median"]
    dy = s.get("dyn", {"replans": []})
    return {"t": t, "restored": s["restored_sessions"], "source": s["normalized"]["source_per_session"], "total": s["normalized"]["total_per_session"],
            "dup": s["bytes"]["duplicate"], "links": dict(links), "replans": len(dy["replans"]), "replan_from": [r["from"] for r in dy["replans"]], "nfr": nfr}


def main():
    rows, fails = [], []
    for g, old in OLD.items():
        new_dir = EV / "_regress_planner" / g
        if not new_dir.exists():
            continue
        olds = {tag(d): d for d in (EV / old).glob("p*") if (d / "summary.json").exists()}
        for d in sorted(new_dir.glob("p*")):
            if not (d / "summary.json").exists():
                continue
            o = olds.get(tag(d))
            if o is None:
                rows.append((g, d.name, "no pre-refactor counterpart", "")); continue
            a, b = info(o), info(d)
            prob = []
            if a["restored"] != b["restored"]:
                prob.append(f"restored {a['restored']} vs {b['restored']}")
            if a["t"] is not None and b["t"] is not None and abs(a["t"] - b["t"]) > 0.5 + 0.05 * a["t"]:
                prob.append(f"T {a['t']:.2f} vs {b['t']:.2f}")
            tol = max(0.02, 1.5 / a["nfr"])   # at least one and a half fragments: at loopback scale one fragment is up to 0.03 Sink
            if abs(a["source"] - b["source"]) > tol or abs(a["total"] - b["total"]) > tol:
                prob.append(f"bytes {a['source']:.2f}/{a['total']:.2f} vs {b['source']:.2f}/{b['total']:.2f}")
            if b["dup"]:
                prob.append(f"duplicates {b['dup']}")
            for k in set(a["links"]) | set(b["links"]):
                if abs(a["links"].get(k, 0) - b["links"].get(k, 0)) > 3:
                    prob.append(f"link {k} {a['links'].get(k, 0)} vs {b['links'].get(k, 0)} fragments")
            if a["replans"] != b["replans"] or a["replan_from"] != b["replan_from"]:
                prob.append(f"re-plans {a['replans']} {a['replan_from']} vs {b['replans']} {b['replan_from']}")
            verdict = "PASS" if not prob else "DIFF: " + "; ".join(prob)
            if prob:
                fails.append((g, d.name, verdict))
            rows.append((g, re.sub(r"_\d{8}-\d{6}$", "", d.name), f"{a['t']:.2f} -> {b['t']:.2f}" if a["t"] is not None and b["t"] is not None else "-", verdict))
    out = ["# Shared-planner loopback regression", "", "Pre-refactor loopback runs (`_dryrun_*`) vs the same configurations with the shared planner (`_regress_planner/`).", "",
           "| group | configuration | T (old -> new, s) | verdict |", "|---|---|---|---|"]
    out += [f"| {g} | `{n}` | {t} | {v} |" for g, n, t, v in rows]
    out += ["", f"{len(rows)} configurations compared; {len(fails)} with differences."]
    (EV / "_regress_planner" / "comparison.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
