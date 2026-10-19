# W / R / N results (LOOPBACK DRY RUN - not results)

## W

- **W-H1**: SUPPORTED
- **W-H2 primary**: {'set': 'all units', 'n': 39, 'successes': 39, 'share': 1.0, 'verdict': 'SUPPORTED'}
- **W-H2 S1**: {'set': 'S1: no RVC', 'n': 39, 'successes': 39, 'share': 1.0, 'verdict': 'SUPPORTED', 'excluded': 0}
- **W-H2 S2**: {'set': 'S2: no cut-induced RVC', 'n': 39, 'successes': 39, 'share': 1.0, 'verdict': 'SUPPORTED', 'excluded': 0}
- **W-H3**: SUPPORTED (Cold reaches 35 dB in 0.0% of 39)
- W1 units present: 40 of 40 (per-unit table: `_dryrun_w2_table.csv`; W1 detail in `_dryrun_wrn_results.json`)

## R

| cell | R-H1 | R-H2 | R-H3 |
|---|---|---|---|
| rho=0.5,c=0 | SUPPORTED (B_src 3.000 / 1.000, R 2.000 / 0.000, reduction 100.0%) | SUPPORTED (discarded M1+M2 0.000, M1 only 0.000) | SUPPORTED (bind 5.859 vs 5.871) |
| rho=1,c=0 | SUPPORTED (B_src 3.000 / 1.062, R 2.000 / 0.062, reduction 96.9%) | SUPPORTED (discarded M1+M2 0.062, M1 only 2.000) | SUPPORTED (bind 5.867 vs 6.031) |
| rho=2,c=0 | NOT SUPPORTED (B_src 2.062 / 1.188, R 1.062 / 0.188, reduction 82.4%) | NOT SUPPORTED (discarded M1+M2 0.250, M1 only 1.062) | SUPPORTED (bind 6.064 vs 6.057) |
| rho=4,c=0 | NOT SUPPORTED (B_src 1.562 / 1.188, R 0.562 / 0.188, reduction 66.7%) | NOT SUPPORTED (discarded M1+M2 0.312, M1 only 0.562) | SUPPORTED (bind 6.251 vs 6.020) |
| rho=8,c=0 | NOT SUPPORTED (B_src 1.312 / 1.125, R 0.312 / 0.125, reduction 60.0%) | NOT SUPPORTED (discarded M1+M2 0.250, M1 only 0.312) | SUPPORTED (bind 6.349 vs 5.944) |
| rho=0.5,c=3 | NOT SUPPORTED (B_src 2.062 / 1.125, R 1.062 / 0.125, reduction 88.2%) | NOT SUPPORTED (discarded M1+M2 0.125, M1 only 1.062) | NOT EVALUABLE (contention not exposure-valid: M1 only True, M1+M2 False) |
| rho=1,c=3 | NOT SUPPORTED (B_src 1.562 / 1.125, R 0.562 / 0.125, reduction 77.8%) | NOT SUPPORTED (discarded M1+M2 0.125, M1 only 0.562) | SUPPORTED (bind 12.385 vs 23.095) |
| rho=2,c=3 | NOT SUPPORTED (B_src 1.312 / 1.125, R 0.312 / 0.125, reduction 60.0%) | NOT SUPPORTED (discarded M1+M2 0.125, M1 only 0.312) | SUPPORTED (bind 17.249 vs 23.021) |
| rho=4,c=3 | NOT SUPPORTED (B_src 1.188 / 1.062, R 0.188 / 0.062, reduction 66.7%) | NOT SUPPORTED (discarded M1+M2 0.125, M1 only 0.188) | descriptive (bind 20.828 vs 23.254) |
| rho=8,c=3 | NOT SUPPORTED (B_src 1.125 / 1.062, R 0.125 / 0.062, reduction 50.0%) | SUPPORTED (discarded M1+M2 0.062, M1 only 0.125) | descriptive (bind 24.028 vs 23.384) |

Manipulation check (c = 0): {'2.0': 'MET (discarded M1 only 1.062 vs 0.750)', '4.0': 'MET (discarded M1 only 0.562 vs 0.375)', '8.0': 'MET (discarded M1 only 0.312 vs 0.188)'}

## N

| cell | class | verdict | effect |
|---|---|---|---|
| 1 | no change | N-H1 SUPPORTED (re-plans 0.000, bind 5.967 vs 5.969, B_src 1.000 vs 1.000) | neutral |
| 2 | no alternative | N-H3 SUPPORTED (bind 45.752 vs 45.761, B_src 1.000 vs 1.000, re-plans 0.000) | neutral |
| 3 | no alternative | N-H3 SUPPORTED (bind 45.603 vs 45.713, B_src 1.000 vs 1.000, re-plans 0.000) | neutral |
| 4 | no change | N-H1 SUPPORTED (re-plans 0.000, bind 1.798 vs 1.797, B_src 1.000 vs 1.000) | neutral |
| 5 | no alternative | N-H3 SUPPORTED (bind 11.348 vs 11.337, B_src 1.000 vs 1.000, re-plans 0.000) | neutral |
| 6 | no alternative | N-H3 SUPPORTED (bind 11.126 vs 11.126, B_src 1.000 vs 1.000, re-plans 0.000) | neutral |
| 7 | no change | N-H1 NOT SUPPORTED (re-plans 0.000, bind 5.611 vs 5.600, B_src 1.062 vs 1.000) | harmful |
| 8 | no alternative | N-H3 SUPPORTED (bind 5.624 vs 5.592, B_src 1.000 vs 1.000, re-plans 0.000) | neutral |
| 9 | alternative available | N-H2 SUPPORTED (bind 17.150 vs 45.389, re-plans 1.000, dups 0.000) | beneficial (traffic flagged) |
| 10 | no alternative | N-H3 NOT SUPPORTED (bind 42.550 vs 45.262, B_src 1.312 vs 1.000, re-plans 1.000) | beneficial (traffic flagged) |
