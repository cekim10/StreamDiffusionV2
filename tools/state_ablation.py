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


def zero_inflight(pl) -> int:
    hs = pl.hidden_states
    if hs is None or hs.shape[0] < 2:
        return 0
    view = hs[1:]
    nbytes = view.numel() * view.element_size()
    view.zero_()
    return nbytes


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
        "inflight_bytes": (pl.hidden_states[1:].numel() * pl.hidden_states.element_size()) if pl.hidden_states is not None and pl.hidden_states.shape[0] > 1 else 0,
        "crossattn_bytes": sum(e["k"].untyped_storage().nbytes() + e["v"].untyped_storage().nbytes() for e in pl.crossattn_cache),
        "prompt_embeds_bytes": pl.conditional_dict["prompt_embeds"].numel() * pl.conditional_dict["prompt_embeds"].element_size(),
    }


# --------------------------------------------------------------------------- configs
def parse_config(name: str) -> dict:
    """Return {'drop': [...], 'delay': [(component, d)], 'restart': bool}."""
    if name in ("repeat", "baseline"):
        return {"drop": [], "delay": [], "restart": False}
    if name == "cold_restart":
        return {"drop": [], "delay": [], "restart": True}
    if name.startswith("drop_"):
        comp = name[len("drop_"):]
        comps = ["kv_all", "vae_all", "inflight"] if comp == "all" else [comp]
        return {"drop": comps, "delay": [], "restart": False}
    if name.startswith("delay_"):
        body = name[len("delay_"):]
        comp, d = body.rsplit("_", 1)
        return {"drop": [], "delay": [(comp, int(d))], "restart": False}
    raise ValueError(f"unknown config {name}")


DEFAULT_CONFIGS = [
    "repeat",
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

    def frames_for_call(self, c: int) -> torch.Tensor:
        lo = self.first + c * self.chunk
        return self.video[:, :, lo:lo + self.chunk].to(self.device, non_blocking=True)

    def start(self):
        set_seed(self.args.seed)
        torch.manual_seed(self.args.seed)
        images = self.video[:, :, :self.first].to(self.device)
        session, _ = self.pm.start_stream_session(self.prompt, images, self.args.noise_scale)
        return session

    def step(self, session, c: int):
        torch.manual_seed(self.args.seed * 100003 + c + 1)  # identical noise per call in every run
        images = self.frames_for_call(c)
        outs = self.pm.run_stream_batch(session, images)
        if not outs:
            return None
        return to_uint8(np.concatenate(outs, axis=0))

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
    session = runner.start()
    rows: list[dict] = []
    info = {"config": name, "bytes_withheld": 0, "events": []}
    pending: list[tuple[int, str, dict]] = []  # (call to restore at, component, snapshot)
    frames_out: list[np.ndarray] = []

    for c in range(M + N):
        if c == M:
            inv = inventory_bytes(pl)
            info["inventory_at_M"] = inv
            if cfg["restart"]:
                session, frames, ms = runner.restart_at(session, c)
                info["bytes_withheld"] = sum(v for k2, v in inv.items() if k2 != "prompt_embeds_bytes")
                info["events"].append({"call": c, "restart_ms": ms})
                frames_out.append(frames)
                rows.extend(score(name, c, M, frames, baseline))
                continue
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
                res = restore_kv(pl, snap)
                info["events"].append({"call": c, "restored": comp, **res})
            else:
                still_pending.append((due, comp, snap))
        pending = still_pending

        frames = runner.step(session, c)
        if c >= M:
            frames_out.append(frames if frames is not None else None)
            rows.extend(score(name, c, M, frames, baseline))
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


def score(name: str, c: int, M: int, frames, baseline: dict) -> list[dict]:
    ref = baseline.get(c)
    rows = []
    if ref is None:
        return rows
    if frames is None:
        for f in range(ref.shape[0]):
            rows.append({"config": name, "call": c, "rel_call": c - M, "frame": f, "psnr": "", "ssim": "", "missing": 1})
        return rows
    nf = min(ref.shape[0], frames.shape[0])
    for f in range(nf):
        a = ref[f].astype(np.float32) / 255.0
        b = frames[f].astype(np.float32) / 255.0
        rows.append({"config": name, "call": c, "rel_call": c - M, "frame": f, "psnr": f"{psnr(a, b):.3f}", "ssim": f"{ssim(a, b):.4f}", "missing": 0})
    return rows


# --------------------------------------------------------------------------- summary
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

    floor = mean_psnr(by_cfg.get("repeat", []), 0, args.post_chunks - 1)
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
            "missing_frames": missing(rows),
            "recovery_rel_call": recovery,
            "events": infos[name]["events"],
        }

    L = [f"# State ablation at migration chunk M={args.migration_chunk}, {args.post_chunks} chunks after, k={static['k']}\n",
         f"Generated {time.strftime('%Y-%m-%d %H:%M:%S %Z')}; GPU {static['gpu_name']}; commit {static['git_commit']}; "
         f"video {args.video_path}; seed {args.seed}. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.\n",
         f"Determinism floor (`repeat` mean PSNR over M..M+{args.post_chunks - 1}): **{floor:.2f} dB**. Recovery = first call whose mean PSNR >= floor - 1 dB.\n",
         "| config | bytes withheld (MB) | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | missing frames | recovery call |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    order = [n for n in DEFAULT_CONFIGS if n in summary] + [n for n in summary if n not in DEFAULT_CONFIGS]
    for name in order:
        s = summary[name]
        L.append(f"| {name} | {s['bytes_withheld_mb']:,.0f} | {s['psnr_M0']:.1f} | {s['psnr_M0_3']:.1f} | {s['psnr_M4_15']:.1f} | {s['psnr_M16_end']:.1f} | "
                 f"{s['ssim_M0_3']:.3f} | {s['ssim_M16_end']:.3f} | {s['missing_frames']} | {s['recovery_rel_call']} |")
    inv = infos[next(iter(infos))].get("inventory_at_M", {})
    L.append("\nInventory at M (bytes): " + ", ".join(f"{k2} {v / MB:,.0f} MB" for k2, v in inv.items()))
    L.append("\nDelay restores: " + "; ".join(f"{n}: {[e for e in summary[n]['events'] if 'restored' in e]}" for n in summary if n.startswith("delay_")))
    L.append("\nGates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.\n")
    (out_dir / "ablation_summary.md").write_text("\n".join(L) + "\n")
    with open(out_dir / "ablation_summary.json", "w") as fh:
        json.dump({"floor_psnr": floor, "per_config": summary}, fh, indent=2, default=str)
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
    p.add_argument("--configs", type=str, default=",".join(DEFAULT_CONFIGS))
    p.add_argument("--save_video", action="store_true", default=False)
    return p.parse_args()


def main():
    args = parse_args()
    torch.set_grad_enabled(False)
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
    for c in range(total_calls):
        frames = runner.step(session, c)
        if frames is not None:
            baseline[c] = frames
    log(f"[ablation] baseline done in {time.perf_counter() - t0:.0f} s; {len(baseline)} calls with output")
    static["inventory_baseline_end"] = inventory_bytes(pl)

    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    all_rows: list[dict] = []
    infos: dict[str, dict] = {}
    csv_path = out_dir / "ablation_raw.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["config", "call", "rel_call", "frame", "psnr", "ssim", "missing"])
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
