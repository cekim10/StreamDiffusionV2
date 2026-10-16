#!/usr/bin/env python3
"""Aggregate the Experiment E pilot (results/evaluation/<experiment>/policy=*): scenario A (single session, cap event)
and scenario B (N = 4 pre-positioning arrangement at the 250 Mbps crossover). Per policy: T_r after the final move,
others' makespan (B), source / total bytes, re-plans with detection delay, transition delay, drained and duplicate
bytes; comparison with the fluid model at the run's own configuration. Writes summary.csv, summary_by_config.csv,
criteria.md (pilot checks: validity, model agreement, M3-vs-M2 differences with switching costs).

    python tools/eval/aggregate_epilot.py --experiment restore_epilot
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "eval"))
import restore_model as rm  # noqa: E402

CTRL = 0.3
ORDER = ["restart", "reuse_fixed", "reuse_aware_in", "reuse_dyn"]


def load(root: Path):
    runs = []
    for d in sorted(root.glob("policy=*")):
        if (d / "summary.json").exists():
            s = json.load(open(d / "summary.json")); s["dir"] = d.name
            cfg = json.load(open(d / "config.json")); ev = cfg["args"].get("cap_events", "")
            s["scenario"] = "B" if s.get("prepos") else ("A2" if ";" in ev else ("A1" if ev else "A0"))
            runs.append(s)
    return runs


def model(s):
    caps = {}
    for k, v in s["caps_mbps"].items():
        node, d = k.split(":"); caps[(d, node)] = v * 1e6
    args = s_args = None
    cfg = json.load(open(ROOT / "results/evaluation" / s["experiment_dir"] / s["dir"] / "config.json")) if "experiment_dir" in s else None
    rm.SINK_BYTES = s["sink_bytes"]; rm.FLEN = s["frag_bytes"]; rm.NFR = -(-s["sink_bytes"] // s["frag_bytes"])
    if s["scenario"] != "B":
        # initial caps: cap events changed the live caps; recover the pre-change value from caps0 if recorded, else from the event
        ev = s["cap_events_spec"]
        for t, node, d, v in s["dyn"]["cap_changes"]:
            caps[(d, node)] = s["caps0_mbps"][f"{node}:{d}"] * 1e6
        m = rm.Model(s["policy"], s["N"], s["moves"], s["tm_s"], caps, cap_events=ev)
        r = m.run(horizon=600)
        tr = None if r["restored_t"]["s0"] is None else r["restored_t"]["s0"] - r["move_t"]["s0"] + CTRL
        return tr, None, r["source_per_session"] * s["N"], len(r["replans"])
    pp = s["prepos"]
    m = rm.Model(s["policy"], s["N"], 1, s["tm_s"], caps, prepos={"policy": pp["policy"], "probs": pp["probs"], "L": pp["L"], "b": pp["b"], "dest": pp["dest"],
                                                                 "tau": pp["tau"], "others_start": pp.get("others_start", 0.0) or 0.0})
    r = m.run(horizon=400)
    return (None if r["t_r"] is None else r["t_r"] + CTRL), (None if r["others_makespan"] is None else r["others_makespan"] + CTRL), r["source_per_session"] * s["N"], len(r["replans"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="restore_epilot")
    ap.add_argument("--allow_loopback", action="store_true")
    a = ap.parse_args()
    root = ROOT / "results/evaluation" / a.experiment
    runs = load(root)
    skip = {"four_hosts_distinct", "nodes_same_commit"} if a.allow_loopback else set()
    invalid = [r["dir"] for r in runs if not all(v for k, v in r["validation"].items() if k not in skip)]
    rows = []
    for r in runs:
        sess = list(csv.DictReader(open(root / r["dir"] / "sessions.csv")))
        s0 = next(x for x in sess if x["session"] == "s0")
        t_r = float(s0["t_r_s"]) if s0.get("t_r_s") else None
        cfg = json.load(open(root / r["dir"] / "config.json"))
        r["cap_events_spec"] = cfg["args"].get("cap_events", "")
        r["caps0_mbps"] = {k: v for k, v in r["caps_mbps"].items()}
        for t, node, d, v in r["dyn"]["cap_changes"]:   # the summary holds the final caps; the initial one is the default cap_mbps unless overridden
            r["caps0_mbps"][f"{node}:{d}"] = cfg["args"]["holder_mbps"] or cfg["args"]["cap_mbps"]
        mt, mo, ms, mr = model(r)
        dy = r["dyn"]
        # stability flags: premature = a re-plan before the cap change; oscillation = fragments moved back to a provider an
        # earlier re-plan moved them away from
        cc = dy["cap_changes"][0][0] if dy["cap_changes"] else None
        premature = sum(1 for x in dy["replans"] if cc is not None and x["t_s"] < cc)
        moved_from = []
        osc = 0
        for x in dy["replans"]:
            if any(p in moved_from for p in x["to"] if p != x["from"]):
                osc += 1
            moved_from.append(x["from"])
        rows.append({"run": r["dir"], "scenario": r["scenario"], "policy": r["policy"], "rep": r["rep"], "t_r_s": t_r, "model_t_r_s": mt,
                     "others_makespan_s": (r["prepos"] or {}).get("others_makespan_s"), "model_others_s": mo,
                     "source_sinks": r["normalized"]["source_per_session"] * r["N"], "model_source_sinks": ms, "total_sinks": r["normalized"]["total_per_session"] * r["N"],
                     "n_replans": dy["n_replans"], "model_replans": mr, "cap_change_s": dy["cap_changes"][0][0] if dy["cap_changes"] else None,
                     "detection_s": [x["detection_delay_s"] for x in dy["replans"]], "transition_s": [x["transition_delay_s"] for x in dy["replans"]],
                     "drained_mib": [round(x["drained_bytes"] / 2**20, 1) for x in dy["replans"]], "dT_s": [round(x["dT_s"], 1) for x in dy["replans"]],
                     "c_switch_s": [round(x["c_switch_s"], 2) for x in dy["replans"]], "moved": [x["moved_fragments"] for x in dy["replans"]],
                     "duplicate_mib": dy["duplicate_bytes"] / 2**20, "premature_replans": premature, "oscillations": osc,
                     "stale_used": sum(1 for x in dy["replans"] if any(v for v in (x.get("cap_est_stale") or {}).values())), "valid": r["dir"] not in invalid})
    with open(root / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
        for x in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in x.items()})
    G = defaultdict(list)
    for x in rows:
        if x["valid"]:
            G[(x["scenario"], x["policy"])].append(x)
    f = lambda v, d=1: "-" if v is None else f"{v:.{d}f}"  # noqa: E731
    med = lambda xs, k: st.median([x[k] for x in xs if x[k] is not None]) if any(x[k] is not None for x in xs) else None  # noqa: E731
    cfg_rows = []
    out = [f"# Experiment E pilot ({a.experiment}), medians of valid runs", "",
           f"Valid runs {len(runs) - len(invalid)}/{len(runs)}; invalid: {invalid or 'none'}", ""]
    for sc, title in (("A", "Scenario A: forwarder collapse (C egress 1 Gbps -> 62.5 Mbps when D holds 50 %)"), ("A1", "A1: forwarder collapse (C egress 1 Gbps -> 62.5 Mbps when D holds 50 %)"),
                      ("A0", "A0: no-collapse control (same mobility, no cap event)"), ("A2", "A2: collapse, then C recovers to 1 Gbps 5 s later"),
                      ("B", "Scenario B: source share change at the 250 Mbps crossover (N = 4)")):
        pols = [p for p in ORDER if (sc, p) in G]
        if not pols:
            continue
        out += [f"## {title}", "", "| policy | T_r (s) | model | others' makespan | model | source Sinks | model | total Sinks | re-plans (model) | premature | oscillations | detection (s) | transition (s) | drained (MiB) | duplicates (MiB) | dT / C_switch (s) |", "|---|" + "---|" * 15]
        for p in pols:
            xs = G[(sc, p)]
            row = {"scenario": sc, "policy": p, "n": len(xs), "t_r_median": med(xs, "t_r_s"), "model_t_r": xs[0]["model_t_r_s"], "others_median": med(xs, "others_makespan_s"),
                   "model_others": xs[0]["model_others_s"], "source_sinks": med(xs, "source_sinks"), "model_source": xs[0]["model_source_sinks"], "total_sinks": med(xs, "total_sinks"),
                   "n_replans": med(xs, "n_replans"), "model_replans": xs[0]["model_replans"],
                   "detection_s": st.median([d for x in xs for d in x["detection_s"] if d is not None]) if any(d is not None for x in xs for d in x["detection_s"]) else None,
                   "transition_s": st.median([d for x in xs for d in x["transition_s"] if d is not None]) if any(d is not None for x in xs for d in x["transition_s"]) else None,
                   "drained_mib": st.median([d for x in xs for d in x["drained_mib"]]) if any(x["drained_mib"] for x in xs) else None,
                   "duplicate_mib": med(xs, "duplicate_mib"), "premature_replans": sum(x["premature_replans"] for x in xs), "oscillations": sum(x["oscillations"] for x in xs)}
            cfg_rows.append(row)
            dts = "; ".join(f"{d} / {c}" for x in xs[:1] for d, c in zip(x["dT_s"], x["c_switch_s"])) or "-"
            out.append(f"| {p} | {f(row['t_r_median'])} | {f(row['model_t_r'])} | {f(row['others_median'])} | {f(row['model_others'])} | {f(row['source_sinks'], 2)} | {f(row['model_source'], 2)} | "
                       f"{f(row['total_sinks'], 2)} | {f(row['n_replans'], 0)} ({row['model_replans']}) | {row['premature_replans']} | {row['oscillations']} | {f(row['detection_s'], 2)} | {f(row['transition_s'], 2)} | {f(row['drained_mib'])} | {f(row['duplicate_mib'])} | {dts} |")
        m2, m3 = next((r_ for r_ in cfg_rows if r_["scenario"] == sc and r_["policy"] == "reuse_aware_in"), None), next((r_ for r_ in cfg_rows if r_["scenario"] == sc and r_["policy"] == "reuse_dyn"), None)
        if m2 and m3 and m2["t_r_median"] is not None and m3["t_r_median"] is not None:
            d = m2["t_r_median"] - m3["t_r_median"]
            out += ["", f"M3 candidate vs M2 (aware at moves): T_r {m2['t_r_median']:.1f} -> {m3['t_r_median']:.1f} s ({d:+.1f} s, {100 * d / m2['t_r_median']:+.0f} %); "
                    f"source {m2['source_sinks']:.2f} -> {m3['source_sinks']:.2f} Sinks; re-plans {f(m3['n_replans'], 0)}; drained {f(m3['drained_mib'])} MiB per re-plan; duplicates {f(m3['duplicate_mib'])} MiB.", ""]
    with open(root / "summary_by_config.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cfg_rows[0].keys())); w.writeheader(); w.writerows(cfg_rows)
    errs = [abs(x["t_r_s"] - x["model_t_r_s"]) for x in rows if x["valid"] and x["t_r_s"] is not None and x["model_t_r_s"] is not None]
    out += ["## Model agreement", "", f"- T_r: max |measured - model| = {max(errs):.2f} s (median {st.median(errs):.2f}) over {len(errs)} runs"]
    (root / "criteria.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
