# D0: recovered per-fragment node logs

Read-only check of `node_{B,C,D}/fragments.csv` copied back from elves-02..04 (`tools/eval/recover_node_logs.sh`).

| experiment | runs | runs with B, C and D logs | files | failing files | distinct verified GiB | repeat or rejected receipts |
|---|---|---|---|---|---|---|
| restore_contention | 72 | 72 | 216 | 0 | 719.8 | 0 |
| restore_contention_v2 | 72 | 72 | 216 | 0 | 719.5 | 0 |
| restore_dissem_hetero | 45 | 45 | 135 | 0 | 216.9 | 0 |
| restore_dissem_pilot | 5 | 5 | 15 | 0 | 24.1 | 0 |
| restore_epilot | 21 | 21 | 63 | 0 | 112.0 | 1 |
| restore_epilot_v2 | 21 | 21 | 63 | 0 | 97.2 | 1 |
| restore_fulle | 84 | 84 | 252 | 0 | 395.5 | 0 |
| restore_holder | 180 | 180 | 540 | 0 | 849.7 | 0 |
| restore_holder_diag | 60 | 60 | 180 | 0 | 464.8 | 0 |
| restore_holder_h4c | 45 | 45 | 135 | 0 | 212.2 | 0 |
| restore_prepos_a3 | 31 | 31 | 93 | 0 | 203.7 | 0 |
| restore_prepos_pilot | 12 | 12 | 36 | 0 | 23.9 | 0 |

Failures: 0
