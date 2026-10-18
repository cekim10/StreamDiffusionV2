# Experiment D results

Aggregated by `tools/eval/aggregate_expD.py` per `aggregation_spec.md` from `results/evaluation/expD_*`. Medians over valid reps.

| criterion | verdict | detail |
|---|---|---|
| G1 | **SUPPORTED** | bw 1000.0: OTTER TTFO 0.675 s (n=3) <= 1.0 [pass]; bw native: OTTER TTFO 0.680 s (n=3) <= 1.0 [pass]; 1 Gbps: OTTER 0.675 s <= 0.1 x Full migration 54.250 s (n=3) [pass] |
| G2 | **SUPPORTED** | bw 1000.0: rejoin 3.581 s, 6 calls (n=3) <= 6.0 s and <= 8 [pass]; bw native: rejoin 3.575 s, 6 calls (n=3) <= 6.0 s and <= 8 [pass] |
| G3 rho 2 | **SUPPORTED** | (a) source M1+M2 1.034 <= 1.10, M1 only 2.014 >= 1.40 (n=3,3) [pass]; (b) discarded M1+M2 0.049 <= 0.10, M1 only 1.014 >= 0.40 [pass]; (c) bind-ready M1+M2 15.105 vs M1 only 15.522 s, within 1.0 s [pass] |
| G3 rho 4 | **SUPPORTED** | (a) source M1+M2 1.024 <= 1.10, M1 only 1.515 >= 1.40 (n=3,3) [pass]; (b) discarded M1+M2 0.036 <= 0.10, M1 only 0.515 >= 0.40 [pass]; (c) bind-ready M1+M2 15.658 vs M1 only 15.165 s, within 1.0 s [pass] |
| G4 | **SUPPORTED** | Full OTTER bind-ready 4.942 s (n=3) <= no placement 15.419 s (n=3) - 0.5 x 0.716 x 14.05 = 10.389 |
| G5 | **NOT SUPPORTED** | (a) bind-ready 15.463 vs no placement 15.531 s, within 1.5 s (n=3) [pass]; (b) B_source,total 1.226 <= 1.02 [fail]; (c) B_post 0.506 <= (1 - x) + 0.02 with x 0.716 [fail]; (d) B_fwd 0.501 >= 0.9 x 0.716 [fail] |
| G6 | **SUPPORTED** | GPU session bind-ready M1+M2 43.094 (n=3), OTTER event-driven 42.820 (n=3) <= M1 only 57.068 (n=3) - 3.5 s |
| G7 | **SUPPORTED** | F: event-driven 15.802 (n=3) <= 0.5 x at moves 51.577 (n=3) s [pass]; F: re-plans 2 <= 2 (reps [2, 2, 2]) [pass]; F: duplicates 0 = 0 [pass]; B rho 2 (no change): re-plans 0 = 0 (reps [0, 0, 0]), bind-ready 15.449 vs 15.241 s within 1.0 s [pass]; B rho 4 (no change): re-plans 0 = 0 (reps [0, 0, 0]), bind-ready 15.072 vs 15.107 s within 1.0 s [pass]; G (no change): re-plans 0 = 0 (reps [0, 0, 0]), bind-ready 8.381 vs 8.669 s within 1.0 s [pass] |
| G8 | **SUPPORTED** | M1 + M2 8.724 (n=3) <= 0.6 x M1 only 15.409 (n=3) s [pass]; OTTER at moves 8.669 (n=3) <= 0.6 x M1 only 15.409 (n=3) s [pass]; OTTER event-driven 8.381 (n=3) <= 0.6 x M1 only 15.409 (n=3) s [pass] |
| G9 | **NOT SUPPORTED** | steady state: OTTER-enabled vs unmodified median chunk service time +0.10 % (|.| <= 2 %), reps 3, identical frames True; inter-chunk completion interval (descriptive) +0.16 % [pass]; bw 1000.0: destination peak memory_allocated {Full migration: 28.663 GiB, Cold restart: 28.018 GiB, M1 only: 27.930 GiB, OTTER event-driven: 27.930 GiB}, spread 0.026 <= 0.01 [fail]; bw native: destination peak memory_allocated {Full migration: 28.663 GiB, Cold restart: 28.018 GiB, M1 only: 27.930 GiB, OTTER event-driven: 27.930 GiB}, spread 0.026 <= 0.01 [fail] |

### G5 clauses for M1 + M2 + top-1 (reported, not judged)

- (a) bind-ready 15.525 vs no placement 15.531 s, within 1.5 s (n=3) -> pass
- (b) B_source,total 1.012 <= 1.02 -> pass
- (c) B_post 0.293 <= (1 - x) + 0.02 with x 0.716 -> pass
- (d) B_fwd 0.715 >= 0.9 x 0.716 -> pass

## Configurations (medians over valid reps)

| scenario | configuration | bw | rho | valid / all | TTFO | bind-ready | rejoin (s / calls) | source | discarded | B_fwd | re-plans | dups |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | Cold restart | native | None | 3 / 3 | 1.18 | - | - / - | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | Cold restart | 1000.0 | None | 3 / 3 | 1.17 | - | - / - | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | Full migration | native | None | 3 / 3 | 7.63 | 7.63 | 0.00 / 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | Full migration | 1000.0 | None | 3 / 3 | 54.25 | 54.25 | 0.00 / 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | M1 only | native | None | 3 / 3 | 0.68 | 3.21 | 3.58 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | M1 only | 1000.0 | None | 3 / 3 | 0.68 | 15.40 | 3.58 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | OTTER cold destination | native | None | 3 / 3 | 0.74 | 3.22 | 3.57 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | OTTER cold destination | 1000.0 | None | 3 / 3 | 0.74 | 15.12 | 4.28 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | OTTER event-driven | native | None | 3 / 3 | 0.68 | 3.16 | 3.57 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | OTTER event-driven | 1000.0 | None | 3 / 4 | 0.67 | 15.41 | 3.58 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Agen_bird_s0 | Full migration | 1000.0 | None | 3 / 3 | 54.12 | 54.12 | 0.00 / 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Agen_bird_s0 | OTTER event-driven | 1000.0 | None | 3 / 3 | 0.68 | 15.38 | 7.75 / 13.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Agen_bird_s1 | Full migration | 1000.0 | None | 3 / 3 | 54.16 | 54.16 | 0.00 / 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Agen_bird_s1 | OTTER event-driven | 1000.0 | None | 3 / 3 | 0.68 | 15.44 | 9.53 / 16.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Agen_boxing_s0 | Full migration | 1000.0 | None | 3 / 3 | 54.19 | 54.19 | 0.00 / 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Agen_boxing_s0 | OTTER event-driven | 1000.0 | None | 3 / 3 | 0.68 | 15.38 | 4.18 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Agen_boxing_s1 | Full migration | 1000.0 | None | 3 / 3 | 54.15 | 54.15 | 0.00 / 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Agen_boxing_s1 | OTTER event-driven | 1000.0 | None | 3 / 3 | 0.68 | 15.38 | 3.58 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| B | Cold restart | 1000.0 | 2.0 | 3 / 3 | 1.42 | - | - / - | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| B | Cold restart | 1000.0 | 4.0 | 3 / 3 | 1.37 | - | - / - | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| B | Full migration | 1000.0 | 2.0 | 3 / 3 | 53.49 | 53.49 | 0.00 / 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| B | Full migration | 1000.0 | 4.0 | 3 / 3 | 53.38 | 53.38 | 0.00 / 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| B | M1 + M2 | 1000.0 | 2.0 | 3 / 3 | 0.94 | 15.10 | 5.39 / 9.00 | 1.03 | 0.05 | 0.73 | 0.00 | 0.00 |
| B | M1 + M2 | 1000.0 | 4.0 | 3 / 3 | 0.92 | 15.66 | 4.20 / 7.00 | 1.02 | 0.04 | 0.36 | 0.00 | 0.00 |
| B | M1 only | 1000.0 | 2.0 | 3 / 3 | 0.92 | 15.52 | 4.23 / 7.00 | 2.01 | 1.01 | 0.00 | 0.00 | 0.00 |
| B | M1 only | 1000.0 | 4.0 | 3 / 3 | 0.96 | 15.17 | 3.62 / 6.00 | 1.52 | 0.52 | 0.00 | 0.00 | 0.00 |
| B | OTTER at moves | 1000.0 | 2.0 | 3 / 3 | 0.90 | 15.24 | 5.37 / 9.00 | 1.02 | 0.15 | 0.74 | 0.00 | 0.00 |
| B | OTTER at moves | 1000.0 | 4.0 | 3 / 3 | 0.91 | 15.11 | 3.60 / 6.00 | 1.02 | 0.10 | 0.36 | 0.00 | 0.00 |
| B | OTTER event-driven | 1000.0 | 2.0 | 3 / 3 | 0.90 | 15.45 | 5.44 / 9.00 | 1.03 | 0.17 | 0.74 | 0.00 | 0.00 |
| B | OTTER event-driven | 1000.0 | 4.0 | 3 / 3 | 0.90 | 15.07 | 3.59 / 6.00 | 1.02 | 0.09 | 0.36 | 0.00 | 0.00 |
| C | Full OTTER | 1000.0 | None | 3 / 3 | 0.71 | 4.94 | 4.17 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| C | M1 + M2 (no placement) | 1000.0 | None | 3 / 3 | 0.70 | 15.42 | 3.57 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| C | M1 + M2 + top-1 | 1000.0 | None | 3 / 3 | 0.70 | 4.90 | 4.18 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| C | oracle | 1000.0 | None | 3 / 3 | 0.70 | 4.92 | 4.18 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| D | Full OTTER (AC) | 1000.0 | None | 3 / 3 | 0.72 | 15.46 | 3.61 / 6.00 | 1.23 | 0.23 | 0.50 | 1.00 | 0.00 |
| D | M1 + M2 (no placement) (AC) | 1000.0 | None | 3 / 3 | 0.72 | 15.53 | 3.61 / 6.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| D | M1 + M2 + top-1 (AC) | 1000.0 | None | 3 / 3 | 0.72 | 15.52 | 3.59 / 6.00 | 1.01 | 0.01 | 0.71 | 0.00 | 0.00 |
| D | oracle (AC) | 1000.0 | None | 3 / 3 | 0.72 | 4.90 | 4.17 / 7.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| E | M1 + M2 | 1000.0 | 2.0 | 3 / 3 | 1.00 | 43.09 | 4.24 / 7.00 | 1.02 | 0.02 | 0.24 | 0.00 | 0.00 |
| E | M1 only | 1000.0 | 2.0 | 3 / 3 | 0.93 | 57.07 | 4.23 / 7.00 | 1.26 | 0.26 | 0.00 | 0.00 | 0.00 |
| E | OTTER event-driven | 1000.0 | 2.0 | 3 / 3 | 0.96 | 42.82 | 4.23 / 7.00 | 1.01 | 0.08 | 0.24 | 0.00 | 0.00 |
| F | M1 + M2 + cap event | 1000.0 | 2.0 | 3 / 3 | 0.98 | 78.39 | 4.24 / 7.00 | 1.03 | 0.05 | 0.73 | 0.00 | 0.00 |
| F | M1 only + cap event | 1000.0 | 2.0 | 3 / 3 | 0.98 | 15.36 | 5.47 / 9.00 | 2.02 | 1.02 | 0.00 | 0.00 | 0.00 |
| F | OTTER at moves + cap event | 1000.0 | 2.0 | 3 / 3 | 0.98 | 51.58 | 3.61 / 6.00 | 1.03 | 0.17 | 0.73 | 0.00 | 0.00 |
| F | OTTER event-driven + cap event | 1000.0 | 2.0 | 3 / 3 | 0.96 | 15.80 | 4.24 / 7.00 | 1.19 | 0.32 | 0.57 | 2.00 | 0.00 |
| G | M1 + M2 (ABCDB) | 1000.0 | 2.0 | 3 / 3 | 1.18 | 8.72 | 4.20 / 7.00 | 1.05 | 0.48 | 0.39 | 0.00 | 0.00 |
| G | M1 only (ABCDB) | 1000.0 | 2.0 | 3 / 3 | 1.19 | 15.41 | 4.25 / 7.00 | 2.54 | 1.03 | 0.00 | 0.00 | 0.00 |
| G | OTTER at moves (ABCDB) | 1000.0 | 2.0 | 3 / 3 | 1.11 | 8.67 | 4.18 / 7.00 | 1.04 | 0.50 | 0.39 | 0.00 | 0.00 |
| G | OTTER event-driven (ABCDB) | 1000.0 | 2.0 | 3 / 3 | 1.08 | 8.38 | 4.78 / 8.00 | 1.04 | 0.50 | 0.39 | 0.00 | 0.00 |

## Invalid runs (3; excluded, kept, re-run)

- `A/policy=reuse_dyn_bw=1000_rho=none_tm=inf_colddest_rep=2_20261017-180438`: no summary.json (incomplete)
- `A/policy=reuse_dyn_bw=1000_rho=none_tm=inf_rep=1_20261017-173408`: NIC peak > 1.15 x cap
- `A/policy=reuse_dyn_bw=native_rho=none_tm=inf_colddest_rep=2_20261017-181205`: no summary.json (incomplete)

## Scenario A configurations needing reps 4-5 (IQR > 10 % of the median): 0

