# VD-4 preregistration addendum 2 (DRAFT, not approved, nothing run): row-wise RoPE deltas for A1

Status: **draft for review** (2026-10-26). Triggered by the pre-registered decision gate of addendum 1b section 5:
the two stream-batch rows carry different positions (`addendum1b_record.md`, `addendum1b_row_differences.md`).
Stage 1 stays blocked. No code is changed until this addendum is approved.

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

## 2. Correction (A1 only; the definition is unchanged)

- Deltas per **(layer, row, slot)**: `delta[l][b][s] = source_pos[l][b][s] - prepare_pos[l][b][s]` (`None` where the
  prepare left the slot empty), using `positions_all` for both.
- `rotate_temp` rotates row `b` of (layer `l`, slot `s`) by `delta[l][b][s]`; V untouched; per-(layer, row, slot)
  records (delta, K elements changed, round-trip error).
- Logged: `a1_deltas_rows` (every layer, row, slot); `a1_deltas_layer0` stays row 0's layer-0 deltas (as before).
- Checks: the frozen checks as they are (`ts_k_as_written` compares against the rotated expectation, which now carries
  per-row rotations, over both rows; `a1_k_rotated` keeps its frozen trigger: a non-zero row-0 layer-0 delta);
  supplemental `a1_deltas_applied_per_row` = the deltas used equal the deltas every row needed (true by construction;
  recorded as a check so a regression is caught), plus every addendum-1 / 1b check.
- Exploratory A1S1 / A1S2 inherit the correction (they share `ts = in_aligned`).

## 3. Validity re-run after the correction: stage 0a (`run_vc.py vd4 --stage 0a`)

A1 on the four stage-0 cells with the corrected implementation; output root `results/evaluation/expVD4a/`; checks to
`osdi/expVC/vd4a_checks_<unit>.*`; no metrics, no clips, no inspection; about 20 min on host D. The stage-0 / 0s / 0r
results stay as they are (they document A1 as implemented before the correction).

Gate `stage0_a1_rows_valid`: all four runs present and valid; every frozen, addendum-1 and addendum-1b check present
and true; `a1_deltas_applied_per_row` true; (layer, row, slot) records complete (30 x 2 x 2 rotated-slot records);
outputs before the move identical to REF (`prefix_identical_to_reference`). Recorded, not required: the number of
post-move calls whose output digest differs from the stage-0r A1 run (expected > 0 wherever a row-1 delta changed),
and the per-row K-changed / round-trip summaries.

`run_vc.py vd4` then requires `stage0_valid`, `stage0_supp_valid`, `stage0_rows_valid` and `stage0_a1_rows_valid`
before stage 1 (the `batch_rows_identical` requirement is replaced by this gate: the rows are known to differ, and the
corrected A1 handles them). Stage 1 still needs the user's approval after the review of stage 0a.

## 4. What does not change

Hypotheses, conditions, thresholds, outcome criteria, attribution rules, the stage plan, the inspection sessions and
fields, the VD-3 rules. Stage-1 A1 streams are produced by the corrected implementation; the stage-0 A1 streams are not
reused for metrics (stage 0 computed none).

## 5. Dry tests to add (`test_vc.py` section 10)

Per-(layer, row, slot) deltas from a fake whose rows differ; the rotation applied per row (a fake `rotate_temp` double
recording the deltas it received); `a1_deltas_applied_per_row` false when a row's delta is wrong; the stage-0a plan
and gate; the driver's refusal of stage 1 until `stage0_a1_rows_valid` holds.
