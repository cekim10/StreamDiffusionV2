# Experiment E pilot: event-driven re-planning vs re-planning at moves, 21 runs (2026-10-15)

Mechanism, scenarios, parameters and model predictions were recorded before the run (TOPOLOGY_PLAN.md G.1 "E-pilot").
`reuse_dyn` = `reuse_aware_in` at moves + every 0.5 s a re-assignment of the bottleneck provider's remaining fragments
when the measured-ETA gain exceeds the switching cost (0.3 s + one fragment drain) plus a 1 s margin and 10 % of the
current ETA, with a 2 s warm-up after any plan. The planner sees measured throughput (2 s window), its own queue and
fragment availability; the live cap change is never revealed to it. Raw runs `restore_epilot/`; tables `summary.csv`,
`summary_by_config.csv`, `criteria.md` (`tools/eval/aggregate_epilot.py --experiment restore_epilot`).

## Run validity

21/21 valid: every fragment verified; paced egress within the (larger of initial and final) cap over every 10 s window
(A 998.2, B 477.3, C 249.1, D 250.0 Mbps worst; C's post-collapse flows paced at 50-62 Mbps per events.csv); NIC
receive peaks <= 1051 Mbps; four distinct hosts on commit 7d759dd; no duplicates in any run. The cap change fired at
21.1-21.2 s in every scenario-A run (D held 50 % 7.1 s after the final move at 14.0 s). Rep spread: <= 0.5 s except
`reuse_dyn` scenario A rep 3 (15.4 s vs 14.0 s, see oscillation below).

## Scenario A: forwarder collapse (single session, A -> B -> C -> D at rho 2; C's egress 1 Gbps -> 62.5 Mbps when D holds 50 %)

| policy | T_r at D (s) | model | source Sinks | re-plans | detection (s) | transition (s) | drained per re-plan |
|---|---|---|---|---|---|---|---|
| restart | **14.0** | 14.1 | 2.00 | - | - | - | - |
| reuse_fixed | 80.2 | 81.8 | 1.00 | - | - | - | - |
| reuse_aware_in (M2) | 53.3 | 53.9 | 1.00 | - | - | - | - |
| reuse_dyn (M3 candidate) | **14.0** (14.0 / 14.0 / 15.4) | 14.2 | 1.18 | 2 / 2 / 4 (model 1) | 0.24 then 2.26 | 0.04-0.07 | 4 MiB (one fragment) |

Reading. The collapse hits only the forwarding paths, so restart (source idle, 1 Gbps to D) is the best policy here by
construction; the dynamic rule reaches the same 14.0 s while sending 1.18 Sinks from the source instead of 2.00, and
move-only aware pays 53.3 s (its plan keeps 0.25 Sink on the collapsed C), fixed forwarding 80.2 s. Measured switching
costs: transition 0.04-0.07 s (the moved fragments join the source's existing flow with FLOW_ADD, so no connection
setup); one 4 MiB fragment drained from the cancelled flow per re-plan; no duplicates. Detection of the collapse took
2.26 s, i.e. the 2 s measurement window plus one check period, as designed.

Two deviations from the model, both about hysteresis: (i) every run re-planned once *before* the collapse was visible
(t = 21.3-21.4 s, measured rates still 352 / 352 / 302 Mbps): a marginal re-balance with dT = 1.7-1.8 s against a
threshold of C_switch + eps = 1.41 s, which the model (perfect rates, no measurement noise) did not make; (ii) rep 3
oscillated: after the collapse re-plan it moved 35 fragments *back* to C at 26.4 s (dT 1.7 s, C's estimate then came
from the nominal cap because C was idle) and had to move 31 of them to the source again at 28.4 s, costing 1.4 s
(15.4 vs 14.0 s). Net effect on T_r in reps 1-2: none; in rep 3: +1.4 s. The idle-provider capacity estimate
(nominal cap) is the identified weakness: a provider that was just measured slow should keep that measurement for a
while instead of reverting to nominal.

## Scenario B: source share change at the crossover (N = 4, holders 250 Mbps, 0.5 Sink wrongly at B, destination C)

| policy | T_r (s) | model | others' makespan | source Sinks | re-plans | transition | drained |
|---|---|---|---|---|---|---|---|
| reuse_fixed | 40.0 | 40.2 | 58.6 | 4.00 | - | - | - |
| reuse_aware_in (M2) | 41.6 | 41.8 | 62.0 | 4.25 | - | - | - |
| reuse_dyn (M3 candidate) | **37.9** | 38.4 | 61.1 | 4.18 | 1 (model 1) | 0.00-0.07 s | 4 MiB |

Reading. At the crossover the move-time plan over-assigns the source (0.25 Sink moved from B to A, the 1.6 s regression
of the holder diagnostic). As the other sessions' flows finish, the measured source rate stays at 235-252 Mbps while
B's forwarding runs at 252 Mbps with less remaining; one re-plan at 16.8 s moves 26-28 fragments from the source back
to B (dT 3.5-4.0 s against C_switch 0.44 + 1 s). Result: 3.8 s (9 %) below move-only aware and 2.1 s below fixed
forwarding, with 0.07 Sink less source traffic than move-only aware; the other three sessions finish 0.9 s earlier than
under move-only aware and 2.5 s later than under fixed (whose session sends nothing extra from the source). One
re-plan, no oscillation, no duplicates.

## Model agreement

T_r within 0.2 s of the model in 20 of 21 runs (median 0.19 s); the exception is the oscillating rep (1.68 s). The model
reproduces every static policy and the re-plan that matters in each scenario, and misses the marginal pre-collapse
re-plan because it has no measurement noise.

## Regressions against M2

None in T_r (every dyn run is faster than or equal to move-only aware). Costs: +0.18 Sink of source traffic in
scenario A (retransmission that buys 39 s), one 4 MiB drain per re-plan, 2-4 re-plans where one was needed, and one
oscillation out of six dyn runs.

## Does this justify a separate M3?

- The large gain (53.3 -> 14.0 s) is a stress test of a forwarder collapse, and restart achieves the same time; the
  dynamic rule's distinctive contribution there is reaching restart's latency at 1.18 instead of 2.00 Sinks of source
  traffic, i.e. preserving progress *and* escaping the collapsed path.
- The small gain (41.6 -> 37.9 s, 9 %) is the realistic case: a plan-once decision at the crossover corrected once
  the shares were measured. It is above the switching cost by an order of magnitude but modest in absolute terms.
- The mechanism is M2's assignment rule run again on measured state, not a topology optimizer. On this pilot it is
  defensible as "event-driven continuity re-planning" inside M3 (with budgeted pre-positioning) provided (a) the
  idle-provider estimate is fixed to avoid oscillation and (b) its benefit is reported as conditional: large only when a
  forwarder degrades mid-restoration, a few seconds when contention shifts, zero when nothing changes (no re-plans
  are triggered then, by construction of the threshold). Whether such changes are frequent enough in practice is not a
  question this testbed can answer; the paper must say so.

## Follow-ups (not run)

- Hysteresis fix: keep a slow measurement as the capacity estimate of an idle provider for the measurement window
  (or longer) instead of reverting to the nominal cap; re-run scenario A rep 3's condition.
- Full E (frozen H8a-c): slow-B, shared-source and C-degradation conditions with restart, star, line, tree,
  butterfly-like, aware-at-moves, dynamic; only after the hysteresis fix.
