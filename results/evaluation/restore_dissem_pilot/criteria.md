# Experiment B (restore_dissem_pilot), medians of valid runs

Valid runs 5/5; invalid: none; incomplete: none

## Makespan (s) per condition and plan, measured / model; source Sinks in brackets

| condition | Star | Pipelined line | Tree | Multipath | Aware | best fixed | aware / best fixed |
|---|---|---|---|---|---|---|---|
| Bs=1000/Bf=1000/Bin=1000 | 41.7 / 41.8 [3.00] | 14.1 / 14.2 [1.00] | 27.9 / 28.0 [1.00] | 14.0 / 14.2 [1.00] | 14.0 / 14.3 [1.00] | Multipath (14.0) | 1.00 |

## Verdicts over the tested conditions only (TOPOLOGY_PLAN F; the full-grid H6f stays open)

- H6e (uniform: multipath within 1 s of line): supported (14.0 vs 14.1)
- H6f over the tested subset (aware within 10 % of the best fixed plan in every tested condition): supported; aware / best fixed = Bs=1000/Bf=1000/Bin=1000: 1.00. Full grid: not tested.

## Model agreement

- makespan: max |measured - model| = 0.23 s (median 0.12); source Sinks: max 0.005

## Egress by node (Sinks) and assignment (fragments per link), medians / first rep

- Bs=1000/Bf=1000/Bin=1000 star: egress {'A': 3.0}, assignment {'A->B': 412, 'A->C': 412, 'A->D': 412}, pipelined None
- Bs=1000/Bf=1000/Bin=1000 line: egress {'A': 1.0, 'B': 1.0, 'C': 1.0}, assignment {'A->B': 412, 'B->C': 412, 'C->D': 412}, pipelined True
- Bs=1000/Bf=1000/Bin=1000 tree: egress {'A': 1.0, 'B': 2.0}, assignment {'A->B': 412, 'B->C': 412, 'B->D': 412}, pipelined True
- Bs=1000/Bf=1000/Bin=1000 multipath: egress {'A': 1.0, 'B': 0.67, 'D': 0.67, 'C': 0.67}, assignment {'A->B': 138, 'B->C': 138, 'B->D': 138, 'C->B': 137, 'A->C': 137, 'C->D': 137, 'D->B': 137, 'D->C': 137, 'A->D': 137}, pipelined True
- Bs=1000/Bf=1000/Bin=1000 aware: egress {'A': 1.0, 'B': 0.67, 'C': 0.67, 'D': 0.67}, assignment {'A->B': 138, 'B->C': 275, 'C->D': 275, 'A->C': 137, 'D->B': 274, 'A->D': 137}, pipelined True
