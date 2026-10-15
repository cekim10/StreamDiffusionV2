# Experiment A pilot: prediction-aware pre-positioning, 12 runs (2026-10-15)

Session s0 executes at source A; candidates B, C, D with p = (0.6, 0.3, 0.1); lookahead L = 10 s; budget b = 1 Sink;
1 Gbps egress and ingress caps everywhere; restoration policy `reuse_aware_in`; pre-positioning policies none /
oracle / top-1 / proportional; the true destination fixed to B, C and D in turn (one draw each; B = correct prediction,
C and D = incorrect). Design, allocation definitions and the model table were written before the run
(TOPOLOGY_PLAN.md D.1, G step 2, G.1). Raw runs `restore_prepos_pilot/policy=reuse_aware_in_*_pp=*`; tables and checks
`restore_prepos_pilot/{summary.csv, summary_by_config.csv, criteria.md}` (`tools/eval/aggregate_prepos.py`).

## Run validity

12/12 valid: every fragment verified; paced egress within cap over every 10 s window (A 989 Mbps worst; B 789, C 302,
D 101 Mbps, i.e. forwarding by the candidates); kernel NIC receive peaks <= 1048 Mbps; four distinct hosts; no early
rate/cancel events. The move fired at 10.00-10.01 s in every run. Pre-positioning traffic is accounted separately
from post-move traffic (`sent_before_move_sinks`, `verified_at_move_sinks` vs `post_move_source_sinks`,
`forwarded_by_nonowner_holders_sinks`); no other session existed, so interference is zero by construction here (A3
measures it with N = 4).

## Results (T_r = move -> all fragments verified at the destination; Sinks per session)

| prepos | true dest | prediction | T_r (s) | model (s) | verified at move B / C / D | forwarded by non-owner holders | post-move source | source total | total traffic |
|---|---|---|---|---|---|---|---|---|---|
| none | B / C / D | - | 14.03 / 14.00 / 14.01 | 14.14 | 0 / 0 / 0 | 0 | 1.00 | 1.00 | 1.00 |
| oracle | B / C / D | - | 3.99 / 4.00 / 4.00 | 4.14 | 0.71 at the destination | 0 | 0.29 | 1.00 | 1.00 |
| top-1 | B | correct | 3.99 | 4.14 | 0.71 / 0 / 0 | 0 | 0.29 | 1.00 | 1.00 |
| top-1 | C | incorrect | 14.01 | 14.14 | 0.71 / 0 / 0 | **0.72** (B -> C) | 0.29 | 1.00 | 1.72 |
| top-1 | D | incorrect | 14.02 | 14.14 | 0.71 / 0 / 0 | **0.72** (B -> D) | 0.29 | 1.00 | 1.72 |
| proportional | B | correct | 8.00 | 8.18 | 0.42 / 0.22 / 0.07 | 0.29 (C, D -> B) | 0.28 | 1.00 | 1.29 |
| proportional | C | incorrect | 10.95 | 11.12 | 0.42 / 0.22 / 0.07 | 0.50 (B, D -> C) | 0.29 | 1.00 | 1.50 |
| proportional | D | incorrect | 12.98 | 13.12 | 0.42 / 0.22 / 0.07 | 0.65 (B, C -> D) | 0.28 | 1.00 | 1.65 |

## Go/no-go (pre-registered checks, `criteria.md`)

- T_r within 1 s of the model in every run: pass (largest deviation 0.18 s; the model's +0.3 s control-plane
  allowance is ~0.15 s pessimistic).
- Per-candidate verified bytes at the move within 0.05 Sink of the model allocation: pass (largest 0.01).
- Incorrect predictions: the non-chosen holders forwarded their verified fragments to the destination in every such
  run (0.72 Sink for top-1, 0.50-0.65 for proportional); the forwarding path through never-owner holders works.
- Source bytes exactly 1.00 Sink in every run: pre-positioned fragments are never resent by the source.
- **Verdict: GO** for the A sweeps.

## Correct vs incorrect prediction

- Correct (top-1 -> B, oracle): T_r drops from 14.0 s to 4.0 s, exactly the (1 - 0.71) x T_s the ingress bound allows.
- Incorrect (top-1 -> C or D): T_r is 14.0 s, the same as with no pre-positioning, although B forwards all 0.72 Sink
  to the destination. This is the predicted ingress-bound outcome (TOPOLOGY_PLAN D.1b, N = 1 row): the destination
  must receive a whole Sink through its own 1 Gbps link, and it does not matter whether the bytes come from A or
  from B. What the run establishes is that the speculative progress is **preserved and reused** (0.72 Sink delivered
  by B, 0.29 by A) rather than discarded, and that the source's total stays at one Sink. Whether reuse of wrongly
  placed fragments buys latency is a question about the shared-source regime (H5e, A3 with N = 4), not this one.
- Proportional spreads the same 0.72 Sink and so lands between the two: 8.0 / 11.0 / 13.0 s for B / C / D, and in each
  case the two non-chosen candidates forward what they hold (traffic 1.29-1.65 Sinks for a source cost of 1.00).

## Analytical prediction vs measurement

Every number matches D.1 (which used the measured T_s = 14.05 s) within 0.4 s and the fluid model within 0.2 s;
the per-candidate allocations match within 0.01 Sink. The one systematic difference is that the testbed is ~0.15 s
faster than the model's control-plane allowance.

## Required changes before the full sweep

None in the harness. Two notes for the sweep: (i) the `correct` flag in `summary.json` compares the destination with
the top-1 candidate, so it is meaningless for the oracle (reported as "incorrect" for C and D although the oracle is
correct by definition); the aggregator should treat the oracle separately; (ii) the tail-coverage policy's target
tau = 7.5 s sits 0.2-0.3 s above the predicted T_r of a half-Sink candidate (7.2-7.3 s), so its H5b-tail verdict is
sensitive to the control-plane time; the margin is real but small and should be reported as such.
