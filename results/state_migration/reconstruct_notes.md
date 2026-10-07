# Reconstruct baseline reading (runs reconstruct, reconstruct2, reconstruct3, reconstruct4; harness 2ce46de; bit-exact from reconstruct2 on)

L40S, 1.3B, k=2, 480x832, M=30, 40 calls after. PSNR vs the uninterrupted baseline: 99 = bit-exact, 40+ = near-identical, 30-35 = same stream with small differences, 20-23 = a different valid stream (seed_shift level).

## Established
1. Replay is deterministic. `replay_full` (first batch + all 30 chunks, same seeds) is bit-exact (99 dB). Cost 17.2 s for 30 chunks of history, i.e. ~570 ms per history chunk vs a 250 ms chunk period at 16 FPS: full replay runs 2.3x slower than real time on this GPU and its cost grows with session length. Full replay is therefore not a general migration path; replay must be truncated, and truncation costs continuity.
2. The sink depends on refresh history. Adaptive sink refresh fired at calls 4 and 48; at M the sink slots hold frames [0, 1, 6]. A sink rebuilt from the first batch alone (`sink0`) reaches 26.9 dB; replaying through the last refresh (`sinkhist`) 28.0; adding faithful positions / noise-EMA / last_image metadata (`_pos`) 29.3 with W=3 and 34.4 dB / SSIM 0.973 with W=6.
3. Transfer into the live session heals to near-identical. In the bit-exact harness: drop_kv_recent -> 47.7 dB long-term (SSIM 0.997), drop_vae_all -> 46.5, drop_inflight -> 36.4, sink delivered 4 calls late (refresh off) -> 43.8, 16 calls late -> 38.1. Recent KV loss is fully forgiven once the 3-slot window refills; sink loss is not forgiven until the sink arrives, and it may arrive 16 chunks (4 s) late.
4. Truncated replay has a ceiling below transfer. Best replay (W=6, sinkhist, pos) 34.4 dB vs transfer-side 38-48 dB. Replay reproduces tensors but not the ring-buffer bookkeeping (slot layout, eviction order) that the live session carries; only full-history replay reproduces that.
5. Latency crossover: full state 9.5 GB moves in 80 s at 1 Gbps, 8 s at 10 Gbps, 0.8 s at 100 Gbps; truncated replay costs 1-7 s plus 10-60 MB of raw frames. Replay wins below ~10-100 Gbps on latency; transfer wins on continuity and on long sessions where replay cost exceeds the link time.

## Not interpretable yet
`replay_W_sinkxfer` (fresh session from chunk M-W, then overwrite sink slots with the transferred originals): 27.1 dB without `_pos`, 20.5 dB with `_pos` (worse than no sink). The implementation of copying original sink slots into a freshly prepared ring buffer is not validated (slot bookkeeping, eviction state and the order of overwrite vs replay). Treat as a harness issue to debug before drawing any conclusion about the hybrid design.

## Reading
State moves because of continuity, not quality (SSIM-vs-input ~0.42 for every config). Within continuity, the durable part is the sink plus its ring position bookkeeping; everything else regenerates within ~8 calls. The design space that survives: transfer the sink late over a slow path (it tolerates 4-16 chunks of delay), regenerate the rest at the destination from seeds within the first second, and carry session metadata verbatim. Whether a placeholder sink can hide the gap before the true sink arrives is the next mechanism experiment.
