#!/usr/bin/env python3
"""M1 input-log replay, validation steps E0 and E1 only (osdi/m1_continuity/proposal.md section 7; plan and reading
rules in osdi/m1_continuity/e0e1_plan.md). No migration protocol, no E2, no frames, no change to any model code path.

Source = the uninterrupted stream of one VC unit (same Runner as the VC REF). A hook on the generator records, from call
M - 12 to M, every generator call exactly as fed: the inputs of both Stream-Batch rows, timesteps, row starts / ends,
the ring metadata before and after the call (positions, end indices, current_step, per-layer eviction queues), the slot
each (layer, row) wrote (a write into a Sink slot is the source's adaptive-refresh decision) and that slot's K / V.
Ring snapshots (K, V and metadata, host memory) are taken before calls M - 12, M - 6, M - 3 and M.

E0  restore the exact ring at M - 12; replay calls M - 12 .. M - 1 with the recorded inputs and decisions. Required:
    every replayed call's metadata and written slot equal the source's, the ring at M equals the source's bitwise
    (K, V on every layer, row and slot; positions, indices, queues), and a replay of call M gives the source's output.
E1  for w in 0, 3, 6, 12: restore the ring at M - w with the recent slots zeroed (Sink and metadata exact); replay calls
    M - w .. M - 1; measure the recent / Sink relative error against the source at M, the per-call error of each
    written slot (convergence), the call-M output error, and the replay time per call.
Decisions are forced in both: adaptive refresh is off during replay and, before each call, the source's refresh slot
is pushed to the front of that layer's / row's eviction queue (the queue state the source reached inside the call).

    python tools/eval/m1_replay.py --unit dog_s1 --gpu_id 0          # one unit = OT-1 (M 34) and OT-L (M 80)
    python tools/eval/m1_replay.py --aggregate                       # e0e1_results.md from the unit files
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

OUT = ROOT / "results/evaluation/osdi/m1_continuity/e0e1"
SCHED = ROOT / "results/evaluation/osdi/expVC/vc_schedules.json"
UNITS = ["train_s0", "train_s1", "audi-snow-trail_s0", "audi-snow-trail_s1", "dog_s1", "butterfly-feeding-slow-motion_s1"]
CELLS = ("OT-1", "OT-L")
WINDOW = 12                 # E0 replays the last 12 calls
E1_W = (0, 3, 6, 12)        # E1 replay windows (0 = no replay: exact Sink, zero recent)
SNAP_OFF = (12, 6, 3, 0)    # ring snapshots before calls M - off


# --------------------------------------------------------------------------- ring state
def blocks(pl):
    return pl.generator.model.blocks


def meta_of(pl) -> dict:
    """Ring metadata of the live pipeline (device tensors cloned; eviction queues deep-copied)."""
    return {"pos": [l_["pos"].clone() for l_ in pl.kv_cache1],
            "gi": [l_["global_end_index"].clone() for l_ in pl.kv_cache1],
            "li": [l_["local_end_index"].clone() for l_ in pl.kv_cache1],
            "cs": [l_.get("current_step") for l_ in pl.kv_cache1],
            "ev": [copy.deepcopy(b.self_attn.evict_idx) for b in blocks(pl)]}


def meta_diff(torch, a: dict, b: dict) -> list:
    """Names of the metadata fields that differ (empty = equal)."""
    bad = []
    for key in ("pos", "gi", "li"):
        for i, (x, y) in enumerate(zip(a[key], b[key])):
            if not torch.equal(x, y):
                bad.append(f"{key}[{i}]")
    if a["cs"] != b["cs"]:
        bad.append("current_step")
    for i, (x, y) in enumerate(zip(a["ev"], b["ev"])):
        if x != y:
            bad.append(f"evict[{i}]")
    return bad


def snapshot(pl, host: str = "cpu") -> dict:
    return {"k": [l_["k"].to(host, copy=True) for l_ in pl.kv_cache1], "v": [l_["v"].to(host, copy=True) for l_ in pl.kv_cache1], "meta": meta_of(pl)}


def restore(pl, snap: dict, sink: int, zero_recent: bool):
    fsl = pl.frame_seq_length
    for li, l_ in enumerate(pl.kv_cache1):
        l_["k"].copy_(snap["k"][li]); l_["v"].copy_(snap["v"][li])
        if zero_recent:
            l_["k"][:, sink * fsl:].zero_(); l_["v"][:, sink * fsl:].zero_()
        l_["pos"].copy_(snap["meta"]["pos"][li])
        l_["global_end_index"].copy_(snap["meta"]["gi"][li]); l_["local_end_index"].copy_(snap["meta"]["li"][li])
        l_["current_step"] = snap["meta"]["cs"][li]
    for b, ev in zip(blocks(pl), snap["meta"]["ev"]):
        b.self_attn.evict_idx = copy.deepcopy(ev)


def written_slots(entry: dict, fsl: int) -> list:
    """Per layer and row, the slot the call wrote: the one whose position became the row's new frame position.
    (A t_refresh realignment in the same call moves the other filled slots below it, so the match is unique.)"""
    out = []
    for li, pos in enumerate(entry["post"]["pos"]):
        rows = []
        for i in range(pos.shape[0]):
            new_pos = int(entry["s"][i]) // fsl
            hit = (pos[i] == new_pos).nonzero().flatten().tolist()
            if len(hit) != 1:
                raise RuntimeError(f"call {entry['c']} layer {li} row {i}: {len(hit)} slots at position {new_pos}")
            rows.append(hit[0])
        out.append(rows)
    return out


# --------------------------------------------------------------------------- recording hook
class Recorder:
    """Wraps pl.generator.forward. Outside the recorded window it only keeps a clone of each call's input (for the
    determinism check across the unit's two source streams); inside it records the full log entry."""

    def __init__(self, torch, pl, sink: int, device, sync, keep_slots: bool = True):
        self.torch, self.pl, self.sink, self.device, self.sync, self.keep_slots = torch, pl, sink, device, sync, keep_slots
        self.orig = pl.generator.forward
        self.call, self.active, self.keep_out = None, False, set()
        self.entries, self.inputs = {}, {}
        pl.generator.forward = self._fwd

    def reset(self):
        self.call, self.active, self.keep_out, self.entries, self.inputs = None, False, set(), {}, {}

    def _fwd(self, *a, **kw):
        c = self.call
        if c is None:
            return self.orig(*a, **kw)
        assert not a, "the generator is called with keywords only"
        pl = self.pl
        assert kw["kv_cache"] is pl.kv_cache1 and kw["crossattn_cache"] is pl.crossattn_cache and kw["conditional_dict"] is pl.conditional_dict
        assert c not in self.inputs, f"two generator calls in step {c}"
        x = kw["noisy_image_or_video"]
        self.inputs[c] = x.detach().clone()
        if not self.active:
            return self.orig(*a, **kw)
        e = {"c": c, "x": x.detach().clone(), "t": kw["timestep"].detach().clone(), "s": kw["current_start"].detach().clone(),
             "e": kw["current_end"].detach().clone(), "pre": meta_of(pl)}
        self.sync(); t0 = time.perf_counter()
        out = self.orig(*a, **kw)
        self.sync(); e["gen_s"] = time.perf_counter() - t0
        e["post"] = meta_of(pl)
        fsl = pl.frame_seq_length
        e["written"] = written_slots(e, fsl)
        e["refresh"] = [(li, i, s) for li, rows in enumerate(e["written"]) for i, s in enumerate(rows) if s < self.sink]
        # the source's freshly written slot of every (layer, row), host copy (E1 convergence reference; E2 skips it)
        if self.keep_slots:
            e["slot_k"] = [[l_["k"][i, s * fsl:(s + 1) * fsl].to("cpu", copy=True) for i, s in enumerate(rows)] for l_, rows in zip(pl.kv_cache1, e["written"])]
            e["slot_v"] = [[l_["v"][i, s * fsl:(s + 1) * fsl].to("cpu", copy=True) for i, s in enumerate(rows)] for l_, rows in zip(pl.kv_cache1, e["written"])]
        if c in self.keep_out:
            e["out"] = out.detach().clone()
        self.entries[c] = e
        return out


def log_bytes(e: dict) -> int:
    """Bytes of one log entry as the source would ship it: generator inputs, timesteps, row starts / ends, and the
    refresh decisions (3 int16 per decision)."""
    return sum(t.numel() * t.element_size() for t in (e["x"], e["t"], e["s"], e["e"])) + 6 * len(e["refresh"])


# --------------------------------------------------------------------------- replay and comparison
def replay(torch, pl, rec: Recorder, calls: list, cfg_thr: float, sync, on_call=None) -> tuple[list, object]:
    """Re-execute the recorded calls on the live ring with forced decisions; returns per-call rows and the last output."""
    fsl = pl.frame_seq_length
    for b in blocks(pl):
        b.self_attn.adapt_sink_thr = -1
    rows, out = [], None
    try:
        for c in calls:
            e = rec.entries[c]
            for li, i, s in e["refresh"]:
                blocks(pl)[li].self_attn.evict_idx[i].insert(0, (s + 1) * fsl)
            sync(); t0 = time.perf_counter()
            out = rec.orig(noisy_image_or_video=e["x"].clone(), conditional_dict=pl.conditional_dict, timestep=e["t"].clone(),
                           kv_cache=pl.kv_cache1, crossattn_cache=pl.crossattn_cache, current_start=e["s"].clone(), current_end=e["e"].clone())
            sync(); dt = time.perf_counter() - t0
            r = {"call": c, "replay_s": dt, "meta_diff": meta_diff(torch, meta_of(pl), e["post"])}
            if on_call is not None:
                r.update(on_call(e))
            rows.append(r)
    finally:
        for b in blocks(pl):
            b.self_attn.adapt_sink_thr = cfg_thr
    return rows, out


def slot_check(torch, pl, device):
    """on_call callback: the replay's freshly written slot of every (layer, row) against the source's."""
    fsl = pl.frame_seq_length

    def f(e: dict) -> dict:
        eq, dk = True, [0.0, 0.0, 0.0, 0.0]   # sum diff^2 K, ref^2 K, diff^2 V, ref^2 V
        for l_, rows, sk, sv in zip(pl.kv_cache1, e["written"], e["slot_k"], e["slot_v"]):
            for i, s in enumerate(rows):
                for j, (key, ref) in enumerate((("k", sk[i]), ("v", sv[i]))):
                    a, b = l_[key][i, s * fsl:(s + 1) * fsl], ref.to(device)
                    eq = eq and bool(torch.equal(a, b))
                    d = (a.float() - b.float())
                    dk[2 * j] += float((d * d).sum()); dk[2 * j + 1] += float((b.float() ** 2).sum())
        return {"slot_bitwise": eq, "slot_rel_k": (dk[0] / dk[1]) ** 0.5 if dk[1] else None, "slot_rel_v": (dk[2] / dk[3]) ** 0.5 if dk[3] else None}
    return f


def compare_ring(torch, pl, snap: dict, sink: int, device) -> dict:
    """Live ring against the source's ring at M: bitwise identity, relative error of the recent and Sink regions (per
    layer and overall), recent error by slot age (0 = oldest recent slot of the row), metadata."""
    fsl = pl.frame_seq_length
    n_slots = pl.kv_cache1[0]["pos"].shape[1]
    out = {"bitwise": {"k": True, "v": True}, "n_diff": {"k": 0, "v": 0}, "per_layer": {"k": [], "v": []},
           "layer0_recent_bitwise": None, "meta_diff": meta_diff(torch, meta_of(pl), snap["meta"])}
    acc = {r: {"k": [0.0, 0.0], "v": [0.0, 0.0]} for r in ("recent", "sink")}
    age = {"k": [[0.0, 0.0] for _ in range(n_slots - sink)], "v": [[0.0, 0.0] for _ in range(n_slots - sink)]}
    for li, l_ in enumerate(pl.kv_cache1):
        pos = snap["meta"]["pos"][li]
        l0 = []
        for key in ("k", "v"):
            a, b = l_[key], snap[key][li].to(device)
            if not torch.equal(a, b):
                out["bitwise"][key] = False
                out["n_diff"][key] += int((a != b).sum())
            d = a.float() - b.float()
            for reg, sl in (("recent", slice(sink * fsl, None)), ("sink", slice(0, sink * fsl))):
                acc[reg][key][0] += float((d[:, sl] ** 2).sum()); acc[reg][key][1] += float((b[:, sl].float() ** 2).sum())
            dd, bb = float((d[:, sink * fsl:] ** 2).sum()), float((b[:, sink * fsl:].float() ** 2).sum())
            out["per_layer"][key].append((dd / bb) ** 0.5 if bb else None)
            for i in range(a.shape[0]):
                order = sorted(range(sink, n_slots), key=lambda s: int(pos[i, s]))
                for rank, s in enumerate(order):
                    seg = slice(s * fsl, (s + 1) * fsl)
                    age[key][rank][0] += float((d[i, seg] ** 2).sum()); age[key][rank][1] += float((b[i, seg].float() ** 2).sum())
            if li == 0:
                l0.append(bool(torch.equal(a[:, sink * fsl:], b[:, sink * fsl:])))
            del a, b, d
        if li == 0:
            out["layer0_recent_bitwise"] = all(l0)
    rel = lambda p: (p[0] / p[1]) ** 0.5 if p[1] else None
    out["recent_rel"] = {k_: rel(acc["recent"][k_]) for k_ in ("k", "v")}
    out["sink_rel"] = {k_: rel(acc["sink"][k_]) for k_ in ("k", "v")}
    out["recent_rel_by_age"] = {k_: [rel(p) for p in age[k_]] for k_ in ("k", "v")}
    return out


def out_error(torch, a, b) -> dict:
    """Generator output (both Stream-Batch rows) against the source's: bitwise and relative error per row."""
    rows = []
    for i in range(b.shape[0]):
        d = a[i].float() - b[i].float()
        rows.append(float((d * d).sum() ** 0.5 / (b[i].float() ** 2).sum() ** 0.5))
    return {"bitwise": bool(torch.equal(a, b)), "rel_per_row": rows}


# --------------------------------------------------------------------------- one cell
def run_cell(torch, pl, rec: Recorder, step, M: int, sink: int, cfg_thr: float, device, sync, mem=None) -> dict:
    """step(c) runs source call c of a freshly started stream. Returns the cell's E0 / E1 record."""
    rec.reset()
    rec.keep_out = {M}
    snaps, times = {}, []
    for c in range(M + 1):
        if (M - c) in SNAP_OFF:
            snaps[M - c] = snapshot(pl)
        rec.call, rec.active = c, c >= M - WINDOW
        sync(); t0 = time.perf_counter()
        step(c)
        sync(); times.append(time.perf_counter() - t0)
    rec.call, rec.active = None, False
    if mem:
        mem(f"after source stream to M={M}")
    missing = [c for c in range(M - WINDOW, M + 1) if c not in rec.entries]
    assert not missing, f"no generator call recorded for {missing}"
    ent = rec.entries
    src = {"call_s_all_median": st.median(times[1:]), "call_s_pre_window_median": st.median(times[1:M - WINDOW]) if M - WINDOW > 2 else None,
           "gen_s_window_median": st.median([ent[c]["gen_s"] for c in range(M - WINDOW, M + 1)]),
           "log_bytes_per_call": log_bytes(ent[M - 1]), "refresh_in_window": {str(c): ent[c]["refresh"] for c in range(M - WINDOW, M + 1) if ent[c]["refresh"]}}
    check = slot_check(torch, pl, device)
    rec_out = {"M": M, "source": src}

    # ---- E0: exact ring at M - 12, replay, compare bitwise
    t0 = time.perf_counter(); restore(pl, snaps[WINDOW], sink, zero_recent=False); sync(); t_restore = time.perf_counter() - t0
    rows, _ = replay(torch, pl, rec, list(range(M - WINDOW, M)), cfg_thr, sync, on_call=check)
    ring = compare_ring(torch, pl, snaps[0], sink, device)
    rows_m, outM = replay(torch, pl, rec, [M], cfg_thr, sync)
    oe = out_error(torch, outM, ent[M]["out"])
    e0_pass = (all(not r["meta_diff"] for r in rows + rows_m) and all(r["slot_bitwise"] for r in rows) and ring["bitwise"]["k"] and ring["bitwise"]["v"]
               and not ring["meta_diff"] and oe["bitwise"])
    rec_out["E0"] = {"window": WINDOW, "pass": e0_pass, "calls": rows, "ring_at_M": ring, "call_M": {**oe, "meta_diff": rows_m[0]["meta_diff"]},
                     "restore_s": t_restore, "replay_s_median": st.median([r["replay_s"] for r in rows])}

    # ---- E1: Sink + metadata exact at M - w, recent zeroed, replay w calls
    rec_out["E1"] = {}
    for w in E1_W:
        restore(pl, snaps[w], sink, zero_recent=True)
        rows, _ = replay(torch, pl, rec, list(range(M - w, M)), cfg_thr, sync, on_call=check)
        ring = compare_ring(torch, pl, snaps[0], sink, device)
        rows_m, outM = replay(torch, pl, rec, [M], cfg_thr, sync)
        rec_out["E1"][str(w)] = {"calls": rows, "ring_at_M": ring, "call_M": {**out_error(torch, outM, ent[M]["out"]), "meta_diff": rows_m[0]["meta_diff"]},
                                 "meta_equal_all": all(not r["meta_diff"] for r in rows + rows_m),
                                 "replay_s_median": st.median([r["replay_s"] for r in rows]) if rows else None}
    del snaps
    return rec_out


def digest(t) -> str:
    import torch

    return hashlib.sha256(t.detach().contiguous().view(torch.int16).cpu().numpy().tobytes()).hexdigest()


# --------------------------------------------------------------------------- GPU driver (one unit)
def run_unit(a):
    import vc_schedules as vs
    from expw_w1 import workload_paths
    import mobility_node as mn

    unit = a.unit
    inp, seed = unit.rsplit("_s", 1)
    sched = vs.unit_sched(json.loads(SCHED.read_text()), unit)
    Ms = {c["id"]: c["resets"][0] for c in sched["conditions"] if c["id"] in CELLS}
    video, prompt = workload_paths(inp, a.loveu_dir)
    margs = mn.parse_args(["--label", "M1R", "--video_path", str(video), "--prompt_file_path", str(prompt), "--seed", seed, "--gpu_id", str(a.gpu_id),
                           "--migration_chunk", "0", "--post_chunks", str(sched["N"])])   # as vc_emulate (same video length)
    rt = mn.GpuRuntime(margs)
    torch, pl, device = rt.torch, rt.pl, rt.device
    sync = lambda: torch.cuda.synchronize(device)
    rec = Recorder(torch, pl, rt.sink, device, sync)
    res = {"unit": unit, "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
           "dirty": bool(subprocess.run(["git", "status", "--porcelain", "--", "tools", "models", "streamv2v"], cwd=ROOT, capture_output=True, text=True).stdout.strip()),
           "host": platform.node(), "gpu": torch.cuda.get_device_name(device), "torch": torch.__version__, "k": rt.k, "sink_slots": rt.sink,
           "fsl": rt.fsl, "cfg_thr": rt.cfg_thr, "cells": {}}
    streams = {}
    first = True
    for cell in CELLS:
        M = Ms[cell]
        if not first:
            rt.pm.reset_stream_state(reset_vae_flags=True)
        first = False
        for b in blocks(pl):
            b.self_attn.adapt_sink_thr = rt.cfg_thr
        session = rt.runner.start()
        t0 = time.time()
        r = run_cell(torch, pl, rec, lambda c: rt.runner.step(session, c), M, rt.sink, rt.cfg_thr, device, sync, mem=rt.mem)
        streams[cell] = {c: digest(x) for c, x in rec.inputs.items()}
        r["elapsed_s"] = time.time() - t0
        res["cells"][cell] = r
        print(f"[M1R] {unit} {cell} M={M}: E0 {'PASS' if r['E0']['pass'] else 'FAIL'}; E1 recent K rel " +
              ", ".join(f"w{w} {r['E1'][str(w)]['ring_at_M']['recent_rel']['k']:.3g}" for w in E1_W) + f"; {r['elapsed_s']:.0f} s", flush=True)
        rec.reset(); del session
        import gc
        gc.collect(); torch.cuda.empty_cache()
    common = sorted(set(streams["OT-1"]) & set(streams["OT-L"]))
    res["determinism"] = {"calls_compared": len(common), "inputs_equal": all(streams["OT-1"][c] == streams["OT-L"][c] for c in common)}
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{unit}.json").write_text(json.dumps(res, indent=1, default=str))
    print(f"[M1R] {unit}: determinism {res['determinism']} -> {out / (unit + '.json')}", flush=True)


# --------------------------------------------------------------------------- aggregation
def aggregate(out_dir: Path) -> dict:
    files = sorted(out_dir.glob("*.json"))
    rows, A = [], {"cells": 0, "e0_pass": 0, "determinism": [], "e1": {str(w): [] for w in E1_W}, "timing": []}
    L = ["# M1 input-log replay: E0 / E1 results", "",
         "Generated by `tools/eval/m1_replay.py --aggregate` from the per-unit files. Reading rules: `e0e1_plan.md` (fixed before the run).", ""]
    E0T = ["| cell | E0 | ring K / V bitwise | metadata | written slots | call-M output | replay s/call | source gen s/call | source call s |", "|---|---|---|---|---|---|---|---|---|"]
    E1T = ["| cell | w | recent K rel | recent V rel | by age K (old..new) | Sink K rel | refreshes in window | layer 0 bitwise | call-M out rel (row 0 / row 1) | metadata |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    TRJ = {}
    for f in files:
        d = json.loads(f.read_text())
        A["determinism"].append((d["unit"], d["determinism"]))
        for cell, r in d["cells"].items():
            key = f"{d['unit']}|{cell}"
            A["cells"] += 1
            e0 = r["E0"]
            A["e0_pass"] += bool(e0["pass"])
            src = r["source"]
            A["timing"].append({"cell": key, "replay": e0["replay_s_median"], "gen": src["gen_s_window_median"], "call": src["call_s_pre_window_median"] or src["call_s_all_median"]})
            E0T.append(f"| {key} | {'PASS' if e0['pass'] else 'FAIL'} | {e0['ring_at_M']['bitwise']['k']} / {e0['ring_at_M']['bitwise']['v']} | "
                       f"{'equal' if not e0['ring_at_M']['meta_diff'] and all(not c['meta_diff'] for c in e0['calls']) else 'DIFF'} | "
                       f"{sum(c['slot_bitwise'] for c in e0['calls'])} / {len(e0['calls'])} | {e0['call_M']['bitwise']} | {e0['replay_s_median']:.3f} | "
                       f"{src['gen_s_window_median']:.3f} | {(src['call_s_pre_window_median'] or src['call_s_all_median']):.3f} |")
            n_ref = sum(len(v) for v in src["refresh_in_window"].values())
            for w in E1_W:
                e = r["E1"][str(w)]
                ring = e["ring_at_M"]
                n_ref_w = sum(len(v) for c, v in src["refresh_in_window"].items() if r["M"] - w <= int(c) < r["M"])
                A["e1"][str(w)].append({"cell": key, "k": ring["recent_rel"]["k"], "v": ring["recent_rel"]["v"], "out": e["call_M"]["rel_per_row"],
                                        "meta": e["meta_equal_all"], "l0": ring["layer0_recent_bitwise"]})
                E1T.append(f"| {key} | {w} | {ring['recent_rel']['k']:.4f} | {ring['recent_rel']['v']:.4f} | "
                           f"{' / '.join(f'{x:.3f}' for x in ring['recent_rel_by_age']['k'])} | {ring['sink_rel']['k']:.4f} | {n_ref_w} | {ring['layer0_recent_bitwise']} | "
                           f"{' / '.join(f'{x:.4f}' for x in e['call_M']['rel_per_row'])} | {'equal' if e['meta_equal_all'] else 'DIFF'} |")
                if w == max(E1_W):
                    TRJ[key] = [(c["slot_rel_k"], c["slot_rel_v"]) for c in e["calls"]]
            rows.append(key)
    # reading quantities (e0e1_plan.md section 3)
    ratio = {}
    for w in E1_W:
        if w == 0:
            continue
        rs = []
        for x, z in zip(A["e1"][str(w)], A["e1"]["0"]):
            rs.append(x["out"][-1] / z["out"][-1] if z["out"][-1] else None)
        ratio[str(w)] = rs
    A["out_ratio_last_row"] = ratio
    keep_up = [t for t in A["timing"] if t["replay"] is not None and t["call"] is not None]
    A["keep_up"] = {"replay_below_call_interval": sum(t["replay"] < t["call"] for t in keep_up), "of": len(keep_up)}
    L += [f"Cells {A['cells']}; E0 pass {A['e0_pass']} / {A['cells']}; determinism (inputs of the two source streams of a unit): " +
          "; ".join(f"{u} {d['inputs_equal']} ({d['calls_compared']} calls)" for u, d in A["determinism"]), "",
          "## E0: exact replay (12 calls from the exact ring at M - 12)", ""] + E0T + ["",
          "## E1: log-only replay (Sink and metadata exact at M - w, recent zeroed)", ""] + E1T + ["",
          "## E1 convergence: relative error of the slot written by each replayed call (w = 12; K / V)", "",
          "| cell | " + " | ".join(f"M-{WINDOW - j}" for j in range(WINDOW)) + " |", "|---|" + "---|" * WINDOW]
    for key, trj in TRJ.items():
        L.append(f"| {key} | " + " | ".join(f"{k:.3f} / {v:.3f}" for k, v in trj) + " |")
    L += ["", "## Reading quantities", "",
          "Call-M output error of the decoded row (last Stream-Batch row) relative to w = 0 (exact Sink, zero recent; the S3 analogue). 0 = the source's output (RS3), 1 = no gain:", ""]
    L += [f"- w = {w}: " + ", ".join(f"{c['cell']} {r:.3f}" for c, r in zip(A["e1"][w], ratio[w]) if r is not None) for w in ratio]
    L += ["", f"Replay (median per call, E0) below the source call interval (median, calls before the window): {A['keep_up']['replay_below_call_interval']} / {A['keep_up']['of']} cells", ""]
    (out_dir / "e0e1_results.md").write_text("\n".join(L) + "\n")
    (out_dir / "e0e1_summary.json").write_text(json.dumps(A, indent=1, default=str))
    print("\n".join(L[:12]))
    return A


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unit", choices=UNITS)
    ap.add_argument("--gpu_id", type=int, default=0)
    ap.add_argument("--loveu_dir", default=None)
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--out_dir", default=str(OUT))
    a = ap.parse_args()
    if a.aggregate:
        aggregate(Path(a.out_dir))
    elif a.unit:
        run_unit(a)
    else:
        ap.error("--unit or --aggregate")


if __name__ == "__main__":
    main()
