# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 11:59:45 PDT; GPU NVIDIA L40S; commit 28baa3610408551dc1498eab954e903758b4c978; video /home/ckim151/StreamDiffusionV2/examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.4161317920312285**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.406 | 0.418 | 0 | -29 |
| replay_0_sink0 | 9,542.0 | 10.3 | 1062 | 15.0 | 19.2 | 25.6 | 26.9 | 0.724 | 0.902 | 0.389 | 0.418 | 0 | -29 |
| replay_1_sink0 | 9,542.0 | 14.9 | 1607 | 17.7 | 21.3 | 25.9 | 27.2 | 0.764 | 0.904 | 0.390 | 0.418 | 0 | -29 |
| replay_3_sink0 | 9,542.0 | 24.0 | 2741 | 22.9 | 24.7 | 27.3 | 26.7 | 0.828 | 0.898 | 0.397 | 0.419 | 0 | -29 |
| replay_6_sink0 | 9,542.0 | 37.7 | 4393 | 26.6 | 26.3 | 27.1 | 27.0 | 0.870 | 0.893 | 0.406 | 0.421 | 0 | -29 |
| replay_full | 9,542.0 | 138.3 | 16657 | 31.7 | 31.3 | 30.7 | 30.6 | 0.946 | 0.946 | 0.408 | 0.418 | 0 | -29 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]} (sink slots at 0..2 means no adaptive sink refresh fired before M).

## Transfer vs seed+replay (analytic; full state 9,542 MB, RTT 10 ms, no decompression/serialization cost)

| config | seed MB | replay ms | T_move @0.1 Gbps | T_move @1 Gbps | T_move @10 Gbps | T_move @100 Gbps | T_recon @0.1 Gbps | T_recon @1 Gbps | T_recon @10 Gbps | T_recon @100 Gbps |
|---|---|---|---|---|---|---|---|---|---|---|
| replay_0_sink0 | 10.3 | 1062 | 800,449 | 80,054 | 8,014 | 810 | 1,934 | 1,158 | 1,080 | 1,073 |
| replay_1_sink0 | 14.9 | 1607 | 800,449 | 80,054 | 8,014 | 810 | 2,863 | 1,742 | 1,630 | 1,618 |
| replay_3_sink0 | 24.0 | 2741 | 800,449 | 80,054 | 8,014 | 810 | 4,764 | 2,952 | 2,771 | 2,753 |
| replay_6_sink0 | 37.7 | 4393 | 800,449 | 80,054 | 8,014 | 810 | 7,565 | 4,719 | 4,434 | 4,406 |
| replay_full | 138.3 | 16657 | 800,449 | 80,054 | 8,014 | 810 | 28,265 | 17,827 | 16,783 | 16,679 |

Continuity of each replay config is in the main table (compare with `repeat`, the full-state-transfer equivalent).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.

