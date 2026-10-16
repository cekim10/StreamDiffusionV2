# Full Experiment E: seven policies under execution mobility, 84 runs (2026-10-16)

Design, policy semantics, fairness rules, the 28 model predictions and the pre-run expectation for the frozen clauses
were committed before the run (TOPOLOGY_PLAN.md G.1 "Full E"; criteria H8a-c in F, frozen 2026-10-15). Policies:
restart; pp_star (progress-preserving star: nothing dropped, the owner keeps what it holds, source sends the rest, no
forwarding); fixed_line (previous owner forwards); fixed_tree (first edge visited forwards); fixed_butterfly (every
past holder forwards, even split by count); reuse_aware_in (M2); reuse_dyn (M3 candidate). Conditions: (1) slow-B
(B egress 125 Mbps), single session B -> C -> D at rho 2; (2) shared source, N = 4, two moves each; (3) C degradation
(C egress 1 Gbps -> 62.5 Mbps when D holds 50 %); (4) revisit B -> C -> D -> B. 3 reps. Raw runs `restore_fulle/`;
tables `summary.csv`, `summary_by_config.csv`, `criteria.md` (`tools/eval/aggregate_fulle.py --experiment restore_fulle`).

## Run validity

84/84 valid: every fragment verified, no duplicates, paced egress within cap over every 10 s window, NIC receive peaks
within 1.15 x cap, four distinct hosts on commit 55c3a07, every session restored in every run. Rep spread <= 0.1 s in
every configuration. Model error: max 0.70 s, median 0.17 s over 84 runs (source bytes within 0.02 Sink).

## Results (medians; T_r = final move -> restored at the final owner; Sinks per session)

| condition | restart | pp_star | fixed_line | fixed_tree | fixed_butterfly | aware (M2) | dyn (M3) |
|---|---|---|---|---|---|---|---|
| 1 slow-B: T_r at D | 14.0 | 14.0 | 14.0 | 56.0 | 52.5 | **14.0** | **14.0** |
| source / total | 2.00 / 2.00 | 2.00 / 2.00 | 1.44 / 2.01 | 1.44 / 2.01 | 1.00 / 2.01 | 1.38 / 2.01 | 1.38 / 2.01 |
| 2 shared source: T_r (median of 4) | 54.6 | 54.6 | 38.7 | 45.7 | **38.4** | 38.7 | 38.8 |
| source / total | 1.30 / 1.30 | 1.30 / 1.30 | 1.00 / 1.48 | 1.13 / 1.48 | 1.00 / 1.48 | 1.00 / 1.48 | 1.00 / 1.48 |
| 3 C degradation: T_r at D | 14.0 | 14.0 | 62.8 | 14.0 | 53.2 | 53.8 | **14.0** (2 re-plans) |
| source / total | 2.00 / 2.00 | 2.00 / 2.00 | 1.25 / 2.01 | 1.25 / 2.01 | 1.00 / 2.01 | 1.00 / 2.01 | 1.18 / 2.01 |
| 4 revisit: T_r at B | 14.0 | **7.0** | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 |
| source / total; held at B on return | 2.51 / 2.51; 0 | 2.00 / 2.00; 0.50 | 1.50 / 2.01; 0.50 | 1.51 / 2.01; 0.50 | 1.00 / 2.01; 0.50 | 1.00 / 2.01; 0.50 | 1.00 / 2.01; 0.50 |

No intermediate owner is restored before being left in any condition (T_m = 7 s < T_s), so the per-period latencies
are defined only at the final owner; the intermediate periods' effect is in the bytes and in the final T_r.

## Frozen verdicts (thresholds unchanged)

| clause | measured | verdict |
|---|---|---|
| H8a slow-B: aware <= 0.75 x best fixed forwarding plan and within 1 s of star, no fixed plan beats it by > 1 s | aware 14.0, best forwarding (line) 14.0, star 14.0; none beats aware | **not supported**, as predicted before the run |
| H8b C degradation: dynamic <= 0.5 x aware with <= 2 re-plans, never worse than aware by > 1 s elsewhere | dyn 14.0 vs aware 53.8 (0.26 x), 2 re-plans; elsewhere dyn - aware = 0.0 / +0.1 / 0.0 s | **supported** |
| H8c shared-source and revisit: every progress-aware policy sends >= 0.25 Sink less from the source than restart and none is Pareto-dominated by restart | shared source: pp_star 1.30 = restart 1.30 (fails the 0.25 clause); line/tree/butterfly/aware/dyn 1.00-1.13 (pass); revisit: all 1.00-2.00 vs 2.51 (pass); none dominated by restart | **not supported** as written |

Reading of the two failures. H8a fails because its premise was wrong, not aware: at the final owner D the fixed line
forwards from the fast previous owner C, so line, star and aware all reach the ingress bound (14.0 s); D.3 had already
predicted "aware = line = star at D" and the clause was written inconsistently with it. The slow holder hurts the plans
that forward *from B* at D: tree (56.0 s) and butterfly (52.5 s). Aware's actual edge over line here is 0.06 Sink less
source traffic, nothing in time. H8c fails on one policy in one condition: pp_star preserves fragments but, without a
revisit, cannot use them (nobody forwards), so it equals restart in bytes (1.30) and time; every forwarding policy
sends 0.17-0.30 Sink less than restart in the shared-source condition and 0.5-1.5 Sinks less on the revisit path. The
clause bundled pp_star with the forwarding policies; the data separate them.

## The three comparisons the experiment was designed for

1. **Restart vs progress-preserving (is progress worth keeping?)** Yes, in two distinct ways. On the revisit path
   every progress-preserving policy restores B in 7.0 s against restart's 14.0 s because 0.50 Sink is still at B (even
   pp_star, with no forwarding at all). Under a shared source the forwarding policies restore in 38.4-38.7 s against
   restart's 54.6 s with 1.00 instead of 1.30 Sinks from the source. With one session and fast links (conditions 1 and
   3) restart is as fast as anything (14.0 s) because the idle source saturates the destination's ingress; it just
   sends 2.0 Sinks instead of 1.0-1.4. Restart is Pareto-dominated in conditions 1, 3 and 4 and on the frontier only in
   condition 2 by having a trivially different total (its own 1.30 against the forwarding plans' 1.48).
2. **Fixed plans vs aware-at-moves (is bottleneck awareness needed?)** Under execution mobility the fixed plans fail
   exactly where their fixed provider is the slow one: tree (hub B) at 56.0 s and butterfly at 52.5 s in slow-B, line
   at 62.8 s under C's degradation (its only provider is C), tree at 45.7 s under a shared source. No fixed plan is
   good in all four conditions; aware-at-moves is never slower than the best fixed plan by more than 0.3 s in
   conditions 1, 2 and 4, and ties restart's time in 1 while sending 1.38 Sinks. Its one weakness is condition 3, where
   its plan at the move keeps 0.25 Sink on the provider that collapses afterwards (53.8 s): a plan-once limitation, the
   question of comparison 3.
3. **Aware-at-moves vs dynamic (is reacting between moves worth it?)** Only where something changes between moves.
   Condition 3: 53.8 -> 14.0 s with two re-plans (0.7 s and 2.7 s after the collapse), equal to restart's time at 1.18
   instead of 2.00 Sinks; everywhere else the dynamic rule made no re-plan and matched aware within 0.1 s (no
   regression, H8b's second clause). Fixed tree happens to reach 14.0 s in condition 3 because its hub B is not the
   collapsing node; that is luck of the topology, not adaptation (it pays 56.0 s in condition 1).

## Pareto frontiers (T_r, source Sinks, total Sinks; ties within 0.2 s / 0.01 Sink do not dominate)

- slow-B: frontier {butterfly (slow but 1.00 Sink), aware, dyn}; restart, pp_star, line, tree dominated.
- shared source: frontier {restart and pp_star (lowest total, 1.30, because they forward nothing), butterfly}; line,
  aware, dyn dominated by butterfly only through its 0.3 s edge (38.4 vs 38.7 s) at equal bytes.
- C degradation: frontier {butterfly, dyn}; restart, pp_star, line, tree, aware dominated.
- revisit: frontier {butterfly, aware, dyn}; restart, pp_star, line, tree dominated.
The dynamic rule is on the frontier in all four conditions; aware-at-moves in three; no fixed plan in more than three.

## Structural vs stress-test gains

Structural (hold whenever the pattern occurs): progress reuse on a revisit (7.0 vs 14.0 s, measured with 0.50 Sink
still at B); source offload under contention (38.4-38.7 vs 54.6 s, 1.00 vs 1.30 Sinks); bottleneck-aware assignment
avoiding a slow fixed provider (14.0 vs 52.5-56.0 s in slow-B). Stress-test specific: the 39.8 s gain of dynamic
re-planning in condition 3 depends on a forwarder collapsing mid-restoration; its structural content is that the
re-planner reaches restart's time while preserving progress (1.18 vs 2.00 Sinks) and costs nothing when nothing
changes (0 re-plans, +0.1 s worst case, in the other three conditions).

## Implications for M3

The data support M2 as the primary mechanism (progress preservation + bottleneck-aware assignment: never beaten by a
fixed plan by more than 0.3 s, Pareto-efficient in three of four conditions) and the dynamic re-planner as a
conditional addition: it removes M2's only measured weakness (plan-once under a mid-restoration change) without a
measurable cost elsewhere, but its large gain is confined to that case. Nothing in Full E required a topology
abstraction; the fixed topologies serve as baselines that each fail in some condition. The frozen H8a and H8c
failures are failures of clause premises (line is as good as aware at the final owner of slow-B; pp_star is not a
forwarding policy), and are reported as such without changing the thresholds.
