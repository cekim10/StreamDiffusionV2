# Fig. 7 results (testbed)

**H1 and H2 hold: OTTER's single migration stalls far less and reaches local service sooner than every exact baseline**

Medians [IQR] over valid reps. TTFO-local, delivery gap and bytes are the Fig. 7 metrics; cutover interruption, remote serving, C2 and NIC are diagnostics.

## Low-refresh (dog)

| method | valid / runs (failed) | TTFO-local (s) | delivery gap (s) | bytes (GB) | cutover (s) | C2 first / min24 / terminal (dB) |
|---|---|---|---|---|---|---|
| Full | 5 / 5 (0) | 54.24 [54.18-54.25] | 54.24 [54.18-54.25] | 6.463 [6.463-6.463] | 54.24 [54.18-54.25] | 99.0 / 99.0 / 99.0 |
| Llumnix-style | 5 / 5 (0) | 213.85 [213.57-213.86] | 50.92 [50.75-50.99] | 22.854 [22.854-22.854] | 50.92 [50.75-50.99] | 99.0 / 99.0 / 99.0 |
| ServerlessLLM-style | 5 / 5 (0) | 36.94 [36.79-36.94] | 18.47 [18.42-18.51] | 0.084 [0.084-0.084] | 18.47 [18.42-18.51] | 99.0 / 99.0 / 99.0 |
| OTTER | 5 / 5 (0) | 23.28 [23.12-23.53] | 1.63 [1.60-1.66] | 1.763 [1.763-1.763] | 1.57 [1.54-1.60] | 29.3 / 27.5 / 48.8 |

H1 gap ratio 0.088 -> True; H2 TTFO ratio 0.630 -> True; OTTER bytes / method {"Full": 0.273, "Llumnix-style": 0.077, "ServerlessLLM-style": 20.997}

## High-refresh (bfly)

| method | valid / runs (failed) | TTFO-local (s) | delivery gap (s) | bytes (GB) | cutover (s) | C2 first / min24 / terminal (dB) |
|---|---|---|---|---|---|---|
| Full | 5 / 5 (0) | 54.22 [54.05-54.23] | 54.22 [54.05-54.23] | 6.463 [6.463-6.463] | 54.22 [54.05-54.23] | 99.0 / 99.0 / 99.0 |
| Llumnix-style | 5 / 5 (0) | 219.21 [219.16-219.35] | 52.57 [52.51-52.58] | 23.555 [23.555-23.555] | 52.57 [52.51-52.58] | 99.0 / 99.0 / 99.0 |
| ServerlessLLM-style | 5 / 5 (0) | 36.78 [36.70-36.79] | 18.33 [18.30-18.36] | 0.064 [0.064-0.064] | 18.33 [18.30-18.36] | 99.0 / 99.0 / 99.0 |
| OTTER | 5 / 5 (0) | 24.62 [24.45-25.78] | 1.59 [1.57-1.73] | 2.243 [2.243-2.282] | 1.51 [1.49-1.73] | 35.9 / 25.5 / 44.4 |

H1 gap ratio 0.087 -> True; H2 TTFO ratio 0.670 -> True; OTTER bytes / method {"Full": 0.347, "Llumnix-style": 0.095, "ServerlessLLM-style": 35.266}

