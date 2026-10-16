# Experiment E pilot (restore_epilot_v2), medians of valid runs

Valid runs 21/21; invalid: none

## A1: forwarder collapse (C egress 1 Gbps -> 62.5 Mbps when D holds 50 %)

| policy | T_r (s) | model | others' makespan | model | source Sinks | model | total Sinks | re-plans (model) | premature | oscillations | detection (s) | transition (s) | drained (MiB) | duplicates (MiB) | dT / C_switch (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reuse_dyn | 14.0 | 14.2 | - | - | 1.18 | 1.19 | 2.00 | 2 (1) | 0 | 0 | 1.73 | 0.04 | 4.0 | 0.0 | 5.5 / 0.44; 19.7 / 0.97 |
## A0: no-collapse control (same mobility, no cap event)

| policy | T_r (s) | model | others' makespan | model | source Sinks | model | total Sinks | re-plans (model) | premature | oscillations | detection (s) | transition (s) | drained (MiB) | duplicates (MiB) | dT / C_switch (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reuse_aware_in | 14.0 | 14.1 | - | - | 1.00 | 1.01 | 2.00 | 0 (0) | 0 | 0 | - | - | - | 0.0 | - |
| reuse_dyn | 14.0 | 14.1 | - | - | 1.00 | 1.01 | 2.00 | 0 (0) | 0 | 0 | - | - | - | 0.0 | - |

M3 candidate vs M2 (aware at moves): T_r 14.0 -> 14.0 s (-0.0 s, -0 %); source 1.00 -> 1.00 Sinks; re-plans 0; drained - MiB per re-plan; duplicates 0.0 MiB.

## A2: collapse, then C recovers to 1 Gbps 5 s later

| policy | T_r (s) | model | others' makespan | model | source Sinks | model | total Sinks | re-plans (model) | premature | oscillations | detection (s) | transition (s) | drained (MiB) | duplicates (MiB) | dT / C_switch (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reuse_aware_in | 14.6 | 14.9 | - | - | 1.00 | 1.01 | 2.00 | 0 (0) | 0 | 0 | - | - | - | 0.0 | - |
| reuse_dyn | 14.0 | 14.1 | - | - | 1.18 | 1.19 | 2.00 | 2 (1) | 0 | 0 | 1.73 | 0.04 | 4.0 | 0.0 | 5.6 / 0.44; 19.8 / 0.97 |

M3 candidate vs M2 (aware at moves): T_r 14.6 -> 14.0 s (+0.6 s, +4 %); source 1.00 -> 1.18 Sinks; re-plans 2; drained 4.0 MiB per re-plan; duplicates 0.0 MiB.

## Scenario B: source share change at the 250 Mbps crossover (N = 4)

| policy | T_r (s) | model | others' makespan | model | source Sinks | model | total Sinks | re-plans (model) | premature | oscillations | detection (s) | transition (s) | drained (MiB) | duplicates (MiB) | dT / C_switch (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reuse_aware_in | 41.6 | 41.8 | 62.1 | 62.2 | 4.25 | 4.26 | 5.07 | 0 (0) | 0 | 0 | - | - | - | 0.0 | - |
| reuse_dyn | 37.7 | 38.1 | 61.1 | 61.2 | 4.18 | 4.19 | 5.07 | 1 (1) | 0 | 0 | - | 0.03 | 4.0 | 0.0 | 4.3 / 0.44 |

M3 candidate vs M2 (aware at moves): T_r 41.6 -> 37.7 s (+4.0 s, +10 %); source 4.25 -> 4.18 Sinks; re-plans 1; drained 4.0 MiB per re-plan; duplicates 0.0 MiB.

## Model agreement

- T_r: max |measured - model| = 0.49 s (median 0.15) over 21 runs
