# State ablation at migration chunk M=30, 40 chunks after, k=1

Generated 2026-10-06 18:28:34 PDT; GPU NVIDIA L40S; commit f529cae23a7a4d7a9c4f591b18381f1b588d6a35; video examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.4576043102890253**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.447 | 0.460 | 0 | -30 |
| drop_kv_recent | 822.7 | 0.0 | - | 21.4 | 24.6 | 44.6 | 50.2 | 0.877 | 0.998 | 0.445 | 0.460 | 0 | -30 |
| drop_vae_all | 2,870.5 | 0.0 | - | 18.4 | 24.2 | 43.3 | 49.0 | 0.839 | 0.998 | 0.431 | 0.460 | 0 | -30 |
| xfer_sink+meta+inflight | 5,426.2 | 0.0 | - | 16.8 | 21.9 | 41.8 | 49.0 | 0.814 | 0.998 | 0.426 | 0.460 | 0 | -30 |
| xfer_sink+meta | 5,426.2 | 0.0 | - | 16.8 | 21.9 | 41.8 | 49.0 | 0.814 | 0.998 | 0.426 | 0.460 | 0 | -30 |
| xfer_meta+inflight | 6,248.9 | 0.0 | - | 14.7 | 17.6 | 20.8 | 21.3 | 0.671 | 0.831 | 0.409 | 0.455 | 0 | -30 |
| ph_zero_8 | 822.7 | 0.0 | - | 27.5 | 23.4 | 29.1 | 46.6 | 0.870 | 0.997 | 0.444 | 0.460 | 0 | -30 |
| ph_local_8 | 822.7 | 0.0 | - | 28.4 | 25.7 | 33.8 | 46.7 | 0.888 | 0.997 | 0.439 | 0.460 | 0 | -30 |
| ph_localrefresh | 822.7 | 0.0 | - | 28.3 | 25.8 | 23.8 | 23.6 | 0.893 | 0.869 | 0.441 | 0.469 | 0 | -30 |

Inventory at M (bytes): kv_sink_bytes 823 MB, kv_recent_bytes 823 MB, kv_all_bytes 1,645 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 4 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 48] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_zero_8 | 8 | 21.7 | 0.847 | 3 | 46.6 | 0.997 |
| ph_local_8 | 8 | 25.3 | 0.885 | 1 | 46.7 | 0.997 |
| ph_localrefresh | - | 25.2 (M+0..7) | 0.889 | n/a (never swapped) | 23.6 (M+16..) | 0.869 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 16.8 | 28.0 | 0.814 | 49.0 | sink 823 MB, meta 2 MB |
| xfer_sink+meta | 16.8 | 28.0 | 0.814 | 49.0 | sink 823 MB, meta 2 MB |
| xfer_meta+inflight | 14.7 | 18.6 | 0.671 | 21.3 | meta 2 MB |
