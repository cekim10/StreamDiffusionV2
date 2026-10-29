#!/usr/bin/env python3
"""M3-S1 duplicate-receipt classifier (osdi/m3s1/preregistration.md, Amendment 1).

The restore node marks a fragment "dup" when it already holds that (session, fragment_id), with no notion of version
(`restore_node._receiver`). Under the M2 delta protocol a destination that holds a *stale* copy of an entry (refreshed
since its snapshot tag) is sent that entry again by design, so every staging run of M3-S1 fails the frozen
`no_duplicates` check. This tool reads the per-node fragment logs (node_X/fragments.csv: `recv` rows with ok = verified
and not dup) and classifies every duplicate receipt of the Sink session:

    stale_resend   via a base flow; the held copy's snapshot tag s is such that the entry was refreshed in (s, c0]
                   (the M2 delta protocol re-sends it by design; the stale copy is overwritten)
    drain_race     via a base flow; the held copy is lineage-valid at c0 but arrived after the migration started
                   (the in-flight fragment of a staging flow cancelled at migration start; the delta was computed before it landed)
    other          anything else (a same-version double delivery: a genuine duplicate)

Amended validity: no `other` duplicates. Snapshot tags are reconstructed from the flows: a base flow's fragments carry
the migration's c0; a staging flow's fragments inherit the holder's tag. Node clocks are compared to the orchestrator's
with a tolerance (NTP skew).

    python tools/eval/m3s1_dupcheck.py [--experiment expM3S1] [--write]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/evaluation/osdi/m3s1"
S0DIR = ROOT / "results/evaluation/osdi/m3s0"
WL_TABLE = {"dog": "events_dog.json", "bfly": "events_bfly.json"}
N_ENTRIES = 180
SKEW_TOL_S = 0.25


class Lineage:
    def __init__(self, J):
        rows, S = int(J["rows"]), int(J["sink_slots"])
        self.refresh = {int(c): {(li * rows + row) * S + slot for li, row, slot in v} for c, v in J["refresh"].items()}

    def refreshed_in(self, s, t):
        out = set()
        for c in range(s + 1, t + 1):
            out |= self.refresh.get(c, set())
        return out


def classify(d: Path, lin_cache: dict):
    s = json.load(open(d / "summary.json"))
    wl = s["workload"]
    if wl not in lin_cache:
        lin_cache[wl] = Lineage(json.load(open(S0DIR / WL_TABLE[wl])))
    lin = lin_cache[wl]
    ev = list(csv.DictReader(open(d / "events.csv")))
    t0 = float(ev[0]["t_wall"])
    flows = {}
    for r in ev:
        if r["event"] == "flow_start":
            j = json.loads(r["detail"]); flows[j["flow"]] = j
    migs = {m["id"]: m for m in s["migrations"]}
    base_c0 = {}
    for fid_, j in flows.items():
        if j["kind"] == "base":
            mid = int(re.match(r"m(\d+):", j["reason"]).group(1)); base_c0[fid_] = (mid, migs[mid]["c0"])
    nodes = {}
    for n in "ABCD":
        f = d / f"node_{n}" / "fragments.csv"
        if not f.exists():
            return {"run": d.name, "workload": wl, "staging": s["staging"], "order": s["order"], "rho": s["rho"], "rep": s["rep"],
                    "frozen_no_duplicates": s["validation"]["no_duplicates"], "missing_node_logs": True}
        nodes[n] = [r for r in csv.DictReader(open(f)) if r["event"] == "recv" and r["session"] == "s0"]
    rows = sorted((float(r["t"]), n, r) for n, rs in nodes.items() for r in rs)
    tag = {n: {} for n in "ABCD"}       # node -> fid -> (snapshot call, t_rel of receipt)
    out = defaultdict(lambda: {"n": 0, "bytes": 0})
    detail = []
    for t, n, r in rows:
        fid, fl, ok = int(r["fragment_id"]), r["flow"], r["ok"] == "True"
        j = flows.get(fl)
        if j is None:
            detail.append({"node": n, "fid": fid, "flow": fl, "class": "other", "why": "unknown flow"}); out["other"]["n"] += 1; out["other"]["bytes"] += int(r["bytes"]); continue
        if j["kind"] == "base":
            mid, c0 = base_c0[fl]; new_tag = c0
        else:
            new_tag = tag[j["src"]].get(fid, (None, None))[0]
        trel = t - t0
        if ok:
            tag[n][fid] = (new_tag, trel)
            continue
        # duplicate receipt
        held = tag[n].get(fid)
        b = int(r["bytes"])
        if j["kind"] == "base" and held is not None and held[0] is not None:
            mid, c0 = base_c0[fl]
            m = migs[mid]
            if fid in lin.refreshed_in(held[0], c0):
                cls, why = "stale_resend", f"held tag {held[0]} refreshed in ({held[0]}, {c0}]"
            elif held[1] >= m["t_start"] - SKEW_TOL_S:
                cls, why = "drain_race", f"held copy arrived at {held[1]:.2f} s >= migration start {m['t_start']:.2f} s (tag {held[0]}, valid at c0 {c0})"
            else:
                cls, why = "other", f"base re-sent a lineage-valid held entry (tag {held[0]}, c0 {c0}, held at {held[1]:.2f} s)"
        elif j["kind"] == "base":
            cls, why = "other", "base duplicate of an entry with no reconstructed tag"
        else:
            cls, why = "other", f"duplicate via staging flow {fl} ({j['src']}->{j['dst']}); held {held}"
        out[cls]["n"] += 1; out[cls]["bytes"] += b
        detail.append({"node": n, "fid": fid, "flow": fl, "kind": j["kind"], "t_rel": round(trel, 3), "class": cls, "why": why})
    tot_n = sum(v["n"] for v in out.values())
    return {"run": d.name, "workload": wl, "staging": s["staging"], "order": s["order"], "rho": s["rho"], "rep": s["rep"],
            "frozen_no_duplicates": s["validation"]["no_duplicates"], "missing_node_logs": False,
            "duplicates": dict(out), "n_duplicates": tot_n, "amended_no_duplicates": out["other"]["n"] == 0 if "other" in out else True,
            "detail": detail}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--experiment", default="expM3S1"); ap.add_argument("--write", action="store_true", help="write osdi/m3s1/dupcheck_<experiment>.json")
    a = ap.parse_args()
    lin_cache = {}
    res = []
    for d in sorted((ROOT / "results/evaluation" / a.experiment).glob("policy=*")):
        if (d / "summary.json").exists():
            res.append(classify(d, lin_cache))
    for r in res:
        if r.get("missing_node_logs"):
            print(f"{r['workload']} {r['staging']}/{r['order']} rho {r['rho']:g} rep {r['rep']}: node logs missing (run d0_remote.py recover --pattern)")
            continue
        D = r["duplicates"]
        print(f"{r['workload']} {r['staging']}/{r['order']} rho {r['rho']:g} rep {r['rep']}: frozen no_dup {r['frozen_no_duplicates']}, dups {r['n_duplicates']} "
              + ", ".join(f"{k} {v['n']} ({v['bytes'] / 1e6:.1f} MB)" for k, v in sorted(D.items())) + f" -> amended no_dup {r['amended_no_duplicates']}")
        for x in r["detail"]:
            if x["class"] == "other":
                print("   OTHER:", x)
    if a.write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"dupcheck_{a.experiment}.json").write_text(json.dumps({"skew_tolerance_s": SKEW_TOL_S, "runs": res}, indent=1))
        print(f"wrote {OUT / f'dupcheck_{a.experiment}.json'}")


if __name__ == "__main__":
    main()
