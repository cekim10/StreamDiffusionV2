# Scenario B criteria (restore_contention_v2), medians of valid runs

Valid runs 72/72; invalid: none; incomplete directories: none

## H3a single move: reuse_fixed makespan shorter than restart by >= 0.5 T_m (3.5 s)

| N | restart | reuse_fixed | reuse_adaptive | restart - fixed | H3a |
|---|---|---|---|---|---|
| 1 | 21.0 | 21.0 | 21.1 | -0.0 | not supported |
| 2 | 36.6 | 29.0 | 31.5 | 7.6 | supported |
| 4 | 65.1 | 55.5 | 57.4 | 9.7 | supported |
| 8 | 121.0 | 110.8 | 112.1 | 10.2 | supported |

## H3a continuous: restart restores < N sessions in all reps while reuse_fixed restores all N in all reps

| N | restart restored (min over reps) | reuse_fixed restored all in all reps | reuse_fixed coverage | H3a |
|---|---|---|---|---|
| 1 | 0..0 of 1 | True | 0.0 | supported |
| 2 | 0..0 of 2 | True | 0.2 | supported |
| 4 | 0..0 of 4 | True | 0.5 | supported |
| 8 | 0..0 of 8 | True | 0.5 | supported |

## H3b: reuse_adaptive better than reuse_fixed (makespan -1 s single move, coverage +0.05 continuous), never worse by the same margin

| N | single: fixed / adaptive makespan | continuous: fixed / adaptive coverage | better | worse |
|---|---|---|---|---|
| 1 | 21.0 / 21.1 | 0.0 / 0.0 | False | False |
| 2 | 29.0 / 31.5 | 0.2 / 0.1 | False | True |
| 4 | 55.5 / 57.4 | 0.5 / 0.4 | False | True |
| 8 | 110.8 / 112.1 | 0.5 / 0.4 | False | True |

H3b: not supported (better at none, worse at [2, 4, 8])
