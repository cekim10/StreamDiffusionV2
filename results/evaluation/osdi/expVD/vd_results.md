# VD results

## Precheck (mechanism, not visual)

- Softmax mass on the zero-filled sink slots (dog, calls [34, 37]): median 0.0172, max 0.2209; 19 of 30 blocks have a median >= 0.01.
- Masked kernel (flash_attn_with_kvcache) vs SDPA with an explicit mask: max |diff| 0.0625 over 30 blocks; sink region zero in every probed call: True.

## Main effects (effect sizes first)

| input | schedule | S: sinkless V4 diff | S: sinkless E diff | D: V1 ratio | R: V1 ratio | R: first-4 E diff | V1 by D x R (mean over S) |
|---|---|---|---|---|---|---|---|
| dog | OT-1 | -0.12 | -0.026 | 0.409 | 0.782 | -0.704 | D0R0 8.01, D0R1 7.40, D1R0 4.18, D1R1 2.13 |
| dog | OT-L | -0.19 | -0.020 | 0.268 | 0.773 | -0.217 | D0R0 9.20, D0R1 8.31, D1R0 3.33, D1R1 1.37 |
| butterfly-feeding-slow-motion | OT-1 | 0.07 | 0.040 | 0.370 | 0.775 | -0.423 | D0R0 3.26, D0R1 2.64, D1R0 1.29, D1R1 0.89 |
| butterfly-feeding-slow-motion | OT-L | 0.01 | 0.034 | 0.451 | 0.949 | -0.209 | D0R0 1.94, D0R1 1.79, D1R0 0.84, D1R1 0.85 |

## Verdicts (preregistered rules; every input and schedule must agree)

- VD-H1 (masking lowers Sink-less color drift and warp error): **NOT SUPPORTED** [True, True, False, False]
- VD-H2 (keeping the decoder cache lowers the reset spike by >= 2x): **SUPPORTED** [True, True, True, True]
- VD-H3 (keeping recent KV lowers the reset spike and first-4 warp error): **SUPPORTED** [True, True, True, True]
- VD-H4 (butterfly: masked + decoder + recent still within 2.0 dB of frozen M1's terminal PSNR): **SUPPORTED** [True, True]
- VD-H5 (D x R interaction on V1): descriptive, see the table.

## Cells

| input | schedule | cell (S D R) | valid | mask violations | V1 reset | Sink-less V4 | Sink-less E | first-4 E | terminal PSNR | first >= 35 dB |
|---|---|---|---|---|---|---|---|---|---|---|
| dog | OT-1 | zero - - | True | None | 8.12 | 1.76 | 2.021 | 3.156 | 44.3 | 66 |
| dog | OT-1 | zero - rec | True | 0 | 7.46 | 1.67 | 1.905 | 2.676 | 44.2 | 66 |
| dog | OT-1 | zero dec - | True | 0 | 4.18 | 1.96 | 1.836 | 2.302 | 44.3 | 66 |
| dog | OT-1 | zero dec rec | True | 0 | 2.25 | 1.85 | 1.660 | 1.541 | 44.2 | 66 |
| dog | OT-1 | mask - - | True | 0 | 7.91 | 1.67 | 2.010 | 3.206 | 44.3 | 65 |
| dog | OT-1 | mask - rec | True | 0 | 7.35 | 1.50 | 1.863 | 2.548 | 44.3 | 65 |
| dog | OT-1 | mask dec - | True | 0 | 4.17 | 1.89 | 1.823 | 2.344 | 44.3 | 65 |
| dog | OT-1 | mask dec rec | True | 0 | 2.00 | 1.68 | 1.623 | 1.428 | 44.3 | 65 |
| dog | OT-1 | encdec | True | 0 | 4.18 | 2.56 | 1.737 | 1.884 | 44.3 | 66 |
| dog | OT-L | zero - - | True | None | 9.24 | 2.15 | 1.798 | 2.682 | 44.9 | 162 |
| dog | OT-L | zero - rec | True | 0 | 8.34 | 2.14 | 1.781 | 2.582 | 44.9 | 162 |
| dog | OT-L | zero dec - | True | 0 | 3.36 | 2.21 | 1.719 | 1.759 | 44.9 | 162 |
| dog | OT-L | zero dec rec | True | 0 | 1.46 | 2.19 | 1.691 | 1.523 | 44.9 | 162 |
| dog | OT-L | mask - - | True | 0 | 9.16 | 1.95 | 1.784 | 2.724 | 45.0 | 161 |
| dog | OT-L | mask - rec | True | 0 | 8.28 | 1.95 | 1.757 | 2.525 | 45.0 | 160 |
| dog | OT-L | mask dec - | True | 0 | 3.30 | 2.02 | 1.704 | 1.791 | 45.0 | 161 |
| dog | OT-L | mask dec rec | True | 0 | 1.29 | 1.99 | 1.666 | 1.457 | 45.0 | 160 |
| dog | OT-L | encdec | True | 0 | 3.36 | 2.40 | 1.696 | 1.480 | 44.9 | 162 |
| butterfly-feeding-slow-motion | OT-1 | zero - - | True | None | 3.30 | 0.70 | 1.336 | 2.128 | 31.3 | 66 |
| butterfly-feeding-slow-motion | OT-1 | zero - rec | True | 0 | 2.66 | 0.72 | 1.262 | 1.650 | 31.4 | 66 |
| butterfly-feeding-slow-motion | OT-1 | zero dec - | True | 0 | 1.31 | 1.06 | 1.268 | 1.643 | 31.3 | 66 |
| butterfly-feeding-slow-motion | OT-1 | zero dec rec | True | 0 | 0.90 | 1.08 | 1.199 | 1.199 | 31.4 | 66 |
| butterfly-feeding-slow-motion | OT-1 | mask - - | True | 0 | 3.22 | 0.76 | 1.372 | 2.116 | 30.9 | 66 |
| butterfly-feeding-slow-motion | OT-1 | mask - rec | True | 0 | 2.62 | 0.81 | 1.306 | 1.715 | 31.0 | 67 |
| butterfly-feeding-slow-motion | OT-1 | mask dec - | True | 0 | 1.28 | 1.11 | 1.305 | 1.637 | 30.9 | 66 |
| butterfly-feeding-slow-motion | OT-1 | mask dec rec | True | 0 | 0.88 | 1.15 | 1.243 | 1.267 | 31.0 | 67 |
| butterfly-feeding-slow-motion | OT-1 | encdec | True | 0 | 1.31 | 0.74 | 1.249 | 1.558 | 31.3 | 65 |
| butterfly-feeding-slow-motion | OT-L | zero - - | True | None | 1.97 | 1.27 | 1.244 | 1.960 | 28.6 | None |
| butterfly-feeding-slow-motion | OT-L | zero - rec | True | 0 | 1.81 | 1.32 | 1.235 | 1.758 | 28.6 | None |
| butterfly-feeding-slow-motion | OT-L | zero dec - | True | 0 | 0.85 | 1.34 | 1.223 | 1.437 | 28.6 | None |
| butterfly-feeding-slow-motion | OT-L | zero dec rec | True | 0 | 0.86 | 1.39 | 1.214 | 1.220 | 28.6 | None |
| butterfly-feeding-slow-motion | OT-L | mask - - | True | 0 | 1.92 | 1.27 | 1.278 | 1.936 | 28.6 | None |
| butterfly-feeding-slow-motion | OT-L | mask - rec | True | 0 | 1.77 | 1.35 | 1.269 | 1.745 | 28.6 | None |
| butterfly-feeding-slow-motion | OT-L | mask dec - | True | 0 | 0.82 | 1.34 | 1.258 | 1.428 | 28.6 | None |
| butterfly-feeding-slow-motion | OT-L | mask dec rec | True | 0 | 0.84 | 1.41 | 1.248 | 1.205 | 28.6 | None |
| butterfly-feeding-slow-motion | OT-L | encdec | True | 0 | 0.85 | 1.28 | 1.223 | 1.371 | 28.6 | None |
