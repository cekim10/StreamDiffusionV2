# State ablation at migration chunk M=30, 40 chunks after, k=4

Generated 2026-10-06 19:22:28 PDT; GPU NVIDIA L40S; commit f529cae23a7a4d7a9c4f591b18381f1b588d6a35; video examples/bird.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.6643554747104645**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.673 | 0.655 | 0 | -27 |
| drop_inflight | 0.6 | 0.0 | - | 13.2 | 14.6 | 23.5 | 24.1 | 0.666 | 0.917 | 0.648 | 0.651 | 0 | -27 |
| drop_kv_recent | 3,290.6 | 0.0 | - | 25.0 | 20.9 | 22.8 | 32.2 | 0.847 | 0.982 | 0.672 | 0.654 | 0 | -27 |
| drop_vae_all | 2,870.5 | 0.0 | - | 14.7 | 21.7 | 26.5 | 29.9 | 0.871 | 0.970 | 0.652 | 0.655 | 0 | -27 |
| xfer_sink+meta+inflight | 12,830.1 | 0.0 | - | 14.9 | 17.6 | 21.4 | 23.8 | 0.791 | 0.910 | 0.654 | 0.652 | 0 | -27 |
| xfer_sink+meta | 12,830.7 | 0.0 | - | 12.5 | 13.9 | 21.0 | 22.8 | 0.580 | 0.894 | 0.585 | 0.652 | 0 | -27 |
| xfer_meta+inflight | 16,120.7 | 0.0 | - | 14.3 | 15.8 | 16.0 | 15.4 | 0.744 | 0.702 | 0.667 | 0.703 | 0 | -27 |
| ph_zero_8 | 3,290.6 | 0.0 | - | 29.5 | 22.4 | 17.4 | 31.7 | 0.864 | 0.965 | 0.685 | 0.655 | 0 | -27 |
| ph_local_8 | 3,290.6 | 0.0 | - | 29.6 | 22.8 | 18.3 | 32.5 | 0.878 | 0.972 | 0.684 | 0.655 | 0 | -27 |
| ph_localrefresh | 3,290.6 | 0.0 | - | 29.8 | 23.1 | 16.8 | 15.5 | 0.879 | 0.706 | 0.684 | 0.700 | 0 | -27 |

Inventory at M (bytes): kv_sink_bytes 3,291 MB, kv_recent_bytes 3,291 MB, kv_all_bytes 6,581 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 1 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 16 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [6, 23, 7], 'recent_slot_pos': [30, 31, 29]}; adaptive sink refresh fired at baseline calls [4, 5, 21, 48] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_zero_8 | 8 | 19.3 | 0.801 | 14 | 31.7 | 0.965 |
| ph_local_8 | 8 | 20.1 | 0.835 | 13 | 32.5 | 0.972 |
| ph_localrefresh | - | 20.2 (M+0..7) | 0.831 | n/a (never swapped) | 15.5 (M+16..) | 0.706 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 14.9 | 18.0 | 0.791 | 23.8 | sink 3,291 MB, meta 2 MB, inflight 1 MB |
| xfer_sink+meta | 12.5 | 16.2 | 0.580 | 22.8 | sink 3,291 MB, meta 2 MB |
| xfer_meta+inflight | 14.3 | 15.7 | 0.744 | 15.4 | meta 2 MB, inflight 1 MB |
