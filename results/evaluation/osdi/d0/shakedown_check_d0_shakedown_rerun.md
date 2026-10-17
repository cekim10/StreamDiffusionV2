# D0 GPU correctness shakedown - check

Conditions from `D0_report.md` section F (written before the runs). Latencies in seconds after the final move's handoff request.

| scenario | policy | first output | Sink bound | rejoin | rejoin PSNR (dB) | source pre / post / total (Sinks) | holder-forwarded | x verified at move | reuse of verified progress | re-plans | NIC peak (Mbps) | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | reuse_dyn | 0.69 | 14.84 | 19.04 | 42.3 | 0.00 / 1.00 / 1.00 | 0.00 |  | None | 0 | 1040 | PASS |
| repeated | restart | 1.06 | 14.66 | 20.67 | 41.4 | 0.99 / 1.03 / 2.02 | 0.00 | B 0.50, C 0.49 | 0.0 | 0 | 1042 | PASS |
| repeated | split | 0.93 | 14.49 | 20.52 | 41.4 | 0.75 / 0.28 / 1.02 | 0.74 | B 0.50, C 0.49 | 0.981 | 0 | 1049 | PASS |
| repeated | reuse_aware_in | 2.00 | 14.98 | 19.78 | 40.9 | 0.75 / 0.27 / 1.02 | 0.74 | B 0.50, C 0.50 | 0.984 | 0 | 1050 | PASS |
| repeated | reuse_dyn | 0.87 | 14.46 | 20.50 | 41.4 | 0.77 / 0.29 / 1.06 | 0.72 | B 0.54, C 0.45 | 0.983 | 0 | 1050 | PASS |
| degradation | reuse_aware_in | 1.12 | 51.68 | 56.49 | 39.2 | 0.75 / 0.28 / 1.03 | 0.73 | B 0.50, C 0.48 | 0.974 | 0 | 1047 | PASS |
| degradation | reuse_dyn | 0.92 | 15.70 | 21.11 | 39.2 | 0.75 / 0.44 / 1.19 | 0.57 | B 0.50, C 0.49 | 0.762 | 2 | 1053 | PASS |
| placement correct | reuse_dyn | 0.70 | 4.34 | 9.11 | 42.6 | 0.72 / 0.28 / 1.00 | 0.00 | B 0.72 | None | 0 | 1039 | PASS |
| placement incorrect | reuse_dyn | 0.73 | 14.97 | 19.17 | 42.3 | 0.72 / 0.51 / 1.23 | 0.50 | B 0.72 | None | 1 | 1052 | PASS |

9 runs; 0 failing.
