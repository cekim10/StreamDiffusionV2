# VD-4 preregistration addendum 1: supplemental stage-0 validation (2026-10-26)

Status: **approved by the user on 2026-10-26** ("Option B"), after the review of the stage-0 results (a319a8cc).
Stage 0 is accepted as passed. Stage 1 is **not** authorized until the supplemental validation below has been run on
the GPU and its results approved.

This addendum does **not** change any frozen VD-4 hypothesis, condition, threshold, outcome criterion, attribution rule
or inspection protocol (`preregistration.md`, `../expVD4_freeze.md`). It adds logging, validity checks and one
validation stage before stage 1. The original stage-0 results are kept as they are and are not re-run or overwritten.

## 1. Why (findings of the stage-0 review)

1. **Sink positions differ per layer.** Only layer 0 was logged. On dog s1 OT-1, layer 0 is aligned ([0, 1]), yet the
   A1 rotation touched 18 (layer, slot) pairs. On train s0 OT-1, both layer-0 deltas are non-zero, yet only 34 of 60
   pairs were rotated. The stage-0 labels (aligned / positive / negative / mixed) describe layer 0 only.
2. **One A1 check was weaker than the preregistration text.** Section 2 says "K differs from the unrotated K wherever a
   delta is non-zero". The code (`a1_k_rotated`) compares one digest over all layers and runs only when a layer-0 delta
   is non-zero, so it did not run on dog. The check "K equals the rotated expectation" did pass in every layer.
3. **The oracle decoder (D) and recent-KV (R) writes have never run on a GPU.** Stage 0 had no D or R condition.
   (`implementation_plan.md` section 3 said stage 0 would check the decoder layout; it did not.)

## 2. Original stage-0 results (preserved, unchanged)

- Commit a319a8cc: `results/evaluation/expVC/<unit>/VD4x-{V0,B0,A1,S3}`, `osdi/expVC/vd4_checks_<unit>.*`,
  `expVD4/vd4_results.*`, `expVD4/vd4_gates.json` (`stage0_valid: true`).
- These files are not re-run or edited. `aggregate_vd4.py` still produces their stage-0 section byte for byte (checked
  by diff). The supplemental results get their own section and their own gate.

## 3. Changes (logging and checks only; no output path changes)

**Original checks (frozen, unchanged):** `checks` in each VD-4 summary. The aggregate `a1_k_rotated` check is kept
exactly as frozen.

**Supplemental records:** `supp` in each VD-4 summary.
- `source_positions`, `final_positions`: every layer, every slot.
- `prepare_positions`: every layer, the temporary-Sink slots.
- `a1_deltas`: every layer and slot.
- `a1_per_layer_slot`: one record per (layer, slot) with the delta, the number of K elements the rotation changed (of
  the total), the rotate / rotate-back max abs error, K equal to the expectation, V unrotated, the position, and
  whether the position equals the snapshot.
- `decoder_layout`: per `_feat_map` entry, tensor or not, shape, dtype, bitwise equality, plus the bookkeeping
  attributes.

**Supplemental checks:** `checks_supp`, kept separate from `checks`. Each is a bitwise comparison:

| check | meaning |
|---|---|
| `positions_final_equal_snapshot` | after the last reset operation, every layer's slot positions equal the snapshot's |
| `ts_k_as_written_per_layer_slot` | every (layer, slot) of the remaining temporary Sink has the K that was written (A1: rotated) |
| `ts_v_unrotated_per_layer_slot` | every (layer, slot) of the remaining temporary Sink has the prepare's V |
| `ts_positions_equal_snapshot_per_layer_slot` | the remaining temporary-Sink slots keep the source's positions in every layer |
| `sink_k/v_equal_per_layer_slot` | oracle Sink slots, per (layer, slot) |
| `recent_k/v_equal_at_write` | recent KV equals the snapshot right after its write |
| `recent_k/v_equal_per_layer_slot` | recent KV equals the snapshot per (layer, slot) after the last reset operation |
| `decoder_equal_at_write` | decoder cache equals the snapshot right after its write |
| `decoder_layout_equal` | same number of `_feat_map` entries; same tensor / non-tensor pattern, shapes and dtypes |
| `decoder_tensors_equal_per_entry` | every decoder-cache tensor equals the snapshot's, entry by entry |
| `decoder_attrs_equal` | `_conv_idx`, `first_decode` equal the snapshot's |

The frozen checks `recent_*_equal` and `decoder_equal` already run after the last reset operation. Together with the
`*_at_write` checks they show that no later reset step (temporary-Sink write, DR-2 decode, oracle Sink write, refresh
freeze) overwrote an injected component.

**Recorded, not required.** Whether K changes where a delta is non-zero is recorded per (layer, slot) and never gates
validity. bf16 rounding can make a small rotation leave some or all bytes unchanged. This replaces the
"K differs ... wherever a delta is non-zero" requirement of preregistration section 2.

**Validity.** A false supplemental check makes the stream invalid, in stage 0s and in every later stage. This is a
stricter validity rule. It does not change any outcome criterion.

## 4. Stage 0s (supplemental validation; `run_vc.py vd4 --stage 0s`)

| run | cells | purpose |
|---|---|---|
| A1 | the four stage-0 cells (dog s1 OT-1, train s0 OT-1, butterfly s0 OT-L, audi s1 OT-1) | per-(layer, slot) A1 checks and records; output digests must equal the stage-0 A1 run call by call (the added logging does not change outputs) |
| D | train s0 OT-1 | decoder-cache layout, digest at the write and after the last reset operation, entries, attributes |
| R | train s0 OT-1 | recent-KV K / V digests and positions at the write and after the last reset operation, per (layer, slot) |

- **Why train s0 OT-1 for D and R:** it has non-zero layer-0 deltas in both slots, it uses the OT-1 schedule (6 of the
  12 confirmation cells), it is a repository clip, and it is a confirmation cell.
- **Output root:** `results/evaluation/expVD4s/` (stage-0 results untouched). Checks go to `osdi/expVC/vd4s_checks_<unit>.*`.
- **No metrics, no clips, no inspection.**
- **Gate `stage0_supp_valid`** (in `vd4_gates.json`): all six runs present and valid; every required frozen and
  supplemental check present and true (`aggregate_vd4.SUPP_REQUIRED`; `a1_k_rotated` is required only where the frozen
  code runs it); 60 A1 (layer, slot) records per cell; the four A1 output digest sequences equal stage 0's.
- **Any failure stops VD-4.**
- `run_vc.py vd4` refuses stage 0s without this file, and refuses stages 1 and later until both `stage0_valid` and
  `stage0_supp_valid` hold. Stage 1 additionally needs the user's approval of the supplemental results.
- **Cost:** 6 runs plus 4 baselines on host D, about 25 min.

## 5. Dry tests

`tools/eval/test_vc.py` section 8: the stage-0s plan; every supplemental check present and true on the fake runtime;
30 layers of positions and 60 A1 records. Negative cases:
- the decoder changed after its write (equal at the write, unequal at the end);
- a decoder layout mismatch;
- one (layer, slot) of the recent KV differing;
- one (layer, slot) of A1's rotated K differing;
- a position moved after the restore.

The gate opens on a complete dry stage 0s, and closes on one differing A1 digest or a missing D run. The stage-0 gate is
unaffected. Section 7's driver check now asserts that stage 1 is refused until the supplemental gate passes. Results
and file hashes: `addendum1_record.md`.
