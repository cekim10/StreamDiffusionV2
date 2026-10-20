"""Experiment RD schedules (results/evaluation/osdi/expRD/preregistration.md, frozen f850072, sections 3 and 6).

A condition is {"id", "phase", "workload", "seed", "structure", "d", "anchor", "resets", "binds", "sink_source", "end"}:
an M1 reset happens before generating each call in `resets`, a Sink bind before generating each call in `binds`, and
the run generates calls 0 .. end. sink_source "withheld" rebinds the Sink packed at the reset that opened the current
Sink-less episode; "trigger" rebinds the Sink packed at the first reset in every episode (Phase 0 stale replay only).
"""

from __future__ import annotations

ANCHORS = (155, 175)
H = 100
G = 25
D_R1 = (0, 10, 25, 50, 75, 100)
D_R3C = (25, 50, 75, 100)
D_R3E = (0, 75)
PHASE1_WORKLOADS = ("butterfly-feeding-slow-motion", "audi-snow-trail", "train", "dog")
REFRESH_HEAVY = ("butterfly-feeding-slow-motion", "audi-snow-trail", "train")
CONTROL = "dog"
SEED = 0

# Phase 0 replay targets (section 6): schedules transcribed from the frozen runs; test_rd.py checks them against the
# recorded moves / binds of the target runs
PHASE0 = [
    {"id": "P0-1_W2_bfly", "workload": "butterfly-feeding-slow-motion", "resets": [34], "binds": [58], "sink_source": "withheld",
     "target": "expW_W2_butterfly-feeding-slow-motion_s0/policy=reuse_dyn_*"},
    {"id": "P0-2_VA_bfly_rho1_split", "workload": "butterfly-feeding-slow-motion", "resets": [30, 54, 77], "binds": [101], "sink_source": "withheld",
     "target": "expVA_butterfly-feeding-slow-motion_rho1/policy=split_bw=*_rep=1_*"},
    {"id": "P0-3_VA_bfly_rho0.5_split", "workload": "butterfly-feeding-slow-motion", "resets": [30, 77, 123], "binds": [54, 100, 147], "sink_source": "trigger",
     "target": "expVA_butterfly-feeding-slow-motion_rho0.5/policy=split_bw=*_rep=1_*"},
    {"id": "P0-4_VA_bfly_rho0.5_restart_fresh", "workload": "butterfly-feeding-slow-motion", "resets": [30, 77, 123], "binds": [54, 103, 150], "sink_source": "withheld",
     "target": "expVA_butterfly-feeding-slow-motion_rho0.5/policy=restart_fresh_*_rep=1_*"},
    {"id": "P0-5_VA_dog_rho1_split", "workload": "dog", "resets": [30, 54, 78], "binds": [101], "sink_source": "withheld",
     "target": "expVA_dog_rho1/policy=split_bw=*_rep=1_*"},
]


def _cond(phase, w, structure, d, b, resets, binds, cid=None, source="withheld"):
    return {"id": cid or f"b{b}_{structure}_d{d}", "phase": phase, "workload": w, "seed": SEED, "structure": structure, "d": d, "anchor": b,
            "resets": list(resets), "binds": list(binds), "sink_source": source, "end": b + H - 1}


def r1(w, d, b):
    return _cond(1, w, "r1", d, b, [b - d], [b])


def r3c(w, d, b):
    return _cond(1, w, "r3c", d, b, [b - d, b - d + round(d / 3), b - d + round(2 * d / 3)], [b])


def r3e(w, d, b):
    e = d // 3
    t1 = b - d - 2 * G
    return _cond(1, w, "r3e", d, b, [t1, t1 + e + G, t1 + 2 * e + 2 * G], [t1 + e, t1 + 2 * e + G, b])


def phase1(w: str) -> list[dict]:
    out = []
    for b in ANCHORS:
        out += [r1(w, d, b) for d in D_R1] + [r3c(w, d, b) for d in D_R3C] + [r3e(w, d, b) for d in D_R3E]
    rep = dict(r1(w, 75, ANCHORS[0])); rep["id"] += "_rep2"; rep["determinism_repeat_of"] = r1(w, 75, ANCHORS[0])["id"]
    return out + [rep]


def phase0(w: str | None = None) -> list[dict]:
    out = []
    for t in PHASE0:
        if w and t["workload"] != w:
            continue
        b = t["binds"][-1]
        out.append({**_cond(0, t["workload"], "replay", None, b, t["resets"], t["binds"], cid=t["id"], source=t["sink_source"]), "target": t["target"]})
    return out


def sinkless_calls(cond: dict) -> list[int]:
    """Calls generated without a bound Sink after the first reset (an episode runs from a reset to the next bind)."""
    out, open_ = [], None
    ev = sorted([(c, 0, "reset") for c in cond["resets"]] + [(c, 1, "bind") for c in cond["binds"]])
    for c, _, k in ev:
        if k == "reset" and open_ is None:
            open_ = c
        elif k == "bind" and open_ is not None:
            out += list(range(open_, c)); open_ = None
    return out


def validate(cond: dict) -> list[str]:
    """Structural checks of a schedule (no GPU)."""
    bad = []
    rs, bs = cond["resets"], cond["binds"]
    if rs != sorted(rs) or bs != sorted(bs) or len(set(rs)) != len(rs):
        bad.append("unsorted / duplicate events")
    if min(rs) < 30:
        bad.append(f"first reset {min(rs)} < 30")
    if bs[-1] != cond["anchor"]:
        bad.append("final bind != anchor")
    if cond["end"] != cond["anchor"] + H - 1:
        bad.append("end != anchor + 99")
    if cond.get("d") is not None and len(sinkless_calls(cond)) != cond["d"]:
        bad.append(f"Sink-less calls {len(sinkless_calls(cond))} != d {cond['d']}")
    # every bind closes an episode opened by a reset at or before it; resets inside an open episode only for r3c
    open_, n_inside = None, 0
    for c, _, k in sorted([(c, 0, "reset") for c in rs] + [(c, 1, "bind") for c in bs]):
        if k == "reset":
            if open_ is not None:
                n_inside += 1
            else:
                open_ = c
        else:
            if open_ is None:
                bad.append(f"bind at {c} without an open episode")
            open_ = None
    if cond.get("structure") == "r3c" and n_inside != 2:
        bad.append("r3c must reset twice inside its episode")
    if cond.get("structure") in ("r1", "r3e") and n_inside:
        bad.append(f"{cond['structure']} resets inside an open episode")
    return bad
