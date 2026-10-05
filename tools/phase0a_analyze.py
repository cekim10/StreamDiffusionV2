#!/usr/bin/env python3
"""Phase 0A analysis: aggregate phase0a_raw.csv + phase0a_static_k*.json, compute R_M / dM,
admission proxies, apply the FROZEN gate (results/quality_elastic/phase0a_code_audit.md, section 6)
and write phase0a_summary.md (+ PNG plots when matplotlib is available).

Usage:  python tools/phase0a_analyze.py --results_dir results/quality_elastic [--target_fps 16]
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

MB = 1024.0 * 1024.0
GIB = 1024.0 ** 3


def median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else float("nan")


def p95(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return float("nan")
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_raw(path: Path) -> dict[int, list[dict]]:
    rows_by_k: dict[int, list[dict]] = {}
    with open(path) as fh:
        for row in csv.DictReader(fh):
            rows_by_k.setdefault(int(row["k"]), []).append(row)
    return rows_by_k


def load_static(results_dir: Path) -> dict[int, dict]:
    out = {}
    for p in sorted(results_dir.glob("phase0a_static_k*.json")):
        with open(p) as fh:
            d = json.load(fh)
        out[int(d["k"])] = d
    return out


def parse_dmon(path: Path, t_start: float | None, t_end: float | None) -> dict:
    """nvidia-smi dmon -s pum -o T output. Returns medians of sm%, mem%, fb MB over the
    measured window when timestamps can be matched, otherwise over the middle 80% of samples."""
    if not path.exists():
        return {}
    rows = []
    cols = None
    for line in path.read_text().splitlines():
        if line.startswith("#Time") or line.startswith("# Time") or (line.startswith("#") and "sm" in line):
            cols = line.lstrip("#").split()
            continue
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split()
        if cols is None or len(parts) != len(cols):
            continue
        rows.append(dict(zip(cols, parts)))
    if not rows:
        return {}

    def pick(name_candidates):
        for c in name_candidates:
            if c in rows[0]:
                return c
        return None

    sm_col, mem_col, fb_col, time_col = pick(["sm"]), pick(["mem"]), pick(["fb"]), pick(["Time", "time"])
    selected = rows
    if time_col and t_start and t_end:
        s_str = time.strftime("%H:%M:%S", time.localtime(t_start))
        e_str = time.strftime("%H:%M:%S", time.localtime(t_end))
        win = [r for r in rows if s_str <= r[time_col] <= e_str]
        if len(win) >= 5:
            selected = win
    else:
        n = len(rows)
        selected = rows[int(0.1 * n): max(int(0.9 * n), int(0.1 * n) + 1)]

    def med(col):
        vals = [fnum(r[col]) for r in selected if col and r.get(col) not in (None, "-")]
        return median(vals)

    return {"sm_util_pct": med(sm_col), "mem_ctrl_util_pct": med(mem_col), "fb_used_mb": med(fb_col),
            "samples": len(selected)}


def parse_dcgm(path: Path) -> dict:
    """dcgmi dmon -e 1002,1003,1004,1005 output: medians over the middle 80% of samples."""
    if not path.exists():
        return {}
    vals: dict[str, list[float]] = {"sm_active": [], "sm_occupancy": [], "tensor_active": [], "dram_active": []}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[0].startswith("GPU"):
            continue
        nums = [fnum(x) for x in parts[2:6]]
        if any(v is None for v in nums):
            continue
        for key, v in zip(vals, nums):
            vals[key].append(v)
    if not vals["dram_active"]:
        return {}
    n = len(vals["dram_active"])
    lo, hi = int(0.1 * n), max(int(0.9 * n), int(0.1 * n) + 1)
    return {key: median(v[lo:hi]) for key, v in vals.items()}


def summarize_k(rows: list[dict], static: dict, results_dir: Path, k: int, target_fps: float) -> dict:
    meas = [r for r in rows if r["phase"] == "measured"]
    if not meas:
        raise SystemExit(f"k={k}: no measured rows")
    col = lambda name, rs=meas: [fnum(r[name]) for r in rs]  # noqa: E731
    mc = static["memory_checkpoints"]
    m_fixed = mc["after_model_load"]["allocated_bytes"]
    m_fixed_device = mc["after_model_load"]["device_used_bytes"]
    m_persistent = median(col("allocated_boundary_mb")) * MB
    m_peak = median(col("peak_allocated_chunk_mb")) * MB
    m_reserved = median(col("reserved_boundary_mb")) * MB
    m_device = median(col("device_used_mb")) * MB
    e2e = col("end_to_end_chunk_ms")
    fps = col("achieved_fps")
    t_start = fnum(meas[0]["wall_time_unix"])
    t_end = fnum(meas[-1]["wall_time_unix"])
    inv = static.get("inventory_after_warmup") or static.get("inventory_after_session_start") or {}
    out = {
        "k": k,
        "n_measured": len(meas),
        "n_warmup": len(rows) - len(meas),
        "M_fixed_bytes": m_fixed,
        "M_fixed_device_bytes": m_fixed_device,
        "M_persistent_bytes": m_persistent,
        "M_peak_bytes": m_peak,
        "M_reserved_bytes": m_reserved,
        "M_device_bytes": m_device,
        "transient_bytes": m_peak - m_persistent,
        "session_delta_bytes": m_persistent - m_fixed,
        "kv_physical_mb": median(col("kv_cache_physical_mb")),
        "kv_logical_mb": median(col("kv_cache_logical_mb")),
        "crossattn_physical_mb": median(col("crossattn_physical_mb")),
        "crossattn_logical_mb": median(col("crossattn_logical_mb")),
        "hidden_state_mb": median(col("hidden_state_mb")),
        "prompt_embeds_mb": median(col("prompt_embeds_physical_mb")),
        "vae_feat_cache_mb": median(col("vae_feat_cache_mb")),
        "session_state_physical_mb": median(col("session_state_physical_mb")),
        "vae_encode_ms_med": median(col("vae_encode_ms")),
        "dit_ms_med": median(col("dit_ms")),
        "dit_ms_p95": p95(col("dit_ms")),
        "vae_decode_ms_med": median(col("vae_decode_ms")),
        "e2e_ms_med": median(e2e),
        "e2e_ms_p95": p95(e2e),
        "e2e_ms_max": max(e2e),
        "fps_med": median(fps),
        "fps_p5": sorted(fps)[max(0, int(0.05 * (len(fps) - 1)))],
        "current_step_med": median(col("current_step")),
        "session_start_ms": static.get("session_start_ms"),
        "kv_stride0": inv.get("kv_stride0"),
        "crossattn_stride0": inv.get("crossattn_stride0"),
        "device_total_bytes": mc["after_model_load"]["device_total_bytes"],
        "gpu_name": static.get("gpu_name"),
        "dmon": parse_dmon(results_dir / f"phase0a_dmon_k{k}.txt", t_start, t_end),
        "dcgm": parse_dcgm(results_dir / f"phase0a_dcgm_k{k}.txt"),
        "frames_out_total": sum(int(r["frames_out"]) for r in meas),
    }
    # Admission proxies (audit section 6).
    total = out["device_total_bytes"]
    per_session = out["session_delta_bytes"] + out["transient_bytes"]
    out["S_mem"] = int((total - m_fixed_device - GIB) // per_session) if per_session > 0 else None
    out["S_compute"] = int(out["fps_med"] // target_fps)
    return out


def verdict(summ: dict[int, dict], target_fps: float) -> tuple[str, list[str]]:
    reasons = []
    if 1 not in summ or 4 not in summ:
        return "INCOMPLETE", ["k=1 and k=4 are both required for R_M."]
    fixed = [s["M_fixed_bytes"] for s in summ.values()]
    if max(fixed) - min(fixed) > 0.01 * max(fixed):
        reasons.append(f"INVALID RUN: M_fixed differs across k by more than 1% ({[round(f / MB) for f in fixed]} MB).")
    d1 = summ[1]["session_delta_bytes"]
    d4 = summ[4]["session_delta_bytes"]
    r_m = d4 / d1 if d1 > 0 else float("inf")
    d_m = summ[4]["M_persistent_bytes"] - summ[1]["M_persistent_bytes"]
    reasons.append(f"R_M = {r_m:.2f}; dM = {d_m / MB:.0f} MB")
    s_mem = {k: s["S_mem"] for k, s in summ.items()}
    s_comp = {k: s["S_compute"] for k, s in summ.items()}
    reasons.append(f"S_mem = {s_mem}; S_compute (at {target_fps:g} FPS, time-sliced) = {s_comp}")
    hbm_binds_somewhere = any(s_mem[k] is not None and s_mem[k] <= s_comp[k] for k in summ if k >= 2)
    cap_change = (s_mem.get(1) or 0) - (s_mem.get(4) or 0)
    reasons.append(f"HBM binds before compute for some k>=2: {hbm_binds_somewhere}; S_mem(1)-S_mem(4) = {cap_change}")

    if r_m < 1.3 or abs(d_m) < 256 * MB:
        return "KILL", reasons + ["R_M < 1.3 or |dM| < 256 MB: physical HBM is effectively insensitive to k."]
    if not hbm_binds_somewhere:
        return "KILL", reasons + ["HBM never binds before compute on this GPU for any k: the delta cannot change admission."]
    if r_m >= 2 and cap_change >= 2:
        return "GO", reasons
    if r_m >= 2:
        return "GRAY", reasons + ["R_M >= 2 but the session-capacity change is < 2 sessions on this GPU."]
    return "GRAY", reasons + ["1.3 <= R_M < 2."]


def fmt_mb(b):
    return f"{b / MB:,.0f}"


def write_summary(results_dir: Path, summ: dict[int, dict], rows_by_k, static_by_k, target_fps: float, plots: list[str]):
    ks = sorted(summ)
    s0 = static_by_k[ks[0]]
    audit_path = results_dir / "phase0a_code_audit.md"
    env_path = results_dir / "phase0a_environment.txt"
    cmd_path = results_dir / "phase0a_commands.txt"
    v, reasons = verdict(summ, target_fps)

    L = []
    L.append("# Phase 0A summary: single-session resource vs denoising-step count k\n")
    L.append(f"Generated {time.strftime('%Y-%m-%d %H:%M:%S %Z')} by `tools/phase0a_analyze.py` from `phase0a_raw.csv` and `phase0a_static_k*.json`.\n")
    L.append(f"## 10. Verdict: **{v}**\n")
    L.extend(f"- {r}" for r in reasons)
    L.append("\nGate definitions were frozen before measurement; see section 6 of the audit below.\n")

    L.append("## 1. Hardware / software configuration\n")
    L.append(f"- GPU: {s0.get('gpu_name')} (capability {s0.get('gpu_capability')}), total HBM {fmt_mb(summ[ks[0]]['device_total_bytes'])} MB")
    L.append(f"- nvidia-smi: `{s0.get('nvidia_smi')}`")
    L.append(f"- host: {s0.get('hostname')}; torch {s0.get('torch')}; CUDA {s0.get('cuda')}; cuDNN {s0.get('cudnn')}; flash_attn available: {s0.get('flash_attn_available')}")
    L.append(f"- python: {s0.get('python')}")
    if env_path.exists():
        L.append("\n<details><summary>phase0a_environment.txt</summary>\n\n```\n" + env_path.read_text().strip() + "\n```\n</details>\n")

    L.append("## 2. Git commit\n")
    L.append(f"- commit: `{s0.get('git_commit')}`")
    L.append(f"- working tree (short status at run time): `{s0.get('git_status_short') or 'clean'}`\n")

    L.append("## 3. Experiment command lines\n")
    if cmd_path.exists():
        L.append("```\n" + cmd_path.read_text().strip() + "\n```")
    else:
        L.append("```\n" + "\n".join(static_by_k[k].get("command", "") for k in ks) + "\n```")
    L.append(f"\nWorkload: model `{s0['args'].get('model_type')}`, config `{s0['args'].get('config_path')}`, video `{s0['args'].get('video_path')}` "
             f"({s0['input_video']['source_frames']} source frames, tiled={s0['input_video']['tiled']}, {s0['input_video']['needed_frames']} frames used), "
             f"{s0['args'].get('height')}x{s0['args'].get('width')}, prompt \"{s0.get('prompt')}\", seed {s0['args'].get('seed')}, noise_scale {s0['args'].get('noise_scale')}, "
             f"warm-up {summ[ks[0]]['n_warmup']} chunks, measured {summ[ks[0]]['n_measured']} chunks of {s0.get('chunk_size')} frames.\n")

    L.append("## 4. Code-path audit\n")
    if audit_path.exists():
        L.append(f"Full audit (written before measurement): [`phase0a_code_audit.md`](phase0a_code_audit.md). Measured confirmation of the replication claims:\n")
    L.append("| k | KV physical MB | KV logical MB | KV stride(0) | cross-attn physical MB | cross-attn logical MB | cross-attn stride(0) | prompt_embeds MB | hidden_state MB | VAE feat cache MB |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for k in ks:
        s = summ[k]
        L.append(f"| {k} | {s['kv_physical_mb']:.0f} | {s['kv_logical_mb']:.0f} | {s['kv_stride0']} | {s['crossattn_physical_mb']:.0f} | {s['crossattn_logical_mb']:.0f} | {s['crossattn_stride0']} | {s['prompt_embeds_mb']:.1f} | {s['hidden_state_mb']:.2f} | {s['vae_feat_cache_mb']:.0f} |")
    L.append("\nInterpretation: KV physical == logical and both scale with k => `repeat()` copies (audit §2). Cross-attn physical < logical with stride(0)==0 => `expand()` view.\n")

    L.append("## 5. Memory breakdown (torch.cuda.memory_allocated unless noted)\n")
    w = s0.get("weights", {})
    L.append("Fixed footprint (identical for all k by construction; checked below):\n")
    L.append("| component | params | CUDA bytes (MB) |")
    L.append("|---|---|---|")
    for name in ("generator", "text_encoder", "vae"):
        if name in w:
            L.append(f"| {name} | {w[name]['param_count']:,} | {fmt_mb(w[name]['cuda_bytes'])} |")
    L.append("")
    L.append("| k | M_fixed (alloc) | M_fixed (device used) | M_persistent | session delta = M_persistent - M_fixed | M_peak (chunk) | transient = peak - persistent | reserved | device used | session tensors (physical) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for k in ks:
        s = summ[k]
        L.append(f"| {k} | {fmt_mb(s['M_fixed_bytes'])} | {fmt_mb(s['M_fixed_device_bytes'])} | {fmt_mb(s['M_persistent_bytes'])} | {fmt_mb(s['session_delta_bytes'])} | {fmt_mb(s['M_peak_bytes'])} | {fmt_mb(s['transient_bytes'])} | {fmt_mb(s['M_reserved_bytes'])} | {fmt_mb(s['M_device_bytes'])} | {s['session_state_physical_mb']:.0f} |")
    L.append("\nAll values are medians over measured chunks; 'session delta' is the per-session persistent cost, 'session tensors' is the sum of the inventoried tensors' unique storages (should be close to the session delta; the gap is allocator rounding and un-inventoried live objects).\n")

    L.append("## 6. Latency / throughput by k\n")
    L.append(f"| k | VAE enc ms (med) | DiT ms (med / p95) | VAE dec ms (med) | chunk e2e ms (med / p95 / max) | FPS (med / p5) | output lag (k chunks, ms) | session start ms | adaptive step (med) | SM util % | mem-ctrl util % | DRAM active (DCGM) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k in ks:
        s = summ[k]
        dm, dc = s["dmon"], s["dcgm"]
        L.append(f"| {k} | {s['vae_encode_ms_med']:.1f} | {s['dit_ms_med']:.1f} / {s['dit_ms_p95']:.1f} | {s['vae_decode_ms_med']:.1f} | "
                 f"{s['e2e_ms_med']:.1f} / {s['e2e_ms_p95']:.1f} / {s['e2e_ms_max']:.1f} | {s['fps_med']:.1f} / {s['fps_p5']:.1f} | {k * s['e2e_ms_med']:.0f} | "
                 f"{(s['session_start_ms'] or float('nan')):.0f} | {s['current_step_med']:.0f} | "
                 f"{dm.get('sm_util_pct', float('nan')):.0f} | {dm.get('mem_ctrl_util_pct', float('nan')):.0f} | {dc.get('dram_active', float('nan')):.2f} |")
    L.append("\nFPS is 4 frames / per-chunk service time of the official `run_stream_batch` (throughput). Glass-to-glass lag in Stream-Batch is k chunk periods (audit §4). Utilization columns are 1 s samples from `nvidia-smi dmon` / `dcgmi dmon` over the measured window and are coarse.\n")

    L.append("## 7. R_M, dM and admission proxies\n")
    if 1 in summ and 4 in summ:
        d1, d4 = summ[1]["session_delta_bytes"], summ[4]["session_delta_bytes"]
        L.append(f"- R_M = (M_persistent(4) - M_fixed) / (M_persistent(1) - M_fixed) = {fmt_mb(d4)} / {fmt_mb(d1)} = **{(d4 / d1 if d1 else float('inf')):.2f}**")
        L.append(f"- dM = M_persistent(4) - M_persistent(1) = **{fmt_mb(summ[4]['M_persistent_bytes'] - summ[1]['M_persistent_bytes'])} MB**")
    L.append(f"\n| k | per-session HBM (delta + transient) MB | S_mem (sessions by HBM) | S_compute (sessions by time-slicing at {target_fps:g} FPS) | binding |")
    L.append("|---|---|---|---|---|")
    for k in ks:
        s = summ[k]
        binding = "HBM" if (s["S_mem"] is not None and s["S_compute"] is not None and s["S_mem"] <= s["S_compute"]) else "compute"
        L.append(f"| {k} | {fmt_mb(s['session_delta_bytes'] + s['transient_bytes'])} | {s['S_mem']} | {s['S_compute']} | {binding} |")
    L.append("\nS_compute assumes one process time-slicing sessions with no cross-session batching benefit; it is a lower bound on compute capacity, so 'compute' binding here is conservative against the hypothesis only if cross-session batching cannot raise throughput. S_mem uses the measured GPU's total HBM minus the fixed footprint and 1 GiB headroom.\n")

    L.append("## 8. Plots / tables\n")
    if plots:
        L.extend(f"![{p}]({p})" for p in plots)
    else:
        L.append("matplotlib not available on the analysis machine; tables above are the primary record.")
    L.append("")

    L.append("## 9. Anomalies and measurement caveats\n")
    caveats = []
    for k in ks:
        s = summ[k]
        if s["e2e_ms_max"] > 3 * s["e2e_ms_med"]:
            caveats.append(f"k={k}: max chunk time {s['e2e_ms_max']:.0f} ms is > 3x the median ({s['e2e_ms_med']:.0f} ms); inspect `phase0a_raw.csv` for stalls (loop seams, t_refresh rewinds at chunk ~50, clock changes).")
        if abs(s["kv_physical_mb"] - s["kv_logical_mb"]) > 1:
            caveats.append(f"k={k}: KV physical != logical ({s['kv_physical_mb']:.0f} vs {s['kv_logical_mb']:.0f} MB): rows share storage, contradicting the repeat() audit; re-check.")
        if s["frames_out_total"] != s["n_measured"] * s0.get("chunk_size", 4):
            caveats.append(f"k={k}: decoded {s['frames_out_total']} frames over {s['n_measured']} measured chunks (expected {s['n_measured'] * s0.get('chunk_size', 4)}).")
    if not caveats:
        caveats.append("No automatic anomaly flags fired.")
    caveats.append("Input video is tiled to reach the chunk budget; loop seams lower the content-adaptive `current_step` for one chunk at each seam, identically across k.")
    caveats.append("Stream-Batch draws k noise rows per chunk, so RNG streams differ across k even with a fixed seed; quality across k is not seed-matched.")
    caveats.append("The text encoder (umt5-xxl) stays resident on the GPU in the official path and is included in M_fixed; it does not vary with k but inflates the fixed footprint used in S_mem.")
    L.extend(f"- {c}" for c in caveats)
    L.append("")

    (results_dir / "phase0a_summary.md").write_text("\n".join(L) + "\n")
    with open(results_dir / "phase0a_summary.json", "w") as fh:
        json.dump({"verdict": v, "reasons": reasons, "per_k": summ}, fh, indent=2, default=str)
    return v


def make_plots(results_dir: Path, summ: dict[int, dict], rows_by_k) -> list[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return []
    ks = sorted(summ)
    plots = []

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(results_dir / name, dpi=120)
        plt.close(fig)
        plots.append(name)

    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.plot(ks, [summ[k]["M_persistent_bytes"] / MB for k in ks], "o-", label="persistent (alloc @ boundary)")
    ax.plot(ks, [summ[k]["M_peak_bytes"] / MB for k in ks], "s--", label="peak (alloc, per chunk)")
    ax.plot(ks, [summ[k]["M_device_bytes"] / MB for k in ks], "^:", label="device used (mem_get_info)")
    ax.axhline(summ[ks[0]]["M_fixed_bytes"] / MB, color="gray", lw=0.8, label="M_fixed")
    ax.set_xlabel("denoising steps k"); ax.set_ylabel("MB"); ax.set_xticks(ks); ax.legend(fontsize=7); ax.set_title("HBM vs k")
    save(fig, "phase0a_hbm_vs_k.png")

    fig, ax = plt.subplots(figsize=(5, 3.5))
    for k in ks:
        e2e = [float(r["end_to_end_chunk_ms"]) for r in rows_by_k[k] if r["phase"] == "measured"]
        ax.plot(range(len(e2e)), e2e, lw=0.8, label=f"k={k}")
    ax.set_xlabel("measured chunk"); ax.set_ylabel("chunk e2e ms"); ax.legend(fontsize=7); ax.set_title("Chunk latency")
    save(fig, "phase0a_latency_vs_k.png")

    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.bar([str(k) for k in ks], [summ[k]["fps_med"] for k in ks])
    ax.set_xlabel("denoising steps k"); ax.set_ylabel("FPS (median)"); ax.set_title("Throughput")
    save(fig, "phase0a_fps_vs_k.png")

    if any(summ[k]["dmon"].get("mem_ctrl_util_pct") is not None for k in ks):
        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.plot(ks, [summ[k]["dmon"].get("mem_ctrl_util_pct", float("nan")) for k in ks], "o-", label="mem-ctrl util % (dmon)")
        ax.plot(ks, [summ[k]["dmon"].get("sm_util_pct", float("nan")) for k in ks], "s--", label="SM util % (dmon)")
        if any(summ[k]["dcgm"] for k in ks):
            ax.plot(ks, [100 * summ[k]["dcgm"].get("dram_active", float("nan")) for k in ks], "^:", label="DRAM active % (DCGM)")
        ax.set_xlabel("denoising steps k"); ax.set_ylabel("%"); ax.set_xticks(ks); ax.legend(fontsize=7); ax.set_title("Utilization")
        save(fig, "phase0a_util_vs_k.png")
    return plots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", type=str, default="results/quality_elastic")
    ap.add_argument("--target_fps", type=float, default=16.0)
    args = ap.parse_args()
    results_dir = Path(args.results_dir)
    rows_by_k = load_raw(results_dir / "phase0a_raw.csv")
    static_by_k = load_static(results_dir)
    summ = {k: summarize_k(rows_by_k[k], static_by_k[k], results_dir, k, args.target_fps)
            for k in sorted(rows_by_k) if k in static_by_k}
    plots = make_plots(results_dir, summ, rows_by_k)
    v = write_summary(results_dir, summ, rows_by_k, static_by_k, args.target_fps, plots)
    print(f"[phase0a_analyze] verdict: {v}  -> {results_dir / 'phase0a_summary.md'}")


if __name__ == "__main__":
    main()
