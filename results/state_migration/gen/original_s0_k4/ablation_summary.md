# State ablation at migration chunk M=30, 40 chunks after, k=4

Generated 2026-10-06 18:50:58 PDT; GPU NVIDIA L40S; commit f529cae23a7a4d7a9c4f591b18381f1b588d6a35; video examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.3891494920477271**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.386 | 0.389 | 0 | -27 |
| drop_inflight | 0.6 | 0.0 | - | 9.9 | 12.8 | 28.8 | 32.4 | 0.420 | 0.940 | 0.284 | 0.389 | 0 | -27 |
| drop_kv_recent | 3,290.6 | 0.0 | - | 30.0 | 27.6 | 31.9 | 46.7 | 0.872 | 0.996 | 0.378 | 0.389 | 0 | -27 |
| drop_vae_all | 2,870.5 | 0.0 | - | 19.4 | 26.0 | 35.0 | 45.5 | 0.786 | 0.996 | 0.363 | 0.389 | 0 | -27 |
| xfer_sink+meta+inflight | 12,830.1 | 0.0 | - | 19.5 | 22.9 | 30.5 | 45.1 | 0.739 | 0.996 | 0.364 | 0.389 | 0 | -27 |
| xfer_sink+meta | 12,830.7 | 0.0 | - | 10.2 | 11.3 | 26.0 | 30.9 | 0.339 | 0.928 | 0.256 | 0.390 | 0 | -27 |
| xfer_meta+inflight | 16,120.7 | 0.0 | - | 18.4 | 18.9 | 15.8 | 16.8 | 0.616 | 0.658 | 0.368 | 0.392 | 0 | -27 |
| ph_zero_8 | 3,290.6 | 0.0 | - | 33.3 | 26.4 | 19.0 | 33.6 | 0.830 | 0.976 | 0.379 | 0.389 | 0 | -27 |
| ph_local_8 | 3,290.6 | 0.0 | - | 34.1 | 27.1 | 23.4 | 34.4 | 0.850 | 0.980 | 0.376 | 0.389 | 0 | -27 |
| ph_localrefresh | 3,290.6 | 0.0 | - | 33.5 | 27.0 | 18.4 | 17.9 | 0.849 | 0.697 | 0.378 | 0.393 | 0 | -27 |

Inventory at M (bytes): kv_sink_bytes 3,291 MB, kv_recent_bytes 3,291 MB, kv_all_bytes 6,581 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 1 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 16 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 32, 33, 48] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_zero_8 | 8 | 21.8 | 0.749 | 10 | 33.6 | 0.976 |
| ph_local_8 | 8 | 23.3 | 0.799 | 6 | 34.4 | 0.980 |
| ph_localrefresh | - | 23.0 (M+0..7) | 0.793 | n/a (never swapped) | 17.9 (M+16..) | 0.697 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 19.5 | 22.1 | 0.739 | 45.1 | sink 3,291 MB, meta 2 MB, inflight 1 MB |
| xfer_sink+meta | 10.2 | 15.5 | 0.339 | 30.9 | sink 3,291 MB, meta 2 MB |
| xfer_meta+inflight | 18.4 | 17.1 | 0.616 | 16.8 | meta 2 MB, inflight 1 MB |
