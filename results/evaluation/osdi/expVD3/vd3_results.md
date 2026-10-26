# VD-3 results

Thresholds: `vd3_thresholds.json` (SHA-256 792a6ac77ffbca24), frozen after the Phase T review. Cells: 16 (12 confirmation). Validity problems: none.


## audi-snow-trail_s0|OT-1 (confirmation; REF V1 P99 2.84; thresholds {"dino": 0.1391, "dE_anchor": 4.7212, "dE_cross": 8.3307})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 4.41 (0.47; -) | -0.142 / 0.77 / 1.28 / 1.53 / 1.05 | -0.094, -0.141 | 1.73 (1.32) | -0.010 / -0.14 / 1.02 / 1.01 | -0.006 | 94 / 30.5 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 4.53 (0.47; 1.03) | -0.066 / -0.29 / 0.81 / 1.14 / 1.12 | -0.012, -0.104 | 1.85 (1.32) | -0.012 / 0.11 / 1.00 / 1.00 | 0.014 | 76 / 29.6 | 0.780 | 0.00 MB | 0.53 | n Y n Y Y |
| DR2 | True | 1.94 (0.47; 0.44) | -0.129 / 1.05 / 1.49 / 1.43 / 0.95 | -0.094, -0.104 | 1.73 (1.32) | -0.010 / -0.14 / 1.02 / 1.01 | -0.006 | 94 / 30.5 | 0.520 | 0.40 MB | 0.09 | Y Y n Y Y |
| DR2+TSin | True | 2.00 (0.47; 0.45) | -0.052 / 0.05 / 0.72 / 1.03 / 1.02 | -0.012, -0.062 | 1.85 (1.32) | -0.012 / 0.11 / 1.00 / 1.00 | 0.014 | 76 / 29.6 | 1.300 | 0.40 MB | 0.63 | Y Y Y Y Y |
| TSinKC | True | 3.35 (0.47; 0.76) | -0.053 / -0.01 / 0.71 / 1.04 / 1.03 | -0.012, -0.065 | 1.85 (1.32) | -0.012 / 0.11 / 1.00 / 1.00 | 0.014 | 76 / 29.6 | 0.780 | 0.00 MB | 0.62 | n Y Y Y Y |
| DR2stale | True | 4.05 (0.47; 0.92) | -0.131 / 1.14 / 1.58 / 1.48 / 0.99 | -0.094, -0.109 | 1.73 (1.32) | -0.010 / -0.14 / 1.02 / 1.01 | -0.006 | 94 / 30.5 | 0.521 | 0.40 MB | 0.07 | n Y n Y Y |
| DR2noise | True | 4.50 (0.47; 1.02) | -0.139 / 0.98 / 1.27 / 1.49 / 1.02 | -0.094, -0.135 | 1.73 (1.32) | -0.010 / -0.14 / 1.02 / 1.01 | -0.006 | 94 / 30.5 | 0.520 | 0.40 MB | 0.02 | n n n Y Y |

## audi-snow-trail_s0|OT-L (confirmation; REF V1 P99 2.84; thresholds {"dino": 0.2195, "dE_anchor": 8.6743, "dE_cross": 9.4334})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 6.23 (0.54; -) | -0.166 / 0.69 / 0.99 / 1.35 / 1.10 | -0.090, -0.145 | 1.23 (0.73) | -0.029 / -0.27 / 1.00 / 1.03 | -0.012 | None / 27.7 | - | 0.00 MB | - | n Y n Y n |
| TSin | True | 10.14 (0.54; 1.63) | -0.055 / 0.52 / 1.08 / 1.01 / 1.16 | -0.063, -0.002 | 0.87 (0.73) | -0.008 / 0.18 / 1.00 / 1.02 | -0.010 | None / 27.8 | 0.776 | 0.00 MB | 0.67 | n Y n Y Y |
| DR2 | True | 3.68 (0.54; 0.59) | -0.161 / 0.55 / 1.04 / 1.32 / 1.06 | -0.090, -0.103 | 1.23 (0.73) | -0.029 / -0.27 / 1.00 / 1.03 | -0.012 | None / 27.7 | 0.520 | 0.40 MB | 0.03 | n Y n Y Y |
| DR2+TSin | True | 2.97 (0.54; 0.48) | -0.052 / 0.52 / 1.00 / 0.96 / 1.11 | -0.063, 0.027 | 0.87 (0.73) | -0.008 / 0.18 / 1.00 / 1.02 | -0.010 | None / 27.8 | 1.299 | 0.40 MB | 0.69 | n Y n Y Y |
| TSinKC | True | 9.20 (0.54; 1.48) | -0.053 / 0.52 / 1.01 / 0.98 / 1.13 | -0.063, 0.021 | 0.87 (0.73) | -0.008 / 0.18 / 1.00 / 1.02 | -0.010 | None / 27.8 | 0.780 | 0.00 MB | 0.68 | n Y n Y Y |
| DR2stale | True | 5.78 (0.54; 0.93) | -0.162 / 0.60 / 1.07 / 1.33 / 1.08 | -0.090, -0.114 | 1.23 (0.73) | -0.029 / -0.27 / 1.00 / 1.03 | -0.012 | None / 27.7 | 0.522 | 0.40 MB | 0.02 | n Y n Y Y |
| DR2noise | True | 7.23 (0.54; 1.16) | -0.165 / 0.55 / 0.99 / 1.33 / 1.08 | -0.090, -0.136 | 1.23 (0.73) | -0.029 / -0.27 / 1.00 / 1.03 | -0.012 | None / 27.7 | 0.521 | 0.40 MB | 0.01 | n Y n Y Y |

## audi-snow-trail_s1|OT-1 (confirmation; REF V1 P99 3.22; thresholds {"dino": 0.1482, "dE_anchor": 4.8588, "dE_cross": 8.2824})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 4.23 (0.42; -) | -0.149 / 0.47 / 1.25 / 1.50 / 1.01 | -0.136, -0.088 | 1.52 (1.25) | -0.007 / -0.12 / 1.02 / 1.01 | -0.000 | None / 33.7 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 4.39 (0.42; 1.04) | -0.097 / -0.28 / 0.99 / 1.05 / 1.03 | -0.023, -0.146 | 1.67 (1.25) | -0.020 / 0.05 / 0.99 / 1.00 | 0.002 | None / 31.1 | 0.778 | 0.00 MB | 0.35 | n Y Y Y Y |
| DR2 | True | 1.87 (0.42; 0.44) | -0.137 / 0.82 / 1.29 / 1.41 / 0.91 | -0.136, -0.052 | 1.52 (1.25) | -0.007 / -0.12 / 1.02 / 1.01 | -0.000 | None / 33.7 | 0.520 | 0.40 MB | 0.08 | Y Y n Y Y |
| DR2+TSin | True | 2.01 (0.42; 0.48) | -0.089 / 0.01 / 0.76 / 0.95 / 0.94 | -0.023, -0.121 | 1.67 (1.25) | -0.020 / 0.05 / 0.99 / 1.00 | 0.002 | None / 31.1 | 1.301 | 0.40 MB | 0.40 | Y Y Y Y Y |
| TSinKC | True | 3.72 (0.42; 0.88) | -0.091 / -0.03 / 0.85 / 0.97 / 0.95 | -0.023, -0.127 | 1.67 (1.25) | -0.020 / 0.05 / 0.99 / 1.00 | 0.002 | None / 31.1 | 0.775 | 0.00 MB | 0.39 | n Y Y Y Y |
| DR2stale | True | 3.91 (0.42; 0.92) | -0.138 / 0.92 / 1.40 / 1.44 / 0.95 | -0.136, -0.055 | 1.52 (1.25) | -0.007 / -0.12 / 1.02 / 1.01 | -0.000 | None / 33.7 | 0.521 | 0.40 MB | 0.07 | n Y n Y Y |
| DR2noise | True | 4.37 (0.42; 1.03) | -0.147 / 0.75 / 1.11 / 1.46 / 0.99 | -0.136, -0.083 | 1.52 (1.25) | -0.007 / -0.12 / 1.02 / 1.01 | -0.000 | None / 33.7 | 0.520 | 0.40 MB | 0.01 | n Y n Y Y |

## audi-snow-trail_s1|OT-L (confirmation; REF V1 P99 3.22; thresholds {"dino": 0.2444, "dE_anchor": 8.4048, "dE_cross": 9.1301})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 5.78 (0.78; -) | -0.149 / 0.99 / 0.81 / 1.31 / 1.06 | -0.126, -0.087 | 1.26 (0.78) | -0.025 / -0.30 / 1.01 / 1.03 | 0.000 | None / 26.9 | - | 0.00 MB | - | n Y n Y n |
| TSin | True | 10.06 (0.78; 1.74) | -0.030 / 0.66 / 1.14 / 1.00 / 1.10 | -0.052, -0.019 | 0.92 (0.78) | 0.005 / 0.10 / 1.01 / 1.02 | 0.002 | None / 26.9 | 0.775 | 0.00 MB | 0.80 | n Y Y Y Y |
| DR2 | True | 3.53 (0.78; 0.61) | -0.145 / 0.84 / 0.75 / 1.29 / 1.03 | -0.126, -0.045 | 1.26 (0.78) | -0.025 / -0.30 / 1.01 / 1.03 | 0.000 | None / 26.9 | 0.520 | 0.40 MB | 0.03 | n Y n Y Y |
| DR2+TSin | True | 3.16 (0.78; 0.55) | -0.026 / 0.64 / 1.10 / 0.95 / 1.05 | -0.052, 0.022 | 0.92 (0.78) | 0.005 / 0.10 / 1.01 / 1.02 | 0.002 | None / 26.9 | 1.302 | 0.40 MB | 0.83 | Y Y Y Y Y |
| TSinKC | True | 9.46 (0.78; 1.64) | -0.027 / 0.64 / 1.08 / 0.97 / 1.07 | -0.052, 0.007 | 0.92 (0.78) | 0.005 / 0.10 / 1.01 / 1.02 | 0.002 | None / 26.9 | 0.780 | 0.00 MB | 0.82 | n Y Y Y Y |
| DR2stale | True | 5.49 (0.78; 0.95) | -0.146 / 0.88 / 0.80 / 1.30 / 1.05 | -0.126, -0.057 | 1.26 (0.78) | -0.025 / -0.30 / 1.01 / 1.03 | 0.000 | None / 26.9 | 0.520 | 0.40 MB | 0.02 | n Y n Y Y |
| DR2noise | True | 6.65 (0.78; 1.15) | -0.149 / 0.84 / 0.72 / 1.30 / 1.05 | -0.126, -0.085 | 1.26 (0.78) | -0.025 / -0.30 / 1.01 / 1.03 | 0.000 | None / 26.9 | 0.521 | 0.40 MB | 0.00 | n Y n Y Y |

## butterfly-feeding-slow-motion_s1|OT-1 (confirmation; REF V1 P99 1.25; thresholds {"dino": 0.0469, "dE_anchor": 0.5907, "dE_cross": 3.6462})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 3.35 (0.67; -) | -0.160 / 0.26 / 0.37 / 1.28 / 1.17 | -0.134, -0.083 | 1.07 (0.75) | -0.012 / -0.02 / 1.03 / 1.01 | 0.001 | 70 / 34.3 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 3.22 (0.67; 0.96) | -0.096 / 1.76 / 3.85 / 1.10 / 1.17 | -0.091, -0.027 | 0.78 (0.75) | -0.014 / 0.19 / 1.02 / 1.01 | 0.001 | 69 / 34.6 | 0.780 | 0.00 MB | 0.40 | n n n Y Y |
| DR2 | True | 1.22 (0.67; 0.36) | -0.152 / 0.07 / 0.58 / 1.22 / 1.12 | -0.134, -0.060 | 1.07 (0.75) | -0.012 / -0.02 / 1.03 / 1.01 | 0.001 | 70 / 34.3 | 0.521 | 0.40 MB | 0.05 | Y n n Y Y |
| DR2+TSin | True | 1.16 (0.67; 0.35) | -0.086 / 1.40 / 3.52 / 1.05 / 1.13 | -0.091, 0.002 | 0.78 (0.75) | -0.014 / 0.19 / 1.02 / 1.01 | 0.001 | 69 / 34.6 | 1.301 | 0.40 MB | 0.46 | Y n n Y Y |
| TSinKC | True | 1.86 (0.67; 0.56) | -0.087 / 1.62 / 3.75 / 1.06 / 1.13 | -0.091, 0.001 | 0.78 (0.75) | -0.014 / 0.19 / 1.02 / 1.01 | 0.001 | 69 / 34.6 | 0.781 | 0.00 MB | 0.46 | n n n Y Y |
| DR2stale | True | 1.37 (0.67; 0.41) | -0.152 / 0.08 / 0.58 / 1.22 / 1.12 | -0.134, -0.059 | 1.07 (0.75) | -0.012 / -0.02 / 1.03 / 1.01 | 0.001 | 70 / 34.3 | 0.521 | 0.40 MB | 0.05 | n n n Y Y |
| DR2noise | True | 2.85 (0.67; 0.85) | -0.160 / 0.25 / 0.63 / 1.26 / 1.15 | -0.134, -0.085 | 1.07 (0.75) | -0.012 / -0.02 / 1.03 / 1.01 | 0.001 | 70 / 34.3 | 0.521 | 0.40 MB | -0.00 | n n n Y Y |

## butterfly-feeding-slow-motion_s1|OT-L (confirmation; REF V1 P99 1.25; thresholds {"dino": 0.0272, "dE_anchor": 0.7536, "dE_cross": 3.4992})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 2.04 (0.73; -) | -0.137 / 0.24 / 0.99 / 1.20 / 1.16 | -0.130, -0.131 | 0.90 (0.76) | -0.026 / 0.03 / 1.01 / 0.99 | -0.004 | 192 / 31.8 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 1.82 (0.73; 0.89) | -0.016 / 1.67 / 3.44 / 1.04 / 1.18 | -0.034, -0.010 | 0.68 (0.76) | -0.023 / 0.28 / 1.01 / 0.99 | -0.004 | 193 / 31.4 | 0.777 | 0.00 MB | 0.88 | n n n Y Y |
| DR2 | True | 0.85 (0.73; 0.41) | -0.134 / 0.21 / 1.05 / 1.18 / 1.15 | -0.130, -0.106 | 0.90 (0.76) | -0.026 / 0.03 / 1.01 / 0.99 | -0.004 | 192 / 31.8 | 0.521 | 0.40 MB | 0.02 | Y n n Y Y |
| DR2+TSin | True | 0.79 (0.73; 0.39) | -0.012 / 1.59 / 3.36 / 1.03 / 1.17 | -0.034, 0.021 | 0.68 (0.76) | -0.023 / 0.28 / 1.01 / 0.99 | -0.004 | 193 / 31.4 | 1.298 | 0.40 MB | 0.91 | Y n n Y Y |
| TSinKC | True | 1.25 (0.73; 0.61) | -0.012 / 1.61 / 3.38 / 1.03 / 1.17 | -0.034, 0.022 | 0.68 (0.76) | -0.023 / 0.28 / 1.01 / 0.99 | -0.004 | 193 / 31.4 | 0.778 | 0.00 MB | 0.91 | Y n n Y Y |
| DR2stale | True | 0.90 (0.73; 0.44) | -0.134 / 0.21 / 1.05 / 1.18 / 1.15 | -0.130, -0.105 | 0.90 (0.76) | -0.026 / 0.03 / 1.01 / 0.99 | -0.004 | 192 / 31.8 | 0.520 | 0.40 MB | 0.02 | Y n n Y Y |
| DR2noise | True | 1.76 (0.73; 0.86) | -0.136 / 0.23 / 1.06 / 1.19 / 1.16 | -0.130, -0.124 | 0.90 (0.76) | -0.026 / 0.03 / 1.01 / 0.99 | -0.004 | 192 / 31.8 | 0.520 | 0.40 MB | 0.01 | n n n Y Y |

## dog_s1|OT-1 (confirmation; REF V1 P99 3.91; thresholds {"dino": 0.0368, "dE_anchor": 0.8969, "dE_cross": 1.5551})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 8.86 (1.20; -) | -0.444 / 1.83 / 2.12 / 2.04 / 1.38 | -0.421, -0.048 | 1.39 (1.04) | -0.006 / -0.06 / 1.09 / 1.05 | 0.000 | 65 / 43.9 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 8.95 (1.20; 1.01) | -0.026 / 0.87 / 1.25 / 1.46 / 1.37 | -0.013, -0.040 | 1.36 (1.04) | -0.000 / 0.10 / 0.99 / 1.00 | 0.000 | 64 / 43.0 | 0.779 | 0.00 MB | 0.94 | n Y n Y Y |
| DR2 | True | 4.60 (1.20; 0.52) | -0.433 / 1.60 / 2.19 / 1.85 / 1.23 | -0.421, -0.013 | 1.39 (1.04) | -0.006 / -0.06 / 1.09 / 1.05 | 0.000 | 65 / 43.9 | 0.520 | 0.40 MB | 0.03 | n n n Y Y |
| DR2+TSin | True | 3.55 (1.20; 0.40) | -0.017 / 0.78 / 1.17 / 1.26 / 1.21 | -0.013, -0.012 | 1.36 (1.04) | -0.000 / 0.10 / 0.99 / 1.00 | 0.000 | 64 / 43.0 | 1.296 | 0.40 MB | 0.96 | Y Y n Y Y |
| TSinKC | True | 5.43 (1.20; 0.61) | -0.017 / 0.67 / 1.00 / 1.28 / 1.23 | -0.013, -0.014 | 1.36 (1.04) | -0.000 / 0.10 / 0.99 / 1.00 | 0.000 | 64 / 43.0 | 0.778 | 0.00 MB | 0.96 | n Y n Y Y |
| DR2stale | True | 6.29 (1.20; 0.71) | -0.438 / 1.63 / 2.17 / 1.90 / 1.27 | -0.421, -0.029 | 1.39 (1.04) | -0.006 / -0.06 / 1.09 / 1.05 | 0.000 | 65 / 43.9 | 0.521 | 0.40 MB | 0.01 | n n n Y Y |
| DR2noise | True | 10.92 (1.20; 1.23) | -0.443 / 2.09 / 2.94 / 2.11 / 1.45 | -0.421, -0.044 | 1.39 (1.04) | -0.006 / -0.06 / 1.09 / 1.05 | 0.000 | 65 / 43.9 | 0.521 | 0.40 MB | 0.00 | n n n Y Y |

## dog_s1|OT-L (confirmation; REF V1 P99 3.91; thresholds {"dino": 0.0264, "dE_anchor": 0.8787, "dE_cross": 1.6065})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 9.18 (0.83; -) | -0.357 / 1.48 / 2.44 / 1.83 / 1.34 | -0.383, -0.092 | 2.09 (1.11) | -0.008 / 0.03 / 1.12 / 1.07 | 0.000 | 160 / 42.0 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 10.42 (0.83; 1.14) | -0.015 / 0.53 / 1.12 / 1.21 / 1.30 | -0.012, -0.036 | 1.49 (1.11) | 0.000 / 0.06 / 1.02 / 1.02 | -0.000 | 161 / 44.3 | 0.777 | 0.00 MB | 0.96 | n Y n Y Y |
| DR2 | True | 4.09 (0.83; 0.45) | -0.353 / 1.46 / 2.46 / 1.77 / 1.28 | -0.383, -0.059 | 2.09 (1.11) | -0.008 / 0.03 / 1.12 / 1.07 | 0.000 | 160 / 42.0 | 0.520 | 0.40 MB | 0.01 | n n n Y Y |
| DR2+TSin | True | 3.77 (0.83; 0.41) | -0.011 / 0.51 / 1.11 / 1.13 / 1.23 | -0.012, 0.001 | 1.49 (1.11) | 0.000 / 0.06 / 1.02 / 1.02 | -0.000 | 161 / 44.3 | 1.298 | 0.40 MB | 0.97 | Y Y n Y Y |
| TSinKC | True | 4.76 (0.83; 0.52) | -0.011 / 0.46 / 1.05 / 1.14 / 1.24 | -0.012, -0.000 | 1.49 (1.11) | 0.000 / 0.06 / 1.02 / 1.02 | -0.000 | 161 / 44.3 | 0.782 | 0.00 MB | 0.97 | n Y n Y Y |
| DR2stale | True | 5.91 (0.83; 0.64) | -0.355 / 1.45 / 2.47 / 1.79 / 1.30 | -0.383, -0.070 | 2.09 (1.11) | -0.008 / 0.03 / 1.12 / 1.07 | 0.000 | 160 / 42.0 | 0.520 | 0.40 MB | 0.01 | n n n Y Y |
| DR2noise | True | 9.38 (0.83; 1.02) | -0.357 / 1.55 / 2.71 / 1.85 / 1.36 | -0.383, -0.088 | 2.09 (1.11) | -0.008 / 0.03 / 1.12 / 1.07 | 0.000 | 160 / 42.0 | 0.521 | 0.40 MB | 0.00 | n n n Y Y |

## train_s0|OT-1 (confirmation; REF V1 P99 6.49; thresholds {"dino": 0.0359, "dE_anchor": 1.0613, "dE_cross": 2.6621})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 4.64 (1.08; -) | -0.273 / 0.40 / 1.88 / 1.50 / 1.28 | -0.236, -0.121 | 1.48 (0.85) | -0.013 / -0.01 / 1.05 / 1.04 | 0.002 | 68 / 32.7 | - | 0.00 MB | - | Y n n Y n |
| TSin | True | 4.10 (1.08; 0.88) | -0.060 / 0.78 / 1.72 / 1.23 / 1.30 | -0.044, -0.053 | 0.97 (0.85) | -0.010 / 0.22 / 1.03 / 1.03 | -0.003 | 70 / 34.7 | 0.778 | 0.00 MB | 0.78 | Y n n Y Y |
| DR2 | True | 2.15 (1.08; 0.46) | -0.271 / 0.62 / 1.73 / 1.41 / 1.18 | -0.236, -0.115 | 1.48 (0.85) | -0.013 / -0.01 / 1.05 / 1.04 | 0.002 | 68 / 32.7 | 0.521 | 0.40 MB | 0.01 | Y n n Y Y |
| DR2+TSin | True | 1.89 (1.08; 0.41) | -0.056 / 0.83 / 1.68 / 1.15 / 1.23 | -0.044, -0.042 | 0.97 (0.85) | -0.010 / 0.22 / 1.03 / 1.03 | -0.003 | 70 / 34.7 | 1.295 | 0.40 MB | 0.79 | Y n n Y Y |
| TSinKC | True | 3.30 (1.08; 0.71) | -0.057 / 0.89 / 1.75 / 1.17 / 1.24 | -0.044, -0.044 | 0.97 (0.85) | -0.010 / 0.22 / 1.03 / 1.03 | -0.003 | 70 / 34.7 | 0.777 | 0.00 MB | 0.79 | Y n n Y Y |
| DR2stale | True | 2.67 (1.08; 0.57) | -0.271 / 0.63 / 1.74 / 1.42 / 1.19 | -0.236, -0.116 | 1.48 (0.85) | -0.013 / -0.01 / 1.05 / 1.04 | 0.002 | 68 / 32.7 | 0.521 | 0.40 MB | 0.01 | Y n n Y Y |
| DR2noise | True | 4.51 (1.08; 0.97) | -0.279 / 0.58 / 1.92 / 1.46 / 1.24 | -0.236, -0.139 | 1.48 (0.85) | -0.013 / -0.01 / 1.05 / 1.04 | 0.002 | 68 / 32.7 | 0.521 | 0.40 MB | -0.02 | Y n n Y Y |

## train_s0|OT-L (confirmation; REF V1 P99 6.49; thresholds {"dino": 0.0238, "dE_anchor": 1.2607, "dE_cross": 2.6357})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 7.93 (1.21; -) | -0.238 / 1.50 / 2.53 / 1.42 / 1.31 | -0.229, -0.136 | 0.59 (0.64) | -0.013 / -0.16 / 1.03 / 1.03 | -0.002 | 179 / 33.7 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 6.49 (1.21; 0.82) | -0.044 / 0.41 / 0.50 / 1.08 / 1.21 | -0.030, -0.073 | 1.23 (0.64) | -0.005 / -0.21 / 0.98 / 1.03 | -0.001 | 179 / 33.7 | 0.778 | 0.00 MB | 0.81 | n n n Y Y |
| DR2 | True | 3.55 (1.21; 0.45) | -0.237 / 1.45 / 2.50 / 1.39 / 1.28 | -0.229, -0.127 | 0.59 (0.64) | -0.013 / -0.16 / 1.03 / 1.03 | -0.002 | 179 / 33.7 | 0.521 | 0.40 MB | 0.00 | Y n n Y Y |
| DR2+TSin | True | 2.90 (1.21; 0.37) | -0.042 / 0.38 / 0.59 / 1.06 / 1.19 | -0.030, -0.059 | 1.23 (0.64) | -0.005 / -0.21 / 0.98 / 1.03 | -0.001 | 179 / 33.7 | 1.294 | 0.40 MB | 0.82 | Y n n Y Y |
| TSinKC | True | 5.35 (1.21; 0.67) | -0.043 / 0.38 / 0.62 / 1.07 / 1.20 | -0.030, -0.063 | 1.23 (0.64) | -0.005 / -0.21 / 0.98 / 1.03 | -0.001 | 179 / 33.7 | 0.778 | 0.00 MB | 0.82 | Y n n Y Y |
| DR2stale | True | 4.13 (1.21; 0.52) | -0.237 / 1.45 / 2.50 / 1.39 / 1.29 | -0.229, -0.129 | 0.59 (0.64) | -0.013 / -0.16 / 1.03 / 1.03 | -0.002 | 179 / 33.7 | 0.521 | 0.40 MB | 0.00 | Y n n Y Y |
| DR2noise | True | 6.83 (1.21; 0.86) | -0.240 / 1.48 / 2.52 / 1.41 / 1.30 | -0.229, -0.154 | 0.59 (0.64) | -0.013 / -0.16 / 1.03 / 1.03 | -0.002 | 179 / 33.7 | 0.520 | 0.40 MB | -0.01 | n n n Y Y |

## train_s1|OT-1 (confirmation; REF V1 P99 6.15; thresholds {"dino": 0.0458, "dE_anchor": 1.2315, "dE_cross": 2.483})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 5.12 (1.14; -) | -0.290 / 1.05 / 2.09 / 1.62 / 1.38 | -0.251, -0.113 | 1.97 (0.86) | -0.023 / 0.17 / 1.06 / 1.04 | -0.003 | 91 / 34.0 | - | 0.00 MB | - | Y n n Y n |
| TSin | True | 4.53 (1.14; 0.89) | -0.057 / 0.44 / 0.88 / 1.24 / 1.28 | -0.042, -0.022 | 0.77 (0.86) | -0.013 / -0.02 / 1.02 / 0.99 | -0.005 | 91 / 34.0 | 0.780 | 0.00 MB | 0.80 | Y n n Y Y |
| DR2 | True | 2.33 (1.14; 0.46) | -0.288 / 1.31 / 2.04 / 1.52 / 1.29 | -0.250, -0.106 | 1.97 (0.86) | -0.023 / 0.17 / 1.06 / 1.04 | -0.003 | 91 / 34.0 | 0.520 | 0.40 MB | 0.01 | Y n n Y Y |
| DR2+TSin | True | 2.01 (1.14; 0.39) | -0.052 / 0.71 / 1.19 / 1.15 / 1.20 | -0.042, -0.009 | 0.77 (0.86) | -0.013 / -0.02 / 1.02 / 0.99 | -0.005 | 91 / 34.0 | 1.300 | 0.40 MB | 0.82 | Y n n Y Y |
| TSinKC | True | 3.42 (1.14; 0.67) | -0.052 / 0.72 / 1.19 / 1.17 / 1.22 | -0.042, -0.009 | 0.77 (0.86) | -0.013 / -0.02 / 1.02 / 0.99 | -0.005 | 91 / 34.0 | 0.781 | 0.00 MB | 0.82 | Y n n Y Y |
| DR2stale | True | 2.72 (1.14; 0.53) | -0.288 / 1.30 / 2.04 / 1.53 / 1.29 | -0.251, -0.106 | 1.97 (0.86) | -0.023 / 0.17 / 1.06 / 1.04 | -0.003 | 91 / 34.0 | 0.520 | 0.40 MB | 0.01 | Y n n Y Y |
| DR2noise | True | 4.48 (1.14; 0.87) | -0.297 / 1.29 / 2.19 / 1.58 / 1.34 | -0.251, -0.134 | 1.97 (0.86) | -0.023 / 0.17 / 1.06 / 1.04 | -0.003 | 91 / 34.0 | 0.521 | 0.40 MB | -0.02 | Y n n Y Y |

## train_s1|OT-L (confirmation; REF V1 P99 6.15; thresholds {"dino": 0.0242, "dE_anchor": 0.9311, "dE_cross": 2.2697})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 8.62 (1.04; -) | -0.258 / 1.74 / 2.72 / 1.45 / 1.34 | -0.249, -0.126 | 0.84 (0.72) | -0.010 / 0.13 / 1.05 / 1.06 | -0.003 | 166 / 34.5 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 6.92 (1.04; 0.80) | -0.050 / 0.63 / 0.80 / 1.07 / 1.23 | -0.033, -0.063 | 1.45 (0.72) | -0.010 / 0.05 / 0.98 / 1.04 | -0.003 | 166 / 34.6 | 0.779 | 0.00 MB | 0.81 | n n n Y Y |
| DR2 | True | 3.82 (1.04; 0.44) | -0.256 / 1.70 / 2.70 / 1.42 / 1.32 | -0.249, -0.114 | 0.84 (0.72) | -0.010 / 0.13 / 1.05 / 1.06 | -0.003 | 166 / 34.5 | 0.520 | 0.40 MB | 0.01 | Y n n Y Y |
| DR2+TSin | True | 3.10 (1.04; 0.36) | -0.049 / 0.59 / 0.80 / 1.04 / 1.20 | -0.033, -0.051 | 1.45 (0.72) | -0.010 / 0.05 / 0.98 / 1.04 | -0.003 | 166 / 34.6 | 1.298 | 0.40 MB | 0.81 | Y n n Y Y |
| TSinKC | True | 5.39 (1.04; 0.63) | -0.049 / 0.60 / 0.86 / 1.05 / 1.21 | -0.033, -0.052 | 1.45 (0.72) | -0.010 / 0.05 / 0.98 / 1.04 | -0.003 | 166 / 34.6 | 0.781 | 0.00 MB | 0.81 | Y n n Y Y |
| DR2stale | True | 4.47 (1.04; 0.52) | -0.256 / 1.70 / 2.70 / 1.42 / 1.32 | -0.249, -0.114 | 0.84 (0.72) | -0.010 / 0.13 / 1.05 / 1.06 | -0.003 | 166 / 34.5 | 0.521 | 0.40 MB | 0.00 | Y n n Y Y |
| DR2noise | True | 6.50 (1.04; 0.75) | -0.258 / 1.73 / 2.73 / 1.44 / 1.33 | -0.249, -0.131 | 0.84 (0.72) | -0.010 / 0.13 / 1.05 / 1.06 | -0.003 | 166 / 34.5 | 0.521 | 0.40 MB | -0.00 | n n n Y Y |

## butterfly-feeding-slow-motion_s0|OT-1 (replication; REF V1 P99 1.40; thresholds {"dino": 0.0558, "dE_anchor": 0.6723, "dE_cross": 4.0346})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 3.30 (0.75; -) | -0.173 / 0.08 / 0.70 / 1.34 / 1.18 | -0.129, -0.124 | 0.95 (0.66) | -0.012 / -0.00 / 1.03 / 1.01 | -0.002 | 66 / 31.3 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 3.03 (0.75; 0.92) | -0.051 / 1.45 / 3.13 / 1.15 / 1.15 | -0.044, -0.036 | 0.72 (0.66) | -0.004 / 0.15 / 1.02 / 1.01 | -0.004 | 65 / 30.5 | 0.779 | 0.00 MB | 0.71 | n n n Y Y |
| DR2 | True | 1.29 (0.75; 0.39) | -0.164 / -0.09 / 0.99 / 1.27 / 1.13 | -0.129, -0.095 | 0.95 (0.66) | -0.012 / -0.00 / 1.03 / 1.01 | -0.002 | 66 / 31.3 | 0.520 | 0.40 MB | 0.05 | Y n n Y Y |
| DR2+TSin | True | 1.20 (0.75; 0.36) | -0.040 / 1.08 / 2.79 / 1.09 / 1.11 | -0.044, -0.002 | 0.72 (0.66) | -0.004 / 0.15 / 1.02 / 1.01 | -0.004 | 65 / 30.5 | 1.296 | 0.40 MB | 0.77 | Y n n Y Y |
| TSinKC | True | 1.75 (0.75; 0.53) | -0.040 / 1.22 / 2.94 / 1.10 / 1.12 | -0.044, -0.003 | 0.72 (0.66) | -0.004 / 0.15 / 1.02 / 1.01 | -0.004 | 65 / 30.5 | 0.778 | 0.00 MB | 0.77 | n n n Y Y |
| DR2stale | True | 1.44 (0.75; 0.44) | -0.164 / -0.09 / 0.99 / 1.27 / 1.13 | -0.129, -0.094 | 0.95 (0.66) | -0.012 / -0.00 / 1.03 / 1.01 | -0.002 | 66 / 31.3 | 0.520 | 0.40 MB | 0.06 | n n n Y Y |
| DR2noise | True | 2.92 (0.75; 0.89) | -0.173 / 0.07 / 1.00 / 1.31 / 1.16 | -0.129, -0.120 | 0.95 (0.66) | -0.012 / -0.00 / 1.03 / 1.01 | -0.002 | 66 / 31.3 | 0.519 | 0.40 MB | 0.01 | n n n Y Y |

## butterfly-feeding-slow-motion_s0|OT-L (replication; REF V1 P99 1.40; thresholds {"dino": 0.0386, "dE_anchor": 0.7829, "dE_cross": 3.7373})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 1.97 (0.70; -) | -0.150 / 0.19 / 1.27 / 1.24 / 1.19 | -0.161, -0.109 | 0.84 (0.73) | -0.041 / 0.05 / 1.00 / 0.98 | 0.002 | None / 28.6 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 1.74 (0.70; 0.88) | -0.021 / 1.41 / 3.27 / 1.07 / 1.18 | -0.035, 0.006 | 0.63 (0.73) | -0.029 / 0.28 / 0.99 / 0.98 | 0.002 | None / 28.6 | 0.780 | 0.00 MB | 0.86 | n n n Y Y |
| DR2 | True | 0.82 (0.70; 0.42) | -0.148 / 0.15 / 1.32 / 1.22 / 1.17 | -0.161, -0.088 | 0.84 (0.73) | -0.041 / 0.05 / 1.00 / 0.98 | 0.002 | None / 28.6 | 0.521 | 0.40 MB | 0.01 | Y n n Y Y |
| DR2+TSin | True | 0.75 (0.70; 0.38) | -0.018 / 1.32 / 3.18 / 1.06 / 1.16 | -0.035, 0.029 | 0.63 (0.73) | -0.029 / 0.28 / 0.99 / 0.98 | 0.002 | None / 28.6 | 1.301 | 0.40 MB | 0.88 | Y n n Y Y |
| TSinKC | True | 1.21 (0.70; 0.61) | -0.018 / 1.34 / 3.21 / 1.06 / 1.17 | -0.035, 0.031 | 0.63 (0.73) | -0.029 / 0.28 / 0.99 / 0.98 | 0.002 | None / 28.6 | 0.777 | 0.00 MB | 0.88 | Y n n Y Y |
| DR2stale | True | 0.88 (0.70; 0.45) | -0.148 / 0.16 / 1.32 / 1.22 / 1.17 | -0.161, -0.088 | 0.84 (0.73) | -0.041 / 0.05 / 1.00 / 0.98 | 0.002 | None / 28.6 | 0.520 | 0.40 MB | 0.02 | Y n n Y Y |
| DR2noise | True | 1.75 (0.70; 0.89) | -0.149 / 0.17 / 1.32 / 1.24 / 1.18 | -0.161, -0.105 | 0.84 (0.73) | -0.041 / 0.05 / 1.00 / 0.98 | 0.002 | None / 28.6 | 0.521 | 0.40 MB | 0.00 | n n n Y Y |

## dog_s0|OT-1 (replication; REF V1 P99 3.96; thresholds {"dino": 0.0356, "dE_anchor": 0.828, "dE_cross": 1.4787})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 8.12 (1.34; -) | -0.425 / 1.51 / 1.76 / 2.02 / 1.33 | -0.353, -0.182 | 1.50 (1.17) | -0.007 / -0.01 / 1.08 / 1.03 | -0.000 | 66 / 44.3 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 8.66 (1.34; 1.07) | -0.023 / 0.86 / 1.22 / 1.43 / 1.34 | -0.009, -0.036 | 1.66 (1.17) | -0.001 / 0.09 / 1.00 / 0.99 | -0.000 | 65 / 43.3 | 0.779 | 0.00 MB | 0.95 | n n n Y Y |
| DR2 | True | 4.36 (1.34; 0.54) | -0.412 / 1.26 / 1.82 / 1.84 / 1.18 | -0.353, -0.146 | 1.50 (1.17) | -0.007 / -0.01 / 1.08 / 1.03 | -0.000 | 66 / 44.3 | 0.520 | 0.40 MB | 0.03 | n n n Y Y |
| DR2+TSin | True | 3.53 (1.34; 0.43) | -0.014 / 0.78 / 1.14 / 1.22 / 1.18 | -0.009, -0.008 | 1.66 (1.17) | -0.001 / 0.09 / 1.00 / 0.99 | -0.000 | 65 / 43.3 | 1.296 | 0.40 MB | 0.97 | Y Y n Y Y |
| TSinKC | True | 5.60 (1.34; 0.69) | -0.015 / 0.70 / 0.96 / 1.25 / 1.20 | -0.009, -0.010 | 1.66 (1.17) | -0.001 / 0.09 / 1.00 / 0.99 | -0.000 | 65 / 43.3 | 0.778 | 0.00 MB | 0.97 | n Y n Y Y |
| DR2stale | True | 6.07 (1.34; 0.75) | -0.418 / 1.27 / 1.81 / 1.89 / 1.22 | -0.353, -0.161 | 1.50 (1.17) | -0.007 / -0.01 / 1.08 / 1.03 | -0.000 | 66 / 44.3 | 0.521 | 0.40 MB | 0.02 | n n n Y Y |
| DR2noise | True | 10.60 (1.34; 1.31) | -0.420 / 1.79 / 2.57 / 2.10 / 1.39 | -0.353, -0.170 | 1.50 (1.17) | -0.007 / -0.01 / 1.08 / 1.03 | -0.000 | 66 / 44.3 | 0.520 | 0.40 MB | 0.01 | n n n Y Y |

## dog_s0|OT-L (replication; REF V1 P99 3.96; thresholds {"dino": 0.0266, "dE_anchor": 0.9373, "dE_cross": 1.6038})

| condition | valid | P1 V1 reset (paired REF; x M1) | P2 D_c / C_c / dE x / E / motion | P2 late D_c, excess drift X | P3 V1 bind (paired REF) | post-bind-20 D_c / C_c / E / motion | last-10 D_c | PSNR first >= 35 / terminal (diagnostic) | cost s | bytes | DINO gap closed | P1 P2a P2b P3 cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frozen M1 | True | 9.24 (0.92; -) | -0.378 / 1.14 / 2.15 / 1.80 / 1.31 | -0.398, -0.019 | 2.28 (1.21) | -0.006 / 0.04 / 1.11 / 1.05 | 0.000 | 162 / 44.9 | - | 0.00 MB | - | n n n Y n |
| TSin | True | 10.38 (0.92; 1.12) | -0.006 / 1.05 / 1.62 / 1.15 / 1.24 | -0.003, -0.043 | 1.69 (1.21) | 0.000 / 0.11 / 1.01 / 1.01 | -0.000 | 162 / 44.9 | 0.779 | 0.00 MB | 0.98 | n n n Y Y |
| DR2 | True | 3.72 (0.92; 0.40) | -0.374 / 1.11 / 2.17 / 1.73 / 1.24 | -0.398, 0.017 | 2.28 (1.21) | -0.006 / 0.04 / 1.11 / 1.05 | 0.000 | 162 / 44.9 | 0.521 | 0.40 MB | 0.01 | Y n n Y Y |
| DR2+TSin | True | 3.80 (0.92; 0.41) | -0.002 / 1.03 / 1.60 / 1.08 / 1.17 | -0.003, -0.003 | 1.69 (1.21) | 0.000 / 0.11 / 1.01 / 1.01 | -0.000 | 162 / 44.9 | 1.295 | 0.40 MB | 0.99 | Y n n Y Y |
| TSinKC | True | 4.75 (0.92; 0.51) | -0.002 / 0.98 / 1.55 / 1.08 / 1.18 | -0.003, -0.005 | 1.69 (1.21) | 0.000 / 0.11 / 1.01 / 1.01 | -0.000 | 162 / 44.9 | 0.775 | 0.00 MB | 0.99 | n n n Y Y |
| DR2stale | True | 5.46 (0.92; 0.59) | -0.374 / 1.10 / 2.18 / 1.75 / 1.26 | -0.398, 0.012 | 2.28 (1.21) | -0.006 / 0.04 / 1.11 / 1.05 | 0.000 | 162 / 44.9 | 0.520 | 0.40 MB | 0.01 | n n n Y Y |
| DR2noise | True | 9.13 (0.92; 0.99) | -0.377 / 1.20 / 2.42 / 1.81 / 1.32 | -0.398, -0.010 | 2.28 (1.21) | -0.006 / 0.04 / 1.11 / 1.05 | 0.000 | 162 / 44.9 | 0.520 | 0.40 MB | 0.00 | n n n Y Y |

## GO / NO-GO (phase-level discrimination; primary thresholds A)

Per confirmation cell and phase: FAIL / DISCRIMINATIVE PASS (frozen M1 violates that phase there) / NON-DISCRIMINATIVE PASS; P3 (no-harm) and cost: PASS / FAIL. Continuity: NO-GO on any FAIL or inspection veto; GO if every input has a discriminative pass in P1 and in P2 (P2a or P2b); otherwise INCONCLUSIVE. Identity preservation: ESTABLISHED only if every input has a discriminative P2a pass.

### DR2+TSin: continuity **NO-GO**, identity preservation **NO-GO** (inspection vetoes ['train_s0|OT-L', 'train_s0|OT-1', 'dog_s1|OT-1', 'train_s1|OT-L', 'audi-snow-trail_s1|OT-L', 'audi-snow-trail_s0|OT-1', 'train_s1|OT-1', 'audi-snow-trail_s0|OT-L'])

| cell | P1 | P2a | P2b | P3 | cost |
|---|---|---|---|---|---|
| audi-snow-trail_s0|OT-1 | DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | PASS | PASS |
| audi-snow-trail_s0|OT-L | FAIL | NON-DISCRIMINATIVE PASS | FAIL | PASS | PASS |
| audi-snow-trail_s1|OT-1 | DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | PASS | PASS |
| audi-snow-trail_s1|OT-L | DISCRIMINATIVE PASS | NON-DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | PASS | PASS |
| butterfly-feeding-slow-motion_s1|OT-1 | DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
| butterfly-feeding-slow-motion_s1|OT-L | DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
| dog_s1|OT-1 | DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | FAIL | PASS | PASS |
| dog_s1|OT-L | DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | FAIL | PASS | PASS |
| train_s0|OT-1 | NON-DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
| train_s0|OT-L | DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
| train_s1|OT-1 | NON-DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
| train_s1|OT-L | DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
- P1 non-discriminative passes: ['train_s0|OT-1', 'train_s1|OT-1']
- P2a non-discriminative passes: ['audi-snow-trail_s0|OT-L', 'audi-snow-trail_s1|OT-L']
- P2b non-discriminative passes: none

### TSinKC: continuity **NO-GO**, identity preservation **NO-GO** (inspection vetoes ['train_s0|OT-L', 'train_s0|OT-1', 'dog_s1|OT-1', 'audi-snow-trail_s1|OT-1', 'train_s1|OT-L', 'audi-snow-trail_s1|OT-L', 'train_s1|OT-1', 'audi-snow-trail_s0|OT-L'])

| cell | P1 | P2a | P2b | P3 | cost |
|---|---|---|---|---|---|
| audi-snow-trail_s0|OT-1 | FAIL | DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | PASS | PASS |
| audi-snow-trail_s0|OT-L | FAIL | NON-DISCRIMINATIVE PASS | FAIL | PASS | PASS |
| audi-snow-trail_s1|OT-1 | FAIL | DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | PASS | PASS |
| audi-snow-trail_s1|OT-L | FAIL | NON-DISCRIMINATIVE PASS | DISCRIMINATIVE PASS | PASS | PASS |
| butterfly-feeding-slow-motion_s1|OT-1 | FAIL | FAIL | FAIL | PASS | PASS |
| butterfly-feeding-slow-motion_s1|OT-L | DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
| dog_s1|OT-1 | FAIL | DISCRIMINATIVE PASS | FAIL | PASS | PASS |
| dog_s1|OT-L | FAIL | DISCRIMINATIVE PASS | FAIL | PASS | PASS |
| train_s0|OT-1 | NON-DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
| train_s0|OT-L | DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
| train_s1|OT-1 | NON-DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
| train_s1|OT-L | DISCRIMINATIVE PASS | FAIL | FAIL | PASS | PASS |
- P1 non-discriminative passes: ['train_s0|OT-1', 'train_s1|OT-1']
- P2a non-discriminative passes: ['audi-snow-trail_s0|OT-L', 'audi-snow-trail_s1|OT-L']
- P2b non-discriminative passes: none

## Sensitivity (threshold sets B and C; never the verdict)

- B / DR2+TSin: continuity NO-GO, identity NO-GO; FAIL phases [('audi-snow-trail_s0|OT-L', 'P1'), ('audi-snow-trail_s0|OT-L', 'P2b'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P2b'), ('butterfly-feeding-slow-motion_s1|OT-L', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-L', 'P2b'), ('dog_s1|OT-1', 'P2a'), ('dog_s1|OT-1', 'P2b'), ('dog_s1|OT-L', 'P2b'), ('train_s0|OT-1', 'P2a'), ('train_s0|OT-1', 'P2b'), ('train_s0|OT-L', 'P2a'), ('train_s0|OT-L', 'P2b'), ('train_s1|OT-1', 'P2a'), ('train_s1|OT-1', 'P2b'), ('train_s1|OT-L', 'P2a'), ('train_s1|OT-L', 'P2b')]
- B / TSinKC: continuity NO-GO, identity NO-GO; FAIL phases [('audi-snow-trail_s0|OT-1', 'P1'), ('audi-snow-trail_s0|OT-L', 'P1'), ('audi-snow-trail_s0|OT-L', 'P2b'), ('audi-snow-trail_s1|OT-1', 'P1'), ('audi-snow-trail_s1|OT-L', 'P1'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P1'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P2b'), ('butterfly-feeding-slow-motion_s1|OT-L', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-L', 'P2b'), ('dog_s1|OT-1', 'P1'), ('dog_s1|OT-1', 'P2b'), ('dog_s1|OT-L', 'P1'), ('dog_s1|OT-L', 'P2b'), ('train_s0|OT-1', 'P2a'), ('train_s0|OT-1', 'P2b'), ('train_s0|OT-L', 'P2a'), ('train_s0|OT-L', 'P2b'), ('train_s1|OT-1', 'P2a'), ('train_s1|OT-1', 'P2b'), ('train_s1|OT-L', 'P2a'), ('train_s1|OT-L', 'P2b')]
- C / DR2+TSin: continuity NO-GO, identity NO-GO; FAIL phases [('audi-snow-trail_s0|OT-1', 'P2a'), ('audi-snow-trail_s0|OT-L', 'P1'), ('audi-snow-trail_s0|OT-L', 'P2a'), ('audi-snow-trail_s0|OT-L', 'P2b'), ('audi-snow-trail_s1|OT-1', 'P2a'), ('audi-snow-trail_s1|OT-L', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P2b'), ('butterfly-feeding-slow-motion_s1|OT-L', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-L', 'P2b'), ('dog_s1|OT-1', 'P2a'), ('dog_s1|OT-1', 'P2b'), ('dog_s1|OT-1', 'P3'), ('dog_s1|OT-L', 'P2a'), ('dog_s1|OT-L', 'P2b'), ('train_s0|OT-1', 'P2a'), ('train_s0|OT-1', 'P2b'), ('train_s0|OT-L', 'P2a'), ('train_s0|OT-L', 'P2b'), ('train_s1|OT-1', 'P2a'), ('train_s1|OT-1', 'P2b'), ('train_s1|OT-L', 'P2a'), ('train_s1|OT-L', 'P2b')]
- C / TSinKC: continuity NO-GO, identity NO-GO; FAIL phases [('audi-snow-trail_s0|OT-1', 'P1'), ('audi-snow-trail_s0|OT-1', 'P2a'), ('audi-snow-trail_s0|OT-L', 'P1'), ('audi-snow-trail_s0|OT-L', 'P2a'), ('audi-snow-trail_s0|OT-L', 'P2b'), ('audi-snow-trail_s1|OT-1', 'P1'), ('audi-snow-trail_s1|OT-1', 'P2a'), ('audi-snow-trail_s1|OT-L', 'P1'), ('audi-snow-trail_s1|OT-L', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P1'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-1', 'P2b'), ('butterfly-feeding-slow-motion_s1|OT-L', 'P2a'), ('butterfly-feeding-slow-motion_s1|OT-L', 'P2b'), ('dog_s1|OT-1', 'P1'), ('dog_s1|OT-1', 'P2a'), ('dog_s1|OT-1', 'P2b'), ('dog_s1|OT-1', 'P3'), ('dog_s1|OT-L', 'P1'), ('dog_s1|OT-L', 'P2a'), ('dog_s1|OT-L', 'P2b'), ('train_s0|OT-1', 'P2a'), ('train_s0|OT-1', 'P2b'), ('train_s0|OT-L', 'P2a'), ('train_s0|OT-L', 'P2b'), ('train_s1|OT-1', 'P2a'), ('train_s1|OT-1', 'P2b'), ('train_s1|OT-L', 'P2a'), ('train_s1|OT-L', 'P2b')]

- Inspection calibration: REF clips flagged ['train_s0|OT-L', 'audi-snow-trail_s1|OT-L']; frozen-M1 clips flagged 16 of 16 cells.
- A NO-GO rejects the preregistered general claim; descriptive utility on a subset is reported as such, never as continuity preservation.

## Component and control hypotheses (confirmation cells)

- C1 (the combination keeps each component's benefit): 12 / 12 -> SUPPORTED
- C2 (TS-in alone leaves the boundary jump above REF P99 on the majority): 10 / 12 -> SUPPORTED
- C3 (the correct latent history beats the stale and noise controls): 12 / 12 -> SUPPORTED
- C4 (TSinKC as a distinct candidate): see its GO / NO-GO line and the per-cell rows.
