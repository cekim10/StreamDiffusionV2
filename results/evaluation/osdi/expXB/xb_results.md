# XB results

Medians over valid reps. TTFO-local, delivery gap, remote serving, RTT and transmitted bytes are MEASURED; remote delivery bytes are ESTIMATED (H.264 size of remotely served output, never transmitted). WAN / radio latency is not measured.

## XB1_dog

| method | valid | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (MB) | transmitted (GB) | output equivalence | first >= 35 dB idx | sustained runs | terminal PSNR | Sink-less median PSNR | switch reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OTTER | 3/3 | 0.67 | 0.69 | 0 | 0 | 0 / 0 | 1.73 | ['0/0', '0/0', '0/0'] | 31 | 3 | 44.2 | 16.6 | - |
| Full | 3/3 | 54.05 | 54.05 | 0 | 0 | 0 / 0 | 6.46 | ['0/0', '0/0', '0/0'] | 0 | 3 | 99.0 | - | - |
| Wait-for-Sink | 3/3 | 14.98 | 14.98 | 0 | 0 | 0 / 0 | 1.73 | ['0/0', '0/0', '0/0'] | 8 | 3 | 47.3 | - | - |
| P-full | 3/3 | 214.16 | 50.71 | 247 | 163.4 | 11.9 / 5.5 | 22.85 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | no_shrink |
| P-sink | 3/3 | 25.05 | 8.11 | 26 | 17.0 | 1.2 / 0.6 | 2.45 | ['0/101', '0/101', '0/101'] | 8 | 3 | 49.4 | - | round_limit |
| R-full | 3/3 | 36.69 | 18.34 | 30 | 18.3 | 1.4 / 0.7 | 0.08 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | - |
| R-win | 3/3 | 5.50 | 4.23 | 2 | 1.3 | 0.1 / 0.1 | 0.01 | ['0/101', '0/101', '0/101'] | - | 0 | 21.6 | - | - |

## XB1_bfly

| method | valid | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (MB) | transmitted (GB) | output equivalence | first >= 35 dB idx | sustained runs | terminal PSNR | Sink-less median PSNR | switch reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OTTER | 3/3 | 0.67 | 0.70 | 0 | 0 | 0 / 0 | 1.73 | ['0/0', '0/0', '0/0'] | - | 0 | 30.4 | 18.4 | - |
| Full | 3/3 | 54.05 | 54.05 | 0 | 0 | 0 / 0 | 6.46 | ['0/0', '0/0', '0/0'] | 0 | 3 | 99.0 | - | - |
| Wait-for-Sink | 3/3 | 14.97 | 14.97 | 0 | 0 | 0 / 0 | 1.73 | ['0/0', '0/0', '0/0'] | 8 | 3 | 36.2 | - | - |
| P-full | 3/3 | 219.48 | 52.42 | 252 | 166.8 | 10.5 / 6.3 | 23.55 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | no_shrink |
| P-sink | 3/3 | 26.51 | 9.58 | 26 | 16.9 | 1.1 / 0.7 | 2.62 | ['0/101', '0/101', '0/101'] | 10 | 3 | 34.0 | - | round_limit |
| R-full | 3/3 | 36.78 | 18.33 | 30 | 18.4 | 1.2 / 0.7 | 0.06 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | - |
| R-win | 3/3 | 4.82 | 4.16 | 1 | 0.7 | 0.1 / 0.0 | 0.01 | ['0/101', '0/101', '0/101'] | - | 0 | 22.2 | - | - |

## XB2_dog

| method | valid | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (MB) | transmitted (GB) | output equivalence | first >= 35 dB idx | sustained runs | terminal PSNR | Sink-less median PSNR | switch reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OTTER | 3/3 | 0.67 | 0.69 | 0 | 0 | 0 / 0 | 1.73 | ['0/0', '0/0', '0/0'] | 31 | 3 | 49.5 | 16.6 | - |
| P-sink | 3/3 | 25.35 | 8.16 | 26 | 17.2 | 1.3 / 0.6 | 2.44 | ['0/101', '0/101', '0/101'] | 8 | 3 | 49.1 | - | round_limit |
| R-full | 3/3 | 134.33 | 65.46 | 112 | 68.9 | 5.4 / 2.5 | 0.32 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | - |

## XB3_dog

| method | valid | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (MB) | transmitted (GB) | output equivalence | first >= 35 dB idx | sustained runs | terminal PSNR | Sink-less median PSNR | switch reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OTTER | 3/3 | 0.83 | 0.75 | 2 | 0.5 | 0 / 0 | 5.16 | ['0/0', '0/0', '0/0'] | 32 | 3 | 41.3 | 16.8 | - |
| Full | 3/3 | 53.42 | 81.56 | 0 | 0 | 0 / 0 | 8.19 | ['0/0', '0/0', '0/0'] | 0 | 3 | 99.0 | - | - |
| Wait-for-Sink | 3/3 | 14.91 | 43.05 | 0 | 0 | 0 / 0 | 5.18 | ['0/0', '0/0', '0/0'] | 8 | 3 | 47.2 | - | - |
| P-sink | 3/3 | 25.24 | 8.27 | 68 | 44.8 | 3.3 / 1.5 | 5.21 | ['0/101', '0/101', '0/101'] | 9 | 3 | 49.4 | - | round_limit |
| R-full | 3/3 | 88.16 | 43.47 | 118 | 71.7 | 5.7 / 2.7 | 0.32 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | - |

## XB4_dog

| method | valid | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (MB) | transmitted (GB) | output equivalence | first >= 35 dB idx | sustained runs | terminal PSNR | Sink-less median PSNR | switch reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OTTER | 3/3 | 0.85 | 0.74 | 2 | 0.4 | 0 / 0 | 3.48 | ['0/0', '0/0', '0/0'] | 33 | 3 | 43.5 | 16.7 | - |
| Full | 3/3 | 53.57 | 67.67 | 0 | 0 | 0 / 0 | 6.47 | ['0/0', '0/0', '0/0'] | 0 | 3 | 99.0 | - | - |
| Wait-for-Sink | 3/3 | 14.94 | 29.03 | 0 | 0 | 0 / 0 | 3.47 | ['0/0', '0/0', '0/0'] | 8 | 3 | 47.2 | - | - |
| P-sink | 3/3 | 19.51 | 2.60 | 45 | 30.2 | 2.2 / 1.0 | 2.79 | ['0/101', '0/101', '0/101'] | 8 | 3 | 46.4 | - | round_limit |
| R-full | 3/3 | 62.61 | 31.19 | 74 | 44.7 | 3.6 / 1.7 | 0.25 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | - |

## ALT_dog

| method | valid | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (MB) | transmitted (GB) | output equivalence | first >= 35 dB idx | sustained runs | terminal PSNR | Sink-less median PSNR | switch reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P-sink | 3/3 | 29.20 | 2.38 | 38 | 26.7 | 1.8 / 0.9 | 2.48 | ['0/101', '0/101', '0/101'] | 8 | 3 | 48.8 | - | threshold |
| R-full | 3/3 | 173.43 | 15.05 | 259 | 158.3 | 12.5 / 5.8 | 0.40 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | - |
| R-win | 3/3 | 2.58 | 1.93 | 1 | 0.7 | 0.1 / 0.0 | 0.00 | ['0/100', '0/100', '0/100'] | - | 0 | 21.1 | - | - |

## ALT_bfly

| method | valid | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (MB) | transmitted (GB) | output equivalence | first >= 35 dB idx | sustained runs | terminal PSNR | Sink-less median PSNR | switch reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P-sink | 3/3 | 35.25 | 2.48 | 46 | 32.8 | 1.9 / 1.1 | 3.02 | ['0/101', '0/101', '0/101'] | 9 | 3 | 39.2 | - | threshold |
| R-full | 3/3 | 168.37 | 14.37 | 250 | 153.9 | 10.4 / 6.2 | 0.29 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | - |
| R-win | 3/3 | 2.57 | 1.92 | 1 | 0.7 | 0.1 / 0.0 | 0.00 | ['0/100', '0/100', '0/100'] | - | 0 | 21.9 | - | - |

## N_dog

| method | valid | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (MB) | transmitted (GB) | output equivalence | first >= 35 dB idx | sustained runs | terminal PSNR | Sink-less median PSNR | switch reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P-full | 3/3 | 66.55 | 12.50 | 60 | 54.1 | 2.9 / 1.3 | 26.21 | ['101/101', '101/101', '101/101'] | 0 | 3 | 99.0 | - | no_shrink |

## Hypotheses (frozen rules)

- **XH1a** (TTFO-local OTTER <= 0.25 x each exact method, XB1 both workloads): **SUPPORTED**
  - XB1_dog vs Full: 0.67 s vs 54.05 s, ratio 0.0124 -> True
  - XB1_dog vs P-full: 0.67 s vs 214.16 s, ratio 0.0031 -> True
  - XB1_dog vs R-full: 0.67 s vs 36.69 s, ratio 0.0183 -> True
  - XB1_bfly vs Full: 0.67 s vs 54.05 s, ratio 0.0124 -> True
  - XB1_bfly vs P-full: 0.67 s vs 219.48 s, ratio 0.0031 -> True
  - XB1_bfly vs R-full: 0.67 s vs 36.78 s, ratio 0.0183 -> True
- **XH2** (P-full never converges at 1 Gbps): **SUPPORTED** (6 runs; reasons ['no_shrink'])
- **XH3** (R-full destination GPU-seconds at trigger 120 >= 3 x at 30): **SUPPORTED** (35.0 s -> 132.8 s, x3.79)
- **XH4** (remote-serving seconds of P-sink and R-full >= 5 x OTTER's TTFO-local, rho 1 and 2): **SUPPORTED**
  - XB3_dog P-sink: 44.8 s vs 5 x 0.83 s (x53.8) -> True
  - XB3_dog R-full: 71.7 s vs 5 x 0.83 s (x86.1) -> True
  - XB4_dog P-sink: 30.2 s vs 5 x 0.85 s (x35.7) -> True
  - XB4_dog R-full: 44.7 s vs 5 x 0.85 s (x52.7) -> True
- **XH1b** (hybrid and approximate methods) and **XH5** (OTTER's trajectory cost): descriptive, in the scenario tables above (Sink-less median PSNR, first call >= 35 dB, terminal PSNR).

## D5 lossy-input sensitivity (descriptive; lossy inputs are never exact recomputation)

| workload | method | codec | valid | TTFO-local (s) | delivery gap (s) | inputs sent (MB) / raw (MB) | min input PSNR (dB) | output equivalence | terminal PSNR |
|---|---|---|---|---|---|---|---|---|---|
| dog | R-full | h264_crf23 | True | 36.44 | 18.06 | 2.4 / 294 | 34.5 | 0/101 | 37.5 |
| dog | R-full | h264_crf28 | True | 36.54 | 18.13 | 1.2 / 294 | 31.7 | 0/101 | 32.8 |
| dog | R-win | h264_crf23 | True | 4.73 | 4.08 | 0.3 / 35 | 34.1 | 0/101 | 23.0 |
| dog | R-win | h264_crf28 | True | 4.72 | 4.04 | 0.2 / 35 | 31.3 | 0/101 | 23.1 |
| bfly | R-full | h264_crf23 | True | 36.71 | 18.20 | 2.0 / 294 | 36.4 | 0/101 | 27.7 |
| bfly | R-full | h264_crf28 | True | 36.51 | 18.09 | 1.0 / 294 | 34.2 | 0/101 | 27.5 |
| bfly | R-win | h264_crf23 | True | 4.74 | 4.09 | 0.3 / 35 | 36.2 | 0/101 | 21.7 |
| bfly | R-win | h264_crf28 | True | 4.68 | 4.03 | 0.1 / 35 | 34.0 | 0/101 | 21.9 |
