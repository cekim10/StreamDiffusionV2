# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 17:00:40 PDT; GPU NVIDIA L40S; commit 2ce46de268836d251b7e2cce8e9263f027c8659f; video /home/ckim151/StreamDiffusionV2/examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.4161317920312285**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.406 | 0.418 | 0 | -29 |
| drop_inflight | 0.2 | 0.0 | - | 10.4 | 21.5 | 36.9 | 36.4 | 0.699 | 0.975 | 0.357 | 0.417 | 0 | -29 |
| drop_kv_recent | 1,645.3 | 0.0 | - | 25.7 | 23.6 | 39.7 | 47.7 | 0.833 | 0.997 | 0.409 | 0.418 | 0 | -29 |
| drop_vae_all | 2,870.5 | 0.0 | - | 19.6 | 23.2 | 39.7 | 46.5 | 0.793 | 0.996 | 0.399 | 0.418 | 0 | -29 |
| delay_kv_sink_4_nr | 1,645.3 | 0.0 | - | 28.0 | 23.0 | 34.3 | 43.8 | 0.800 | 0.994 | 0.399 | 0.418 | 0 | -29 |
| delay_kv_sink_16_nr | 1,645.3 | 0.0 | - | 28.0 | 23.0 | 17.0 | 38.1 | 0.800 | 0.964 | 0.399 | 0.419 | 0 | -29 |
| replay_3_sinkhist | 9,542.0 | 42.3 | 4983 | 25.7 | 26.2 | 28.2 | 28.0 | 0.868 | 0.908 | 0.405 | 0.419 | 0 | -29 |
| replay_3_sinkhist_pos | 9,542.0 | 42.3 | 4967 | 24.0 | 26.4 | 29.6 | 29.3 | 0.872 | 0.946 | 0.397 | 0.417 | 0 | -29 |
| replay_6_sinkhist_pos | 9,542.0 | 56.0 | 6614 | 31.8 | 31.9 | 35.4 | 34.4 | 0.948 | 0.973 | 0.408 | 0.418 | 0 | -29 |
| replay_3_sinkxfer | 7,896.7 | 14.9 | 1614 | 20.7 | 22.6 | 26.6 | 27.1 | 0.803 | 0.899 | 0.403 | 0.416 | 0 | -29 |
| replay_3_sinkxfer_pos | 7,896.7 | 14.9 | 1619 | 22.4 | 20.3 | 20.1 | 20.5 | 0.703 | 0.758 | 0.418 | 0.424 | 0 | -29 |
| replay_6_sinkxfer_pos | 7,896.7 | 28.6 | 3285 | 21.4 | 19.8 | 20.1 | 20.5 | 0.665 | 0.755 | 0.419 | 0.426 | 0 | -29 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: delay_kv_sink_4_nr: [{'call': 34, 'restored': 'kv_sink', 'slots_restored': 180, 'slots_expired': 0}]; delay_kv_sink_16_nr: [{'call': 46, 'restored': 'kv_sink', 'slots_restored': 180, 'slots_expired': 0}]

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 48] (sinkhist configs replay through the last one before M).

## Transfer vs seed+replay (analytic; full state 9,542 MB, RTT 10 ms, no decompression/serialization cost)

| config | seed MB | sink xfer MB | replay ms | T_move @0.1 Gbps | T_move @1 Gbps | T_move @10 Gbps | T_move @100 Gbps | T_recon @0.1 Gbps | T_recon @1 Gbps | T_recon @10 Gbps | T_recon @100 Gbps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| replay_3_sinkhist | 42.3 | 0 | 4983 | 800,449 | 80,054 | 8,014 | 810 | 8,539 | 5,348 | 5,028 | 4,997 |
| replay_3_sinkhist_pos | 42.3 | 0 | 4967 | 800,449 | 80,054 | 8,014 | 810 | 8,523 | 5,331 | 5,012 | 4,980 |
| replay_6_sinkhist_pos | 56.0 | 0 | 6614 | 800,449 | 80,054 | 8,014 | 810 | 11,321 | 7,094 | 6,671 | 6,629 |
| replay_3_sinkxfer | 14.9 | 1645 | 1614 | 800,449 | 80,054 | 8,014 | 810 | 140,889 | 15,551 | 3,017 | 1,763 |
| replay_3_sinkxfer_pos | 14.9 | 1645 | 1619 | 800,449 | 80,054 | 8,014 | 810 | 140,894 | 15,556 | 3,022 | 1,769 |
| replay_6_sinkxfer_pos | 28.6 | 1645 | 3285 | 800,449 | 80,054 | 8,014 | 810 | 143,710 | 17,336 | 4,699 | 3,435 |

Continuity of each replay config is in the main table (compare with `repeat`, the full-state-transfer equivalent).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.

