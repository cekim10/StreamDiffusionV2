# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 18:38:59 PDT; GPU NVIDIA L40S; commit f529cae23a7a4d7a9c4f591b18381f1b588d6a35; video examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.4161317920312285**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.406 | 0.418 | 0 | -29 |
| drop_inflight | 0.2 | 0.0 | - | 10.4 | 21.5 | 36.9 | 36.4 | 0.699 | 0.975 | 0.357 | 0.417 | 0 | -29 |
| drop_kv_recent | 1,645.3 | 0.0 | - | 25.7 | 23.6 | 39.7 | 47.7 | 0.833 | 0.997 | 0.409 | 0.418 | 0 | -29 |
| drop_vae_all | 2,870.5 | 0.0 | - | 19.6 | 23.2 | 39.7 | 46.5 | 0.793 | 0.996 | 0.399 | 0.418 | 0 | -29 |
| xfer_sink+meta+inflight | 7,894.2 | 0.0 | - | 19.3 | 20.2 | 37.3 | 45.8 | 0.717 | 0.996 | 0.396 | 0.418 | 0 | -29 |
| xfer_sink+meta | 7,894.4 | 0.0 | - | 10.2 | 16.7 | 33.5 | 35.2 | 0.540 | 0.970 | 0.352 | 0.417 | 0 | -29 |
| xfer_meta+inflight | 9,539.5 | 0.0 | - | 16.5 | 16.1 | 18.0 | 18.8 | 0.571 | 0.748 | 0.391 | 0.419 | 0 | -29 |
| ph_zero_8 | 1,645.3 | 0.0 | - | 28.0 | 23.0 | 23.5 | 43.0 | 0.800 | 0.993 | 0.399 | 0.418 | 0 | -29 |
| ph_local_8 | 1,645.3 | 0.0 | - | 28.9 | 24.1 | 28.4 | 43.4 | 0.822 | 0.993 | 0.385 | 0.418 | 0 | -29 |
| ph_localrefresh | 1,645.3 | 0.0 | - | 28.6 | 24.4 | 20.5 | 20.3 | 0.826 | 0.777 | 0.388 | 0.424 | 0 | -29 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 48] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_zero_8 | 8 | 20.1 | 0.757 | 5 | 43.0 | 0.993 |
| ph_local_8 | 8 | 22.8 | 0.802 | 3 | 43.4 | 0.993 |
| ph_localrefresh | - | 22.6 (M+0..7) | 0.806 | n/a (never swapped) | 20.3 (M+16..) | 0.777 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 19.3 | 24.4 | 0.717 | 45.8 | sink 1,645 MB, meta 2 MB, inflight 0 MB |
| xfer_sink+meta | 10.2 | 22.5 | 0.540 | 35.2 | sink 1,645 MB, meta 2 MB |
| xfer_meta+inflight | 16.5 | 16.7 | 0.571 | 18.8 | meta 2 MB, inflight 0 MB |
