# OTTER (OSDI) paper claims list - 2026-10-20

Built from frozen results only; no result or verdict is changed here and no experiment is proposed as run. Sources (all
under `results/evaluation/`):

| short | frozen plan / report | run directories |
|---|---|---|
| ExpD | `osdi/prereg_freeze.md` (81bb628), `osdi/expD/expD_report.md` (+ erratum 2026-10-19), `osdi/expD/expD_results.{md,json}` | `expD_{A,Agen_*,B,C,D,E,F,G,G9}/` (147 runs + G9) |
| W / R / N | `osdi/followup_prereg_freeze.md` (4001882), `osdi/wrn_report.md`, `osdi/wrn_results.{md,json}`, `osdi/w2_table.csv` | `expW_W1/`, `expW_W2_<clip>_s<seed>/`, `expW_WAR_*`, `expR_c{0,3}/`, `expN_cell{1..10}/` (312 runs) |
| M3-v2 dev | `osdi/expN/m3_root_cause.md`, `m3v2_design.md` (frozen e39609a), `m3v2_gpu_regression{,_r2}.md` | `m3dev_cell{7..10}/`, `m3dev_r2_cell{7..10}/` (development data, not evidence) |
| V | `osdi/expN/m3v2_holdout_plan.md` (+ Amendment 1), `osdi/expN/expV_report.md` | `expV_cell{4..7}/`, `expV_a1_cell{1,2,3,8}/` (96 runs in the verdict set; `expV_cell{1,2,3,8}` superseded) |
| A, B | `osdi/m1m2_followup.md` (A frozen bfc2ce0), `osdi/m1m2_results.md`, `osdi/expB_reuse.{md,json}` | `expA_<clip>_s<seed>/` (40 runs), `expW_B/` (10 runs) |
| VACW | `osdi/expM2/vacw_v0_design.md` (9137bc9 + Amendment 1), `osdi/vacw_v0_freeze.md`, `osdi/expM2/vacw_v0_report.md`, `vacw_v0_results.{md,json}` | `expVA_{dog,butterfly-feeding-slow-motion}_rho{0.5,1}/` (36 runs) |
| background | earlier single-GPU state study and Phase 1 handoff (`osdi/existing_results_inventory.md` rows 1, 2, 5, 6) | `state_migration/prompt_sweep/`, `state_migration/mechanism/`, `single_handoff/` - **not preregistered under the OSDI protocol**; cite as characterization, not as evaluation |

Interpretation rules applied throughout (from the instruction of 2026-10-20): VACW stays NO-GO; frozen M2 assumes a
stable Sink snapshot; VACW H2 is capturing-owner egress, not aggregate traffic; VACW H3 passes against
`restart_fresh` only (1.1-1.5 s slower than stale `split`); no claim that a fresh Sink improves or preserves visual
recovery; butterfly fails trajectory recovery under all three policies at three hops; execution resumption, Sink
integrity and reference-trajectory recovery are separate; single PSNR crossing is not sustained recovery; PSNR is not
perceptual continuity; V contains a NOT SUPPORTED hypothesis; Experiment T is paused; canonicalization is deferred and
is not a paper mechanism.

Common conditions unless stated: StreamDiffusionV2 1.3B, video-to-video, 480 x 832, 4 x L40S (elves-01..04, GPU 0),
Ethernet with software-emulated per-node caps (token bucket + max-min allocation), warm destinations (process running,
weights loaded), T_s = 14.05 s at 1 Gbps, PSNR against the uninterrupted run of the same seed (35 dB = "rejoin").

Classification: **Main** / **Supporting** / **Limitation** / **Unsupported (must not claim)**.

---

## M1 - Temporal State Decomposition

**M1-1. Execution resumes in well under a second, independent of bandwidth and input.** - *Main*
- Wording: "OTTER resumes generation at the destination 0.67-0.69 s after a migration trigger, for every tested input
  and bandwidth, by transferring only 2.67 MiB of immediate state."
- Evidence: ExpD G1 SUPPORTED - TTFO 0.675 s at 1 Gbps (0.67-0.68), 0.680 s native, vs Full migration 54.25 s (ratio
  0.012) (`expD_A/`); W-H1 SUPPORTED - 0.668-0.693 s over 20 workloads x 2 seeds, spread 0.024 s (`expW_W2_*`); ExpD
  generalization bird / boxing 0.67-0.72 s (`expD_Agen_*`); background Phase 1: 0.69-0.74 s from 250 Mbps to native.
- Holds: warm destination; single GPU session per node; fast path over a separate TCP connection.
- Counterexamples: cold destination TTFO 70.7-75.7 s (process start + weight load + CUDA init dominate; ExpD external
  group); Experiment A: every recent slot added to the fast path costs +0.9 s at native.
- Does NOT establish: that the output during the gap is continuous with the pre-migration stream (gap PSNR vs the
  reference ~17 dB, Exp A n = 0 median over the first 6 calls); anything about perceived interruption; behaviour with a
  cold destination.

**M1-2. Taking the Sink off the critical path does not prevent a later return to the reference, under bounded
conditions; without the Sink the stream never returns.** - *Main (narrowed 2026-10-20)*
- Wording: "Execution resumes without the attention Sink; when the Sink is bound later, the stream can return to the
  uninterrupted trajectory - after one move at 1 Gbps it crosses back in 39 of 40 inputs and stays there in 31 - while
  without the Sink it never does. How late the Sink may arrive is not established: after three moves (~71 Sink-less
  calls) one refresh-heavy input never returns."
- Evidence: W-H3 SUPPORTED - Cold restart reaches 35 dB in 0 qualifying units (last-10 medians 18-30 dB); W-H2 39 / 40
  units cross 35 dB after a late bind (bind at call 58-59, rejoin median 7 calls, range 3-40; `w2_table.csv`); ExpD
  scenario B: Cold restart never rejoins; background state study: Sink loss diverges in 31 / 31 runs.
- Holds: single move, 1 Gbps, M = 34, horizon 100 calls (W2).
- Counterexamples: audi-snow-trail s1 never crosses (W2); 9 of 40 W2 units never hold 10 consecutive calls >= 35 dB
  (`w2_table.csv`, `sustained_calls` empty); butterfly 0 / 18 after three moves (E2E-4).
- Does NOT establish: a tolerable Sink delay ("the Sink may arrive late" in general); sustained recovery for
  refresh-heavy inputs (E2E-2); recovery after several moves (E2E-4).

**M1-3. Recent KV and VAE caches need not be transferred.** - *Supporting*
- Wording: "Shipping recent KV slots with the fast path does not improve recovery and delays resumption."
- Evidence: Experiment A NO-GO for n = 1, 2, 3 slots (`expA_*`, 40 runs, native): sustained 10 / 10 units at every n,
  terminal PSNR 42.1-42.3 vs 42.3 dB, gap +1.8-2.2 dB, TTFO +0.9 s and +575 MB per slot; background state study:
  ephemeral-only loss heals in 21 / 21 runs without a refresh before M, 5 / 10 with one.
- Holds: native bandwidth (A); the background study's conditions for the ephemeral result.
- Counterexamples: background study - ephemeral-only loss did not heal on bird k2 / k4 within 40 chunks.
- Does NOT establish: that reconstruction of the recent window is always harmless (the background bird cases); the
  effect at 1 Gbps (A at 1 Gbps not run; +4.6 s per slot computed, not measured).

**M1-4. Sink churn is real and dominated by RoPE realignment.** - *Supporting (motivation for M2 scope)*
- Evidence: W1 - no unit single-version stable at w = 25 calls (0 / 40; P_25 medians 0.50 / 0.79 / 0.97 by group);
  Task B exact (`expW_B/`): realignment re-rotates ~half the Sink K every ~45 calls; 412-fragment reuse 50-64 % after
  50 calls (88-99 % refresh-only); RoPE re-rotation not bitwise (2-6 % of bf16 elements differ by one ulp).
- Does NOT establish: that canonicalized keys reconstruct correctly end to end (not tested; canonicalization deferred).

**M1-x. Unsupported / must not claim**
- "Transferring recent KV improves continuity" (A NO-GO). "Recovery is independent of the workload" (E2E-2..4).
  "Resumption is seamless / without visible interruption" (gap PSNR ~17 dB; no perceptual measurement).

## M2 - Continuity Wavefront

**M2-1. Verified restoration progress is kept across repeated moves, removing almost all redundant source traffic.** -
*Main*
- Wording: "Across repeated moves, OTTER forwards fragments already verified at earlier owners instead of re-sending them
  from the source, removing 87-99.6 % of the redundant source bytes of restart-style restoration and keeping discarded
  work at or below 0.06 Sink."
- Evidence: R-H1 SUPPORTED in 8 / 10 cells, R-H2 in 9 / 10 (`expR_c0/`, `expR_c3/`): M1 + M2 B_source 1.008-1.039
  Sinks vs M1 only 1.068-3.000; discarded 0.010-0.061 vs up to 2.000; ExpD G3 rho 2 (1.03 vs 2.01 source, 0.049 vs
  1.014 discarded) and rho 4 SUPPORTED (`expD_B/`); G8 revisit: bind-ready 8.38-8.72 vs 15.41 s (`expD_G/`).
- Holds: rho 1-8 at 1 Gbps on dog; one Sink snapshot per restoration (stable-version assumption, M2-4). **WX
  (2026-10-21): R-H1 / R-H2 / R-H3(a) also supported at rho 1, 2, 4 on butterfly-feeding-slow-motion, audi-snow-trail
  and train (4 / 4 tested inputs, seed 0; reduction 93.0-99.6 %, discarded <= 0.058 Sink).**
- Counterexamples / NE: R rho 0.5 c = 0 NOT EVALUABLE (version event in 9 / 9 runs); R-H1 rho 8 c = 3 NOT EVALUABLE.
- Does NOT establish: lower aggregate network traffic (every owner still receives one full Sink); behaviour on other
  workloads (R is dog only).

**M2-2. Without contention progress preservation does not change latency; under source contention it shortens it as a
system.** - *Supporting*
- Evidence: R-H3(a) SUPPORTED rho 1-8 (bind-ready within 0.17 s, 15.3-15.6 s, ingress-bound); R-H3(b) SUPPORTED at
  rho 1 (28.9 vs 57.4 s) and rho 2 (43.0 vs 57.0 s); NOT EVALUABLE at rho 0.5 (exposure); rho 4 / 8 descriptive (49.8 /
  53.6 vs 57.1 s); ExpD G6 (scenario E, `expD_E/`): GPU-session bind-ready 43.09 (M1 + M2) / 42.82 (OTTER event-driven) vs 57.07 s.
- Holds: c = 3 background network sessions on the source's egress; 1 Gbps.
- Does NOT establish: a per-session latency gain without contention; scaling beyond c = 3 on GPUs (network-level
  sessions only).

**M2-3. Restored Sinks are integrity-verified at every bind.** - *Main (as a property)*
- Wording: "Every bound Sink is byte-identical to the snapshot it was taken from (per-fragment SHA-256 plus whole-Sink
  digest)."
- Evidence: validity rule `final_sink_digest_matches_source` and `all_fragments_verified` hold in every valid ExpD and
  W / R / N fast-path run (`wrn_validity.py`, ExpD validation); VACW H1a 24 / 24 binds of the intended snapshot.
- Does NOT establish: that the snapshot is the *current* Sink of the session (M2-4).

**M2-4. The frozen M2 restores the trigger-time snapshot (stable-version assumption).** - *Limitation (must be stated)*
- Evidence: ExpD erratum - in all 69 repeated-mobility runs no owner bound before being left, so the assumption held by
  timing, not because the Sink was static (dog promotes 16-18 times in 330 calls); R rho 0.5 c = 0: the bound owner's
  Sink changes before the move in every run (NOT EVALUABLE); VACW: at rho 0.5 every owner after the first binds and
  generates before it is left, and the frozen `split` binds S_0 at C and D.
- Effect measured so far (descriptive): dog rho 0.5 stale `split` still crosses 35 dB in 3 / 3 (max 41.3 dB vs 43.6-44.1
  with fresh Sinks); butterfly fails with either.
- Wording for the paper: "M2 restores the Sink snapshot taken at the trigger; when an owner binds and generates before
  it is left (T_m > T_s), downstream owners restore an older Sink than the one the session last used."

**M2-5. Fresh snapshots with hash reuse are implementable and correct, but not adopted (VACW v0, NO-GO).** -
*Limitation / negative result (may be reported as such)*
- Evidence (`expVA_*`, 36 / 36 valid): H1a SUPPORTED (24 / 24 binds); H1b NOT SUPPORTED (6 / 12; butterfly 0 / 6); H2
  SUPPORTED at rho 0.5 - capturing-owner egress 0.429 (dog) / 0.523 (butterfly) vs 1.000 Sink for `restart_fresh`,
  aggregate 3.00 Sinks for every policy; H3 SUPPORTED at rho 0.5 against `restart_fresh` (+0.22 / -0.23 s) but **1.1-1.5 s
  slower than stale `split`** (manifest wait ~1.5 s: D2H + pack 0.93-1.14 s, hashing 0.13 s, install 0.17-0.24 s); rho 1
  NOT EVALUABLE (no fresh transition). Decision NO-GO by the frozen rule.
- Does NOT establish: any effect of a fresh Sink on visual recovery (butterfly fails under all three policies; dog
  difference is 3 reps, descriptive); aggregate traffic reduction; benefit at rho >= 1.

**M2-x. Unsupported / must not claim**
- "OTTER reduces network traffic" (aggregate is unchanged; say *source / redundant* bytes). "Every owner restores the
  latest state" (stable-version). "Fresh snapshots improve continuity." The superseded 94 % / ~30 Mbps reuse estimate.
  Key canonicalization as a mechanism (deferred).

## M3 - Restoration Graph Morphing

(Pre-positioning results are listed here; if the paper presents placement as a separate component, move G4 / G5.)

**M3-1. Correct pre-positioning cuts bind-ready by two thirds; incorrect placement costs no latency.** - *Main*
- Evidence: ExpD G4 SUPPORTED - Full OTTER bind-ready 4.94 s (4.94-4.96) vs 15.42 s (`expD_C/`); scenario C oracle
  4.90-4.93 s; N cells 4-6 (correct placement) 4.95 / 32.6-32.8 s. ExpD G5 NOT SUPPORTED for OTTER event-driven
  (scenario D, `expD_D/`; M3-v1: B_source 1.23 > 1.02, B_post 0.51 > 0.30, B_fwd 0.50 < 0.64) while M1 + M2 + top-1 met every clause (1.01 /
  0.29 / 0.72; reported, not judged); latency unchanged (15.46 vs 15.53 s).
- Holds: dog, one move, lookahead L = 10 s, budget 1 Sink, placement probabilities as preregistered.
- Does NOT establish: how often placement is correct in practice (no trace; ExpT paused).

**M3-2. The bottleneck-aware event-driven planner (M3-v2) avoids unneeded re-plans and keeps the gain where an
alternative provider exists.** - *Main, with its stated limitation*
- Wording: "When a provider degrades and its fragments are available elsewhere, OTTER re-plans 2.0-5.7 x faster
  restoration than planning at moves; when no alternative exists or nothing changed, it does not re-plan (at most one
  4-fragment probe)."
- Evidence: V holdout (`expV_a1_cell{1,2,3,8}/`, `expV_cell{4..7}/`): V-H1 1 / 1, V-H2 3 / 3 (V2 12.24 vs 44.95 s; V4
  19.12 vs 38.32; V5 21.57 vs 122.08), V-H3 4 / 4 (0 re-plans in V6-V8, one probe in V3).
- Counterexamples: **V-H4 NOT SUPPORTED in V4 / V5** - v2 is 4.1 s slower than M3-v1 when the degraded holder is the
  only active provider (probe + confirmation delay).
- Holds: dog seed 0, single move, one magnitude and onset per cell, frozen parameters (min_frags 8, 2-fragment margins,
  probe 4).
- **End-to-end with repeated moves (M3E, `expM3E/m3e_report.md`, 2026-10-20): H1-H7 all SUPPORTED** - contention
  43.1 vs 57.2 s (M1 only); holder bottleneck 20.7 s vs 52.1 s (at moves) and 78.5 s (M1 + M2) with 2 re-plans; 0
  re-plans and no harm under ingress / source bottlenecks and without change; TTFO and GPU service time unchanged.
  M3-v2 is 5.2 s slower than M1 only in the holder-bottleneck case (M1 only avoids the holder at 2.0 Sinks of source
  traffic). rho 2. **WX (2026-10-21): H1-H4, H6, H7 supported on all four tested inputs** (dog, butterfly, audi-snow-trail,
  train; seed 0), with 0 re-plans wherever re-planning cannot help and 2 (one probe) under the holder bottleneck.
- Does NOT establish: performance under realistic, continuously varying traces (ExpT paused); inputs, seeds or models
  beyond the four tested inputs, seed 0 and StreamDiffusionV2 1.3B; four concurrent M3-v2 GPU sessions (M3E S1 / WX X4
  used network-level M3-v1 competitors).

**M3-3. The frozen M3-v1 rule mis-models shared ingress and oscillates.** - *Limitation (motivates v2; report)*
- Evidence: N-H1 NOT SUPPORTED cell 7 (1 false-positive re-plan per rep, +0.22 Sink), N-H3 NOT SUPPORTED cells 8 (+3.5 s)
  and 10 (28-32 re-plans, +0.23 Sink), N-H2 NOT SUPPORTED cell 9 (7.5 x faster but 3 > 2 re-plans); root cause
  `m3_root_cause.md` (shared-ingress shares read as independent capacities; fragment-quantized rates).
- Note: M3-v2 was developed on N cells 7-10 (development data) and evaluated on V; the V result, not the regression
  PASS, is the evidence.

**M3-x. Unsupported / must not claim**
- "M3 improves restoration under network changes" without the class qualifier (cells 2, 3, 5, 6, V3, V6-V8: nothing to
  gain). "M3-v2 dominates M3-v1" (V-H4 6 / 8). Results on real mobility / network traces.

## End-to-end visual continuity (three separate levels)

**E2E-1. Execution resumption** - see M1-1 (*Main*). Fast output, not uninterrupted appearance: gap frames diverge from
the reference (~17 dB) until the Sink binds (~15 s at 1 Gbps, ~3 s native).

**E2E-2. Single crossing vs sustained recovery after one move.** - *Supporting + Limitation*
- Evidence: W-H2 39 / 40 single crossings (all 40 units valid after one re-run); sustained (10 consecutive calls >= 35 dB)
  in 31 / 40: **8 crossing units never hold it** (train x2, street-artist-painting x2, butterfly x2, cricket-bat-practice
  s0, audi-snow-trail s0) plus the non-crossing audi-snow-trail s1; 9
  end the horizon with a last-10 median < 35 dB (W2, 1 Gbps). At native bandwidth (Exp A) all 10 units tested,
  including four of those clips, sustain 35 dB 6-11 calls after the bind (observation, not a hypothesis of A).
- Wording: "After one move at 1 Gbps, the stream crosses back to the reference in 39 of 40 inputs and stays there in 31;
  refresh-heavy inputs may not stay there."
- Does NOT establish: sustained recovery for refresh-heavy inputs at 1 Gbps; causality of bind latency (correlational).

**E2E-3. Sink integrity** - see M2-3 (*Main*, as a property).

**E2E-4. Reference-trajectory recovery after three moves is workload-dependent.** - *Limitation (must be stated)*
- Evidence (VACW runs, all three policies): dog crosses 35 dB in 18 / 18 runs; butterfly in **0 / 18** (`split`,
  `restart_fresh`, `split_va`, rho 0.5 and 1), post-bind last-10 median ~29.5 dB, maximum 32.2-33.8 dB over 180-230
  calls after a bind at call 101-151; R / ExpD repeated mobility are dog-only.
- Does NOT establish: the cause (Sink-less duration, repeated resets, Sink / recent mismatch, or workload sensitivity;
  not isolated); whether the diverged stream is perceptually acceptable.

**E2E-x. Unsupported / must not claim**
- "OTTER preserves visual continuity" or "continuity-preserving migration" without the three-level qualification.
  Perceptual continuity from PSNR (PSNR-to-reference measures trajectory equality; SSIM-vs-input ~0.42 for every
  stream in the background study). Any no-reference temporal metric (not measured).

## System overhead and generality

**S-1. No steady-state cost.** - *Supporting*
- Evidence: ExpD G9 - chunk service time +0.10 % (identical frames); destination peak `memory_allocated` OTTER 27.93 GiB
  = M1 only, Full migration 28.66, Cold 28.02 GiB. G9 as frozen is **NOT SUPPORTED** (memory spread 2.6 % > 1 %); state
  it as measured, with OTTER at the lowest value.
- Fresh-snapshot capture (VACW, not adopted): ~1.1-1.3 s per handoff of a bound owner.

**S-2. Workload breadth for resumption and single-move recovery.** - *Supporting*
- Evidence: 20 inputs (4 repo clips + 16 LOVEU-TGVE) x 2 seeds in W; RVC in 36 / 40 units did not prevent crossing
  (35 / 36). LOVEU frames may not appear in figures (collection-level licence).

**S-3. Generality beyond the testbed.** - *Limitation*
- One model (1.3B), one resolution, one GPU type, emulated caps on a single Ethernet fabric (no latency / loss
  emulation), warm destinations, one GPU session per node; repeated-mobility, network-adaptation, holdout and VACW
  experiments on one or two workloads; external C/R not run (no CRIU / cuda-checkpoint on the testbed, driver 575; ExpD);
  Experiment T (traces) paused.

---

## A. The strongest defensible claims (5-7)

1. **Sub-second resumption** (M1-1): 0.67-0.69 s to first output across 20 inputs x 2 seeds and from 250 Mbps to native,
   80 x faster than Full migration at 1 Gbps (54.25 s), with 2.67 MiB of immediate state; warm destination.
2. **The Sink can be taken off the critical path** (M1-2, M1-3): generation resumes without it; bound after one move at
   1 Gbps the stream crosses back to the reference in 39 / 40 inputs and stays in 31 / 40; without it, never (0 units,
   31 / 31 background runs); shipping recent KV adds +0.9 s per slot for no recovery gain (A NO-GO). The tolerable Sink
   delay is not established (three moves: butterfly 0 / 18).
3. **Verified Sink integrity at every bind** (M2-3): digest-identical binds in every valid run, including 24 / 24 fresh
   and stale binds in VACW.
4. **Progress preservation across repeated moves** (M2-1, M2-2): 87-99.6 % of redundant source bytes removed, discarded
   work <= 0.06 Sink at rho 1-8; revisit 8.4-8.7 vs 15.4 s; under source contention 28.9 vs 57.4 s (rho 1) and 43.0 vs
   57.0 s (rho 2) - for a stable Sink snapshot.
5. **Placement** (M3-1): correct pre-positioning 15.42 -> 4.94 s; an incorrect placement costs no latency with M2.
6. **Bottleneck-aware re-planning, conditioned** (M3-2): 2.0-5.7 x faster where an alternative exists, no re-plan where
   none does (V-H1 / H2 / H3 all supported), with the measured 4.1 s reaction cost when the degraded holder is alone.

Proposed headline (revised from the 2026-10-20 draft): *"OTTER resumes streaming video-diffusion sessions on a warm
destination in under a second by decoupling execution from restoration of the attention Sink, binds an integrity-
verified Sink snapshot as soon as it arrives, preserves verified restoration progress across repeated migrations, and
re-plans fragment delivery when a provider becomes the bottleneck."* It omits trajectory recovery, aggregate traffic,
and freshness of the restored Sink.

## B. Most serious reviewer objections

1. **"What does continuity mean here?"** Output resumes fast, but gap frames diverge (~17 dB) for the whole restoration
   window, return to the reference is a single PSNR crossing, refresh-heavy inputs do not stay there at 1 Gbps (8 / 40),
   and after three moves butterfly never returns under any policy; there is no perceptual or no-reference measure.
2. **Stale restoration in the slow-mobility regime.** When T_m > T_s (owners bind and generate before moving), M2
   restores the trigger-time snapshot; the fix (VACW) is correct and cuts source egress but is NO-GO and adds ~1.5 s
   against stale restoration.
3. **Narrow evaluation surface.** One model / resolution / GPU; emulated bandwidth caps only; dog-only repeated mobility
   and network adaptation; M3-v2 holdout on one workload and single moves; the ExpD end-to-end numbers use M3-v1, not
   the final M3.
4. **Baselines.** Full migration and Cold restart are the only system baselines; no CRIU / cuda-checkpoint comparison
   (not runnable on the testbed), no pre-copy live migration of the Sink while generating (Task B: 120-236 Mbps dirty
   rate at a 25-call sync suggests a cost, but it is not implemented or measured).
5. **Realism of mobility and network dynamics.** rho values and degradation onsets are synthetic (one magnitude, one
   onset); the trace study (T) is paused; warm destinations are assumed (cold destination ~71-76 s).

## C. Remove from the abstract / introduction

- "seamless", "uninterrupted", "continuity-preserving" or "preserves visual continuity" without the three-level split.
- "restores the original generation trajectory" as a general property.
- "reduces network traffic" (say redundant / source bytes; aggregate unchanged).
- "always restores the latest state" / any freshness claim for M2.
- "adapts to changing networks" without the class qualifier; "M3-v2 improves on M3-v1" without V-H4.
- "negligible overhead" beyond the measured +0.10 % service time (memory criterion failed as frozen).
- "generalizes across models / deployments"; "outperforms checkpoint/restore".
- Recent-KV transfer as a benefit; canonicalized-key reuse; the 94 % / 30 Mbps estimate.

## D. Evidence gaps that materially affect OSDI readiness

1. **Continuity measurement beyond PSNR-to-reference** (perceptual / no-reference temporal metric, compared with the
   input's own motion, plus visual examples of gap and post-bind frames). Without it, objection B1 has no answer.
2. **Cause and envelope of multi-hop recovery failure** (Sink-less duration vs repeated resets vs Sink / recent
   mismatch vs workload), at least for butterfly plus 1-2 other refresh-heavy clips with dog as control. This decides
   whether the paper states a bound ("recovers if the Sink binds within N calls") or only a limitation.
3. **Generality of M1:** at least one more model or resolution for resumption and the Sink-necessity result.
4. **Final-M3 end-to-end coverage:** closed by M3E (2026-10-20): the ExpD E / F / B configurations re-run with M3-v2
   plus two negative cases, all seven hypotheses supported (dog only; WX extends the inputs).
5. **A stronger baseline or a documented reason for its absence:** C/R blocked by driver and privileges (documented);
   a Sink pre-copy baseline is the reviewer-expected comparison for slow mobility.

Not gaps for this paper (decided): canonicalization (deferred), VACW adoption (NO-GO), Experiment T (paused - but see
objection B5).
