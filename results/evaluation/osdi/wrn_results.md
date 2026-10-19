# W / R / N results

## W

- **W-H1**: SUPPORTED
- **W-H2 primary**: {'set': 'all units', 'n': 40, 'successes': 39, 'share': 0.975, 'verdict': 'SUPPORTED'}
- **W-H2 S1**: {'set': 'S1: no RVC', 'n': 4, 'verdict': 'counts only (n < 10)', 'successes': 4, 'excluded': 36}
- **W-H2 S2**: {'set': 'S2: no cut-induced RVC', 'n': 26, 'successes': 25, 'share': 0.9615384615384616, 'verdict': 'SUPPORTED', 'excluded': 14}
- **W-H3**: SUPPORTED (Cold reaches 35 dB in 0.0% of 39)
- W1 units present: 40 of 40 (per-unit table: `w2_table.csv`; W1 detail in `wrn_results.json`)

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
