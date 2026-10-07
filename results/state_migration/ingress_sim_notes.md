# Shared-ingress check (offline simulation, tools/test_sink_router.py; A->B->C->D, T_m = 2 s, 1 Gbps links, T_s = 13.8 s)

Ingress = total receive capacity of an edge as a multiple of one link; concurrent incoming flows share it (processor sharing).

| ingress | direct | split | relay_pipe | restart |
|---|---|---|---|---|
| 1x | 16.0 s, 1.65 GB | 20.6 s, 2.15 GB | 20.5 s, 4.95 GB | 20.6 s, 2.09 GB |
| 2x | 16.2 s, 1.65 GB | 16.7 s, 2.31 GB | 20.7 s, 4.95 GB | 20.1 s, 2.09 GB |
| 3x | 16.2 s, 1.65 GB | 16.1 s, 2.31 GB | 20.5 s, 4.95 GB | 20.4 s, 2.09 GB |
| unlimited | 16.5 s, 1.65 GB | 15.9 s, 2.31 GB | 20.4 s, 4.95 GB | 20.2 s, 2.09 GB |

Reading:
- With 1x ingress every policy must pull the full 1.6 GB into D through one link after the last move, so split, restart and pipelined relay tie on readiness (~last move + T_s). Split's latency advantage over restart comes from path diversity (two or more links into the new edge); with 2x ingress it already matches the oracle.
- Split's advantage that does not depend on ingress: no wasted transfer and no replication. Total traffic at 1x is similar to restart (2.15 vs 2.09 GB) but the bytes are placed differently: restart re-sends everything from the source (A uplink 2.09 GB), split sends 1.16 GB from the source and the rest from B and C (progress stays useful, the source's uplink is not reloaded). relay_pipe moves 4.95 GB.
- Claim to make: progress-aware routing preserves completed transfer progress across mobility (no restart waste, no full-hop replication) and converts any ingress headroom at the new edge directly into continuity-ready latency, reaching the oracle at 2x.
Server confirmation: tools/run_mobility.sh with INGRESS="1 2 u", POLICIES="split restart relay_pipe direct".
