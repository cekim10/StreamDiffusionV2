#!/usr/bin/env python3
"""Why is ~730 MB of the Sink dirty at the E3 switchover? (osdi/m1_continuity/e4_plan.md)

Reproduces the E3 replay run's Sink deterministically in one process (same workload, seed, call boundaries and
fragment size: base boundary c0, switch call M, 4 MiB fragments of the exact `pack_component("sink")` serialization),
records every call's cache decisions in between (refresh = a write into a Sink slot; realignment = a position shift
of an unwritten Sink slot), and attributes every changed byte range of the Sink serialization:

  refresh        the (layer, row, slot) entry received newly generated K / V in [c0, M) (whether or not it was
                 realigned afterwards); V or K changed
  realign_only   not refreshed; only K changed, and the source's sequence of RoPE shifts applied to the c0 value
                 reproduces the M value bitwise
  other          any other change (V changed without a refresh, K changed without a shift, or a shift that does not
                 reproduce bitwise)
  position       the int64 Sink position table inside the serialization (metadata)

Fragments are counted once, under the highest-priority category among the changed ranges they overlap
(refresh > other > realign_only > position). The same process then runs the E3 destination's log-only replay
(ring at c0 with the recent slots zeroed, calls c0 .. M-1, forced decisions) and checks per block whether the
destination's Sink equals the source's bitwise. The E3 final dirty bytes are reconciled against the reproduction.

    python tools/eval/m1_sink_dirty.py --c0 31 --M 64 --e3_final_bytes 730191056 --e3_dr2_bytes 399360
"""

from __future__ import annotations

import argparse
import hashlib
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
PRIO = ("refresh", "other", "realign_only", "position")


def contiguous(header, bufs) -> bytearray:
    buf = bytearray(header["nbytes"]); mv = memoryview(buf)
    for t, b in zip(header["tensors"], bufs):
        mv[t["offset"]:t["offset"] + t["nbytes"]] = memoryview(b).cast("B")
    return buf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--c0", type=int, default=31); ap.add_argument("--M", type=int, default=64)
    ap.add_argument("--frag_bytes", type=int, default=4 << 20)
    ap.add_argument("--video", default="examples/original.mp4"); ap.add_argument("--prompt", default="examples/prompt.txt"); ap.add_argument("--seed", default="1")
    ap.add_argument("--post_chunks", default="1500"); ap.add_argument("--gpu_id", default="0")
    ap.add_argument("--e3_final_bytes", type=int, default=730191056); ap.add_argument("--e3_dr2_bytes", type=int, default=399360)
    ap.add_argument("--out", default=str(OUT / "e4_sink_dirty.json"))
    a = ap.parse_args()
    import numpy as np

    import m1_replay as mr
    import mobility_node as mn
    from models.wan.causal_model import _shift_temporal_rope
    from mobility_node import frag_table

    margs = mn.parse_args(["--label", "E4", "--video_path", a.video, "--prompt_file_path", a.prompt, "--seed", a.seed, "--gpu_id", a.gpu_id,
                           "--migration_chunk", "30", "--post_chunks", a.post_chunks])
    rt = mn.GpuRuntime(margs)
    torch, pl, dev = rt.torch, rt.pl, rt.device
    sync = lambda: torch.cuda.synchronize(dev)  # noqa: E731
    S, fsl = rt.sink, rt.fsl
    rec = mr.Recorder(torch, pl, S, dev, sync, keep_slots=False)
    session = rt.session = rt.runner.start()   # serialize_live reads the runtime's session
    for c in range(a.c0):
        rt.runner.step(session, c)
    sync()
    ser0 = rt.serialize_live()
    h0, b0 = rt.pack(ser0, "sink"); B0 = contiguous(h0, b0); del b0, ser0
    ring0 = mr.snapshot(pl)
    for c in range(a.c0, a.M):
        rec.call, rec.active = c, True
        rt.runner.step(session, c)
    rec.call, rec.active = None, False
    sync()
    serM = rt.serialize_live()
    hM, bM = rt.pack(serM, "sink"); BM = contiguous(hM, bM); del bM
    small = {comp: int(rt.pack(serM, comp)[0]["nbytes"]) for comp in ("inflight", "meta")}
    del serM
    ringM = mr.snapshot(pl)
    assert [t["name"] for t in h0["tensors"]] == [t["name"] for t in hM["tensors"]] and h0["nbytes"] == hM["nbytes"]

    # ---- decisions per (layer, row, slot): refresh calls, realignment shifts (in order)
    hist = {}   # (li, b, s) -> {"refresh": [calls], "shifts": [(call, delta)]}
    for c in range(a.c0, a.M):
        e = rec.entries[c]
        for li, rows in enumerate(e["written"]):
            pre, post = e["pre"]["pos"][li].tolist(), e["post"]["pos"][li].tolist()
            for b, w in enumerate(rows):
                for s in range(S):
                    h = hist.setdefault((li, b, s), {"refresh": [], "shifts": []})
                    if w == s:
                        h["refresh"].append(c)
                    elif post[b][s] != pre[b][s]:
                        h["shifts"].append((c, int(post[b][s] - pre[b][s])))
    # ---- changed byte ranges of the serialization, attributed per block part
    T = {t["name"]: t for t in hM["tensors"]}
    blk = fsl * T["kv/0/k"]["shape"][2] * T["kv/0/k"]["shape"][3] * 2   # bytes of one (row, slot) block of K or V
    rows_n = T["kv/0/k"]["shape"][0]
    freqs = pl.generator.model.freqs.to(dev)
    v0, vM = memoryview(B0), memoryview(BM)
    ranges = []   # (lo, hi, category, detail)
    blocks = {"refresh": 0, "other": 0, "realign_only": 0, "unchanged": 0}
    block_bytes = {k: 0 for k in blocks}
    refreshed_then_shifted = 0
    n_layers = len(pl.kv_cache1)
    for li in range(n_layers):
        for part in ("k", "v"):
            t = T[f"kv/{li}/{part}"]
            for b in range(rows_n):
                for s in range(S):
                    lo = t["offset"] + (b * S + s) * blk; hi = lo + blk
                    if v0[lo:hi] == vM[lo:hi]:
                        blocks["unchanged"] += 1; block_bytes["unchanged"] += blk; continue
                    h = hist[(li, b, s)]
                    if h["refresh"]:
                        cat = "refresh"
                        if part == "k" and any(c_ > h["refresh"][0] for c_, _ in h["shifts"]):
                            refreshed_then_shifted += 1
                    elif part == "k" and h["shifts"]:
                        k0 = ring0["k"][li][b, s * fsl:(s + 1) * fsl].to(dev)
                        for _, d in h["shifts"]:
                            k0 = _shift_temporal_rope(k0, freqs, d)
                        cat = "realign_only" if torch.equal(k0, ringM["k"][li][b, s * fsl:(s + 1) * fsl].to(dev)) else "other"
                    else:
                        cat = "other"
                    blocks[cat] += 1; block_bytes[cat] += blk
                    ranges.append((lo, hi, cat, [li, part, b, s]))
        t = T[f"ring/{li}/pos_sink"]
        if v0[t["offset"]:t["offset"] + t["nbytes"]] != vM[t["offset"]:t["offset"] + t["nbytes"]]:
            ranges.append((t["offset"], t["offset"] + t["nbytes"], "position", [li]))
    covered = sum(hi - lo for lo, hi, _, _ in ranges)
    diff_bytes_total = int(np.count_nonzero(np.frombuffer(B0, np.uint8) != np.frombuffer(BM, np.uint8)))
    # ---- fragments (E3: 4 MiB slices of the serialization; dirty = hash differs), one category each
    frags = frag_table(len(BM), a.frag_bytes)
    fr_cat = {k: {"fragments": 0, "bytes": 0} for k in PRIO}
    dirty_frag_bytes, dirty_frags, unexplained = 0, 0, 0
    ranges.sort()
    for f in frags:
        lo, hi = f["off"], f["off"] + f["len"]
        if hashlib.sha256(v0[lo:hi]).digest() == hashlib.sha256(vM[lo:hi]).digest():
            continue
        dirty_frags += 1; dirty_frag_bytes += f["len"]
        cats = {c_ for r_lo, r_hi, c_, _ in ranges if r_lo < hi and r_hi > lo}
        if not cats:
            unexplained += 1; cats = {"other"}
        top = next(c_ for c_ in PRIO if c_ in cats)
        fr_cat[top]["fragments"] += 1; fr_cat[top]["bytes"] += f["len"]
    # ---- the E3 destination's log-only replay: does its Sink equal the source's, per category?
    rec_entries = rec.entries
    mr.restore(pl, ring0, S, zero_recent=True)
    rows_r, _ = mr.replay(torch, pl, rec, list(range(a.c0, a.M)), -1, sync)
    meta_ok = all(not r_["meta_diff"] for r_ in rows_r)
    repro = {k: {"blocks": 0, "bitwise": 0, "rel_err_max": 0.0} for k in ("refresh", "other", "realign_only")}
    for lo, hi, cat, det in ranges:
        if cat == "position":
            continue
        li, part, b, s = det
        live = pl.kv_cache1[li][part][b, s * fsl:(s + 1) * fsl]
        ref = ringM[part][li][b, s * fsl:(s + 1) * fsl].to(dev)
        eq = bool(torch.equal(live, ref))
        d = (live.float() - ref.float())
        rel = float((d * d).sum().sqrt() / (ref.float() ** 2).sum().sqrt())
        repro[cat]["blocks"] += 1; repro[cat]["bitwise"] += eq; repro[cat]["rel_err_max"] = max(repro[cat]["rel_err_max"], rel)
    pos_equal = all(torch.equal(l_["pos"][:, :S], ringM["meta"]["pos"][li][:, :S]) for li, l_ in enumerate(pl.kv_cache1))
    # ---- refresh entries by call (what per-call exact patches would send, and what would remain at the switch)
    ref_calls = sorted(c_ for h in hist.values() for c_ in h["refresh"])
    e3_dirty = a.e3_final_bytes - a.e3_dr2_bytes - small["inflight"] - small["meta"]
    res = {"host": platform.node(), "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
           "c0": a.c0, "M": a.M, "frag_bytes": a.frag_bytes, "sink_bytes": len(BM), "n_fragments": len(frags), "block_bytes": blk,
           "reproduction": {"dirty_fragments": dirty_frags, "dirty_fragment_bytes": dirty_frag_bytes, "e3_sink_dirty_bytes": e3_dirty, "matches_e3": dirty_frag_bytes == e3_dirty,
                            "inflight_bytes": small["inflight"], "meta_bytes": small["meta"]},
           "changed_bytes": {"in_changed_ranges": covered, "bytes_that_differ": diff_bytes_total},
           "fragments_by_category": fr_cat, "fragments_unexplained": unexplained,
           "blocks_by_category": blocks, "block_bytes_by_category": block_bytes, "refresh_blocks_later_realigned_K": refreshed_then_shifted,
           "refresh_events": {"n": len(ref_calls), "entries_layer_row_slot": sum(1 for h in hist.values() if h["refresh"]), "by_call": {str(c_): ref_calls.count(c_) for c_ in sorted(set(ref_calls))}},
           "realign_calls": sorted({c_ for h in hist.values() for c_, _ in h["shifts"]}),
           "replay_reproduction": {"metadata_equal_every_call": meta_ok, "sink_positions_equal_at_M": pos_equal, "by_category": repro}}
    Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("reproduction", "fragments_by_category", "blocks_by_category", "refresh_events", "realign_calls", "replay_reproduction")}, indent=1, default=str))


if __name__ == "__main__":
    main()
