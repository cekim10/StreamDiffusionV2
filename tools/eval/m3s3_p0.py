#!/usr/bin/env python3
"""M3-S3 Phase P0 (osdi/m3s3/preregistration.md): offline checks, on one GPU, of the two pieces M3-S3 adds to M3-S2.

One deterministic generation of a workload. Call s is the "switch": calls < s belong to the old owner A, calls >= s
to the new owner B. A's lineage history (m3_path.LineageHistory, frozen M2 detection rule) records calls 30 .. s - 1;
B's own history starts at s with the positions read at boundary s, exactly as the new owner's does after a switch.
At boundary s the Sink is serialized the way M2 retains it (GpuRuntime.retain_sink -> host copy).

Checks (all bitwise):
  R  retained entries: m3_path.retained_entries (the old owner's holder entries, cut from the retained host copy) give
     the same metadata and bytes as m3_path.gpu_entry_payload and as the live ring, for all 180 entries.
  M  merge: B's history with A's prepended is contiguous; an export missing its last call is refused.
  E  for every target t and entry valid under the merged history: (a) the retained entry at s with its ordered shifts
     of [s, t) equals the live entry at t; (b) an entry copied at A-era version v0 < s with its ordered shifts of
     [v0, t), which span both owners, equals the live entry at t.
  N  a new-owner history that misses the switch call's events (claims start s, no record of call s): every entry it
     would reuse whose call-s event it missed must differ from the live entry (detected by the comparison).
  S  Sinks assembled at t from retained-s entries, A-era v0 entries and entries at t (all-retained shape + 5 random
     mixes): 360 block checksums equal the target's.

    python tools/eval/m3s3_p0.py --video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0 \\
        --out results/evaluation/osdi/m3s3/p0_dog.json
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video_path", required=True); ap.add_argument("--prompt_file_path", required=True); ap.add_argument("--seed", default="0")
    ap.add_argument("--gpu_id", default="0")
    ap.add_argument("--v0", type=int, default=50); ap.add_argument("--switch", type=int, default=80)
    ap.add_argument("--targets", default="100,120,140")
    ap.add_argument("--mixes", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import torch

    import mobility_node as mn
    import m3_path as m3
    from proto_handoff import bytes_to_tensor
    from models.wan.causal_model import _shift_temporal_rope

    margs = mn.parse_args(["--label", "P0", "--video_path", a.video_path, "--prompt_file_path", a.prompt_file_path, "--seed", a.seed, "--gpu_id", a.gpu_id,
                           "--migration_chunk", "30", "--post_chunks", "1500"])
    rt = mn.GpuRuntime(margs)
    pl, dev, fsl, S = rt.pl, rt.device, rt.fsl, rt.sink
    sync = lambda: torch.cuda.synchronize(dev)  # noqa: E731
    s_sw, v0 = a.switch, a.v0
    targets = sorted(int(x) for x in a.targets.split(","))
    assert 30 < v0 < s_sw < targets[0]
    t_all = time.time()

    def live(e):
        li, i, s = coords[e]
        return pl.kv_cache1[li]["k"][i, s * fsl:(s + 1) * fsl].detach().clone(), pl.kv_cache1[li]["v"][i, s * fsl:(s + 1) * fsl].detach().clone()

    session = rt.session = rt.runner.start()
    histA, histB = m3.LineageHistory(30), m3.LineageHistory(s_sw)
    lastA = lastB = None
    coords, N = None, None
    at_v0, retained, R, cks = {}, {}, None, {}
    live_t = {}
    for c in range(targets[-1] + 1):
        if c == 30:
            lastA = m3.gpu_track_events(rt, None)[0]
            L, rows = len(pl.kv_cache1), int(pl.kv_cache1[0]["k"].shape[0])
            N = L * rows * S; coords = [m3.coords_of(e, rows, S) for e in range(N)]
        if c == v0:
            sync(); at_v0 = {e: live(e) for e in range(N)}
        if c == s_sw:
            sync()
            snap = rt.serialize_live()
            hdr, buf, ret_s = rt.retain_sink(snap)
            R = {"entries": 0, "meta_equal": 0, "bytes_equal_payload": 0, "bytes_equal_live": 0, "retain_s": ret_s, "mismatch": []}
            t0 = time.perf_counter()
            for e, mk, mv, bk, bv in m3.retained_entries(hdr, buf, rows, S, fsl):
                pk, pv, (gk, gv), nk = m3.gpu_entry_payload(rt, snap, e)
                R["entries"] += 1
                R["meta_equal"] += int(mk == pk and mv == pv and nk == len(bk))
                eqp = bytes(bk) == gk.tobytes() and bytes(bv) == gv.tobytes()
                R["bytes_equal_payload"] += int(eqp)
                lk, lv = live(e)
                eql = torch.equal(bytes_to_tensor(mk, bk, dev), lk) and torch.equal(bytes_to_tensor(mv, bv, dev), lv)
                R["bytes_equal_live"] += int(eql)
                if not (eqp and eql) and len(R["mismatch"]) < 20:
                    R["mismatch"].append(e)
                retained[e] = (mk, mv, bytes(bk), bytes(bv))
            R["convert_and_compare_s"] = time.perf_counter() - t0
            del snap
            lastB = m3.gpu_track_events(rt, None)[0]   # the new owner reads its positions at the switch boundary
        if c in targets:
            sync(); live_t[c] = {e: live(e) for e in range(N)}
            ck = rt.sink_checksums(); ck.pop("s"); cks[c] = ck["blocks"]
        rt.runner.step(session, c); sync()
        if c >= 30:
            if c < s_sw:
                lastA, ref, sh = m3.gpu_track_events(rt, lastA); histA.record(c, ref, sh)
            else:
                lastB, ref, sh = m3.gpu_track_events(rt, lastB); histB.record(c, ref, sh)
        if c % 20 == 0:
            print(f"[P0] call {c} ({time.time() - t_all:.0f} s)", flush=True)

    def from_export(x):
        h = m3.LineageHistory(int(x["start"]))
        h.last = int(x["last"])
        h.refresh = {int(c): set(v) for c, v in x["refresh"].items()}
        h.shifts = {int(c): [tuple(y) for y in v] for c, v in x["shifts"].items()}
        h.issued = {(int(e), int(v)): hh for e, v, hh in x["issued"]}
        return h

    expA, expB = histA.export(), histB.export()
    merged = from_export(expB)
    Mres = {"merge": merged.merge_prefix(expA)}
    gap = dict(expA); gap["refresh"] = {k: v for k, v in expA["refresh"].items() if int(k) != s_sw - 1}
    gap["shifts"] = {k: v for k, v in expA["shifts"].items() if int(k) != s_sw - 1}
    gB = from_export(expB)
    Mres["gap"] = gB.merge_prefix(gap)
    Mres["gap_v0_valid_after_refusal"] = sum(1 for e in range(N) if gB.valid(e, v0, targets[0]))
    late = from_export({**expB, "refresh": {k: v for k, v in expB["refresh"].items() if int(k) != s_sw}, "shifts": {k: v for k, v in expB["shifts"].items() if int(k) != s_sw}})
    freqs = pl.generator.model.freqs.to(dev)

    def shifted(k, ds):
        for d in ds:
            k = _shift_temporal_rope(k, freqs, int(d))
        return k

    def ret_kv(e):
        mk, mv, bk, bv = retained[e]
        return bytes_to_tensor(mk, bk, dev), bytes_to_tensor(mv, bv, dev)

    E = {"ret_valid": 0, "ret_exact": 0, "ret_with_shifts": 0, "x_valid": 0, "x_exact": 0, "x_with_shifts_both_owners": 0, "mismatch": []}
    Nl = {"exposed": 0, "detected": 0}
    ev_s = set(merged.refresh.get(s_sw, ())) | {e for e, d in merged.shifts.get(s_sw, ())}
    for t in targets:
        for e in range(N):
            lk, lv = live_t[t][e]
            if merged.valid(e, s_sw, t):
                ds = merged.shifts_since(e, s_sw, t)
                k, v = ret_kv(e)
                ok = torch.equal(shifted(k, ds), lk) and torch.equal(v, lv)
                E["ret_valid"] += 1; E["ret_exact"] += int(ok); E["ret_with_shifts"] += int(bool(ds))
                if not ok and len(E["mismatch"]) < 30:
                    E["mismatch"].append(["ret", t, e])
            if merged.valid(e, v0, t):
                ds = merged.shifts_since(e, v0, t)
                k, v = at_v0[e]
                ok = torch.equal(shifted(k, ds), lk) and torch.equal(v, lv)
                E["x_valid"] += 1; E["x_exact"] += int(ok)
                E["x_with_shifts_both_owners"] += int(bool(merged.shifts_since(e, v0, s_sw)) and bool(merged.shifts_since(e, s_sw, t)))
                if not ok and len(E["mismatch"]) < 30:
                    E["mismatch"].append(["x", t, e])
            if e in ev_s and late.valid(e, s_sw, t):
                k, v = ret_kv(e)
                Nl["exposed"] += 1
                Nl["detected"] += int(not (torch.equal(shifted(k, late.shifts_since(e, s_sw, t)), lk) and torch.equal(v, lv)))

    def assemble(t, choice):
        for e, (li, i, s) in enumerate(coords):
            vv = choice[e]
            if vv == t:
                k, v = live_t[t][e]
            elif vv == s_sw:
                k, v = ret_kv(e); k = shifted(k, merged.shifts_since(e, s_sw, t))
            else:
                k, v = at_v0[e]; k = shifted(k, merged.shifts_since(e, v0, t))
            pl.kv_cache1[li]["k"][i, s * fsl:(s + 1) * fsl] = k
            pl.kv_cache1[li]["v"][i, s * fsl:(s + 1) * fsl] = v
        sync()
        ck = rt.sink_checksums(); ck.pop("s")
        return [[ii // 2, "kv"[ii % 2], b, s_] for ii, layer in enumerate(ck["blocks"]) for b, row in enumerate(layer) for s_, x in enumerate(row) if x != cks[t][ii][b][s_]]

    rng = random.Random(20261029)
    Ssc = []
    for t in targets:
        scen = [("retained_all", 0, {e: (s_sw if merged.valid(e, s_sw, t) else t) for e in range(N)})]
        for m in range(a.mixes):
            ch = {}
            for e in range(N):
                vv = rng.choice([v0, s_sw, t])
                ch[e] = vv if (vv == t or merged.valid(e, vv, t)) else t
            scen.append(("mix", m, ch))
        for kind, key, ch in scen:
            bad = assemble(t, ch)
            Ssc.append({"t": t, "kind": kind, "key": key, "from_retained": sum(1 for e in range(N) if ch[e] == s_sw), "from_v0": sum(1 for e in range(N) if ch[e] == v0),
                        "n_block_mismatch": len(bad), "mismatched": bad[:10]})
    res = {"host": platform.node(), "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
           "video": a.video_path, "prompt": a.prompt_file_path, "seed": a.seed, "v0": v0, "switch": s_sw, "targets": targets, "n_entries": N,
           "history_A": histA.summary(), "history_B": histB.summary(), "events_at_switch_call": len(ev_s), "R": R, "M": Mres, "E": E, "N_late": Nl, "S": Ssc,
           "verdict": {"R_retained_entries_exact": R["entries"] == N and R["meta_equal"] == N and R["bytes_equal_payload"] == N and R["bytes_equal_live"] == N,
                       "M_merge_contiguous": Mres["merge"]["contiguous"] is True, "M_gap_refused": Mres["gap"]["contiguous"] is False and Mres["gap_v0_valid_after_refusal"] == 0,
                       "E_retained_all_exact": E["ret_valid"] > 0 and E["ret_exact"] == E["ret_valid"],
                       "E_cross_owner_all_exact": E["x_valid"] > 0 and E["x_exact"] == E["x_valid"],
                       "N_late_start_all_detected": Nl["detected"] == Nl["exposed"], "N_late_start_exposed": Nl["exposed"],
                       "S_assemblies_all_exact": all(x["n_block_mismatch"] == 0 for x in Ssc), "S_assemblies": len(Ssc)},
           "wall_s": time.time() - t_all}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res["verdict"], indent=1))


if __name__ == "__main__":
    main()
