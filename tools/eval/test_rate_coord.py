#!/usr/bin/env python3
"""Rate coordinator verification (osdi/concurrency/pilot_protocol.md, verification 2: single-session equivalence).

1. `rate_coord.selftest()` (shared cap, release on close).
2. Recorded runs, one session each, every allocation point replayed through today's rule and through the coordinator
   (max-min over the same active flows, sites = the run's hosts):
   - Fig. 7: every migration task alone on its link. Today: min(out cap, in cap). Coordinator: the same flow alone.
   - Fig. 11 (OTTER with M3): at every M3 plan, the active forwards plus any active migration task. Today: the task
     gets the cap; each forward gets min(cap / forwards out of its sender, cap / forwards into its receiver)
     (`_m3_rerate`, cap-conserving equal shares). Coordinator: one max-min over all of them.
   Identical rates at every point = equivalence. Any difference is listed (it would make C3b / C4 not comparable with
   Fig. 7 / 11 for that kind of flow set).

    python tools/eval/test_rate_coord.py
    python tools/eval/test_rate_coord.py --live COORD_LOG   # one-session live run (run_conc.sh dry_coord1): every
                                                            # allocation in the log vs today's rule on the same flows
"""

from __future__ import annotations

import csv
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import rate_coord  # noqa: E402

EVAL = ROOT / "results/evaluation"
CAP = 1e9


def events(d):
    out = []
    for r in csv.DictReader(open(Path(d) / "events.csv", newline="")):
        out.append((r["event"], float(r["t_wall"]), json.loads(r["detail"]) if r["detail"] else {}))
    return out


def tasks_of(ev):
    ends = [(t, e) for e, t, _ in ev if e in ("xb_task_done", "xb_task_cancelled") or e.endswith("xb_precopy_cancelled")]
    tks = []
    for e, t, d in ev:
        if e == "xb_task_start":
            tks.append({"id": d.get("id"), "src": d.get("src"), "dst": d.get("dst"), "t0": t})
    for i, tk in enumerate(tks):   # a task ends at its done / cancel event or, at the latest, when the next task starts
        nxt = tks[i + 1]["t0"] if i + 1 < len(tks) else float("inf")
        tk["t1"] = min([t for t, _ in ends if t > tk["t0"]] + [nxt])
    return tks


def today_rates(fwd, task):
    """Today: the active migration task at the cap; forwards at min(cap / n_out, cap / n_in) among forwards."""
    n_out, n_in = defaultdict(int), defaultdict(int)
    for f in fwd:
        n_out[f["src"]] += 1; n_in[f["dst"]] += 1
    r = {f["id"]: min(CAP / n_out[f["src"]], CAP / n_in[f["dst"]]) for f in fwd}
    if task:
        r[task["id"]] = CAP
    return r


def coord_rates(fwd, task):
    co = rate_coord.Coordinator(CAP)
    for f in fwd + ([task] if task else []):
        co.handle({"op": "open", "session": "s", "id": f["id"], "src": f["src"], "dst": f["dst"]})
    return co.handle({"op": "rates", "session": "s"})["rates"], co.n_violations


def live(log):
    """Every allocation of a one-session run with --coord against today's rule on the same active flows. A difference is
    expected only where today's rule would put more than the cap on a link (a migration task sharing a link with a
    forward); any other difference is a failure."""
    ents = [json.loads(x) for x in open(log) if x.strip()]
    same = over = bad = 0
    for e in ents:
        fl = [{"id": g, "src": f["src"], "dst": f["dst"], "kind": f["kind"]} for g, f in e["flows"].items()]
        fwd = [f for f in fl if f["kind"] == "m3"]
        tasks = [f for f in fl if f["kind"] != "m3"]
        task = tasks[0] if tasks else None
        if len(tasks) > 1:
            bad += 1; print(f"  FAIL {len(tasks)} migration transfers of one session at once"); continue
        a = today_rates(fwd, task)
        b = {g: f["rate_bps"] for g, f in e["flows"].items()}
        if all(abs(a[k] - b[k]) <= 1 for k in a):
            same += 1; continue
        load = defaultdict(float)
        for f in fl:
            load[("out", f["src"])] += a[f["id"]]; load[("in", f["dst"])] += a[f["id"]]
        if any(v > CAP + 1 for v in load.values()):
            over += 1
        else:
            bad += 1; print(f"  FAIL allocation {e['version']} ({e['op']} {e['flow']}): today {a} vs coordinator {b}")
    print(f"  {'ok' if bad == 0 else 'FAIL'} live one-session run: {len(ents)} allocations, {same} identical to today's rule, "
          f"{over} differ only where today's rule exceeds the cap, {bad} other differences")
    return bad == 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--live":
        sys.exit(0 if live(sys.argv[2]) else 1)
    ok = rate_coord.selftest()
    n7 = 0
    for d in sorted(glob.glob(str(EVAL / "expF7_*" / "policy=*"))) + sorted(glob.glob(str(EVAL / "expF12_*_bw1000" / "policy=*"))):
        for tk in tasks_of(events(d)):
            r, _ = coord_rates([], tk)
            ok &= abs(r[tk["id"]] - CAP) < 1; n7 += 1
    print(f"  {'ok' if ok else 'FAIL'} Fig. 7 / 12a (1 Gbps): {n7} migration tasks, each alone: coordinator rate = cap = today's")
    pts = diff = viol = 0
    worst = []
    for d in sorted(glob.glob(str(EVAL / "expF11_*" / "policy=precopy_replay*m3=*"))):
        ev = events(d)
        tks = tasks_of(ev)
        done = {x.get("flow"): t for e, t, x in ev if e.endswith("m3_forward_done")}
        fl = []
        for e, t, x in ev:
            if e != "m3_plan":
                continue
            for f in x.get("flows", []):
                fl.append({"id": f["id"], "src": f["src"], "dst": f["dst"], "t0": t, "t1": done.get(f["id"], float("inf"))})
            act = [f for f in fl if f["t0"] <= t < f["t1"]]
            task = next((k for k in tks if k["t0"] <= t < k["t1"]), None)
            if task and not any(f["src"] == task["src"] or f["dst"] == task["dst"] for f in act):
                task_shared = None   # the task shares no link with a forward: alone on its link in both rules
            else:
                task_shared = task
            a, b = today_rates(act, task_shared), coord_rates(act, task_shared)
            pts += 1; viol += b[1]
            dd = {k: (a[k] / 1e6, b[0][k] / 1e6) for k in a if abs(a[k] - b[0][k]) > 1}
            if dd:
                diff += 1; worst.append((Path(d).parent.name, round(t - ev[0][1], 1), dd))
    good = diff == 0 and viol == 0
    ok &= good
    print(f"  {'ok' if good else 'DIFF'} Fig. 11 M3 plans: {pts} allocation points, {diff} with a different rate, {viol} cap violations (coordinator)")
    for w in worst[:10]:
        print(f"      {w[0]} t+{w[1]} s: today vs coordinator (Mbps) {w[2]}")
    print("ALL PASS" if ok else "NOT EQUIVALENT (see above)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
