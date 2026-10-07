#!/usr/bin/env python3
"""State-criticality ablation at a simulated migration boundary (Obs 1 + Obs 2).

One process. Runs an uninterrupted baseline session, then for each config re-runs the SAME
session (same seeds per chunk) up to migration chunk M, applies the ablation (drop / delay /
cold restart), continues for N chunks, and scores every output frame against the baseline.
See results/state_migration/state_map.md section 3 for what each config does.

Outputs under --out_dir:
    ablation_raw.csv        one row per (config, call, frame): psnr, ssim
    ablation_summary.md     per-config table + recovery point + bytes withheld
    ablation_summary.json
    ablation_static.json    environment, inventory bytes, timings
    videos/<config>.mp4     (with --save_video) frames from M onward
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from skimage.metrics import structural_similarity  # noqa: E402

from models.data import TextDataset  # noqa: E402
from models.util import set_seed  # noqa: E402
from streamv2v.inference import SingleGPUInferencePipeline  # noqa: E402
from streamv2v.inference_common import load_mp4_as_tensor, merge_cli_config  # noqa: E402

MB = 1024.0 * 1024.0


# --------------------------------------------------------------------------- state access
def kv_layers(pl):
    return pl.kv_cache1


def zero_kv_slots(pl, slot_lo: int, slot_hi: int) -> int:
    """Zero ring-buffer slots [slot_lo, slot_hi) in every layer. Returns bytes zeroed."""
    fsl = pl.frame_seq_length
    nbytes = 0
    for layer in kv_layers(pl):
        for key in ("k", "v"):
            view = layer[key][:, slot_lo * fsl: slot_hi * fsl]
            nbytes += view.numel() * view.element_size()
            view.zero_()
    return nbytes


def snapshot_kv(pl, slot_lo: int, slot_hi: int) -> dict:
    fsl = pl.frame_seq_length
    snap = {"k": [], "v": [], "pos": [], "lo": slot_lo, "hi": slot_hi}
    for layer in kv_layers(pl):
        snap["k"].append(layer["k"][:, slot_lo * fsl: slot_hi * fsl].detach().clone())
        snap["v"].append(layer["v"][:, slot_lo * fsl: slot_hi * fsl].detach().clone())
        snap["pos"].append(layer["pos"][:, slot_lo:slot_hi].detach().clone())
    return snap


def force_copy_kv(pl, snap: dict) -> int:
    """Overwrite slots [lo,hi) with the snapshot (k, v, pos) regardless of current contents."""
    fsl = pl.frame_seq_length
    n = 0
    for li, layer in enumerate(kv_layers(pl)):
        layer["k"][:, snap["lo"] * fsl: snap["hi"] * fsl] = snap["k"][li]
        layer["v"][:, snap["lo"] * fsl: snap["hi"] * fsl] = snap["v"][li]
        layer["pos"][:, snap["lo"]:snap["hi"]] = snap["pos"][li]
        n += snap["k"][li].numel() * snap["k"][li].element_size() * 2
    return n


def restore_kv(pl, snap: dict) -> dict:
    """Copy snapshotted slots back only where the slot still holds the same frame position
    (a delayed delivery of a slot that was overwritten in the meantime is useless)."""
    fsl = pl.frame_seq_length
    restored = 0
    expired = 0
    for li, layer in enumerate(kv_layers(pl)):
        cur_pos = layer["pos"][:, snap["lo"]:snap["hi"]]
        same = cur_pos == snap["pos"][li]
        for b in range(same.shape[0]):
            for s in range(same.shape[1]):
                lo = (snap["lo"] + s) * fsl
                hi = lo + fsl
                if bool(same[b, s]):
                    layer["k"][b, lo:hi] = snap["k"][li][b, s * fsl:(s + 1) * fsl]
                    layer["v"][b, lo:hi] = snap["v"][li][b, s * fsl:(s + 1) * fsl]
                    restored += 1
                else:
                    expired += 1
    return {"slots_restored": restored, "slots_expired": expired}


def serialize_state(pl, pm, session) -> dict:
    """Deep-copy everything a destination would need to continue this session exactly."""
    snap = {"kv": [], "ring": [], "evict": [], "vae": {}, "session": {}, "pipeline": {}}
    for layer in kv_layers(pl):
        snap["kv"].append({"k": layer["k"].detach().clone(), "v": layer["v"].detach().clone()})
        snap["ring"].append({"global_end_index": layer["global_end_index"].detach().clone(),
                             "local_end_index": layer["local_end_index"].detach().clone(),
                             "pos": layer["pos"].detach().clone(),
                             "total_steps": layer.get("total_steps"), "current_step": layer.get("current_step")})
    for block in pl.generator.model.blocks:
        ev = getattr(block.self_attn, "evict_idx", None)
        snap["evict"].append([list(r) for r in ev] if isinstance(ev, list) else None)
    snap["crossattn"] = [{"k": e["k"].detach().clone(), "v": e["v"].detach().clone(), "is_init": e.get("is_init", False)} for e in pl.crossattn_cache]
    vm = pl.vae.model
    for attr in ("_enc_feat_map", "_feat_map"):
        fm = getattr(vm, attr, None)
        snap["vae"][attr] = [t.detach().clone() if isinstance(t, torch.Tensor) else t for t in fm] if isinstance(fm, list) else None
    for attr in ("_enc_conv_idx", "_conv_idx", "first_encode", "first_decode", "first_batch"):
        snap["vae"][attr] = getattr(vm, attr, None)
        if isinstance(snap["vae"][attr], list):
            snap["vae"][attr] = list(snap["vae"][attr])
    snap["pipeline"] = {"hidden_states": pl.hidden_states.detach().clone(),
                        "kv_cache_starts": pl.kv_cache_starts.detach().clone(),
                        "kv_cache_ends": pl.kv_cache_ends.detach().clone(),
                        "timestep": pl.timestep.detach().clone(),
                        "denoising_step_list": pl.denoising_step_list.detach().clone(),
                        "pm_processed": pm.processed}
    snap["session"] = {"current_start": session.current_start, "current_end": session.current_end,
                       "noise_scale": session.noise_scale, "init_noise_scale": session.init_noise_scale,
                       "last_image": session.last_image.detach().clone(), "processed": session.processed,
                       "chunk_size": session.chunk_size}
    return snap


STATE_COMPONENTS = ("sink", "recent", "meta", "vae", "inflight")


def restore_state(pl, pm, session, snap: dict, comps: set) -> dict:
    """Overwrite a freshly allocated destination with the selected components of `snap`.
    Everything not selected is left EMPTY (zeros / fresh), never the dummy-prepare contents."""
    fsl = pl.frame_seq_length
    sink = pl.num_sink_tokens
    moved = {c: 0 for c in STATE_COMPONENTS}
    for li, layer in enumerate(kv_layers(pl)):
        layer["k"].zero_(); layer["v"].zero_()
        if "sink" in comps:
            layer["k"][:, :sink * fsl] = snap["kv"][li]["k"][:, :sink * fsl]
            layer["v"][:, :sink * fsl] = snap["kv"][li]["v"][:, :sink * fsl]
            moved["sink"] += 2 * snap["kv"][li]["k"][:, :sink * fsl].numel() * snap["kv"][li]["k"].element_size()
        if "recent" in comps:
            layer["k"][:, sink * fsl:] = snap["kv"][li]["k"][:, sink * fsl:]
            layer["v"][:, sink * fsl:] = snap["kv"][li]["v"][:, sink * fsl:]
            moved["recent"] += 2 * snap["kv"][li]["k"][:, sink * fsl:].numel() * snap["kv"][li]["k"].element_size()
        if "meta" in comps:
            r = snap["ring"][li]
            layer["global_end_index"].copy_(r["global_end_index"]); layer["local_end_index"].copy_(r["local_end_index"])
            layer["pos"].copy_(r["pos"])
            if r["total_steps"] is not None:
                layer["total_steps"] = r["total_steps"]; layer["current_step"] = r["current_step"]
            moved["meta"] += r["pos"].numel() * 8 + 16
    if "meta" in comps:
        for block, ev in zip(pl.generator.model.blocks, snap["evict"]):
            block.self_attn.evict_idx = [list(r) for r in ev] if ev is not None else None
        for e, se in zip(pl.crossattn_cache, snap["crossattn"]):
            e["k"] = se["k"]; e["v"] = se["v"]; e["is_init"] = se["is_init"]
        pl.kv_cache_starts.copy_(snap["pipeline"]["kv_cache_starts"]); pl.kv_cache_ends.copy_(snap["pipeline"]["kv_cache_ends"])
        pl.timestep.copy_(snap["pipeline"]["timestep"])
        pm.processed = snap["pipeline"]["pm_processed"]
        for key in ("current_start", "current_end", "noise_scale", "init_noise_scale", "processed", "chunk_size"):
            setattr(session, key, snap["session"][key])
        session.last_image = snap["session"]["last_image"].clone()
        moved["meta"] += snap["session"]["last_image"].numel() * snap["session"]["last_image"].element_size()
    vm = pl.vae.model
    for attr in ("_enc_feat_map", "_feat_map"):
        fm = getattr(vm, attr, None)
        src = snap["vae"].get(attr)
        if not isinstance(fm, list) or src is None:
            continue
        for i, t in enumerate(fm):
            if isinstance(t, torch.Tensor):
                if "vae" in comps and isinstance(src[i], torch.Tensor):
                    t.copy_(src[i]); moved["vae"] += t.numel() * t.element_size()
                else:
                    t.zero_()
    if "vae" in comps:
        for attr in ("_enc_conv_idx", "_conv_idx", "first_encode", "first_decode", "first_batch"):
            if snap["vae"].get(attr) is not None:
                setattr(vm, attr, list(snap["vae"][attr]) if isinstance(snap["vae"][attr], list) else snap["vae"][attr])
    hs = pl.hidden_states
    if "inflight" in comps:
        hs.copy_(snap["pipeline"]["hidden_states"]); moved["inflight"] += hs[:-1].numel() * hs.element_size()
    else:
        hs[:-1].zero_()
    return moved


def make_placeholder_sink(pl) -> int:
    """Destination-local temporary sink: copy the most recent slots' K/V and positions into the sink
    slots (the model then anchors on what it has, instead of attending to zero keys)."""
    fsl = pl.frame_seq_length
    sink = pl.num_sink_tokens
    n = pl.num_kv_cache
    nbytes = 0
    for layer in kv_layers(pl):
        for si in range(sink):
            src_slot = n - sink + si  # the last `sink` slots
            layer["k"][:, si * fsl:(si + 1) * fsl] = layer["k"][:, src_slot * fsl:(src_slot + 1) * fsl]
            layer["v"][:, si * fsl:(si + 1) * fsl] = layer["v"][:, src_slot * fsl:(src_slot + 1) * fsl]
            layer["pos"][:, si] = layer["pos"][:, src_slot]
            nbytes += 2 * fsl * layer["k"].shape[0] * layer["k"].shape[2] * layer["k"].shape[3] * layer["k"].element_size()
    return nbytes


def vae_cache_tensors(pl, which: str):
    vm = pl.vae.model
    attrs = {"enc": ["_enc_feat_map"], "dec": ["_feat_map"], "all": ["_enc_feat_map", "_feat_map"]}[which]
    out = []
    for attr in attrs:
        fm = getattr(vm, attr, None)
        if isinstance(fm, list):
            out.extend(t for t in fm if isinstance(t, torch.Tensor))
    return out


def zero_vae_cache(pl, which: str) -> int:
    nbytes = 0
    for t in vae_cache_tensors(pl, which):
        nbytes += t.numel() * t.element_size()
        t.zero_()
    return nbytes


def inflight_view(pl):
    """Rows holding chunks still being denoised. `inference_stream` shifts rows down before each call
    (`causal_stream_inference.py:269-270`) and re-noises rows 0..k-2 after it (`:292-298`); the last
    row is the finished chunk of two calls ago, already decoded. So the live state is rows [:k-1]."""
    hs = pl.hidden_states
    if hs is None or hs.shape[0] < 2:
        return None
    return hs[:-1]


def zero_inflight(pl) -> int:
    view = inflight_view(pl)
    if view is None:
        return 0
    nbytes = view.numel() * view.element_size()
    view.zero_()
    return nbytes


def slot_positions(pl) -> dict:
    """RoPE frame position held by each ring-buffer slot at this moment (layer 0, row 0).
    Sink slots still at 0..2 => no adaptive refresh has fired yet."""
    pos = pl.kv_cache1[0]["pos"][0].tolist()
    sink = pl.num_sink_tokens
    return {"sink_slot_pos": pos[:sink], "recent_slot_pos": pos[sink:]}


def inventory_bytes(pl) -> dict:
    fsl = pl.frame_seq_length
    sink = pl.num_sink_tokens
    n = pl.num_kv_cache
    kv_row = 0
    for layer in kv_layers(pl):
        kv_row += layer["k"][:, :fsl].numel() * layer["k"].element_size() * 2  # k+v per slot (all rows)
    return {
        "kv_sink_bytes": kv_row * sink,
        "kv_recent_bytes": kv_row * (n - sink),
        "kv_all_bytes": kv_row * n,
        "vae_enc_bytes": sum(t.numel() * t.element_size() for t in vae_cache_tensors(pl, "enc")),
        "vae_dec_bytes": sum(t.numel() * t.element_size() for t in vae_cache_tensors(pl, "dec")),
        "inflight_bytes": (inflight_view(pl).numel() * pl.hidden_states.element_size()) if inflight_view(pl) is not None else 0,
        "crossattn_bytes": sum(e["k"].untyped_storage().nbytes() + e["v"].untyped_storage().nbytes() for e in pl.crossattn_cache),
        "prompt_embeds_bytes": pl.conditional_dict["prompt_embeds"].numel() * pl.conditional_dict["prompt_embeds"].element_size(),
    }


# --------------------------------------------------------------------------- configs
def parse_config(name: str) -> dict:
    """Return {'drop': [...], 'delay': [(component, d)], 'restart': bool}."""
    if name in ("repeat", "baseline"):
        return {"drop": [], "delay": [], "restart": False}
    if name == "seed_shift":
        return {"drop": [], "delay": [], "restart": False, "seed_offset": 7919}
    if name == "cold_restart":
        return {"drop": [], "delay": [], "restart": True}
    if name.startswith("xfer_"):
        comps = set(STATE_COMPONENTS) if name == "xfer_all" else set(name[len("xfer_"):].split("+"))
        unknown = comps - set(STATE_COMPONENTS)
        if unknown:
            raise ValueError(f"unknown xfer components {unknown} in {name}")
        return {"drop": [], "delay": [], "restart": False, "xfer": comps}
    if name.startswith("ph_"):
        # ph_zero_D : zero sink, refresh off, true sink swapped in at M+D
        # ph_local_D: local placeholder sink (copy of recent slots), refresh off, true sink swapped in at M+D
        # ph_local_noswap / ph_zero_noswap: placeholder only, never swapped
        # ph_localrefresh: zero sink, adaptive refresh ON, never swapped (== drop_kv_sink)
        if name == "ph_localrefresh":
            return {"drop": ["kv_sink"], "delay": [], "restart": False, "ph": "refresh"}
        parts = name.split("_")
        kind = parts[1]
        arrival = None if parts[2] == "noswap" else int(parts[2])
        return {"drop": [], "delay": [], "restart": False, "ph": kind, "arrival": arrival, "no_refresh": True}
    if name == "replay_full":
        return {"drop": [], "delay": [], "restart": False, "replay": "full", "sink0": True}
    if name.startswith("replay_"):
        parts = name.split("_")
        w = int(parts[1])
        toks = set(parts[2:])
        unknown = toks - {"sink0", "sinkhist", "sinkxfer", "pos"}
        if unknown:
            raise ValueError(f"unknown replay tokens {unknown} in {name}")
        return {"drop": [], "delay": [], "restart": False, "replay": w,
                "sink0": bool(toks & {"sink0", "sinkhist"}), "sinkhist": "sinkhist" in toks,
                "sinkxfer": "sinkxfer" in toks, "pos": "pos" in toks}
    no_refresh = name.endswith("_nr")
    base = name[:-3] if no_refresh else name
    if base.startswith("drop_"):
        comp = base[len("drop_"):]
        comps = ["kv_all", "vae_all", "inflight"] if comp == "all" else [comp]
        return {"drop": comps, "delay": [], "restart": False, "no_refresh": no_refresh}
    if base.startswith("delay_"):
        body = base[len("delay_"):]
        comp, d = body.rsplit("_", 1)
        return {"drop": [], "delay": [(comp, int(d))], "restart": False, "no_refresh": no_refresh}
    raise ValueError(f"unknown config {name}")


MECHANISM_CONFIGS = [
    "repeat",
    "xfer_all",
    "xfer_sink+meta",
    "xfer_sink+meta+vae",
    "xfer_sink+meta+vae+inflight",
    "xfer_meta",
    "xfer_meta+vae+inflight",
    "replay_3_sinkhist_pos",
    "ph_localrefresh",
    "ph_zero_noswap",
    "ph_local_noswap",
    "ph_zero_1", "ph_zero_4", "ph_zero_8", "ph_zero_16",
    "ph_local_1", "ph_local_4", "ph_local_8", "ph_local_16",
]

RECONSTRUCT_CONFIGS = [
    "repeat",
    "seed_shift",
    "cold_restart",
    "replay_1",
    "replay_3",
    "replay_6",
    "replay_0_sink0",
    "replay_1_sink0",
    "replay_3_sink0",
    "replay_6_sink0",
    "replay_3_sinkhist",
    "replay_6_sinkhist",
    "replay_full",
]

DEFAULT_CONFIGS = [
    "repeat",
    "seed_shift",
    "drop_inflight",
    "drop_kv_recent",
    "drop_kv_sink",
    "drop_kv_all",
    "drop_vae_enc",
    "drop_vae_dec",
    "drop_vae_all",
    "drop_all",
    "cold_restart",
    "delay_kv_recent_1",
    "delay_kv_recent_2",
    "delay_kv_sink_1",
    "delay_kv_sink_4",
    "delay_kv_sink_16",
    "delay_kv_all_1",
    "drop_kv_sink_nr",
    "delay_kv_sink_1_nr",
    "delay_kv_sink_4_nr",
    "delay_kv_sink_16_nr",
]


# --------------------------------------------------------------------------- metrics
def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2))
    return 99.0 if mse == 0.0 else 10.0 * math.log10(1.0 / mse)


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    return float(structural_similarity(a, b, channel_axis=2, data_range=1.0))


def to_uint8(frames: np.ndarray) -> np.ndarray:
    return np.clip(frames * 255.0 + 0.5, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- session runner
class Runner:
    def __init__(self, pm, video: torch.Tensor, prompt: str, args, device):
        self.pm = pm
        self.pl = pm.pipeline
        self.video = video  # [1,C,T,H,W] bf16 pinned on host
        self.prompt = prompt
        self.args = args
        self.device = device
        self.chunk = pm.base_chunk_size * self.pl.num_frame_per_block
        self.first = 1 + self.chunk
        self.seed_offset = 0
        self.last_refresh_call = -1  # set after the baseline run from sink-slot position changes
        self.noise_hist = {}  # baseline session.noise_scale after each call

    def frames_for_call(self, c: int) -> torch.Tensor:
        lo = self.first + c * self.chunk
        return self.video[:, :, lo:lo + self.chunk].to(self.device, non_blocking=True)

    def reset_attention_eviction_state(self):
        """`reset_stream_state` re-allocates the KV cache but leaves each layer's ring-buffer
        eviction queue (`self_attn.evict_idx`) from the previous session in place
        (`models/wan/causal_model.py:194,309-313`; nothing in streamv2v resets it). A second
        session would therefore evict slots in a different order than the first. Clear it so
        every run starts from the same state."""
        for block in getattr(self.pl.generator.model, "blocks", []):
            sa = getattr(block, "self_attn", None)
            if sa is not None and hasattr(sa, "evict_idx"):
                sa.evict_idx = None

    def input_frames_for_output_call(self, c: int) -> np.ndarray | None:
        """Output at call c is input chunk c-(k-1) (Stream-Batch lag); return it as uint8 HWC."""
        lag = len(self.pl.denoising_step_list) - 1
        ci = c - lag
        if ci < 0:
            return None
        lo = self.first + ci * self.chunk
        x = self.video[0, :, lo:lo + self.chunk].float()  # [C,T,H,W] in [-1,1]
        x = (x.permute(1, 2, 3, 0) * 0.5 + 0.5).clamp(0, 1).numpy()
        return to_uint8(x)

    def start(self, seed_offset: int = 0):
        set_seed(self.args.seed)
        torch.manual_seed(self.args.seed + seed_offset)
        self.seed_offset = seed_offset
        self.reset_attention_eviction_state()
        # `prepare()` aliases `self.timestep = self.denoising_step_list` and `inference_stream` writes the
        # motion-adaptive step into `timestep[0]` (`causal_stream_inference.py:256,279`), so after one
        # session the schedule itself has drifted (e.g. 700 -> 626). Restore the canonical schedule so
        # every session starts from the configured steps (the demo does the same via
        # `_canonical_denoising_step_list`).
        if not hasattr(self, "_canonical_steps"):
            self._canonical_steps = self.pl.denoising_step_list.detach().clone()
        self.pl.denoising_step_list = self._canonical_steps.clone()
        images = self.video[:, :, :self.first].to(self.device)
        session, _ = self.pm.start_stream_session(self.prompt, images, self.args.noise_scale)
        return session

    def step(self, session, c: int):
        torch.manual_seed(self.args.seed * 100003 + c + 1 + getattr(self, "seed_offset", 0))  # identical noise per call in every run
        images = self.frames_for_call(c)
        outs = self.pm.run_stream_batch(session, images)
        if not outs:
            return None
        return to_uint8(np.concatenate(outs, axis=0))

    def fresh_destination(self):
        """Allocate a brand-new session's buffers (dummy prepare on the first batch; harness overhead,
        not counted). restore_state() then overwrites or zeroes every buffer."""
        self.reset_attention_eviction_state()
        self.pl.denoising_step_list = self._canonical_steps.clone()
        set_seed(self.args.seed)
        torch.manual_seed(self.args.seed)
        images0 = self.video[:, :, :self.first].to(self.device)
        session, _ = self.pm.start_stream_session(self.prompt, images0, self.args.noise_scale)
        return session

    def jump_metadata(self, session, chunk_idx: int):
        """Make the replay session look like the original session right before `chunk_idx`:
        RoPE/stream positions (`current_start/_end`), the motion-adaptive noise-scale EMA and
        `last_image` are tiny per-session metadata that a destination would receive verbatim."""
        fsl = self.pl.frame_seq_length
        latents_in_first = 1 + self.chunk // self.pm.base_chunk_size
        start_frame = latents_in_first + chunk_idx
        # reproduce the t_refresh rewind the original session applies (streamv2v/inference.py:234-236)
        if start_frame >= self.pm.t_refresh:
            rewinds = (start_frame - self.pm.t_refresh) // (self.pm.t_refresh - (self.pl.num_kv_cache - 1)) + 1
            raise RuntimeError(f"pos-faithful jump across a t_refresh rewind (chunk {chunk_idx}, {rewinds} rewinds) is not implemented; use M < {self.pm.t_refresh - latents_in_first}")
        session.current_start = start_frame * fsl
        session.current_end = session.current_start + fsl
        if chunk_idx - 1 in self.noise_hist:
            session.noise_scale = float(self.noise_hist[chunk_idx - 1])
        lo = self.first + chunk_idx * self.chunk
        session.last_image = self.video[:, :, lo - 1: lo].to(self.device)

    def replay_restart(self, c: int, w, sink0: bool, sinkhist: bool = False, pos_faithful: bool = False):
        """Seed-and-replay reconstruction at migration call c.
        sink0=False: new session from [frame before chunk c-w, chunk c-w], then replay chunks c-w+1..c-1.
        sink0=True : new session from the ORIGINAL first batch (frames 0..4) so the sink slots are rebuilt
                     exactly by deterministic replay, then replay the last w chunks c-w..c-1.
        Replayed outputs are discarded (the source already displayed them). Returns
        (session, replay_ms, seed_bytes_uint8, replayed_calls)."""
        torch.cuda.synchronize(self.device)
        t0 = time.perf_counter()
        frame_bytes = 3 * self.args.height * self.args.width  # uint8 camera frame
        if sink0:
            self.reset_attention_eviction_state()
            self.pl.denoising_step_list = self._canonical_steps.clone()
            set_seed(self.args.seed)
            torch.manual_seed(self.args.seed)
            images0 = self.video[:, :, :self.first].to(self.device)
            session, _ = self.pm.start_stream_session(self.prompt, images0, self.args.noise_scale)
            seed_bytes = self.first * frame_bytes
            # prepare() wrote 2 latent frames (slots 0,1); the remaining sink slots are filled by the next
            # chunks of the ORIGINAL session (chunk 1 for sink_size=3), so replay those too for an exact sink.
            # prepare() wrote `prepare_latents` latent frames into slots 0..; harness chunk 0 (frames 5..8)
            # writes the next slot. Replay chunks 0..sink_fill_end-1 to fill all sink slots exactly.
            prepare_latents = 1 + self.chunk // self.pm.base_chunk_size
            sink_fill_end = max(0, self.pl.num_sink_tokens - prepare_latents)
            if sinkhist:
                # also replay through the last adaptive sink refresh observed in the baseline run
                sink_fill_end = max(sink_fill_end, self.last_refresh_call + 1)
            for cc in range(0, sink_fill_end):
                self.step(session, cc)
                seed_bytes += self.chunk * frame_bytes
            first_replay = sink_fill_end if w == "full" else max(c - w, sink_fill_end)
        else:
            if w < 1:
                raise ValueError("replay_W without sink0 needs W >= 1 (W=0 is cold_restart)")
            self.reset_attention_eviction_state()
            self.pl.denoising_step_list = self._canonical_steps.clone()
            start_chunk = c - w
            lo = self.first + start_chunk * self.chunk
            torch.manual_seed(self.args.seed * 100003 + start_chunk + 1)
            images0 = self.video[:, :, lo - 1: lo + self.chunk].to(self.device)
            session, _ = self.pm.start_stream_session(self.prompt, images0, self.args.noise_scale)
            seed_bytes = (1 + self.chunk) * frame_bytes
            first_replay = start_chunk + 1
        replayed = 0
        if sink0:
            replayed += sink_fill_end
        if pos_faithful:
            self.jump_metadata(session, first_replay)
        for cc in range(first_replay, c):
            self.step(session, cc)
            seed_bytes += self.chunk * frame_bytes
            replayed += 1
        torch.cuda.synchronize(self.device)
        return session, (time.perf_counter() - t0) * 1e3, seed_bytes, replayed

    def restart_at(self, session, c: int):
        """Official prompt-switch path: new session seeded with [last_image, chunk c]."""
        torch.manual_seed(self.args.seed * 100003 + c + 1)
        images = torch.cat([session.last_image, self.frames_for_call(c)], dim=2)
        torch.cuda.synchronize(self.device)
        t0 = time.perf_counter()
        new_session, initial_video = self.pm.start_stream_session(self.prompt, images, self.args.noise_scale)
        torch.cuda.synchronize(self.device)
        ms = (time.perf_counter() - t0) * 1e3
        frames = to_uint8(np.asarray(initial_video))[1:]  # drop the seed frame; keep chunk c's 4 frames
        return new_session, frames, ms


def run_config(name: str, runner: Runner, M: int, N: int, baseline: dict, log) -> tuple[list[dict], dict]:
    cfg = parse_config(name)
    pl = runner.pl
    sink, n = pl.num_sink_tokens, pl.num_kv_cache
    session = runner.start(seed_offset=cfg.get("seed_offset", 0))
    rows: list[dict] = []
    info = {"config": name, "bytes_withheld": 0, "events": []}
    pending: list[tuple[int, str, dict]] = []  # (call to restore at, component, snapshot)
    frames_out: list[np.ndarray] = []
    restart_frames = None

    for c in range(M + N):
        if c == M:
            inv = inventory_bytes(pl)
            info["inventory_at_M"] = inv
            info["slot_pos_at_M"] = slot_positions(pl)
            if cfg.get("xfer") is not None:
                snap = serialize_state(pl, runner.pm, session)
                session = runner.fresh_destination()
                moved = restore_state(pl, runner.pm, session, snap, cfg["xfer"])
                info["bytes_withheld"] = sum(v for k2, v in inv.items() if k2 != "prompt_embeds_bytes") - sum(moved.values())
                info["bytes_moved"] = moved
                info["events"].append({"call": c, "xfer": sorted(cfg["xfer"]), "moved_mb": {k2: round(v / MB, 1) for k2, v in moved.items()}})
                del snap
            elif cfg.get("ph") is not None and cfg["ph"] != "refresh":
                true_sink = snapshot_kv(pl, 0, sink)
                for block in pl.generator.model.blocks:
                    block.self_attn.adapt_sink_thr = -1
                info["bytes_withheld"] = zero_kv_slots(pl, 0, sink)
                if cfg["ph"] == "local":
                    info["placeholder_bytes"] = make_placeholder_sink(pl)
                if cfg.get("arrival") is not None:
                    pending.append((c + cfg["arrival"], "true_sink_swap", true_sink))
                info["events"].append({"call": c, "placeholder": cfg["ph"], "arrival": cfg.get("arrival")})
            elif cfg.get("replay") is not None:
                sink_snap = snapshot_kv(pl, 0, sink) if cfg.get("sinkxfer") else None
                session, ms, seed_bytes, replayed = runner.replay_restart(c, cfg["replay"], cfg["sink0"], cfg.get("sinkhist", False), cfg.get("pos", False))
                info["bytes_withheld"] = sum(v for k2, v in inv.items() if k2 != "prompt_embeds_bytes")
                if sink_snap is not None:
                    moved = force_copy_kv(pl, sink_snap)
                    info["bytes_withheld"] -= moved
                    info["sink_transfer_bytes"] = moved
                    info["events"].append({"call": c, "sink_transferred_bytes": moved})
                info["seed_bytes"] = seed_bytes
                info["replay_ms"] = ms
                info["events"].append({"call": c, "replay_ms": ms, "seed_bytes": seed_bytes, "replayed_calls": replayed, "sink0": cfg["sink0"]})
                # fall through: chunk M itself has not been consumed yet
            elif cfg["restart"]:
                session, frames, ms = runner.restart_at(session, c)
                info["bytes_withheld"] = sum(v for k2, v in inv.items() if k2 != "prompt_embeds_bytes")
                info["events"].append({"call": c, "restart_ms": ms})
                # The restart denoises chunk M synchronously; the baseline emits chunk M at call M+(k-1).
                # Score it there and record the k-1 missing calls as the bubble.
                lag = len(pl.denoising_step_list) - 1
                for gap in range(lag):
                    rows.extend(score(name, c + gap, M, None, baseline, runner))
                frames_out.append(frames)
                restart_frames = (c + lag, frames)
                continue
            if cfg.get("no_refresh"):
                for block in pl.generator.model.blocks:
                    block.self_attn.adapt_sink_thr = -1  # restored by the next prepare() via _initialize_kv_cache
                info["events"].append({"call": c, "adaptive_sink_refresh": "disabled"})
            for comp in cfg["drop"]:
                info["bytes_withheld"] += apply_drop(pl, comp, sink, n)
            for comp, d in cfg["delay"]:
                lo, hi = slot_range(comp, sink, n)
                snap = snapshot_kv(pl, lo, hi)
                info["bytes_withheld"] += zero_kv_slots(pl, lo, hi)
                pending.append((c + d, comp, snap))
            info["events"].append({"call": c, "applied": cfg})

        still_pending = []
        for due, comp, snap in pending:
            if c == due:
                if comp == "true_sink_swap":
                    res = {"swapped_bytes": force_copy_kv(pl, snap)}
                else:
                    res = restore_kv(pl, snap)
                info["events"].append({"call": c, "restored": comp, **res})
            else:
                still_pending.append((due, comp, snap))
        pending = still_pending

        frames = runner.step(session, c)
        if restart_frames is not None and c == restart_frames[0]:
            # pipeline is still refilling: the baseline-aligned frames for this call are the restart's own output
            assert frames is None
            frames = restart_frames[1]
            restart_frames = None
        rows.extend(score(name, c, M, frames, baseline, runner))
        if c >= M:
            frames_out.append(frames if frames is not None else None)
        if c == M or (c > M and (c - M) in (1, 4, 16)):
            vals = [float(r["psnr"]) for r in rows if r["call"] == c and r["psnr"] != ""]
            log(f"  {name}: call {c} (M{c - M:+d}) " + (f"psnr {np.mean(vals):.1f}" if vals else "no output"))
    return rows, info | {"frames": frames_out}


def slot_range(comp: str, sink: int, n: int) -> tuple[int, int]:
    return {"kv_recent": (sink, n), "kv_sink": (0, sink), "kv_all": (0, n)}[comp]


def apply_drop(pl, comp: str, sink: int, n: int) -> int:
    if comp in ("kv_recent", "kv_sink", "kv_all"):
        lo, hi = slot_range(comp, sink, n)
        return zero_kv_slots(pl, lo, hi)
    if comp in ("vae_enc", "vae_dec", "vae_all"):
        return zero_vae_cache(pl, comp[len("vae_"):])
    if comp == "inflight":
        return zero_inflight(pl)
    raise ValueError(comp)


def score(name: str, c: int, M: int, frames, baseline: dict, runner=None) -> list[dict]:
    """PSNR vs baseline for every call; SSIM vs baseline and SSIM vs the INPUT frame (absolute fidelity,
    independent of which valid stream the baseline happened to be) only from M on (SSIM is slow)."""
    ref = baseline.get(c)
    rows = []
    if ref is None:
        return rows
    if frames is None:
        for f in range(ref.shape[0]):
            rows.append({"config": name, "call": c, "rel_call": c - M, "frame": f, "psnr": "", "ssim": "", "ssim_in": "", "missing": 1})
        return rows
    nf = min(ref.shape[0], frames.shape[0])
    inp = runner.input_frames_for_output_call(c) if (runner is not None and c >= M) else None
    for f in range(nf):
        a = ref[f].astype(np.float32) / 255.0
        b = frames[f].astype(np.float32) / 255.0
        row = {"config": name, "call": c, "rel_call": c - M, "frame": f, "psnr": f"{psnr(a, b):.3f}", "ssim": "", "ssim_in": "", "missing": 0}
        if c >= M:
            row["ssim"] = f"{ssim(a, b):.4f}"
            if inp is not None and f < inp.shape[0]:
                row["ssim_in"] = f"{ssim(inp[f].astype(np.float32) / 255.0, b):.4f}"
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- summary
def summary_drift(rows):
    per = {}
    for r in rows:
        if r["psnr"] != "":
            per.setdefault(int(r["call"]), []).append(float(r["psnr"]))
    for c in sorted(per):
        if np.mean(per[c]) < 60.0:
            return c
    return "never (bit-exact)" if per else "n/a"


def summarize(all_rows: list[dict], infos: dict, out_dir: Path, args, static: dict):
    by_cfg: dict[str, list[dict]] = {}
    for r in all_rows:
        by_cfg.setdefault(r["config"], []).append(r)

    def mean_psnr(rows, lo, hi):
        vals = [float(r["psnr"]) for r in rows if lo <= r["rel_call"] <= hi and r["psnr"] != ""]
        return float(np.mean(vals)) if vals else float("nan")

    def mean_ssim(rows, lo, hi):
        vals = [float(r["ssim"]) for r in rows if lo <= r["rel_call"] <= hi and r["ssim"] != ""]
        return float(np.mean(vals)) if vals else float("nan")

    def missing(rows):
        return sum(int(r["missing"]) for r in rows)

    def mean_ssim_in(rows, lo, hi):
        vals = [float(r["ssim_in"]) for r in rows if lo <= r["rel_call"] <= hi and r.get("ssim_in")]
        return float(np.mean(vals)) if vals else float("nan")

    def first_call_below(rows, thr):
        per = {}
        for r in rows:
            if r["psnr"] != "":
                per.setdefault(int(r["call"]), []).append(float(r["psnr"]))
        for c in sorted(per):
            if np.mean(per[c]) < thr:
                return c
        return None

    floor = mean_psnr(by_cfg.get("repeat", []), 0, args.post_chunks - 1)
    valid_div = mean_psnr(by_cfg.get("seed_shift", []), 0, args.post_chunks - 1)
    summary = {}
    for name, rows in by_cfg.items():
        per_call = {}
        for r in rows:
            if r["psnr"] != "":
                per_call.setdefault(r["rel_call"], []).append(float(r["psnr"]))
        recovery = None
        for rc in sorted(per_call):
            if np.mean(per_call[rc]) >= floor - 1.0:
                recovery = rc
                break
        summary[name] = {
            "bytes_withheld_mb": infos[name]["bytes_withheld"] / MB,
            "psnr_M0": mean_psnr(rows, 0, 0),
            "psnr_M0_3": mean_psnr(rows, 0, 3),
            "psnr_M4_15": mean_psnr(rows, 4, 15),
            "psnr_M16_end": mean_psnr(rows, 16, 10**6),
            "ssim_M0_3": mean_ssim(rows, 0, 3),
            "ssim_M16_end": mean_ssim(rows, 16, 10**6),
            "ssim_in_M0_3": mean_ssim_in(rows, 0, 3),
            "ssim_in_M16_end": mean_ssim_in(rows, 16, 10**6),
            "first_call_psnr_below_60": first_call_below(rows, 60.0),
            "seed_mb": infos[name].get("seed_bytes", 0) / MB,
            "arrival": next((e.get("arrival") for e in infos[name]["events"] if "placeholder" in e), None),
            "psnr_M0_7": mean_psnr(rows, 0, 7),
            "sink_transfer_mb": infos[name].get("sink_transfer_bytes", 0) / MB,
            "replay_ms": infos[name].get("replay_ms"),
            "missing_frames": missing(rows),
            "recovery_rel_call": recovery,
            "events": infos[name]["events"],
        }

    L = [f"# State ablation at migration chunk M={args.migration_chunk}, {args.post_chunks} chunks after, k={static['k']}\n",
         f"Generated {time.strftime('%Y-%m-%d %H:%M:%S %Z')}; GPU {static['gpu_name']}; commit {static['git_commit']}; "
         f"video {args.video_path}; seed {args.seed}. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.\n",
         f"Determinism floor (`repeat` mean PSNR over M..M+{args.post_chunks - 1}): **{floor:.2f} dB** (99 = bit-exact). "
         f"Valid-but-different reference (`seed_shift`, same state, different noise): **{valid_div:.2f} dB**; an ablation at or above this level diverged no more than an equally valid stream would. "
         f"Recovery = first call whose mean PSNR >= floor - 1 dB.\n",
         f"Absolute reference: baseline SSIM vs INPUT video over M.. = **{static.get('baseline_ssim_vs_input_M_on')}**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).\n",
         f"Drift onset: first call where `repeat` falls below 60 dB vs baseline = {summary_drift(by_cfg.get('repeat', []))}.\n",
         "| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = [n for n in DEFAULT_CONFIGS if n in summary] + [n for n in summary if n not in DEFAULT_CONFIGS]
    for name in order:
        s = summary[name]
        rp = f"{s['replay_ms']:.0f}" if s.get("replay_ms") is not None else "-"
        L.append(f"| {name} | {s['bytes_withheld_mb']:,.1f} | {s['seed_mb']:.1f} | {rp} | {s['psnr_M0']:.1f} | {s['psnr_M0_3']:.1f} | {s['psnr_M4_15']:.1f} | {s['psnr_M16_end']:.1f} | "
                 f"{s['ssim_M0_3']:.3f} | {s['ssim_M16_end']:.3f} | {s['ssim_in_M0_3']:.3f} | {s['ssim_in_M16_end']:.3f} | {s['missing_frames']} | {s['recovery_rel_call']} |")
    inv = infos[next(iter(infos))].get("inventory_at_M", {})
    L.append("\nInventory at M (bytes): " + ", ".join(f"{k2} {v / MB:,.0f} MB" for k2, v in inv.items()))
    L.append("\nDelay restores: " + "; ".join(f"{n}: {[e for e in summary[n]['events'] if 'restored' in e]}" for n in summary if n.startswith("delay_")))
    first_info = infos[next(iter(infos))]
    if "slot_pos_at_M" in first_info:
        L.append(f"\nRing-buffer slot positions at M (layer 0): {first_info['slot_pos_at_M']}; adaptive sink refresh fired at baseline calls {static.get('sink_refresh_calls')} (sinkhist configs replay through the last one before M).")
    # Transfer-vs-replay crossover (analytic, from measured bytes and replay time)
    replay_cfgs = [n for n in order if summary[n].get("replay_ms") is not None]
    if replay_cfgs:
        full_bytes = sum(v for k2, v in inv.items() if k2 != "prompt_embeds_bytes")
        rtt_ms = 10.0
        bws = [0.1, 1.0, 10.0, 100.0]  # Gbps
        L.append(f"\n## Transfer vs seed+replay (analytic; full state {full_bytes / MB:,.0f} MB, RTT {rtt_ms:.0f} ms, no decompression/serialization cost)\n")
        L.append("| config | seed MB | sink xfer MB | replay ms | " + " | ".join(f"T_move @{bw:g} Gbps" for bw in bws) + " | " + " | ".join(f"T_recon @{bw:g} Gbps" for bw in bws) + " |")
        L.append("|---|---|---|---|" + "---|" * (2 * len(bws)))
        for n in replay_cfgs:
            s2 = summary[n]
            t_move = [rtt_ms + full_bytes * 8 / (bw * 1e9) * 1e3 for bw in bws]
            t_rec = [rtt_ms + (s2["seed_mb"] + s2.get("sink_transfer_mb", 0)) * MB * 8 / (bw * 1e9) * 1e3 + s2["replay_ms"] for bw in bws]
            L.append(f"| {n} | {s2['seed_mb']:.1f} | {s2.get('sink_transfer_mb', 0):.0f} | {s2['replay_ms']:.0f} | " + " | ".join(f"{t:,.0f}" for t in t_move) + " | " + " | ".join(f"{t:,.0f}" for t in t_rec) + " |")
        L.append("\nContinuity of each replay config is in the main table (compare with `repeat`, the full-state-transfer equivalent).")
    L.append("\nGates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.\n")
    ph_cfgs = [n for n in order if summary[n].get("arrival") is not None or n.startswith("ph_")]
    if ph_cfgs:
        L.append("\n## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)\n")
        L.append("| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |")
        L.append("|---|---|---|---|---|---|---|")
        for n in ph_cfgs:
            rws = by_cfg[n]
            D = summary[n].get("arrival")
            per = {}
            for r in rws:
                if r["psnr"] != "":
                    per.setdefault(r["rel_call"], []).append(float(r["psnr"]))
            if D is None:
                gap_lo, gap_hi, rejoin, tail = 0, args.post_chunks - 1, "n/a (never swapped)", float("nan")
                L.append(f"| {n} | - | {mean_psnr(rws, 0, 7):.1f} (M+0..7) | {mean_ssim(rws, 0, 7):.3f} | {rejoin} | {mean_psnr(rws, 16, 10**6):.1f} (M+16..) | {mean_ssim(rws, 16, 10**6):.3f} |")
                continue
            rejoin = None
            for rc in sorted(per):
                if rc >= D and np.mean(per[rc]) >= 30.0:
                    rejoin = rc - D
                    break
            L.append(f"| {n} | {D} | {mean_psnr(rws, 0, max(D - 1, 0)):.1f} | {mean_ssim(rws, 0, max(D - 1, 0)):.3f} | {rejoin} | {mean_psnr(rws, D + 8, 10**6):.1f} | {mean_ssim(rws, D + 8, 10**6):.3f} |")
    xf = [n for n in order if n.startswith("xfer_") or n.startswith("replay_")]
    if xf:
        L.append("\n## Natural refill vs replay: early continuity (M+0..7)\n")
        L.append("| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |")
        L.append("|---|---|---|---|---|---|")
        for n in xf:
            s2 = summary[n]
            mv = infos[n].get("bytes_moved")
            mv_s = ", ".join(f"{k2} {v / MB:,.0f} MB" for k2, v in mv.items() if v) if mv else f"seed {s2['seed_mb']:.0f} MB, replay {s2.get('replay_ms') or 0:.0f} ms"
            L.append(f"| {n} | {s2['psnr_M0']:.1f} | {s2['psnr_M0_7']:.1f} | {s2['ssim_M0_3']:.3f} | {s2['psnr_M16_end']:.1f} | {mv_s} |")
    (out_dir / "ablation_summary.md").write_text("\n".join(L) + "\n")
    with open(out_dir / "ablation_summary.json", "w") as fh:
        json.dump({"floor_psnr": floor, "seed_shift_psnr": valid_div, "per_config": summary}, fh, indent=2, default=str)
    return summary


# --------------------------------------------------------------------------- main
def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config_path", type=str, default=str(REPO_ROOT / "configs/wan_causal_dmd_v2v.yaml"))
    p.add_argument("--checkpoint_folder", type=str, default=str(REPO_ROOT / "ckpts/wan_causal_dmd_v2v"))
    p.add_argument("--prompt_file_path", type=str, default=str(REPO_ROOT / "examples/prompt.txt"))
    p.add_argument("--video_path", type=str, default=str(REPO_ROOT / "examples/original.mp4"))
    p.add_argument("--output_folder", type=str, default=str(REPO_ROOT / "results/state_migration"))
    p.add_argument("--noise_scale", type=float, default=0.8)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--width", type=int, default=832)
    p.add_argument("--fps", type=int, default=16)
    p.add_argument("--step", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--gpu_id", type=int, default=None)
    p.add_argument("--model_type", type=str, default="T2V-1.3B")
    p.add_argument("--fixed_noise_scale", action="store_true", default=False)
    p.add_argument("--t2v", action="store_true", default=False)
    p.add_argument("--profile", action="store_true", default=False)
    p.add_argument("--use_taehv", action="store_true", default=False)
    p.add_argument("--normalize_latents", action="store_true", default=False)
    p.add_argument("--use_tensorrt", action="store_true", default=False)
    p.add_argument("--fast", action="store_true", default=False)
    p.add_argument("--out_dir", type=str, default=str(REPO_ROOT / "results/state_migration"))
    p.add_argument("--migration_chunk", type=int, default=30)
    p.add_argument("--post_chunks", type=int, default=40)
    p.add_argument("--configs", type=str, default=None, help="comma list; overrides --preset")
    p.add_argument("--preset", type=str, choices=["ablation", "reconstruct", "mechanism"], default="ablation")
    p.add_argument("--save_video", action="store_true", default=False)
    return p.parse_args()


def main():
    args = parse_args()
    torch.set_grad_enabled(False)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[ablation] use_deterministic_algorithms unavailable: {exc}")
    if not torch.cuda.is_available():
        raise SystemExit("CUDA required; local runs are not evidence.")
    if args.gpu_id is not None:
        torch.cuda.set_device(args.gpu_id)
    device = torch.device(f"cuda:{torch.cuda.current_device()}")
    config = merge_cli_config(args.config_path, args)
    config.profile = False
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_fh = open(out_dir / "ablation_log.txt", "a")

    def log(msg):
        print(msg, flush=True)
        log_fh.write(msg + "\n")
        log_fh.flush()

    set_seed(args.seed)
    pm = SingleGPUInferencePipeline(config, device)
    pm.load_model(args.checkpoint_folder)
    pl = pm.pipeline
    k = len(pl.denoising_step_list)
    if args.use_taehv:
        log("WARNING: TAEHV wrapper has no _enc_feat_map/_feat_map; vae_* configs will withhold 0 bytes.")

    chunk = pm.base_chunk_size * pl.num_frame_per_block
    total_calls = args.migration_chunk + args.post_chunks
    needed = 1 + chunk + total_calls * chunk
    video = load_mp4_as_tensor(args.video_path, resize_hw=(args.height, args.width))
    src_frames = int(video.shape[1])
    reps = (needed + src_frames - 1) // src_frames
    if reps > 1:
        video = video.repeat(1, reps, 1, 1)
    video = video[:, :needed].to(torch.bfloat16).unsqueeze(0).pin_memory()
    prompt = TextDataset(args.prompt_file_path)[0]
    runner = Runner(pm, video, prompt, args, device)

    static = {
        "k": k, "denoising_step_list": [int(s) for s in pl.denoising_step_list], "args": vars(args),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip(),
        "gpu_name": torch.cuda.get_device_name(device), "torch": torch.__version__, "hostname": platform.node(),
        "source_frames": src_frames, "needed_frames": needed, "chunk": chunk,
    }

    # Baseline (uninterrupted).
    log(f"[ablation] baseline: {total_calls} calls, M={args.migration_chunk}, k={k}")
    session = runner.start()
    baseline: dict[int, np.ndarray] = {}
    t0 = time.perf_counter()
    sink_pos_hist = {}
    for c in range(total_calls):
        frames = runner.step(session, c)
        if frames is not None:
            baseline[c] = frames
        sink_pos_hist[c] = slot_positions(pl)["sink_slot_pos"]
        runner.noise_hist[c] = float(session.noise_scale)
    refresh_calls = [c for c in range(1, total_calls) if sink_pos_hist[c] != sink_pos_hist[c - 1]]
    pre_M_refresh = [c for c in refresh_calls if c < args.migration_chunk]
    runner.last_refresh_call = pre_M_refresh[-1] if pre_M_refresh else -1
    static["sink_refresh_calls"] = refresh_calls
    static["sink_pos_at_M_baseline"] = sink_pos_hist.get(args.migration_chunk - 1)
    log(f"[ablation] adaptive sink refresh fired at calls {refresh_calls}; last before M: {runner.last_refresh_call}")
    log(f"[ablation] baseline done in {time.perf_counter() - t0:.0f} s; {len(baseline)} calls with output")
    baseline_in_ssim = {}
    for c in sorted(baseline):
        if c >= args.migration_chunk:
            inp = runner.input_frames_for_output_call(c)
            if inp is not None:
                baseline_in_ssim[c] = float(np.mean([ssim(inp[f].astype(np.float32) / 255.0, baseline[c][f].astype(np.float32) / 255.0) for f in range(min(inp.shape[0], baseline[c].shape[0]))]))
    static["baseline_ssim_vs_input_M_on"] = float(np.mean(list(baseline_in_ssim.values()))) if baseline_in_ssim else None
    log(f"[ablation] baseline SSIM vs input (M on): {static['baseline_ssim_vs_input_M_on']}")
    static["inventory_baseline_end"] = inventory_bytes(pl)

    preset = {"ablation": DEFAULT_CONFIGS, "reconstruct": RECONSTRUCT_CONFIGS, "mechanism": MECHANISM_CONFIGS}[args.preset]
    configs = [c.strip() for c in args.configs.split(",") if c.strip()] if args.configs else list(preset)
    all_rows: list[dict] = []
    infos: dict[str, dict] = {}
    csv_path = out_dir / "ablation_raw.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["config", "call", "rel_call", "frame", "psnr", "ssim", "ssim_in", "missing"])
        writer.writeheader()
        for name in configs:
            if name == "drop_inflight" and k < 2:
                log(f"[ablation] skip {name}: k={k} has no in-flight rows")
                continue
            log(f"[ablation] config {name}")
            t0 = time.perf_counter()
            rows, info = run_config(name, runner, args.migration_chunk, args.post_chunks, baseline, log)
            frames_out = info.pop("frames")
            info["run_s"] = time.perf_counter() - t0
            infos[name] = info
            all_rows.extend(rows)
            writer.writerows(rows)
            fh.flush()
            if args.save_video:
                from diffusers.utils import export_to_video  # noqa: WPS433

                vid_dir = out_dir / "videos"
                vid_dir.mkdir(exist_ok=True)
                frames = [f for f in frames_out if f is not None]
                if frames:
                    export_to_video(np.concatenate(frames, 0).astype(np.float32) / 255.0, str(vid_dir / f"{name}.mp4"), fps=args.fps)
    if args.save_video:
        from diffusers.utils import export_to_video  # noqa: WPS433

        frames = [baseline[c] for c in sorted(baseline) if c >= args.migration_chunk]
        export_to_video(np.concatenate(frames, 0).astype(np.float32) / 255.0, str(out_dir / "videos" / "baseline.mp4"), fps=args.fps)

    static["infos"] = infos
    with open(out_dir / "ablation_static.json", "w") as fh:
        json.dump(static, fh, indent=2, default=str)
    summary = summarize(all_rows, infos, out_dir, args, static)
    log("[ablation] done -> " + str(out_dir / "ablation_summary.md"))
    for name, s in summary.items():
        log(f"  {name:22s} withheld {s['bytes_withheld_mb']:7.0f} MB  PSNR M+0..3 {s['psnr_M0_3']:5.1f}  M+16.. {s['psnr_M16_end']:5.1f}  recovery {s['recovery_rel_call']}")


if __name__ == "__main__":
    main()
