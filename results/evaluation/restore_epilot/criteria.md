# Experiment E pilot (restore_epilot), medians of valid runs

Valid runs 21/21; invalid: none

## Scenario A: forwarder collapse (C egress 1 Gbps -> 62.5 Mbps when D holds 50 %)

| policy | T_r (s) | model | others' makespan | model | source Sinks | model | total Sinks | re-plans (model) | detection (s) | transition (s) | drained (MiB) | duplicates (MiB) | dT / C_switch (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| restart | 14.0 | 14.1 | - | - | 2.00 | 2.02 | 2.00 | 0 (0) | - | - | - | 0.0 | - |
| reuse_fixed | 80.2 | 81.8 | - | - | 1.00 | 1.01 | 2.00 | 0 (0) | - | - | - | 0.0 | - |
| reuse_aware_in | 53.3 | 53.9 | - | - | 1.00 | 1.01 | 2.00 | 0 (0) | - | - | - | 0.0 | - |
| reuse_dyn | 14.0 | 14.2 | - | - | 1.18 | 1.19 | 2.01 | 2 (1) | 2.25 | 0.05 | 4.0 | 0.0 | 1.8 / 0.41; 28.0 / 0.97 |

M3 candidate vs M2 (aware at moves): T_r 53.3 -> 14.0 s (+39.3 s, +74 %); source 1.00 -> 1.18 Sinks; re-plans 2; drained 4.0 MiB per re-plan; duplicates 0.0 MiB.

## Scenario B: source share change at the 250 Mbps crossover (N = 4)

| policy | T_r (s) | model | others' makespan | model | source Sinks | model | total Sinks | re-plans (model) | detection (s) | transition (s) | drained (MiB) | duplicates (MiB) | dT / C_switch (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reuse_fixed | 40.0 | 40.2 | 58.6 | 58.8 | 4.00 | 4.01 | 5.07 | 0 (0) | - | - | - | 0.0 | - |
| reuse_aware_in | 41.6 | 41.8 | 62.0 | 62.2 | 4.25 | 4.26 | 5.07 | 0 (0) | - | - | - | 0.0 | - |
| reuse_dyn | 37.9 | 38.4 | 61.1 | 61.3 | 4.18 | 4.19 | 5.07 | 1 (1) | - | 0.00 | 4.0 | 0.0 | 4.0 / 0.44 |

M3 candidate vs M2 (aware at moves): T_r 41.6 -> 37.9 s (+3.8 s, +9 %); source 4.25 -> 4.18 Sinks; re-plans 1; drained 4.0 MiB per re-plan; duplicates 0.0 MiB.

## Model agreement

- T_r: max |measured - model| = 1.68 s (median 0.19) over 21 runs
