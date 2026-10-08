# Figure 7: continuity timeline after a single physical handoff

Drawn by `tools/eval/plot_fig7.py --bw 1000` from the frozen Phase 1 (sweep v3) run directories only. Phase 1 was not rerun and the harness was not modified. Every plotted PSNR value is a measured per-chunk value from `metrics.csv`; every event marker is a measured timestamp from `events.csv`. No synthetic or interpolated samples were added. Data behind the figure: `fig7_data.csv` (kind=chunk rows: one per generated chunk of each policy; kind=event rows: measured event times, with the chunk-axis position used for the markers).

## Selected run

| | |
|---|---|
| bandwidth | 1000 Mbps (sender token-bucket shaping over the MSS-1400 TCP transport) |
| workload / seed / k | `examples/original.mp4`, seed 0, k = 2 (480x832, Wan 1.3B causal DMD v2v) |
| migration | chunk 30 (identical for all policies and reps) |
| Ours run | `single_handoff/policy=ours_bw=1000_rep=2_workload=original_seed=0_k=2_mss=1400_20261008-140946` |
| companions (same rep) | `policy=cold_bw=1000_rep=2_..._20261008-141251`, `policy=replay_bw=1000_rep=2_..._20261008-141356`, `policy=full_bw=1000_rep=2_..._20261008-141052` |
| harness commit | `32acfb9` (git_commit.txt reads "dirty" on both hosts because the v2 result directories had just been moved into `_v2_async_checksum/` in the working tree; no code differed from `32acfb9`) |

Why this run is representative:
- 1 Gbps makes the three phases visible at chunk granularity: the Sink (1.65 GB) is in flight for ~14 s, i.e. 24 chunks of the destination's own stream, before binding at chunk 25. At native speed the gap is 4 chunks and at 250 Mbps it is 97 chunks, which would compress or stretch panel (a) beyond legibility.
- Rep 2 has the median continuity-ready time of the three 1 Gbps reps (15.33 s vs 15.63 / 15.33 s). The three reps are bit-identical in per-chunk PSNR (same bind chunk 25, same rejoin +6, same PSNR sequence); they differ only in transfer timing by a few hundred ms.

## Measured events (seconds since migration start; destination clock)

| event | t (s) | chunk-axis position |
|---|---|---|
| GO (in-flight rows + metadata landed, 2.8 MB) | 0.159 | before chunk 0 |
| first output on the destination (chunk 30 = chunk 0 on the axis) | 0.712 | 0 |
| Sink received (1.73 GB incl. framing; H2D 0.40 s included) | 14.393 | 23.5 |
| Sink verified (parallel per-tensor SHA-256, compared with the source digest) | 14.474 | 23.6 |
| Sink bound (next chunk boundary; 73 slot keys re-rotated) | 14.783 | 24.1 (bound call = 55 = chunk 25) |
| first output produced on the transferred Sink | 15.33 | 25 |
| rejoin: first chunk with PSNR >= 35 dB vs the uninterrupted run | 18.887 | 31 (= bind + 6 calls) |
| SDV2-FullMigration first output (same rep) | 53.78 | not drawable on the chunk axis (no output for 90 chunk-times) |

Chunk-axis position of an event = linear position between the measured output times of the two neighbouring chunks (chunk r is produced during (t_out[r-1], t_out[r]]). This is a placement rule for markers only; it creates no data.

## Phases of Ours (panel a)

1. Execution-ready: output flows from chunk 0 (0.71 s after migration start). Restart produces nothing for chunk 0 and its first output is at 1.06 s; Replay's first output is at 6.1 s; FullMigration's at 53.8 s.
2. Continuity gap (chunks 0-24): the destination runs a valid stream from the in-flight rows and fresh KV, but it is a different trajectory: PSNR 15.3-17.3 dB vs the uninterrupted run (Restart 15.8-23.6 dB, Replay 24-33.7 dB on the same axis).
3. Post-bind recovery (chunks 25-31): after the Sink binds, PSNR rises monotonically 18.6 -> 21.0 -> 23.0 -> 26.7 -> 28.5 -> 30.5 -> 35.6 dB (chunks +0..+6) and reaches the rejoin criterion 6 calls after bind.
4. On the original trajectory (chunk 31 onward): PSNR 40.3-46.4 dB, mean 43.9 dB from bind+8 to the end of the window (chunk 79).

## Validation (printed by the script; all from the frozen v3 directories)

- rejoin_calls_after_bind == 6 for the selected run: OK (bound call 55, first chunk >= 35 dB is call 61 at 35.6 dB).
- post-bind PSNR range, raw: calls 55-109 min 18.6 / max 46.4 dB; from bind+8 onward min 40.3 / max 46.4 / mean 43.9 dB.
- SDV2-Restart never reaches the rejoin criterion: max 23.6 dB over 79 chunks (Replay max 33.7 dB, also never).
- FullMigration is bit-identical (sentinel 99 dB) for every one of its 80 chunks; it is shown as a reference annotation plus the off-axis bar in panel (b) because it has no output for the first 53.8 s and cannot be put on the chunk axis fairly.
- All four run directories are top-level directories of `results/evaluation/single_handoff/` (sweep v3); none come from `_v1_inline_checksum/`, `_v2_async_checksum/` or `_shakedown/`.

## Consistency at other bandwidths (Ours, all 3 reps each; same script with --bw native / 250)

| bw (Mbps) | bind chunk | rejoin (calls after bind) | Sink received (s) | bound (s) | rejoin (s) | PSNR in gap, mean (dB) | PSNR from bind+8, mean (dB) |
|---|---|---|---|---|---|---|---|
| 250 | 97-98 | 6, 7, 6 | 55.95-56.48 | 56.35-56.96 | 60.45-61.66 | 16.8 | 39.4-39.5 |
| 500 | 50 | 8, 8, 8 | 28.70-28.77 | 29.21-29.29 | 34.50-34.60 | 16.7 | 39.5 |
| 1000 | 25 | 6, 6, 6 | 14.32-14.66 | 14.77-15.08 | 18.89-19.18 | 16.7 | 43.9 |
| 2500 | 11 | 6, 6, 6 | 6.14-6.18 | 6.61-6.64 | 10.72-10.74 | 16.5 | 43.7 |
| 5000 | 6 | 6, 6, 6 | 3.29-3.30 | 3.73-3.75 | 7.84-7.85 | 16.2 | 43.9 |
| native | 4 | 6, 6, 6 | 2.07-2.09 | 2.53-2.54 | 6.63-6.65 | 16.1 | 45.4 |

The qualitative shape is the same at every bandwidth: flat ~16-17 dB gap while the Sink is in flight, bind at the next chunk boundary after arrival, recovery to >= 35 dB in 6 calls (7-8 at 250/500 Mbps, where the Sink is 50-100 chunks old at bind), then 39-45 dB. The post-bind plateau is lower the later the Sink binds (45.4 dB at 4 chunks late, 39.4 dB at 97 chunks late), consistent with the late-binding study in the state-ablation notes.

## Frames

Generated frames were not saved by the Phase 1 harness (the run directories contain config/events/metrics/network/summary only; no image or array files exist anywhere under `results/evaluation/`). Per the Phase 1 freeze, generation was not rerun to produce them: a rerun would be a different execution, and its frames could not be claimed as the frames of the plotted run. If a frame strip is wanted for the paper, it needs a separate, explicitly labelled run (e.g. a Phase 2 'frames' pass with the same seed/k/bandwidth that also saves frames at migration, mid-gap, pre-bind, bind+0, bind+3 and rejoin); the earlier qualitative strips under results/state_migration/figures/ come from the single-host state-ablation runs, not from this handoff.

## Note on Fig. 6 panel (b)

While building Fig. 7 it became clear that `continuity_ready_rel_s` is the time of the first output produced on the transferred Sink (bind), not the time the stream is back on the original trajectory (rejoin, 6 calls later). Fig. 6(b), its table header and the Phase 1 notes were relabelled "Sink bound" accordingly; no numbers changed.
