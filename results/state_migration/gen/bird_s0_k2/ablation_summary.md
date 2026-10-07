# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 19:10:28 PDT; GPU NVIDIA L40S; commit f529cae23a7a4d7a9c4f591b18381f1b588d6a35; video examples/bird.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.7164226230233908**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.726 | 0.713 | 0 | -29 |
| drop_inflight | 0.2 | 0.0 | - | 14.6 | 21.5 | 32.4 | 32.3 | 0.838 | 0.978 | 0.714 | 0.712 | 0 | -29 |
| drop_kv_recent | 1,645.3 | 0.0 | - | 21.0 | 21.5 | 32.4 | 43.7 | 0.846 | 0.997 | 0.715 | 0.713 | 0 | -29 |
| drop_vae_all | 2,870.5 | 0.0 | - | 16.0 | 21.5 | 33.8 | 38.7 | 0.877 | 0.993 | 0.702 | 0.713 | 0 | -29 |
| xfer_sink+meta+inflight | 7,894.2 | 0.0 | - | 15.5 | 19.1 | 26.5 | 30.4 | 0.817 | 0.969 | 0.691 | 0.712 | 0 | -29 |
| xfer_sink+meta | 7,894.4 | 0.0 | - | 13.7 | 18.6 | 24.8 | 27.3 | 0.742 | 0.944 | 0.660 | 0.710 | 0 | -29 |
| xfer_meta+inflight | 9,539.5 | 0.0 | - | 14.6 | 16.1 | 18.6 | 18.1 | 0.714 | 0.792 | 0.686 | 0.735 | 0 | -29 |
| ph_zero_8 | 1,645.3 | 0.0 | - | 24.4 | 20.5 | 21.6 | 33.8 | 0.835 | 0.983 | 0.735 | 0.712 | 0 | -29 |
| ph_local_8 | 1,645.3 | 0.0 | - | 25.2 | 21.4 | 23.2 | 33.9 | 0.866 | 0.984 | 0.737 | 0.712 | 0 | -29 |
| ph_localrefresh | 1,645.3 | 0.0 | - | 25.2 | 21.6 | 19.1 | 18.3 | 0.862 | 0.797 | 0.737 | 0.738 | 0 | -29 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [22, 1, 6], 'recent_slot_pos': [29, 30, 31]}; adaptive sink refresh fired at baseline calls [4, 20, 48] (sinkhist configs replay through the last one before M).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.


## Placeholder: gap quality vs rejoin after the true sink arrives (tau = 30 dB)

| config | arrival D | PSNR gap M..M+D-1 | SSIM gap | rejoin (calls after arrival to >= 30 dB) | PSNR M+D+8.. | SSIM M+D+8.. |
|---|---|---|---|---|---|---|
| ph_zero_8 | 8 | 19.6 | 0.810 | 9 | 33.8 | 0.983 |
| ph_local_8 | 8 | 20.8 | 0.852 | 8 | 33.9 | 0.984 |
| ph_localrefresh | - | 20.8 (M+0..7) | 0.840 | n/a (never swapped) | 18.3 (M+16..) | 0.797 |

## Natural refill vs replay: early continuity (M+0..7)

| config | PSNR M+0 | PSNR M+0..7 | SSIM M+0..3 | PSNR M+16.. | moved / seed |
|---|---|---|---|---|---|
| xfer_sink+meta+inflight | 15.5 | 22.0 | 0.817 | 30.4 | sink 1,645 MB, meta 2 MB, inflight 0 MB |
| xfer_sink+meta | 13.7 | 21.3 | 0.742 | 27.3 | sink 1,645 MB, meta 2 MB |
| xfer_meta+inflight | 14.6 | 17.4 | 0.714 | 18.1 | meta 2 MB, inflight 0 MB |
