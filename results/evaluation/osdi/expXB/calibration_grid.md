# XB calibration grid

Setting: XB1 (A -> B, trigger chunk 30, 1 Gbps, dog, seed 0). Calibration runs are not evidence for XH1-XH5.
TTFO-local, delivery gap, remote-served chunks and RTT are measured. Delivery bytes are ESTIMATED (H.264 size of remotely served output; not transmitted).

## P-full: selected thr=256:rl=10; alternative (min delivery gap) thr=256:rl=10

Jitter of the selected setting's repeats: 0.3 %

| setting | rep | valid | class check | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (KB) | rounds | dirty MiB per round | switch / finish reason | inputs FFV1 / raw (MiB) | output equivalence | terminal PSNR | first >= 35 dB idx | sustained 10 idx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| thr=16:rl=3 | 1 | True | True | 213.86 | 50.90 | 247 | 163.0 | 11869 / 5530 | 3 | [6164, 5224, 5208] | round_limit | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=16:rl=6 | 1 | True | True | 213.96 | 51.23 | 246 | 162.7 | 11826 / 5510 | 3 | [6164, 5224, 5208] | no_shrink | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=16:rl=10 | 1 | True | True | 216.21 | 51.65 | 245 | 164.6 | 11780 / 5489 | 3 | [6164, 5224, 5208] | no_shrink | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=64:rl=3 | 1 | True | True | 216.66 | 51.53 | 246 | 165.1 | 11826 / 5510 | 3 | [6164, 5224, 5208] | round_limit | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=64:rl=6 | 1 | True | True | 215.62 | 51.41 | 245 | 164.2 | 11780 / 5489 | 3 | [6164, 5224, 5208] | no_shrink | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=64:rl=10 | 1 | True | True | 215.69 | 51.54 | 248 | 164.1 | 11915 / 5552 | 3 | [6164, 5224, 5208] | no_shrink | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=256:rl=3 | 1 | True | True | 213.82 | 50.92 | 246 | 162.9 | 11826 / 5510 | 3 | [6164, 5224, 5208] | round_limit | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=256:rl=6 | 1 | True | True | 216.40 | 51.54 | 245 | 164.9 | 11780 / 5489 | 3 | [6164, 5224, 5208] | no_shrink | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=256:rl=10 **(selected)** | 1 | True | True | 213.45 | 50.89 | 246 | 162.6 | 11826 / 5510 | 3 | [6164, 5224, 5208] | no_shrink | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=256:rl=10 **(selected)** | 2 | True | True | 214.14 | 50.84 | 247 | 163.3 | 11869 / 5530 | 3 | [6164, 5224, 5208] | no_shrink | - / - | 101/101 | 99.0 | 0 | 0 |
| thr=256:rl=10 **(selected)** | 3 | True | True | 213.99 | 50.90 | 246 | 163.1 | 11826 / 5510 | 3 | [6164, 5224, 5208] | no_shrink | - / - | 101/101 | 99.0 | 0 | 0 |

## P-sink: selected thr=16:rl=1; alternative (min delivery gap) thr=256:rl=6 (differs: run in XB1, rule 4)

Jitter of the selected setting's repeats: 2.2 %

| setting | rep | valid | class check | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (KB) | rounds | dirty MiB per round | switch / finish reason | inputs FFV1 / raw (MiB) | output equivalence | terminal PSNR | first >= 35 dB idx | sustained 10 idx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| thr=16:rl=1 **(selected)** | 1 | True | True | 25.66 | 8.35 | 26 | 17.3 | 1235 / 573 | 1 | [1645] | round_limit | - / - | 0/101 | 49.4 | 8 | 8 |
| thr=16:rl=1 **(selected)** | 2 | True | True | 25.62 | 8.36 | 26 | 17.3 | 1235 / 573 | 1 | [1645] | round_limit | - / - | 0/101 | 49.4 | 8 | 8 |
| thr=16:rl=1 **(selected)** | 3 | True | True | 25.10 | 8.15 | 26 | 17.0 | 1235 / 573 | 1 | [1645] | round_limit | - / - | 0/101 | 49.4 | 8 | 8 |
| thr=16:rl=2 | 1 | True | True | 27.13 | 2.39 | 37 | 24.7 | 1791 / 835 | 2 | [1645, 689] | round_limit | - / - | 0/101 | 48.5 | 9 | 9 |
| thr=16:rl=3 | 1 | True | True | 28.87 | 2.19 | 38 | 26.7 | 1836 / 854 | 3 | [1645, 689, 24] | round_limit | - / - | 0/101 | 48.8 | 8 | 8 |
| thr=16:rl=3 | 2 | True | True | 29.51 | 2.21 | 39 | 27.3 | 1880 / 874 | 3 | [1645, 689, 24] | round_limit | - / - | 0/101 | 49.1 | 9 | 9 |
| thr=16:rl=3 | 3 | True | True | 28.51 | 2.18 | 37 | 26.3 | 1791 / 835 | 3 | [1645, 689, 24] | round_limit | - / - | 0/101 | 48.5 | 9 | 9 |
| thr=16:rl=6 | 1 | True | True | 30.50 | 2.23 | 39 | 28.3 | 1880 / 874 | 4 | [1645, 689, 24, 0] | threshold | - / - | 0/101 | 49.1 | 9 | 9 |
| thr=16:rl=10 | 1 | True | True | 31.28 | 2.40 | 39 | 28.9 | 1880 / 874 | 4 | [1645, 689, 24, 0] | threshold | - / - | 0/101 | 49.1 | 9 | 9 |
| thr=64:rl=3 | 1 | True | True | 29.12 | 2.20 | 38 | 26.9 | 1836 / 854 | 3 | [1645, 689, 24] | threshold | - / - | 0/101 | 48.8 | 8 | 8 |
| thr=64:rl=6 | 1 | True | True | 30.14 | 2.53 | 39 | 27.6 | 1880 / 874 | 3 | [1645, 689, 24] | threshold | - / - | 0/101 | 49.1 | 9 | 9 |
| thr=64:rl=10 | 1 | True | True | 30.28 | 2.45 | 39 | 27.8 | 1880 / 874 | 3 | [1645, 689, 24] | threshold | - / - | 0/101 | 49.1 | 9 | 9 |
| thr=256:rl=3 | 1 | True | True | 29.54 | 2.40 | 38 | 27.1 | 1836 / 854 | 3 | [1645, 689, 24] | threshold | - / - | 0/101 | 48.8 | 8 | 8 |
| thr=256:rl=6 | 1 | True | True | 28.66 | 2.19 | 38 | 26.5 | 1836 / 854 | 3 | [1645, 689, 24] | threshold | - / - | 0/101 | 48.8 | 8 | 8 |
| thr=256:rl=10 | 1 | True | True | 29.17 | 2.25 | 39 | 26.9 | 1880 / 874 | 3 | [1645, 689, 24] | threshold | - / - | 0/101 | 49.1 | 9 | 9 |

## R-full: selected lag=1:rl=1; alternative (min delivery gap) lag=2:rl=10 (differs: run in XB1, rule 4)

Jitter of the selected setting's repeats: 1.0 %

| setting | rep | valid | class check | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (KB) | rounds | dirty MiB per round | switch / finish reason | inputs FFV1 / raw (MiB) | output equivalence | terminal PSNR | first >= 35 dB idx | sustained 10 idx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lag=1:rl=1 **(selected)** | 1 | True | True | 36.84 | 18.46 | 30 | 18.4 | 1427 / 666 | 1 | - | round_limit | 80 / 280 | 101/101 | 99.0 | 0 | 0 |
| lag=1:rl=1 **(selected)** | 2 | True | True | 36.49 | 18.20 | 30 | 18.3 | 1427 / 666 | 1 | - | round_limit | 80 / 280 | 101/101 | 99.0 | 0 | 0 |
| lag=1:rl=1 **(selected)** | 3 | True | True | 36.81 | 18.43 | 30 | 18.4 | 1427 / 666 | 1 | - | round_limit | 80 / 280 | 101/101 | 99.0 | 0 | 0 |
| lag=1:rl=2 | 1 | True | True | 53.31 | 17.82 | 58 | 35.5 | 2806 / 1302 | 2 | - | round_limit | 117 / 408 | 101/101 | 99.0 | 0 | 0 |
| lag=1:rl=3 | 1 | True | True | 69.37 | 17.29 | 85 | 52.1 | 4083 / 1894 | 3 | - | round_limit | 152 / 531 | 101/101 | 99.0 | 0 | 0 |
| lag=1:rl=3 | 2 | True | True | 70.75 | 17.75 | 87 | 53.0 | 4178 / 1940 | 3 | - | round_limit | 155 / 540 | 101/101 | 99.0 | 0 | 0 |
| lag=1:rl=3 | 3 | True | True | 69.20 | 17.23 | 85 | 52.0 | 4083 / 1894 | 3 | - | round_limit | 152 / 531 | 101/101 | 99.0 | 0 | 0 |
| lag=1:rl=6 | 1 | True | True | 121.85 | 17.33 | 172 | 104.5 | 8296 / 3864 | 6 | - | round_limit | 266 / 929 | 101/101 | 99.0 | 0 | 0 |
| lag=1:rl=10 | 1 | True | True | 177.54 | 15.74 | 265 | 161.8 | 12721 / 5933 | 10 | - | round_limit | 388 / 1354 | 101/101 | 99.0 | 0 | 0 |
| lag=2:rl=3 | 1 | True | True | 71.05 | 17.87 | 87 | 53.2 | 4178 / 1940 | 3 | - | round_limit | 155 / 540 | 101/101 | 99.0 | 0 | 0 |
| lag=2:rl=6 | 1 | True | True | 118.27 | 16.68 | 167 | 101.6 | 8057 / 3749 | 6 | - | round_limit | 259 / 906 | 101/101 | 99.0 | 0 | 0 |
| lag=2:rl=10 | 1 | True | True | 174.51 | 15.66 | 260 | 158.9 | 12506 / 5836 | 10 | - | round_limit | 381 / 1331 | 101/101 | 99.0 | 0 | 0 |

## R-win: selected W=6; alternative (min delivery gap) W=1 (differs: run in XB1, rule 4)

Jitter of the selected setting's repeats: 1.0 %

| setting | rep | valid | class check | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (KB) | rounds | dirty MiB per round | switch / finish reason | inputs FFV1 / raw (MiB) | output equivalence | terminal PSNR | first >= 35 dB idx | sustained 10 idx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| W=1 | 1 | True | True | 2.65 | 1.98 | 1 | 0.7 | 62 / 32 | 0 | - | inputs | 3 / 10 | 0/100 | 21.1 | - | - |
| W=3 | 1 | True | True | 3.15 | 2.50 | 1 | 0.7 | 62 / 32 | 0 | - | inputs | 6 / 19 | 0/101 | 21.9 | - | - |
| W=6 **(selected)** | 1 | True | True | 4.81 | 4.16 | 1 | 0.7 | 62 / 32 | 0 | - | inputs | 10 / 33 | 0/101 | 23.3 | - | - |
| W=6 **(selected)** | 2 | True | True | 4.81 | 4.14 | 1 | 0.7 | 62 / 32 | 0 | - | inputs | 10 / 33 | 0/101 | 23.3 | - | - |
| W=6 **(selected)** | 3 | True | True | 4.77 | 4.11 | 1 | 0.7 | 62 / 32 | 0 | - | inputs | 10 / 33 | 0/101 | 23.3 | - | - |

R-win latency-quality trade-off (all W; rule 3 keeps W within 1.0 dB of the best terminal PSNR, then the smallest TTFO-local):

| W | TTFO-local (s) | delivery gap (s) | remote chunks | terminal PSNR (dB) | first >= 35 dB idx | sustained 10 idx |
|---|---|---|---|---|---|---|
| 1 | 2.65 | 1.98 | 1 | 21.1 | - | - |
| 3 | 3.15 | 2.50 | 1 | 21.9 | - | - |
| 6 | 4.81 | 4.16 | 1 | 23.3 | - | - |

Measured LAN RTT A-B (TCP echo, median per run): 0.17-0.34 ms; WAN / radio latency is not emulated or measured.

Runs: 43 (43 valid, 43 eligible).
