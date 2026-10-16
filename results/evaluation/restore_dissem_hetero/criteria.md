# Experiment B (restore_dissem_hetero + restore_dissem_pilot), medians of valid runs

Valid runs 50/50; invalid: none; incomplete: none

## Makespan (s) per condition and plan, measured / model; source Sinks in brackets

| condition | Star | Pipelined line | Tree | Multipath | Aware | best fixed | aware / best fixed |
|---|---|---|---|---|---|---|---|
| Bs=1000/Bf=1000/Bin=1000 | 41.7 / 41.8 [3.00] | 14.1 / 14.2 [1.00] | 27.9 / 28.0 [1.00] | 14.0 / 14.2 [1.00] | 14.0 / 14.3 [1.00] | Multipath (14.0) | 1.00 |
| Bs=1000/Bf=500/Bin=1000 | 41.7 / 41.8 [3.00] | 28.0 / 28.0 [1.00] | 55.6 / 55.6 [1.00] | 18.6 / 18.9 [1.00] | 16.9 / 17.1 [1.20] | Multipath (18.6) | 0.91 |
| Bs=1000/Bf=125/Bin=1000 | 41.7 / 41.8 [3.00] | 111.0 / 111.2 [1.00] | 221.1 / 221.5 [1.00] | 73.8 / 74.5 [1.00] | 42.1 / 42.3 [2.18] | Star (41.7) | 1.01 |
| Bs=250/Bf=1000/Bin=1000 | 166.0 / 166.2 [3.00] | 55.6 / 55.6 [1.00] | 55.6 / 55.6 [1.00] | 55.4 / 55.7 [1.00] | 55.4 / 55.6 [1.00] | Multipath (55.4) | 1.00 |

## Verdicts over the tested conditions only (TOPOLOGY_PLAN F; the full-grid H6f stays open)

- H6a (best fixed plan differs across conditions): supported: Bs=1000/Bf=1000/Bin=1000: Multipath, Bs=1000/Bf=500/Bin=1000: Multipath, Bs=1000/Bf=125/Bin=1000: Star, Bs=250/Bf=1000/Bin=1000: Multipath
- H6b (B_s = 250: every forwarding plan <= 0.5 x star): supported (star 166.0, line 55.6, tree 55.6, multipath 55.4)
- H6c (B_f = 125: line and tree >= 2 x star): supported (star 41.7, line 111.0, tree 221.1)
- H6d (B_f = 500: multipath <= 0.75 x line and <= 0.5 x tree): supported (multipath 18.6, line 28.0, tree 55.6)
- H6e (uniform: multipath within 1 s of line): supported (14.0 vs 14.1)
- H6f over the tested subset (aware within 10 % of the best fixed plan in every tested condition): supported; aware / best fixed = Bs=1000/Bf=1000/Bin=1000: 1.00, Bs=1000/Bf=500/Bin=1000: 0.91, Bs=1000/Bf=125/Bin=1000: 1.01, Bs=250/Bf=1000/Bin=1000: 1.00. Full grid: not tested.

## Model agreement

- makespan: max |measured - model| = 0.70 s (median 0.17); source Sinks: max 0.006

## Egress by node (Sinks) and assignment (fragments per link), medians / first rep

- Bs=1000/Bf=1000/Bin=1000 star: egress {'A': 3.0}, assignment {'A->B': 412, 'A->C': 412, 'A->D': 412}, pipelined None
- Bs=1000/Bf=1000/Bin=1000 line: egress {'A': 1.0, 'B': 1.0, 'C': 1.0}, assignment {'A->B': 412, 'B->C': 412, 'C->D': 412}, pipelined True
- Bs=1000/Bf=1000/Bin=1000 tree: egress {'A': 1.0, 'B': 2.0}, assignment {'A->B': 412, 'B->C': 412, 'B->D': 412}, pipelined True
- Bs=1000/Bf=1000/Bin=1000 multipath: egress {'A': 1.0, 'B': 0.67, 'D': 0.67, 'C': 0.67}, assignment {'A->B': 138, 'B->C': 138, 'B->D': 138, 'C->B': 137, 'A->C': 137, 'C->D': 137, 'D->B': 137, 'D->C': 137, 'A->D': 137}, pipelined True
- Bs=1000/Bf=1000/Bin=1000 aware: egress {'A': 1.0, 'B': 0.67, 'C': 0.67, 'D': 0.67}, assignment {'A->B': 138, 'B->C': 275, 'C->D': 275, 'A->C': 137, 'D->B': 274, 'A->D': 137}, pipelined True
- Bs=1000/Bf=500/Bin=1000 star: egress {'A': 3.0}, assignment {'A->B': 412, 'A->C': 412, 'A->D': 412}, pipelined None
- Bs=1000/Bf=500/Bin=1000 line: egress {'A': 1.0, 'B': 1.0, 'C': 1.0}, assignment {'A->B': 412, 'B->C': 412, 'C->D': 412}, pipelined True
- Bs=1000/Bf=500/Bin=1000 tree: egress {'A': 1.0, 'B': 2.0}, assignment {'A->B': 412, 'B->C': 412, 'B->D': 412}, pipelined True
- Bs=1000/Bf=500/Bin=1000 multipath: egress {'A': 1.0, 'B': 0.67, 'D': 0.67, 'C': 0.67}, assignment {'A->B': 138, 'B->C': 138, 'B->D': 138, 'C->B': 137, 'A->C': 137, 'C->D': 137, 'D->B': 137, 'D->C': 137, 'A->D': 137}, pipelined True
- Bs=1000/Bf=500/Bin=1000 aware: egress {'A': 1.2, 'B': 0.6, 'D': 0.6, 'C': 0.6}, assignment {'A->B': 165, 'B->C': 247, 'C->D': 247, 'A->C': 165, 'A->D': 165, 'D->B': 247}, pipelined True
- Bs=1000/Bf=125/Bin=1000 star: egress {'A': 3.0}, assignment {'A->B': 412, 'A->C': 412, 'A->D': 412}, pipelined None
- Bs=1000/Bf=125/Bin=1000 line: egress {'A': 1.0, 'B': 1.0, 'C': 1.0}, assignment {'A->B': 412, 'B->C': 412, 'C->D': 412}, pipelined True
- Bs=1000/Bf=125/Bin=1000 tree: egress {'A': 1.0, 'B': 2.0}, assignment {'A->B': 412, 'B->C': 412, 'B->D': 412}, pipelined True
- Bs=1000/Bf=125/Bin=1000 multipath: egress {'A': 1.0, 'C': 0.67, 'B': 0.67, 'D': 0.67}, assignment {'A->B': 138, 'B->C': 138, 'B->D': 138, 'C->B': 137, 'A->C': 137, 'C->D': 137, 'D->B': 137, 'D->C': 137, 'A->D': 137}, pipelined True
- Bs=1000/Bf=125/Bin=1000 aware: egress {'A': 2.18, 'D': 0.27, 'C': 0.27, 'B': 0.27}, assignment {'A->B': 300, 'A->C': 301, 'A->D': 299, 'D->B': 100, 'B->C': 99, 'C->D': 100, 'B->D': 13, 'D->C': 12, 'C->B': 12}, pipelined True
- Bs=250/Bf=1000/Bin=1000 star: egress {'A': 3.0}, assignment {'A->B': 412, 'A->C': 412, 'A->D': 412}, pipelined None
- Bs=250/Bf=1000/Bin=1000 line: egress {'A': 1.0, 'B': 1.0, 'C': 1.0}, assignment {'A->B': 412, 'B->C': 412, 'C->D': 412}, pipelined True
- Bs=250/Bf=1000/Bin=1000 tree: egress {'A': 1.0, 'B': 2.0}, assignment {'A->B': 412, 'B->C': 412, 'B->D': 412}, pipelined True
- Bs=250/Bf=1000/Bin=1000 multipath: egress {'A': 1.0, 'B': 0.67, 'C': 0.67, 'D': 0.67}, assignment {'A->B': 138, 'B->C': 138, 'B->D': 138, 'C->B': 137, 'A->C': 137, 'C->D': 137, 'D->B': 137, 'D->C': 137, 'A->D': 137}, pipelined True
- Bs=250/Bf=1000/Bin=1000 aware: egress {'A': 1.0, 'B': 0.67, 'C': 0.67, 'D': 0.67}, assignment {'A->B': 138, 'B->C': 275, 'C->D': 275, 'A->C': 137, 'D->B': 274, 'A->D': 137}, pipelined True
