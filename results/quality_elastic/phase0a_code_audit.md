# Phase 0A code-path audit (written BEFORE any measurement)

Audited commit: see `git rev-parse HEAD` recorded in `phase0a_static_k*.json` (audit performed at 6961a5c, "Fix position refresh in streaming inference").
Target path: single-GPU Stream-Batch, `streamv2v/inference.py` (`SingleGPUInferencePipeline`), model `T2V-1.3B`, config `configs/wan_causal_dmd_v2v.yaml`, 480x832.

## 1. How `--step k` reaches the model

| Claim | Verified location | Result |
|---|---|---|
| `--step k` selects the first k non-zero timesteps of the YAML schedule and re-appends 0 | `streamv2v/inference_common.py:84-91` (`merge_cli_config`) | TRUE. YAML v2v schedule is `[1000,750,500,250,0]`, so k in {1,2,3,4} is valid. |
| For v2v the terminal 0 is removed so `len(denoising_step_list) == k` | `models/wan/causal_stream_inference.py:73-80` (`_init_denoising_step_list`) | TRUE (`if not args.t2v: ...[:-1]`). |
| Stream-Batch batch dimension == k (denoising stages of ONE session), not users | `causal_stream_inference.py:211` (`self.batch_size = len(self.denoising_step_list)`); `inference_stream` shifts rows `hidden_states[1:] = hidden_states[:-1]` (`:271-277`) | TRUE. Row i holds the chunk currently at denoising stage i. |

## 2. Which per-session tensors are physically replicated by k

| Tensor | Allocation / transform | Physical vs view | k-dependence |
|---|---|---|---|
| `kv_cache1[i]['k'/'v']`, i in 0..29 | allocated once with `batch_size = noise.shape[0] = 1` as `zeros([1, 9360, 12, 128])` (`causal_stream_inference.py:88-110`), filled during the k sequential `prepare()` passes, then `.repeat(k,1,1,1)` (`:224-225`) | **physical copy**, k rows | linear in k. Logical per row: 30 layers x 2 x 9360 x 1536 x 2 B = 1.725 GB |
| `kv_cache1[i]['global_end_index'/'local_end_index'/'pos']` | `.repeat(k)` (`:227-229`) | physical, negligible bytes | linear, negligible |
| `crossattn_cache[i]['k'/'v']` | pre-allocated zeros `[1,512,12,128]` (`:112-125`), then **replaced** by freshly computed B=1 tensors on the first cross-attn call (`models/wan/wan_base/modules/model.py:174-180`), then `.expand(k,-1,-1,-1)` (`causal_stream_inference.py:231-232`) | **view** (stride 0 on dim 0) | none. Logical 94 MB total, physical 94 MB regardless of k. The pre-allocated zeros become garbage after replacement. |
| `conditional_dict['prompt_embeds']` | `.repeat(k,1,1)` (`:258`) | physical, [k,512,4096] bf16 = 4 MB/row | linear, small |
| `hidden_states` | `zeros([k, 1, 16, 60, 104])` bf16 (`:241-243`) | physical, 200 KB/row | linear, negligible |
| `block_x` | only for `block_mode in ['output','middle']`; single-GPU input mode -> `None` (`:245-250`) | n/a | none |
| `kv_cache_starts/ends`, `timestep` | k-length long tensors (`:252-256`) | negligible | negligible |
| `self_attn.evict_idx` (per layer) | Python list of lists, one per batch row (`models/wan/causal_model.py:309-313`) | host memory | none on HBM |
| VAE encoder/decoder feature caches | `_enc_feat_map` / `_feat_map`, one cached tensor per CausalConv3d (`models/wan/wan_base/modules/vae.py:546-583, 611-660, 662-679`) | physical, B=1, resolution-dependent | none (decode is called on `denoised_pred[[-1]]`, i.e. one row) |
| Model weights (DiT 1.3B, umt5-xxl text encoder, Wan VAE) | moved to GPU in bf16 once (`streamv2v/inference.py:92-93`) | physical, shared across k | none. The text encoder is resident for the whole session even though it is only used in `prepare()`. |

KV cache window is a fixed ring buffer (`num_kv_cache: 6`, `num_sink_tokens: 3`, `configs/wan_causal_dmd_v2v.yaml:54-55`), so persistent state does NOT grow with session duration.

Expected k-dependent persistent delta from logical sizes alone (NOT evidence, to be checked against physical measurement):
`(k-1) x 1.725 GB` for KV + `(k-1) x 4 MB` prompt embeds -> `~5.2 GB` between k=1 and k=4.
The repo authors already model exactly this delta in `demo/util.py:174-213` (`estimate_stream_batch_extra_memory_bytes`) and use it to choose batch vs no-batch mode by free memory (`select_stream_execution_mode`). This is prior art: the k-memory coupling is known inside one session; what is untested is whether it matters for multi-session admission.

## 3. Transient (per-chunk) allocations

Per `inference_stream` call the DiT runs B=k rows x 1 latent frame (1560 tokens): activations `[k,1560,1536]` per layer, FFN `[k,1560,8192]`, q/k/v padding `torch.cat` copies (`causal_model.py:261-277`), attention over up to 9360 cached tokens via `flash_attn_with_kvcache` (`:403-416`), plus `randn_like` per row in `add_noise` (`causal_stream_inference.py:292-298`). Expected to scale ~linearly in k but be small relative to KV. VAE decode of one latent frame to 4 pixel frames at 480x832 (`vae.py:611-660`) is k-independent and may dominate the transient peak. These are freed at chunk boundaries, so `memory_allocated()` at a chunk boundary == persistent live memory.

## 4. Session start and output lag

`start_stream_session` (`streamv2v/inference.py:188-215`) encodes 1 + chunk_size (=5) pixel frames, runs `prepare()` (k sequential full-DiT passes at B=1), decodes the initial frames. Afterwards each chunk is 4 pixel frames -> 1 latent frame. Output for a chunk is emitted only once `session.processed >= num_steps` (`:248`), so steady-state glass-to-glass lag is k chunk periods; per-chunk service time is the throughput metric.

## 5. Harness fidelity notes

- The harness calls the official `start_stream_session` / `run_stream_batch` unchanged; timing is injected by wrapping `vae.stream_encode`, `pipeline.inference_stream`, `vae.stream_decode_to_pixel` as instance attributes (no source edits).
- Deviations from `streamv2v/inference.py:main`: (a) the input video is kept on host memory and each chunk is copied to the GPU before the timed region, instead of resident on GPU as a bf16 tensor (so M_fixed excludes the input video); (b) `examples/original.mp4` (5.06 s) is tiled along time to supply 10 warm-up + 100 measured chunks; loop seams create motion spikes that `compute_noise_scale_and_step` (`inference.py:51-57`) turns into a lower `current_step`, identically for all k because the input and seed are fixed.
- RNG: `set_seed(seed)` once per process; Stream-Batch draws k `randn` rows per chunk, so the noise streams differ across k by construction. Quality comparison across k is therefore not seed-matched at the row level; this is inherent to the official path.

## 6. Frozen gate operationalization (fixed before results)

Definitions (all from `torch.cuda.memory_allocated()` unless stated):
- `M_fixed(k)`: allocated bytes right after `load_model()` + `.to(cuda, bf16)` and a `synchronize()`, before any session. Must agree across k to within 1%; otherwise the run is invalid.
- `M_persistent(k)`: median over measured chunks of allocated bytes at the chunk boundary (after `run_stream_batch` returns and `synchronize()`).
- `M_peak(k)`: median over measured chunks of `max_memory_allocated()` with peak stats reset before each chunk.
- `M_device(k)`: median over measured chunks of `total - free` from `torch.cuda.mem_get_info()` at the chunk boundary (process-level, includes CUDA context and allocator reserve).
- `R_M = (M_persistent(4) - M_fixed) / (M_persistent(1) - M_fixed)`; `dM = M_persistent(4) - M_persistent(1)`.
- Admission proxy on the measured GPU with total HBM `H`:
  `S_mem(k) = floor((H - M_device_fixed - 1 GiB headroom) / (M_persistent(k) - M_fixed + (M_peak(k) - M_persistent(k))))`
  `S_compute(k) = floor(achieved_fps(k) / 16)` where achieved_fps uses the median per-chunk service time (time-slicing upper bound for one process; cross-session batching could raise this, which only strengthens the memory-bound argument if S_mem < S_compute).
  "Materially affects admission" := `S_mem(k) <= S_compute(k)` for at least one k in {2,3,4} AND `S_mem(1) - S_mem(4) >= 2` sessions on the measured GPU.
- Verdict: GO if `R_M >= 2` and the admission clause holds; GRAY if `1.3 <= R_M < 2`, or `R_M >= 2` but the admission clause fails only because `S_mem(1) - S_mem(4) < 2`; KILL if `R_M < 1.3`, or `|dM| < 256 MB`, or `S_mem(k) > S_compute(k)` for all k (HBM never binds before compute on this GPU, so the delta cannot change admission).
