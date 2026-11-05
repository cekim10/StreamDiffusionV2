# Fig. 10 long ages (exploratory calibration for E9 D5; measured)

Protocol: `longage_protocol.md`. No hypothesis is tested. Medians [min-max] over valid reps; E9 = the simulator's current extrapolation (150-240 slope, capped at the Sink).

## Low-refresh (dog)

| age | arm | valid | base (MB) | E9 extrapolated delta (MB) | readiness (s) | interruption (s) | fallbacks | retained held to 2nd trigger | retained (MB) | 2nd cutover SINKOK / DELTAOK / mismatched blocks | peak RSS / GPU reserved A, B (GB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1000 | Full | 0 / 0 | - |  | - [---] | - [---] | 0 | [] | [] | [] | 0.0 / 0.0, 0.0 / 0.0 |
| 1000 | Versioned (M2) | 2 / 2 | 117.4 | 293.1 | 8.86 [8.86-8.86] | 1.41 [1.41-1.41] | 0 | [True, True] | ['1645', '1645'] | [(True, True, 0), (True, True, 0)] | 29.9 / 30.8, 28.5 / 36.6 |
| 1000 | equivalence (B's outputs S1..S2 equal per rep) | {} | | | | | | | | | |
| 3000 | Full | 0 / 0 | - |  | - [---] | - [---] | 0 | [] | [] | [] | 0.0 / 0.0, 0.0 / 0.0 |
| 3000 | Versioned (M2) | 2 / 2 | 127.0 | 932.1 | 8.89 [8.88-8.90] | 1.42 [1.41-1.42] | 0 | [True, True] | ['1645', '1645'] | [(True, True, 0), (True, True, 0)] | 57.2 / 30.7, 55.7 / 36.8 |
| 3000 | equivalence (B's outputs S1..S2 equal per rep) | {} | | | | | | | | | |

## High-refresh (bfly)

| age | arm | valid | base (MB) | E9 extrapolated delta (MB) | readiness (s) | interruption (s) | fallbacks | retained held to 2nd trigger | retained (MB) | 2nd cutover SINKOK / DELTAOK / mismatched blocks | peak RSS / GPU reserved A, B (GB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1000 | Full | 0 / 0 | - |  | - [---] | - [---] | 0 | [] | [] | [] | 0.0 / 0.0, 0.0 / 0.0 |
| 1000 | Versioned (M2) | 2 / 2 | 558.3 | 757.5 | 9.05 [8.99-9.10] | 1.42 [1.42-1.42] | 0 | [True, True] | ['1645', '1645'] | [(True, True, 0), (True, True, 0)] | 30.2 / 30.7, 28.6 / 36.8 |
| 1000 | equivalence (B's outputs S1..S2 equal per rep) | {} | | | | | | | | | |
| 3000 | Full | 0 / 0 | - |  | - [---] | - [---] | 0 | [] | [] | [] | 0.0 / 0.0, 0.0 / 0.0 |
| 3000 | Versioned (M2) | 2 / 2 | 596.6 | 1609.4 | 10.30 [10.30-10.30] | 1.49 [1.48-1.49] | 0 | [True, True] | ['1645', '1645'] | [(True, True, 0), (True, True, 0)] | 57.4 / 30.7, 55.7 / 36.7 |
| 3000 | equivalence (B's outputs S1..S2 equal per rep) | {} | | | | | | | | | |

Reading (protocol section 4): a fallback (base sent in full) is counted, never mixed into the delta medians' interpretation; the simulator is re-gated only if these values change its delta model.
