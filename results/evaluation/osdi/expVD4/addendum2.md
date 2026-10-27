# VD-4 preregistration addendum 2: row-wise RoPE deltas for A1

Status: **approved by the user on 2026-10-26** (after the draft of 72d64af4). Triggered by the pre-registered decision
gate of addendum 1b section 5: the two stream-batch rows carry different positions (`addendum1b_record.md`,
`addendum1b_row_differences.md`). Stage 1 stays blocked until stage 0a has run and its results have been reviewed.

This addendum changes the **implementation** of condition A1 (and of the exploratory A1S1 / A1S2, which share it) to
match its frozen definition. It does not change any hypothesis, condition definition, threshold, outcome criterion,
attribution rule, stage plan or inspection protocol. The stage-0, 0s and 0r results, the frozen VD-4 documents and the
VD-3 artifacts are preserved.

## 1. Discrepancy (documented before any correction)

The preregistered A1 (section 3 of `preregistration.md`): "B0 with the temporary-Sink keys re-rotated to the source's
slot positions (delta = source - prepare, per layer and slot; V untouched)". The KV cache has two stream-batch rows
with their own positions. The implementation computed the deltas from row 0 and applied them to both rows
(`vc_emulate.vd4_reset`, `mobility_node.rotate_temp`). Stage 0r measured the consequence: on 8 (dog), 14 (train),
17 (butterfly) and 10 (audi) of the 60 (layer, slot) pairs of the temporary Sink, row 1 needed a different delta
(including 2-5 pairs per cell where row 1 needed no rotation at all and was rotated, and one pair on butterfly where
row 1 needed a rotation and got none). So the A1 streams of stages 0, 0s and 0r are "row-0 deltas on both rows", a
deviation from the definition. Their validity checks (K equal to what was written, V untouched, positions equal the
snapshot, digests reproducible) hold for what was written; they do not make the written keys the preregistered ones.

Unaffected: B0 (unrotated temporary Sink, row-independent), D, R, DR, S1-S3, Q8, Q4 (whole-tensor injections), V0.
VD-3's finding that the TS-in keys were positionally misaligned stands (it is about B0's unrotated keys).

## 2. Correction (A1 only; the definition is unchanged) - as implemented

1. Deltas per **(layer, batch row, slot)**: `delta[l][b][s] = source_pos[l][b][s] - prepare_pos[l][b][s]` from the
   per-row positions (`positions_all`: the snapshot's meta, restored and checked for every row) and the prepare's
   position tensors; `None` where the prepare left the slot empty (`vc_emulate.vd4_reset`).
2. `mobility_node.rotate_temp(saved, deltas[l][b][s])` rotates **row b only** of (layer l, slot s) by its own delta
   (`_shift_temporal_rope`, the model's own primitive, as before); a zero or `None` delta leaves the row untouched.
3. V is never written by the rotation (every row).
4. The snapshot's position metadata is restored whole (`restore_fast` -> `restore_state`, every row) and never
   rewritten by the temporary-Sink write; checked per row after the last reset operation.
5. Records per (layer, row, slot): delta applied, K elements changed, round-trip error, K as written, V unrotated,
   K equal to the prepare's (zero-delta rows), position and its equality with the snapshot (`supp.a1_per_layer_row_slot`).
   The frozen fields keep their meaning (`a1_deltas_layer0` = row 0's layer-0 deltas; `a1_k_rotated` keeps its frozen
   trigger).

**Independent oracle** (`mobility_node.a1_reference`): the expected keys are built without `rotate_temp` from the
**original** prepare tensors (K and positions, before any rotation) and the snapshot's position tensors: the deltas by
tensor subtraction, the temporal RoPE channels (the first `c - 2 * (c // 3)` complex pairs, the split the model's
`rope_apply` uses) of row b, slot s multiplied by `exp(i * delta * theta_j)` with `theta_j = 10000 ** (-2 j / dim)`
recomputed from `rope_params`' formula in float64, cast to the key dtype. Checks (`checks_supp`, every one required):

| check | meaning |
|---|---|
| `a1_deltas_equal_independent` | the independently derived deltas equal the ones computed in `vd4_reset` |
| `a1_deltas_applied_per_row` | the deltas `rotate_temp` reports having applied equal the computed per-row deltas (regression guard) |
| `ts_k_as_written_rows` | every (layer, row, slot) of the remaining temporary Sink holds the rotated K that was written |
| `ts_v_unrotated_rows` | every (layer, row, slot) holds the prepare's V |
| `a1_zero_delta_rows_unchanged` | every (layer, row, slot) with a zero delta holds the prepare's K bitwise |
| `a1_k_within_1ulp_of_independent_reference` | every element of the live rotated K is within 1 unit in the last place (bf16) of the independent expectation; the bitwise-equal fraction and the max abs difference are recorded (on CPU the two agree bitwise) |
| addendum 1 / 1b checks | positions of every row equal the snapshot after the restore and after the last reset operation; prepare rows filled the same slots; per-(layer, slot) K / V checks over both rows |

## 3. Validity re-run after the correction: stage 0a (`run_vc.py vd4 --stage 0a`)

A1 on the four stage-0 cells with the corrected implementation; output root `results/evaluation/expVD4a/`; checks to
`osdi/expVC/vd4a_checks_<unit>.*`; no metrics, no clips, no inspection; about 20 min on host D. The stage-0 / 0s / 0r
results stay as they are (they document A1 as implemented before the correction).

Gate `stage0_a1_rows_valid`: all four runs present and valid; every frozen, addendum-1, 1b and 2 check present and
true (section 2 table; `aggregate_vd4.A1_REQUIRED`); (layer, row, slot) records complete (30 x 2 x 2); outputs before
the move identical to REF (`prefix_identical_to_reference`). Recorded, not required, reported **descriptively** (they
say nothing about quality): the number of post-move calls whose output digest differs from the stage-0r A1 run
(expected > 0 wherever a row-1 delta changed) and the first differing call; pre-move differing calls (must be 0, as
part of the REF equivalence); the per-row deltas, K-changed and round-trip summaries; the reference comparison.

`run_vc.py vd4` then requires `stage0_valid`, `stage0_supp_valid`, `stage0_rows_valid` and `stage0_a1_rows_valid`
before stage 1 (the `batch_rows_identical` requirement is replaced by this gate: the rows are known to differ, and the
corrected A1 handles them). Stage 1 still needs the user's approval after the review of stage 0a.

## 4. What does not change

Hypotheses, conditions, thresholds, outcome criteria, attribution rules, the stage plan, the inspection sessions and
fields, the VD-3 rules. Stage-1 A1 streams are produced by the corrected implementation; the stage-0 A1 streams are not
reused for metrics (stage 0 computed none).

## 5. Tests (`test_vc.py`)

- Section 10 (fake runtime, dry): `rotate_temp` receives per-(layer, row, slot) deltas (a fake whose row 1 differs in
  one layer: row 1 = [5, 0, None], row 0 = [0, 0, None]); 30 x 2 x 2 records; the frozen layer-0 field stays row 0's; a
  reported delta that differs from the computed one fails `a1_deltas_applied_per_row`; the stage-0a plan; the gate
  opens on a complete dry stage 0a with the digest differences vs stage 0r reported; a rotated K outside 1 ulp of the
  reference, or pre-move outputs differing from REF, close the gate while the earlier gates stay.
- Section 11 (CPU torch, run when torch is importable; the model's `_shift_temporal_rope` source): on synthetic bf16
  keys with 2 rows, 4 layers, per-layer position tensors - correct batch indexing (4 x 2 x 3 records, 9 rotations, each
  (layer, row, slot) by its own delta); row isolation (rotating row 1 leaves row 0 bitwise unchanged and vice versa; the
  empty slot untouched); different row deltas (22 vs 34) give each row its own rotation; V and the prepare's positions
  unchanged for every row; zero-delta entries keep the prepare's K bitwise; the independent reference derives the same
  deltas from the position tensors and its expected K equals the rotated K bitwise; a one-element deviation beyond 1
  ulp is caught.
- Section 7's driver check expects the refusal of stage 1 until `stage0_a1_rows_valid` holds.

Results and file hashes: `addendum2_record.md`.
