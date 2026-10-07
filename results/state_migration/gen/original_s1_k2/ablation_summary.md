# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 20:04:20 PDT; GPU NVIDIA L40S; commit f529cae23a7a4d7a9c4f591b18381f1b588d6a35; video examples/original.mp4; seed 1. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.41589774936437607**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.406 | 0.417 | 0 | -29 |
| drop_inflight | 0.2 | 0.0 | - | 10.4 | 21.7 | 36.9 | 36.2 | 0.704 | 0.973 | 0.360 | 0.417 | 0 | -29 |
| drop_kv_recent | 1,645.3 | 0.0 | - | 25.6 | 22.8 | 39.7 | 47.8 | 0.825 | 0.997 | 0.410 | 0.417 | 0 | -29 |
| drop_vae_all | 2,870.5 | 0.0 | - | 19.7 | 23.6 | 40.1 | 46.4 | 0.797 | 0.996 | 0.399 | 0.417 | 0 | -29 |
| xfer_sink+meta+inflight | 7,894.2 | 0.0 | - | 19.2 | 20.4 | 37.7 | 45.3 | 0.720 | 0.995 | 0.397 | 0.417 | 0 | -29 |
| xfer_sink+meta | 7,894.4 | 0.0 | - | 10.1 | 17.1 | 34.0 | 34.1 | 0.532 | 0.962 | 0.350 | 0.418 | 0 | -29 |
| xfer_meta+inflight | 9,539.5 | 0.0 | - | 16.5 | 16.4 | 17.2 | 18.8 | 0.566 | 0.743 | 0.392 | 0.417 | 0 | -29 |
| ph_zero_8 | 1,645.3 | 0.0 | - | 28.3 | 23.3 | 23.0 | 43.4 | 0.799 | 0.993 | 0.400 | 0.417 | 0 | -29 |
| ph_local_8 | 1,645.3 | 0.0 | - | 29.5 | 24.5 | 27.9 | 43.5 | 0.833 | 0.993 | 0.386 | 0.417 | 0 | -29 |
| ph_localrefresh | 1,645.3 | 0.0 | - | 28.9 | 24.6 | 20.3 | 20.5 | 0.833 | 0.772 | 0.388 | 0.424 | 0 | -29 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 48] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_zero_8 | 8 | 20.4 | 0.754 | 6 | 43.4 | 0.993 |
| ph_local_8 | 8 | 23.0 | 0.807 | 3 | 43.5 | 0.993 |
| ph_localrefresh | - | 22.8 (M+0..7) | 0.806 | n/a (never swapped) | 20.5 (M+16..) | 0.772 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 19.2 | 25.1 | 0.720 | 45.3 | sink 1,645 MB, meta 2 MB, inflight 0 MB |
| xfer_sink+meta | 10.1 | 22.9 | 0.532 | 34.1 | sink 1,645 MB, meta 2 MB |
| xfer_meta+inflight | 16.5 | 16.6 | 0.566 | 18.8 | meta 2 MB, inflight 0 MB |
