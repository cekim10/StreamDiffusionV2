# Experiment WX results: workload expansion of the core mobility experiments (GPU, 2026-10-21)

Frozen preregistration `preregistration.md` (a181126; record `../expWX_freeze.md`, including the 2026-10-21 shakedown-check
correction), implementation e576643 / 6c9f846. GPU shakedown 21 / 21 PASS. Main sweep **144 runs, 144 valid, 0
inapplicable, no re-run** (butterfly-feeding-slow-motion, audi-snow-trail, train; seed 0; A -> B -> C -> D; 1 Gbps).
Verdicts by `tools/eval/aggregate_wx.py` (`wx_results.{md,json}`), applying the frozen R and M3E rules per input; dog =
the frozen R / M3E verdicts (read, not recomputed). Nothing in the configurations, thresholds or rules changed after the
freeze.

## 1. Verdicts: every imported hypothesis supported on all four tested inputs

| config | hypothesis | dog (frozen) | butterfly | audi-snow-trail | train | supported on |
|---|---|---|---|---|---|---|
| X1 rho 1 | R-H1 / R-H2 / R-H3(a) | S / S / S | S / S / S | S / S / S | S / S / S | 4 / 4 each |
| X2 rho 4 | R-H1 / R-H2 / R-H3(a) | S / S / S | S / S / S | S / S / S | S / S / S | 4 / 4 each |
| X3 rho 2, no change | R-H1 / R-H2 / R-H3(a); M3E H4, H6, H7 | all S | all S | all S | all S | 4 / 4 each |
| X4 contention | M3E H1, H6, H7 | all S | all S | all S | all S | 4 / 4 each |
| X5 holder bottleneck | M3E H2, H6, H7 | all S | all S | all S | all S | 4 / 4 each |
| X6 ingress bottleneck | M3E H3, H6, H7 | all S | all S | all S | all S | 4 / 4 each |

S = SUPPORTED. **No NOT SUPPORTED and no NOT EVALUABLE cell.** R's manipulation check MET in every input at rho 2 and 4.

## 2. Numbers (medians of 3 reps; bind-ready after the final move)

| | butterfly | audi-snow-trail | train | dog (frozen) |
|---|---|---|---|---|
| X1 rho 1: B_source M1 only / M1 + M2; reduction | 3.000 / 1.008; 99.6 % | 3.000 / 1.011; 99.5 % | 3.000 / 1.008; 99.6 % | 3.000 / 1.008; 99.6 % |
| X2 rho 4: reduction; discarded M1 + M2 | 93.0 %; 0.053 | 93.0 %; 0.053 | 94.4 %; 0.044 | 93.9 %; 0.044 |
| X3 rho 2: reduction; bind M1 only / M1 + M2 / M3-v2 | 96.2 %; 15.65 / 15.60 / 15.66 s | 96.4 %; 15.44 / 15.37 / 15.50 s | 96.2 %; 15.48 / 15.40 / 15.50 s | 96.2 %; M3E S4 15.34 / 15.38 / 15.33 s |
| X4 contention: M1 only / M1 + M2 / M3-v2 | 57.03 / 42.87 / 43.20 s | 57.11 / 42.74 / 42.77 s | 57.20 / 42.95 / 43.04 s | 57.23 / 43.23 / 43.08 s |
| X5 holder: M3-v2 / at moves / M1 + M2 / M1 only; M3-v2 re-plans (probes) | 20.67 / 52.10 / 78.69 / 15.73 s; 2 (1) | 20.79 / 50.96 / 78.13 / 15.47 s; 2 (1) | 20.39 / 52.24 / 79.38 / 15.88 s; 2 (1) | 20.71 / 52.13 / 78.53 / 15.50 s; 2 (1) |
| X5: M3-v2 B_source; share of M1 only's redundant bytes removed | 1.177; 82.7 % | 1.185; 82.1 % | 1.182; 82.1 % | 1.180 (M3E) |
| X6 ingress: M3-v2 / M1 + M2; M3-v2 re-plans | 118.18 / 118.27 s; 0 | 118.03 / 117.94 s; 0 | 118.10 / 117.88 s; 0 | 118.40 / 117.52 s; 0 |

M3-v2 re-planned 0 times in every X3, X4 and X6 run on every input and exactly 2 times (one 4-fragment probe) in every
X5 run.

## 3. Descriptive observations

- **The restoration results are input-independent within the tested set.** Bind-ready, source bytes, discarded work
  and re-planning differ across the four inputs by at most ~0.5 s and ~0.03 Sink in every configuration; promotion
  frequency (16 to 200 per 330 calls in W1) did not change them, and no run was inapplicable (no owner-side promotion
  before the final bind at rho >= 1).
- **Reference-trajectory recovery is input-dependent:** on the three refresh-heavy inputs the final owner never
  reached 35 dB in any of the 144 runs (every run ended at the call window), whereas dog rejoins in R / M3E. This is the
  RD finding (failure associated with Sink-less time after three moves) on a further 144 runs; it does not affect any WX
  hypothesis, which concern restoration, bytes and re-planning only.
- H2's source-byte threshold rationale (about 65 % of M1 only's redundant bytes removed) holds on every input:
  82.1-82.7 % removed.

## 4. Scope

Four tested video inputs with their prompts (dog = the tabby-cat video with "A dog walks on the grass, realistic"),
seed 0, one model (StreamDiffusionV2 1.3B), emulated 1 Gbps caps, rho 1 / 2 / 4, one degradation magnitude and onset.
No claim extends beyond them.
