# Figure manifest (OSDI evaluation, 2026-10-16)

Status legend: **M** = generated from committed measurements (`results/evaluation/paper_figures/eval/`, script
`tools/eval/plot_paper_figures.py`, one `.meta.json` per panel); **E** = existing figure from an earlier script;
**MISSING** = needs an experiment that has not run. Level: GPU = real generation; net = network-level restoration
harness on the four physical hosts (fragment completion only). No panel plots model or analytical values as data.

Naming used in every panel (also in `POLICY` in the plotting script):
| name in figures | implementation | design component |
|---|---|---|
| Full migration | `full` (single handoff) | baseline |
| Cold restart | `cold` | baseline |
| Replay | `replay` (re-run the last chunks from the prompt) | baseline |
| OTTER (M1) | `ours` (immediate state first, Sink async) | M1 |
| Restart | `restart` | baseline |
| PP-Star | `pp_star` (keep fragments where they land, source sends the rest, no forwarding) | M2 without forwarding |
| Wavefront (M2) | `split` / `reuse_fixed` (keep verified fragments; newest holder forwards; source sends the rest) | M2 |
| Fixed line / tree / butterfly-like | `fixed_line`, `fixed_tree`, `fixed_butterfly` | fixed-topology baselines |
| OTTER (M2+M3, at moves) | `reuse_aware_in` (bottleneck-aware fragment-level provider assignment, re-planned at moves) | M2 + M3 assignment |
| OTTER (M2+M3, event-driven) | `reuse_dyn` (+ re-planning on measured changes with hysteresis) | M2 + M3 full (without placement) |
| Top-1 / Proportional placement | `--prepos top1 / proportional` | M3 proactive placement |
| Oracle | `direct` (GPU) / `--prepos oracle` (net) | upper bound |

Error bars: min-max over 3 repetitions unless stated; deterministic emulation gives spreads of 0.0-0.5 s, reported in
each meta file. GPU per-bandwidth points use median with p25-p75.

---

## F1. State composition and temporal sensitivity (RQ1)

| panel | status | content |
|---|---|---|
| F1a composition / requirements | E (`fig2a_state_composition`, `fig2a_state_requirements`) | bytes per component |
| F1b component-loss PSNR curves | E (`fig2b_state_ablation`) | PSNR vs chunk after one component withheld |
| F1c loss-by-component sweep | **M** `eval/F1c_loss_by_component_sweep` | 31 runs: Sink lost vs ephemeral lost |
| F1d frames | E (`fig3_state_loss_frames`) | qualitative |

- Hypothesis: only 2.67 MiB is needed to resume; the 1.61 GiB Sink determines the trajectory; the 4.41 GiB ephemeral
  state is reconstructible.
- Axes: F1c x = run (31), y = PSNR to the bit-exact reference (dB), 35 dB line.
- Baselines: uninterrupted same-seed execution (bit-exact reference).
- Independent: withheld component; clip, seed, prompt. Controlled: k = 2, migration chunk M, model, GPU.
- Metrics: PSNR (dB), SSIM; mean over 16 chunks after M (Sink), last 16 chunks (ephemeral).
- Data: `results/state_migration/prompt_sweep/summary.csv`, `gen/`, `mechanism/`.
- Missing: nothing for the claim; generalization beyond the 31 runs (other models) is not claimed.
- Variability: per-run points (no aggregation).
- Interpretation / claim: "losing the Sink KV leaves the stream on a different trajectory in 31/31 runs (18-27 dB);
  losing only ephemeral state heals above 35 dB in 21/21 runs without an adaptive refresh before M."
- Possible negative result (already measured): with a refresh before M, ephemeral-only loss heals in 5/10 runs; the
  claim must carry that condition.

## F2. Migration first output vs bandwidth (RQ2)

| panel | status | content |
|---|---|---|
| F2a first output vs bandwidth | **M** `eval/F2a_first_output_vs_bw` (GPU) | full / replay / cold / OTTER (M1) |
| F2b OTTER's three events vs bandwidth | **M** `eval/F2b_otter_events_vs_bw` (GPU) | first output, Sink verified, Sink bound |
| F2c external baselines | MISSING | requires the external baselines (see audit) |

- Hypothesis: first output is bandwidth-independent for OTTER (immediate state only) and scales with 6.02 GiB / B for
  full migration; Sink binding scales with 1.61 GiB / B.
- Axes: x = link bandwidth (0.25, 0.5, 1, 2.5, 5 Gbps, unshaped 9.4); y = seconds after the trigger (log).
- Baselines: full migration, cold restart, replay; MISSING: external C/R systems.
- Independent: bandwidth. Controlled: hosts elves-01 -> elves-02, clip/seed/k, migration chunk 30, MSS 1400.
- Metrics: first output (s), Sink verified (s), Sink bound (s); bytes moved.
- Data: `single_handoff/summary_by_policy_bw.csv`; 3 reps per point; p25-p75 bars.
- Claim: "OTTER resumes generation in 0.69-0.74 s at every bandwidth from 0.25 to 9.4 Gbps, 11-284x sooner than full
  migration; the Sink binds after 3.1-57.4 s, during which output continues."
- Negative results to report: cold restart's first output is faster (1.07 s) but diverges (19-22 dB); OTTER's output
  before bind is ~16 dB (F3), i.e. execution resumes before continuity.

## F3. Visual continuity and quality recovery timeline (RQ2, RQ7)

| panel | status | content |
|---|---|---|
| F3a PSNR timeline @1 Gbps | **M** `eval/F3a_continuity_timeline_1gbps` (GPU, 1 rep per policy) | events: first output 0.71, Sink verified 14.39, bound 14.78, >= 35 dB at 18.89 s |
| F3b rejoin vs bind delay | E (`fig4b_rejoin_vs_delay`, single GPU) | rejoin ~6 calls after bind for any delay |
| F3c timeline under repeated / degraded mobility | MISSING (Experiment D) | |

- Hypothesis: quality recovers a constant ~6 calls after bind, independent of when bind happens.
- Axes: x = time after trigger (s), y = PSNR (dB).
- Variability: F3a is one representative rep (others in F2b medians); F3c must report 3 reps with bands.
- Claim: "OTTER's stream rejoins the uninterrupted trajectory (>= 35 dB) 4.1 s after Sink bind at 1 Gbps."
- Negative: before bind OTTER's output is far from the reference (~16 dB); replay never rejoins (27-30 dB).

## F4. Restoration progress under repeated mobility (RQ3)

| panel | status | content |
|---|---|---|
| F4a Sink bound after the final move vs rho | **M** `eval/F4a_gpu_repeated_mobility_latency` (GPU) | restart, relay, pipelined relay, wavefront, oracle |
| F4b source / discarded Sinks vs rho | **M** `eval/F4b_gpu_repeated_mobility_bytes` (GPU) | |
| F4c continuous mobility, shared source | **M** `eval/F4c_continuous_mobility_shared_source` (net) | sessions restored k/N and source Sinks |
| F4d revisit | **M** `eval/F4d_revisit_restore` (net, Full E cond. 4) | 7.0 vs 14.0 s; 0.50 Sink still at B |
| F4e repeated mobility with M2+M3 on GPU | MISSING (Experiment D, scenarios B, G) | |

- Hypothesis: preserving verified progress removes discarded transfers; it reduces latency only where the binding
  resource is a shared sender or where the execution revisits a holder.
- Axes: F4a/F4b x = rho = T_s / T_m (0.5-8), y = seconds / Sinks; F4c x = sessions N (1-8); F4d bars per policy.
- Independent: rho, N, policy. Controlled: 1 Gbps caps, T_s = 14.05 s, fragment size 4 MiB.
- Claims: "Under a single-ingress destination, every non-oracle policy binds the Sink ~15 s after the final move;
  preservation's measured benefit there is bytes (0.03-0.07 vs up to 2.0 Sinks discarded)" (F4a/b); "with the source
  shared by N = 1-8 continuously moving sessions, restart restored no session within the run while the wavefront
  restored all" (F4c; within the run length, not an infinite-time claim); "on a revisit, the 0.50 Sink still at B
  halves the restore time" (F4d).
- Negative (measured, must be stated): H2's latency clause rejected on GPU (F4a); H3b (probe-rate adaptive) rejected.

## F5. Fixed topologies vs OTTER (RQ4)

| panel | status | content |
|---|---|---|
| F5a dissemination of one Sink to three nodes | **M** `eval/F5a_dissemination_topologies` (net) | star / line / tree / butterfly-like / OTTER assignment x 4 conditions |
| F5b restore at the final owner under mobility | **M** `eval/F5b_mobility_policies_latency` (net, Full E) | 7 policies x 4 conditions |
| F5c source Sinks under mobility | **M** `eval/F5c_mobility_policies_source_bytes` (net, Full E) | |
| D1 transfer graphs | design `design/D1_transfer_graphs` | schematics + measured assignment counts (B_f = 500) |

- Hypothesis: no fixed topology is best in every condition; fragment-level assignment matches or beats the best fixed
  one.
- Claims (with scope): "the best fixed plan changes with the bottleneck (multipath / star); OTTER's assignment is within
  1 % of the best fixed plan in three tested conditions and 9 % faster at 500 Mbps forwarders by sending 0.20 Sink more
  from the source" (F5a; four conditions, full grid not tested); "under execution mobility each fixed plan fails where
  its fixed provider is slow (tree 56.0 s, butterfly 52.5 s, line 62.8 s); OTTER at moves is never slower than the best
  fixed plan by more than 0.3 s except when a provider degrades after the plan (53.8 s), which event-driven re-planning
  removes (14.0 s)" (F5b).
- Frozen outcomes shown in the caption: H8a NOT SUPPORTED, H8b SUPPORTED, H8c NOT SUPPORTED AS WRITTEN.
- Negative: in shared-source and slow-B conditions restart / PP-Star are as fast as anything at a single destination
  when the source is idle (14.0 s); OTTER's advantage there is bytes.

## F6. Dynamic re-planning (RQ5)

| panel | status | content |
|---|---|---|
| F6a flow timeline into D, at-moves vs event-driven | **M** `eval/F6a_morphing_flow_timeline` (net, Full E cond. 3 rep 1) | flows per provider, cap change, re-plans, restoration |
| F6b event-driven vs at-moves across scenarios | **M** `eval/F6b_event_driven_vs_at_moves` (net, E-pilot v2) | no change / collapse / collapse+recovery / share change, re-plan counts |
| F6c per-fragment progress by provider | MISSING (needs node_D/fragments.csv from elves-04) | |
| F6d re-planning on GPU | MISSING (Experiment D, scenario F) | |

- Hypothesis: re-planning on measured throughput removes plan-once losses when conditions change, and does nothing
  when they do not.
- Claim: "with a forwarder collapsing mid-restoration, OTTER re-plans twice (0.7 s and 2.7 s after the change) and
  restores in 14.0 s instead of 53.8 s with 1.18 instead of 2.00 Sinks of source traffic compared with restart; with no
  change it makes no re-plan; at a source-share change it gains 10 % (41.6 -> 37.7 s)."
- Switching costs (table in text): transition 0.01-0.10 s, one 4 MiB fragment drained per re-plan, no duplicates,
  detection 0.7 / 2.7 s (two-stage, 2 s window).
- Negative: idle-provider recovery is not detected (no probing); the share-change gain sits just above the hysteresis
  threshold (dT 3.9-4.3 s vs 3.8-4.1 s).

## F7. Proactive placement (RQ6)

| panel | status | content |
|---|---|---|
| F7a correct vs incorrect predictions | **M** `eval/F7a_placement_correct_incorrect` (net, 1 rep per point) | none / oracle / top-1 / proportional x true destination |
| F7b value of a wrong placement vs holder egress | **M** `eval/F7b_wrong_placement_value_vs_holder` (net, diagnostic) | fixed vs OTTER |
| F7c budget x lookahead | MISSING (A1) | |
| F7d calibration | MISSING (A2) | |
| F7e interference with active restorations | partly measured (A3, H5d) - table, not yet a panel | |

- Hypothesis: correct placement removes the ingress-bound wait; incorrect placement keeps value only under a shared
  source with fast holders; bottleneck-aware routing prevents it from becoming harmful.
- Claims: "a correct top-1 placement of 0.71 Sink cuts restoration from 14.0 to 4.0 s; a wrong one costs nothing in
  source bytes (1.00 Sink) and the never-owner holder forwards it" (F7a); "with four sessions sharing the source, a
  wrong 0.5 Sink placement saves 27.7 s with fast holders, and costs 104 s under fixed forwarding from a 62.5 Mbps
  holder, which OTTER turns into a 3.3 s gain" (F7b, diagnostic).
- Frozen outcomes to state: H5d FAIL (+3.3 vs 3.5 s); H5e slow-holder aware clause FAIL by 0.2 s.
- Not claimed: a real predictor, budget/lookahead optimality.

## F8. GPU end-to-end streaming SLO (RQ7)

| panel | status | content |
|---|---|---|
| F8a output interval percentiles, single migration @1 Gbps | **M** `eval/F8a_output_interval_single_migration` (GPU) | p50/p95/p99/max of chunk-output intervals, 240 samples per policy |
| F8b TTFO / bind / rejoin per scenario A-G | MISSING (Experiment D) | |
| F8c decode-interval CDF, jitter, decode-deadline miss rate (proxy) | MISSING (Experiment D; needs t_decode logging) | descriptive only; no frame-delivery / SLO-compliance claim unless a consumer with defined delivery semantics is implemented (prereg v2, section 6) |
| F8d continuity coverage under repeated mobility | MISSING (Experiment D) | |
| F8e throughput (chunks/s) per scenario | MISSING (Experiment D) | |

- Hypotheses G1-G9 in `gpu_end_to_end_preregistration.md` (DRAFT v2, not yet frozen). Chunk completion, frame decode
  completion and frame delivery are distinct timestamps; only the first two are planned.
- F8a caution: one chunk = one model call; frame-level metrics need Experiment D's definitions.

## F9. Overhead and scalability (RQ8)

| panel | status | content |
|---|---|---|
| F9a restoration makespan vs concurrent sessions | **M** `eval/F9a_sessions_makespan` (net) | |
| F9b destination GPU memory | **M** `eval/F9b_destination_gpu_memory` (GPU) | 25.8-25.9 GiB for every policy |
| F9c steady-state overhead (no migration) | MISSING | fragment tracking + hashing vs unmodified |
| F9d control-plane / re-planning overhead | measured numbers (Phase 1: 0.28-0.32 s per plan; E-pilot v2 switching) - table | |
| F9e multi-session GPU | MISSING (Experiment D, scenario E) | |

---

## Prioritized missing experiments

1. **Experiment D on GPU** (F8b-e, F3c, F4e, F6d, F9e): port `reuse_aware_in`, `reuse_dyn`, pre-positioning and
   full / cold execution policies to the GPU harness; scenarios A-G (see the preregistration).
2. **External baselines** (F2c, F8): the two feasible systems from `external_baseline_audit.md`.
3. **Steady-state overhead** (F9c): OTTER enabled, no migration, vs unmodified generation.
4. **Copy back per-fragment logs** from elves-02..04 for the existing net runs (F6c) - no new runs.
5. **A1 reduced** (F7c): 11 (b, L) cells x {top-1, proportional, oracle, none} x 10 draws; and **A2** (F7d) - only
   if the paper keeps a placement-budget claim.
6. **B full grid** - only if the paper claims H6f beyond the four tested conditions.
