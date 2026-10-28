# VD-5 results (oracle sufficiency of joint recent KV + exact Sink restoration; not a practical migration)

Thresholds: VD-3's frozen `vd3_thresholds.json` (SHA-256 792a6ac77ffbca24); VD-4's resolution rule. Validity: **PASS**.

## Validity

- reuse gate (dog_s1 OT-1, B0 / R / S3 re-run at the VD-5 commit vs the stored VD-4 runs): **PASS** {'B0': {'calls': 158, 'stored_calls': 158, 'differing': 0}, 'R': {'calls': 158, 'stored_calls': 158, 'differing': 0}, 'S3': {'calls': 158, 'stored_calls': 158, 'differing': 0}}
- reused B0 / R / S3 rule outcomes and V1 equal VD-4's aggregate: {'B0': True, 'R': True, 'S3': True}
- train_s0|OT-1 RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 89, Sink equal to the restored one after the bind True
- train_s0|OT-1 V0 equals REF after the move: PASS
- train_s0|OT-L RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 93, Sink equal to the restored one after the bind False
- audi-snow-trail_s0|OT-1 RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 92, Sink equal to the restored one after the bind True
- audi-snow-trail_s0|OT-L RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 93, Sink equal to the restored one after the bind False
- audi-snow-trail_s0|OT-L V0 equals REF after the move: PASS
- dog_s1|OT-1 RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 73, Sink equal to the restored one after the bind True
- dog_s1|OT-1 V0 equals REF after the move: PASS
- dog_s1|OT-L RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 75, Sink equal to the restored one after the bind False
- dog_s1|OT-L V0 equals REF after the move: PASS
- train_s1|OT-1 RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 88, Sink equal to the restored one after the bind True
- train_s1|OT-L RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 94, Sink equal to the restored one after the bind False
- butterfly-feeding-slow-motion_s1|OT-1 RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 95, Sink equal to the restored one after the bind True
- butterfly-feeding-slow-motion_s1|OT-L RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 98, Sink equal to the restored one after the bind False
- butterfly-feeding-slow-motion_s1|OT-L V0 equals REF after the move: PASS
- audi-snow-trail_s1|OT-1 RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 91, Sink equal to the restored one after the bind True
- audi-snow-trail_s1|OT-1 V0 equals REF after the move: PASS
- audi-snow-trail_s1|OT-L RS3: stream valid, oracle checks, joint-restoration checks: PASS; bind re-rotated 94, Sink equal to the restored one after the bind False

## Formal results (12 cells numeric; flags on the six inspected cells against REF of the same session)

| condition | phase | numeric | flags (REF) | resolution |
|---|---|---|---|---|
| B0 | P1 | 11 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| B0 | P2a | 6 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| B0 | P2b | 3 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| B0 | P3 | 12 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| R | P1 | 12 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| R | P2a | 6 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| R | P2b | 2 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| R | P3 | 12 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| S3 | P1 | 10 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| S3 | P2a | 11 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| S3 | P2b | 11 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| S3 | P3 | 12 / 12 | 0 (0) | not inspected (VD-5 session; descriptive) |
| RS3 | P1 | 12 / 12 | 0 (0) | not inspected |
| RS3 | P2a | 11 / 12 | 0 (0) | not inspected |
| RS3 | P2b | 11 / 12 | 0 (0) | not inspected |
| RS3 | P3 | 12 / 12 | 0 (0) | not inspected |

Oracle bytes RS3: 3450.5 MB (idealized lower bounds 1 Gbps 27.60 s, 10 Gbps 2.76 s; not a migration latency).

**Primary question (RS3 sufficient for P1 and P2):** not inspected

Rater calibration: not inspected

## RS3 vs R and vs S3

- RS3 vs R (P1): {'numeric_non_inferior_P1': 12, 'of': 12, 'block_B_at_M': None, 'non_inferior': True}
- RS3 vs S3 (P2): {'numeric_non_inferior_P2': 12, 'of': 12, 'block_B_closer_to_REF': None, 'non_inferior': True}

## Per-cell numeric values

| cell | condition | V1 (P99) | D_c | late D_c | X_late | C_c | dE_cross | warp eO - eR | dO / dR | P1 P2a P2b P3 |
|---|---|---|---|---|---|---|---|---|---|---|
| train_s0|OT-1 | B0 | 1.89 (6.49) | -0.056 | -0.044 | -0.042 | 0.83 | 1.68 | +1.01 | 1.226 | y n n y |
| train_s0|OT-1 | R | 1.01 (6.49) | -0.037 | -0.044 | +0.010 | 0.67 | 1.29 | +0.89 | 1.223 | y n n y |
| train_s0|OT-1 | S3 | 1.71 (6.49) | -0.007 | +0.000 | -0.023 | 0.15 | 0.20 | +0.26 | 1.030 | y y y y |
| train_s0|OT-1 | RS3 | 1.12 (6.49) | -0.005 | +0.000 | -0.013 | 0.18 | 0.32 | +0.18 | 1.034 | y y y y |
| train_s0|OT-L | B0 | 2.90 (6.49) | -0.042 | -0.030 | -0.059 | 0.38 | 0.59 | +0.41 | 1.189 | y n n y |
| train_s0|OT-L | R | 1.90 (6.49) | -0.038 | -0.030 | -0.019 | 0.41 | 0.64 | +0.39 | 1.184 | y n n y |
| train_s0|OT-L | S3 | 2.99 (6.49) | -0.001 | +0.002 | -0.022 | 0.01 | 0.17 | +0.02 | 1.020 | y y y y |
| train_s0|OT-L | RS3 | 1.86 (6.49) | -0.000 | +0.002 | -0.011 | 0.08 | 0.21 | +0.02 | 1.020 | y y y y |
| audi-snow-trail_s0|OT-1 | B0 | 2.00 (2.84) | -0.052 | -0.012 | -0.062 | 0.05 | 0.72 | +0.28 | 1.023 | y y y y |
| audi-snow-trail_s0|OT-1 | R | 0.82 (2.84) | -0.041 | -0.012 | -0.022 | -0.11 | 0.60 | +0.69 | 1.110 | y y n y |
| audi-snow-trail_s0|OT-1 | S3 | 1.66 (2.84) | +0.001 | -0.002 | +0.009 | 0.13 | 0.21 | +0.40 | 0.982 | y y y y |
| audi-snow-trail_s0|OT-1 | RS3 | 0.80 (2.84) | -0.004 | -0.001 | -0.006 | 0.10 | 0.14 | +0.24 | 1.029 | y y y y |
| audi-snow-trail_s0|OT-L | B0 | 2.97 (2.84) | -0.052 | -0.063 | +0.027 | 0.52 | 1.00 | -0.38 | 1.113 | n y n y |
| audi-snow-trail_s0|OT-L | R | 2.16 (2.84) | -0.051 | -0.063 | +0.032 | 0.52 | 1.05 | -0.38 | 1.139 | y y n y |
| audi-snow-trail_s0|OT-L | S3 | 3.03 (2.84) | -0.005 | +0.006 | -0.004 | -0.01 | 0.06 | +0.27 | 1.044 | n y y y |
| audi-snow-trail_s0|OT-L | RS3 | 2.07 (2.84) | -0.003 | +0.007 | -0.000 | 0.09 | 0.07 | +0.16 | 1.050 | y y y y |
| dog_s1|OT-1 | B0 | 3.55 (3.91) | -0.017 | -0.013 | -0.012 | 0.78 | 1.17 | +0.69 | 1.211 | y y n y |
| dog_s1|OT-1 | R | 2.04 (3.91) | -0.013 | -0.013 | -0.001 | 0.67 | 1.06 | +0.47 | 1.195 | y y n y |
| dog_s1|OT-1 | S3 | 3.46 (3.91) | -0.001 | -0.000 | -0.004 | 0.46 | 0.49 | +0.59 | 1.117 | y y n y |
| dog_s1|OT-1 | RS3 | 2.10 (3.91) | -0.000 | -0.000 | -0.001 | 0.40 | 0.43 | +0.33 | 1.112 | y y n y |
| dog_s1|OT-L | B0 | 3.77 (3.91) | -0.011 | -0.012 | +0.001 | 0.51 | 1.11 | +0.35 | 1.230 | y y n y |
| dog_s1|OT-L | R | 1.79 (3.91) | -0.010 | -0.012 | +0.004 | 0.51 | 1.11 | +0.32 | 1.227 | y y n y |
| dog_s1|OT-L | S3 | 4.01 (3.91) | -0.001 | +0.000 | -0.006 | 0.20 | 0.24 | +0.15 | 1.051 | n y y y |
| dog_s1|OT-L | RS3 | 1.80 (3.91) | -0.000 | +0.000 | -0.001 | 0.15 | 0.18 | +0.11 | 1.042 | y y y y |
| train_s1|OT-1 | B0 | 2.01 (6.15) | -0.052 | -0.042 | -0.009 | 0.71 | 1.19 | +0.98 | 1.201 | y n n y |
| train_s1|OT-1 | R | 1.22 (6.15) | -0.048 | -0.042 | -0.000 | 0.71 | 1.19 | +0.80 | 1.186 | y n n y |
| train_s1|OT-1 | S3 | 1.61 (6.15) | -0.008 | +0.000 | -0.026 | 0.27 | 0.27 | +0.27 | 1.035 | y y y y |
| train_s1|OT-1 | RS3 | 1.22 (6.15) | -0.003 | +0.000 | -0.012 | 0.35 | 0.32 | +0.20 | 1.039 | y y y y |
| train_s1|OT-L | B0 | 3.10 (6.15) | -0.049 | -0.033 | -0.051 | 0.59 | 0.80 | +0.28 | 1.205 | y n n y |
| train_s1|OT-L | R | 1.78 (6.15) | -0.046 | -0.033 | -0.022 | 0.62 | 0.76 | +0.31 | 1.206 | y n n y |
| train_s1|OT-L | S3 | 2.88 (6.15) | -0.000 | +0.000 | -0.011 | 0.06 | 0.13 | -0.03 | 1.007 | y y y y |
| train_s1|OT-L | RS3 | 1.62 (6.15) | +0.001 | +0.000 | -0.004 | 0.13 | 0.17 | +0.00 | 1.012 | y y y y |
| butterfly-feeding-slow-motion_s1|OT-1 | B0 | 1.16 (1.25) | -0.086 | -0.091 | +0.002 | 1.40 | 3.52 | +0.54 | 1.129 | y n n y |
| butterfly-feeding-slow-motion_s1|OT-1 | R | 0.90 (1.25) | -0.080 | -0.091 | +0.024 | 1.23 | 3.23 | +0.51 | 1.136 | y n n y |
| butterfly-feeding-slow-motion_s1|OT-1 | S3 | 1.05 (1.25) | -0.005 | -0.001 | -0.012 | 0.12 | 0.31 | +0.40 | 1.028 | y y y y |
| butterfly-feeding-slow-motion_s1|OT-1 | RS3 | 0.77 (1.25) | -0.003 | -0.000 | -0.006 | 0.15 | 0.43 | +0.14 | 1.020 | y y y y |
| butterfly-feeding-slow-motion_s1|OT-L | B0 | 0.79 (1.25) | -0.012 | -0.034 | +0.021 | 1.59 | 3.36 | +0.31 | 1.169 | y n n y |
| butterfly-feeding-slow-motion_s1|OT-L | R | 0.78 (1.25) | -0.013 | -0.035 | +0.013 | 1.53 | 3.30 | +0.32 | 1.173 | y n n y |
| butterfly-feeding-slow-motion_s1|OT-L | S3 | 0.77 (1.25) | -0.007 | -0.028 | +0.022 | 0.11 | 0.20 | +0.20 | 1.009 | y n y y |
| butterfly-feeding-slow-motion_s1|OT-L | RS3 | 0.72 (1.25) | -0.007 | -0.029 | +0.024 | 0.05 | 0.12 | +0.16 | 1.006 | y n y y |
| audi-snow-trail_s1|OT-1 | B0 | 2.01 (3.22) | -0.089 | -0.023 | -0.121 | 0.01 | 0.76 | -0.43 | 0.942 | y y y y |
| audi-snow-trail_s1|OT-1 | R | 0.85 (3.22) | -0.067 | -0.023 | -0.053 | -0.13 | 0.77 | +0.10 | 1.047 | y y y y |
| audi-snow-trail_s1|OT-1 | S3 | 1.82 (3.22) | -0.005 | +0.000 | -0.007 | 0.10 | 0.20 | +0.41 | 0.991 | y y y y |
| audi-snow-trail_s1|OT-1 | RS3 | 0.82 (3.22) | -0.005 | +0.000 | -0.008 | 0.07 | 0.13 | +0.29 | 1.028 | y y y y |
| audi-snow-trail_s1|OT-L | B0 | 3.16 (3.22) | -0.026 | -0.052 | +0.022 | 0.64 | 1.10 | -0.48 | 1.049 | y y y y |
| audi-snow-trail_s1|OT-L | R | 2.07 (3.22) | -0.024 | -0.052 | +0.040 | 0.66 | 1.08 | -0.56 | 1.071 | y y y y |
| audi-snow-trail_s1|OT-L | S3 | 2.89 (3.22) | +0.000 | -0.005 | +0.018 | -0.08 | 0.15 | +0.35 | 1.042 | y y y y |
| audi-snow-trail_s1|OT-L | RS3 | 2.20 (3.22) | +0.000 | -0.005 | +0.010 | 0.03 | 0.12 | +0.21 | 1.049 | y y y y |

## Interaction I = (RS3 - S3) - (R - B0) (lower-is-closer form; additive when |I| <= the cell's tolerance): **complementary**

| metric | additive | synergistic | antagonistic |
|---|---|---|---|
| V1 | 10 | 0 | 2 |
| D_c | 12 | 0 | 0 |
| late D_c | 12 | 0 | 0 |
| C_c | 12 | 0 | 0 |
| dE_cross | 12 | 0 | 0 |
| warp excess | 12 | 0 | 0 |
| frame-diff ratio | 12 | 0 | 0 |

| cell | V1 | D_c | late D_c | C_c | dE_cross | warp excess | frame-diff ratio |
|---|---|---|---|---|---|---|---|
| train_s0|OT-1 | +0.290 (a) | +0.016 (a) | -0.000 (a) | +0.186 (a) | +0.506 (a) | +0.036 (a) | +0.006 (a) |
| train_s0|OT-L | -0.134 (a) | +0.004 (a) | +0.001 (a) | +0.027 (a) | -0.012 (a) | +0.023 (a) | +0.005 (a) |
| audi-snow-trail_s0|OT-1 | +0.334 (a) | +0.017 (a) | -0.000 (a) | +0.134 (a) | +0.049 (a) | -0.571 (a) | -0.076 (a) |
| audi-snow-trail_s0|OT-L | -0.149 (a) | -0.000 (a) | -0.000 (a) | +0.095 (a) | -0.043 (a) | -0.112 (a) | -0.020 (a) |
| dog_s1|OT-1 | +0.150 (a) | +0.003 (a) | -0.000 (a) | +0.062 (a) | +0.058 (a) | -0.044 (a) | +0.011 (a) |
| dog_s1|OT-L | -0.220 (a) | -0.000 (a) | +0.000 (a) | -0.056 (a) | -0.061 (a) | -0.004 (a) | -0.007 (a) |
| train_s1|OT-1 | +0.400 (a) | -0.000 (a) | -0.000 (a) | +0.089 (a) | +0.045 (a) | +0.118 (a) | +0.019 (a) |
| train_s1|OT-L | +0.047 (a) | +0.002 (a) | -0.000 (a) | +0.039 (a) | +0.072 (a) | -0.006 (a) | +0.003 (a) |
| butterfly-feeding-slow-motion_s1|OT-1 | -0.015 (a) | +0.004 (a) | -0.001 (a) | +0.198 (a) | +0.415 (a) | -0.220 (a) | -0.016 (a) |
| butterfly-feeding-slow-motion_s1|OT-L | -0.036 (a) | -0.001 (a) | +0.000 (a) | +0.001 (a) | -0.023 (a) | -0.056 (a) | -0.007 (a) |
| audi-snow-trail_s1|OT-1 | +0.167 (a) | +0.022 (a) | +0.000 (a) | +0.105 (a) | -0.083 (a) | -0.646 (a) | +0.031 (a) |
| audi-snow-trail_s1|OT-L | +0.393 (a) | +0.002 (a) | +0.000 (a) | +0.097 (a) | -0.014 (a) | -0.066 (a) | -0.015 (a) |
