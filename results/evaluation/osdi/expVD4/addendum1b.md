# VD-4 preregistration addendum 1b: batch-row positions (2026-10-26)

Status: **approved by the user on 2026-10-26** ("Option 1: validate batch-row positions before changing A1"). Stage 0
and stage 0s are accepted and preserved. Stage 1 stays blocked until the validation below has run on the GPU and its
results have been reviewed.

This addendum does **not** change any frozen VD-4 hypothesis, condition, threshold, outcome criterion, attribution rule
or inspection protocol, and does not change the A1 implementation. It adds per-row logging and checks, and one
validation run whose outcome decides whether an addendum 2 (row-wise RoPE deltas for A1) is needed.

## 1. Finding (review of the stage-0s results)

The stage-0 A1 runs reported `rotated_slot_layers` = 18, 34, 38, 34; the stage-0s per-(layer, slot) records count 9,
17, 19, 17 pairs with a non-zero delta: exactly half. The KV cache has a **batch dimension of 2** (the stream batch;
`models/wan/causal_stream_inference.py:105` allocates `pos` as `[batch, slots]`), and the model keeps **per-row**
positions, eviction order, Sink-refresh decisions and RoPE re-alignment (`models/wan/causal_model.py:324-396`,
`_realign_kv_positions(kv_cache, i, ...)` per row `i`). `rotate_temp` loops over the rows, so it rotated 2 x 9 = 18
(layer, row, slot) triples on dog, etc.

`mobility_node.positions()` reads **row 0 only** (`p[0, s_]`). The stage-0s records confirm 2 rows (`k_elements` =
4,792,320 = 2 x 1560 x 12 x 128 per (layer, slot)). Whether row 1 carries the same positions as row 0 is not known from
the stage-0 / 0s data: no snapshot was kept and only row 0 was logged.

## 2. Audit of every use of row-0 positions

| site | used for | rows | effect |
|---|---|---|---|
| `mobility_node.positions()` (`vc_emulate.vd4_reset`: `meta_positions_equal_snapshot`, `recent_positions_equal`, `sink_positions_equal`, `positions_final_equal_snapshot`, `ts_positions_equal_snapshot_per_layer_slot`, the logged positions) | **logging and verification only** | row 0 | the position checks of stages 0 / 0s covered row 0 only; no injection depends on them |
| `vc_emulate.vd4_reset`, A1 deltas (`live_pos[li][s_] - prepare pos_[0, s_]`) | **injection**: `rotate_temp` applies these deltas to **every** row | row 0's deltas on both rows | if row 1's source or prepare positions differ from row 0's, row 1 of the temporary Sink was rotated to row 0's positions, not its own - a deviation from the preregistered A1 definition ("re-rotated to the source's slot positions") |
| `mobility_node.write_sink_slots` (`pos[0, s_]` selects the slots the prepare filled; K / V written for every row) | injection (TS-in in B0, A1, D, R, S1, S2, A1S1, A1S2; also VD-3's TSin) | row 0 selects, all rows written | correct as long as every row's prepare filled the same slots (a fresh 2-call session fills slots 0, 1 in each row); now checked (`prepare_rows_filled_identical`) |
| `mobility_node.temp_slots_left` (`pos[0, s_]`) | verification after the bind | row 0 | none on injection |
| `write_snap_slots` (oracle recent / Sink KV: `layer[k/v][:, slot] = snap[...][:, slot]`) | injection (R, DR, S1-S3, Q8, Q4) | **all rows**, no position used | unaffected |
| meta restore (`restore_state`: `layer["pos"].copy_(r["pos"])`) and V0 (`restore_all_from`) | position restoration | **whole tensor, all rows** | unaffected |
| frozen M1 bind / realign (`_realign_kv_positions` per row) | mechanism | per row | unaffected (frozen, not touched) |

Conclusion of the audit: the truncation affects **logging / verification** everywhere except one place, the **A1
deltas**, which are an injection. Tensor-value checks (K / V digests, decoder cache) and output-digest checks in stages
0 and 0s include every row and stay valid. R, S3 and D inject whole tensors and are unaffected; only their **position**
checks were row-0 only, and the meta restore they rely on copies the whole `pos` tensor. A1 is the only condition whose
result could deviate from its definition; B0, D, R, S1-S3 do not depend on positions beyond the (now checked) prepare
slot pattern.

## 3. Changes (logging and checks only; the A1 implementation is unchanged)

- `mobility_node.positions_all(slots, snap)`: per (layer, batch row, slot). `positions()` is kept as it was for the
  frozen checks.
- `supp` records: `source_positions_rows`, `prepare_positions_rows`, `final_positions_rows`, `batch_rows`,
  `rows_differ` (every (layer, row, slot) whose source position differs from row 0's, with both values),
  `batch_rows_identical` (sink slots / recent slots / all), `a1_row_deltas` (the deltas each row would need),
  `a1_row_deltas_equal_row0`.
- `checks_supp` (validity; a false one makes the stream invalid): `prepare_rows_filled_identical`,
  `meta_positions_rows_equal_snapshot` (after the fast-path restore), `positions_rows_final_equal_snapshot` (after the
  last reset operation), `ts_positions_rows_equal_snapshot`, and - when the condition injects them -
  `recent_positions_rows_equal`, `sink_positions_rows_equal`.
- `rows_differ` / `batch_rows_identical` / `a1_row_deltas_equal_row0` are **recorded, never required**: they are the
  decision gate of section 5, not a validity rule.

## 4. Stage 0r (`run_vc.py vd4 --stage 0r`)

A1 on the four stage-0 cells (dog s1 OT-1, train s0 OT-1, butterfly s0 OT-L, audi s1 OT-1), logging and verification
only; output root `results/evaluation/expVD4r/` (stage-0 and 0s results untouched); checks to
`osdi/expVC/vd4r_checks_<unit>.*`; no metrics, no clips, no inspection. Output digests must equal the stage-0s A1 run
call by call (the added logging must not change outputs). About 20 min on host D.

Gates (`vd4_gates.json`):
- `stage0_rows_valid`: all four runs present and valid, every required row check present and true, 2 batch rows, the
  `rows_differ` record present, digests equal stage 0s.
- `batch_rows_identical`: on every cell, `rows_differ` is empty and the per-row A1 deltas equal row 0's.
- `run_vc.py vd4` refuses stage 0r without this file and refuses stages 1 and later unless `stage0_rows_valid` **and**
  `batch_rows_identical` hold.

## 5. Decision gate (pre-registered)

- **Rows identical** (`batch_rows_identical` true): the frozen A1 applied to every row the deltas that row needed, so
  A1 matches its preregistered definition. Record the finding in this addendum's record, keep the A1 implementation,
  and stage 1 may be requested (it still needs the user's approval).
- **Any relevant position differs**: do not proceed to stage 1. Report every (cell, layer, row, slot) difference with
  both values. Prepare addendum 2 specifying row-wise RoPE deltas for A1; correct A1 only after the discrepancy is
  documented; rerun the affected validity (stage 0s A1 on the four cells, which will then **not** be expected to equal
  the earlier digests, plus the stage-0 A1 oracle checks). B0, D, R, S1-S3 are unaffected by the audit above; their
  position checks are re-done per row by the `checks_supp` of every later run.

## 6. Dry tests

`tools/eval/test_vc.py` section 9: the stage-0r plan; 30 x 2 x 6 positions logged, every row check true, row deltas
equal row 0's; a differing row recorded exactly ((layer, row, slot), both values) and flagged without failing validity; a
prepare whose rows filled different slots fails `prepare_rows_filled_identical`; the gates on a complete dry stage 0r;
a differing row keeps `stage0_rows_valid` and closes `batch_rows_identical` (listed in the results); a differing A1
digest closes `stage0_rows_valid` while the earlier gates stay. Section 7's driver check expects the refusal of stage 1
until addendum 1b's gates hold. Results and file hashes: `addendum1b_record.md`.
