# Experiment 3 Scenario B: source-egress contention, v2 (2026-10-14)

72 runs: N in {1, 2, 4, 8} sessions x {restart, reuse_fixed, reuse_adaptive} x {one move, continuous mobility} x 3 reps.
Network-level harness (no GPU), real Sink size (1.61 GiB, 412 x 4 MiB fragments), MSS-capped TCP, per-fragment SHA-256.
A = elves-01 is every session's source; sessions live on B, C, D (elves-02..04) and move every T_m = 7.02 s (rho = 2).
Every node's egress and ingress capped at 1 Gbps, shared max-min fairly by all flows. Design, predictions and criteria
were committed before any run (EXPERIMENT_PLAN.md, Scenario B); the harness fixes between v1 and v2 are listed there.
Raw runs: `restore_contention_v2/policy=*`; tables `summary.csv`, `summary_by_config.csv`; verdicts `criteria.md`;
figures `figures/figE6_makespan_vs_N`, `figE7_source_bytes_vs_N`, `figE7b_coverage_vs_N` (tools/eval/aggregate_restore.py).

## Run quality

72/72 valid: every fragment verified; each node's paced payload within 1.05 x cap in every 10 s window (worst A 1002,
B 830, C 901, D 858 Mbps); kernel NIC receive peak 1105 Mbps at most (no outside traffic this time); the early
rate/cancel path never triggered. Results agree with the v1 run to within 0.6 s.

## Results (medians of 3)

One move, then stay (makespan = time until every session is restored at its final edge):

| N | restart | reuse_fixed | reuse_adaptive | restart - fixed | relative |
|---|---|---|---|---|---|
| 1 | 21.0 s | 21.0 s | 21.1 s | 0.0 s | 0 % |
| 2 | 36.6 s | 29.0 s | 31.5 s | 7.6 s | 21 % |
| 4 | 65.1 s | 55.5 s | 57.4 s | 9.7 s | 15 % |
| 8 | 121.0 s | 110.8 s | 112.1 s | 10.2 s | 8 % |

Source bytes per session: restart 1.50 / 1.32 / 1.17 / 1.09 Sinks, reuse_fixed 1.00 at every N, reuse_adaptive
1.17 / 1.09 / 1.04 / 1.01.

Continuous mobility over B -> C -> D -> B (run length 2 N T_s + 2 T_m):

| N | restart restored | reuse_fixed restored, makespan | reuse_adaptive restored, makespan | coverage fixed / adaptive |
|---|---|---|---|---|
| 1 | 0 of 1 | 1 of 1, 28.1 s | 1 of 1, 28.1 s | 0.00 / 0.00 |
| 2 | 0 of 2 | 2 of 2, 50.1 s | 2 of 2, 58.0 s | 0.18 / 0.10 |
| 4 | 0 of 4 | 4 of 4, 59.0 s | 4 of 4, 75.2 s | 0.51 / 0.40 |
| 8 | 0 of 8 | 8 of 8, 118.4 s | 8 of 8, 144.8 s | 0.51 / 0.43 |

Source bytes per session under continuous mobility: restart 3.01 / 2.53 / 2.28 / 2.15 Sinks (all discarded),
reuse_fixed 1.00, reuse_adaptive 1.70 / 1.67 / 1.36 / 1.30.

## Verdicts (pre-registered criteria)

- H3a, one move: supported at N = 2, 4, 8 (gaps 7.6, 9.7, 10.2 s >= 3.5 s); not at N = 1 (0.0 s), as predicted.
- H3a, continuous: supported at every N: restart restored no session in any rep, reuse_fixed restored all sessions in
  all reps.
- H3b: not supported. reuse_adaptive was never better than reuse_fixed and was worse at N = 2, 4, 8.

## Reading

1. With one move, reuse helps exactly by the source time already invested before the move. Restart must resend what
   it delivered to the abandoned edges; reuse sends every byte from the source once. The absolute saving is 7.6-10.2 s
   (T_m to 1.5 T_m) at every N >= 2 and shrinks relatively as N grows (21 % -> 8 %), because each session's pre-move
   progress shrinks as the source is shared by more sessions. This matches the flow model written before the run.
2. With N = 1 the edge's 1 Gbps ingress, not the source, is the bottleneck (as in Phase 1), so reuse cannot help.
3. Under continuous mobility restart livelocks: each ownership period delivers at most S / (N rho) < S, which is
   discarded at the next move, so no session is ever restored while the source keeps sending 2-3 Sinks per session.
   Reuse accumulates progress across edges and restores every session; at N >= 4 its makespan is within 5 % of the
   source-bound N T_s (59.0 vs 56.2 s, 118.4 vs 112.4 s). At N = 1, 2 the makespan is about 2 N T_s because the bottleneck
   moves from the source to the receiving edge, which must collect each Sink from several holders through one ingress.
4. Coverage (share of the run in which the current edge holds the whole Sink) reaches 0.51 at N = 4, 8 within the run
   length used; it is bounded by the run length, not a steady-state value.
5. Adaptive provider selection loses because its estimate is myopic: it compares the rate a new flow would get from the
   source now against a holder's rate, and sends some held fragments from the source. With the source as the shared
   bottleneck those bytes delay every other session (source bytes 1.30-1.70 Sinks per session under continuous mobility
   vs 1.00 for fixed routing).

## What this means for the design

- The defensible mechanism is progress preservation with a simple rule: never send from the source what a holder
  already has, and send everything else from the source exactly once. That rule (reuse_fixed) is optimal for source
  bytes and is never beaten by the adaptive variant in this scenario.
- Its latency value is conditional: zero when the receiving edge's ingress binds (single session, Phase 1), a constant
  T_m-scale saving when the source is shared and mobility stops, and the difference between never and always restoring
  when mobility continues faster than the per-session source share allows (N rho > 1).
- Adaptive source selection has not shown any benefit. It should not be presented as a contribution unless a scenario
  with heterogeneous holder links (Step 2: slow or contended holders) shows a gain.
