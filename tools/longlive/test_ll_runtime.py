#!/usr/bin/env python3
"""CPU test of tools/longlive/ll_runtime.py on a tiny random LongLive model (no weights, no GPU).

Same code path as the real model (vendored CausalWanModel, FlowMatchScheduler, WanVAE_ cached decode, LongLive
config: 3-frame blocks, 4 steps, local_attn_size 12, sink 3, global_sink), with dim 32 / 2 layers, a 4 x 4 latent and
a stub text encoder. Checks: per-call determinism, a different seed differs, export / import of the full state at a
call reproduces the uninterrupted run (latents, frames and state), the sink is written by call 0 only, the window
rolls, recache and a prompt switch run, the inventory roles.

    python tools/longlive/test_ll_runtime.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ll_runtime as llr  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  [ok] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAILS.append(msg)


class StubText:
    """prompt -> fixed random embedding [1, 512, text_dim]."""

    def __init__(self, dim):
        self.dim = dim

    def __call__(self, text_prompts):
        g = torch.Generator().manual_seed(sum(map(ord, text_prompts[0])) % (2 ** 31))
        e = torch.randn([1, 512, self.dim], generator=g).to(torch.bfloat16)
        e[:, 16:] = 0
        return {"prompt_embeds": e}


def tiny_model():
    if not torch.cuda.is_available():   # the vendored t5.py evaluates torch.cuda.current_device() as a default argument
        torch.cuda.current_device = lambda: 0
    from utils.scheduler import FlowMatchScheduler
    from utils.wan_wrapper import WanDiffusionWrapper, WanVAEWrapper
    from wan.modules.causal_model import CausalWanModel
    from wan.modules.vae import WanVAE_
    if not torch.cuda.is_available():   # cross-attention calls flash_attention directly (CUDA only): use the SDPA path
        import wan.modules.model as wm
        from wan.modules.attention import attention
        wm.flash_attention = lambda q, k, v, k_lens=None, **kw: attention(q, k, v)

    cfg = OmegaConf.load(llr.DEFAULT_CFG)
    torch.manual_seed(0)
    gen = WanDiffusionWrapper.__new__(WanDiffusionWrapper)
    torch.nn.Module.__init__(gen)
    gen.model = CausalWanModel(dim=32, ffn_dim=64, freq_dim=32, text_dim=16, num_heads=2, num_layers=2,
                               local_attn_size=cfg.model_kwargs.local_attn_size, sink_size=cfg.model_kwargs.sink_size).eval()
    for p in gen.model.parameters():
        p.data.normal_(0, 0.05)
    gen.uniform_timestep = False
    gen.scheduler = FlowMatchScheduler(shift=cfg.model_kwargs.timestep_shift, sigma_min=0.0, extra_one_step=True)
    gen.scheduler.set_timesteps(1000, training=True)
    gen.seq_len = 32760
    gen.post_init()
    vae = WanVAEWrapper.__new__(WanVAEWrapper)
    torch.nn.Module.__init__(vae)
    vae.mean, vae.std = torch.zeros(16), torch.ones(16)
    vae.model = WanVAE_(dim=8, z_dim=16, dim_mult=[1, 2, 4, 4], num_res_blocks=1, attn_scales=[],
                        temperal_downsample=[False, True, True]).eval()
    for p in vae.model.parameters():
        p.data.normal_(0, 0.05)
    gen, vae = gen.to(torch.bfloat16), vae.to(torch.bfloat16)
    return llr.LLModel(cfg, "cpu", gen, StubText(16), vae, latent=(16, 4, 4))


def run(s, n):
    return [s.step() for _ in range(n - s.call)]


def lat(outs):
    return [llr.digest(o["latents"]) for o in outs]


def frm(outs):
    return [llr.digest(o["frames"]) for o in outs]


def main():
    torch.set_grad_enabled(False)
    m = tiny_model()
    P = ["a boy on a lawn", "the boy starts running"]
    print("- determinism and seeds")
    a = llr.LLSession(m, P[:1], seed=0).start()
    oa = run(a, 8)
    b = llr.LLSession(m, P[:1], seed=0).start()
    ob = run(b, 8)
    check(lat(oa) == lat(ob) and frm(oa) == frm(ob), "same seed: latents and frames equal call by call")
    check(a.checksums() == b.checksums(), "same seed: final state equal")
    c = llr.LLSession(m, P[:1], seed=1).start()
    check(lat(run(c, 2)) != lat(oa[:2]), "another seed: different latents")
    check(oa[0]["frames"].shape[0] == 9 and all(o["frames"].shape[0] == 12 for o in oa[1:]),
          f"frames per call: 9 then 12 ({[o['frames'].shape[0] for o in oa[:3]]})")
    check(oa[0]["frames"].dtype == torch.uint8 and oa[0]["frames"].shape[1:] == (32, 32, 3), f"frames uint8 [T, 32, 32, 3] {tuple(oa[0]['frames'].shape)}")

    print("- state: sink written by call 0 only, window rolls")
    s = llr.LLSession(m, P[:1], seed=0).start()
    run(s, 1)
    sink1 = s.checksums()["sink_kv"]
    run(s, 2)
    win2 = s.checksums()["window_kv"]
    run(s, 8)
    ck = s.checksums()
    check(ck["sink_kv"] == sink1, "sink K / V unchanged from call 1 to call 8 (global_sink)")
    check(ck["window_kv"] != win2, "window K / V changes")
    check(s.kv[0]["local_end_index"].item() == 12 * m.frame_seq_length, f"window full: local_end {s.kv[0]['local_end_index'].item()}")
    check(s.kv[0]["global_end_index"].item() == 24 * m.frame_seq_length, f"global_end = 24 frames {s.kv[0]['global_end_index'].item()}")
    inv = s.inventory()
    check(set(inv["_by_role"]) == set(llr.ROLES) and all(v > 0 for v in inv["_by_role"].values()), f"inventory by role {inv['_by_role']}")
    check(inv["sink_kv"]["bytes"] * 3 == inv["window_kv"]["bytes"], "sink 3 frames, window 9 frames")
    check(s.latbuf.shape[1] == 12, f"latent buffer holds 12 frames ({s.latbuf.shape[1]})")

    print("- export / import (full migration) reproduces the uninterrupted run")
    r = llr.LLSession(m, P[:1], seed=0).start()
    run(r, 5)
    snap = r.export_state()
    orr = run(r, 10)
    d = llr.LLSession(m, P[:1], seed=0).start().import_state(snap)
    od = run(d, 10)
    check(lat(od) == lat(orr) and frm(od) == frm(orr), "imported session: latents and frames equal calls 5-9")
    check(d.checksums() == r.checksums(), "imported session: final state equal")
    nov = llr.LLSession(m, P[:1], seed=0).start()
    snap2 = dict(snap, tensors={k: v for k, v in snap["tensors"].items() if k != "vae_decoder_cache"})
    nov.import_state(snap2)
    check(frm(run(nov, 10)) != frm(orr), "without the VAE decoder cache: frames differ (the cache is state)")

    print("- recache (LongLive-native reconstruction) from the sink and the latent buffer")
    rc = llr.LLSession(m, P[:1], seed=0).start()
    rc.import_state({"counters": snap["counters"], "tensors": {k: snap["tensors"][k] for k in ("sink_kv", "latent_buffer")}})
    rc.recache(); rc.warm_decoder()
    wr, wrc = snap["tensors"]["window_kv"], rc.export_state(["window_kv"])["tensors"]["window_kv"]
    same = [bool(torch.equal(x, y)) for x, y in zip(wr, wrc)]
    check(same[:2] == [True, True] and not all(same[2:]),
          f"recache window: layer 0 exact (no attention before its K / V), deeper layers differ ({same})")
    orc = run(rc, 10)
    check(len(orc) == 5 and all(torch.isfinite(o["latents"].float()).all() for o in orc), "recache path runs, finite output")
    check(rc.checksums()["sink_kv"] == r.checksums()["sink_kv"], "recache keeps the sink (global_sink)")

    print("- prompt switch")
    sw = llr.LLSession(m, P, seed=0, switch_calls=[5]).start()
    osw = run(sw, 8)
    check(sw.segment == 1 and lat(osw[:5]) == lat(oa[:5]) and lat(osw[5:]) != lat(oa[5:8]), "switch at call 5: same before, different after")

    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
