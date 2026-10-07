# State ablation at migration chunk M=30, 40 chunks after, k=1

Generated 2026-10-06 18:59:59 PDT; GPU NVIDIA L40S; commit f529cae23a7a4d7a9c4f591b18381f1b588d6a35; video examples/bird.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.7719959169626236**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.775 | 0.772 | 0 | -30 |
| drop_kv_recent | 822.7 | 0.0 | - | 22.8 | 24.7 | 41.4 | 48.0 | 0.906 | 0.998 | 0.767 | 0.772 | 0 | -30 |
| drop_vae_all | 2,870.5 | 0.0 | - | 17.2 | 25.0 | 41.3 | 46.4 | 0.915 | 0.998 | 0.748 | 0.772 | 0 | -30 |
| xfer_sink+meta+inflight | 5,426.2 | 0.0 | - | 17.7 | 22.5 | 39.8 | 46.5 | 0.882 | 0.998 | 0.747 | 0.772 | 0 | -30 |
| xfer_sink+meta | 5,426.2 | 0.0 | - | 17.7 | 22.5 | 39.8 | 46.5 | 0.882 | 0.998 | 0.747 | 0.772 | 0 | -30 |
| xfer_meta+inflight | 6,248.9 | 0.0 | - | 15.5 | 19.6 | 22.2 | 22.2 | 0.766 | 0.868 | 0.706 | 0.767 | 0 | -30 |
| ph_zero_8 | 822.7 | 0.0 | - | 25.0 | 23.4 | 27.1 | 47.2 | 0.878 | 0.998 | 0.768 | 0.772 | 0 | -30 |
| ph_local_8 | 822.7 | 0.0 | - | 25.9 | 25.5 | 30.9 | 47.3 | 0.918 | 0.998 | 0.776 | 0.772 | 0 | -30 |
| ph_localrefresh | 822.7 | 0.0 | - | 25.4 | 24.9 | 23.2 | 22.3 | 0.910 | 0.875 | 0.775 | 0.770 | 0 | -30 |

Inventory at M (bytes): kv_sink_bytes 823 MB, kv_recent_bytes 823 MB, kv_all_bytes 1,645 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 4 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 48] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_zero_8 | 8 | 23.0 | 0.868 | 4 | 47.2 | 0.998 |
| ph_local_8 | 8 | 25.1 | 0.910 | 3 | 47.3 | 0.998 |
| ph_localrefresh | - | 24.3 (M+0..7) | 0.896 | n/a (never swapped) | 22.3 (M+16..) | 0.875 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 17.7 | 27.6 | 0.882 | 46.5 | sink 823 MB, meta 2 MB |
| xfer_sink+meta | 17.7 | 27.6 | 0.882 | 46.5 | sink 823 MB, meta 2 MB |
| xfer_meta+inflight | 15.5 | 20.7 | 0.766 | 22.2 | meta 2 MB |
