# State ablation at migration chunk M=30, 80 chunks after, k=2

Generated 2026-10-09 20:55:52 PDT; GPU NVIDIA L40S; commit 9ddc74ed15a5b347b4f325404689b821ad3bc399; video examples/train.mp4; seed 1. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+79): **nan dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.49347469927743076**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = n/a.

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ph_localrefresh | 1,645.3 | 0.0 | - | 27.8 | 21.9 | 17.3 | 17.1 | 0.802 | 0.668 | 0.491 | 0.519 | 0 | None |
| xfer_sink+meta+inflight | 4,603.6 | 0.0 | - | 16.6 | 19.5 | 31.2 | 34.4 | 0.720 | 0.977 | 0.442 | 0.491 | 0 | None |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [22, 24, 6], 'recent_slot_pos': [30, 31, 29]}; adaptive sink refresh fired at baseline calls [4, 20, 22, 48, 93] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_localrefresh | - | 19.8 (M+0..7) | 0.741 | n/a (never swapped) | 17.1 (M+16..) | 0.668 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 16.6 | 23.0 | 0.720 | 34.4 | sink 1,645 MB, meta 2 MB, inflight 0 MB |
