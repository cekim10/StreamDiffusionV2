# Phase 0A summary: single-session resource vs denoising-step count k

Generated 2026-10-05 15:01:10 PDT by `tools/phase0a_analyze.py` from `phase0a_raw.csv` and `phase0a_static_k*.json`.

## 10. Verdict: **KILL**

- R_M = 2.06; dM = 4959 MB
- S_mem = {1: 4, 2: 3, 3: 2, 4: 2}; S_compute (at 16 FPS, time-sliced) = {1: 0, 2: 0, 3: 0, 4: 0}
- HBM binds before compute for some k>=2: False; S_mem(1)-S_mem(4) = 2
- HBM never binds before compute on this GPU for any k: the delta cannot change admission.

Gate definitions were frozen before measurement; see section 6 of the audit below.

## 1. Hardware / software configuration

- GPU: NVIDIA L40S (capability [8, 9]), total HBM 45,459 MB
- nvidia-smi: `NVIDIA L40S, 575.51.03, 46068 MiB, 210 MHz, 405 MHz, 350.00 W
NVIDIA L40S, 575.51.03, 46068 MiB, 210 MHz, 405 MHz, 350.00 W`
- host: elves-01; torch 2.6.0+cu124; CUDA 12.4; cuDNN 90100; flash_attn available: True
- python: 3.10.22 (main, Oct  3 2026, 01:32:06) [Clang 22.1.3 ]

<details><summary>phase0a_environment.txt</summary>

```
date: 2026-10-05T21:49:40Z
host: elves-01
commit: e0c9d34badf6aca55a09bdbd778f5d8ee0409a38
git status:
?? results/quality_elastic/phase0a_environment.txt
python: Python 3.10.22
index, name, driver_version, memory.total [MiB], clocks.max.sm [MHz], clocks.max.memory [MHz]
0, NVIDIA L40S, 575.51.03, 46068 MiB, 2520 MHz, 9001 MHz
1, NVIDIA L40S, 575.51.03, 46068 MiB, 2520 MHz, 9001 MHz
torch 2.6.0+cu124 cuda 12.4
flash_attn 2.7.4.post1
STEPS=1 2 3 4 GPU=0 WARMUP=10 MEASURED=100 SEED=0 EXTRA=
```
</details>

## 2. Git commit

- commit: `e0c9d34badf6aca55a09bdbd778f5d8ee0409a38`
- working tree (short status at run time): `?? results/quality_elastic/phase0a_commands.txt
?? results/quality_elastic/phase0a_dmon_k1.txt
?? results/quality_elastic/phase0a_environment.txt
?? results/quality_elastic/phase0a_log_k1.txt`

## 3. Experiment command lines

```
python tools/phase0a_quality_elastic.py --step 1 --gpu_id 0 --out_dir results/quality_elastic --warmup_chunks 10 --measured_chunks 100 --seed 0 
python tools/phase0a_quality_elastic.py --step 2 --gpu_id 0 --out_dir results/quality_elastic --warmup_chunks 10 --measured_chunks 100 --seed 0 
python tools/phase0a_quality_elastic.py --step 3 --gpu_id 0 --out_dir results/quality_elastic --warmup_chunks 10 --measured_chunks 100 --seed 0 
python tools/phase0a_quality_elastic.py --step 4 --gpu_id 0 --out_dir results/quality_elastic --warmup_chunks 10 --measured_chunks 100 --seed 0
```

Workload: model `T2V-1.3B`, config `/home/ckim151/StreamDiffusionV2/configs/wan_causal_dmd_v2v.yaml`, video `/home/ckim151/StreamDiffusionV2/examples/original.mp4` (81 source frames, tiled=True, 445 frames used), 480x832, prompt "A dog walks on the grass, realistic", seed 0, noise_scale 0.8, warm-up 10 chunks, measured 100 chunks of 4 frames.

## 4. Code-path audit

Full audit (written before measurement): [`phase0a_code_audit.md`](phase0a_code_audit.md). Measured confirmation of the replication claims:

| k | KV physical MB | KV logical MB | KV stride(0) | cross-attn physical MB | cross-attn logical MB | cross-attn stride(0) | prompt_embeds MB | hidden_state MB | VAE feat cache MB |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1645 | 1645 | 14376960 | 90 | 90 | 786432 | 4.0 | 0.19 | 2870 |
| 2 | 3291 | 3291 | 14376960 | 90 | 180 | 0 | 8.0 | 0.38 | 2870 |
| 3 | 4936 | 4936 | 14376960 | 90 | 270 | 0 | 12.0 | 0.57 | 2870 |
| 4 | 6581 | 6581 | 14376960 | 90 | 360 | 0 | 16.0 | 0.76 | 2870 |

Interpretation: KV physical == logical and both scale with k => `repeat()` copies (audit §2). Cross-attn physical < logical with stride(0)==0 => `expand()` view.

## 5. Memory breakdown (torch.cuda.memory_allocated unless noted)

Fixed footprint (identical for all k by construction; checked below):

| component | params | CUDA bytes (MB) |
|---|---|---|
| generator | 1,418,996,800 | 2,707 |
| text_encoder | 5,680,910,336 | 10,835 |
| vae | 126,892,531 | 242 |

| k | M_fixed (alloc) | M_fixed (device used) | M_persistent | session delta = M_persistent - M_fixed | M_peak (chunk) | transient = peak - persistent | reserved | device used | session tensors (physical) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 13,789 | 16,154 | 18,458 | 4,670 | 20,669 | 2,210 | 23,894 | 24,430 | 4610 |
| 2 | 13,789 | 16,154 | 20,107 | 6,318 | 22,317 | 2,210 | 26,296 | 26,834 | 6260 |
| 3 | 13,789 | 16,154 | 21,754 | 7,966 | 23,964 | 2,210 | 27,244 | 27,782 | 7909 |
| 4 | 13,789 | 16,154 | 23,418 | 9,629 | 25,628 | 2,210 | 28,860 | 29,398 | 9559 |

All values are medians over measured chunks; 'session delta' is the per-session persistent cost, 'session tensors' is the sum of the inventoried tensors' unique storages (should be close to the session delta; the gap is allocator rounding and un-inventoried live objects).

## 6. Latency / throughput by k

| k | VAE enc ms (med) | DiT ms (med / p95) | VAE dec ms (med) | chunk e2e ms (med / p95 / max) | FPS (med / p5) | output lag (k chunks, ms) | session start ms | adaptive step (med) | SM util % | mem-ctrl util % | DRAM active (DCGM) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 143.4 | 74.9 / 75.8 | 248.6 | 468.7 / 470.6 / 482.5 | 8.5 / 8.5 | 469 | 1185 | 626 | 98 | 84 | nan |
| 2 | 143.8 | 127.4 / 129.0 | 249.5 | 522.7 / 525.7 / 541.2 | 7.7 / 7.6 | 1045 | 981 | 626 | 97 | 73 | nan |
| 3 | 143.7 | 179.6 / 193.0 | 249.3 | 574.7 / 587.7 / 589.8 | 7.0 / 6.8 | 1724 | 1079 | 626 | 97 | 70 | nan |
| 4 | 144.0 | 245.6 / 259.6 | 249.9 | 641.8 / 655.3 / 658.5 | 6.2 / 6.1 | 2567 | 1275 | 626 | 96 | 69 | nan |

FPS is 4 frames / per-chunk service time of the official `run_stream_batch` (throughput). Glass-to-glass lag in Stream-Batch is k chunk periods (audit §4). Utilization columns are 1 s samples from `nvidia-smi dmon` / `dcgmi dmon` over the measured window and are coarse.

## 7. R_M, dM and admission proxies

- R_M = (M_persistent(4) - M_fixed) / (M_persistent(1) - M_fixed) = 9,629 / 4,670 = **2.06**
- dM = M_persistent(4) - M_persistent(1) = **4,959 MB**

| k | per-session HBM (delta + transient) MB | S_mem (sessions by HBM) | S_compute (sessions by time-slicing at 16 FPS) | binding |
|---|---|---|---|---|
| 1 | 6,880 | 4 | 0 | compute |
| 2 | 8,529 | 3 | 0 | compute |
| 3 | 10,176 | 2 | 0 | compute |
| 4 | 11,839 | 2 | 0 | compute |

S_compute assumes one process time-slicing sessions with no cross-session batching benefit; it is a lower bound on compute capacity, so 'compute' binding here is conservative against the hypothesis only if cross-session batching cannot raise throughput. S_mem uses the measured GPU's total HBM minus the fixed footprint and 1 GiB headroom.

## 8. Plots / tables

matplotlib not available on the analysis machine; tables above are the primary record.

## 9. Anomalies and measurement caveats

- No automatic anomaly flags fired.
- Input video is tiled to reach the chunk budget; loop seams lower the content-adaptive `current_step` for one chunk at each seam, identically across k.
- Stream-Batch draws k noise rows per chunk, so RNG streams differ across k even with a fixed seed; quality across k is not seed-matched.
- The text encoder (umt5-xxl) stays resident on the GPU in the official path and is included in M_fixed; it does not vary with k but inflates the fixed footprint used in S_mem.

