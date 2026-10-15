# Step 2 criteria (restore_holder), medians of valid runs

Valid runs 180/180; invalid: none; incomplete directories: none

## Makespan (s) and source bytes per session (Sinks); C = pre-registered crossover condition

| N | B_h | C | restart | reuse_fixed | reuse_adaptive | reuse_aware | P0 restart < fixed - 3.5 s | H4a aware <= 0.85 fixed | H4b aware <= 1.05 min(fixed*, restart) | H4c source |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 62.5 | yes | 21.0 /1.50 | 118.3 /1.00 | 21.1 /1.44 | 21.1 /1.44 | ok | ok | ok | ok |
| 1 | 125 | yes | 21.0 /1.50 | 62.8 /1.00 | 21.0 /1.40 | 21.0 /1.39 | ok | ok | ok | ok |
| 1 | 250 | yes | 21.0 /1.50 | 35.1 /1.00 | 21.0 /1.33 | 21.0 /1.30 | ok | ok | ok | ok |
| 1 | 500 |  | 21.0 /1.50 | 21.2 /1.00 | 21.1 /1.25 | 21.1 /1.17 |  |  | ok | FAIL |
| 1 | 1000 |  | 21.0 /1.50 | 21.0 /1.00 | 21.1 /1.17 | 21.1 /1.00 |  |  | ok | ok |
| 2 | 62.5 | yes | 36.6 /1.32 | 92.8 /1.00 | 35.3 /1.26 | 34.2 /1.21 | ok | ok | ok | ok |
| 2 | 125 | yes | 36.6 /1.32 | 50.9 /1.00 | 34.5 /1.22 | 31.7 /1.12 | ok | ok | ok | ok |
| 2 | 250 |  | 36.6 /1.32 | 29.8 /1.00 | 33.4 /1.17 | 29.0 /1.01 |  |  | ok | ok |
| 2 | 500 |  | 36.6 /1.32 | 29.0 /1.00 | 32.2 /1.12 | 29.0 /1.00 |  |  | ok | ok |
| 2 | 1000 |  | 36.6 /1.32 | 29.0 /1.00 | 31.5 /1.09 | 29.0 /1.00 |  |  | ok | ok |
| 4 | 62.5 | yes | 65.1 /1.17 | 84.4 /1.00 | 63.1 /1.14 | 57.3 /1.03 | ok | ok | ok | ok |
| 4 | 125 |  | 65.2 /1.17 | 55.5 /1.00 | 61.8 /1.11 | 55.5 /1.00 |  |  | ok | ok |
| 4 | 250 |  | 65.2 /1.17 | 55.4 /1.00 | 59.7 /1.08 | 55.5 /1.00 |  |  | ok | ok |
| 4 | 500 |  | 65.2 /1.17 | 55.5 /1.00 | 58.2 /1.05 | 55.5 /1.00 |  |  | ok | ok |
| 4 | 1000 |  | 65.2 /1.17 | 55.5 /1.00 | 57.4 /1.04 | 55.5 /1.00 |  |  | ok | ok |

(* in the no-crossover set only; everywhere aware must also be within 1.05 x restart)

- P0: holds
- H4a: holds
- H4b: holds
- H4c: fails at [(1, 500.0)]

Outcome mapping: Case 1 (bottleneck-aware provider selection + progress preservation)
