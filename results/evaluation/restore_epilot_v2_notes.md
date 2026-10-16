# Experiment E pilot v2: re-planner with corrected hysteresis, 21 runs (2026-10-15)

Changes relative to the v1 pilot (`restore_epilot`, kept unchanged), fixed before the run (TOPOLOGY_PLAN.md G.1
"E-pilot v2"): (1) a provider's capacity estimate is its latest valid throughput measurement and is kept while the
provider is idle (stale-flagged after one 2 s window) instead of reverting to the nominal cap; (2) the switch condition
is dT > C_switch + max(2.0 s, 0.10 x ETA_current). Scenarios: A1 forwarder collapse (as v1), A0 no-collapse control,
A2 collapse followed by recovery of C to 1 Gbps 5 s later, B source-share change at the 250 Mbps crossover; 3 reps.
Raw runs `restore_epilot_v2/`; tables `summary.csv`, `summary_by_config.csv`, `criteria.md`
(`tools/eval/aggregate_epilot.py --experiment restore_epilot_v2`).

## Run validity

21/21 valid: every fragment verified, no duplicates, paced egress within cap (A 997.7, B 476.5, C 390.9, D 249.1 Mbps
worst over 10 s; C's flows paced at 34-50 Mbps after each collapse), NIC receive peaks <= 1055 Mbps, four distinct hosts
on commit 85588c6. Cap changes fired at 21.1 s (collapse) and 26.0 s (recovery) in every applicable run. Rep spread
<= 0.1 s in every configuration (v1 had a 1.4 s outlier).

## Results (medians; T_r = final move -> all fragments verified at the owner)

| scenario | policy | T_r (s) | model | source Sinks | re-plans | premature | oscillations | detection (s) | transition (s) | drained / re-plan |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 collapse | reuse_dyn | **14.0** | 14.2 | 1.18 | 2 (every rep) | **0** | **0** | 0.7 then 2.7 | 0.02-0.07 | 4 MiB |
| A1 collapse (v1 pilot, same condition) | reuse_aware_in / restart / fixed | 53.3 / 14.0 / 80.2 | | 1.00 / 2.00 / 1.00 | | | | | | |
| A0 control | reuse_aware_in | 14.0 | 14.1 | 1.00 | - | | | | | |
| A0 control | reuse_dyn | **14.0** | 14.1 | 1.00 | **0** | 0 | 0 | - | - | - |
| A2 recovery | reuse_aware_in | 14.6 | 14.9 | 1.00 | - | | | | | |
| A2 recovery | reuse_dyn | **14.0** | 14.1 | 1.18 | 2 | 0 | 0 | 0.7 then 2.7 | 0.02-0.06 | 4 MiB |
| B share change | reuse_aware_in | 41.6 | 41.8 | 4.25 | - | | | | | |
| B share change | reuse_dyn | **37.7** | 38.1 | 4.18 | 1 (every rep) | 0 | 0 | - | 0.01-0.10 | 4-8 MiB |

Model error: max 0.49 s, median 0.15 s over the 21 runs (v1: 1.68 s max because of the oscillating rep).

## The eight questions

1. **Premature re-planning disappears: yes.** No re-plan before the cap change in any of the 9 collapse/recovery runs
   (v1: one in every run, dT 1.7-1.8 s against a 1.4 s threshold). The first re-plan now comes 0.7 s *after* the change,
   when the 2 s window already mixes pre- and post-collapse rates (C measured at 235 Mbps against 369-386 for A and B):
   dT 5.1-5.7 s, above the 2.44 s threshold. It moves about half of C's remaining fragments to the source; the second
   re-plan at 2.7 s after the change (C measured at 34-50 Mbps, dT 19.7-32.7 s) moves most of the rest. Two steps in
   the same direction, not a correction of the first: detection in two stages is the cost of a 2 s window, not an
   instability.
2. **Oscillation disappears: yes**, 0 in 21 runs (v1: 1 in 6 dyn runs). After the collapse re-plans C keeps 4-6
   fragments, so it stays active and measured at 34-50 Mbps; nothing moves back to it.
3. **Collapse recovery remains effective: yes.** T_r 14.0 s in every A1 rep (v1 median 14.0, outlier 15.4), equal to
   restart's 14.0 s with 1.18 instead of 2.00 Sinks from the source; move-only aware 53.3 s (v1 run, same condition).
4. **No-collapse behaviour stable: yes.** 0 re-plans in all three control reps; T_r 14.0 s and source 1.00 Sink,
   identical to move-only aware. The trigger is silent when nothing changes.
5. **Bandwidth recovery detected safely: not exploited, and not harmful.** When C recovers at 26 s, dyn has already
   moved its work to the source (which is as fast), so there is nothing to gain: 14.0 s against move-only aware's
   14.6 s (whose fragments at C benefit from the recovery). The last measurement of C (34-50 Mbps) is kept and nothing
   returns to C. Where the recovered provider were the only fast path this conservatism would cost time; that case is
   not in this pilot and the "keep the last measurement" rule is stated as a limitation.
6. **Source-share adaptation still improves latency: yes.** The re-plan fired in all three B reps (dT 3.9-4.3 s against a
   threshold of 3.8-4.1 s, borderline as predicted) and T_r is 37.7 s against 41.6 s for move-only aware (-10 %) and 40.0
   s for fixed forwarding (v1 run); source bytes 4.18 vs 4.25 Sinks; the other three sessions finish 1.0 s earlier than
   under move-only aware. The margin is thin: a 0.4 s smaller gain would have been (correctly) forgone as noise.
7. **Switching overhead**: transition 0.01-0.10 s (FLOW_ADD onto the source's running flow), one 4 MiB fragment drained
   per re-plan (8 MiB once), no duplicates, re-plan computation negligible (sub-millisecond, 412 fragments).
8. **Regressions against M2**: none in T_r in any scenario; the costs are 0.18 Sink of source traffic in the collapse
   scenarios and one drained fragment per re-plan.

## Reading for M3

The corrected trigger behaves as a system component should: silent when nothing changes, decisive on a large change
(two steps within 2.7 s), and just above noise on a small one. Its gains remain conditional on something changing
during a restoration: 39 s (and 0.82 Sink of source traffic saved relative to restart) when a forwarder collapses, 4 s
(10 %) when the source's share shifts at the crossover, 0 otherwise. The mechanism is M2's assignment rule re-run on
measured state while all verified fragments stay where they are; nothing in these runs required a topology
abstraction. Open limitation: an idle provider's recovery is not observed (no probing).

## Next (not run)

Full Experiment E under the frozen H8a-c (slow-B, shared-source, C-degradation and revisit conditions with restart,
progress-preserving star, line, tree, butterfly-like, aware-at-moves, dynamic), then the M3 decision and GPU (D).
