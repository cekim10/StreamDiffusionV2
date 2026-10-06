# State ablation at migration chunk M=30, 40 chunks after, k=2

Generated 2026-10-06 13:30:39 PDT; GPU NVIDIA L40S; commit b8278ae5f280afc1706fe140727c04d6cc0a135f; video /home/ckim151/StreamDiffusionV2/examples/original.mp4; seed 0. Scores are per-frame vs the uninterrupted baseline with identical per-chunk seeds.

Determinism floor (`repeat` mean PSNR over M..M+39): **99.00 dB** (99 = bit-exact). Valid-but-different reference (`seed_shift`, same state, different noise): **nan dB**; an ablation at or above this level diverged no more than an equally valid stream would. Recovery = first call whose mean PSNR >= floor - 1 dB.

Absolute reference: baseline SSIM vs INPUT video over M.. = **0.4161317920312285**; the `SSIM-in` columns are the same metric for each config (quality proxy that does not depend on which valid stream the baseline is).

Drift onset: first call where `repeat` falls below 60 dB vs baseline = never (bit-exact).

| config | bytes withheld (MB) | seed (MB) | replay ms | PSNR M+0 | PSNR M+0..3 | PSNR M+4..15 | PSNR M+16.. | SSIM M+0..3 | SSIM M+16.. | SSIM-in M+0..3 | SSIM-in M+16.. | missing frames | recovery call |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repeat | 0.0 | 0.0 | - | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.406 | 0.418 | 0 | -29 |
| cold_restart | 9,542.0 | 0.0 | - | nan | 17.3 | 21.3 | 21.5 | 0.612 | 0.800 | 0.412 | 0.421 | 4 | -29 |
| replay_full | 9,542.0 | 142.8 | 17192 | 99.0 | 99.0 | 99.0 | 99.0 | 1.000 | 1.000 | 0.406 | 0.418 | 0 | -29 |
| replay_0_sink0 | 9,542.0 | 10.3 | 1060 | 14.7 | 18.8 | 25.7 | 26.9 | 0.719 | 0.902 | 0.391 | 0.417 | 0 | -29 |
| replay_3_sink0 | 9,542.0 | 24.0 | 2724 | 22.3 | 24.4 | 27.4 | 26.7 | 0.825 | 0.898 | 0.396 | 0.418 | 0 | -29 |
| replay_3_sinkhist | 9,542.0 | 42.3 | 4952 | 25.7 | 26.2 | 28.2 | 28.0 | 0.868 | 0.908 | 0.405 | 0.419 | 0 | -29 |
| replay_6_sinkhist | 9,542.0 | 56.0 | 6617 | 28.0 | 28.2 | 29.2 | 28.6 | 0.914 | 0.918 | 0.408 | 0.418 | 0 | -29 |

Inventory at M (bytes): kv_sink_bytes 1,645 MB, kv_recent_bytes 1,645 MB, kv_all_bytes 3,291 MB, vae_enc_bytes 1,069 MB, vae_dec_bytes 1,801 MB, inflight_bytes 0 MB, crossattn_bytes 90 MB, prompt_embeds_bytes 8 MB

Delay restores: 

Ring-buffer slot positions at M (layer 0): {'sink_slot_pos': [0, 1, 6], 'recent_slot_pos': [31, 29, 30]}; adaptive sink refresh fired at baseline calls [4, 48] (sinkhist configs replay through the last one before M).

## Transfer vs seed+replay (analytic; full state 9,542 MB, RTT 10 ms, no decompression/serialization cost)

| config | seed MB | replay ms | T_move @0.1 Gbps | T_move @1 Gbps | T_move @10 Gbps | T_move @100 Gbps | T_recon @0.1 Gbps | T_recon @1 Gbps | T_recon @10 Gbps | T_recon @100 Gbps |
|---|---|---|---|---|---|---|---|---|---|---|
| replay_full | 142.8 | 17192 | 800,449 | 80,054 | 8,014 | 810 | 29,183 | 18,400 | 17,322 | 17,214 |
| replay_0_sink0 | 10.3 | 1060 | 800,449 | 80,054 | 8,014 | 810 | 1,933 | 1,156 | 1,079 | 1,071 |
| replay_3_sink0 | 24.0 | 2724 | 800,449 | 80,054 | 8,014 | 810 | 4,746 | 2,935 | 2,754 | 2,736 |
| replay_3_sinkhist | 42.3 | 4952 | 800,449 | 80,054 | 8,014 | 810 | 8,508 | 5,317 | 4,997 | 4,965 |
| replay_6_sinkhist | 56.0 | 6617 | 800,449 | 80,054 | 8,014 | 810 | 11,324 | 7,097 | 6,674 | 6,632 |

Continuity of each replay config is in the main table (compare with `repeat`, the full-state-transfer equivalent).

Gates (state_map.md section 4) are applied by the reader, not by this script; the numbers above are the record.

