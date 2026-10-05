#!/usr/bin/env python3
"""Phase 0A: single-session resource characterization of Stream-Batch vs denoising-step count k.

Runs ONE k per process (launch once per k, see tools/run_phase0a.sh) so that CUDA allocator
state does not leak between configurations. Uses the official single-GPU session API
(`SingleGPUInferencePipeline.start_stream_session` / `run_stream_batch`) unchanged; timing is
injected by wrapping three bound methods as instance attributes.

Outputs (appended / written under --out_dir):
    phase0a_raw.csv            one row per chunk (warm-up and measured), all k share the file
    phase0a_static_k{k}.json   per-process static facts: config, versions, weight bytes,
                               memory checkpoints, tensor inventory (logical vs physical)
    phase0a_output_k{k}.mp4    decoded measured frames (for later quality evaluation)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

from models.data import TextDataset  # noqa: E402
from models.util import set_seed  # noqa: E402
from streamv2v.inference import SingleGPUInferencePipeline, compute_noise_scale_and_step  # noqa: E402
from streamv2v.inference_common import load_mp4_as_tensor, merge_cli_config  # noqa: E402

MB = 1024.0 * 1024.0

CSV_COLUMNS = [
    "k",
    "chunk_idx",
    "phase",
    "wall_time_unix",
    "current_step",
    "noise_scale",
    "frames_in",
    "frames_out",
    "vae_encode_ms",
    "dit_ms",
    "vae_decode_ms",
    "end_to_end_chunk_ms",
    "achieved_fps",
    "allocated_boundary_mb",
    "reserved_boundary_mb",
    "peak_allocated_chunk_mb",
    "peak_reserved_chunk_mb",
    "transient_mb",
    "device_used_mb",
    "device_free_mb",
    "kv_cache_physical_mb",
    "kv_cache_logical_mb",
    "crossattn_physical_mb",
    "crossattn_logical_mb",
    "hidden_state_mb",
    "prompt_embeds_physical_mb",
    "vae_feat_cache_mb",
    "session_state_physical_mb",
]


# --------------------------------------------------------------------------- helpers
def _git(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *cmd], cwd=REPO_ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _nvidia_smi_query() -> dict:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,clocks.sm,clocks.mem,power.limit",
                "--format=csv,noheader",
            ],
            text=True,
        ).strip()
        return {"nvidia_smi": out}
    except Exception as exc:  # noqa: BLE001
        return {"nvidia_smi": f"unavailable: {exc}"}


def _storage_key(t: torch.Tensor) -> tuple[int, int]:
    st = t.untyped_storage()
    return (st.data_ptr(), st.nbytes())


def tensor_bytes(tensors: list[torch.Tensor]) -> dict:
    """Logical bytes (numel * itemsize, counts expand() views fully) vs physical bytes
    (unique untyped storages on the current device, counts a storage once)."""
    logical = 0
    seen: set[tuple[int, int]] = set()
    physical = 0
    for t in tensors:
        if t is None or not isinstance(t, torch.Tensor) or not t.is_cuda:
            continue
        logical += t.numel() * t.element_size()
        key = _storage_key(t)
        if key not in seen:
            seen.add(key)
            physical += key[1]
    return {"logical_bytes": logical, "physical_bytes": physical}


def module_param_bytes(module: torch.nn.Module) -> dict:
    tensors = [p for p in module.parameters()] + [b for b in module.buffers()]
    cuda = [t for t in tensors if t.is_cuda]
    return {
        "param_count": sum(p.numel() for p in module.parameters()),
        "cuda_bytes": sum(t.numel() * t.element_size() for t in cuda),
        "cpu_bytes": sum(t.numel() * t.element_size() for t in tensors if not t.is_cuda),
    }


def _flatten_cache_tensors(cache_list, keys) -> list[torch.Tensor]:
    out = []
    if not cache_list:
        return out
    for entry in cache_list:
        for key in keys:
            val = entry.get(key) if isinstance(entry, dict) else None
            if isinstance(val, torch.Tensor):
                out.append(val)
    return out


def _vae_feat_tensors(vae_model) -> list[torch.Tensor]:
    out = []
    for attr in ("_enc_feat_map", "_feat_map"):
        fm = getattr(vae_model, attr, None)
        if isinstance(fm, list):
            out.extend([t for t in fm if isinstance(t, torch.Tensor)])
    return out


def session_inventory(pipeline) -> dict:
    """Per-session live state, split by component, logical vs physical."""
    kv = _flatten_cache_tensors(pipeline.kv_cache1, ("k", "v"))
    kv_meta = _flatten_cache_tensors(pipeline.kv_cache1, ("global_end_index", "local_end_index", "pos"))
    ca = _flatten_cache_tensors(pipeline.crossattn_cache, ("k", "v"))
    hs = [t for t in (pipeline.hidden_states, pipeline.block_x) if isinstance(t, torch.Tensor)]
    idx = [
        t
        for t in (
            getattr(pipeline, "kv_cache_starts", None),
            getattr(pipeline, "kv_cache_ends", None),
            getattr(pipeline, "timestep", None),
        )
        if isinstance(t, torch.Tensor)
    ]
    cond = pipeline.conditional_dict or {}
    pe = [v for v in cond.values() if isinstance(v, torch.Tensor)]
    vae_feat = _vae_feat_tensors(getattr(pipeline.vae, "model", None))

    inv = {
        "kv_cache": tensor_bytes(kv),
        "kv_cache_meta": tensor_bytes(kv_meta),
        "crossattn_cache": tensor_bytes(ca),
        "hidden_state": tensor_bytes(hs),
        "index_tensors": tensor_bytes(idx),
        "prompt_embeds": tensor_bytes(pe),
        "vae_feat_cache": tensor_bytes(vae_feat),
    }
    inv["session_total"] = tensor_bytes(kv + kv_meta + ca + hs + idx + pe + vae_feat)
    if pipeline.kv_cache1:
        k0 = pipeline.kv_cache1[0]["k"]
        inv["kv_row_shape"] = list(k0.shape)
        inv["kv_stride0"] = k0.stride(0)
    if pipeline.crossattn_cache:
        c0 = pipeline.crossattn_cache[0]["k"]
        inv["crossattn_shape"] = list(c0.shape)
        inv["crossattn_stride0"] = c0.stride(0)  # 0 => expand() view shared across rows
    evict = []
    for block in getattr(pipeline.generator.model, "blocks", []):
        ev = getattr(getattr(block, "self_attn", None), "evict_idx", None)
        if isinstance(ev, list):
            evict.append([len(row) for row in ev])
    inv["evict_idx_rows_per_layer"] = evict[:2]
    return inv


def mem_checkpoint(device: torch.device) -> dict:
    torch.cuda.synchronize(device)
    free, total = torch.cuda.mem_get_info(device)
    return {
        "allocated_bytes": torch.cuda.memory_allocated(device),
        "reserved_bytes": torch.cuda.memory_reserved(device),
        "max_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "max_reserved_bytes": torch.cuda.max_memory_reserved(device),
        "device_used_bytes": total - free,
        "device_free_bytes": free,
        "device_total_bytes": total,
    }


class StageTimer:
    """Wrap a callable; synchronize before/after and append elapsed ms to a bucket."""

    def __init__(self, fn, bucket: list, device: torch.device):
        self.fn = fn
        self.bucket = bucket
        self.device = device

    def __call__(self, *args, **kwargs):
        torch.cuda.synchronize(self.device)
        t0 = time.perf_counter()
        out = self.fn(*args, **kwargs)
        torch.cuda.synchronize(self.device)
        self.bucket.append((time.perf_counter() - t0) * 1e3)
        return out


def tile_video(video: torch.Tensor, needed_frames: int) -> torch.Tensor:
    """video: [C, T, H, W]. Repeat along T until at least needed_frames."""
    t = video.shape[1]
    reps = (needed_frames + t - 1) // t
    if reps > 1:
        video = video.repeat(1, reps, 1, 1)
    return video[:, :needed_frames]


# --------------------------------------------------------------------------- main
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Mirror the official CLI so merge_cli_config() produces the same config object.
    p.add_argument("--config_path", type=str, default=str(REPO_ROOT / "configs/wan_causal_dmd_v2v.yaml"))
    p.add_argument("--checkpoint_folder", type=str, default=str(REPO_ROOT / "ckpts/wan_causal_dmd_v2v"))
    p.add_argument("--prompt_file_path", type=str, default=str(REPO_ROOT / "examples/prompt.txt"))
    p.add_argument("--video_path", type=str, default=str(REPO_ROOT / "examples/original.mp4"))
    p.add_argument("--output_folder", type=str, default=str(REPO_ROOT / "results/quality_elastic"))
    p.add_argument("--noise_scale", type=float, default=0.8)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--width", type=int, default=832)
    p.add_argument("--fps", type=int, default=16)
    p.add_argument("--step", type=int, required=True, help="denoising step count k")
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
    # Harness-only options.
    p.add_argument("--out_dir", type=str, default=str(REPO_ROOT / "results/quality_elastic"))
    p.add_argument("--warmup_chunks", type=int, default=10)
    p.add_argument("--measured_chunks", type=int, default=100)
    p.add_argument("--target_fps", type=float, default=16.0, help="only recorded; used by the analyzer")
    p.add_argument("--save_video", action="store_true", default=False)
    p.add_argument("--memory_snapshot", action="store_true", default=False,
                   help="record torch.cuda.memory._record_memory_history and dump a snapshot after warm-up (heavy)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.t2v:
        raise SystemExit("Phase 0A targets the official v2v workload; --t2v is not supported here.")
    torch.set_grad_enabled(False)

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required. Local CPU runs are not valid Phase 0A evidence.")
    if args.gpu_id is not None:
        torch.cuda.set_device(args.gpu_id)
    device = torch.device(f"cuda:{torch.cuda.current_device()}")

    config = merge_cli_config(args.config_path, args)
    config.profile = False  # harness does its own synchronized timing
    k = len([s for s in config.denoising_step_list if int(s) != 0])
    assert k == args.step, f"config truncated to {k} steps but --step {args.step} requested"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    set_seed(args.seed)

    static: dict = {
        "k": k,
        "denoising_step_list": [int(s) for s in config.denoising_step_list],
        "args": vars(args),
        "config": {key: val for key, val in OmegaConf.to_container(config, resolve=True).items()
                   if key not in ("negative_prompt",)},
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_status_short": _git(["status", "--short"]),
        "hostname": platform.node(),
        "python": sys.version,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "gpu_name": torch.cuda.get_device_name(device),
        "gpu_capability": list(torch.cuda.get_device_capability(device)),
        **_nvidia_smi_query(),
        "flash_attn_available": None,
        "command": " ".join(sys.argv),
        "memory_checkpoints": {},
    }
    try:
        from models.wan import causal_model as _cm  # noqa: WPS433

        static["flash_attn_available"] = bool(getattr(_cm, "FLASH_ATTN_AVAILABLE", None))
    except Exception:  # noqa: BLE001
        pass

    # --- M0: CUDA context only
    torch.cuda.synchronize(device)
    static["memory_checkpoints"]["after_cuda_init"] = mem_checkpoint(device)

    # --- build pipeline (weights -> GPU, bf16)
    pipeline_manager = SingleGPUInferencePipeline(config, device)
    pipeline_manager.load_model(args.checkpoint_folder)
    pipeline = pipeline_manager.pipeline
    torch.cuda.synchronize(device)
    static["memory_checkpoints"]["after_model_load"] = mem_checkpoint(device)  # == M_fixed
    static["weights"] = {
        "generator": module_param_bytes(pipeline.generator),
        "text_encoder": module_param_bytes(pipeline.text_encoder),
        "vae": module_param_bytes(pipeline.vae),
    }
    static["model_geometry"] = {
        "frame_seq_length": int(pipeline.frame_seq_length),
        "num_kv_cache": int(pipeline.num_kv_cache),
        "kv_cache_length": int(pipeline.kv_cache_length),
        "num_sink_tokens": int(pipeline.num_sink_tokens),
        "num_transformer_blocks": int(pipeline.num_transformer_blocks),
        "num_heads": int(pipeline.num_heads),
        "num_frame_per_block": int(pipeline.num_frame_per_block),
        "base_chunk_size": int(pipeline_manager.base_chunk_size),
        "t_refresh": int(pipeline_manager.t_refresh),
    }

    # --- input video on HOST (official main() keeps it on GPU; see audit section 5)
    chunk_size = pipeline_manager.base_chunk_size * pipeline.num_frame_per_block
    first_batch_frames = 1 + chunk_size
    total_chunks = args.warmup_chunks + args.measured_chunks
    needed_frames = first_batch_frames + total_chunks * chunk_size
    video = load_mp4_as_tensor(args.video_path, resize_hw=(args.height, args.width))  # [C,T,H,W] float32
    static["input_video"] = {"path": args.video_path, "source_frames": int(video.shape[1]),
                             "needed_frames": needed_frames, "tiled": bool(video.shape[1] < needed_frames)}
    video = tile_video(video, needed_frames).to(torch.bfloat16).unsqueeze(0).pin_memory()  # [1,C,T,H,W]

    prompt = TextDataset(args.prompt_file_path)[0]
    static["prompt"] = prompt

    # --- timing hooks (instance attributes; no source edits)
    enc_ms: list[float] = []
    dit_ms: list[float] = []
    dec_ms: list[float] = []
    prep_ms: list[float] = []
    pipeline.vae.stream_encode = StageTimer(pipeline.vae.stream_encode, enc_ms, device)
    pipeline.inference_stream = StageTimer(pipeline.inference_stream, dit_ms, device)
    pipeline.prepare = StageTimer(pipeline.prepare, prep_ms, device)  # session start only
    pipeline.vae.stream_decode_to_pixel = StageTimer(pipeline.vae.stream_decode_to_pixel, dec_ms, device)

    if args.memory_snapshot:
        torch.cuda.memory._record_memory_history(max_entries=200000)

    # --- session start (official path)
    torch.cuda.reset_peak_memory_stats(device)
    first_images = video[:, :, :first_batch_frames].to(device, non_blocking=True)
    torch.cuda.synchronize(device)
    t0 = time.perf_counter()
    session, initial_video = pipeline_manager.start_stream_session(prompt, first_images, args.noise_scale)
    torch.cuda.synchronize(device)
    static["session_start_ms"] = (time.perf_counter() - t0) * 1e3
    static["session_start_stage_ms"] = {"vae_encode": sum(enc_ms), "prepare_total": sum(prep_ms), "vae_decode": sum(dec_ms)}
    static["memory_checkpoints"]["after_session_start"] = mem_checkpoint(device)
    static["inventory_after_session_start"] = session_inventory(pipeline)
    enc_ms.clear(); dit_ms.clear(); dec_ms.clear()
    del first_images

    num_steps = len(pipeline.denoising_step_list)
    csv_path = out_dir / "phase0a_raw.csv"
    write_header = not csv_path.exists()
    decoded_measured: list[np.ndarray] = []
    frame_cursor = first_batch_frames

    with open(csv_path, "a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()

        for chunk_idx in range(total_chunks):
            phase = "warmup" if chunk_idx < args.warmup_chunks else "measured"
            images = video[:, :, frame_cursor:frame_cursor + chunk_size].to(device, non_blocking=True)
            frame_cursor += chunk_size
            torch.cuda.synchronize(device)
            torch.cuda.reset_peak_memory_stats(device)
            enc_ms.clear(); dit_ms.clear(); dec_ms.clear()

            # The step chosen for this chunk is content-adaptive; reproduce the official call to log it.
            _, logged_step = compute_noise_scale_and_step(
                torch.cat([session.last_image, images], dim=2), chunk_size + 1, chunk_size,
                float(session.noise_scale), float(session.init_noise_scale))

            t_start = time.perf_counter()
            outputs = pipeline_manager.run_stream_batch(session, images)
            torch.cuda.synchronize(device)
            e2e_ms = (time.perf_counter() - t_start) * 1e3

            peak_alloc = torch.cuda.max_memory_allocated(device)
            peak_res = torch.cuda.max_memory_reserved(device)
            del images
            boundary = mem_checkpoint(device)
            inv = session_inventory(pipeline)
            frames_out = int(sum(o.shape[0] for o in outputs))
            if phase == "measured" and args.save_video:
                decoded_measured.extend(outputs)

            row = {
                "k": k,
                "chunk_idx": chunk_idx,
                "phase": phase,
                "wall_time_unix": f"{time.time():.3f}",
                "current_step": logged_step,
                "noise_scale": f"{float(session.noise_scale):.5f}",
                "frames_in": chunk_size,
                "frames_out": frames_out,
                "vae_encode_ms": f"{sum(enc_ms):.3f}",
                "dit_ms": f"{sum(dit_ms):.3f}",
                "vae_decode_ms": f"{sum(dec_ms):.3f}" if dec_ms else "",
                "end_to_end_chunk_ms": f"{e2e_ms:.3f}",
                "achieved_fps": f"{chunk_size / (e2e_ms / 1e3):.3f}",
                "allocated_boundary_mb": f"{boundary['allocated_bytes'] / MB:.1f}",
                "reserved_boundary_mb": f"{boundary['reserved_bytes'] / MB:.1f}",
                "peak_allocated_chunk_mb": f"{peak_alloc / MB:.1f}",
                "peak_reserved_chunk_mb": f"{peak_res / MB:.1f}",
                "transient_mb": f"{(peak_alloc - boundary['allocated_bytes']) / MB:.1f}",
                "device_used_mb": f"{boundary['device_used_bytes'] / MB:.1f}",
                "device_free_mb": f"{boundary['device_free_bytes'] / MB:.1f}",
                "kv_cache_physical_mb": f"{inv['kv_cache']['physical_bytes'] / MB:.1f}",
                "kv_cache_logical_mb": f"{inv['kv_cache']['logical_bytes'] / MB:.1f}",
                "crossattn_physical_mb": f"{inv['crossattn_cache']['physical_bytes'] / MB:.1f}",
                "crossattn_logical_mb": f"{inv['crossattn_cache']['logical_bytes'] / MB:.1f}",
                "hidden_state_mb": f"{inv['hidden_state']['physical_bytes'] / MB:.3f}",
                "prompt_embeds_physical_mb": f"{inv['prompt_embeds']['physical_bytes'] / MB:.2f}",
                "vae_feat_cache_mb": f"{inv['vae_feat_cache']['physical_bytes'] / MB:.1f}",
                "session_state_physical_mb": f"{inv['session_total']['physical_bytes'] / MB:.1f}",
            }
            writer.writerow(row)
            fh.flush()

            if chunk_idx == args.warmup_chunks - 1:
                static["memory_checkpoints"]["after_warmup"] = boundary
                static["inventory_after_warmup"] = inv
                if args.memory_snapshot:
                    snap = out_dir / f"phase0a_memsnapshot_k{k}.pickle"
                    torch.cuda.memory._dump_snapshot(str(snap))
                    torch.cuda.memory._record_memory_history(enabled=None)
                    static["memory_snapshot_path"] = str(snap)

    static["memory_checkpoints"]["end"] = mem_checkpoint(device)
    static["memory_stats_end"] = {key: val for key, val in torch.cuda.memory_stats(device).items()
                                  if key.endswith(".all.current") or key.endswith(".all.peak")}
    static["num_steps_runtime"] = num_steps
    static["chunk_size"] = chunk_size

    if args.save_video and decoded_measured:
        from diffusers.utils import export_to_video  # noqa: WPS433

        frames = np.concatenate(decoded_measured, axis=0)
        export_to_video(frames, str(out_dir / f"phase0a_output_k{k}.mp4"), fps=args.fps)
        static["output_video"] = str(out_dir / f"phase0a_output_k{k}.mp4")

    with open(out_dir / f"phase0a_static_k{k}.json", "w") as fh:
        json.dump(static, fh, indent=2, default=str)

    print(f"[phase0a] k={k} done. allocated@boundary={static['memory_checkpoints']['end']['allocated_bytes'] / MB:.0f} MB, "
          f"M_fixed={static['memory_checkpoints']['after_model_load']['allocated_bytes'] / MB:.0f} MB, "
          f"session_start={static['session_start_ms']:.0f} ms")


if __name__ == "__main__":
    main()
