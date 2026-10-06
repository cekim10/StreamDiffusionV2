# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 11:22:28 PDT; GPU NVIDIA L40S; commit 28a685add333894b89d33bb5f7303636df6949f6; video /home/ckim151/StreamDiffusionV2/examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **32.09 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **22.81 dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.4161317920312285**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = 1.

| config | bytes withheld (MB) | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 34.1 | 34.0 | 32.3 | 31.7 | 0.974 | 0.964 | 0.409 | 0.421 | 0 | -23 |
| seed_shift | 0.0 | 23.9 | 22.7 | 23.3 | 22.6 | 0.749 | 0.754 | 0.408 | 0.419 | 0 | None |
| drop_inflight | 0.2 | 10.4 | 21.3 | 30.8 | 30.7 | 0.696 | 0.954 | 0.358 | 0.420 | 0 | -23 |
| drop_kv_recent | 1,645.3 | 25.4 | 23.7 | 30.9 | 31.7 | 0.829 | 0.964 | 0.411 | 0.421 | 0 | -23 |
| drop_kv_sink | 1,645.3 | 27.8 | 24.1 | 20.5 | 20.3 | 0.821 | 0.777 | 0.388 | 0.425 | 0 | -23 |
| drop_kv_all | 3,290.6 | 20.9 | 17.8 | 17.5 | 18.7 | 0.665 | 0.747 | 0.398 | 0.417 | 0 | -23 |
| drop_vae_enc | 1,069.5 | 34.1 | 28.6 | 31.5 | 32.0 | 0.903 | 0.967 | 0.424 | 0.421 | 0 | -23 |
| drop_vae_dec | 1,801.1 | 19.6 | 26.7 | 32.0 | 31.7 | 0.833 | 0.964 | 0.391 | 0.421 | 0 | -23 |
| drop_vae_all | 2,870.5 | 19.6 | 23.1 | 31.4 | 32.0 | 0.784 | 0.967 | 0.402 | 0.421 | 0 | -23 |
| drop_all | 6,161.4 | 10.4 | 14.9 | 18.7 | 19.1 | 0.527 | 0.747 | 0.358 | 0.418 | 0 | -23 |
| cold_restart | 9,542.0 | nan | 17.3 | 21.3 | 21.5 | 0.612 | 0.799 | 0.412 | 0.421 | 4 | -23 |
| delay_kv_recent_1 | 1,645.3 | 25.4 | 25.0 | 31.5 | 31.7 | 0.854 | 0.964 | 0.410 | 0.421 | 0 | -23 |
| delay_kv_recent_2 | 1,645.3 | 25.4 | 23.7 | 30.9 | 31.7 | 0.829 | 0.964 | 0.411 | 0.421 | 0 | -23 |
| delay_kv_sink_1 | 1,645.3 | 27.8 | 26.1 | 25.5 | 24.8 | 0.871 | 0.878 | 0.397 | 0.424 | 0 | -23 |
| delay_kv_sink_4 | 1,645.3 | 27.8 | 24.1 | 20.5 | 20.3 | 0.821 | 0.777 | 0.388 | 0.425 | 0 | -23 |
| delay_kv_sink_16 | 1,645.3 | 27.8 | 24.1 | 20.5 | 20.3 | 0.821 | 0.777 | 0.388 | 0.425 | 0 | -23 |
| delay_kv_all_1 | 3,290.6 | 20.9 | 22.8 | 26.4 | 25.4 | 0.780 | 0.891 | 0.401 | 0.419 | 0 | -23 |
| drop_kv_sink_nr | 1,645.3 | 27.3 | 22.8 | 17.0 | 16.7 | 0.796 | 0.683 | 0.400 | 0.413 | 0 | -23 |
| delay_kv_sink_1_nr | 1,645.3 | 27.3 | 28.4 | 31.7 | 32.0 | 0.904 | 0.965 | 0.405 | 0.421 | 0 | -23 |
| delay_kv_sink_4_nr | 1,645.3 | 27.3 | 22.8 | 28.4 | 32.0 | 0.796 | 0.966 | 0.400 | 0.421 | 0 | -23 |
| delay_kv_sink_16_nr | 1,645.3 | 27.3 | 22.8 | 17.0 | 30.3 | 0.796 | 0.940 | 0.400 | 0.422 | 0 | -23 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: delay_kv_recent_1: [{'call': 31, 'restored': 'kv_recent', 'slots_restored': 120, 'slots_expired': 60}]; delay_kv_recent_2: [{'call': 32, 'restored': 'kv_recent', 'slots_restored': 60, 'slots_expired': 120}]; delay_kv_sink_1: [{'call': 31, 'restored': 'kv_sink', 'slots_restored': 120, 'slots_expired': 60}]; delay_kv_sink_4: [{'call': 34, 'restored': 'kv_sink', 'slots_restored': 0, 'slots_expired': 180}]; delay_kv_sink_16: [{'call': 46, 'restored': 'kv_sink', 'slots_restored': 0, 'slots_expired': 180}]; delay_kv_all_1: [{'call': 31, 'restored': 'kv_all', 'slots_restored': 300, 'slots_expired': 60}]; delay_kv_sink_1_nr: [{'call': 31, 'restored': 'kv_sink', 'slots_restored': 180, 'slots_expired': 0}]; delay_kv_sink_4_nr: [{'call': 34, 'restored': 'kv_sink', 'slots_restored': 180, 'slots_expired': 0}]; delay_kv_sink_16_nr: [{'call': 46, 'restored': 'kv_sink', 'slots_restored': 180, 'slots_expired': 0}]

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.

