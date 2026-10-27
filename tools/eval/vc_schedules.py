#!/usr/bin/env python3
"""Experiment VC conditions from frozen runs (osdi/expVC/preregistration.md draft 3, section 3.3; implementation_plan.md
section 3). Nothing here runs a model.

Every condition: the calls at which operations happen (M1 resets, Sink binds, a cold restart), the horizon, the span
of saved frames, the source run(s), and the delivery timeline used by the last-frame-hold playback model, labelled
"realized" (the run's delivered-chunk times), "derived" (constructed from realized quantities, rule stated) or "copied"
(another input's or schedule's times; counterfactual).

    python tools/eval/vc_schedules.py            # -> results/evaluation/osdi/expVC/vc_schedules.json
"""

from __future__ import annotations

import csv
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))

INPUTS = ("dog", "train", "butterfly-feeding-slow-motion", "audi-snow-trail")
WX_SHORT = {"butterfly-feeding-slow-motion": "bfly", "audi-snow-trail": "audi", "train": "train"}
PRE = 16          # saved calls before the first operation
HORIZON = 100     # calls b .. b + 99 after the final bind
K = 2             # Stream-Batch depth of the model (denoising steps); output at call c is input chunk c - (K - 1)
EV = ROOT / "results/evaluation"
VD_INPUTS = ("dog", "butterfly-feeding-slow-motion")   # osdi/expVD/preregistration.md (first two inputs)


VD2_CELLS = [("DR1", 1, False, None), ("DR2", 2, False, None), ("RP1", 0, True, None), ("TSin", 0, False, "in"), ("TSout", 0, False, "out"),
             ("DR2+TSout", 2, False, "out"), ("RP1+TSout", 0, True, "out"), ("DR4", 4, False, None)]   # DR4: exploratory, outside verdicts


def vd2_conditions(ot: dict) -> list[dict]:
    """Experiment VD-2 (osdi/expVD2/preregistration.md): destination-side reconstruction at the OT schedule `ot`:
    DR-k decoder cache from the source's last k latent frames, RP-1 one-chunk replay, TS-in / TS-out temporary Sink
    from the input / from the source's last output frames, and combinations. Emulator only."""
    x = ot["id"].split("-")[1]
    out = []
    for name, dr, rp, ts in VD2_CELLS:
        out.append({**ot, "id": f"VD2{x}-{name}", "kind": "vd2", "dr": dr, "rp": rp, "ts": ts, "vd2_of": ot["id"], "exploratory": name == "DR4",
                    "label": f"VD-2 {name} at the {ot['id']} schedule (counterfactual reconstruction at the destination)"})
    return out


VD3_CELLS = [("TSin", 0, "in", False, "last"), ("DR2", 2, None, False, "last"), ("DR2+TSin", 2, "in", False, "last"),
             ("TSinKC", 0, "in", True, "last"), ("DR2stale", 2, None, False, "stale"), ("DR2noise", 2, None, False, "noise")]


# Source runs whose recorded workload is not what they generated (osdi/audi_s0_w2_provenance.md). A schedule taken
# from such a run is a copied schedule for the labelled input; VD-3 labels it so (frozen VC conditions are unchanged).
PROVENANCE = {"expW_W2_audi-snow-trail_s0/policy=reuse_dyn_bw=1000_rho=none_tm=inf_rep=1_20261019-135751":
              "the source run generated train seed 1 (an orphaned node of a failed train seed-1 invocation), not audi-snow-trail seed 0; "
              "for audi-snow-trail its schedule is a copied schedule"}


def vd3_conditions(ot: dict) -> list[dict]:
    """Experiment VD-3 (osdi/expVD3/preregistration.md): DR-2 + TS-in confirmation with components, TSin-KC (the
    prepare's own decoder cache kept) and the stale / noise decoder-cache controls."""
    x = ot["id"].split("-")[1]
    note = next((v for k, v in PROVENANCE.items() if any(src.endswith(k) for src in ot.get("sources", []))), None)
    extra = {"counterfactual": True, "provenance_note": note} if note else {}
    return [{**ot, **extra, "id": f"VD3{x}-{name}", "kind": "vd3", "dr": dr, "ts": ts, "keep_cache": kc, "dr_source": src, "vd3_of": ot["id"],
             "label": f"VD-3 {name} at the {ot['id']} schedule (counterfactual reconstruction at the destination)" + (" - copied schedule: " + note if note else "")}
            for name, dr, ts, kc, src in VD3_CELLS]


# Experiment VD-4 (osdi/expVD4/preregistration.md): oracle source-state diagnostics on top of VD-3's DR2+TSin (B0).
# name: (decoder "dr2" | "oracle", oracle recent KV, temporary Sink "in" | "in_aligned" | None, oracle Sink slots,
#        quantization, exploratory, V0 full injection)
VD4_CELLS = [("B0", "dr2", False, "in", [], None, False, False), ("A1", "dr2", False, "in_aligned", [], None, False, False),
             ("D", "oracle", False, "in", [], None, False, False), ("R", "dr2", True, "in", [], None, False, False),
             ("DR", "oracle", True, "in", [], None, False, False),
             ("S1", "dr2", False, "in", [2], None, False, False), ("S2", "dr2", False, "in", [2, 1], None, False, False),
             ("S3", "dr2", False, None, [2, 1, 0], None, False, False),
             ("A1S1", "dr2", False, "in_aligned", [2], None, True, False), ("A1S2", "dr2", False, "in_aligned", [2, 1], None, True, False),
             ("Q8", "dr2", False, None, [2, 1, 0], "fp8", True, False), ("Q4", "dr2", False, None, [2, 1, 0], "int4", True, False),
             ("V0", None, False, None, [], None, False, True)]


def vd4_conditions(ot: dict) -> list[dict]:
    x = ot["id"].split("-")[1]
    out = []
    for name, dec, rec, ts, slots, q, expl, v0 in VD4_CELLS:
        c = {**ot, "id": f"VD4{x}-{name}", "kind": "vd4", "dec": dec, "oracle_recent": rec, "ts": ts, "oracle_sink_slots": slots, "quant": q,
             "exploratory": expl, "v0": v0, "vd4_of": ot["id"],
             "label": f"VD-4 {name} at the {ot['id']} schedule (oracle diagnostic; not a practical migration)"}
        if v0:   # full-state injection with refresh unfrozen: no Sink is withheld, so there is no bind
            c["binds"] = []
        out.append(c)
    return out


VD4_FILE = ROOT / "results/evaluation/osdi/expVD4/vd4_schedules.json"   # overlay: vc_schedules.json is frozen (VD-3 freeze record)
_VD4 = None


def vd4_overlay() -> dict:
    global _VD4
    if _VD4 is None:
        _VD4 = json.loads(VD4_FILE.read_text())["units"] if VD4_FILE.exists() else {}
    return _VD4


def unit_sched(sched: dict, unit_name: str) -> dict:
    """The schedule of a unit directory name '<input>_s<seed>' (seed 0 units are the 'inputs' entries), with the VD-4
    overlay's conditions appended (they live in their own file so the frozen vc_schedules.json stays byte-identical)."""
    base = sched["units"][unit_name] if unit_name in sched.get("units", {}) else sched["inputs"][unit_name.rsplit("_s", 1)[0]]
    ov = vd4_overlay().get(unit_name)
    return {**base, "conditions": base["conditions"] + ov} if ov else base


def build_vd4(out: dict) -> dict:
    units = {}
    for inp, u in out["inputs"].items():
        ot = {c["id"]: c for c in u["conditions"] if c["id"] in ("OT-1", "OT-L")}
        units[f"{inp}_s0"] = vd4_conditions(ot["OT-1"]) + vd4_conditions(ot["OT-L"])
    for name, u in out["units"].items():
        ot = {c["id"]: c for c in u["conditions"] if c["id"] in ("OT-1", "OT-L")}
        units[name] = vd4_conditions(ot["OT-1"]) + vd4_conditions(ot["OT-L"])
    return {"note": "Experiment VD-4 conditions (overlay of the frozen vc_schedules.json)", "units": units}


def seed1_units(out: dict) -> dict:
    """VD-3 seed-1 units: OT-1 from the frozen W2 seed-1 reuse_dyn run of each input, OT-L copied from dog's seed-0
    RD-X schedule (counterfactual stress condition), REF, and the VD-3 conditions."""
    dog_rdx = _first_valid("expRDX_dog/policy=split_*_rep=1_*")
    units = {}
    for inp in INPUTS:
        w2 = _first_valid(f"expW_W2_{inp}_s1/policy=reuse_dyn_*")
        s = json.load(open(w2 / "summary.json"))
        m1, b1 = int(s["moves"][0]["call"]), int(s["final"]["bind_call"])
        tl1 = _timeline(w2); cad1 = _cadence(tl1, b1)
        ot1 = _cond("OT-1", inp, "ot", [m1], [b1], b1 + HORIZON - 1, "OTTER single move 1 Gbps at seed 1 (W2 s1 realized; no M3 behavior evaluated)",
                    [_rel(w2)], {"kind": "realized", "t_by_call": tl1, "cadence_s": cad1, "bind_rel_s": s["final"]["sink_bind_rel_s"], "move_t": [0.0]})
        s2 = json.load(open(dog_rdx / "summary.json"))
        mL, bL = int(s2["moves"][0]["call"]), int(s2["final"]["bind_call"])
        tlL = _timeline(dog_rdx)
        otL = _cond("OT-L", inp, "ot", [mL], [bL], bL + HORIZON - 1, "counterfactual replay at seed 1 under a copied schedule (dog's seed-0 RD-X run); stress condition",
                    [_rel(dog_rdx)], {"kind": "copied", "t_by_call": tlL, "cadence_s": _cadence(tlL, bL), "bind_rel_s": s2["final"]["sink_bind_rel_s"], "move_t": [0.0]}, counterfactual=True)
        conds = [ot1, otL] + vd3_conditions(ot1) + vd3_conditions(otL)
        for c in conds:
            c["seed"] = 1
        end_all = max(c["end"] for c in conds)
        units[f"{inp}_s1"] = {"N": end_all + 1, "seed": 1, "ref": {"frames_from": min(c["frames_from"] for c in conds), "frames_to": end_all,
                                                                   "timeline": {"kind": "derived", "rule": "uninterrupted: one chunk per OT-1 post-bind cadence", "cadence_s": cad1}},
                              "conditions": conds}
    return units


def vd_conditions(ot: dict) -> list[dict]:
    """Experiment VD: the 2 x 2 x 2 factorial of what survives the M1 reset at the OT schedule `ot`, without the
    (zero, reset, reset) cell (= `ot` itself), plus (zero, encoder + decoder kept, reset). The emulator keeps the state;
    nothing is transferred (counterfactual state, realized schedule)."""
    out = []
    x = ot["id"].split("-")[1]
    cells = [(m, d, r) for m in (False, True) for d in (False, True) for r in (False, True) if (m, d, r) != (False, False, False)]
    for m, d, r in cells:
        keep = (["vae_dec"] if d else []) + (["recent"] if r else [])
        out.append({**ot, "id": f"VD{x}-{'mask' if m else 'zero'}-{'dec' if d else 'nodec'}-{'rec' if r else 'norec'}", "kind": "vd", "mask": m, "keep": keep,
                    "vd_of": ot["id"], "label": f"VD diagnosis at the {ot['id']} schedule: sink slots {'masked' if m else 'zero (attended)'}, keep {keep or 'nothing'} (counterfactual state)"})
    out.append({**ot, "id": f"VD{x}-zero-encdec-norec", "kind": "vd", "mask": False, "keep": ["vae_dec", "vae_enc"], "vd_of": ot["id"],
                "label": f"VD diagnosis at the {ot['id']} schedule: keep VAE encoder + decoder caches (counterfactual state)"})
    return out


def _valid_runs(pattern: str) -> list[Path]:
    from wrn_validity import run_validity_wrn
    out = []
    for d in sorted(EV.glob(pattern)):
        try:
            s = json.load(open(d / "summary.json"))
        except OSError:
            continue
        if run_validity_wrn(s, d, dry=False)[0]:
            out.append(d)
    return out


def _first_valid(pattern: str) -> Path:
    runs = _valid_runs(pattern)
    if not runs:
        raise SystemExit(f"no valid run matches {pattern}")
    return runs[0]


def _timeline(d: Path) -> dict:
    """call -> delivery time (s, relative to the run's t0 = first move request) of every delivered chunk at or after t0."""
    out = {}
    for r in csv.DictReader(open(d / "metrics.csv", newline="")):
        if r["missing"] in ("True", "true") or not r["t_out_rel"]:
            continue
        t = float(r["t_out_rel"])
        if t >= 0:
            out[int(r["call"])] = t
    return out


def _cadence(tl: dict, after_call: int) -> float:
    calls = sorted(c for c in tl if c >= after_call)
    dts = [tl[b] - tl[a] for a, b in zip(calls, calls[1:]) if b == a + 1]
    return st.median(dts)


def _rel(d: Path) -> str:
    return str(d.relative_to(ROOT))


def _cond(cid, inp, kind, resets, binds, end, label, sources, timeline, cold_call=None, counterfactual=False, extra=None):
    first = min(resets + ([cold_call] if cold_call is not None else []))
    c = {"id": cid, "input": inp, "kind": kind, "label": label, "resets": resets, "binds": binds, "cold_call": cold_call, "sink_source": "withheld",
         "end": end, "frames_from": first - PRE, "frames_to": end, "sources": sources, "counterfactual": counterfactual, "timeline": timeline}
    c.update(extra or {})
    return c


def build() -> dict:
    out = {"rules": {"PRE": PRE, "HORIZON": HORIZON, "K": K, "timeline_t0": "first move request of the source run",
                     "pre_move_timeline": "calls before the first move are placed at the run's median post-bind cadence, the last one at t = 0 (synthesized; no pre-move rows are logged)"},
           "inputs": {}}
    dog_rdx = _first_valid("expRDX_dog/policy=split_*_rep=1_*")
    for inp in INPUTS:
        conds = []
        # OT-1: W2 single move, 1 Gbps
        w2 = _first_valid(f"expW_W2_{inp}_s0/policy=reuse_dyn_*")
        s = json.load(open(w2 / "summary.json"))
        m1, b1 = int(s["moves"][0]["call"]), int(s["final"]["bind_call"])
        tl1 = _timeline(w2); cad1 = _cadence(tl1, b1)
        conds.append(_cond("OT-1", inp, "ot", [m1], [b1], b1 + HORIZON - 1, "OTTER single move 1 Gbps (W2 realized; policy reuse_dyn, one move from one source: no M3 behavior evaluated)",
                           [_rel(w2)], {"kind": "realized", "t_by_call": tl1, "cadence_s": cad1, "bind_rel_s": s["final"]["sink_bind_rel_s"], "move_t": [0.0]}))
        # OT-L: RD-X single move, 320 Mbps (train: dog's schedule, counterfactual)
        rdx = _first_valid(f"expRDX_{inp}/policy=split_*_rep=1_*") if inp != "train" else dog_rdx
        s = json.load(open(rdx / "summary.json"))
        mL, bL = int(s["moves"][0]["call"]), int(s["final"]["bind_call"])
        tlL = _timeline(rdx); cadL = _cadence(tlL, bL)
        cf = inp == "train"
        conds.append(_cond("OT-L", inp, "ot", [mL], [bL], bL + HORIZON - 1,
                           ("counterfactual replay under a copied schedule (dog's RD-X run); not a realized train run" if cf else "OTTER single move 320 Mbps (RD-X realized; policy split)"),
                           [_rel(rdx)], {"kind": "copied" if cf else "realized", "t_by_call": tlL, "cadence_s": cadL, "bind_rel_s": s["final"]["sink_bind_rel_s"], "move_t": [0.0]},
                           counterfactual=cf))
        # OT-R: M1 + M2 (split) repeated mobility, rho 2
        rr = _first_valid(f"expWX_{WX_SHORT[inp]}_X3/policy=split_*_rep=1_*") if inp != "dog" else _first_valid("expM3E_S4/policy=split_*_rep=1_*")
        s = json.load(open(rr / "summary.json"))
        mR = [int(m["call"]) for m in s["moves"]]; bR = int(s["final"]["bind_call"])
        tlR = _timeline(rr)
        conds.append(_cond("OT-R", inp, "ot", mR, [bR], bR + HORIZON - 1, "M1 + M2 (policy split) repeated mobility A->B->C->D, rho 2; not M3-v2",
                           [_rel(rr)], {"kind": "realized", "t_by_call": tlR, "cadence_s": _cadence(tlR, bR), "bind_rel_s": s["final"]["sink_bind_rel_s"],
                                        "move_t": [float(m["t_req"]) for m in s["moves"]]}))
        # WFS-1 / WFS-L: reset and bind before the same call (RD d = 0); hold = the paired run's move -> bind time
        for ot in (conds[0], conds[1]):
            m, end = ot["resets"][0], ot["end"]
            hold = float(ot["timeline"]["bind_rel_s"])
            ttfo = ot["timeline"]["t_by_call"][m]          # the run's first output after the move (M1 resume latency incl. the first call)
            cad = ot["timeline"]["cadence_s"]
            tl = {c: hold + ttfo + (c - m) * cad for c in range(m, end + 1)}
            skipped_live = list(range(m, m + int(hold // 0.25) + (1 if hold % 0.25 else 0)))   # input chunks a real-time camera produces during the hold
            conds.append(_cond(f"WFS-{ot['id'][-1]}", inp, "wfs", [m], [m], end,
                               f"Wait-for-Sink at the {ot['id']} move: Sink bound before generation resumes; recent KV / VAE rebuilt (M1); last-frame hold {hold:.2f} s",
                               ot["sources"], {"kind": "derived", "rule": "t(c) = hold + first-output latency of the paired run + (c - move) x its post-bind cadence",
                                               "t_by_call": tl, "cadence_s": cad, "hold_s": hold, "move_t": [0.0]},
                               counterfactual=ot["counterfactual"],
                               extra={"paired_with": ot["id"], "stall_s": hold,
                                      "skipped_input_calls_harness": [],
                                      "skipped_input_calls_live_realtime": skipped_live,
                                      "note": "the harness delays (generates every input call in order after the hold); a real-time player that drops the backlog would skip the listed input chunks (hold / 0.25 s of video)"}))
        # COLD-1 / COLD-L: cold restart at the same move call (W2 cold realized timeline; COLD-L copied, shifted)
        cold = _first_valid(f"expW_W2_{inp}_s0/policy=cold_*")
        s = json.load(open(cold / "summary.json"))
        mc = int(s["moves"][0]["call"]); tlc = _timeline(cold); cadc = _cadence(tlc, mc + K)
        for ot in (conds[0], conds[1]):
            m, end = ot["resets"][0], ot["end"]
            if m == mc:
                tl, kind = {c: t for c, t in tlc.items() if c <= end}, "realized"
                last = max(tl); tl.update({c: tl[last] + (c - last) * cadc for c in range(last + 1, end + 1)})
            else:
                tl, kind = {c - mc + m: t for c, t in tlc.items() if c - mc + m <= end}, "copied"
                last = max(tl); tl.update({c: tl[last] + (c - last) * cadc for c in range(last + 1, end + 1)})
            conds.append(_cond(f"COLD-{ot['id'][-1]}", inp, "cold", [], [], end,
                               f"cold restart at the {ot['id']} move ({'W2 cold realized timeline' if kind == 'realized' else 'timeline copied from the W2 cold run, shifted to this move call'})",
                               [_rel(cold)], {"kind": kind, "t_by_call": tl, "cadence_s": cadc, "hold_s": tlc.get(mc + K - 1), "move_t": [0.0],
                                              "extended_beyond_run_at_cadence": True},
                               cold_call=m, counterfactual=kind == "copied" or ot["counterfactual"],
                               extra={"paired_with": ot["id"], "no_output_calls": [m], "emit_call": m + K - 1}))
        if inp in VD_INPUTS:
            conds += vd_conditions(conds[0]) + vd_conditions(conds[1])   # after the seven VC conditions (VD-D3: VC first)
            conds += vd2_conditions(conds[0]) + vd2_conditions(conds[1])   # VD-2 (skipped by vc_emulate unless requested)
        conds += vd3_conditions(conds[0]) + vd3_conditions(conds[1])   # VD-3 on every input (skipped unless requested)
        end_all = max(c["end"] for c in conds)
        cad_ref = conds[0]["timeline"]["cadence_s"]
        out["inputs"][inp] = {"N": end_all + 1, "ref": {"frames_from": min(c["frames_from"] for c in conds), "frames_to": end_all,
                                                        "timeline": {"kind": "derived", "rule": "uninterrupted: one chunk per OT-1 post-bind cadence", "cadence_s": cad_ref}},
                              "conditions": conds}
    out["units"] = seed1_units(out)
    return out


def check(out: dict) -> list[str]:
    """Every extracted schedule against its source run's recorded moves and binds (as test_rd.py does for RD Phase 0)."""
    bad = []
    items = list(out["inputs"].items()) + list(out.get("units", {}).items())
    items += [(k, {"conditions": v, "N": (out.get("units", {}).get(k) or out["inputs"][k.rsplit("_s", 1)[0]])["N"]}) for k, v in (out.get("vd4") or {}).items()]
    for inp, u in items:
        for c in u["conditions"]:
            s = json.load(open(ROOT / c["sources"][0] / "summary.json"))
            moves = [int(m["call"]) for m in s["moves"]]
            if c["kind"] == "vd4" and c.get("v0"):
                if c["resets"] != moves or c["binds"] != []:
                    bad.append(f"{inp} {c['id']}: V0 {c['resets']} / {c['binds']} vs run moves {moves}")
            elif c["kind"] in ("ot", "vd", "vd2", "vd3", "vd4"):
                if c["resets"] != moves or c["binds"] != [int(s["final"]["bind_call"])]:
                    bad.append(f"{inp} {c['id']}: {c['resets']} / {c['binds']} vs run moves {moves} bind {s['final']['bind_call']}")
            elif c["kind"] == "wfs":
                if c["resets"] != c["binds"] or c["resets"][0] != moves[0]:
                    bad.append(f"{inp} {c['id']}: WFS reset {c['resets']} bind {c['binds']} vs move {moves}")
            elif c["kind"] == "cold" and c["cold_call"] not in (34, 80):
                bad.append(f"{inp} {c['id']}: cold call {c['cold_call']}")
            if c["frames_from"] < 0 or c["end"] >= u["N"]:
                bad.append(f"{inp} {c['id']}: span outside the baseline")
    return bad


def main():
    out = build()
    vd4 = build_vd4(out)
    bad = check({**out, "vd4": vd4["units"]})
    p = ROOT / "results/evaluation/osdi/expVC/vc_schedules.json"
    txt = json.dumps(out, indent=1)
    if p.exists() and p.read_text() != txt:
        bad.append("vc_schedules.json would change: it is frozen (VD-3 freeze record); not written")
    else:
        p.write_text(txt)
    VD4_FILE.parent.mkdir(parents=True, exist_ok=True)
    VD4_FILE.write_text(json.dumps(vd4, indent=1))
    for inp, u in list(out["inputs"].items()) + list(out["units"].items()):
        print(f"{inp}: N {u['N']}")
        for c in u["conditions"]:
            tl = c["timeline"]
            print(f"  {c['id']:7s} {c['kind']:4s} resets {c['resets']} binds {c['binds']} cold {c['cold_call']} end {c['end']} frames {c['frames_from']}..{c['frames_to']} "
                  f"timeline {tl['kind']} cadence {tl['cadence_s']:.3f} s{' hold %.2f s' % tl['hold_s'] if tl.get('hold_s') else ''}{' COUNTERFACTUAL' if c['counterfactual'] else ''}")
    print("schedule check:", "OK" if not bad else bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
