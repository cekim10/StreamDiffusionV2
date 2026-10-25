# VD-3 Phase T: distributions for the restoration thresholds (REF streams and frozen-M1 controls only; no threshold chosen)

Primary comparison: candidate minus REF of the same seed at the same calls, same pre-move anchor. Natural variation and measurement noise below are the candidates for its thresholds; the cross-seed difference is sensitivity only; frozen M1 is context only.

| cell | conf. | REF V1 P95 / P99 / max | DINO window P5-P95 width (lag-10 change P95) | dE window width (lag-10 P95) | e_R rel. width | d_R rel. width | REF early-late DINO | embedder noise (call / window max) | cross-seed DINO P95 | cross-seed dE P95 | frozen M1: D_c / C_c / V1 reset / X late |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dog_s0 OT-1 | - | 1.82 / 3.27 / 4.15 | 0.036 (0.036) | 0.83 (0.68) | 0.62 | 0.76 | -0.015 | 0.00000 / 0.00000 | 0.004 | 0.14 | -0.425 / 1.51 / 8.12 / -0.182 |
| dog_s0 OT-L | - | 1.83 / 3.89 / 4.15 | 0.027 (0.027) | 0.94 (0.84) | 0.61 | 0.75 | -0.009 | - / - | 0.003 | 0.23 | -0.378 / 1.14 / 9.24 / -0.019 |
| dog_s1 OT-1 | Y | 1.78 / 3.39 / 4.08 | 0.037 (0.037) | 0.90 (0.71) | 0.62 | 0.75 | -0.014 | 0.00000 / 0.00000 | 0.004 | 0.14 | -0.444 / 1.83 / 8.86 / -0.048 |
| dog_s1 OT-L (copied) | Y | 1.78 / 4.05 / 4.25 | 0.026 (0.026) | 0.88 (0.88) | 0.59 | 0.75 | -0.008 | - / - | 0.003 | 0.23 | -0.357 / 1.48 / 9.18 / -0.092 |
| train_s0 OT-1 | Y | 1.91 / 6.45 / 10.12 | 0.036 (0.018) | 1.06 (1.00) | 0.23 | 0.27 | 0.008 | 0.00000 / 0.00000 | 0.014 | 0.73 | -0.273 / 0.40 / 4.64 / -0.121 |
| train_s0 OT-L (copied) | Y | 1.95 / 7.80 / 10.12 | 0.024 (0.018) | 1.26 (1.18) | 0.25 | 0.27 | -0.003 | - / - | 0.015 | 0.69 | -0.238 / 1.50 / 7.93 / -0.136 |
| train_s1 OT-1 | Y | 1.81 / 7.21 / 10.48 | 0.046 (0.024) | 1.23 (1.22) | 0.24 | 0.27 | 0.001 | 0.00000 / 0.00000 | 0.014 | 0.73 | -0.290 / 1.05 / 5.12 / -0.113 |
| train_s1 OT-L (copied) | Y | 1.94 / 7.08 / 10.48 | 0.024 (0.022) | 0.93 (0.75) | 0.24 | 0.30 | -0.005 | - / - | 0.015 | 0.69 | -0.258 / 1.74 / 8.62 / -0.126 |
| butterfly-feeding-slow-motion_s0 OT-1 | - | 1.26 / 1.40 / 1.44 | 0.056 (0.039) | 0.67 (0.56) | 0.22 | 0.27 | -0.006 | 0.00000 / 0.00000 | 0.016 | 0.54 | -0.173 / 0.08 / 3.30 / -0.124 |
| butterfly-feeding-slow-motion_s0 OT-L | - | 1.27 / 1.38 / 1.48 | 0.039 (0.030) | 0.78 (0.72) | 0.23 | 0.27 | -0.031 | - / - | 0.011 | 0.49 | -0.150 / 0.19 / 1.97 / -0.109 |
| butterfly-feeding-slow-motion_s1 OT-1 | Y | 1.16 / 1.25 / 1.29 | 0.047 (0.026) | 0.59 (0.54) | 0.23 | 0.27 | -0.013 | 0.00000 / 0.00000 | 0.016 | 0.54 | -0.160 / 0.26 / 3.35 / -0.083 |
| butterfly-feeding-slow-motion_s1 OT-L (copied) | Y | 1.15 / 1.27 / 1.50 | 0.027 (0.022) | 0.75 (0.74) | 0.22 | 0.26 | -0.010 | - / - | 0.011 | 0.49 | -0.137 / 0.24 / 2.04 / -0.131 |
| audi-snow-trail_s0 OT-1 (copied) | Y | 2.05 / 2.65 / 2.67 | 0.139 (0.130) | 4.72 (4.68) | 0.84 | 0.68 | -0.136 | 0.00000 / 0.00000 | 0.042 | 0.39 | -0.142 / 0.77 / 4.41 / -0.141 |
| audi-snow-trail_s0 OT-L | Y | 2.24 / 2.85 / 3.97 | 0.219 (0.202) | 8.67 (7.77) | 0.84 | 0.66 | 0.029 | - / - | 0.045 | 0.51 | -0.166 / 0.69 / 6.23 / -0.145 |
| audi-snow-trail_s1 OT-1 | Y | 1.72 / 2.85 / 3.33 | 0.148 (0.153) | 4.86 (4.91) | 0.86 | 0.70 | -0.145 | 0.00000 / 0.00000 | 0.042 | 0.39 | -0.149 / 0.47 / 4.23 / -0.088 |
| audi-snow-trail_s1 OT-L (copied) | Y | 1.92 / 3.30 / 4.65 | 0.244 (0.224) | 8.40 (7.66) | 0.81 | 0.68 | 0.010 | - / - | 0.045 | 0.51 | -0.149 / 0.99 / 5.78 / -0.087 |

Emulation determinism per unit (G1 and prefix digests): see the JSON (`measurement_noise.emulation`).
