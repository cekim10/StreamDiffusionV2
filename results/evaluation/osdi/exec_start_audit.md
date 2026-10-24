# EXEC_START impact audit - execution evidence (2026-10-23)

Read-only scan of every non-dry run directory. 'A chunks' = chunks the source delivered at or after the trigger (orchestrator metrics log).
A generating source advances about L / 0.56 s calls before the move; a dead one leaves the move at the trigger call.

| experiment | path | runs | exec_start event | A first_output event | runs with 0 A chunks | move call == trigger call | window L (s) |
|---|---|---|---|---|---|---|---|
| d0_shakedown | placement_window | 2 | 2 | 0 | 2 | 2 | - |
| d0_shakedown_rerun | placement_window | 2 | 2 | 0 | 2 | 2 | - |
| expD_A | cold_destination | 6 | 6 | 0 | 6 | 6 | - |
| expD_C | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expD_D | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expD_correctness | cold_destination | 1 | 1 | 0 | 1 | 1 | - |
| expD_correctness | placement_window | 6 | 6 | 0 | 6 | 6 | - |
| expN_cell1 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expN_cell10 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expN_cell2 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expN_cell3 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expN_cell4 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expN_cell5 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expN_cell6 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expN_cell7 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expN_cell8 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expN_cell9 | placement_window | 9 | 9 | 0 | 9 | 9 | - |
| expV_a1_cell1 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_a1_cell2 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_a1_cell3 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_a1_cell8 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_cell1 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_cell2 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_cell3 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_cell4 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_cell5 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_cell6 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_cell7 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expV_cell8 | placement_window | 12 | 12 | 0 | 12 | 12 | - |
| expXB_ALT_bfly | xb_fixed | 9 | 9 | 9 | 0 | 9 | - |
| expXB_ALT_dog | xb_fixed | 9 | 9 | 9 | 0 | 9 | - |
| expXB_XB1_bfly | xb_fixed | 12 | 12 | 12 | 0 | 12 | - |
| expXB_XB1_dog | xb_fixed | 12 | 12 | 12 | 0 | 12 | - |
| expXB_XB2_dog | xb_fixed | 6 | 6 | 6 | 0 | 6 | - |
| expXB_XB3_dog | xb_fixed | 6 | 6 | 6 | 0 | 6 | - |
| expXB_XB4_dog | xb_fixed | 6 | 6 | 6 | 0 | 6 | - |
| expXB_cal | xb_fixed | 43 | 43 | 43 | 0 | 43 | - |
| expXB_cal_void1 | xb_before_fix | 7 | 7 | 0 | 7 | 7 | - |
| expXB_gate_bfly | xb_fixed | 2 | 2 | 2 | 0 | 2 | - |
| expXB_gate_bfly_void1 | xb_before_fix | 2 | 2 | 0 | 2 | 2 | - |
| expXB_gate_dog | xb_fixed | 2 | 2 | 2 | 0 | 2 | - |
| expXB_gate_dog_void1 | xb_before_fix | 2 | 2 | 0 | 2 | 2 | - |
| expXB_shk_XB1_bfly | xb_fixed | 4 | 4 | 4 | 0 | 4 | - |
| expXB_shk_XB1_dog | xb_fixed | 4 | 4 | 4 | 0 | 4 | - |
| expXB_shk_XB2_dog | xb_fixed | 2 | 2 | 2 | 0 | 2 | - |
| expXB_shk_XB3_dog | xb_fixed | 2 | 2 | 2 | 0 | 2 | - |
| expXB_shk_XB4_dog | xb_fixed | 2 | 2 | 2 | 0 | 2 | - |
| m3dev_cell10 | placement_window | 3 | 3 | 0 | 3 | 3 | - |
| m3dev_cell7 | placement_window | 3 | 3 | 0 | 3 | 3 | - |
| m3dev_cell8 | placement_window | 3 | 3 | 0 | 3 | 3 | - |
| m3dev_cell9 | placement_window | 3 | 3 | 0 | 3 | 3 | - |
| m3dev_r2_cell10 | placement_window | 3 | 3 | 0 | 3 | 3 | - |
| m3dev_r2_cell7 | placement_window | 3 | 3 | 0 | 3 | 3 | - |
| m3dev_r2_cell8 | placement_window | 3 | 3 | 0 | 3 | 3 | - |
| m3dev_r2_cell9 | placement_window | 3 | 3 | 0 | 3 | 3 | - |
| restore_epilot | network_only_harness | 9 | 0 | 0 | 9 | 0 | [10.0] |
| restore_epilot_v2 | network_only_harness | 6 | 0 | 0 | 6 | 0 | [10.0] |
| restore_holder_diag | network_only_harness | 60 | 0 | 0 | 60 | 0 | [10.0] |
| restore_prepos_a3 | network_only_harness | 31 | 0 | 0 | 31 | 0 | [10.0] |
| restore_prepos_pilot | network_only_harness | 12 | 0 | 0 | 12 | 0 | [10.0] |
| shk_N_cell9 | placement_window | 2 | 2 | 0 | 2 | 2 | - |

Affected paths: 312 runs; source delivered 0 chunks after the trigger in 312.
Not applicable (network-only harness, no model generation): 118 runs (restore_epilot, restore_epilot_v2, restore_holder_diag, restore_prepos_a3, restore_prepos_pilot).
XB after the fix (0b034dd): 121 runs; source delivered chunks in 121 (pre-copy / recompute keep the source generating; R-win stops it within ~1-2 chunks).

## Related design property (not the bug): chunk-boundary wait at OTTER handoffs

A handoff waits for the generating owner to finish its current chunk. At the first move the source has just finished SOURCE_PREP and is idle at a boundary.
At later moves the owner is generating. Values are moves[i].t_stop - t_req over every OTTER-style run with moves:

- first moves: n = 892, median 0.002 s, P90 0.003 s, max 0.018 s
- later moves: n = 924, median 0.205 s, P90 0.421 s, max 0.644 s
