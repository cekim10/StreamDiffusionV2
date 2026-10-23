# XB shakedown check

| scenario | policy | valid | stop | TTFO-local (s) | delivery gap (s) | remote chunks | first >= 35 dB idx | terminal PSNR | notes |
|---|---|---|---|---|---|---|---|---|---|
| XB1_dog | full | True | horizon | 54.27 | 54.27 | 0 | 0 | 99.0 | - |
| XB1_dog | precopy_full | True | horizon | 214.65 | 52.16 | 245 | 0 | 99.0 | - |
| XB1_dog | precopy_sink | True | horizon | 25.47 | 8.29 | 26 | 8 | 49.4 | - |
| XB1_dog | recompute_full | True | horizon | 36.73 | 18.35 | 30 | 0 | 99.0 | - |
| XB1_dog | recompute_win | True | horizon | 4.83 | 4.17 | 1 | - | 23.3 | - |
| XB1_dog | reuse_dyn2 | True | horizon | 0.68 | 0.69 | 0 | 31 | 44.2 | - |
| XB1_dog | split_wait | True | horizon | 14.99 | 14.99 | 0 | 8 | 47.3 | - |
| XB1_bfly | full | True | horizon | 54.36 | 54.36 | 0 | 0 | 99.0 | - |
| XB1_bfly | precopy_full | True | horizon | 218.35 | 52.73 | 251 | 0 | 99.0 | - |
| XB1_bfly | precopy_sink | True | horizon | 26.38 | 9.44 | 26 | 10 | 34.0 | - |
| XB1_bfly | recompute_full | True | horizon | 36.56 | 18.23 | 30 | 0 | 99.0 | - |
| XB1_bfly | recompute_win | True | horizon | 5.47 | 4.21 | 2 | - | 21.6 | - |
| XB1_bfly | reuse_dyn2 | True | horizon | 0.68 | 0.70 | 0 | - | 30.4 | - |
| XB1_bfly | split_wait | True | horizon | 14.98 | 14.98 | 0 | 8 | 36.2 | - |
| XB2_dog | precopy_sink | True | horizon | 25.11 | 8.18 | 26 | 8 | 49.1 | - |
| XB2_dog | recompute_full | True | horizon | 134.26 | 65.51 | 112 | 0 | 99.0 | - |
| XB2_dog | reuse_dyn2 | True | horizon | 0.68 | 0.69 | 0 | 31 | 49.5 | - |

SHAKEDOWN FAIL
- XB3_dog: 0 methods with a run, expected 5
- XB4_dog: 0 methods with a run, expected 5
