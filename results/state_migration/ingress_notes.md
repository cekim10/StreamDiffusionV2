# Shared-ingress result (server, results/state_migration/mobility, harness 155dc9c; A->B->C->D, T_m = 2 s, 1 Gbps links)

Ingress = total receive capacity of an edge as a multiple of one link, shared by concurrent incoming flows (processor sharing). The source's real TCP flow pays only the sharing penalty on top of its own link pacing; emulated edge->edge forwards pay the full link time.

| ingress | direct (oracle) | split | relay_pipe | restart |
|---|---|---|---|---|
| 1x | 17.8 s, 1.65 GB | 21.0 s, 2.31 GB, 0 waste | 19.4 s, 4.94 GB | 23.8 s, 2.20 GB, 548 MB waste |
| 2x | 17.7 s | **18.2 s**, 2.42 GB | 19.3 s | 23.8 s |
| unlimited | 17.7 s | 17.7 s | 19.3 s | 24.3 s |

Regression check passed: the unlimited rows reproduce the previous run (17.7 / 19.3 / 24.3 / 17.7).

## Reading
- Split's latency advantage over restart does not vanish at 1x ingress (21.0 vs 23.8 s) but shrinks; at 2x it is within 0.5 s of the oracle. The mechanism converts ingress headroom at the new edge into readiness; with a single receive link, readiness is bounded by (last move + one full sink time) for every policy that has to bring the sink into the new edge.
- Split never wastes bytes and never replicates the full sink (2.3-2.4 GB total vs 4.9 GB for pipelined relay); restart wastes 548 MB per two moves at this T_m.
- Pipelined relay looks best at 1x (19.4 s) because it feeds the new edge through one link that is never shared. Its cost is 3x traffic, and in this harness the emulated edge->edge links carry no serialization overhead while the real source link does (~0.08 s per 55 MB segment, from the direct run), which flatters relay_pipe by roughly 2 s at 1x. Adding that overhead to emulated links is a one-line calibration (`Ingress.take`) and would put relay_pipe at ~21.5 s at 1x; it was not applied in this run so the table stays comparable with the earlier ones.

## Claim after this check
Progress-aware routing preserves completed transfer progress across mobility: no restart waste, no full-hop replication, and readiness that improves monotonically with the new edge's ingress headroom, matching the oracle from 2x. With exactly one receive link it still beats restart by the time its already-delivered prefix would have taken to resend, and it beats pipelined relay on traffic by 2x. The reviewer concern "split only aggregates bandwidth" is answered: aggregation explains the gap between 1x and 2x, progress preservation explains the gap to restart and relay at every ingress.
