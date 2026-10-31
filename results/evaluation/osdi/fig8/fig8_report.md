# Fig. 8 report: streaming continuity and native performance

Preregistration FROZEN 6badbbea (decisions D1-D5). Runs: 8a = re-analysis of the 40 Fig. 7 runs (3dd8cd3c); 8b = 20
native runs (A, B) and 10 OTTER runs with M2 + M3 tracking (ecffe467, run commit 3dd8cd3c on every host).
Numbers: `fig8_results.{json,md}` (`tools/eval/fig8_report.py`). Figures: `figures/` (`tools/eval/plot_fig8.py`).

## 1. Verdicts (frozen rules)

| hypothesis | Low-refresh (dog) | High-refresh (butterfly) | verdict |
|---|---|---|---|
| F8-H1: median total stall OTTER <= 0.25 x best baseline | 0.111 | 0.106 | **SUPPORTED** |
| F8-H2: median OTTER time per call (B) <= 1.03 x native (B) | 1.054 | 1.055 | **NOT SUPPORTED** |

## 2. Validity

- 8a: 40 / 40 Fig. 7 runs valid (unchanged); the longest interval of every run equals its Fig. 7 delivery gap (asserted).
- Native: 20 / 20 valid. rc 0, 120 / 120 window chunks, NVIDIA L40S (driver 575.51.03), looped input equal to the
  repeated original by PyAV and by upstream's loader (`loader_equal` true on both hosts), one commit (3dd8cd3c).
  Upstream's own "Average FPS" agrees with the window median within 0.1 %.
- OTTER: 10 / 10 valid. Fig. 7 validity, C1 pass, `track_ms` on all 91 window calls, no migration or staging event in
  the window.

## 3. Panel 8a: cumulative stall time [V] measured

| method | dog total stall (s) | butterfly total stall (s) | stalls |
|---|---|---|---|
| Full | 53.64 [53.58-53.65] | 53.62 [53.45-53.63] | 1 |
| Llumnix-style P-full | 61.80 [61.48-62.04] | 63.48 [63.41-63.52] | 10 |
| ServerlessLLM-style R-full | 17.86 [17.82-17.90] | 17.73 [17.70-17.76] | 1 |
| OTTER | 1.99 [1.96-2.02] | 1.87 [1.87-2.10] | 2 |

OTTER's two stalls are the source start stall and the cutover. P-full accumulates a snapshot stall in every pre-copy
round plus the final stop-and-copy, so its total exceeds Full's although its longest stall is shorter.

## 4. Panel 8b: steady-state throughput on host B [V] measured

| | dog per call (s) | dog frames/s | butterfly per call (s) | butterfly frames/s |
|---|---|---|---|---|
| native, host A | 0.5309 [0.5309-0.5310] | 7.53 | 0.5323 [0.5313-0.5330] | 7.52 |
| **native, host B** | 0.5277 [0.5272-0.5278] | **7.58** | 0.5281 [0.5275-0.5283] | **7.57** |
| OTTER generation, B | 0.5554 [0.5552-0.5562] | 7.20 | 0.5565 [0.5522-0.5565] | 7.19 |
| **OTTER generation + tracking, B** | 0.5560 [0.5558-0.5569] | **7.19** | 0.5571 [0.5528-0.5571] | **7.18** |
| OTTER tracking per call (ms), median / max | 0.57 / 1.16 | | 0.58 / 0.79 | |
| OTTER delivered call period, B (descriptive) | 0.6035 | 6.63 | 0.6042 | 6.62 |

Real-time ratio against 16 fps output: native 0.47, OTTER 0.45 (neither is real time on one L40S at this setting).

### Where the 5.4 % comes from (descriptive; existing logs, no new runs; not a preregistered test)

| step | dog | butterfly | source |
|---|---|---|---|
| native, host A | 0.5309 s | 0.5323 s | upstream `--profile` |
| harness generation, host A, **no OTTER code** | 0.5576 s (+5.0 %) | 0.5585 s (+4.9 %) | A's uninterrupted reference session in the same 8b runs (`node_A/baseline_record.json`, `service_s`, calls 40-159, same timer as `chunk_s`; median of the 5 run medians) |
| OTTER M2 + M3 tracking, host B | +0.57 ms (+0.10 %) | +0.58 ms (+0.10 %) | `track_ms` |

- The OTTER tracking added per call is 0.1 %. The rest of the gap (about 5 %) is already present on host A when the
  harness generates the uninterrupted reference with no OTTER code at all.
- Code-level differences between the harness generation path and upstream's loop (from the code, not separated by
  measurement): deterministic settings (`cudnn.deterministic`, `cudnn.benchmark = False`,
  `use_deterministic_algorithms`, CUBLAS workspace); a host-to-device copy of each call's input (upstream holds the whole
  input on the GPU in bf16); conversion of each call's output to uint8 on the CPU; per-call `torch.manual_seed`; the
  node's other threads. Which of them accounts for the 5 % is not identified.
- This does not change the verdict: F8-H2 is NOT SUPPORTED by the frozen rule, which compares the integrated execution
  (section 4 of the preregistration) with native.

## 5. Figures

- `fig8a_dog`, `fig8a_bfly`: cumulative stall (s) vs time since the migration trigger (s); thick step line = the rep
  with the median total stall, thin lines = the other reps; every curve ends at its run's last chunk (marker); total
  stall printed at the end. Linear axes from 0.
- `fig8b_throughput`: native (B) vs OTTER (B, generation + tracking); bar = median, whisker = IQR, dots = 5 reps;
  value printed.

## 6. Claim wording

Can claim:
- "Over the whole migration, OTTER accumulates 1.9-2.0 s of output stall, 9.0-9.5x less than the best full-state
  baseline (ServerlessLLM-style, 17.7-17.9 s) and 27-34x less than Full and Llumnix-style pre-copy." (two workloads,
  one A -> B migration at 1 Gbps)
- "OTTER's per-call version and lineage tracking costs 0.6 ms (0.1 % of a call)."
- "In our prototype, steady-state generation runs at 7.2 frames/s vs 7.6 for native StreamDiffusionV2 (5.4 % slower);
  the same gap appears in our evaluation harness without any OTTER code."

Must not claim:
- That OTTER runs within 3 % of native, "no overhead", or "native performance" (F8-H2 NOT SUPPORTED).
- That the 5 % is caused by determinism or by any one harness difference (not separated).
- That the 0.1 % is the whole cost of OTTER in steady state on its own path (the comparison with native is integrated).
- Frame loss (the harness delays; it does not drop), WAN latency, or any overhead during migration or staging (Fig. 14).

## 7. Open options (user decision; none run)

1. Report as is: F8-H2 NOT SUPPORTED, with the decomposition in section 4.
2. An exploratory diagnosis under its own preregistration (it cannot change F8-H2): for example on host B, native with
   the harness's deterministic settings, and the harness reference session without them, 5 reps each, to identify the
   cause class of the 5 %.
