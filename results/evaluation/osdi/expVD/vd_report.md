# Experiment VD - report (2026-10-24)

Frozen plan `preregistration.md` (FROZEN 2026-10-23, `../expVD_freeze.md`). Aggregation `tools/eval/aggregate_vd.py` ->
`vd_results.md` / `.json`. 32 emulations (dog and butterfly x OT-1 and OT-L x 8 conditions) plus the two frozen-M1
controls from VC-1; all valid, 0 mask violations. Precheck `vd_precheck.json`. Nothing here changes M1, M2 or M3-v2.

## 1. Precheck (mechanism)

- Softmax mass on the zero-filled sink slots during the Sink-less window (dog, calls 34-37): median 1.7 %, maximum
  22 % (block 0); 19 of 30 blocks have a median >= 1 %. Dilution exists but is small outside the first block.
- The masked kernel (`flash_attn_with_kvcache` on the cache after the sink slots) equals SDPA with an explicit
  boolean mask to max |diff| 0.0625 on outputs of magnitude ~12 (0.7 %, bf16 rounding). The sink region was zero in
  every probed call.

## 2. Verdicts (frozen rules; effect sizes first)

| id | factor | main effect (dog OT-1 / OT-L; butterfly OT-1 / OT-L) | verdict |
|---|---|---|---|
| VD-H1 | masking the zero slots lowers Sink-less color drift and warp error | dE -0.12 / -0.19; **+0.07 / +0.01**. E diff -0.026 / -0.020; **+0.040 / +0.034** | **NOT SUPPORTED** (dog yes, butterfly no) |
| VD-H2 | keeping the VAE decoder cache lowers the reset spike by >= 2x | V1 ratio **0.41 / 0.27; 0.37 / 0.45** | **SUPPORTED** (4 / 4) |
| VD-H3 | keeping the recent KV lowers the reset spike and the first-4-call warp error | V1 ratio 0.78 / 0.77; 0.78 / 0.95. first-4 E diff -0.70 / -0.22; -0.42 / -0.21 | **SUPPORTED** (4 / 4) |
| VD-H4 | on butterfly, masked + decoder + recent still ends within 2 dB of frozen M1 | terminal PSNR 31.0 vs 31.3 dB (OT-1), 28.6 vs 28.6 dB (OT-L); no condition reaches 35 dB on OT-L | **SUPPORTED** |
| VD-H5 | D x R interaction on the reset spike | V1 (mean over S): dog OT-1 8.0 -> 7.4 (R) -> 4.2 (D) -> **2.1 (D + R)**; dog OT-L 9.2 -> 8.3 -> 3.3 -> **1.4**; butterfly OT-1 3.3 -> 2.6 -> 1.3 -> **0.9**; OT-L 1.9 -> 1.8 -> 0.8 -> **0.9** | descriptive: the decoder cache carries most of the effect; with both kept, the reset spike is below REF's own P99 (3.96 dog, 1.40 butterfly) in every case |

The encoder cache adds nothing over the decoder cache (V1 identical: 4.18 / 3.36 / 1.31 / 0.85), and it does not
change the Sink-less window either.

## 3. Reading, and the next step fixed by the frozen mapping

- **The reset jump is a short-term-state problem.** The VAE decoder cache (which holds only the last 2 time steps of
  every layer's input, `vae.py` CACHE_T = 2) and the recent KV together bring the jump into REF's normal
  frame-to-frame range. Per the frozen mapping, the next M1 question is the cheapest reconstruction of that state at
  the destination (decoder cache from the last 1-2 latent frames, ~200-400 KB; recent KV from a one-chunk replay),
  not Sink transfer.
- **The Sink-less content change is not touched by any of these.** DINO / color / prompt deviations during the window
  are the same with every combination of masking, decoder cache and recent KV, and (VD-H4) on butterfly the
  post-bind trajectory stays where frozen M1 leaves it. Per the mapping, the residual is the Sink's own absence, so
  the "minimum temporal state" question (an approximate or destination-local Sink) is the right next design
  question. It was not designed before this result.
- **Masking is not a candidate M1 variant.** Its effect is small and input-dependent.

## 4. Cost note (measured in VC / VD, not in a migration)

"Kept" means the emulator handed the destination the state; nothing was transferred. The decoder cache is 1.8 GB and
the recent KV 1.6 GB, so neither can be carried on the fast path; VD-2 tests their reconstruction.
