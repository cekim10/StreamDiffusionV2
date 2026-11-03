# Fig. 12a results

Rules: `preregistration.md`. Medians [IQR] over valid reps.

F12-H1 SUPPORTED {'dog': True, 'bfly': True}; F12-H2 NOT SUPPORTED {'dog': True, 'bfly': False}; F12-H3 SUPPORTED {'dog': True, 'bfly': True}; B* {'dog': 'native', 'bfly': '0.25 Gbps'}; benefit-shrink region {'dog': [], 'bfly': []}

## Low-refresh (dog)

| bandwidth | method | valid / runs | TTFO-local (s) | gap (s) | bytes (GB) | peak 10 s rx at B (Gbps) | OTTER sink / first (s), share |
|---|---|---|---|---|---|---|---|
| 0.25 Gbps | Full | 3 / 3 | 209.8 | 209.84 | 6.46 | 0.26 |  |
| 0.25 Gbps | Llumnix-style | 3 / 3 | 766.0 | 183.37 | 22.97 | 0.27 |  |
| 0.25 Gbps | ServerlessLLM-style | 3 / 3 | 37.7 | 19.31 | 0.08 | 0.04 |  |
| 0.25 Gbps | OTTER | 3 / 3 | 75.6 | 1.64 | 1.82 | 0.26 | 59.3 / 75.6, 0.78 |
| 0.5 Gbps | Full | 3 / 3 | 106.4 | 106.40 | 6.46 | 0.52 |  |
| 0.5 Gbps | Llumnix-style | 3 / 3 | 398.0 | 95.42 | 22.91 | 0.52 |  |
| 0.5 Gbps | ServerlessLLM-style | 3 / 3 | 37.2 | 18.65 | 0.08 | 0.04 |  |
| 0.5 Gbps | OTTER | 3 / 3 | 41.2 | 1.61 | 1.79 | 0.52 | 31.6 / 41.2, 0.77 |
| 1 Gbps | Full | 3 / 3 | 54.2 | 54.15 | 6.46 | 1.03 |  |
| 1 Gbps | Llumnix-style | 3 / 3 | 213.8 | 51.01 | 22.85 | 1.04 |  |
| 1 Gbps | ServerlessLLM-style | 3 / 3 | 36.8 | 18.45 | 0.08 | 0.04 |  |
| 1 Gbps | OTTER | 3 / 3 | 23.1 | 1.65 | 1.76 | 1.03 | 17.4 / 23.1, 0.75 |
| 2.5 Gbps | Full | 3 / 3 | 22.9 | 22.92 | 6.46 | 2.54 |  |
| 2.5 Gbps | Llumnix-style | 3 / 3 | 104.3 | 24.47 | 22.85 | 2.46 |  |
| 2.5 Gbps | ServerlessLLM-style | 3 / 3 | 36.6 | 18.30 | 0.08 | 0.04 |  |
| 2.5 Gbps | OTTER | 3 / 3 | 13.1 | 1.63 | 1.75 | 1.43 | 9.1 / 13.1, 0.69 |
| native | Full | 3 / 3 | 7.3 | 7.27 | 6.46 | 5.28 |  |
| native | Llumnix-style | 3 / 3 | 65.7 | 12.76 | 26.21 | 4.43 |  |
| native | ServerlessLLM-style | 3 / 3 | 36.9 | 18.40 | 0.08 | 0.04 |  |
| native | OTTER | 3 / 3 | 11.4 | 1.59 | 1.75 | 1.43 | 5.2 / 11.4, 0.45 |

Gap ratio OTTER / best baseline: 0.25 Gbps 0.085, 0.5 Gbps 0.086, 1 Gbps 0.089, 2.5 Gbps 0.089, native 0.219
TTFO-local OTTER / ServerlessLLM-style (exploratory): 0.25 Gbps 2.00, 0.5 Gbps 1.11, 1 Gbps 0.63, 2.5 Gbps 0.36, native 0.31

## High-refresh (bfly)

| bandwidth | method | valid / runs | TTFO-local (s) | gap (s) | bytes (GB) | peak 10 s rx at B (Gbps) | OTTER sink / first (s), share |
|---|---|---|---|---|---|---|---|
| 0.25 Gbps | Full | 3 / 3 | 209.9 | 209.95 | 6.46 | 0.26 |  |
| 0.25 Gbps | Llumnix-style | 3 / 3 | 789.5 | 192.00 | 23.70 | 0.27 |  |
| 0.25 Gbps | ServerlessLLM-style | 3 / 3 | 38.4 | 19.59 | 0.06 | 0.03 |  |
| 0.25 Gbps | OTTER | 3 / 3 | 154.9 | 1.66 | 4.67 | 0.26 | 70.2 / 154.9, 0.45 |
| 0.5 Gbps | Full | 3 / 3 | 106.8 | 106.80 | 6.46 | 0.52 |  |
| 0.5 Gbps | Llumnix-style | 3 / 3 | 409.9 | 99.42 | 23.59 | 0.52 |  |
| 0.5 Gbps | ServerlessLLM-style | 3 / 3 | 38.0 | 19.11 | 0.06 | 0.03 |  |
| 0.5 Gbps | OTTER | 3 / 3 | 49.0 | 1.68 | 2.69 | 0.52 | 35.2 / 49.0, 0.72 |
| 1 Gbps | Full | 3 / 3 | 54.4 | 54.41 | 6.46 | 1.03 |  |
| 1 Gbps | Llumnix-style | 3 / 3 | 262.4 | 52.44 | 28.08 | 1.04 |  |
| 1 Gbps | ServerlessLLM-style | 3 / 3 | 38.1 | 19.24 | 0.06 | 0.03 |  |
| 1 Gbps | OTTER | 3 / 3 | 26.0 | 1.79 | 2.25 | 1.03 | 18.9 / 26.0, 0.74 |
| 2.5 Gbps | Full | 3 / 3 | 23.0 | 22.96 | 6.46 | 2.53 |  |
| 2.5 Gbps | Llumnix-style | 3 / 3 | 105.9 | 25.37 | 23.43 | 2.44 |  |
| 2.5 Gbps | ServerlessLLM-style | 3 / 3 | 38.2 | 19.20 | 0.06 | 0.03 |  |
| 2.5 Gbps | OTTER | 3 / 3 | 14.1 | 1.73 | 1.99 | 1.61 | 9.5 / 14.1, 0.70 |
| native | Full | 3 / 3 | 7.3 | 7.33 | 6.46 | 5.25 |  |
| native | Llumnix-style | 3 / 3 | 69.8 | 14.11 | 26.52 | 4.55 |  |
| native | ServerlessLLM-style | 3 / 3 | 37.9 | 19.03 | 0.06 | 0.03 |  |
| native | OTTER | 3 / 3 | 11.6 | 1.63 | 1.96 | 1.59 | 5.3 / 11.6, 0.46 |

Gap ratio OTTER / best baseline: 0.25 Gbps 0.085, 0.5 Gbps 0.088, 1 Gbps 0.093, 2.5 Gbps 0.090, native 0.222
TTFO-local OTTER / ServerlessLLM-style (exploratory): 0.25 Gbps 4.03, 0.5 Gbps 1.29, 1 Gbps 0.68, 2.5 Gbps 0.37, native 0.31

