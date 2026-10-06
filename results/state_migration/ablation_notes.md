# State-ablation reading (run 3, commit 28a685a harness, results commit 0ab7b4a)

L40S, 1.3B, k=2, 480x832, official example tiled, M=30, 40 calls after. All numbers from `ablation_summary.md` / `ablation_raw.csv`.

## References
- `repeat` (same state, same seeds): 32.1 dB mean, not bit-exact. Root cause found after the run: `prepare()` aliases `timestep` to `denoising_step_list` and `inference_stream` writes the adaptive step into it, so a second session starts with a drifted schedule (fixed in harness commit e0cc615; also affects the official restart path). Pre-M divergence shrinks from 27.5 dB (call 1) to 33 dB (call 29), i.e. the two sessions converge as the ring buffer flushes the different start, which is consistent with that cause. Relative comparisons between configs are unaffected because every config shares the same second-session schedule.
- `seed_shift` (same state, different noise): 22.8 dB, SSIM 0.75 vs baseline, SSIM-vs-input 0.419 (baseline 0.421). This is what "an equally valid but different stream" looks like.

## Per-component findings (bytes at k=2)
| component | bytes | immediate effect (M+0..3) | horizon / recovery | late delivery |
|---|---|---|---|---|
| in-flight denoising row | 0.2 MB | 10.4 dB at M+0 (one destroyed chunk), 21.3 over M+0..3 | recovers by M+4 | n/a (advances every call) |
| VAE encoder cache | 1,069 MB | none at M+0, -5 dB over M+1..3 | recovers at M+4 | useless after 1 call (rewritten) |
| VAE decoder cache | 1,801 MB | 19.6 dB at M+0 | recovers by M+3 | useless after 1 call |
| recent KV (3 slots) | 1,645 MB | 23.7 over M+0..3 (-10 dB) | recovers by ~M+6 by natural refill | +1 call: 25.0 (slight), +2 calls: 23.7 (none) |
| sink KV, adaptive refresh ON | 1,645 MB | 24.1 over M+0..3 | never returns to baseline (20 dB), but SSIM-vs-input 0.425 >= baseline: a different valid stream, not a worse one | +1: partial (120/180 slots), +4/+16: 0 slots restorable, refresh already replaced them |
| sink KV, adaptive refresh OFF | 1,645 MB | 22.8 over M+0..3 | without delivery: 17 dB forever, SSIM 0.68 and SSIM-vs-input 0.413 < baseline: genuinely degraded (attending to zero keys) | **+1: 31.7/32.0 full recovery; +4: 32.0 full; +16: 30.3 (SSIM 0.94) near-full, recovering within ~8 calls of arrival** |
| cold restart (official path) | all | 4 missing frames, 17.3 over M+0..3 | settles at 21.5 dB / SSIM 0.80, SSIM-vs-input 0.421: a fresh valid stream | n/a |

## Against the frozen gates (state_map.md section 4)
- Obs 1 (criticality): GRAY. Impact per byte is extremely heterogeneous (0.2 MB in-flight row = -13 dB at M+0; 1.07 GB encoder cache = -5 dB for one call; 1.6 GB recent KV = -10 dB), but there is no small working set in raw bytes: immediate continuity needs decoder cache + recent KV + in-flight (3.4 GB, 56%) and long-term identity needs the sink (27%). The gate's ">=50% withheld within 1 dB" clause is not met by any config.
- Obs 2 (urgency): PASS, with a mechanism-level tension. Sink KV delivered 4 to 16 calls (1 to 4 s) late fully restores continuity with the original stream, while recent KV delivered 2 calls late is worthless. Deadlines differ by >= 8x between the two halves of the same KV tensor. The tension: during the wait the destination either (a) keeps zeroed sinks (refresh off) and renders degraded frames, or (b) lets adaptive refresh promote recent frames to sinks and immediately produces a good-looking but different stream, after which the true sinks can no longer be slotted in. Neither is what the AR use case wants (same dragon, no bad frames); a placeholder-then-swap design is the obvious candidate and is untested.

## What the metrics say about the problem itself
Long-term SSIM-vs-input is ~0.42 for every config including drop_all and cold restart. Execution state does not buy quality after a few chunks; it buys **continuity with the pre-migration stream** (same identity/style). The right objective for this line of work is a continuity metric at the migration boundary (identity/style similarity to pre-migration frames, flicker at the seam), not generic video quality.

## Strong baseline still unmeasured
Every component above is reconstructable from kilobytes to a few MB of seeds (noisy latents, last raw frames) plus replay compute (~0.4-1 s on L40S): decoder cache from one latent, recent KV from 3 latents, sink KV from the first chunk's latents and seeds (deterministic replay), in-flight row from chunk M-1's input. A `reconstruct_*` config family must be run before any data-path design is claimed; if seed+replay matches full-state transfer, the problem becomes scheduling recompute against deadlines at the destination, not routing GB of state.

## Caveats
- "Drop" = zero-filled slots that attention still spans; this models an empty destination buffer, not masked-out slots. The refresh-off sink numbers in particular include the cost of attending to zero keys.
- One video, one prompt, one seed, k=2, L40S. The sink-delay result is the one to replicate first (other content, k=1 and k=4, a second seed).
