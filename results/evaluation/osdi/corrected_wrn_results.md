# W / R / N results

## W

- **W-H1**: SUPPORTED
- **W-H2 primary**: {'set': 'all units', 'n': 40, 'successes': 39, 'share': 0.975, 'verdict': 'SUPPORTED'}
- **W-H2 S1**: {'set': 'S1: no RVC', 'n': 4, 'verdict': 'counts only (n < 10)', 'successes': 4, 'excluded': 36}
- **W-H2 S2**: {'set': 'S2: no cut-induced RVC', 'n': 26, 'successes': 25, 'share': 0.9615384615384616, 'verdict': 'SUPPORTED', 'excluded': 14}
- **W-H3**: SUPPORTED (Cold reaches 35 dB in 0.0% of 39)
- W1 units present: 40 of 40 (per-unit table: `corrected_w2_table.csv`; W1 detail in `corrected_wrn_results.json`)

## R

| cell | R-H1 | R-H2 | R-H3 |
|---|---|---|---|
| rho=0.5,c=0 | NOT EVALUABLE (fewer than 3 valid applicable reps) | NOT EVALUABLE (fewer than 3 valid applicable reps) | NOT EVALUABLE (fewer than 3 valid applicable reps) |
| rho=1,c=0 | SUPPORTED (B_src 3.000 / 1.008, R 2.000 / 0.008, reduction 99.6%) | SUPPORTED (discarded M1+M2 0.025, M1 only 2.000) | SUPPORTED (bind 15.538 vs 15.605) |
| rho=2,c=0 | SUPPORTED (B_src 2.028 / 1.039, R 1.028 / 0.039, reduction 96.2%) | SUPPORTED (discarded M1+M2 0.061, M1 only 1.028) | SUPPORTED (bind 15.469 vs 15.468) |
| rho=4,c=0 | SUPPORTED (B_src 1.520 / 1.032, R 0.520 / 0.032, reduction 93.9%) | SUPPORTED (discarded M1+M2 0.044, M1 only 0.520) | SUPPORTED (bind 15.287 vs 15.453) |
| rho=8,c=0 | SUPPORTED (B_src 1.265 / 1.027, R 0.265 / 0.027, reduction 89.9%) | SUPPORTED (discarded M1+M2 0.041, M1 only 0.265) | SUPPORTED (bind 15.355 vs 15.457) |
| rho=0.5,c=3 | SUPPORTED (B_src 2.019 / 1.010, R 1.019 / 0.010, reduction 99.0%) | SUPPORTED (discarded M1+M2 0.010, M1 only 1.019) | NOT EVALUABLE (contention not exposure-valid: M1 only True, M1+M2 False) |
| rho=1,c=3 | SUPPORTED (B_src 1.518 / 1.017, R 0.518 / 0.017, reduction 96.7%) | SUPPORTED (discarded M1+M2 0.017, M1 only 0.518) | SUPPORTED (bind 28.925 vs 57.359) |
| rho=2,c=3 | SUPPORTED (B_src 1.260 / 1.019, R 0.260 / 0.019, reduction 92.5%) | SUPPORTED (discarded M1+M2 0.019, M1 only 0.260) | SUPPORTED (bind 43.024 vs 57.040) |
| rho=4,c=3 | SUPPORTED (B_src 1.131 / 1.017, R 0.131 / 0.017, reduction 87.0%) | SUPPORTED (discarded M1+M2 0.017, M1 only 0.131) | descriptive (bind 49.789 vs 57.067) |
| rho=8,c=3 | NOT EVALUABLE (R(M1 only) = 0.068 < 0.10) | SUPPORTED (discarded M1+M2 0.017, M1 only 0.068) | descriptive (bind 53.613 vs 57.130) |

Manipulation check (c = 0): {'2.0': 'MET (discarded M1 only 1.028 vs 0.750)', '4.0': 'MET (discarded M1 only 0.520 vs 0.375)', '8.0': 'MET (discarded M1 only 0.265 vs 0.188)'}

## N

| cell | class | verdict | effect |
|---|---|---|---|
| 1 | no change | N-H1 SUPPORTED (re-plans 0.000, bind 15.156 vs 15.021, B_src 1.000 vs 1.000) | neutral |
| 2 | no alternative | N-H3 SUPPORTED (bind 118.299 vs 118.028, B_src 1.000 vs 1.000, re-plans 0.000) | neutral |
| 3 | no alternative | N-H3 SUPPORTED (bind 117.919 vs 118.448, B_src 1.000 vs 1.000, re-plans 0.000) | neutral |
| 4 | no change | N-H1 SUPPORTED (re-plans 0.000, bind 4.947 vs 4.949, B_src 1.000 vs 1.000) | neutral |
| 5 | no alternative | N-H3 SUPPORTED (bind 32.624 vs 32.799, B_src 1.000 vs 1.000, re-plans 0.000) | neutral |
| 6 | no alternative | N-H3 SUPPORTED (bind 32.671 vs 32.730, B_src 1.000 vs 1.000, re-plans 0.000) | neutral |
| 7 | no change | N-H1 NOT SUPPORTED (re-plans 1.000, bind 15.000 vs 15.006, B_src 1.226 vs 1.010) | harmful |
| 8 | no alternative | N-H3 NOT SUPPORTED (bind 18.560 vs 15.013, B_src 1.027 vs 1.000, re-plans 3.000) | harmful |
| 9 | alternative available | N-H2 NOT SUPPORTED (bind 15.072 vs 113.398, re-plans 3.000, dups 0.000) | beneficial (traffic flagged) |
| 10 | no alternative | N-H3 NOT SUPPORTED (bind 113.891 vs 117.752, B_src 1.229 vs 1.000, re-plans 29.000) | beneficial (traffic flagged) |

## V (M3-v2 holdout)

| cell | class | verdict (v2 vs at moves) | V-H4 (v2 vs v1) |
|---|---|---|---|
| V1 | no change | V-H1 SUPPORTED (re-plans 0.000, bind 12.084 vs 12.100, B_src 1.010 vs 1.010) | SUPPORTED (v2 vs v1: bind 12.084 vs 12.080, B_src 1.010 vs 1.073, re-plans 0.000 vs 1.000) |
| V2 | alternative available | V-H2 SUPPORTED (bind 12.235 vs 44.947, re-plans 1.000, dups 0.000) | SUPPORTED (v2 vs v1: bind 12.235 vs 12.129, B_src 1.306 vs 1.299, re-plans 1.000 vs 2.000) |
| V3 | no alternative | V-H3 SUPPORTED (bind 20.262 vs 20.369, B_src 1.010 vs 1.000, re-plans 1.000) | SUPPORTED (v2 vs v1: bind 20.262 vs 20.298, B_src 1.010 vs 1.073, re-plans 1.000 vs 1.000) |
| V4 | alternative available | V-H2 SUPPORTED (bind 19.118 vs 38.322, re-plans 2.000, dups 0.000) | NOT SUPPORTED (v2 vs v1: bind 19.118 vs 15.058, B_src 1.367 vs 1.411, re-plans 2.000 vs 3.000) |
| V5 | alternative available | V-H2 SUPPORTED (bind 21.566 vs 122.077, re-plans 2.000, dups 0.000) | NOT SUPPORTED (v2 vs v1: bind 21.566 vs 17.425, B_src 1.231 vs 1.338, re-plans 2.000 vs 3.000) |
| V6 | no alternative | V-H3 SUPPORTED (bind 87.588 vs 87.747, B_src 1.000 vs 1.000, re-plans 0.000) | SUPPORTED (v2 vs v1: bind 87.588 vs 86.818, B_src 1.000 vs 1.253, re-plans 0.000 vs 5.000) |
| V7 | no alternative | V-H3 SUPPORTED (bind 15.241 vs 15.092, B_src 1.000 vs 1.000, re-plans 0.000) | SUPPORTED (v2 vs v1: bind 15.241 vs 15.605, B_src 1.000 vs 1.170, re-plans 0.000 vs 2.000) |
| V8 | no alternative | V-H3 SUPPORTED (bind 335.286 vs 335.733, B_src 1.000 vs 1.000, re-plans 0.000) | SUPPORTED (v2 vs v1: bind 335.286 vs 335.428, B_src 1.000 vs 1.000, re-plans 0.000 vs 0.000) |

## A (M1 recent-KV handoff, native bandwidth)

- n = 1 slots: NO-GO (sustained 10 vs 10, terminal 42.1 vs 42.3 dB, TTFO 1.62 vs 0.68 s, fast-path bytes 578 MB, consumed ok 10/10, outputs differ 10/10)
- n = 2 slots: NO-GO (sustained 10 vs 10, terminal 42.2 vs 42.3 dB, TTFO 2.47 vs 0.68 s, fast-path bytes 1153 MB, consumed ok 10/10, outputs differ 10/10)
- n = 3 slots: NO-GO (sustained 10 vs 10, terminal 42.2 vs 42.3 dB, TTFO 3.37 vs 0.68 s, fast-path bytes 1728 MB, consumed ok 10/10, outputs differ 10/10)
- n = 0 baseline: {'units': 10, 'sustained': 10, 'terminal_median': 42.2782, 'ttfo_median': 0.6807831525802612, 'gap_median': 17.021283333333333, 'fg_bytes_median': 2799408.0, 'consumed_ok': 0, 'differs_from_n0': 0}
