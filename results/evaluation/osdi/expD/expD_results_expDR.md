# Experiment D results

Aggregated by `tools/eval/aggregate_expD.py` per `aggregation_spec.md` from `results/evaluation/expDR_*`. Medians over valid reps.

| criterion | verdict | detail |
|---|---|---|
| G1 | **NOT EVALUABLE** | bw 1000.0: OTTER TTFO - s (n=0) <= 1.0; bw native: OTTER TTFO - s (n=0) <= 1.0; 1 Gbps: OTTER - s <= 0.1 x Full migration - s (n=0) |
| G2 | **NOT EVALUABLE** | bw 1000.0: rejoin - s, - calls (n=0) <= 6.0 s and <= 8; bw native: rejoin - s, - calls (n=0) <= 6.0 s and <= 8 |
| G3 rho 2 | **NOT EVALUABLE** | (a) source M1+M2 - <= 1.10, M1 only - >= 1.40 (n=0,0); (b) discarded M1+M2 - <= 0.10, M1 only - >= 0.40; (c) bind-ready M1+M2 - vs M1 only - s, within 1.0 s |
| G3 rho 4 | **NOT EVALUABLE** | (a) source M1+M2 - <= 1.10, M1 only - >= 1.40 (n=0,0); (b) discarded M1+M2 - <= 0.10, M1 only - >= 0.40; (c) bind-ready M1+M2 - vs M1 only - s, within 1.0 s |
| G4 | **SUPPORTED** | Full OTTER bind-ready 5.183 s (n=3) <= no placement 15.674 s (n=3) - 0.5 x 0.716 x 14.05 = 10.644 |
| G5 | **NOT SUPPORTED** | (a) bind-ready 15.788 vs no placement 15.782 s, within 1.5 s (n=3) [pass]; (b) B_source,total 1.226 <= 1.02 [fail]; (c) B_post 0.506 <= (1 - x) + 0.02 with x 0.716 [fail]; (d) B_fwd 0.501 >= 0.9 x 0.716 [fail] |
| G6 | **NOT EVALUABLE** | GPU session bind-ready M1+M2 - (n=0), OTTER event-driven - (n=0) <= M1 only - (n=0) - 3.5 s |
| G7 | **NOT EVALUABLE** | F: event-driven - (n=0) <= 0.5 x at moves - (n=0) s; F: re-plans - <= 2 (reps []); F: duplicates - = 0; B rho 2 (no change): re-plans - = 0 (reps []), bind-ready - vs - s within 1.0 s; B rho 4 (no change): re-plans - = 0 (reps []), bind-ready - vs - s within 1.0 s; G (no change): re-plans - = 0 (reps []), bind-ready - vs - s within 1.0 s |
| G8 | **NOT EVALUABLE** | M1 + M2 - (n=0) <= 0.6 x M1 only - (n=0) s; OTTER at moves - (n=0) <= 0.6 x M1 only - (n=0) s; OTTER event-driven - (n=0) <= 0.6 x M1 only - (n=0) s |
| G9 | **NOT EVALUABLE** | steady state: no expD_G9 run; bw 1000.0: destination peak memory_allocated {Full migration: - GiB, Cold restart: - GiB, M1 only: - GiB, OTTER event-driven: - GiB}, spread - <= 0.01; bw native: destination peak memory_allocated {Full migration: - GiB, Cold restart: - GiB, M1 only: - GiB, OTTER event-driven: - GiB}, spread - <= 0.01 |

### G5 clauses for M1 + M2 + top-1 (reported, not judged)

- (a) bind-ready 15.771 vs no placement 15.782 s, within 1.5 s (n=3) -> pass
- (b) B_source,total 1.010 <= 1.02 -> pass
- (c) B_post 0.290 <= (1 - x) + 0.02 with x 0.716 -> pass
- (d) B_fwd 0.717 >= 0.9 x 0.716 -> pass

## Configurations (medians over valid reps)

| scenario | configuration | bw | rho | valid / all | TTFO | bind-ready | rejoin (s / calls) | source | discarded | B_fwd | re-plans | dups |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C | Full OTTER | 1000.0 | None | 3 / 3 | 0.97 | 5.18 | 4.16 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| C | M1 + M2 (no placement) | 1000.0 | None | 3 / 3 | 0.97 | 15.67 | 3.58 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| C | M1 + M2 + top-1 | 1000.0 | None | 3 / 3 | 0.98 | 5.20 | 4.17 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| C | oracle | 1000.0 | None | 3 / 3 | 1.06 | 5.27 | 4.17 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| D | Full OTTER (AC) | 1000.0 | None | 3 / 3 | 1.02 | 15.79 | 3.60 / 6.00 | 1.23 | 0.23 | 0.50 | 1.00 | 0.00 |
| D | M1 + M2 (no placement) (AC) | 1000.0 | None | 3 / 3 | 1.00 | 15.78 | 3.59 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| D | M1 + M2 + top-1 (AC) | 1000.0 | None | 3 / 3 | 1.04 | 15.77 | 3.59 / 6.00 | 1.01 | 0.01 | 0.72 | 0.00 | 0.00 |
| D | oracle (AC) | 1000.0 | None | 3 / 3 | 1.01 | 5.25 | 4.20 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## Invalid runs (0; excluded, kept, re-run)


## Scenario A configurations needing reps 4-5 (IQR > 10 % of the median): 0

