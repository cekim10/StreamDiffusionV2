# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 19:41:57 PDT; GPU NVIDIA L40S; commit f529cae23a7a4d7a9c4f591b18381f1b588d6a35; video examples/boxing.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.23937083473429083**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.224 | 0.245 | 0 | -29 |
| drop_inflight | 0.2 | 0.0 | - | 10.4 | 22.8 | 39.0 | 38.7 | 0.615 | 0.988 | 0.333 | 0.253 | 0 | -29 |
| drop_kv_recent | 1,645.3 | 0.0 | - | 24.3 | 24.8 | 36.2 | 37.9 | 0.859 | 0.989 | 0.267 | 0.250 | 0 | -29 |
| drop_vae_all | 2,870.5 | 0.0 | - | 21.1 | 23.8 | 34.8 | 35.6 | 0.707 | 0.984 | 0.368 | 0.249 | 0 | -29 |
| xfer_sink+meta+inflight | 7,894.2 | 0.0 | - | 20.9 | 21.5 | 33.9 | 35.6 | 0.586 | 0.985 | 0.442 | 0.245 | 0 | -29 |
| xfer_sink+meta | 7,894.4 | 0.0 | - | 8.8 | 17.7 | 32.3 | 32.5 | 0.367 | 0.971 | 0.432 | 0.244 | 0 | -29 |
| xfer_meta+inflight | 9,539.5 | 0.0 | - | 19.2 | 18.4 | 22.1 | 22.2 | 0.574 | 0.816 | 0.361 | 0.215 | 0 | -29 |
| ph_zero_8 | 1,645.3 | 0.0 | - | 29.0 | 24.6 | 27.1 | 35.2 | 0.878 | 0.983 | 0.192 | 0.246 | 0 | -29 |
| ph_local_8 | 1,645.3 | 0.0 | - | 29.9 | 26.5 | 29.1 | 35.2 | 0.894 | 0.983 | 0.186 | 0.246 | 0 | -29 |
| ph_localrefresh | 1,645.3 | 0.0 | - | 29.5 | 26.4 | 23.1 | 22.7 | 0.895 | 0.829 | 0.188 | 0.239 | 0 | -29 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 32, 48] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_zero_8 | 8 | 22.7 | 0.843 | 2 | 35.2 | 0.983 |
| ph_local_8 | 8 | 25.0 | 0.873 | 2 | 35.2 | 0.983 |
| ph_localrefresh | - | 24.5 (M+0..7) | 0.874 | n/a (never swapped) | 22.7 (M+16..) | 0.829 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 20.9 | 26.3 | 0.586 | 35.6 | sink 1,645 MB, meta 2 MB, inflight 0 MB |
| xfer_sink+meta | 8.8 | 23.6 | 0.367 | 32.5 | sink 1,645 MB, meta 2 MB |
| xfer_meta+inflight | 19.2 | 19.5 | 0.574 | 22.2 | meta 2 MB, inflight 0 MB |
