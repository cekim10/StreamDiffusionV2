# Experiment VC - report (2026-10-24)

Frozen plan `preregistration.md` (FROZEN 2026-10-23, `../expVC_freeze.md`). Aggregation `tools/eval/aggregate_vc.py` ->
`vc_results.md` / `.json`. Emulation on host D (G1 re-passed with the VD flag in the code: dog OT-L vs the real RD-X run,
|dPSNR| 0.0 over 174 calls; G3 passed on all 48 streams; `vc1_checks_*.md`). Four inputs, seed 0, conditions REF,
OT-1, OT-L, OT-R, WFS-1 / -L, COLD-1 / -L. train's OT-L is a counterfactual replay under dog's copied schedule.
Generation continuity, playback continuity and reference-trajectory recovery are reported apart and never merged.

## 1. Verdicts (frozen rules)

| id | statement | verdict | evidence |
|---|---|---|---|
| VC-H1 | post-bind motion consistency: E_O / E_R <= 1.10 and motion ratio in [0.90, 1.10] in the 20 calls after the bind and the last 10 calls, OT-1 / OT-L / OT-R | **supported on 3 of 4 inputs** (butterfly, train, audi); **not supported on dog** | the only failing cell is dog OT-L post-bind-20: E_O / E_R 1.114 [1.001, 1.171] (threshold 1.10). Every last-10 window on every input is 0.975-1.019; every motion ratio is within [0.98, 1.05] |
| VC-H2 | OTTER's reset jump <= a cold restart's at the same call | **NOT SUPPORTED** (6 of 8 pairs fail) | V1(OT) / V1(COLD) = 1.06, 1.29 (dog), 1.36, 1.14 (butterfly), 1.09 (train OT-1), 1.24 (audi OT-1); 0.79 (train OT-L), 0.52 (audi OT-L). Both OTTER's and COLD's jumps sit at the 98th-100th percentile of REF's own frame-to-frame variation (REF P99: 1.4-6.5) |
| VC-H3 | the Sink-less window is less consistent than REF | descriptive, **observed on every input** | table in section 2 |
| VC-H4 | playback trade-off | descriptive | section 4 |

## 2. Generation continuity by period (OTTER - REF at the same calls; DINO = content similarity, CLIP = prompt alignment, dE = global color drift to REF, E = warp-error ratio)

| input | period | DINO diff (REF band width) | CLIP diff | dE | E_O / E_R |
|---|---|---|---|---|---|
| dog | Sink-less (24-74 calls) | **-0.38 to -0.43** (0.03) | -0.035 | 1.4-2.2 | 1.8-2.3 |
| dog | after bind, last 10 | 0.000 | 0.000 | 0.01-0.02 | 1.00 |
| butterfly | Sink-less | **-0.15 to -0.19** (0.04-0.06) | -0.004 to -0.011 | 0.7-1.3 | 1.2-1.4 |
| butterfly | after bind, last 10 | -0.002 to +0.002 | 0.000 | 0.15-0.17 | 1.00-1.02 |
| train | Sink-less | **-0.24 to -0.28** (0.02-0.05) | -0.053 to -0.061 | 1.6-2.5 | 1.4-1.6 |
| train | after bind, last 10 | -0.002 to +0.003 | 0.000 | 0.11-0.26 | 0.98-0.99 |
| audi-snow-trail | Sink-less | **-0.14 to -0.17** (0.12-0.22) | -0.027 to -0.051 | 1.0-1.3 | 1.35-1.6 |
| audi-snow-trail | after bind, last 10 | -0.004 to -0.012 | 0.002 | 0.11-0.25 | 0.98-1.01 |

Reading (the paper may state this, with the metrics named and no perceptual claim):
- **During the Sink-less window the output leaves the pre-move content on every input** (Case A): content
  similarity falls by 4-15 times REF's own band width, prompt alignment and color drift with it, and temporal
  consistency is 1.2-2.3 times worse than REF's. The window lasts the Sink transfer: 24 calls (~14 s) at 1 Gbps, 74
  calls (~44 s) at 320 Mbps, 48 calls (~29 s) over three moves.
- **After the bind every input returns to REF's content, prompt alignment, color and motion consistency**,
  including butterfly and audi-snow-trail, whose PSNR to REF never reaches 35 dB (butterfly terminal 28.6-31.3 dB).
  On those inputs the post-bind stream is Case B: consistent with REF on every embedding, flow and color metric while
  not pixel-equal to it. No perceptual equivalence is claimed from these metrics.
- **The reset itself is a visible jump** on every input, as large as or larger than a cold restart's. VD attributes it
  to the VAE decoder cache and the recent KV (its report).

## 3. The Sink-exact hybrid for comparison (Wait-for-Sink, generation only)

Binding the exact Sink before generating removes the Sink-less window: WFS-1's post-bind-20 DINO difference is
-0.012 to -0.018 on every input, with dE 0.25-0.69. Its first 20 calls are still less consistent than REF (E_O / E_R
1.09-1.52), because the recent KV and VAE caches are rebuilt. Its cost is in playback.

## 4. Playback continuity (last-frame-hold model, rate matched to the measured delivery cadence)

| condition | stalls | longest freeze | resume jump (V1) |
|---|---|---|---|
| OTTER (OT-1 / OT-L / OT-R) | **0** on every input (lateness <= 0.16 s; OT-R <= 1.0 s cumulative) | <= 0.09 s | - |
| COLD-1 / -L | 1 | 0.58-0.59 s | 1.8-9.0 |
| WFS-1 | 1 | 14.5-15.0 s | 3.3-7.6 |
| WFS-L | 1 | 43.9-44.1 s | 2.4-8.2 |

OTTER never freezes; its cost is the content change of section 2. Wait-for-Sink freezes for the whole Sink transfer
and still jumps when it resumes. A cold restart freezes 0.6 s and jumps.

## 5. Limitations

Seed 0, four inputs, one model; the realized schedules of frozen runs (OT-L for train copied from dog); embedding and
flow metrics only, no human evaluation (VC-2 deferred, IRB first); the playback model is a simple player, not a
measurement of a real client; no isolation record for the dog unit (the copy-back crash), the other three units show
no NIC traffic on the VC host.
