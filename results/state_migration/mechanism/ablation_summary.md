# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 18:00:52 PDT; GPU NVIDIA L40S; commit 1682bb9f4acdfb13ef51f5c0dd1c31a9e7dc0722; video /home/ckim151/StreamDiffusionV2/examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.4161317920312285**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.406 | 0.418 | 0 | -29 |
| xfer_all | 3,378.3 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.406 | 0.418 | 0 | -29 |
| xfer_sink+meta | 7,894.4 | 0.0 | - | 10.2 | 16.7 | 33.5 | 35.2 | 0.540 | 0.970 | 0.352 | 0.417 | 0 | -29 |
| xfer_sink+meta+vae | 5,023.8 | 0.0 | - | 9.2 | 17.1 | 34.1 | 35.8 | 0.621 | 0.972 | 0.347 | 0.418 | 0 | -29 |
| xfer_sink+meta+vae+inflight | 5,023.6 | 0.0 | - | 25.7 | 23.6 | 39.7 | 47.7 | 0.833 | 0.997 | 0.409 | 0.418 | 0 | -29 |
| xfer_meta | 9,539.7 | 0.0 | - | 10.4 | 14.9 | 18.7 | 19.1 | 0.527 | 0.747 | 0.358 | 0.418 | 0 | -29 |
| xfer_meta+vae+inflight | 6,669.0 | 0.0 | - | 21.1 | 17.8 | 17.5 | 18.7 | 0.666 | 0.747 | 0.398 | 0.417 | 0 | -29 |
| replay_3_sinkhist_pos | 9,542.0 | 42.3 | 4963 | 24.0 | 26.4 | 29.6 | 29.3 | 0.872 | 0.946 | 0.397 | 0.417 | 0 | -29 |
| ph_localrefresh | 1,645.3 | 0.0 | - | 28.6 | 24.4 | 20.5 | 20.3 | 0.826 | 0.777 | 0.388 | 0.424 | 0 | -29 |
| ph_zero_noswap | 1,645.3 | 0.0 | - | 28.0 | 23.0 | 17.0 | 16.7 | 0.800 | 0.683 | 0.399 | 0.413 | 0 | -29 |
| ph_local_noswap | 1,645.3 | 0.0 | - | 28.9 | 24.1 | 21.1 | 20.7 | 0.822 | 0.778 | 0.385 | 0.406 | 0 | -29 |
| ph_zero_1 | 1,645.3 | 0.0 | - | 28.0 | 29.3 | 40.7 | 43.8 | 0.915 | 0.994 | 0.403 | 0.418 | 0 | -29 |
| ph_zero_4 | 1,645.3 | 0.0 | - | 28.0 | 23.0 | 34.3 | 43.8 | 0.800 | 0.994 | 0.399 | 0.418 | 0 | -29 |
| ph_zero_8 | 1,645.3 | 0.0 | - | 28.0 | 23.0 | 23.5 | 43.0 | 0.800 | 0.993 | 0.399 | 0.418 | 0 | -29 |
| ph_zero_16 | 1,645.3 | 0.0 | - | 28.0 | 23.0 | 17.0 | 38.1 | 0.800 | 0.964 | 0.399 | 0.419 | 0 | -29 |
| ph_local_1 | 1,645.3 | 0.0 | - | 28.9 | 29.1 | 41.7 | 43.8 | 0.923 | 0.994 | 0.399 | 0.418 | 0 | -29 |
| ph_local_4 | 1,645.3 | 0.0 | - | 28.9 | 24.1 | 36.8 | 43.9 | 0.822 | 0.994 | 0.385 | 0.418 | 0 | -29 |
| ph_local_8 | 1,645.3 | 0.0 | - | 28.9 | 24.1 | 28.4 | 43.4 | 0.822 | 0.993 | 0.385 | 0.418 | 0 | -29 |
| ph_local_16 | 1,645.3 | 0.0 | - | 28.9 | 24.1 | 21.1 | 38.8 | 0.822 | 0.973 | 0.385 | 0.419 | 0 | -29 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 48] (sinkhist configs replay through the last one before M).

## Transfer vs seed+replay (analytic; full state 9,542 MB, RTT 10 ms, no decompression/serialization cost)

| config | seed MB | sink xfer MB | replay ms | T_move @0.1 Gbps | T_move @1 Gbps | T_move @10 Gbps | T_move @100 Gbps | T_recon @0.1 Gbps | T_recon @1 Gbps | T_recon @10 Gbps | T_recon @100 Gbps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| replay_3_sinkhist_pos | 42.3 | 0 | 4963 | 800,449 | 80,054 | 8,014 | 810 | 8,519 | 5,327 | 5,008 | 4,976 |

Continuity of each replay config is in the main table (compare with `repeat`, the full-state-transfer equivalent).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_localrefresh | - | 22.6 (M+0..7) | 0.806 | n/a (never swapped) | 20.3 (M+16..) | 0.777 |
| ph_zero_noswap | - | 20.1 (M+0..7) | 0.757 | n/a (never swapped) | 16.7 (M+16..) | 0.683 |
| ph_local_noswap | - | 22.8 (M+0..7) | 0.802 | n/a (never swapped) | 20.7 (M+16..) | 0.778 |
| ph_zero_1 | 1 | 28.0 | 0.859 | 2 | 43.9 | 0.993 |
| ph_zero_4 | 4 | 23.0 | 0.800 | 4 | 43.8 | 0.994 |
| ph_zero_8 | 8 | 20.1 | 0.757 | 5 | 43.0 | 0.993 |
| ph_zero_16 | 16 | 18.5 | 0.723 | 4 | 42.4 | 0.992 |
| ph_local_1 | 1 | 28.9 | 0.879 | 2 | 44.0 | 0.994 |
| ph_local_4 | 4 | 24.1 | 0.822 | 3 | 44.1 | 0.994 |
| ph_local_8 | 8 | 22.8 | 0.802 | 3 | 43.4 | 0.993 |
| ph_local_16 | 16 | 21.8 | 0.788 | 4 | 42.8 | 0.993 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_all | 99.0 | 99.0 | 1.000 | 99.0 | sink 1,645 MB, recent 1,645 MB, meta 2 MB, vae 2,871 MB, inflight 0 MB |
| xfer_sink+meta | 10.2 | 22.5 | 0.540 | 35.2 | sink 1,645 MB, meta 2 MB |
| xfer_sink+meta+vae | 9.2 | 22.9 | 0.621 | 35.8 | sink 1,645 MB, meta 2 MB, vae 2,871 MB |
| xfer_sink+meta+vae+inflight | 25.7 | 27.1 | 0.833 | 47.7 | sink 1,645 MB, meta 2 MB, vae 2,871 MB, inflight 0 MB |
| xfer_meta | 10.4 | 16.4 | 0.527 | 19.1 | meta 2 MB |
| xfer_meta+vae+inflight | 21.1 | 17.4 | 0.666 | 18.7 | meta 2 MB, vae 2,871 MB, inflight 0 MB |
| replay_3_sinkhist_pos | 24.0 | 27.6 | 0.872 | 29.3 | seed 42 MB, replay 4963 ms |
