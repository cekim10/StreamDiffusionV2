#!/usr/bin/env python3
"""CPU test of tools/eval/m1_replay.py with a tiny real CausalWanModel (models/wan/causal_model.py; SDPA fallback) and a
source loop with the same Stream-Batch / t_refresh semantics as inference_stream + run_stream_batch. Checks: E0 passes
bitwise over a window that contains adaptive refreshes and a t_refresh realignment; E1 keeps the metadata equal and
layer 0 bitwise; tampering with one recorded input, or dropping the refresh decisions, makes E0 fail.

    python tools/eval/test_m1_replay.py
"""

from __future__ import annotations

import sys
import types
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

import torch  # noqa: E402

warnings.filterwarnings("ignore")
import m1_replay as mr  # noqa: E402
from models.wan import causal_model as cm  # noqa: E402

B, C, H, W, HEADS, LAYERS, SINK, SLOTS, T_REFRESH, TEXT = 2, 4, 4, 4, 2, 3, 3, 6, 30, 8
FSL = (H // 2) * (W // 2)
M = 40           # window 28 .. 40 contains the t_refresh rewind at call 30
DT = torch.bfloat16


class Gen(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, noisy_image_or_video, conditional_dict, timestep, kv_cache=None, crossattn_cache=None, current_start=None, current_end=None):
        return self.model(noisy_image_or_video.permute(0, 2, 1, 3, 4), t=timestep, context=conditional_dict["prompt_embeds"], seq_len=FSL,
                          kv_cache=kv_cache, crossattn_cache=crossattn_cache, current_start=current_start, current_end=current_end).permute(0, 2, 1, 3, 4)


def build_model():
    torch.manual_seed(0)
    m = cm.CausalWanModel(model_type="t2v", patch_size=(1, 2, 2), text_len=TEXT, in_dim=C, dim=HEADS * 128, ffn_dim=256, freq_dim=32,
                          text_dim=16, out_dim=C, num_heads=HEADS, num_layers=LAYERS)
    g = torch.Generator().manual_seed(1)
    for p in m.parameters():
        p.data = (torch.randn(p.shape, generator=g) * 0.05).to(p.dtype)
    return Gen(m.to(DT).eval())


def fresh_stream(gen, thr: float):
    """A new session: empty ring, fresh eviction queues, and a step(c) with inference_stream's semantics."""
    pl = types.SimpleNamespace(generator=gen, frame_seq_length=FSL)
    pl.kv_cache1 = [{"k": torch.zeros(B, SLOTS * FSL, HEADS, 128, dtype=DT), "v": torch.zeros(B, SLOTS * FSL, HEADS, 128, dtype=DT),
                     "global_end_index": torch.zeros(B, dtype=torch.long), "local_end_index": torch.zeros(B, dtype=torch.long),
                     "pos": torch.full((B, SLOTS), cm.KV_POS_EMPTY, dtype=torch.long), "total_steps": B, "current_step": B} for _ in range(LAYERS)]
    pl.crossattn_cache = [{"k": torch.zeros(B, TEXT, HEADS, 128, dtype=DT), "v": torch.zeros(B, TEXT, HEADS, 128, dtype=DT), "is_init": False} for _ in range(LAYERS)]
    pl.conditional_dict = {"prompt_embeds": torch.randn(B, TEXT, 16, generator=torch.Generator().manual_seed(2)).to(DT)}
    for b in gen.model.blocks:
        b.self_attn.evict_idx = None
        b.self_attn.sink_size = SINK
        b.self_attn.adapt_sink_thr = thr
    st = {"hs": torch.zeros(B, 1, C, H, W, dtype=DT), "starts": torch.zeros(B, dtype=torch.long), "ends": torch.full((B,), FSL, dtype=torch.long), "cur": 0,
          "ts": torch.tensor([[700], [350]], dtype=torch.long)}

    def step(c: int):
        if st["cur"] // FSL >= T_REFRESH:
            st["cur"] = SLOTS * FSL - FSL
        g = torch.Generator().manual_seed(1000 + c)
        hs = st["hs"]
        hs[1:] = hs[:-1].clone(); hs[0] = torch.randn(1, C, H, W, generator=g).to(DT)
        st["starts"][1:] = st["starts"][:-1].clone(); st["starts"][0] = st["cur"]
        st["ends"][1:] = st["ends"][:-1].clone(); st["ends"][0] = st["cur"] + FSL
        out = pl.generator(noisy_image_or_video=hs, conditional_dict=pl.conditional_dict, timestep=st["ts"].expand(-1, 1), kv_cache=pl.kv_cache1,
                           crossattn_cache=pl.crossattn_cache, current_start=st["starts"], current_end=st["ends"])
        out = out.clone(); out[0] = (0.6 * out[0].float() + 0.4 * torch.randn(1, C, H, W, generator=g)).to(DT)
        st["hs"] = out
        st["cur"] += FSL
    return pl, step


def main():
    fails = []

    def check(name, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")
        if not ok:
            fails.append(name)

    gen = build_model()
    noop = lambda: None
    # pick a refresh threshold that gives some (not all) refreshes in the window
    thr = None
    for cand in (0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95):
        pl, step = fresh_stream(gen, cand)
        for c in range(M + 1):
            step(c)
        pos = [l_["pos"].clone() for l_ in pl.kv_cache1]
        pl, step = fresh_stream(gen, cand)
        rec = mr.Recorder(torch, pl, SINK, "cpu", noop)
        rec.reset(); rec.call = None
        n_ref = 0
        for c in range(M + 1):
            rec.call, rec.active = c, c >= M - mr.WINDOW
            step(c)
        n_ref = sum(len(rec.entries[c]["refresh"]) for c in range(M - mr.WINDOW, M))
        pl.generator.forward = rec.orig
        if 0 < n_ref < (mr.WINDOW * LAYERS * B) // 2:
            thr = cand
            break
    check("threshold with partial refreshes in the window", thr is not None, f"thr={thr} refreshes={n_ref}")
    if thr is None:
        sys.exit(1)

    def run(tamper=None):
        pl, step = fresh_stream(gen, thr)
        rec = mr.Recorder(torch, pl, SINK, "cpu", noop)
        orig_replay = mr.replay
        if tamper is not None:
            def replay_t(torch_, pl_, rec_, calls, cfg, sync, on_call=None):
                tamper(rec_)
                return orig_replay(torch_, pl_, rec_, calls, cfg, sync, on_call)
            mr.replay = replay_t
        try:
            r = mr.run_cell(torch, pl, rec, step, M, SINK, thr, "cpu", noop)
        finally:
            mr.replay = orig_replay
            pl.generator.forward = rec.orig
        return r, rec

    r, rec = run()
    realigned = any(int(rec.entries[c]["s"][0]) // FSL == SLOTS - 1 for c in range(M - mr.WINDOW, M))
    check("window contains a t_refresh rewind", realigned)
    check("E0 pass (ring bitwise, metadata, written slots, call-M output)", r["E0"]["pass"],
          f"ring {r['E0']['ring_at_M']['bitwise']} meta {r['E0']['ring_at_M']['meta_diff'][:2]} out {r['E0']['call_M']['bitwise']}")
    check("E0 per-call slot error 0", all(c["slot_rel_k"] == 0 and c["slot_rel_v"] == 0 for c in r["E0"]["calls"]))
    for w in mr.E1_W:
        e = r["E1"][str(w)]
        check(f"E1 w={w} metadata equal on every call", e["meta_equal_all"])
        if w >= 6:   # w = 3: a refresh among the last 3 calls leaves one recent slot unwritten (zero)
            check(f"E1 w={w} layer 0 recent bitwise", e["ring_at_M"]["layer0_recent_bitwise"])
    e0 = r["E1"]["0"]["ring_at_M"]["recent_rel"]
    check("E1 w=0 recent error is 1 (zeroed)", abs(e0["k"] - 1) < 1e-6 and abs(e0["v"] - 1) < 1e-6, str(e0))
    errs = [r["E1"][str(w)]["ring_at_M"]["recent_rel"]["k"] for w in mr.E1_W]
    check("E1 recent K error finite and below w=0 for w>=3", all(x == x for x in errs) and all(x < errs[0] for x in errs[1:]), str([round(x, 4) for x in errs]))
    print("    E1 call-M out rel (row 1):", [round(r["E1"][str(w)]["call_M"]["rel_per_row"][-1], 4) for w in mr.E1_W])
    print("    E1 w=12 trajectory K:", [round(c["slot_rel_k"], 3) for c in r["E1"]["12"]["calls"]])
    check("log bytes per call = inputs + t + starts/ends + decisions", r["source"]["log_bytes_per_call"] > 0, str(r["source"]["log_bytes_per_call"]))

    def bump(rec_):
        e = rec_.entries[M - 5]
        e["x"] = e["x"].clone(); e["x"][0, 0, 0, 0, 0] += 0.5
    r2, _ = run(bump)
    check("negative: a tampered input makes E0 fail", not r2["E0"]["pass"])

    def drop(rec_):
        for c in rec_.entries:
            rec_.entries[c]["refresh"] = []
    r3, _ = run(drop)
    check("negative: dropped refresh decisions make E0 fail", not r3["E0"]["pass"], f"meta diffs {sum(bool(c['meta_diff']) for c in r3['E0']['calls'])}")

    # aggregation on a synthetic unit file built from this cell
    import json, tempfile
    d = Path(tempfile.mkdtemp())
    (d / "dog_s1.json").write_text(json.dumps({"unit": "dog_s1", "determinism": {"calls_compared": 35, "inputs_equal": True}, "cells": {"OT-1": r, "OT-L": r}}, default=str))
    A = mr.aggregate(d)
    check("aggregate", A["cells"] == 2 and A["e0_pass"] == 2 and (d / "e0e1_results.md").exists())
    print("ALL PASS" if not fails else f"FAILED: {fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
