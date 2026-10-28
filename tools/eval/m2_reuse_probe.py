#!/usr/bin/env python3
"""E7: can a host reuse the Sink it retained from an earlier migration (A -> B -> A)? Offline reconstruction probe,
one process, one GPU (osdi/m1_continuity/e7_plan.md). Not a migration protocol.

1. A (source) generates to M1 and logs calls c0 .. M1-1 (inputs, decisions, exact refresh patches; E5's log).
2. A's retained snapshot: a host copy of A's Sink (and its positions) at the M1 boundary.
3. B is built exactly as E5's destination: ring at c0 with recent zero, log replay with the patches applied after
   their calls; its Sink digest must equal A's at M1. Cutover as E5 (in-flight + metadata from A; replayed ring kept;
   refresh resumes).
4. B generates calls M1 .. M2-1 (a fixed interval). Every call's Sink events are recorded: realignment shifts of
   unwritten Sink slots (the RoPE delta) and refresh writes (the written K / V, exact).
5. From A's retained Sink, candidate reconstructions of B's Sink at M2, each compared with B's actual Sink per block
   (bitwise) and with the existing Sink digest (int64 block checksums + positions):
     ordered          every event in call order: shifts, then the refresh values as written
     current_values   refreshed entries <- B's values at M2; every other entry <- the retained value shifted by each
                      recorded delta in order
     summed_shift     as current_values, but one shift by the sum of the deltas (are intermediate shifts needed?)
     last_written     refreshed entries <- their last written value, without the shifts that followed it
     patches_only     refreshed entries <- B's values at M2; no shifts for the others
   Positions: B's Sink positions at M2 (metadata) in every candidate.
Reports bytes (fresh base vs each candidate's update), GPU apply time, the host -> GPU time of the retained Sink, the
interval's event counts, and B's per-call tracking cost.

    python tools/eval/m2_reuse_probe.py --c0 31 --M1 64 --interval 60
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

OUT = ROOT / "results/evaluation/osdi/m1_continuity"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--c0", type=int, default=31); ap.add_argument("--M1", type=int, default=64); ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--video", default="examples/original.mp4"); ap.add_argument("--prompt", default="examples/prompt.txt"); ap.add_argument("--seed", default="1")
    ap.add_argument("--post_chunks", default="400"); ap.add_argument("--gpu_id", default="0")
    ap.add_argument("--out", default=str(OUT / "e7_reuse_probe.json"))
    a = ap.parse_args()
    import m1_replay as mr
    import mobility_node as mn
    from models.wan.causal_model import _shift_temporal_rope

    margs = mn.parse_args(["--label", "E7", "--video_path", a.video, "--prompt_file_path", a.prompt, "--seed", a.seed, "--gpu_id", a.gpu_id,
                           "--migration_chunk", "30", "--post_chunks", a.post_chunks])
    rt = mn.GpuRuntime(margs)
    torch, pl, dev = rt.torch, rt.pl, rt.device
    sync = lambda: torch.cuda.synchronize(dev)  # noqa: E731
    S, fsl = rt.sink, rt.fsl
    M1, M2 = a.M1, a.M1 + a.interval
    freqs = pl.generator.model.freqs.to(dev)
    sl = lambda s_: slice(s_ * fsl, (s_ + 1) * fsl)  # noqa: E731
    rec = mr.Recorder(torch, pl, S, dev, sync, keep_slots=False)

    def step_logged(session, c, patches_out):
        rec.call, rec.active = c, True
        rt.runner.step(session, c)
        rec.call, rec.active = None, False
        e = rec.entries[c]
        pw = {}
        for li, i, s_ in e["refresh"]:
            pw[(li, i, s_)] = (pl.kv_cache1[li]["k"][i, sl(s_)].clone(), pl.kv_cache1[li]["v"][i, sl(s_)].clone())
        patches_out[c] = pw
        return e

    # ---- 1. A to M1, logging c0 .. M1-1
    session = rt.session = rt.runner.start()
    L = len(pl.kv_cache1)   # the ring exists once the session has started
    for c in range(a.c0):
        rt.runner.step(session, c)
    sync()
    ring_c0 = mr.snapshot(pl)
    patchA = {}
    for c in range(a.c0, M1):
        step_logged(session, c, patchA)
    sync()
    A_ser = rt.serialize_live()
    # ---- 2. A's retained snapshot (host copy of the Sink and its positions at the M1 boundary)
    t0 = time.perf_counter()
    retained = {"k": [l_["k"][:, :S * fsl].to("cpu", copy=True) for l_ in pl.kv_cache1], "v": [l_["v"][:, :S * fsl].to("cpu", copy=True) for l_ in pl.kv_cache1],
                "pos": [l_["pos"][:, :S].to("cpu", copy=True) for l_ in pl.kv_cache1]}
    sync(); retain_d2h_s = time.perf_counter() - t0
    retained_bytes = sum(t.numel() * t.element_size() for t in retained["k"] + retained["v"])
    ckA = rt.sink_checksums(); ckA.pop("s")
    # ---- 3. B = E5's destination at M1
    mr.restore(pl, ring_c0, S, zero_recent=True)
    for b in pl.generator.model.blocks:
        b.self_attn.adapt_sink_thr = -1
    for c in range(a.c0, M1):
        mr.replay(torch, pl, rec, [c], -1, sync)
        for (li, i, s_), (k_, v_) in patchA[c].items():
            pl.kv_cache1[li]["k"][i, sl(s_)] = k_; pl.kv_cache1[li]["v"][i, sl(s_)] = v_
    sync()
    ckB1 = rt.sink_checksums(); ckB1.pop("s")
    B_equal_A_at_M1 = ckB1 == ckA
    kv_keep = ([l_["k"].clone() for l_ in pl.kv_cache1], [l_["v"].clone() for l_ in pl.kv_cache1])
    rt.sa.restore_state(pl, rt.pm, session, A_ser, {"meta", "inflight"})   # the fast path: in-flight + metadata (zeroes the ring)
    for l_, k_, v_ in zip(pl.kv_cache1, *kv_keep):
        l_["k"].copy_(k_); l_["v"].copy_(v_)
    del kv_keep, A_ser
    rt.unfreeze_refresh()
    sync()
    # ---- 4. B generates M1 .. M2-1; record every Sink event
    events = []   # per call: {"call", "shifts": [(li, b, s, delta)], "writes": {(li, b, s): (k, v)}}
    patchB, step_s, track_s = {}, [], []
    for c in range(M1, M2):
        t0 = time.perf_counter()
        e = step_logged(session, c, patchB)
        sync(); step_s.append(time.perf_counter() - t0)
        t1 = time.perf_counter()
        shifts = []
        for li, rows in enumerate(e["written"]):
            pre, post = e["pre"]["pos"][li].tolist(), e["post"]["pos"][li].tolist()
            for b, w in enumerate(rows):
                for s_ in range(S):
                    if w != s_ and post[b][s_] != pre[b][s_]:
                        shifts.append((li, b, s_, int(post[b][s_] - pre[b][s_])))
        track_s.append(time.perf_counter() - t1)
        events.append({"call": c, "shifts": shifts, "writes": patchB[c]})
    sync()
    B2 = {"k": [l_["k"][:, :S * fsl].clone() for l_ in pl.kv_cache1], "v": [l_["v"][:, :S * fsl].clone() for l_ in pl.kv_cache1],
          "pos": [l_["pos"][:, :S].clone() for l_ in pl.kv_cache1]}
    ckB2 = rt.sink_checksums(); ckB2.pop("s")
    refreshed = {}
    for ev in events:
        for key in ev["writes"]:
            refreshed[key] = ev["call"]   # last write
    n_writes = sum(len(ev["writes"]) for ev in events)
    shift_calls = sorted({ev["call"] for ev in events if ev["shifts"]})
    shifted_entries = {(li, b, s_) for ev in events for li, b, s_, _ in ev["shifts"]}
    # blocks of B's Sink that differ from the retained one (what a version diff would have to account for)
    diff_blocks = sum(1 for li in range(L) for key in ("k", "v") for b in range(B2[key][li].shape[0]) for s_ in range(S)
                      if not torch.equal(B2[key][li][b, sl(s_)], retained[key][li][b, sl(s_)].to(dev)))

    # ---- 5. reconstructions from the retained Sink
    def load_retained() -> float:
        sync(); t0 = time.perf_counter()
        for li, l_ in enumerate(pl.kv_cache1):
            l_["k"][:, :S * fsl].copy_(retained["k"][li], non_blocking=False); l_["v"][:, :S * fsl].copy_(retained["v"][li], non_blocking=False)
            l_["pos"][:, :S].copy_(B2["pos"][li])   # positions at M2 (metadata)
        sync(); return time.perf_counter() - t0

    def rot(li, b, s_, delta):
        k = pl.kv_cache1[li]["k"]
        k[b, sl(s_)] = _shift_temporal_rope(k[b, sl(s_)], freqs, delta)

    def compare(name, t_apply, h2d, nbytes, n_items):
        ck = rt.sink_checksums(); ck.pop("s")
        bad = [[li, key, b, s_] for li in range(L) for key in ("k", "v") for b in range(B2[key][li].shape[0]) for s_ in range(S)
               if not torch.equal(pl.kv_cache1[li][key][b, sl(s_)], B2[key][li][b, sl(s_)])]
        return {"strategy": name, "digest_equal": ck == ckB2, "blocks_equal": 2 * L * B2["k"][0].shape[0] * S - len(bad), "blocks_total": 2 * L * B2["k"][0].shape[0] * S,
                "mismatched_blocks": bad[:30], "n_mismatched": len(bad), "apply_s": t_apply, "retained_h2d_s": h2d, "update_bytes": nbytes, "update_items": n_items}

    blk = B2["k"][0][0, sl(0)].numel() * B2["k"][0].element_size()   # one (row, slot) K or V block
    meta_bytes = sum(t.numel() * 8 for t in B2["pos"])                 # Sink positions at M2
    res_strat = []
    # ordered
    h2d = load_retained(); sync(); t0 = time.perf_counter()
    for ev in events:
        for li, b, s_, d in ev["shifts"]:
            rot(li, b, s_, d)
        for (li, b, s_), (k_, v_) in ev["writes"].items():
            pl.kv_cache1[li]["k"][b, sl(s_)] = k_; pl.kv_cache1[li]["v"][b, sl(s_)] = v_
    sync()
    n_shift_ev = sum(len(ev["shifts"]) for ev in events)
    res_strat.append(compare("ordered", time.perf_counter() - t0, h2d, n_writes * 2 * blk + meta_bytes + 16 * n_shift_ev, {"writes": n_writes, "shift_events": n_shift_ev}))

    def current_values(shift_mode: str, refreshed_mode: str):
        h2d = load_retained(); sync(); t0 = time.perf_counter()
        for li in range(L):
            for b in range(B2["k"][li].shape[0]):
                for s_ in range(S):
                    key = (li, b, s_)
                    if key in refreshed:
                        if refreshed_mode == "current":
                            pl.kv_cache1[li]["k"][b, sl(s_)] = B2["k"][li][b, sl(s_)]; pl.kv_cache1[li]["v"][b, sl(s_)] = B2["v"][li][b, sl(s_)]
                        else:   # last written value, no later shifts
                            k_, v_ = patchB[refreshed[key]][key]
                            pl.kv_cache1[li]["k"][b, sl(s_)] = k_; pl.kv_cache1[li]["v"][b, sl(s_)] = v_
                        continue
                    ds = [d for ev in events for (l2, b2, s2, d) in ev["shifts"] if (l2, b2, s2) == key]
                    if not ds or shift_mode == "none":
                        continue
                    if shift_mode == "sequence":
                        for d in ds:
                            rot(li, b, s_, d)
                    else:
                        rot(li, b, s_, sum(ds))
        sync()
        return h2d, time.perf_counter() - t0
    for name, sm, rm in (("current_values", "sequence", "current"), ("summed_shift", "sum", "current"), ("last_written", "sequence", "last"), ("patches_only", "none", "current")):
        h2d, t_apply = current_values(sm, rm)
        n_ent = len(refreshed)
        res_strat.append(compare(name, t_apply, h2d, n_ent * 2 * blk + meta_bytes + (0 if sm == "none" else 16 * n_shift_ev), {"refreshed_entries": n_ent}))
    sink_base_bytes = int(rt.pack(rt.serialize_live(), "sink")[0]["nbytes"])
    res = {"host": platform.node(), "gpu": torch.cuda.get_device_name(dev), "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
           "workload": {"video": a.video, "seed": a.seed}, "c0": a.c0, "M1": M1, "M2": M2, "interval_calls": a.interval,
           "B_built_as_E5_destination": {"sink_digest_equal_A_at_M1": B_equal_A_at_M1},
           "retained": {"bytes": retained_bytes, "where": "host memory (CPU copy at the M1 boundary)", "d2h_s": retain_d2h_s},
           "interval": {"refresh_writes": n_writes, "refreshed_entries_distinct": len(refreshed), "refresh_calls": sorted({ev["call"] for ev in events if ev["writes"]}),
                        "shift_calls": shift_calls, "shift_events": n_shift_ev, "shifted_entries": len(shifted_entries),
                        "refreshed_and_shifted_entries": len(shifted_entries & set(refreshed)), "blocks_differing_from_retained": diff_blocks,
                        "B_step_s_median": float(sorted(step_s)[len(step_s) // 2]), "tracking_s_median": float(sorted(track_s)[len(track_s) // 2])},
           "block_bytes": blk, "fresh_sink_base_bytes": sink_base_bytes, "strategies": res_strat}
    Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("B_built_as_E5_destination", "retained", "interval", "fresh_sink_base_bytes")}, indent=1, default=str))
    for r_ in res_strat:
        print(r_["strategy"], "digest_equal", r_["digest_equal"], "blocks", r_["blocks_equal"], "/", r_["blocks_total"], "bytes", r_["update_bytes"], "apply_s", round(r_["apply_s"], 4), "h2d", round(r_["retained_h2d_s"], 3))


if __name__ == "__main__":
    main()
