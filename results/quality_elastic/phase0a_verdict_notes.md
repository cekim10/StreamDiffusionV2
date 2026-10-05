# Phase 0A verdict notes (interpretation of phase0a_summary.md; numbers are traceable to phase0a_raw.csv / phase0a_static_k*.json)

Run: commit e0c9d34 harness, NVIDIA L40S 46 GB, torch 2.6.0+cu124, flash_attn 2.7.4.post1, 1.3B, 480x832, official v2v example, 10 warm-up + 100 measured chunks per k. Results commit 8bd1094.

## Verdict: KILL (frozen gate, section 6 of phase0a_code_audit.md)

| gate clause | measured | outcome |
|---|---|---|
| R_M >= 2 | 2.06 (9,629 MB / 4,670 MB) | passes, barely |
| abs(dM) >= 256 MB | 4,959 MB | passes |
| HBM binds before compute for some k >= 2 (S_mem(k) <= S_compute(k)) | S_mem = {4,3,2,2}, S_compute = {0,0,0,0} at 16 FPS | **fails for every k** |

A single 1.3B session cannot reach 16 FPS on this GPU at any k (8.5 FPS at k=1, 6.2 FPS at k=4), so compute saturates (SM util 96-98%) long before HBM. The k-dependent HBM delta is real but cannot change admission here.

## How far from HBM binding

For HBM to bind, S_mem(k) sessions must fit in one 250 ms chunk budget (4 frames at 16 FPS):

| k | S_mem | required per-session chunk time | measured | shortfall |
|---|---|---|---|---|
| 1 | 4 | 62.5 ms | 468.7 ms | 7.5x |
| 2 | 3 | 83.3 ms | 522.7 ms | 6.3x |
| 3 | 2 | 125.0 ms | 574.7 ms | 4.6x |
| 4 | 2 | 125.0 ms | 641.8 ms | 5.1x |

The chunk time at k=1 is 469 ms of which VAE encode + decode is 392 ms and DiT is 75 ms. DiT grows ~52-66 ms per extra Stream-Batch row (75 -> 127 -> 180 -> 246 ms), i.e. roughly linear: on this GPU the batch rows are not amortized against weight reads.

## Unexpected findings (reported regardless of verdict)

1. **Per-session persistent state is dominated by the causal VAE feature cache, not by KV.** The VAE encoder/decoder `feat_cache` holds 2,870 MB per session (k-independent) versus 1,645 MB of KV at k=1. Excluding the VAE cache, the KV-only ratio would be 3.84; the VAE cache dilutes R_M to 2.06. The session inventory sums to 4,610 MB vs a measured delta of 4,670 MB, so the inventory is complete to ~1%.
2. **Transient per-chunk memory is 2,210 MB and k-independent**, consistent with VAE decode at 480x832 dominating the peak.
3. **repeat() vs expand() confirmed physically**: KV physical == logical and scales 1,645 -> 6,581 MB; cross-attn stays 90 MB physical with stride(0) = 0 for k >= 2.
4. The fixed footprint is 13,789 MB allocated (16,154 MB device-level), of which the umt5-xxl text encoder is 10,835 MB and is only used at session start.

## What this does and does not say

- It kills the admission-control reading of H1 on L40S with the official (non-TAEHV) VAE for the 1.3B model, under the gate as frozen.
- It does not measure H100 or the TAEHV (`--use_taehv`) path. From the numbers above, flipping the admission clause would need a 5-7x reduction in per-session chunk time at the same memory; TAEHV removes most of the 392 ms VAE time and shrinks the VAE cache, and H100 is roughly 3-4x faster than L40S in bf16. Whether that configuration crosses over is a separate decision, not a rescue of this run.
- Compute-only quality elasticity (DiT time linear in k) is confirmed but is already covered by StreamDiffusionV2's own motion-adaptive step selection and SLO-adaptive batch/no-batch switch, as the task brief anticipated.
