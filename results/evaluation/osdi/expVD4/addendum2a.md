# VD-4 preregistration addendum 2a (DRAFT, not approved, nothing run): the independent reference's RoPE angle

Status: **draft for review** (2026-10-26), written after the stage-0a result (52a1c461). Stage 1 stays blocked.
No GPU run until this addendum is approved.

## 1. What stage 0a showed

Gate `stage0_a1_rows_valid` = **false** on all four cells. On every cell exactly one check failed:
`a1_k_within_1ulp_of_independent_reference`. Everything else passed: stream valid apart from that check, pre-move
outputs equal REF, per-row positions equal the snapshot (after the restore and after the last reset operation), the
prepare's rows filled the same slots, the deltas derived independently from the position tensors equal the computed
ones, the deltas `rotate_temp` applied equal them, K as written and V unrotated on every (layer, row, slot), zero-delta
rows unchanged, 120 / 120 records, round-trip max 0.0625 (butterfly 0.125), K changed where and only where the delta is
non-zero. Post-move digests differ from stage 0r on every post-move call (expected: row 1 is rotated differently).

| cell | non-zero deltas (row 0 / row 1) | (layer, row, slot) bitwise equal to the reference | max abs difference |
|---|---|---|---|
| dog s1 OT-1 | 13 (9 / 4) | 107 / 120 | 20.1 |
| train s0 OT-1 | 29 (17 / 12) | 91 / 120 | 40.8 |
| butterfly s0 OT-L | 37 (19 / 18) | 83 / 120 | 39.4 |
| audi s1 OT-1 | 31 (17 / 14) | 89 / 120 | 41.0 |

The set of (layer, row, slot) that disagree with the reference is **exactly the set with a non-zero delta** on every
cell (13, 29, 37, 31); every zero-delta entry agrees bitwise. The differences (up to 41, with keys of magnitude about
30-40) are rotations by a different angle, not rounding.

## 2. Cause: an error in the reference, not in the correction

`a1_reference` (addendum 2, section 2) recomputed theta_j = 10000 ** (-2 j / d) over the **head dim** d = 128. The
model builds its RoPE table per axis (`models/wan/wan_base/modules/model.py:483-489`):
`torch.cat([rope_params(1024, d - 4 * (d // 6)), rope_params(1024, 2 * (d // 6)), rope_params(1024, 2 * (d // 6))])`,
so the temporal angles are theta_j = 10000 ** (-2 j / d_t) with **d_t = d - 4 * (d // 6) = 44** (22 complex pairs,
the `c - 2 * (c // 3)` columns `_shift_temporal_rope` uses, `causal_model.py:118-127`). `rotate_temp` uses the model's
own table and is right; the reference rotated by the wrong angles.

Why the CPU test did not catch it: section 11 built its synthetic `freqs` table with the same (wrong) formula as the
reference, so the two agreed with each other - the test was circular on the angle. Offline reproduction with the
model's real table construction (`rope_params` source, d = 128, keys of the observed scale, deltas 22, 23, -29, 1):
the wrong theta gives max abs differences 11-60 with 67 % of elements equal (the untouched spatial channels); the
corrected theta gives **bitwise equality** for every delta.

## 3. Changes (reference and test only; the A1 correction of addendum 2 is unchanged)

- `mobility_node.a1_reference`: theta over d_t = d - 4 * (d // 6) (asserting n_t = d_t / 2). Still independent of
  `rotate_temp` and of the model's table: own delta arithmetic, own angles from `rope_params`' formula, own complex
  multiply.
- `test_vc.py` section 11 now builds the table **the model's way** (the `rope_params` source, three concatenated
  parts, head dim 24 so the temporal dim differs from the head dim) and requires the reference to equal the rotated K
  bitwise; a regression check asserts that a reference with theta over the head dim differs by far more than rounding.
- Reporting: the stage-0a results (`results/evaluation/expVD4a`, `vd4a_checks_*`) are **preserved** and still reported
  in `vd4_results.md` as the first run; they no longer decide the gate.

## 4. Stage 0a2 (`run_vc.py vd4 --stage 0a2`)

The same four runs as stage 0a (the corrected A1 on dog s1 OT-1, train s0 OT-1, butterfly s0 OT-L, audi s1 OT-1) into
`results/evaluation/expVD4a2/`, checks `osdi/expVC/vd4a2_checks_<unit>.*`, no metrics, no clips; about 20 min on host
D. The gate `stage0_a1_rows_valid` is computed from this root with addendum 2's rule unchanged (every check, pre-move =
REF, complete records). Expected if the diagnosis is right: the rotated keys equal the reference bitwise (the
within-1-ulp check passes with bitwise fraction 1.0) and the output digests equal the stage-0a run call by call (the
rotation itself did not change; recorded, descriptive). `run_vc.py vd4 --stage 0a` now refuses to run again, so the
first run is never overwritten; stages 1 and later require the gate from stage 0a2.

## 5. What does not change

The A1 correction (addendum 2 section 2, items 1-5), hypotheses, conditions, thresholds, outcome criteria, the stage
plan, the inspection protocol, the stage-0 / 0s / 0r / 0a results, the frozen VD-4 documents and the VD-3 artifacts.
Results and file hashes: `addendum2a_record.md`.
