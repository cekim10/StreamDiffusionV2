# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 11:44:42 PDT; GPU NVIDIA L40S; commit 75d5b829938b646d0af67d7d0ebe9a52c1132e0d; video /home/ckim151/StreamDiffusionV2/examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **22.57 dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.4161317920312285**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.406 | 0.418 | 0 | -29 |
| seed_shift | 0.0 | 0.0 | - | 23.7 | 22.6 | 23.0 | 22.3 | 0.749 | 0.754 | 0.405 | 0.414 | 0 | None |
| cold_restart | 9,542.0 | 0.0 | - | nan | 17.3 | 21.3 | 21.5 | 0.612 | 0.800 | 0.412 | 0.421 | 4 | -29 |
| replay_1 | 9,542.0 | 5.7 | 780 | nan | 18.2 | 21.4 | 21.4 | 0.680 | 0.801 | 0.398 | 0.415 | 4 | -29 |
| replay_3 | 9,542.0 | 14.9 | 1614 | 18.8 | 20.0 | 22.1 | 22.1 | 0.723 | 0.811 | 0.395 | 0.416 | 0 | -29 |
| replay_6 | 9,542.0 | 28.6 | 3300 | 22.2 | 22.9 | 24.0 | 23.6 | 0.778 | 0.821 | 0.397 | 0.421 | 0 | -29 |
| replay_0_sink0 | 9,542.0 | 5.7 | 780 | nan | 19.0 | 25.4 | 26.9 | 0.736 | 0.899 | 0.397 | 0.416 | 4 | -29 |
| replay_1_sink0 | 9,542.0 | 10.3 | 1059 | 17.3 | 20.4 | 25.7 | 26.9 | 0.757 | 0.902 | 0.396 | 0.417 | 0 | -29 |
| replay_3_sink0 | 9,542.0 | 19.4 | 2164 | 22.0 | 23.9 | 26.6 | 26.9 | 0.824 | 0.901 | 0.398 | 0.417 | 0 | -29 |
| replay_6_sink0 | 9,542.0 | 33.1 | 3843 | 25.8 | 26.2 | 27.1 | 26.7 | 0.860 | 0.891 | 0.403 | 0.420 | 0 | -29 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

## Transfer vs seed+replay (analytic; full state 9,542 MB, RTT 10 ms, no decompression/serialization cost)

| config | seed MB | replay ms | T_move @0.1 Gbps | T_move @1 Gbps | T_move @10 Gbps | T_move @100 Gbps | T_recon @0.1 Gbps | T_recon @1 Gbps | T_recon @10 Gbps | T_recon @100 Gbps |
|---|---|---|---|---|---|---|---|---|---|---|
| replay_1 | 5.7 | 780 | 800,449 | 80,054 | 8,014 | 810 | 1,269 | 838 | 794 | 790 |
| replay_3 | 14.9 | 1614 | 800,449 | 80,054 | 8,014 | 810 | 2,870 | 1,748 | 1,636 | 1,625 |
| replay_6 | 28.6 | 3300 | 800,449 | 80,054 | 8,014 | 810 | 5,707 | 3,550 | 3,334 | 3,313 |
| replay_0_sink0 | 5.7 | 780 | 800,449 | 80,054 | 8,014 | 810 | 1,270 | 838 | 795 | 791 |
| replay_1_sink0 | 10.3 | 1059 | 800,449 | 80,054 | 8,014 | 810 | 1,932 | 1,156 | 1,078 | 1,070 |
| replay_3_sink0 | 19.4 | 2164 | 800,449 | 80,054 | 8,014 | 810 | 3,804 | 2,337 | 2,191 | 2,176 |
| replay_6_sink0 | 33.1 | 3843 | 800,449 | 80,054 | 8,014 | 810 | 6,633 | 4,131 | 3,881 | 3,856 |

Continuity of each replay config is in the main table (compare with `repeat`, the full-state-transfer equivalent).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.

