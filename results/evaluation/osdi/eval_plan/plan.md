# OTTER OSDI Evaluation Plan (user, 2026-10-30)

Source: the user's plan, recorded as given (structure and requirements unchanged). Each figure gets its own
preregistration before any run; this file is the map, not a frozen protocol.

**Guiding question.** Does OTTER reduce streaming interruption relative to existing migration approaches, while
preserving native StreamDiffusionV2 throughput and generation quality, and stay effective under repeated GPU mobility?

## 1. Research questions

| RQ | question | target |
|---|---|---|
| RQ1 | Can OTTER minimize streaming disruption compared with existing migration approaches? | end-to-end |
| RQ2 | Does OTTER preserve the performance of native StreamDiffusionV2? | runtime overhead |
| RQ3 | How does replay-based live migration overcome the limits of conventional state transfer? | M1 |
| RQ4 | How effectively does versioned Sink reuse reduce migration costs? | M2 |
| RQ5 | Can lineage-based staging accelerate repeated GPU mobility? | M3 |
| RQ6 | Does OTTER keep correctness and generation quality across operating conditions? | correctness, quality, sensitivity |

Flow: end-to-end → mechanisms → robustness → quality and overhead.

## 2. Baselines

Primary:

| baseline | type | migration | purpose |
|---|---|---|---|
| StreamDiffusionV2 | native, no migration | none | reference for normal throughput and quality (not a migration competitor) |
| Full | reference migration | full-state stop-and-copy | basic migration cost |
| Llumnix-style (P-full) | external 1 | iterative full-state pre-copy | limits of conventional pre-copy |
| ServerlessLLM-style (R-full) | external 2 | input transfer + full recomputation | recomputation cost |
| OTTER | proposed | M1 + M2 + M3 | streaming-aware live migration |

P-full / R-full are re-implementations in OTTER's harness: always written "Llumnix-style" / "ServerlessLLM-style", with
implementation differences disclosed.

Internal ablations (only where they isolate a mechanism): OTTER without replay (M1), without versioned reuse (M2),
without lineage staging (M3); Wait-for-Sink; P-sink; R-win (W = 6) for the latency-quality trade-off.

## 3. Setup and metrics

Model StreamDiffusionV2; current elves L40S hosts; 1 Gbps default plus a bandwidth sweep; sub-ms LAN; dog, butterfly +
more inputs (vary Sink refresh intensity, duration, motion; the 20 Fig. 5 inputs are candidates, cost permitting);
seed 0 + more seeds; mobility patterns single / repeated / cancelled / return; >= 3 reps per condition, >= 5 for key
results.

| metric | definition |
|---|---|
| TTFO-local | trigger → destination's first local output |
| delivery gap | source's last delivered frame → destination's first delivered frame |
| destination readiness | time until the destination holds the required state |
| remote serving time | cumulative time the serving GPU differs from the user's location |
| transferred bytes | bytes actually sent on the network |
| FPS | generation throughput, normal and during migration |
| quality | reference fidelity and temporal consistency |
| memory overhead | extra GPU / CPU memory held by OTTER |

TTFO-local, delivery gap and readiness are distinct. Check that XB-era and current M1/M2/M3 results use the same
metric definitions.

## 4. Figures

| fig | RQ | panels | methods | priority |
|---|---|---|---|---|
| 7 End-to-end | RQ1 | a TTFO-local, b delivery gap, c transferred bytes; low / high refresh | Full, Llumnix-style, ServerlessLLM-style, OTTER | P0 |
| 8 Continuity + native perf | RQ1-2 | a cumulative delivered frames vs wall time (migration marked), b steady-state FPS: native vs OTTER tracking on, no migration (+ during staging if possible) | native SDV2, Full, P-full, R-full, OTTER | P0 |
| 9 Live replay (M1) | RQ3 | a remaining dirty state per pre-copy round (P-full, Sink-only), b delivery gap / readiness (Wait-for-Sink, P-sink, OTTER replay; + replay / patch / verify cost) | | P1 |
| 10 Versioned reuse (M2) | RQ4 | a Sink bytes vs version age (full, unchanged-only, versioned), b readiness vs version age (full, versioned) | | P1 |
| 11 Repeated mobility (M3) | RQ5 | a remote serving per workload / scenario, b final readiness | Full, ServerlessLLM-style, OTTER w/o staging, full OTTER (Llumnix-style if it completes; mark non-convergence) | P0 |
| 12 Sensitivity | RQ6 | a bandwidth 0.25 / 0.5 / 1 / 2.5 / native Gbps, b time between moves | external, OTTER w/o staging, full OTTER | P1 |
| 13 Quality | RQ6 | a fidelity (PSNR / SSIM or LPIPS vs reference, temporal consistency at the boundary, CLIP optional), b frame strips around the boundary | native SDV2, Full, R-full, OTTER, R-win | P0 |
| 14 Overheads | RQ2 | a throughput loss: native, OTTER idle, OTTER during transfer / staging; b memory: GPU, replay log, Sink metadata, retained state (+ retained-state budget if needed) | | P0 |

Constraints written into the plan:
- Fig. 7 must be re-measured with the current frozen OTTER; XB's 0.67 s / 0.7 s are from an earlier implementation and
  are not the representative result. Check that P-full and R-full meet the same correctness conditions.
- Fig. 8 / 14: overhead is measured, never assumed negligible.
- Fig. 11: separate the gain over external baselines from the effect of staging itself, under the same conditions.
  Scenarios: A→B→C→D; A→B, B→C cancelled, B→D; A→B→A. No claim of lower total traffic (M3-S3: +5-10 %).
  M3-S3 Phase D (internal): readiness 21.3 → 8.2 s low-refresh, 24.7 → 9.7 s high-refresh. XB3/XB4 used a different
  scenario and an older OTTER: rerun current OTTER with external baselines in the same scenario.
- Fig. 12: report the region where the benefit shrinks, if any.
- Fig. 13: control frame alignment and seed; separate reference fidelity from perceptual quality; Sink K/V exactness
  does not imply bitwise-identical output frames.

## 5. Tables

- Table 1, configuration: GPU model / count / memory, CPU / host memory, bandwidth / RTT, model configuration,
  resolution / denoising steps, inputs, migration schedule, repetitions, quality metrics.
- Table 2, correctness and recovery: initial and repeated migration (Sink K/V digest equality), version mismatch
  (invalid lineage rejected), corrupted state (detected), cancelled migration (partial-state validity), previous owner
  failure (recovery). Reuse the M1/M2/M3 0/360 block checks; report only checks actually run.

## 6. Existing evidence → new work

| fig | existing | to do |
|---|---|---|
| 7 | XB1 | rerun external comparison with current OTTER |
| 8 | XB delivery gap, M1 traces | native SDV2 FPS, frame timeline |
| 9 | XB-N, M1 E3 / E6 | per-round pre-copy trace, current replay ablation |
| 10 | M2 E9 / E10, Fig. 5 data | version-age sweep with readiness |
| 11 | XB3 / XB4, M3-S3 Phase D | current OTTER vs external, more mobility patterns |
| 12 | XB 1 Gbps / native | bandwidth and mobility-frequency sweeps |
| 13 | XB quality, M1 / M2 correctness | current OTTER quality, boundary evaluation |
| 14 | runtime traces | native overhead, memory |

## 7. Order

- Phase 1 (P0): (1) current OTTER vs external, Fig. 7; (2) native vs OTTER, Figs. 8, 14; (3) current OTTER repeated
  mobility, Fig. 11; (4) current OTTER quality, Fig. 13.
- Phase 2 (P1): (5) M1 convergence / replay ablation, Fig. 9; (6) M2 version-age sensitivity, Fig. 10; (7) more M3
  mobility scenarios, Fig. 11.
- Phase 3 (P1-P2): (8) bandwidth sweep, 12a; (9) mobility frequency, 12b; (10) more inputs and seeds; (11) retained-state
  memory budget, 14.

First decision: the Fig. 7 protocol (baseline implementation versions, workloads, trigger, quality gate, measurement
window, repetitions), shared by every later figure.

## 8. Minimum for submission

External (Llumnix-style + ServerlessLLM-style); native SDV2; TTFO-local, delivery gap, bytes; frame-delivery continuity;
M1 replay ablation + pre-copy convergence; M2 real cost reduction; M3 repeated mobility + staging ablation; reference
fidelity + boundary consistency; exact Sink verification; multiple workloads, seeds, bandwidths; FPS + GPU memory.
These are required comparisons, not required numbers.

## 9. Paper structure

6.1 Setup (hardware, workloads, baselines, metrics) · 6.2 End-to-end (Figs. 7, 8) · 6.3 Mechanisms (Figs. 9-11) ·
6.4 Sensitivity (Fig. 12) · 6.5 Quality and correctness (Fig. 13, Table 2) · 6.6 Overheads (Fig. 14).
