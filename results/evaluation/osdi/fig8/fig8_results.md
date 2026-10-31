# Fig. 8 results

**F8-H1 (total stall): SUPPORTED. F8-H2 (native performance): NOT EVALUABLE.**

## Low-refresh (dog)

| method | valid / runs | total stall (s) | stalls | T_ref (s) |
|---|---|---|---|---|
| Full | 5 / 5 | 53.64 [53.58-53.65] | 1 | 0.597 |
| Llumnix-style | 5 / 5 | 61.80 [61.48-62.04] | 10 | 0.610 |
| ServerlessLLM-style | 5 / 5 | 17.86 [17.82-17.90] | 1 | 0.605 |
| OTTER | 5 / 5 | 1.99 [1.96-2.02] | 2 | 0.603 |

F8-H1 ratio 0.111 -> True

| 8b | n | per call (s) | frames/s |
|---|---|---|---|
| native, host A | 0 | - [---] | - |
| native, host B | 0 | - [---] | - |
| OTTER generation, B | 0 | - [---] | - |
| OTTER generation + tracking, B | 0 | - [---] | - |

OTTER tracking per call: median - ms. F8-H2 ratio - -> None

## High-refresh (bfly)

| method | valid / runs | total stall (s) | stalls | T_ref (s) |
|---|---|---|---|---|
| Full | 5 / 5 | 53.62 [53.45-53.63] | 1 | 0.597 |
| Llumnix-style | 5 / 5 | 63.48 [63.41-63.52] | 10 | 0.608 |
| ServerlessLLM-style | 5 / 5 | 17.73 [17.70-17.76] | 1 | 0.604 |
| OTTER | 5 / 5 | 1.87 [1.87-2.10] | 2 | 0.604 |

F8-H1 ratio 0.106 -> True

| 8b | n | per call (s) | frames/s |
|---|---|---|---|
| native, host A | 0 | - [---] | - |
| native, host B | 0 | - [---] | - |
| OTTER generation, B | 0 | - [---] | - |
| OTTER generation + tracking, B | 0 | - [---] | - |

OTTER tracking per call: median - ms. F8-H2 ratio - -> None

