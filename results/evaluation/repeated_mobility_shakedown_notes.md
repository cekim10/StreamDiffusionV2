# Phase 1 shakedown: physical repeated mobility A -> B -> C -> D at rho 2 (2026-10-13)

One run per policy, 1 Gbps per flow with per-node ingress and egress capped at 1 Gbps, T_s = 14.05 s, T_m = 7.025 s,
dog workload, seed 0, k = 2, migration at chunk 30, 4 MiB fragments (412). Hosts: A elves-01, B elves-02, C elves-03,
D elves-04. Raw runs: `repeated_mobility/policy=*_rho=2_tm=7.025_rep=1_20261013-*`. This is a single repetition:
nothing below is a result yet, only a check that the harness measures what the plan says.

## Validation (all 15 checks pass in all 5 runs)

Four distinct hosts; ownership A -> B -> C -> D; single owner at every move; all fragments verified; no version
mismatch; final Sink digest equals the source's; continuity after rejoin comparable to Phase 1 (39-45 dB). Shaping is
visible on the wire: kernel NIC receive peaks 1035-1049 Mbps at the receiving nodes (cap 1000 Mbps; the 1-s sampling
window and protocol overhead account for the excess), bookkeeping peak 1007 Mbps. Actual moves at 7.06-7.07 s and
14.06-14.10 s (nominal 7.025 / 14.05 s; chunk-boundary quantization adds <= 0.05 s here).

## Results (seconds after the final move C -> D; bytes as multiples of the Sink, 1.61 GiB)

| policy | first output | Sink received | bound | first output on bound Sink | rejoin (>= 35 dB) | total sent | wasted | reused from non-source |
|---|---|---|---|---|---|---|---|---|
| direct (oracle) | 0.94 | already there | 0.28 | 0.94 | 5.72 | 1.00 | 0.00 | 0 |
| relay (store and forward) | 0.64 | 27.99 | 28.24 | 28.84 | 33.62 | 3.00 | 0.00 | 3291 MiB |
| relay_pipe | 0.64 | 13.99 | 14.19 | 14.79 | 20.21 | 3.00 | 0.00 | 3291 MiB |
| restart | 0.64 | 13.99 | 14.20 | 14.80 | 20.21 | 2.02 | 1.02 | 0 |
| reuse, fixed routing (split) | 0.55 | 13.91 | 14.68 | 15.28 | 19.47 | 2.03 | 0.05 | 1640 MiB |

Bytes sent per node: restart A 3321 MiB; split A 1693, B 832, C 808 MiB; relay_pipe A, B, C 1645 MiB each.

## Reading

1. Restart pays the full transfer after the final move (Sink received 14.0 s after the move, = T_s) and throws away
   1.02 Sinks (824 MiB at B, 852 MiB at C). The oracle has the Sink at D before the move; the gap restart - oracle
   (13.9 s of continuity-ready latency) is the cost of not knowing the destination.
2. Reusing completed fragments (split) does what it is designed to do: at B -> C it forwards B's 48.8 % and asks A only
   for the rest; at C -> D it uses C (49 %), B (24 %) and A (27 %); 1640 MiB come from non-source holders and waste falls
   from 1.02 to 0.05 Sinks. The trace is in the run's `trace.txt`.
3. But with one 1 Gbps receive link at D, reuse does not shorten restoration: the Sink completes at D at the same time
   (28.43 s vs 28.45 s after migration start for restart vs split). The three sources into D just share D's ingress.
   This matches the emulation at 1x ingress. Split's later bind (14.68 vs 14.20 s) is not a routing effect: the Sink
   was verified at the same moment in both runs and the generator bound it at its next chunk boundary, 0.66 s later in
   split and 0.10 s later in restart (chunk = 0.55 s).
4. Reuse also does not reduce total traffic (2.03 vs 2.02 Sinks): forwarding B's and C's progress to D costs the same
   bytes as sending them from A. What changes is who sends: the source's egress drops from 3321 MiB to 1693 MiB. The
   measurable benefit at this topology is source offload and the absence of waste, not latency or bytes.
5. Relay pipelines are as fast as restart here but move 3 Sinks through every link; store-and-forward relay accumulates
   one T_s per hop after B (28 s after the final move).
6. The 0.05 Sink of waste in split are 19 fragments that landed at B or C in the last ~0.4 s before a move, after the
   new plan had already assigned them to another holder; they were never forwarded. A plan that also counts fragments in
   flight to the old owner would remove this.

## Pre-registered criteria (EXPERIMENT_PLAN.md), applied to this single repetition only

- H1 "restart wastes >= 0.25 Sink at rho >= 2": met (1.02).
- H1 "restart's continuity-ready after the final move >= T_s + 3 s (17.05 s)": not met (14.80 s). Restart restarts the
  transfer at the final move with the whole link, so it cannot exceed about T_s + one chunk; the clause was ill-posed but
  stays as written. "Direct lower by >= T_s / 2": met (0.94 vs 14.80 s).
- H1 "restart wastes <= 0.1 Sink at rho <= 1": not yet measured.
- H2 latency "split beats restart by >= 1 s at rho >= 2": not met (split 0.48 s later, a chunk-phase effect); the
  expected outcome at single ingress.
- H2 traffic "split wasted <= 0.1 Sink and total <= 0.6 x relay_pipe": waste met (0.05); total not met (2.03 > 1.80).

## Implications for the next phases (to be confirmed by the sweep)

- At a single receive link the restoration latency after the final move is set by D's ingress, not by where the
  fragments are; no routing over existing holders can beat "remaining bytes / D's ingress". Progress reuse helps
  latency only if the remaining bytes shrink before the final move, i.e. if fragments reach the eventual destination
  earlier (pre-positioning, prediction) or if D has more ingress than one link (Experiment 3 Scenario A at native speed).
- Reuse's clear benefits are zero waste and source-egress offload. Experiment 3 Scenario B (source serving several
  sessions) is where offload can turn into latency, and should be run before designing any routing optimizer.
