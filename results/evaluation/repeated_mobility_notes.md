# Phase 1: physical repeated mobility A -> B -> C -> D, rho sweep (2026-10-13)

75 runs: 5 policies x rho {0.5, 1, 2, 4, 8} x 3 reps, plus the 5 shakedown runs (rho 2, not included in the medians).
1 Gbps per flow, per-node ingress and egress capped at 1 Gbps (max-min fair), T_s = 14.05 s (measured), T_m = T_s / rho.
Hosts A elves-01, B elves-02, C elves-03, D elves-04, GPU 0 each; dog workload, seed 0, k = 2, migration at chunk 30,
4 MiB fragments. Raw runs: `repeated_mobility/policy=*_bw=1000_rho=*`; table `repeated_mobility/figures/mobility_table.csv`;
figures `repeated_mobility/figures/figE1_*, figE2{a,b,c}_*, figE3_*` (tools/eval/plot_mobility.py).

Policy names: "oracle" is the policy previously called `direct` (it knows the final owner D at time zero and sends there
only). The plan's policy 4 "direct to the current destination from the source" is identical to restart on a path that
never revisits a node, so it is not a separate run. "Reuse, fixed routing" is `split`; it has no source selection and is
not OTTER's routing.

## Run quality

- 74/75 runs pass every validation check. The one flag is `relay_pipe_forwarded_before_complete = False` in relay_pipe
  rho 1 rep 2: at rho 1 the move to C comes 0.06-0.14 s before B finishes, so there was nothing left to pipeline. This
  is the knife edge predicted in the plan, not a harness fault.
- No contamination: node service time 0.556 s/chunk in every run; kernel NIC receive peaks 1037-1063 Mbps (cap 1000);
  actual mean move intervals within 0.02 s of nominal (28.11, 14.06, 7.03, 3.53, 1.77 s); all runs stopped on
  rejoin + tail, none on timeout.

## Results (medians of 3; continuity-ready = first output produced on the bound Sink, seconds after the final move)

| rho | restart | relay | relay_pipe | reuse (fixed) | oracle |
|---|---|---|---|---|---|
| 0.5 | 15.1 | 15.3 | 15.3 | 15.3 | 0.67 |
| 1 | 14.9 | 14.8 | 15.4 | 14.8 | 0.68 |
| 2 | 15.3 | 29.3 | 14.9 | 15.3 | 0.85 |
| 4 | 15.4 | 35.9 | 14.9 | 14.8 | 7.8 |
| 8 | 15.2 | 39.5 | 14.8 | 15.3 | 11.4 |

Bytes per Sink (total sent / unused / sent by the source A):

| rho | restart | relay, relay_pipe | reuse (fixed) | oracle |
|---|---|---|---|---|
| 0.5 | 3.00 / 0.00 / 3.00 | 3.00 / 0 / 1.00 | 3.00 / 0.00 / 1.00 | 1.00 / 0 / 1.00 |
| 1 | 3.00 / 2.00 / 3.00 | 3.00 / 0 / 1.00 | 3.00 / 0.04 / 1.01 | 1.00 / 0 / 1.00 |
| 2 | 2.01 / 1.01 / 2.01 | 3.00 / 0 / 1.00 | 2.02 / 0.07 / 1.06 | 1.00 / 0 / 1.00 |
| 4 | 1.51 / 0.51 / 1.51 | 3.00 / 0 / 1.00 | 1.51 / 0.04 / 1.02 | 1.00 / 0 / 1.00 |
| 8 | 1.26 / 0.26 / 1.26 | 3.00 / 0 / 1.00 | 1.27 / 0.03 / 1.02 | 1.00 / 0 / 1.00 |

"Unused" (plan definition (a)): delivered to an owner that neither bound nor forwarded it. At rho 0.5 every owner binds
before it is left, so restart's copies at B and C were used there (0 unused); the orchestrator's own `wasted` counter
(2.00 at rho 0.5) did not make that distinction and is kept in the table for reference. No bytes were lost in flight
(cancelled flows ended at fragment boundaries).

Continuity at the intermediate owners (share of chunks executed at B and C at >= 35 dB): 0.34 for every non-oracle policy
at rho 0.5, 0 for every policy at rho >= 1 (no intermediate owner binds before being left), 0 for the oracle everywhere.

## Reading

1. Restoration latency after the final move is the same for restart, relay_pipe and reuse at every rho (14.8-15.4 s,
   about T_s + one chunk). D has one 1 Gbps receive link, and every policy except the oracle starts the final
   delivery at the final move with nothing (restart) or with fragments that are not at D (reuse, relay_pipe), so all
   of them pay "Sink bytes / D's ingress". Where the fragments sit does not matter.
2. Restart's real cost is bytes, not latency: it throws away 2.00 / 1.01 / 0.51 / 0.26 Sinks at rho 1 / 2 / 4 / 8 and
   makes the source send that much more. The loss per move is the fraction of the Sink delivered within T_m, so it
   shrinks as mobility gets faster; the worst case is rho just above 1, where each intermediate owner receives almost
   the whole Sink and is left before binding.
3. Reuse with fixed routing removes that waste (0.03-0.07 Sinks, the residue being fragments that land at an old owner
   just after the move was planned) and keeps the source near one Sink (1.00-1.06) at every rho; total bytes equal
   restart's at rho >= 2 because forwarding a held fragment costs the same as sending it from the source.
4. Relay (store and forward) adds one T_s per hop that the chain is behind (29-40 s at rho >= 2); pipelining removes
   that but moves 3 Sinks at every rho.
5. Only knowing the destination early reduces latency: the oracle's latency after the final move falls by exactly the
   bytes it could send to D before the move (0.7 s at rho <= 2, 7.8 s at rho 4, 11.4 s at rho 8 versus ~15 s). Its
   price is that the intermediate owners never get continuity (0 vs 0.34 at rho 0.5).
6. Control-plane delay from a move to the first new flow: median 0.28-0.32 s, max 0.68 s for restart, relay_pipe and
   reuse (orchestrator RPCs plus TCP connection setup); this is the route-switching cost of the current prototype.

## Pre-registered criteria (EXPERIMENT_PLAN.md), applied to the 3-rep medians

H1, repeated mobility creates restoration-progress loss:
- restart unused >= 0.25 Sink at rho >= 2: met at rho 2 (1.01), 4 (0.51), 8 (0.26).
- restart continuity-ready after the final move >= T_s + 3 s (17.05 s) at rho >= 2: not met (15.2-15.4 s). As noted in
  the shakedown, restart restarts with the whole link at the final move and cannot exceed T_s plus a chunk; the clause
  was ill-posed and stays as written.
- oracle lower than restart by >= T_s / 2 (7.0 s) at rho >= 2: met at rho 2 (14.5 s) and 4 (7.5 s), not at rho 8 (3.7 s).
- restart unused <= 0.1 Sink at rho <= 1: met at rho 0.5 (0.00), not at rho 1 (2.00).
- Verdict: progress loss exists and is large in bytes (up to 2 Sinks), but it does not show up as extra restoration
  latency at the final destination. The predicted regime change "around rho = 1" is real in a different form: waste
  peaks just above rho = 1 and falls toward 0 as rho grows; below 1 it is 0 because owners bind before they are left.

H2, preserving verified progress reduces restoration time:
- reuse beats restart by >= 1 s at rho >= 2: not met (differences -0.03, +0.56, -0.14 s). H2's latency part is rejected
  for a single-ingress destination, as the emulation predicted.
- reuse unused <= 0.1 Sink at rho >= 2: met (0.07, 0.04, 0.03).
- reuse total <= 0.6 x relay_pipe (1.8 Sinks) at rho >= 2: met at rho 4 (1.51) and 8 (1.27), not at rho 2 (2.02).
- Verdict: reuse buys zero waste and ~1 Sink of source egress at every rho, not latency.

## Unexpected observations and negative results

- No policy gives an intermediate owner continuity when rho >= 1, even at rho = 1 exactly (B finishes 0.06-0.14 s after
  being left). The window "owner binds before it moves" requires T_m > T_s + bind + recovery (about T_s + 5 s).
- Restart is not slower than reuse at any rho here. The claim "carrying restoration progress across mobility reduces
  restoration latency" is not supported on this topology.

## What this means for the next phases

- Latency at the final owner can only improve if bytes reach it before it becomes the owner: earlier knowledge of the
  next owner (prediction, or speculative pre-positioning to likely next owners) or more receive capacity at the owner
  (multiple NICs or an unshaped 9.4 Gbps ingress with several 1 Gbps sources). Experiment 2 (pre-positioned fragments at
  0-100 %) quantifies the first directly; Experiment 3 Scenario A at native speed quantifies the second.
- Reuse's measured value is source offload and zero waste. It matters for latency only when the source's egress, not the
  destination's ingress, is the bottleneck: one source serving several mobile sessions (Experiment 3 Scenario B). That
  experiment should run before any routing optimizer is designed.
- The simplest policy supported so far for a single session: send from the source to the current owner and keep
  fragments where they land (reuse), because it matches restart's latency, removes its waste and halves source load.
