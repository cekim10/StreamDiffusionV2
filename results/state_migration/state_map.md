# StreamDiffusionV2 execution-state map for migration experiments

Code-level inventory of every per-session object, its measured size, how long it stays useful (structural horizon), how to drop or delay it for a criticality ablation, and what it can be rebuilt from. Sizes are from the Phase 0A run on L40S (`results/quality_elastic/phase0a_static_k{1,2}.json`, 1.3B, 480x832, commit e0c9d34); k = denoising steps (official demo default k=2).

## 1. Inventory (measured, physical bytes on GPU)

| state object | where it lives | k=1 | k=2 | k-dependence | structural horizon | reconstructable from |
|---|---|---|---|---|---|---|
| KV cache, recent slots (3 latent frames) | `pipeline.kv_cache1[i]['k'/'v']` slots 3..5, 30 layers (`models/wan/causal_stream_inference.py:88-110`) | 823 MB | 1,645 MB | linear (`repeat`) | overwritten after 3 more chunks (ring buffer, `num_kv_cache: 6`) | replaying the DiT on the 3 stored noisy-latent inputs (3 x 200 KB x k) in order; ~75 ms per frame-forward on L40S |
| KV cache, sink slots (3 latent frames) | same tensors, slots 0..2 (`sink_tokens = 3 * 1560`, `causal_model.py:318`) | 823 MB | 1,645 MB | linear | persists for the whole session; replaced only by adaptive sink refresh (`causal_model.py:332-347`, cosine-sim < 0.2) | the inputs that produced them (session start frame or a refresh frame) + one forward each |
| KV metadata: `pos`, `global/local_end_index`, `evict_idx` | `kv_cache1[i]`, `self_attn.evict_idx` (python) | < 1 KB | < 1 KB | none | must match the slot contents | nothing; always send |
| Cross-attn cache | `pipeline.crossattn_cache[i]['k'/'v']` (`expand` view) | 90 MB | 90 MB | none | whole session (until prompt change) | prompt_embeds (4 MB) + one K/V projection per layer (sub-ms); or prompt text + T5 (~hundreds of ms) |
| Prompt embeds | `conditional_dict['prompt_embeds']` [k,512,4096] | 4 MB | 8 MB | linear | whole session | prompt text + umt5-xxl (10.8 GB of weights must be resident) |
| In-flight denoising rows | `pipeline.hidden_states` [k,1,16,60,104] | 0.2 MB | 0.4 MB | linear | advance every chunk; row j is lost if not delivered before the next call | nothing cheap: they are partially denoised chunks whose noisy inputs are gone unless kept |
| RoPE / stream positions | `session.current_start/_end`, `pipeline.kv_cache_starts/_ends`, `timestep` | bytes | bytes | none | every chunk | re-derivable from chunk index (t_refresh rewind at 50) |
| VAE encoder feature cache | `vae.model._enc_feat_map` (one entry per CausalConv3d, last `CACHE_T=2` input frames each; `vae.py:14,207-216`) | ~2.2 GB (est.) | same | none | **fully replaced by the next chunk** (each chunk writes all entries) | the last 2 raw input pixel frames (2 x 2.4 MB bf16) + one encoder pass (143 ms on L40S) |
| VAE decoder feature cache | `vae.model._feat_map` (`vae.py:611-660`) | ~0.7 GB (est.) | same | none | fully replaced by the next decode | the last decoded latent frame (200 KB) + one decoder pass (250 ms on L40S) |
| `last_image`, `noise_scale`, `init_noise_scale` | `SingleGPUStreamSession` | 2.4 MB | 2.4 MB | none | next chunk only (motion-adaptive step, `inference.py:51-57`) | the last raw frame |
| Model weights | DiT 2.7 GB, umt5-xxl 10.8 GB, VAE 242 MB | 13.8 GB | 13.8 GB | none | static | pre-provisioned at every edge |

VAE cache total measured: 2,870 MB; encoder/decoder split is estimated from layer widths and should be measured by the harness (`vae_enc_bytes`, `vae_dec_bytes` columns).

## 2. What the code structure already decides

1. **The horizon of most bytes is one chunk.** 62% of per-session state (VAE caches, 2.87 GB) is rewritten on every chunk. Delaying it by even one chunk is identical to dropping it. "Soon" delivery does not exist for this state: it is either on the fast path or reconstructed.
2. **Recent KV expires in 3 chunks (0.75 s at 16 FPS).** The ring buffer overwrites the oldest non-sink slot each chunk (`causal_model.py:350-376`). A delayed delivery is useful only for slots whose `pos` is unchanged on arrival; the harness restores slot-by-slot under that check.
3. **Sink KV is the only long-lived state.** Three latent frames (823 MB x k) persist for the session. This is the natural "deferrable but durable" candidate: if quality survives its absence for a while, it can go on a background path or be pre-positioned.
4. **Almost everything is reconstructable from kilobytes to megabytes of seeds plus one forward pass.** VAE caches from 2 raw frames, KV from 6 stored noisy latents, cross-attn from 4 MB of embeds. Send-seeds-and-recompute is therefore the strong baseline that any "route the state" design has to beat, and it only loses when the destination is compute-starved or the recompute latency exceeds the frame deadline. Both sides must be measured (Obs 3) before claiming a data-path design.
5. **Cold restart is the existing migration path.** A prompt change already does `reset_stream_state` + `start_stream_session` (`demo/vid2vid.py:557-575`), costing 0.98-1.19 s on L40S plus a k-1 chunk output bubble. Any state-transfer scheme is compared against this.

## 3. Ablation mechanics (what `tools/state_ablation.py` does at migration chunk M)

| config | operation at chunk boundary M | bytes withheld (k=2) | notes |
|---|---|---|---|
| `repeat` | nothing | 0 | determinism floor; both runs reseed `torch.manual_seed(seed + chunk)` before every chunk |
| `drop_kv_recent` | `k[:, 3*fsl:] = 0`, `v[...] = 0` in all 30 layers | 1,645 MB | zero = fresh buffer at destination; attention still spans the slots (cache_seqlens unchanged), so this models "arrived empty", not "masked" |
| `drop_kv_sink` | zero slots 0..2 | 1,645 MB | |
| `drop_kv_all` | zero all 6 slots | 3,291 MB | |
| `drop_vae_enc` / `drop_vae_dec` / `drop_vae_all` | `.zero_()` every tensor in `_enc_feat_map` / `_feat_map` | ~2.2 / ~0.7 / 2.87 GB | keeps shapes and the `'Rep'` markers so the encode/decode path is unchanged; setting entries to `None` would silently skip the temporal downsample and change the latent count |
| `drop_inflight` | `hidden_states[1:] = 0` (k >= 2) | 0.2 MB x (k-1) | the k-1 chunks in flight are lost |
| `drop_all` | all of the above | ~6.2 GB | metadata and prompt embeds kept: "destination has weights + metadata only" |
| `cold_restart` | `start_stream_session(prompt, [last_image, chunk M])` | everything | official prompt-switch path; produces a k-1 chunk output gap |
| `delay_kv_recent_d`, `delay_kv_sink_d`, `delay_kv_all_d` | snapshot slots at M, zero them, restore at M+d only where `pos[slot]` is unchanged | as drop | d in {1,2,4,16}; recent slots are all gone by d=3 by construction |

Quality is scored per frame against the uninterrupted baseline run with the same seeds: PSNR and SSIM, per call index relative to M, plus the recovery point (first call whose mean PSNR is within 1 dB of the `repeat` floor).

## 4. Planned gates (frozen before running)

- **Obs 1 (criticality) is a signal** if some config withholding >= 50% of bytes keeps mean PSNR over calls M..M+3 within 1 dB of `repeat`, AND at least one small component (in-flight rows, recent KV, or VAE enc cache) costs >= 3 dB when dropped. Otherwise state is uniformly important (KILL for heterogeneity) or uniformly unimportant (KILL: just restart).
- **Obs 2 (urgency) is a signal** if sink-KV delay of 4-16 chunks recovers to within 1 dB while recent-KV delay of 2 does not, i.e. deadlines differ by >= 4x between components. If every delay behaves like drop, there is no "soon" tier and the design collapses to fast path + reconstruct.
- **Obs 3 (crossover)** is computed, not run: with T_fast = bytes_fast / BW and T_rebuild from Phase 0A stage times, report the bandwidth below which seed+recompute beats any transfer scheme. If that bandwidth is above what edge links offer (>= 1 Gbps), the data-path thesis is KILL regardless of Obs 1/2.
