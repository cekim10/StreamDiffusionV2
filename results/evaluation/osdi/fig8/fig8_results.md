# Fig. 8 results

**F8-H1 (total stall): SUPPORTED. F8-H2 (native performance): NOT SUPPORTED.**

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
| native, host A | 5 | 0.5309 [0.5309-0.5310] | 7.53 |
| native, host B | 5 | 0.5277 [0.5272-0.5278] | 7.58 |
| OTTER generation, B | 5 | 0.5554 [0.5552-0.5562] | 7.20 |
| OTTER generation + tracking, B | 5 | 0.5560 [0.5558-0.5569] | 7.19 |

OTTER tracking per call: median 0.572 ms. F8-H2 ratio 1.0536 -> False

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
| native, host A | 5 | 0.5323 [0.5313-0.5330] | 7.52 |
| native, host B | 5 | 0.5281 [0.5275-0.5283] | 7.57 |
| OTTER generation, B | 5 | 0.5565 [0.5522-0.5565] | 7.19 |
| OTTER generation + tracking, B | 5 | 0.5571 [0.5528-0.5571] | 7.18 |

OTTER tracking per call: median 0.578 ms. F8-H2 ratio 1.0548 -> False

