#!/usr/bin/env python3
"""Experiment VC emulator (osdi/expVC/implementation_plan.md section 2). Does not modify rd_emulate.py or any mechanism.

One process = one input on one GPU: the uninterrupted reference (GpuRuntime.baseline, frames kept), then each requested
condition of results/evaluation/osdi/expVC/vc_schedules.json from call 0:

  ot   (OT-1, OT-L, OT-R)  RD semantics: an M1 reset before every reset call (serialize, pack in-flight + meta [+ the Sink
                           once per episode], release, provision, unpack, restore_fast); a bind before every bind call
                           (the withheld Sink of the episode). Same operations as rd_emulate.run_condition.
  wfs  (WFS-1, WFS-L)      reset and bind before the same call (RD d = 0): the Sink is bound before generation resumes.
  cold (COLD-1, COLD-L)    at the move call c the destination path of the frozen `cold` policy: release, provision (a
                           fresh destination session, as MANIFEST provisioning), GpuRuntime.cold_restart(c); no model
                           call at c (skip), the cold restart's frames emitted at c + k - 1 (the node's pending_cold rule).

Saved: every output frame of the condition's span (FFV1, vc_frames.FrameStore) in --frames_dir on local disk, and
calls.csv / summary.json under --out_root (results; copied back to elves-01 by run_vc.py).

    python tools/eval/vc_emulate.py --input dog --only OT-L,COLD-1,WFS-1 --frames_dir /local/vc_frames --out_root results/evaluation/expVC0
    python tools/eval/vc_emulate.py --input dog --dry_run --frames_dir /tmp/vcf      # fake runtime (protocol test)
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

from rd_emulate import payload_of, sha  # noqa: E402
import vc_frames as vf  # noqa: E402

SCHED = ROOT / "results/evaluation/osdi/expVC/vc_schedules.json"


def dry_frames(c: int, phase_shift: int, h: int, w: int) -> np.ndarray:
    """Fake runtime only: 4 deterministic frames per call; the pattern shifts after an operation so markers are visible."""
    y, x = np.mgrid[0:h, 0:w]
    return np.stack([np.stack([(x + 3 * (4 * c + f) + phase_shift) % 256, (y + 2 * (4 * c + f)) % 256, ((x + y) // 2 + phase_shift) % 256], -1)
                     for f in range(4)]).astype(np.uint8)


def set_sink_mask(rt, on: bool, dry: bool) -> int:
    """Experiment VD: mask (or stop masking) the zero-filled sink slots in every attention block; returns the number of
    mask violations counted since the last call (the sink region was not empty while masked)."""
    if dry:
        return 0
    v = 0
    for block in rt.pl.generator.model.blocks:
        sa_ = block.self_attn
        v += getattr(sa_, "mask_violations", 0)
        sa_.mask_violations = 0
        sa_.mask_sink_slots = bool(on)
    return v


def keep_state(rt, kept: list, keep: list, dry: bool) -> dict:
    """Experiment VD: give the destination session the source's state of the kept components (recent KV, VAE decoder
    and / or encoder caches) together with the M1 fast path. Nothing is transferred; the emulator copies it.
    state_ablation.restore_state zeroes every KV slot, every unselected VAE cache and the in-flight rows on each call,
    so the fast path (meta, in-flight) and the kept components are restored in ONE call. In the M1 reset itself the VAE
    caches are zero; a decoder-only keep therefore puts the encoder cache and its bookkeeping back to that state."""
    if dry or not kept:
        return {"kept": keep}
    for h, pl in kept:
        rt.unpack(dict(h), pl)
    comps = {"meta", "inflight"} | ({"recent"} if "recent" in keep else set()) | ({"vae"} if any(x.startswith("vae") for x in keep) else set())
    vm = rt.pl.vae.model
    enc_reset = None
    if "vae_dec" in keep and "vae_enc" not in keep:
        enc_reset = {"tensors": [t.clone() for t in rt.sa.vae_cache_tensors(rt.pl, "enc")],
                     "attrs": {a: (list(getattr(vm, a)) if isinstance(getattr(vm, a, None), list) else getattr(vm, a, None)) for a in ("_enc_conv_idx", "first_encode")}}
    moved = rt.sa.restore_state(rt.pl, rt.pm, rt.session, rt.snap, comps)
    if enc_reset is not None:
        cur = rt.sa.vae_cache_tensors(rt.pl, "enc")
        assert len(cur) == len(enc_reset["tensors"]), "encoder cache layout changed"
        for t, b in zip(cur, enc_reset["tensors"]):
            t.copy_(b)
        for a, v in enc_reset["attrs"].items():
            setattr(vm, a, v)
    for block in rt.pl.generator.model.blocks:
        block.self_attn.adapt_sink_thr = -1   # as restore_fast: refresh frozen until the true Sink binds
    rt.torch.cuda.synchronize(rt.device)
    return {"kept": keep, "comps_restored": sorted(comps), "moved_bytes": {k_: int(v) for k_, v in (moved or {}).items()}}


def vd2_reset(rt, c: int, cond: dict, fast_pl: list, dry: bool, log: dict, src_last_image, src_dec_cache, src_latents, recent_frames):
    """Experiment VD-2: the M1 reset at call c with destination-side reconstruction (preregistration section 7).
    Order: [TS prepare -> save its sink slots] -> [RP-1 replay | fast path restore] -> [write the saved slots] -> [DR-k
    decode]. Costs are serial GPU seconds, measured per step; a combination's cost is the sum of what actually ran."""
    dr, rp, ts = int(cond.get("dr") or 0), bool(cond.get("rp")), cond.get("ts")
    cost = log["cost_s"]
    temp = None
    if ts:
        if dry:
            images = None
        elif ts == "in":
            images = rt.torch.cat([src_last_image, rt.runner.frames_for_call(c)], dim=2)   # the cold-restart seed: [last input frame, current chunk]
        else:
            fr = np.concatenate(recent_frames)[-5:] if recent_frames else None   # the source's last 5 output frames (1 + chunk)
            if fr is None or len(fr) < 5:
                raise RuntimeError("TS-out needs the source's last 5 output frames")
            images = rt.frames_to_images(fr)
        temp, cost["ts_prepare_s"] = rt.temp_sink_prepare(images, c)
    if rp:
        cost["rp_replay_s"], log["replayed"] = rt.replay_one_chunk(c)   # regenerates recent KV, VAE caches and in-flight rows
        if temp is None:
            rt.zero_sink_slots()   # RP-1 alone: no temporary Sink (the replay's own prepare wrote one)
    else:
        for h, pl in fast_pl:
            rt.unpack(dict(h), pl)
        rt.restore_fast()   # frozen M1 fast path: meta + in-flight; KV and VAE caches zero
    if temp is not None:
        log["ts_slots_written"] = rt.write_sink_slots(temp)   # 2 of 3 (prepare's latents); the third stays zero until the bind
    if dr:
        if not dry:
            log["latent_shapes"] = [list(z.shape) for z in src_latents]
            if len(src_latents) < dr:
                log["dr_short"] = f"only {len(src_latents)} latent frames captured"
        cost["dr_decode_s"] = rt.decode_latents(src_latents)
        log["fidelity"] = rt.vae_dec_fidelity(src_dec_cache)
    rt.freeze_refresh()
    cost["total_serial_s"] = float(sum(cost.values()))


def vd3_reset(rt, c: int, cond: dict, fast_pl: list, dry: bool, log: dict, src_last_image, src_latents, stale_latents, seed: int):
    """Experiment VD-3 (osdi/expVD3/preregistration.md section 2): the M1 reset at call c with destination-side
    reconstruction. Order: [TS-in prepare -> save its sink slots (and, TSinKC, its decoder state)] -> fast path restore
    (meta + in-flight; KV and VAE caches zero, as frozen M1) -> [write the saved slots] -> [TSinKC: write the saved
    decoder state] -> [DR-2 decode of the latent source: last / stale / noise]. Serial GPU seconds per step; the
    TSinKC copy is an emulation artifact (a node keeps the cache instead of zeroing it) and is recorded but not counted."""
    dr, ts, kc, src = int(cond.get("dr") or 0), cond.get("ts"), bool(cond.get("keep_cache")), cond.get("dr_source") or "last"
    cost = log["cost_s"]
    temp = kc_state = None
    if ts:
        images = None if dry else rt.torch.cat([src_last_image, rt.runner.frames_for_call(c)], dim=2)   # the cold-restart seed: [last input frame, current chunk]
        temp, cost["ts_prepare_s"] = rt.temp_sink_prepare(images, c)
        if kc:
            kc_state = rt.vae_dec_state_copy()
            log["kc_prepare_digest"] = rt.dec_digest(kc_state["tensors"]) if not dry else "fake-dec-digest"
    for h, pl in fast_pl:
        rt.unpack(dict(h), pl)
    rt.restore_fast()   # frozen M1 fast path: meta + in-flight; KV and VAE caches zero
    if temp is not None:
        log["ts_slots_written"] = rt.write_sink_slots(temp)   # 2 of 3 (prepare's latents); the third stays zero until the bind
    if kc_state is not None:
        log["kc_copy_s_not_counted"], log["kc_live_digest"] = rt.vae_dec_state_write(kc_state)
        log["kc_digest_equal"] = log["kc_live_digest"] == log["kc_prepare_digest"]
    if dr:
        lats = {"last": src_latents, "stale": stale_latents}.get(src)
        if src == "noise":
            lats, log["noise"] = rt.noise_latents(src_latents, seed * 1000003 + c)
        if not dry:
            log["latent_shapes"] = [list(z.shape) for z in lats]
            if len(lats) < dr:
                log["dr_short"] = f"only {len(lats)} latent frames ({src})"
        log["dr_source"] = src
        cost["dr_decode_s"] = rt.decode_latents(lats)
    rt.freeze_refresh()
    cost["total_serial_s"] = float(sum(cost.values()))
    return temp


def vd4_reset(rt, c: int, cond: dict, snap: dict, fast_pl: list, dry: bool, log: dict, src_last_image, src_latents):
    """Experiment VD-4 (osdi/expVD4/preregistration.md section 3): the M1 reset at call c with oracle state from the ONE
    snapshot taken at the reset (the same instant the fast path and the withheld Sink were packed).
    V0: every component from the snapshot, refresh unfrozen, no bind (validity gate: must equal REF).
    Otherwise: [TS-in prepare] -> frozen fast path (meta + in-flight; KV / VAE zero) -> [oracle recent KV] ->
    [temporary-Sink K / V; A1: K re-rotated to the source positions] -> [oracle Sink slots, fixed order 2, 1, 0;
    quantized if requested] -> [decoder: oracle cache | DR-2 decode] -> refresh frozen -> verification of every
    injected component (bytes, digests, positions) after the last reset operation, i.e. nothing later overwrote it."""
    cost, chk = log["cost_s"], log["checks"]
    sup, chs = log.setdefault("supp", {}), log.setdefault("checks_supp", {})   # VD-4 addendum 1: per-layer / per-slot records and checks
    if cond.get("v0"):
        rt.restore_all_from(snap)
        log["v0"] = True
        return None
    sink, n_slots = int(getattr(rt, "sink", 3)), rt.n_slots()
    ts, dec, rec, slots, quant = cond.get("ts"), cond.get("dec"), bool(cond.get("oracle_recent")), list(cond.get("oracle_sink_slots") or []), cond.get("quant")
    temp = None
    if ts:
        images = None if dry else rt.torch.cat([src_last_image, rt.runner.frames_for_call(c)], dim=2)
        temp, cost["ts_prepare_s"] = rt.temp_sink_prepare(images, c)
        log["prepare_positions_layer0"] = [int(p) for p in (temp[0][2][0, :sink].tolist() if not dry else [0, 1, -(1 << 30)])]
        sup["prepare_positions"] = [[int(p) for p in t_[2][0, :sink].tolist()] for t_ in temp] if not dry else []
    for h, pl in fast_pl:
        rt.unpack(dict(h), pl)
    rt.restore_fast()
    src_pos = rt.positions(list(range(n_slots)), snap)
    live_pos = rt.positions(list(range(n_slots)))
    log["source_positions_layer0"] = src_pos[0]
    sup["source_positions"] = src_pos   # every layer, every slot
    chk["meta_positions_equal_snapshot"] = live_pos == src_pos
    if rec:
        rt.write_snap_slots(snap, list(range(sink, n_slots)))
        log["bytes"]["oracle_recent"] = rt.kv_nbytes(list(range(sink, n_slots)))
        rs = list(range(sink, n_slots))   # addendum 1: equal right after the write (and again after the last reset step below)
        chs["recent_k_equal_at_write"] = rt.kv_digest(rs, "k") == rt.kv_digest(rs, "k", snap=snap)
        chs["recent_v_equal_at_write"] = rt.kv_digest(rs, "v") == rt.kv_digest(rs, "v", snap=snap)
    ts_written, expect_k = [], None
    if temp is not None:
        if ts == "in_aligned":
            EMPTY = -(1 << 30)
            deltas = []
            for li, (k_, v_, pos_) in enumerate(temp):
                pp = pos_[0, :sink].tolist() if not dry else [0, 1, EMPTY]
                deltas.append([None if pp[s_] == EMPTY else live_pos[li][s_] - int(pp[s_]) for s_ in range(sink)])
            temp_w, log["a1_rotation"] = rt.rotate_temp(temp, deltas)
            log["a1_deltas_layer0"] = deltas[0]
            sup["a1_deltas"] = deltas
            sup["a1_per_layer_slot"] = log["a1_rotation"].pop("per_layer_slot", [])   # delta, K changed (elements), round-trip error
        else:
            temp_w = temp
        log["ts_slots_written"] = rt.write_sink_slots(temp_w)
        ts_written = [s_ for s_ in range(log["ts_slots_written"])]
        expect_k = temp_w
    kv_over = None
    if slots:
        if quant:
            kv_over, log["bytes"]["oracle_sink_payload"] = rt.quantize_slots(snap, slots, quant)
        rt.write_snap_slots(snap, slots, kv_over)
        log["bytes"]["oracle_sink"] = rt.kv_nbytes(slots)
    if dec == "oracle":
        st = rt.dec_state_from_snap(snap) if not dry else rt.vae_dec_state_copy()
        log["oracle_dec_copy_s"], live_dg = rt.vae_dec_state_write(st)
        log["bytes"]["oracle_decoder"] = int(sum(t.numel() * t.element_size() for t in st["tensors"])) if not dry else 1800000000
        log["dec_snapshot_digest"] = rt.dec_digest(st["tensors"]) if not dry else live_dg
        chs["decoder_equal_at_write"] = live_dg == log["dec_snapshot_digest"]
    elif dec == "dr2":
        if not dry:
            log["latent_shapes"] = [list(z.shape) for z in src_latents]
        cost["dr_decode_s"] = rt.decode_latents(src_latents)
        log["bytes"]["dr2_latents"] = 2 * 16 * 60 * 104 * 2
    rt.freeze_refresh()
    cost["total_serial_s"] = float(sum(v for v in cost.values() if v is not None))
    # ---- verification after the last reset operation (bytes, digests, positions; K and V separately)
    if rec:
        rs = list(range(sink, n_slots))
        chk["recent_k_equal"] = rt.kv_digest(rs, "k") == rt.kv_digest(rs, "k", snap=snap)
        chk["recent_v_equal"] = rt.kv_digest(rs, "v") == rt.kv_digest(rs, "v", snap=snap)
        chk["recent_positions_equal"] = rt.positions(rs) == rt.positions(rs, snap)
    if slots:
        chk["sink_k_equal"] = rt.kv_digest(slots, "k") == rt.kv_digest(slots, "k", snap=snap, kv_override=kv_over)
        chk["sink_v_equal"] = rt.kv_digest(slots, "v") == rt.kv_digest(slots, "v", snap=snap, kv_override=kv_over)
        chk["sink_positions_equal"] = rt.positions(slots) == rt.positions(slots, snap)
    left_ts = [s_ for s_ in ts_written if s_ not in slots]
    if left_ts:
        chk["ts_k_as_written"] = rt.kv_digest(left_ts, "k") == rt.temp_digest(expect_k, left_ts, "k")
        chk["ts_v_unrotated"] = rt.kv_digest(left_ts, "v") == rt.temp_digest(temp, left_ts, "v")
        if ts == "in_aligned" and not dry and any(d for d in log.get("a1_deltas_layer0", []) if d):
            chk["a1_k_rotated"] = rt.kv_digest(left_ts, "k") != rt.temp_digest(temp, left_ts, "k")   # the rotation was applied to K
    if dec == "oracle":
        chk["decoder_equal"] = rt.dec_digest() == log["dec_snapshot_digest"]
    chk["layers"] = len(rt.positions([0]))
    # ---- addendum 1 (supplemental; recorded separately from the frozen checks above): per layer and slot, after the
    # last reset operation; K changes from the A1 rotation are recorded, never required (bf16 rounding)
    fin = rt.positions(list(range(n_slots)))
    sup["final_positions"] = fin
    chs["positions_final_equal_snapshot"] = fin == src_pos
    if rec:
        rs = list(range(sink, n_slots))
        for part in ("k", "v"):
            eq = rt.slot_equal(rs, part, snap=snap)
            sup[f"recent_{part}_equal_per_layer_slot"] = eq
            chs[f"recent_{part}_equal_per_layer_slot"] = all(all(r) for r in eq)
    if slots:
        for part in ("k", "v"):
            eq = rt.slot_equal(slots, part, snap=snap, override=kv_over)
            chs[f"sink_{part}_equal_per_layer_slot"] = all(all(r) for r in eq)
    if left_ts:
        ke, ve = rt.slot_equal(left_ts, "k", saved=expect_k), rt.slot_equal(left_ts, "v", saved=temp)
        chs["ts_k_as_written_per_layer_slot"], chs["ts_v_unrotated_per_layer_slot"] = all(all(r) for r in ke), all(all(r) for r in ve)
        pos_ok = [[fin[li][s_] == src_pos[li][s_] for s_ in left_ts] for li in range(len(fin))]
        chs["ts_positions_equal_snapshot_per_layer_slot"] = all(all(r) for r in pos_ok)
        if ts == "in_aligned":
            by = {(r["layer"], r["slot"]): r for r in sup.get("a1_per_layer_slot", [])}
            sup["a1_per_layer_slot"] = [{**by.get((li, s_), {"layer": li, "slot": s_}), "k_as_expected": ke[li][j], "v_unrotated": ve[li][j], "position_equal_snapshot": pos_ok[li][j],
                                         "position": fin[li][s_]} for li in range(len(ke)) for j, s_ in enumerate(left_ts)]
    if dec == "oracle":
        lay = rt.dec_layout(snap)
        sup["decoder_layout"] = lay
        chs["decoder_layout_equal"] = bool(lay.get("layout_ok"))
        chs["decoder_tensors_equal_per_entry"] = bool(lay.get("tensors_equal"))
        chs["decoder_attrs_equal"] = bool(lay.get("attrs_equal"))
    return temp


def run_condition(rt, cond: dict, base_record: list, dry: bool, store: vf.FrameStore, k: int, hw) -> tuple[list[dict], dict]:
    resets, binds = set(cond["resets"]), set(cond["binds"])
    cc = cond.get("cold_call")
    t1 = min(cond["resets"] + ([cc] if cc is not None else []))
    rows, log = [], []
    withheld = None
    bound_sha = []
    prefix_ok = True
    pending_cold = None
    shift = 0
    keep = list(cond.get("keep") or [])
    vd_log = {"mask": bool(cond.get("mask")), "keep": keep, "mask_violations": 0, "kept": []}
    vd2 = cond.get("kind") == "vd2"
    dr, rp, ts = int(cond.get("dr") or 0), bool(cond.get("rp")), cond.get("ts")
    vd2_log = {"dr": dr, "rp": rp, "ts": ts, "cost_s": {}, "fidelity": None, "latent_shapes": None, "replayed": None} if vd2 else None
    vd3 = cond.get("kind") == "vd3"
    vd4 = cond.get("kind") == "vd4"
    vd4_log = {"cost_s": {}, "checks": {}, "bytes": {}, "condition": {k_: cond.get(k_) for k_ in ("dec", "oracle_recent", "ts", "oracle_sink_slots", "quant", "v0")}} if vd4 else None
    vd3_log = {"dr": dr, "ts": ts, "keep_cache": bool(cond.get("keep_cache")), "dr_source": cond.get("dr_source"), "cost_s": {}} if vd3 else None
    stale_calls = [cond["resets"][0] - 18, cond["resets"][0] - 17] if (vd3 and cond.get("dr_source") == "stale") else []   # DR-2's pair (m-2, m-1) 16 calls earlier
    stale_latents, temp_sink = [], None
    recent_frames = []   # the source's last output frames (TS-out), kept as uint8
    if (vd2 or vd3 or vd4) and not dry:
        rt.capture_latents = True
    if dry:
        rt.provision(); rt.bound = True
    else:
        rt.session = rt.runner.start()
    t_run = time.time()
    for c in range(cond["end"] + 1):
        event = []
        if c in resets:   # --- identical to rd_emulate.run_condition (withheld Sink, packed once per episode)
            t0 = time.perf_counter()
            snap = rt.serialize_live()
            fast = [rt.pack(snap, comp) for comp in ("inflight", "meta")]
            kept = [rt.pack(snap, comp) for comp in (["recent"] if "recent" in keep else []) + (["vae"] if any(x.startswith("vae") for x in keep) else [])]
            if withheld is None:
                h, bufs = rt.pack(snap, "sink")
                pl = payload_of(h, bufs)
                withheld = (h, pl, sha(pl), c)
                log.append({"call": c, "op": "episode_open", "sink": "packed", "sha": withheld[2][:16]})
            else:
                log.append({"call": c, "op": "reset_inside_episode", "sink": "kept", "sha": withheld[2][:16]})
            fast_pl = [(dict(h), payload_of(h, bufs)) for h, bufs in fast]
            kept_pl = [(dict(h), payload_of(h, bufs)) for h, bufs in kept]
            vd4_snap = snap if vd4 else None   # VD-4: every oracle component comes from this one snapshot
            if vd4:
                src_last_image = None if dry else snap["session"]["last_image"].detach().clone()
                src_latents = list(rt.last_latents)[-2:] if not dry else []
            if vd2 or vd3:
                src_last_image = None if dry else snap["session"]["last_image"].detach().clone()
                src_dec_cache = rt.vae_dec_cache_copy() if (dr or cond.get("keep_cache")) else None
                src_latents = (list(rt.last_latents)[-dr:] if dr else []) if not dry else []
            del snap, fast, kept
            rt.release(); rt.provision()
            if vd2:
                vd2_reset(rt, c, cond, fast_pl, dry, vd2_log, src_last_image, src_dec_cache, src_latents, recent_frames)
                shift += 25 + 10 * dr + (30 if rp else 0) + (50 if ts else 0)
            elif vd4:
                temp_sink = vd4_reset(rt, c, cond, vd4_snap, fast_pl, dry, vd4_log, src_last_image, src_latents)
                del vd4_snap
                shift += 25 + (10 if cond.get("dec") else 0) + (50 if cond.get("ts") else 0) + 5 * len(cond.get("oracle_sink_slots") or []) + (9 if cond.get("oracle_recent") else 0) + (99 if cond.get("v0") else 0)
            elif vd3:
                temp_sink = vd3_reset(rt, c, cond, fast_pl, dry, vd3_log, src_last_image, src_latents, stale_latents, int(rt.args.seed))
                if src_dec_cache is not None:
                    vd3_log["fidelity"] = rt.vae_dec_fidelity(src_dec_cache)   # reconstructed (DR2 / stale / noise) vs the source's cache
                shift += 25 + 10 * dr + (50 if ts else 0) + (5 if cond.get("keep_cache") else 0) + {"stale": 3, "noise": 7}.get(cond.get("dr_source"), 0)
            else:
                for h, pl in fast_pl:
                    rt.unpack(dict(h), pl)
                rt.restore_fast()
            if keep:
                vd_log["kept"].append({"call": c, **keep_state(rt, kept_pl, keep, dry)})
            del kept_pl
            if cond.get("mask"):
                vd_log["mask_violations"] += set_sink_mask(rt, True, dry)
            event.append("reset"); log[-1]["reset_s"] = time.perf_counter() - t0; shift += 40
        if c in binds:
            assert withheld is not None, f"bind at {c} without a withheld Sink"
            h, pl, s_, at = withheld
            assert sha(pl) == s_, "withheld Sink bytes changed"
            t0 = time.perf_counter()
            if cond.get("mask"):
                vd_log["mask_violations"] += set_sink_mask(rt, False, dry)   # the true Sink is bound: attention over all slots again
            rt.unpack(dict(h), pl)
            shifted = rt.bind()
            if vd3 and temp_sink is not None:
                vd3_log["temp_slots_left_after_bind"] = rt.temp_slots_left(temp_sink)
            if vd4 and temp_sink is not None:
                vd4_log["temp_slots_left_after_bind"] = rt.temp_slots_left(temp_sink)
            bound_sha.append({"call": c, "sha": s_, "packed_at": at})
            log.append({"call": c, "op": "bind", "sha": s_[:16], "packed_at": at, "slots_rerotated": shifted, "bind_s": time.perf_counter() - t0})
            withheld = None
            event.append("bind"); shift += 7
        if cc is not None and c == cc:   # --- the frozen `cold` destination path
            t0 = time.perf_counter()
            rt.release(); rt.provision()
            frames_cold, ms = rt.cold_restart(c)
            pending_cold = {"skip": c, "emit": c + k - 1, "frames": frames_cold}
            log.append({"call": c, "op": "cold_restart", "cold_restart_ms": ms, "s": time.perf_counter() - t0})
            event.append("cold_restart"); shift += 90
        out_in = c - (k - 1)
        if pending_cold is not None and c in (pending_cold["skip"], pending_cold["emit"]):
            is_skip = c == pending_cold["skip"] and c != pending_cold["emit"]
            is_emit = c == pending_cold["emit"]
            produced, ps, ss, dt, pos = rt.step(c, override=pending_cold["frames"] if is_emit else None, skip=is_skip)
            if is_skip:
                event.append("skip"); out_in = None
            if is_emit:
                event.append("emit"); out_in = pending_cold["skip"]; pending_cold = None
        else:
            produced, ps, ss, dt, pos = rt.step(c)
        fr = getattr(rt, "last_frames", None)
        if dry and produced:
            fr = dry_frames(out_in, shift + 3 * int(rt.args.seed) * ((c * 7) % 5), *hw)
        if not produced:
            fr = None
        if vd2 and fr is not None:
            recent_frames.append(np.asarray(fr)); del recent_frames[:-2]
        if c in stale_calls and not dry and produced:
            stale_latents.append(rt.last_latents[-1].detach().clone())   # the decode input of call c (one decode per call)
        dg = vf.frame_digest(fr)
        if c < t1 and not dry and dg != base_record[c]["frame_digest"]:
            prefix_ok = False
        phase = "prefix" if c < t1 else ("sinkless" if (withheld is not None) else ("cold" if cc is not None else "bound"))
        ref_dg = base_record[c]["frame_digest"] if (base_record and not dry) else None
        rows.append({"call": c, "phase": phase, "event": "+".join(event), "psnr": ps, "ssim": ss, "produced": produced, "chunk_s": dt,
                     "out_input_call": out_in if produced else None, "frame_digest": dg, "ref_match": (dg == ref_dg) if (dg and ref_dg) else None})
        if cond["frames_from"] <= c <= cond["frames_to"]:
            store.add(c, fr, events=event, phase=phase, out_input_call=out_in if produced else None, digest=dg)
    realized = {"resets": [r["call"] for r in rows if "reset" in r["event"]], "binds": [r["call"] for r in rows if "bind" in r["event"]],
                "cold": [r["call"] for r in rows if "cold_restart" in r["event"]], "no_output": [r["call"] for r in rows if not r["produced"]]}
    exp_no_out = [cc] if (cc is not None and k > 1) else []
    valid = (realized["resets"] == cond["resets"] and realized["binds"] == cond["binds"] and realized["cold"] == ([cc] if cc is not None else [])
             and [c for c in realized["no_output"] if c >= t1] == exp_no_out and (dry or prefix_ok)
             and all((bs["packed_at"] in cond["resets"]) for bs in bound_sha))
    if cond.get("mask"):
        vd_log["mask_violations"] += set_sink_mask(rt, False, dry)
    if cond.get("kind") == "vd" and vd_log["mask_violations"]:
        valid = False   # the masked slots were not empty: the condition did not test what it claims
    if vd3:
        if stale_calls and not dry and len(stale_latents) != 2:
            valid = False; vd3_log["invalid"] = f"stale latents captured {len(stale_latents)} of 2"
        if vd3_log.get("ts_slots_written") not in (None, 2) or (vd3_log.get("temp_slots_left_after_bind") or 0) != 0:
            valid = False; vd3_log["invalid"] = f"temporary Sink slots written {vd3_log.get('ts_slots_written')}, left after the bind {vd3_log.get('temp_slots_left_after_bind')}"
        if vd3_log.get("keep_cache") and vd3_log.get("kc_digest_equal") is False:
            valid = False; vd3_log["invalid"] = "TSinKC: the live decoder cache differs from the prepare's"
        vd3_log["stale_calls"] = stale_calls
    if vd4:
        if cond.get("v0") and not dry:   # validity gate: every output after the move equals REF
            post = [r for r in rows if r["call"] >= t1 and r["produced"]]
            vd4_log["v0_identical_calls"] = sum(1 for r in post if r["frame_digest"] == base_record[r["call"]]["frame_digest"])
            vd4_log["v0_calls"] = len(post)
            vd4_log["v0_pass"] = vd4_log["v0_identical_calls"] == len(post) and len(post) > 0
            if not vd4_log["v0_pass"]:
                valid = False; vd4_log["invalid"] = f"V0: {vd4_log['v0_identical_calls']} of {len(post)} post-move outputs equal REF"
        bad = [k_ for k_, v in vd4_log["checks"].items() if v is False] + [f"supp:{k_}" for k_, v in (vd4_log.get("checks_supp") or {}).items() if v is False]
        if bad:
            valid = False; vd4_log["invalid"] = f"oracle checks failed: {bad}"
        if vd4_log.get("ts_slots_written") not in (None, 2) or (vd4_log.get("temp_slots_left_after_bind") or 0) != 0:
            valid = False; vd4_log["invalid"] = f"temporary Sink slots written {vd4_log.get('ts_slots_written')}, left after the bind {vd4_log.get('temp_slots_left_after_bind')}"
    if (vd2 or vd3 or vd4) and not dry:
        rt.capture_latents = False; rt.last_latents.clear()
    summary = {"condition": {k_: v for k_, v in cond.items() if k_ != "timeline"}, "t_first_op": t1, "events": log, "vd": vd_log if cond.get("kind") == "vd" else None,
               "vd2": vd2_log, "vd3": vd3_log, "vd4": vd4_log, "bound_sink": bound_sha, "realized": realized,
               "prefix_identical_to_reference": None if dry else prefix_ok, "valid": valid, "elapsed_s": time.time() - t_run}
    rt.release()
    return rows, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--only", default="", help="comma list of condition ids (default all seven)")
    ap.add_argument("--schedules", default=str(SCHED))
    ap.add_argument("--frames_dir", required=True, help="local-disk directory for the FFV1 frames (outside the repository)")
    ap.add_argument("--out_root", default=None)
    ap.add_argument("--gpu_id", type=int, default=0)
    ap.add_argument("--loveu_dir", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--no_ref_frames", action="store_true", help="do not store REF frames (checks that need none)")
    ap.add_argument("--skip_done", action="store_true", help="skip a condition whose summary.json in out_root is valid (re-runs after a failure)")
    a = ap.parse_args()
    import vc_schedules as vs

    allsched = json.loads(Path(a.schedules).read_text())
    sched = vs.unit_sched(allsched, f"{a.input}_s{a.seed}")   # seed-1 units (VD-3) and the VD-4 overlay
    if a.seed != 0 and f"{a.input}_s{a.seed}" not in allsched.get("units", {}):
        sys.exit(f"no schedule unit {a.input}_s{a.seed}")
    only = set(a.only.split(",")) if a.only else None
    conds = [c for c in sched["conditions"] if ((c["id"] in only) if only else (c.get("kind") not in ("vd2", "vd3", "vd4")))]   # VD-2 / VD-3 / VD-4 conditions only on request
    from expw_w1 import workload_paths
    import mobility_node as mn

    video, prompt = workload_paths(a.input, a.loveu_dir)
    N = sched["N"]
    hw = (96, 160) if a.dry_run else (480, 832)
    margs = mn.parse_args(["--label", "VC", "--video_path", str(video), "--prompt_file_path", str(prompt), "--seed", str(a.seed), "--gpu_id", str(a.gpu_id),
                           "--migration_chunk", "0", "--post_chunks", str(N), "--sink_fp"] +
                          (["--dry_run", "--dry_service_s", "0.0005", "--dry_sink_mb", "4", "--height", str(hw[0]), "--width", str(hw[1])] if a.dry_run else []))
    rt = mn.FakeRuntime(margs) if a.dry_run else mn.GpuRuntime(margs)
    k = int(rt.k)
    t0 = time.time()
    rt.baseline(0, N, keep_frames=True, write_ref=False)
    base_record = rt.base_record
    t_base = time.time() - t0
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_root = Path(a.out_root or ROOT / f"results/evaluation/{'_dryrun_' if a.dry_run else ''}expVC")
    unit = out_root / f"{a.input}_s{a.seed}"
    frames_root = Path(a.frames_dir) / f"{out_root.name}_{a.input}_s{a.seed}_{stamp}"
    host_meta = {"commit": commit, "host": platform.node(), "gpu_id": a.gpu_id, "dry_run": a.dry_run, "k": k, "baseline_s": t_base, "video": str(video), "prompt_file": str(prompt),
                 "frames_dir": str(frames_root), "versions": {} if a.dry_run else {"torch": rt.torch.__version__, "gpu": rt.torch.cuda.get_device_name(rt.device)}}
    if not a.no_ref_frames:
        ref = sched["ref"]
        st_ = vf.FrameStore(frames_root, "REF")
        for c in range(ref["frames_from"], ref["frames_to"] + 1):
            fr = rt.base.get(c) if not a.dry_run else dry_frames(c - (k - 1), 3 * a.seed * ((c * 7) % 5), *hw)   # dry: seeds differ a little
            st_.add(c, fr, phase="ref", out_input_call=c - (k - 1), digest=None if a.dry_run else base_record[c]["frame_digest"])
        st_.close({"input": a.input, "condition": "REF", **host_meta})
        d = unit / "REF"; d.mkdir(parents=True, exist_ok=True)
        (d / "summary.json").write_text(json.dumps({"condition": {"id": "REF", "kind": "ref", "frames_from": ref["frames_from"], "frames_to": ref["frames_to"], "resets": [], "binds": [], "cold_call": None},
                                                    "valid": True, "frames": str(frames_root / "REF"), **host_meta}, indent=1))
    for cond in conds:
        prev = unit / cond["id"] / "summary.json"
        if a.skip_done and prev.exists():
            try:
                if json.loads(prev.read_text()).get("valid") and Path(json.loads(prev.read_text())["frames"]).exists():
                    print(f"[VC] skip {cond['id']}: valid run exists", flush=True); continue
            except (ValueError, KeyError, OSError):
                pass
        store = vf.FrameStore(frames_root, cond["id"])
        rows, summ = run_condition(rt, cond, base_record, a.dry_run, store, k, hw)
        store.close({"input": a.input, "condition": cond["id"], **host_meta})
        d = unit / cond["id"]
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "calls.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
            for r in rows:
                w.writerow({k_: (f"{v:.4f}" if isinstance(v, float) else v) for k_, v in r.items()})
        summ.update({"input": a.input, "seed": a.seed, "frames": str(frames_root / cond["id"]), **host_meta})
        (d / "summary.json").write_text(json.dumps(summ, indent=1, default=str))
        print(f"[VC] {a.input} {cond['id']}: valid {summ['valid']} realized {summ['realized']} {summ['elapsed_s']:.0f} s -> {frames_root / cond['id']}", flush=True)


if __name__ == "__main__":
    main()
