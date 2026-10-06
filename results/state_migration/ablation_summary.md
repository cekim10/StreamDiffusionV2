# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-05 23:35:25 PDT; GPU NVIDIA L40S; commit eb5a718f50826be9effcdca1d6c00bf88570f16c; video /home/ckim151/StreamDiffusionV2/examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **32.09 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **22.81 dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

| config | bytes withheld (MB) | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|
| repeat | 0 | 34.1 | 34.0 | 32.3 | 31.7 | 0.974 | 0.964 | 0 | 0 |
| seed_shift | 0 | 23.9 | 22.7 | 23.3 | 22.6 | 0.749 | 0.754 | 0 | None |
| drop_inflight | 0 | 34.1 | 34.0 | 32.3 | 31.7 | 0.974 | 0.964 | 0 | 0 |
| drop_kv_recent | 1,645 | 25.4 | 23.7 | 30.9 | 31.7 | 0.829 | 0.964 | 0 | 7 |
| drop_kv_sink | 1,645 | 27.8 | 24.1 | 20.5 | 20.3 | 0.821 | 0.777 | 0 | None |
| drop_kv_all | 3,291 | 20.9 | 17.8 | 17.5 | 18.7 | 0.665 | 0.747 | 0 | None |
| drop_vae_enc | 1,069 | 34.1 | 28.6 | 31.5 | 32.0 | 0.903 | 0.967 | 0 | 0 |
| drop_vae_dec | 1,801 | 19.6 | 26.7 | 32.0 | 31.7 | 0.833 | 0.964 | 0 | 3 |
| drop_vae_all | 2,871 | 19.6 | 23.1 | 31.4 | 32.0 | 0.784 | 0.967 | 0 | 6 |
| drop_all | 6,161 | 16.5 | 16.1 | 18.0 | 18.8 | 0.570 | 0.748 | 0 | None |
| cold_restart | 9,542 | 15.4 | 17.0 | 21.3 | 21.5 | 0.607 | 0.799 | 4 | None |
| delay_kv_recent_1 | 1,645 | 25.4 | 25.0 | 31.5 | 31.7 | 0.854 | 0.964 | 0 | 6 |
| delay_kv_recent_2 | 1,645 | 25.4 | 23.7 | 30.9 | 31.7 | 0.829 | 0.964 | 0 | 7 |
| delay_kv_sink_1 | 1,645 | 27.8 | 26.1 | 25.5 | 24.8 | 0.871 | 0.878 | 0 | None |
| delay_kv_sink_4 | 1,645 | 27.8 | 24.1 | 20.5 | 20.3 | 0.821 | 0.777 | 0 | None |
| delay_kv_sink_16 | 1,645 | 27.8 | 24.1 | 20.5 | 20.3 | 0.821 | 0.777 | 0 | None |
| delay_kv_all_1 | 3,291 | 20.9 | 22.8 | 26.4 | 25.4 | 0.780 | 0.891 | 0 | None |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: delay_kv_recent_1: [{'call': 31, 'restored': 'kv_recent', 'slots_restored': 120, 'slots_expired': 60}]; delay_kv_recent_2: [{'call': 32, 'restored': 'kv_recent', 'slots_restored': 60, 'slots_expired': 120}]; delay_kv_sink_1: [{'call': 31, 'restored': 'kv_sink', 'slots_restored': 120, 'slots_expired': 60}]; delay_kv_sink_4: [{'call': 34, 'restored': 'kv_sink', 'slots_restored': 0, 'slots_expired': 180}]; delay_kv_sink_16: [{'call': 46, 'restored': 'kv_sink', 'slots_restored': 0, 'slots_expired': 180}]; delay_kv_all_1: [{'call': 31, 'restored': 'kv_all', 'slots_restored': 300, 'slots_expired': 60}]

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.

