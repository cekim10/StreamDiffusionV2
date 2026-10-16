# Full Experiment E (restore_fulle), medians of valid runs

Valid runs 84/84; invalid: none

## 1 slow-B

| policy | T_r final owner (s) | model | per-period latencies (rep 1) | source / S | model | total / S | unused / S | re-plans (model) | held at B on return | dup MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| restart | 14.0 (14.0-14.0) | 14.1 | [None, None, 14.04] | 2.00 | 2.02 | 2.00 | 1.00 | 0 (0) | - | 0.0 |
| pp_star | 14.0 (14.0-14.0) | 14.1 | [None, None, 14.04] | 2.00 | 2.02 | 2.00 | 1.00 | 0 (0) | - | 0.0 |
| fixed_line | 14.0 (14.0-14.0) | 14.1 | [None, None, 13.95] | 1.44 | 1.45 | 2.01 | 0.44 | 0 (0) | - | 0.0 |
| fixed_tree | 56.0 (56.0-56.1) | 56.4 | [None, None, 55.95] | 1.44 | 1.45 | 2.01 | 0.50 | 0 (0) | - | 0.0 |
| fixed_butterfly | 52.5 (52.5-52.5) | 52.9 | [None, None, 52.45] | 1.00 | 1.00 | 2.01 | 0.03 | 0 (0) | - | 0.0 |
| reuse_aware_in | 14.0 (14.0-14.0) | 14.1 | [None, None, 13.97] | 1.38 | 1.39 | 2.01 | 0.38 | 0 (0) | - | 0.0 |
| reuse_dyn | 14.0 (14.0-14.0) | 14.1 | [None, None, 13.98] | 1.38 | 1.39 | 2.01 | 0.38 | 0 (0) | - | 0.0 |

Pareto frontier (T_r, source Sinks, total Sinks): ['fixed_butterfly', 'reuse_aware_in', 'reuse_dyn']; dominated: restart by ['fixed_line', 'reuse_aware_in', 'reuse_dyn'], pp_star by ['fixed_line', 'reuse_aware_in', 'reuse_dyn'], fixed_line by ['reuse_aware_in', 'reuse_dyn'], fixed_tree by ['fixed_line', 'fixed_butterfly', 'reuse_aware_in', 'reuse_dyn']

## 2 shared source

| policy | T_r final owner (s) | model | per-period latencies (rep 1) | source / S | model | total / S | unused / S | re-plans (model) | held at B on return | dup MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| restart | 54.6 (54.6-54.6) | 54.7 | [None, None, 55.47, None, None, 55.01, None, None, 54.13, None, None, 52.83] | 1.30 | 1.30 | 1.30 | 0.30 | 0 (0) | - | 0.0 |
| pp_star | 54.6 (54.6-54.6) | 54.7 | [None, None, 55.46, None, None, 55.01, None, None, 54.14, None, None, 52.83] | 1.30 | 1.30 | 1.30 | 0.30 | 0 (0) | - | 0.0 |
| fixed_line | 38.7 (38.7-38.7) | 39.0 | [None, None, 41.32, None, None, 39.55, None, None, 37.86, None, None, 36.11] | 1.00 | 1.00 | 1.48 | 0.00 | 0 (0) | - | 0.0 |
| fixed_tree | 45.7 (45.7-45.8) | 46.0 | [None, None, 48.27, None, None, 46.63, None, None, 44.88, None, None, 43.12] | 1.13 | 1.13 | 1.48 | 0.30 | 0 (0) | - | 0.0 |
| fixed_butterfly | 38.4 (38.4-38.5) | 38.8 | [None, None, 41.37, None, None, 39.21, None, None, 37.57, None, None, 36.14] | 1.00 | 1.00 | 1.48 | 0.09 | 0 (0) | - | 0.0 |
| reuse_aware_in | 38.7 (38.7-38.8) | 39.0 | [None, None, 41.33, None, None, 39.56, None, None, 37.86, None, None, 36.11] | 1.00 | 1.00 | 1.48 | 0.00 | 0 (0) | - | 0.0 |
| reuse_dyn | 38.8 (38.7-38.8) | 39.0 | [None, None, 41.29, None, None, 39.64, None, None, 37.89, None, None, 36.13] | 1.00 | 1.00 | 1.48 | 0.00 | 0 (0) | - | 0.0 |

Pareto frontier (T_r, source Sinks, total Sinks): ['restart', 'pp_star', 'fixed_butterfly']; dominated: fixed_line by ['fixed_butterfly'], fixed_tree by ['fixed_line', 'fixed_butterfly', 'reuse_aware_in', 'reuse_dyn'], reuse_aware_in by ['fixed_butterfly'], reuse_dyn by ['fixed_butterfly']

## 3 C degradation

| policy | T_r final owner (s) | model | per-period latencies (rep 1) | source / S | model | total / S | unused / S | re-plans (model) | held at B on return | dup MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| restart | 14.0 (14.0-14.0) | 14.1 | [None, None, 14.0] | 2.00 | 2.02 | 2.00 | 1.00 | 0 (0) | - | 0.0 |
| pp_star | 14.0 (14.0-14.0) | 14.1 | [None, None, 14.01] | 2.00 | 2.02 | 2.00 | 1.00 | 0 (0) | - | 0.0 |
| fixed_line | 62.8 (62.8-62.9) | 63.5 | [None, None, 62.84] | 1.25 | 1.26 | 2.01 | 0.25 | 0 (0) | - | 0.0 |
| fixed_tree | 14.0 (14.0-14.0) | 14.1 | [None, None, 13.98] | 1.25 | 1.26 | 2.01 | 0.50 | 0 (0) | - | 0.0 |
| fixed_butterfly | 53.2 (53.2-53.3) | 53.9 | [None, None, 53.23] | 1.00 | 1.01 | 2.01 | 0.13 | 0 (0) | - | 0.0 |
| reuse_aware_in | 53.8 (53.8-53.8) | 53.9 | [None, None, 53.78] | 1.00 | 1.01 | 2.01 | 0.12 | 0 (0) | - | 0.0 |
| reuse_dyn | 14.0 (14.0-14.0) | 14.2 | [None, None, 13.98] | 1.18 | 1.19 | 2.01 | 0.31 | 2 (1) | - | 0.0 |

Pareto frontier (T_r, source Sinks, total Sinks): ['fixed_butterfly', 'reuse_dyn']; dominated: restart by ['fixed_tree', 'reuse_dyn'], pp_star by ['fixed_tree', 'reuse_dyn'], fixed_line by ['fixed_tree', 'fixed_butterfly', 'reuse_aware_in', 'reuse_dyn'], fixed_tree by ['reuse_dyn'], reuse_aware_in by ['fixed_butterfly']

## 4 revisit

| policy | T_r final owner (s) | model | per-period latencies (rep 1) | source / S | model | total / S | unused / S | re-plans (model) | held at B on return | dup MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| restart | 14.0 (14.0-14.0) | 14.1 | [None, None, None, 13.99] | 2.51 | 2.53 | 2.51 | 1.00 | 0 (0) | 0.00 | 0.0 |
| pp_star | 7.0 (7.0-7.0) | 7.1 | [None, None, None, 7.01] | 2.00 | 2.02 | 2.00 | 1.00 | 0 (0) | 0.50 | 0.0 |
| fixed_line | 7.0 (7.0-7.0) | 7.1 | [None, None, None, 6.99] | 1.50 | 1.51 | 2.01 | 0.75 | 0 (0) | 0.50 | 0.0 |
| fixed_tree | 7.0 (7.0-7.0) | 7.1 | [None, None, None, 6.97] | 1.51 | 1.51 | 2.01 | 1.01 | 0 (0) | 0.50 | 0.0 |
| fixed_butterfly | 7.0 (7.0-7.0) | 7.1 | [None, None, None, 6.99] | 1.00 | 1.01 | 2.01 | 0.44 | 0 (0) | 0.50 | 0.0 |
| reuse_aware_in | 7.0 (6.9-7.0) | 7.1 | [None, None, None, 6.95] | 1.00 | 1.01 | 2.01 | 0.44 | 0 (0) | 0.50 | 0.0 |
| reuse_dyn | 7.0 (6.9-7.0) | 7.1 | [None, None, None, 6.95] | 1.00 | 1.01 | 2.01 | 0.44 | 0 (0) | 0.50 | 0.0 |

Pareto frontier (T_r, source Sinks, total Sinks): ['fixed_butterfly', 'reuse_aware_in', 'reuse_dyn']; dominated: restart by ['pp_star', 'fixed_line', 'fixed_tree', 'fixed_butterfly', 'reuse_aware_in', 'reuse_dyn'], pp_star by ['fixed_line', 'fixed_tree', 'fixed_butterfly', 'reuse_aware_in', 'reuse_dyn'], fixed_line by ['fixed_butterfly', 'reuse_aware_in', 'reuse_dyn'], fixed_tree by ['fixed_butterfly', 'reuse_aware_in', 'reuse_dyn']

## Frozen verdicts (TOPOLOGY_PLAN F)

- H8a (slow-B: aware-at-moves <= 0.75 x best fixed forwarding plan and within 1 s of star; no fixed plan beats it by > 1 s): not supported (aware 14.0, best forwarding 14.0, star 14.0, beaten by none)
- H8b (C degradation: dynamic <= 0.5 x aware-at-moves with <= 2 re-plans; never worse than aware-at-moves by > 1 s elsewhere): supported (dynamic 14.0, aware 53.8, re-plans 2, worse in none)
- H8c (shared-source and revisit: every progress-aware policy sends >= 0.25 Sink less from the source than restart and none is Pareto-dominated by restart): not supported (2 shared source: restart 1.30 S, fewer-by-0.25 False, dominated by restart none; 4 revisit: restart 2.51 S, fewer-by-0.25 True, dominated by restart none)

## Model agreement

- T_r: max |measured - model| = 0.70 s (median 0.17) over 84 runs
