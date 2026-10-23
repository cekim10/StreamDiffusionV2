#!/usr/bin/env python3
"""Experiment VD precheck (osdi/expVD/preregistration.md section 2): measured attention dilution and the masked
kernel's correctness, on one GPU, before the factorial. A mechanism check, not a visual one.

On a Sink-less session (the input's OT-1 move call: the session generates calls 0 .. M - 1, then an M1 reset exactly
as vc_emulate does), for 4 calls, every attention block's KV-cache attention is probed (models/wan/causal_model.py
ATTN_PROBE; the frozen attention itself is untouched):
  mass     softmax probability on the zero-filled sink slots, per block and Stream-Batch row, averaged over heads and a
           fixed subsample of 256 queries (float32 logits q k^T / sqrt(d) over the cache prefix the kernel reads)
  equiv    on the first probed call of every block: the masked kernel call (cache after the sink slots, cache_seqlens -
           sink_tokens) vs scaled_dot_product_attention over the whole prefix with an explicit boolean mask that
           excludes the sink slots; max |difference|
  zero     the sink region of the cache is exactly zero (what masking assumes)

    python tools/eval/vd_precheck.py --input dog --gpu_id 0      # -> results/evaluation/osdi/expVD/vd_precheck.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

from rd_emulate import payload_of  # noqa: E402

SCHED = ROOT / "results/evaluation/osdi/expVC/vc_schedules.json"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default="dog")
    ap.add_argument("--gpu_id", type=int, default=0)
    ap.add_argument("--calls", type=int, default=4)
    ap.add_argument("--loveu_dir", default=None)
    ap.add_argument("--out", default=str(ROOT / "results/evaluation/osdi/expVD/vd_precheck.json"))
    a = ap.parse_args()
    import torch
    import torch.nn.functional as F

    import models.wan.causal_model as cm
    import mobility_node as mn
    from expw_w1 import workload_paths

    ot1 = next(c for c in json.loads(SCHED.read_text())["inputs"][a.input]["conditions"] if c["id"] == "OT-1")
    M = ot1["resets"][0]
    video, prompt = workload_paths(a.input, a.loveu_dir)
    margs = mn.parse_args(["--label", "VD", "--video_path", str(video), "--prompt_file_path", str(prompt), "--seed", "0", "--gpu_id", str(a.gpu_id),
                           "--migration_chunk", "0", "--post_chunks", str(M + a.calls + 2)])
    rt = mn.GpuRuntime(margs)
    rt.base = {}
    rt.session = rt.runner.start()
    for c in range(M):
        rt.step(c)
    # M1 reset at the move call (the vc_emulate / rd_emulate operation, without packing the Sink)
    snap = rt.serialize_live()
    fast = [(dict(h), payload_of(h, bufs)) for h, bufs in [rt.pack(snap, comp) for comp in ("inflight", "meta")]]
    del snap
    rt.release(); rt.provision()
    for h, pl in fast:
        rt.unpack(dict(h), pl)
    rt.restore_fast()

    blocks = list(rt.pl.generator.model.blocks)
    index = {id(b.self_attn): i for i, b in enumerate(blocks)}
    rec = {"mass": [], "equiv": {}, "sink_zero": []}
    state = {"call": None}

    def probe(mod, q, k_cache, v_cache, seq_lens, sink_tokens):
        li = index.get(id(mod))
        if li is None:
            return
        with torch.no_grad():
            B, Lq, H, D = q.shape
            stride = max(1, Lq // 256)
            for b in range(B):
                n = int(seq_lens[b].item())
                if n <= sink_tokens:
                    continue
                qs = q[b, ::stride].float()
                kk = k_cache[b, :n].float()
                p = torch.softmax(torch.einsum("qhd,khd->hqk", qs, kk) / math.sqrt(D), dim=-1)
                rec["mass"].append({"block": li, "call": state["call"], "row": b, "mass": float(p[..., :sink_tokens].sum(-1).mean().item())})
                rec["sink_zero"].append(bool(k_cache[b, :sink_tokens].abs().amax().item() == 0 and v_cache[b, :sink_tokens].abs().amax().item() == 0))
                if li not in rec["equiv"] and b == 0:
                    qb, kb, vb = q[b:b + 1], k_cache[b:b + 1, :n], v_cache[b:b + 1, :n]
                    if cm.FLASH_ATTN_AVAILABLE:
                        x1 = cm.flash_attn_interface.flash_attn_with_kvcache(q=qb, k_cache=kb[:, sink_tokens:].contiguous(), v_cache=vb[:, sink_tokens:].contiguous(),
                                                                             cache_seqlens=torch.tensor([n - sink_tokens], dtype=torch.int32, device=q.device))
                        if isinstance(x1, tuple):
                            x1 = x1[0]
                        kernel = "flash_attn_with_kvcache"
                    else:
                        x1 = cm.attention_with_kvcache_fallback(q=qb, k_cache=kb[:, sink_tokens:], v_cache=vb[:, sink_tokens:],
                                                                cache_seqlens=torch.tensor([n - sink_tokens], dtype=torch.int32, device=q.device))
                        kernel = "sdpa_fallback"
                    mask = torch.ones(1, 1, Lq, n, dtype=torch.bool, device=q.device); mask[..., :sink_tokens] = False
                    x2 = F.scaled_dot_product_attention(qb.transpose(1, 2), kb.transpose(1, 2), vb.transpose(1, 2), attn_mask=mask).transpose(1, 2)
                    rec["equiv"][li] = {"kernel": kernel, "max_abs_diff": float((x1.float() - x2.float()).abs().max().item()),
                                        "ref_max_abs": float(x2.float().abs().max().item())}

    cm.ATTN_PROBE = probe
    t0 = time.time()
    try:
        for c in range(M, M + a.calls):
            state["call"] = c
            rt.step(c)
    finally:
        cm.ATTN_PROBE = None
    by_block = {}
    for r in rec["mass"]:
        by_block.setdefault(r["block"], []).append(r["mass"])
    per_block = {b: {"median": st.median(v), "max": max(v), "n": len(v)} for b, v in sorted(by_block.items())}
    allm = [r["mass"] for r in rec["mass"]]
    eq = list(rec["equiv"].values())
    out = {"input": a.input, "move_call": M, "probed_calls": [M, M + a.calls - 1], "flash_attn": bool(cm.FLASH_ATTN_AVAILABLE),
           "mass_on_zero_sink_slots": {"median": st.median(allm) if allm else None, "max": max(allm) if allm else None,
                                       "blocks_with_median_ge_0.01": sum(1 for v in per_block.values() if v["median"] >= 0.01), "n_blocks": len(per_block), "per_block": per_block},
           "masked_kernel_equivalence": {"blocks": len(eq), "max_abs_diff": max((e["max_abs_diff"] for e in eq), default=None), "kernel": eq[0]["kernel"] if eq else None,
                                         "per_block": rec["equiv"]},
           "sink_region_zero_all": all(rec["sink_zero"]) if rec["sink_zero"] else None, "elapsed_s": time.time() - t0,
           "reading": "if the median mass is below 0.01 in every block, masking cannot matter (VD-H1 expected to fail); the factorial runs regardless"}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k not in ("masked_kernel_equivalence",)} | {"equiv_max_abs_diff": out["masked_kernel_equivalence"]["max_abs_diff"]}, default=float)[:1500])


if __name__ == "__main__":
    main()
