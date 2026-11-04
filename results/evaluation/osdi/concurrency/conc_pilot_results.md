# Concurrency pilot (measured; pilot, not a hypothesis test)

Protocol: `pilot_protocol.md`. One run per session; C1 = S1 alone. Window = trigger -> first local output. NIC = the destination host's peak 10 s receive rate.

| cond | method | session | valid | TTFO-local (s) | gap (s) | bytes (GB) | served calls/s in window | dest. NIC peak (Mbps) | GPU reserved / RSS peak A, B (GB) | vs C1: TTFO / gap (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | Full | S1 | True  | 54.16 | 54.16 | 6.463 | 0.00 | 1035 | 26.0 / 34.2, 29.4 / 35.5 |  |
| C1 | OTTER | S1 | True  | 23.71 | 1.61 | 1.763 | 1.43 | 1033 | 29.2 / 31.6, 30.7 / 28.2 |  |
| C1 | R-full | S1 | True  | 38.24 | 19.22 | 0.085 | 0.81 | 35 | 26.0 / 29.9, 29.2 / 27.6 |  |
| C2 | OTTER | S1 | True  | 23.67 | 1.62 | 1.763 | 1.44 | 1034 | 29.2 / 30.0, 30.7 / 27.4 | -0.04 / +0.00 |
| C2 | OTTER | S2 | True  | 23.03 | 1.64 | 1.763 | 1.43 | 1035 | 29.2 / 31.6, 30.7 / 28.3 | -0.68 / +0.03 |
| C3a | Full | S1 | False ['NIC peak > 1.15 x cap'] | 54.52 | 54.52 | 6.463 | 0.00 | 2068 | 26.0 / 34.2, 29.4 / 35.5 | +0.36 / +0.36 |
| C3a | Full | S2 | False ['NIC peak > 1.15 x cap'] | 54.47 | 54.47 | 6.463 | 0.00 | 2069 | 26.0 / 34.3, 29.4 / 33.9 | +0.32 / +0.32 |
| C3a | OTTER | S1 | False ['NIC B rx 10 s mean 1461 Mbps > 1.15 x 1000'] | 23.96 | 1.66 | 1.763 | 1.42 | 2067 | 29.2 / 31.6, 30.7 / 28.2 | +0.25 / +0.04 |
| C3a | OTTER | S2 | False ['NIC B rx 10 s mean 1289 Mbps > 1.15 x 1000'] | 23.24 | 1.69 | 1.763 | 1.42 | 2066 | 29.2 / 31.7, 30.7 / 26.7 | -0.47 / +0.08 |
| C3a | R-full | S1 | True  | 37.17 | 18.71 | 0.084 | 0.81 | 70 | 26.0 / 29.8, 29.2 / 25.9 | -1.06 / -0.51 |
| C3a | R-full | S2 | True  | 38.39 | 19.58 | 0.085 | 0.81 | 70 | 26.0 / 29.9, 29.2 / 26.4 | +0.15 / +0.37 |

| cond | method | trigger offset S2 - S1 (s) | window overlap (s) | overlap / shorter window | both completed | both valid |
|---|---|---|---|---|---|---|
| C2 | OTTER | 0.000 | 23.03 | 1.00 | True | True |
| C3a | Full | 0.000 | 54.47 | 1.00 | True | False |
| C3a | OTTER | -0.000 | 23.24 | 1.00 | True | False |
| C3a | R-full | -0.000 | 37.17 | 1.00 | True | True |

Condition-aware validity (`condition_valid`; the original `valid` above is unchanged). Host cap: C1 / C2 / C3a = 1 Gbps x the sessions on that NIC direction, each shaped to its own emulated 1 Gbps link (C3a: two independent links on one physical NIC, not a shared link); C3b / C4 = one shared 1 Gbps. Burst = largest sample of <= 1.5 s (1.03 s typical) <= 1.15 x; sustained = largest time-weighted mean over >= 10 s <= 1.05 x (after the header factor). Per session: configured rate, completion, per-transfer rate.

| cond | method | session | condition_valid | NIC links used (host:dir, sessions, burst / sustained x host cap) | transfers (Mbps payload) | coarse samples (max s) | reasons |
|---|---|---|---|---|---|---|---|
| C1 | Full | S1 | True | elves-01:tx 1: 0.994 / 0.988 x 1, elves-03:rx 1: 0.993 / 0.988 x 1 | full 983 | 2 (3.8) | - |
| C1 | OTTER | S1 | True | elves-01:tx 1: 0.990 / 0.985 x 1, elves-03:rx 1: 0.996 / 0.986 x 1 | precopy 826 | 2 (1.9) | - |
| C1 | R-full | S1 | True | elves-01:tx 1: 0.333 / 0.033 x 1, elves-03:rx 1: 0.335 / 0.033 x 1 | inputs 397, inputs 365 | 0 (0.0) | - |
| C2 | OTTER | S1 | True | elves-01:tx 1: 0.994 / 0.986 x 1, elves-03:rx 1: 0.994 / 0.987 x 1 | precopy 828 | 2 (1.7) | - |
| C2 | OTTER | S2 | True | elves-02:rx 1: 1.001 / 0.988 x 1, elves-04:tx 1: 0.990 / 0.987 x 1 | precopy 832 | 2 (1.8) | - |
| C3a | Full | S1 | True | elves-01:tx 2: 0.991 / 0.987 x 2, elves-03:rx 2: 0.991 / 0.987 x 2 | full 985 | 2 (3.9) | - |
| C3a | Full | S2 | True | elves-01:tx 2: 0.991 / 0.987 x 2, elves-03:rx 2: 0.992 / 0.987 x 2 | full 984 | 4 (4.4) | - |
| C3a | OTTER | S1 | True | elves-01:tx 2: 0.988 / 0.986 x 2, elves-03:rx 2: 0.993 / 0.987 x 2 | precopy 820 | 0 (0.0) | - |
| C3a | OTTER | S2 | True | elves-01:tx 2: 0.988 / 0.986 x 2, elves-03:rx 2: 0.990 / 0.986 x 2 | precopy 822 | 4 (2.2) | - |
| C3a | R-full | S1 | True | elves-01:tx 2: 0.309 / 0.033 x 2, elves-03:rx 2: 0.317 / 0.033 x 2 | inputs 450, inputs 363 | 0 (0.0) | - |
| C3a | R-full | S2 | True | elves-01:tx 2: 0.334 / 0.033 x 2, elves-03:rx 2: 0.249 / 0.033 x 2 | inputs 429, inputs 367 | 2 (2.3) | - |

Verification 1, measured (host NIC / cap after the header factor; burst 1 s <= 1.15, sustained 10 s <= 1.05):

| cond | method | session | host:dir | peak 1 s | peak 10 s mean | ok |
|---|---|---|---|---|---|---|
