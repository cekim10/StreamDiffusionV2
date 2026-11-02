#!/usr/bin/env python3
"""LongLive-1.3B as a per-call streaming session (second model for OTTER; osdi/second_model_survey.md).

The vendored LongLive code (third_party/longlive, unmodified) generates a whole video offline: noise for every frame is
drawn up front, the denoiser draws its re-noising from the global RNG, and the VAE decodes once at the end. This module
re-implements its inference loop (LongLive1.0 pipeline/causal_inference.py and pipeline/interactive_causal_inference.py,
Apache-2.0) as one call = one block of num_frame_per_block latent frames, with three harness changes that migration
needs and that leave the model untouched:
  - per-call seeding: the block's initial noise and each denoising step's re-noising come from a torch.Generator seeded
    by (seed, call, step), so any host reproduces call c without carrying RNG state (same distribution as upstream,
    other samples; the reference is always this runtime's own uninterrupted run);
  - streaming decode: the VAE decodes each block with its causal feature cache (upstream decode_to_pixel(use_cache=True)),
    the cache held per session;
  - explicit session state: KV cache, cross-attention cache, VAE decoder cache, the last local_attn_size output latents
    (the input of LongLive's KV recache) and the counters, exported / imported by component.

State roles (OTTER temporal semantics):
  durable    sink K / V: the first sink_size latent frames of every layer, written by call 0 and never again with
             global_sink (LongLive's shipped configs)
  ephemeral  rolling-window K / V, cross-attention K / V (prompt-derived), VAE decoder feature cache
  immediate  the last local_attn_size output latents, call / frame counters, cache end indices, prompt segment
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
LL_DIR = ROOT / "third_party/longlive"
if str(LL_DIR) not in sys.path:
    sys.path.insert(0, str(LL_DIR))

DEFAULT_CFG = LL_DIR / "configs/longlive_inference.yaml"
CKPT_DIR = ROOT / "wan_models/LongLive-1.3B"
LATENT = (16, 60, 104)   # latent C, H, W at 480 x 832
ROLES = ("durable", "ephemeral", "immediate")


def call_seed(seed: int, call: int, k: int) -> int:
    """Seed of the k-th noise draw of call `call` (k = 0: the block's initial noise, k >= 1: re-noising before step k)."""
    return ((seed * 1_000_003 + call) * 131 + k) % (2 ** 63)


def nbytes(t) -> int:
    return t.numel() * t.element_size() if isinstance(t, torch.Tensor) else 0


def digest(t: torch.Tensor) -> str:
    return hashlib.blake2b(t.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes(), digest_size=16).hexdigest()


def load_model(cfg_path=DEFAULT_CFG, device="cuda", ckpt_dir=CKPT_DIR):
    """The LongLive generator (base checkpoint + LoRA, as upstream interactive_inference.py), text encoder and VAE, bf16."""
    import os

    import peft
    from omegaconf import OmegaConf
    from utils.lora_utils import configure_lora_for_model
    from utils.wan_wrapper import WanDiffusionWrapper, WanTextEncoder, WanVAEWrapper

    cfg = OmegaConf.load(cfg_path)
    cwd = os.getcwd()
    os.chdir(ROOT)   # the vendored code opens wan_models/... relative to the working directory
    try:
        gen = WanDiffusionWrapper(**cfg.model_kwargs, is_causal=True)
        te = WanTextEncoder()
        vae = WanVAEWrapper()
    finally:
        os.chdir(cwd)
    sd = torch.load(Path(ckpt_dir) / "longlive_base.pt", map_location="cpu")
    gen.load_state_dict(sd["generator_ema" if cfg.use_ema else "generator"])
    gen.model = configure_lora_for_model(gen.model, model_name="generator", lora_config=cfg.adapter, is_main_process=True)
    lora = torch.load(Path(ckpt_dir) / "lora.pt", map_location="cpu")
    peft.set_peft_model_state_dict(gen.model, lora["generator_lora"] if isinstance(lora, dict) and "generator_lora" in lora else lora)
    gen = gen.to(device=device, dtype=torch.bfloat16)
    te = te.to(device=device, dtype=torch.bfloat16)
    vae = vae.to(device=device, dtype=torch.bfloat16)
    return LLModel(cfg, torch.device(device), gen, te, vae)


class LLModel:
    """Weights and fixed hyper-parameters, shared by every session in the process."""

    def __init__(self, cfg, device, generator, text_encoder, vae, latent=LATENT):
        self.cfg, self.device = cfg, torch.device(device)
        self.generator, self.text_encoder, self.vae = generator, text_encoder, vae
        self.scheduler = generator.get_scheduler()
        steps = torch.tensor(list(cfg.denoising_step_list), dtype=torch.long)
        if cfg.warp_denoising_step:   # upstream CausalInferencePipeline.__init__
            ts = torch.cat((self.scheduler.timesteps.cpu(), torch.tensor([0], dtype=torch.float32)))
            steps = ts[1000 - steps]
        self.denoising_step_list = steps
        self.F = int(cfg.num_frame_per_block)
        self.local_attn_size = int(cfg.model_kwargs.local_attn_size)
        self.sink_size = int(cfg.model_kwargs.sink_size)
        self.context_noise = int(getattr(cfg, "context_noise", 0))
        self.global_sink = bool(getattr(cfg, "global_sink", False))
        self.latent = tuple(latent)
        self.frame_seq_length = (self.latent[1] // 2) * (self.latent[2] // 2)   # patch (1, 2, 2)
        base = self.base_model()
        self.num_layers = len(base.blocks)
        self.num_heads = base.num_heads
        self.head_dim = base.dim // base.num_heads
        if self.F > 1:
            generator.model.num_frame_per_block = self.F   # upstream CausalInferencePipeline.__init__
        generator.model.local_attn_size = self.local_attn_size   # upstream inference()
        size = 32760 if self.local_attn_size == -1 else self.local_attn_size * self.frame_seq_length
        for m in [generator.model, *generator.model.modules()]:   # upstream _set_all_modules_max_attention_size
            if hasattr(m, "max_attention_size"):
                m.max_attention_size = size

    def base_model(self):
        m = self.generator.model
        return m.get_base_model() if hasattr(m, "get_base_model") else m

    def sync(self):
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)


class LLSession:
    """One streaming session: call c generates latent frames [c F, (c + 1) F) and decodes them."""

    def __init__(self, model: LLModel, prompts: list[str], seed: int = 0, switch_calls: list[int] | None = None):
        self.m, self.prompts, self.seed = model, list(prompts), int(seed)
        self.switch_calls = list(switch_calls or [])
        assert len(self.switch_calls) == len(self.prompts) - 1, "one switch call per prompt after the first"
        self.call = 0
        self.frame = 0      # current_start_frame (latent frames generated so far)
        self.segment = 0
        self.kv = self.xattn = self.feat_map = None
        self.latbuf = None  # [1, <= local_attn_size, C, H, W] last output latents
        self.cond = None

    # ---- set-up -----------------------------------------------------------------------------------------------
    def start(self):
        m, dev, dt = self.m, self.m.device, torch.bfloat16
        size = (m.local_attn_size if m.local_attn_size != -1 else 1024) * m.frame_seq_length
        self.kv = [{"k": torch.zeros([1, size, m.num_heads, m.head_dim], dtype=dt, device=dev),
                    "v": torch.zeros([1, size, m.num_heads, m.head_dim], dtype=dt, device=dev),
                    "global_end_index": torch.tensor([0], dtype=torch.long, device=dev),
                    "local_end_index": torch.tensor([0], dtype=torch.long, device=dev)} for _ in range(m.num_layers)]
        tl = m.base_model().text_len
        self.xattn = [{"k": torch.zeros([1, tl, m.num_heads, m.head_dim], dtype=dt, device=dev),
                       "v": torch.zeros([1, tl, m.num_heads, m.head_dim], dtype=dt, device=dev),
                       "is_init": False} for _ in range(m.num_layers)]
        m.vae.model.clear_cache()
        self.feat_map = m.vae.model._feat_map
        self.latbuf = torch.zeros([1, 0, *m.latent], dtype=dt, device=dev)
        with torch.no_grad():
            self.cond = [m.text_encoder(text_prompts=[p]) for p in self.prompts]
        self.call = self.frame = self.segment = 0
        return self

    # ---- one call -----------------------------------------------------------------------------------------------
    def _gen(self, k: int) -> torch.Generator:
        g = torch.Generator(device=self.m.device)
        g.manual_seed(call_seed(self.seed, self.call, k))
        return g

    def _forward(self, x, t, cond):
        return self.m.generator(noisy_image_or_video=x, conditional_dict=cond, timestep=t, kv_cache=self.kv,
                                crossattn_cache=self.xattn, current_start=self.frame * self.m.frame_seq_length)

    @torch.no_grad()
    def step(self, decode: bool = True) -> dict:
        """Generate (and decode) the next block. Returns latents, frames (uint8 [T, H, W, 3] on the device) and timings."""
        m, F, dev = self.m, self.m.F, self.m.device
        if self.segment < len(self.switch_calls) and self.call >= self.switch_calls[self.segment]:
            self.segment += 1
            self.recache()
        cond = self.cond[self.segment]
        m.sync(); t0 = time.perf_counter()
        noisy = torch.randn([1, F, *m.latent], generator=self._gen(0), device=dev, dtype=torch.bfloat16)
        steps = m.denoising_step_list
        for i, ts in enumerate(steps):
            timestep = torch.ones([1, F], device=dev, dtype=torch.int64) * ts
            _, pred = self._forward(noisy, timestep, cond)
            if i < len(steps) - 1:   # upstream: add_noise(pred, randn_like(pred), next_t)
                flat = pred.flatten(0, 1)
                eps = torch.randn(flat.shape, generator=self._gen(i + 1), device=dev, dtype=flat.dtype)
                noisy = m.scheduler.add_noise(flat, eps, steps[i + 1] * torch.ones([F], device=dev, dtype=torch.long)
                                              ).unflatten(0, pred.shape[:2])
        # rerun with clean context to update the cache (upstream)
        self._forward(pred, torch.ones([1, F], device=dev, dtype=torch.int64) * m.context_noise, cond)
        m.sync(); t1 = time.perf_counter()
        frames = None
        if decode:
            frames = self.decode(pred)
        m.sync(); t2 = time.perf_counter()
        self.latbuf = torch.cat([self.latbuf, pred.to(self.latbuf.dtype)], dim=1)[:, -max(m.local_attn_size, F):]
        out = {"call": self.call, "latents": pred, "frames": frames, "t_gen_s": t1 - t0, "t_dec_s": t2 - t1}
        self.frame += F
        self.call += 1
        return out

    def decode(self, latents: torch.Tensor) -> torch.Tensor:
        """Streaming VAE decode of one block with this session's causal feature cache -> uint8 [T, H, W, 3]."""
        vae = self.m.vae
        vae.model._feat_map = self.feat_map
        x = vae.decode_to_pixel(latents, use_cache=True)[0]   # [T, C, H, W] in [-1, 1]
        self.feat_map = vae.model._feat_map
        return ((x * 0.5 + 0.5).clamp(0, 1) * 255).round().to(torch.uint8).permute(0, 2, 3, 1).contiguous()

    @torch.no_grad()
    def recache(self, frames: torch.Tensor | None = None):
        """LongLive's KV recache (upstream _recache_after_switch) from the last local_attn_size output latents."""
        m = self.m
        if not m.global_sink:
            for c in self.kv:
                c["k"].zero_(); c["v"].zero_()
        for c in self.xattn:
            c["k"].zero_(); c["v"].zero_(); c["is_init"] = False
        if self.frame == 0:
            return
        n = self.frame if m.local_attn_size == -1 else min(m.local_attn_size, self.frame)
        x = (self.latbuf if frames is None else frames)[:, -n:]
        assert x.shape[1] == n, f"recache needs {n} latent frames, has {x.shape[1]}"
        m.generator.model.block_mask = m.base_model()._prepare_blockwise_causal_attn_mask(
            device=x.device, num_frames=n, frame_seqlen=m.frame_seq_length, num_frame_per_block=m.F,
            local_attn_size=m.local_attn_size)
        t = torch.ones([1, n], device=x.device, dtype=torch.int64) * m.context_noise
        m.generator(noisy_image_or_video=x, conditional_dict=self.cond[self.segment], timestep=t, kv_cache=self.kv,
                    crossattn_cache=self.xattn, current_start=(self.frame - n) * m.frame_seq_length,
                    sink_recache_after_switch=not m.global_sink)
        for c in self.xattn:
            c["k"].zero_(); c["v"].zero_(); c["is_init"] = False

    @torch.no_grad()
    def replay(self, latents: list[torch.Tensor], decode: bool = True):
        """Teacher-forced replay of logged output blocks: per block only the clean context pass the source ran after
        generating it (and the decode, which advances the VAE cache), no denoising. Started from the true state at call
        c (e.g. call 0) it reproduces the source's state; started from `from_sink` it rebuilds the window approximately."""
        m = self.m
        for lat in latents:
            if self.segment < len(self.switch_calls) and self.call >= self.switch_calls[self.segment]:
                self.segment += 1
                self.recache()
            lat = lat.to(m.device, torch.bfloat16)
            self._forward(lat, torch.ones([1, m.F], device=m.device, dtype=torch.int64) * m.context_noise, self.cond[self.segment])
            if decode:
                self.decode(lat)
            self.latbuf = torch.cat([self.latbuf, lat], dim=1)[:, -max(m.local_attn_size, m.F):]
            self.frame += m.F
            self.call += 1

    def from_sink(self, sink: list[torch.Tensor], call: int, segment: int = 0):
        """A started session holding only the durable sink, positioned at `call` as if the stream's history before it
        were truncated to the sink: empty window (local end = sink), VAE decoder cache cleared, empty latent buffer."""
        m, S = self.m, self.m.sink_size * self.m.frame_seq_length
        for i, t in enumerate(sink):
            self.kv[i // 2]["kv"[i % 2]][:, :S].copy_(t)
        for c in self.kv:
            c["global_end_index"].fill_(call * m.F * m.frame_seq_length)
            c["local_end_index"].fill_(S)
        self.call, self.frame, self.segment = call, call * m.F, segment
        m.vae.model.clear_cache()
        self.feat_map = m.vae.model._feat_map
        self.latbuf = self.latbuf[:, :0]
        return self

    @torch.no_grad()
    def warm_decoder(self, n: int | None = None):
        """Approximate VAE decoder cache: clear it and decode the last n buffered latents, discarding the frames."""
        self.m.vae.model.clear_cache()
        self.feat_map = self.m.vae.model._feat_map
        n = n or self.m.F
        if self.latbuf.shape[1]:
            self.decode(self.latbuf[:, -n:])

    # ---- state ----------------------------------------------------------------------------------------------------
    def components(self) -> dict[str, tuple[str, list]]:
        """name -> (role, [tensors or None]) for the inventory, export and checksums."""
        S = self.m.sink_size * self.m.frame_seq_length
        return {
            "sink_kv": ("durable", [c[kk][:, :S] for c in self.kv for kk in ("k", "v")]),
            "window_kv": ("ephemeral", [c[kk][:, S:] for c in self.kv for kk in ("k", "v")]),
            "crossattn_kv": ("ephemeral", [c[kk] for c in self.xattn for kk in ("k", "v")]),
            "vae_decoder_cache": ("ephemeral", list(self.feat_map)),
            "latent_buffer": ("immediate", [self.latbuf]),
        }

    def counters(self) -> dict:
        return {"call": self.call, "frame": self.frame, "segment": self.segment,
                "end_index": [[int(c["global_end_index"].item()), int(c["local_end_index"].item())] for c in self.kv],
                "xattn_init": [bool(c["is_init"]) for c in self.xattn]}

    def inventory(self) -> dict:
        inv = {name: {"role": role, "bytes": sum(nbytes(t) for t in ts)} for name, (role, ts) in self.components().items()}
        S = self.m.sink_size * self.m.frame_seq_length
        used = self.kv[0]["local_end_index"].item()
        inv["window_kv"]["bytes_used"] = inv["window_kv"]["bytes"] * max(0, used - S) // max(1, self.kv[0]["k"].shape[1] - S)
        inv["_by_role"] = {r: sum(v["bytes"] for v in inv.values() if isinstance(v, dict) and v.get("role") == r) for r in ROLES}
        return inv

    def export_state(self, names=None) -> dict:
        """Copies (on the CPU) of the named components plus the counters; names None = all."""
        comps = self.components()
        names = list(comps) if names is None else list(names)
        return {"counters": self.counters(),
                "tensors": {n: [None if t is None else t.detach().to("cpu", copy=True) for t in comps[n][1]] for n in names}}

    def import_state(self, st: dict):
        """Restore exported components into this (started) session; components not in `st` keep their current value."""
        c = st["counters"]
        self.call, self.frame, self.segment = c["call"], c["frame"], c["segment"]
        for kv, (g, l) in zip(self.kv, c["end_index"]):
            kv["global_end_index"].fill_(g); kv["local_end_index"].fill_(l)
        for xa, ini in zip(self.xattn, c["xattn_init"]):
            xa["is_init"] = ini
        S = self.m.sink_size * self.m.frame_seq_length
        dev = self.m.device
        for name, ts in st["tensors"].items():
            if name == "sink_kv":
                for i, t in enumerate(ts):
                    self.kv[i // 2]["kv"[i % 2]][:, :S].copy_(t)
            elif name == "window_kv":
                for i, t in enumerate(ts):
                    self.kv[i // 2]["kv"[i % 2]][:, S:].copy_(t)
            elif name == "crossattn_kv":
                for i, t in enumerate(ts):
                    self.xattn[i // 2]["kv"[i % 2]].copy_(t)
            elif name == "vae_decoder_cache":
                self.feat_map[:] = [None if t is None else t.to(dev) for t in ts]
            elif name == "latent_buffer":
                self.latbuf = ts[0].to(dev)
        return self

    def checksums(self) -> dict:
        """Per-component digests; the KV ones per layer and per latent-frame slot (frame_seq_length tokens)."""
        fs = self.m.frame_seq_length
        out = {}
        for name, (_, ts) in self.components().items():
            if name in ("sink_kv", "window_kv"):
                out[name] = [[digest(t[:, s * fs:(s + 1) * fs]) for s in range(t.shape[1] // fs)] for t in ts]
            else:
                out[name] = [None if t is None else digest(t) for t in ts]
        return out
