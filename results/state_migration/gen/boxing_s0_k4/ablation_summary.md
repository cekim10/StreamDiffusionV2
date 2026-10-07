# State ablation at migration chunk M=30, 40 chunks after, k=4

Generated 2026-10-06 19:53:54 PDT; GPU NVIDIA L40S; commit f529cae23a7a4d7a9c4f591b18381f1b588d6a35; video examples/boxing.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.23837888035923244**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.214 | 0.243 | 0 | -27 |
| drop_inflight | 0.6 | 0.0 | - | 9.7 | 12.7 | 32.5 | 35.2 | 0.157 | 0.977 | 0.345 | 0.249 | 0 | -27 |
| drop_kv_recent | 3,290.6 | 0.0 | - | 31.2 | 25.7 | 31.6 | 46.0 | 0.914 | 0.997 | 0.224 | 0.243 | 0 | -27 |
| drop_vae_all | 2,870.5 | 0.0 | - | 20.7 | 28.1 | 34.8 | 44.5 | 0.762 | 0.997 | 0.320 | 0.243 | 0 | -27 |
| xfer_sink+meta+inflight | 12,830.1 | 0.0 | - | 20.8 | 22.5 | 30.7 | 42.5 | 0.707 | 0.996 | 0.330 | 0.243 | 0 | -27 |
| xfer_sink+meta | 12,830.7 | 0.0 | - | 9.3 | 10.5 | 27.2 | 32.7 | 0.100 | 0.965 | 0.300 | 0.256 | 0 | -27 |
| xfer_meta+inflight | 16,120.7 | 0.0 | - | 20.5 | 19.7 | 19.0 | 19.7 | 0.652 | 0.751 | 0.305 | 0.210 | 0 | -27 |
| ph_zero_8 | 3,290.6 | 0.0 | - | 38.4 | 28.3 | 22.3 | 38.3 | 0.915 | 0.989 | 0.199 | 0.236 | 0 | -27 |
| ph_local_8 | 3,290.6 | 0.0 | - | 38.0 | 29.0 | 25.5 | 39.1 | 0.929 | 0.991 | 0.193 | 0.236 | 0 | -27 |
| ph_localrefresh | 3,290.6 | 0.0 | - | 38.3 | 28.9 | 20.8 | 20.3 | 0.930 | 0.762 | 0.197 | 0.225 | 0 | -27 |

Inventory at M (bytes): kv_sink_bytes 3,291 MB, kv_recent_bytes 3,291 MB, kv_all_bytes 6,581 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 1 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 16 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [22, 16, 6], 'recent_slot_pos': [30, 31, 29]}; adaptive sink refresh fired at baseline calls [4, 14, 20, 48] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_zero_8 | 8 | 24.0 | 0.845 | 9 | 38.3 | 0.989 |
| ph_local_8 | 8 | 25.7 | 0.881 | 5 | 39.1 | 0.991 |
| ph_localrefresh | - | 25.4 (M+0..7) | 0.876 | n/a (never swapped) | 20.3 (M+16..) | 0.762 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 20.8 | 23.1 | 0.707 | 42.5 | sink 3,291 MB, meta 2 MB, inflight 1 MB |
| xfer_sink+meta | 9.3 | 16.1 | 0.100 | 32.7 | sink 3,291 MB, meta 2 MB |
| xfer_meta+inflight | 20.5 | 18.8 | 0.652 | 19.7 | meta 2 MB, inflight 1 MB |
