# Experiment B pilot: dissemination plans at uniform 1 Gbps, 5 runs (2026-10-15)

One Sink (1.61 GiB, 412 fragments) held at A, needed at B, C and D; every node's egress and ingress capped at 1 Gbps;
plans star / pipelined line / tree (A->B->{C,D}) / disjoint-fragment multipath (butterfly-like) / aware assignment;
1 rep each. Go/no-go and model predictions were committed before the run (TOPOLOGY_PLAN.md G step 3, G.1 "B-pilot").
Raw runs `restore_dissem_pilot/plan=*`; this file is the reading (the Experiment B aggregator is written with the sweep).

## Run validity

5/5 valid on every check: all fragments verified at all three destinations, no duplicates, no missing fragments,
paced egress within cap over every 10 s window (A 996.6, B 993.2, C 987.3, D 664.4 Mbps worst), kernel NIC receive
peaks <= 1056 Mbps, four distinct hosts, **all four nodes on the same commit** (4787218, reported by each node's HELLO
and checked by the orchestrator). Forwarders pipelined in every forwarding plan: the first forwarded fragment left B
0.10-0.20 s after the start, 14 s before B held the whole Sink.

## Results (completion time per destination, s; bytes in Sinks)

| plan | B / C / D | makespan | model | analytical | source | total | egress by node |
|---|---|---|---|---|---|---|---|
| star | 41.7 / 41.7 / 41.7 | 41.7 | 41.8 | 42.2 | 3.00 | 3.00 | A 3.0 |
| pipelined line | 13.9 / 14.1 / 14.1 | 14.1 | 14.2 | 14.1 + lag | 1.00 | 3.00 | A 1.0, B 1.0, C 1.0 |
| tree | 14.0 / 27.9 / 27.9 | 27.9 | 28.0 | 28.1 | 1.00 | 3.00 | A 1.0, B 2.0 |
| multipath (butterfly-like) | 14.0 / 14.0 / 14.0 | 14.0 | 14.2 | 14.1 + lag | 1.00 | 3.00 | A 1.0, B/C/D 0.67 each |
| aware assignment | 14.0 / 14.0 / 14.0 | 14.0 | 14.3 | 14.1 + lag | 1.00 | 3.00 | A 1.0, B/C/D 0.67 each |

## Go/no-go (pre-registered)

| check | threshold | measured | verdict |
|---|---|---|---|
| line within 1 s of 14.1 | 1.0 s | 0.02 s | pass |
| multipath within 1 s of 14.1 | 1.0 s | 0.08 s | pass |
| tree within 1 s of 28.1 | 1.0 s | 0.22 s | pass |
| star within 1 s of 42.2 | 1.0 s | 0.54 s | pass |
| aware within 1 s of line | 1.0 s | 0.07 s | pass |
| every forwarder pipelined; no duplicate or missing fragment; nodes on one commit | - | all true | pass |

**GO.** Model error <= 0.3 s on every completion time; the analytical values (D.2) are met within 0.5 s.

## Reading

1. The harness does what Experiment B needs: fragment-level pipelined forwarding (B forwards within 0.1 s of its first
   verified fragment), disjoint-fragment multipath with every node forwarding 2/3 Sink, per-destination completion,
   and the source-byte / total-byte distinction (every forwarding plan moves 3 Sinks in total while the source sends 1).
2. At uniform capacities the predicted collapse onto the ingress bound is measured: line, multipath and the aware
   assignment all finish at 14.0-14.1 s = S / 1 Gbps; the tree pays B's shared egress (27.9 s) and the star pays A's
   (41.7 s). Nothing here distinguishes multipath from line, as predicted (H6e regime).
3. The aware assignment, computed once at t0 from caps, its own queue and fragment availability, produced the same
   egress split as the fixed multipath plan (A 1.0, B/C/D 0.67 each) and the same completion time. Whether it beats the
   fixed families where they differ (model: 17.1 vs 18.9 s at B_f = 500 Mbps; 42.3 vs star's 41.8 at B_f = 125 Mbps
   with 1.19 Sinks of retransmission) is for the heterogeneous B runs, not this pilot.

## Caveat

This is a dissemination workload (one Sink to three fixed destinations), not OTTER's mobility problem; it validates
the mechanisms and the model that Experiment E will use under A -> B -> C -> D execution mobility. No claim about M3
follows from it.
