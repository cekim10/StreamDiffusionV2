# D0 GPU correctness shakedown - check

Conditions from `D0_report.md` section F (written before the runs). Latencies in seconds after the final move's handoff request.

| scenario | policy | first output | Sink bound | rejoin | rejoin PSNR (dB) | source pre / post / total (Sinks) | holder-forwarded | x verified at move | reuse of verified progress | re-plans | NIC peak (Mbps) | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | reuse_dyn | 0.68 | 14.85 | 19.03 | 42.3 | 0.00 / 1.00 / 1.00 | 0.00 |  | None | 0 | 1040 | PASS |
| repeated | restart | 1.07 | 15.30 | 20.16 | 40.8 | 0.99 / 1.03 / 2.03 | 0.00 | B 0.51, C 0.48 | 0.0 | 0 | 1041 | PASS |
| repeated | split | 0.97 | 15.18 | 19.99 | 40.8 | 0.75 / 0.28 / 1.03 | 0.74 | B 0.50, C 0.49 | 0.977 | 0 | 1045 | PASS |
| repeated | reuse_aware_in | 0.91 | 14.51 | 20.54 | 41.4 | 0.75 / 0.27 / 1.02 | 0.74 | B 0.50, C 0.49 | 0.984 | 0 | 1048 | PASS |
| repeated | reuse_dyn | 0.96 | 15.15 | 19.97 | 40.8 | 0.75 / 0.28 / 1.02 | 0.74 | B 0.50, C 0.49 | 0.981 | 0 | 1046 | PASS |
| degradation | reuse_aware_in | 1.05 | 51.06 | 55.28 | 39.3 | 0.75 / 0.28 / 1.03 | 0.73 | B 0.50, C 0.49 | 0.977 | 0 | 1046 | PASS |
| degradation | reuse_dyn | 0.93 | 15.79 | 21.19 | 39.2 | 0.75 / 0.44 / 1.19 | 0.57 | B 0.50, C 0.49 | 0.761 | 2 | 1049 | PASS |
| placement correct | reuse_dyn | 0.70 | 4.30 | 9.10 | 42.6 | 0.72 / 0.28 / 1.00 | 0.00 | B 0.72 | None | 0 | 1039 | PASS |
| placement incorrect | reuse_dyn | 0.74 | 14.94 | 19.14 | 42.3 | 0.72 / 0.51 / 1.23 | 0.50 | B 0.71 | None | 1 | 1043 | PASS |

9 runs; 0 failing.
