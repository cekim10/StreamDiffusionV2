# State ablation at migration chunk M=30, 80 chunks after, k=2

Generated 2026-10-20 17:45:19 PDT; GPU NVIDIA L40S; commit 914d25c9c7b590be11b929c27be0df9d6164c90e; video examples/original.mp4; seed 2. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+79): **nan dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.4136177826672792**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = n/a.

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| drop_inflight | 0.2 | 0.0 | - | 9.9 | 21.0 | 36.4 | 35.9 | 0.689 | 0.974 | 0.357 | 0.414 | 0 | None |
| drop_kv_recent | 1,645.3 | 0.0 | - | 25.2 | 24.0 | 39.1 | 47.3 | 0.834 | 0.997 | 0.407 | 0.414 | 0 | None |
| drop_vae_all | 2,870.5 | 0.0 | - | 19.0 | 23.1 | 38.9 | 46.4 | 0.782 | 0.996 | 0.401 | 0.414 | 0 | None |
| ph_localrefresh | 1,645.3 | 0.0 | - | 27.9 | 23.3 | 19.1 | 19.2 | 0.811 | 0.753 | 0.389 | 0.421 | 0 | None |
| xfer_sink+meta+inflight | 4,603.6 | 0.0 | - | 18.6 | 20.1 | 36.9 | 45.5 | 0.705 | 0.995 | 0.393 | 0.414 | 0 | None |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 48, 93] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_localrefresh | - | 21.7 (M+0..7) | 0.793 | n/a (never swapped) | 19.2 (M+16..) | 0.753 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 18.6 | 25.0 | 0.705 | 45.5 | sink 1,645 MB, meta 2 MB, inflight 0 MB |
