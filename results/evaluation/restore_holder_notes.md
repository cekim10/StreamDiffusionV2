# Experiment 3 Step 2: heterogeneous holder bandwidth (2026-10-14)

180 runs: N in {1, 2, 4} x holder egress B_h in {62.5, 125, 250, 500, 1000} Mbps x {restart, reuse_fixed,
reuse_adaptive, reuse_aware} x 3 reps; one move per session; source A egress and every ingress 1 Gbps; rho = 2.
Design, fluid-model predictions and criteria were committed before the run (EXPERIMENT_PLAN.md, "Experiment 3 Step 2").
Raw runs `restore_holder/policy=*_bh=*`; tables `summary.csv`, `summary_by_config.csv`; verdicts `criteria.md`;
figures `figures/figE8_makespan_vs_bh_N{1,2,4}`, `figE9_source_vs_bh_N{1,2,4}` (tools/eval/aggregate_holder.py).

## Run quality

180/180 valid: every fragment verified; paced egress within cap in every 10 s window (source worst 998.5 Mbps; edges at
most 1.02 x B_h); kernel NIC receive peaks at most 1074 Mbps; four distinct hosts; no early rate/cancel events.
Rep spread is 0.0-0.5 s at every configuration. The fluid model (restore_model.py) matches every median makespan
within 0.99 s (median 0.14 s) and every source-bytes figure within 0.1 Sink.

## Results (medians of 3; makespan s / source Sinks per session)

| N | B_h (Mbps) | restart | reuse_fixed | reuse_adaptive | reuse_aware |
|---|---|---|---|---|---|
| 1 | 62.5 * | 21.0 / 1.50 | 118.3 / 1.00 | 21.1 / 1.44 | 21.1 / 1.44 |
| 1 | 125 * | 21.0 / 1.50 | 62.8 / 1.00 | 21.0 / 1.40 | 21.0 / 1.39 |
| 1 | 250 * | 21.0 / 1.50 | 35.1 / 1.00 | 21.0 / 1.33 | 21.0 / 1.30 |
| 1 | 500 | 21.0 / 1.50 | 21.2 / 1.00 | 21.1 / 1.25 | 21.1 / 1.17 |
| 1 | 1000 | 21.0 / 1.50 | 21.0 / 1.00 | 21.1 / 1.17 | 21.1 / 1.00 |
| 2 | 62.5 * | 36.6 / 1.32 | 92.8 / 1.00 | 35.3 / 1.26 | 34.2 / 1.21 |
| 2 | 125 * | 36.6 / 1.32 | 50.9 / 1.00 | 34.5 / 1.22 | 31.7 / 1.12 |
| 2 | 250 | 36.6 / 1.32 | 29.8 / 1.00 | 33.4 / 1.17 | 29.0 / 1.01 |
| 2 | 500 | 36.6 / 1.32 | 29.0 / 1.00 | 32.2 / 1.12 | 29.0 / 1.00 |
| 2 | 1000 | 36.6 / 1.32 | 29.0 / 1.00 | 31.5 / 1.09 | 29.0 / 1.00 |
| 4 | 62.5 * | 65.1 / 1.17 | 84.4 / 1.00 | 63.1 / 1.14 | 57.3 / 1.03 |
| 4 | 125 | 65.2 / 1.17 | 55.5 / 1.00 | 61.8 / 1.11 | 55.5 / 1.00 |
| 4 | 250 | 65.2 / 1.17 | 55.4 / 1.00 | 59.7 / 1.08 | 55.5 / 1.00 |
| 4 | 500 | 65.2 / 1.17 | 55.5 / 1.00 | 58.2 / 1.05 | 55.5 / 1.00 |
| 4 | 1000 | 65.2 / 1.17 | 55.5 / 1.00 | 57.4 / 1.04 | 55.5 / 1.00 |

\* pre-registered crossover set C (model: reuse_fixed slower than restart).

## Verdicts (pre-registered criteria)

- P0 (crossover exists): holds in all six C conditions. Restart beats unconditional reuse by 14-97 s (N = 1),
  14-56 s (N = 2) and 19 s (N = 4, 62.5 Mbps). Unconditional reuse is not a generally optimal policy.
- H4a (heterogeneity benefit, aware <= 0.85 fixed in C): holds in all six; ratios 0.18 / 0.33 / 0.60 (N = 1),
  0.37 / 0.62 (N = 2), 0.68 (N = 4).
- H4b (no regression): holds everywhere. Outside C, aware equals fixed to within 0.1 s; everywhere aware is within
  0.1 s of, or better than, restart.
- H4c (source efficiency): **fails at (N = 1, B_h = 500)**. Aware sends 1.17 Sinks per session from the source
  (fixed: 1.00) while finishing at the same time (21.1 vs 21.2 s). All other 14 conditions pass; everywhere aware sends
  fewer source bytes than restart.
- Outcome mapping: Case 1 (bottleneck-aware provider selection + progress preservation), qualified by the H4c failure.

## Reading

1. The crossover is real and large. With one session and a 62.5 Mbps holder, forwarding the held half of the Sink
   takes 111 s while the idle source could resend it in 7 s; unconditional reuse costs 97 s. The condition for a
   crossover is f S / B_h > (bytes the source still owes all sessions) / B_src, which with a shared source becomes
   rarer as N grows: it needs B_h <= 250 Mbps at N = 1, <= 125 at N = 2, 62.5 at N = 4, and nothing in this grid at
   N = 8 (model). Scenario B (B_h = 1 Gbps) was entirely in the no-crossover regime, which is why fixed reuse was
   optimal there.
2. Where aware adds value beyond "take the better of restart and fixed": N = 2 and N = 4 in C. At N = 2, 125 Mbps it is
   13 % faster than restart and 38 % faster than fixed by sending 0.12 Sink from the source and the rest from the
   holder; at N = 4, 62.5 Mbps (both the source and the forwarding edges congested, each edge forwarding for more than
   one session) it is 12 % / 32 % faster with only 0.03 Sink of retransmission. At N = 1 it only ties restart: the
   destination's ingress bounds everything at T_m + T_s = 21 s.
3. The H4c failure is the rule's blind spot, not noise (3 reps identical, model predicted 1.18). Aware balances the
   egress backlogs of the source and the holder, but at N = 1 the binding resource is the destination's ingress, so
   fragments moved to the source shorten nothing. A corrected rule would move a fragment off a holder only when the
   holder's estimated finish exceeds the ingress-bound finish (bytes still to deliver to the owner / its ingress cap)
   as well as the source's; this is not implemented and not claimed. At B_h = 1000 the same rule already sends 1.00.
4. The Scenario B adaptive rule (probe-rate, per-session load) is worse than aware everywhere at N >= 2 and sends more
   source bytes in every condition. In C it beats fixed but never matches aware, because it under-weights the source's
   backlog from other sessions: its estimate of the source is the max-min share of one new flow, not the time until the
   source has drained everyone's queue.

## What this means for the design

- Progress preservation stays the primary mechanism; provider selection is a second, conditional one. The sentence
  to defend: fragments held at the previous edge should be forwarded from there unless the holder's egress backlog would
  outlast the shared source's; the comparison must use whole-node backlogs, not per-flow rates.
- The latency gain of provider selection is bounded by min(restart, fixed) at N = 1 (ingress-bound) and reaches
  12-13 % below the better baseline at N = 2 and 4 only when holders are 8-16 x slower than the source.
- Report the H4c failure with the fix sketched above; do not describe the rule as source-optimal.
