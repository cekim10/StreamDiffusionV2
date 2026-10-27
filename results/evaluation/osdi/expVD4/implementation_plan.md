# VD-4 implementation plan and dry-test results (2026-10-26; final, with the frozen preregistration)

Implemented and dry-tested on the fake runtime; nothing ran on a GPU. The dry tests check the protocol, bookkeeping,
verification and gates, never an effect.

## 1. Components

| file | what |
|---|---|
| `vc_schedules.py` | `VD4_CELLS` / `vd4_conditions`: 13 conditions per schedule (B0, A1, D, R, DR, S1, S2, S3, A1S1, A1S2, Q8, Q4, V0); written to an **overlay** `expVD4/vd4_schedules.json`. `unit_sched()` appends the overlay; `main()` refuses to change the frozen `expVC/vc_schedules.json` (its SHA-256 stays equal to the VD-3 freeze record) |
| `vc_emulate.py` | `vd4_reset`: one snapshot per reset; V0 = `restore_all_from(snapshot)` with refresh unfrozen and no bind, then a post-move digest check against REF; otherwise TS-in prepare -> fast path -> oracle recent KV -> temporary Sink (A1: keys re-rotated) -> oracle Sink slots (fixed order; quantized for Q8 / Q4) -> oracle decoder cache or DR-2 -> refresh frozen -> verification. Any failed check or a V0 mismatch makes the stream invalid. VD-2 / VD-3 / VD-4 conditions run only on request |
| `mobility_node.py` | emulator-only helpers: `restore_all_from`, `write_snap_slots`, `kv_digest` (live / snapshot / override; K and V separately), `temp_digest`, `kv_nbytes`, `positions`, `dec_state_from_snap`, `rotate_temp` (`_shift_temporal_rope`, round-trip error), `quantize_slots` (fp8 e4m3 per tensor; int4 groups of 64); fake doubles |
| `vc_metrics.py` | VD-4 Sink-less windows; V0 skipped (a digest gate, not a metric condition) |
| `vd4_export_clips.py` | one blinded session per stage (REF and B0 always included, at most six clips per grid), key `vd4_<session>_blind_key.json` per session, form `expVD4/vd4_inspection_form_<session>.md` with the VD-4 fields; VD-3's exporter, key and form untouched |
| `aggregate_vd4.py` | VD-3's frozen thresholds (SHA-256 checked) and `aggregate_vd3.rules` reused; per condition and phase: numeric passes, visual flags vs REF in the same session, STRICT / NEAR / not resolved / not inspected, raw counts; attribution per phase; correspondence with Cohen's kappa; bytes and lower bounds; validity (V0, B0 = VD-3 digests, oracle checks); `vd4_gates.json` |
| `run_vc.py vd4 --stage 0/1/2/2b/3 [--phase key]` | stage plans of preregistration section 5; refuses before `expVD4_freeze.md`, refuses stages > 0 until the stage-0 gate passed, derives stage 2b's cells and stage 3's existence from the stage-2 gate; per-session key fetched through the agent (gzip + base64) and saved only if its SHA-256 equals the form's, after the inspection is committed |

Unchanged: every frozen VC / VD / VD-2 / VD-3 path, schedule entry and threshold (test_vc checks the frozen schedule
file byte for byte and re-runs the VD-3 tests).

## 2. Dry-test results

- `tools/eval/test_vc.py`: **ALL PASS, 79 checks**, of which 14 in the new section 7:
  frozen `vc_schedules.json` byte-identical to the VD-3 freeze record; 13 VD-4 conditions per schedule (V0 without a
  bind, S2 = slots 2, 1, A1S1 exploratory); 26 VD-4 streams on each of two units, all valid; G3 including V0; A1S2's
  oracle slots verified (K, V, positions), the remaining TS slot's V unrotated, positions logged; **negative cases**: an
  oracle Sink slot whose live K differs from the snapshot fails `sink_k_equal`, and a later reset step (the DR-2
  decode) overwriting the injected recent KV fails `recent_k_equal`; STRICT / NEAR / not resolved / not inspected
  classes (including a numeric failure and a zero-flag case); Cohen's kappa 1 and 0; session clips (2 cells x 6
  codes, key SHA-256 in the form, VD-4 fields, no condition names); aggregation with a synthetic recorded session
  (B0's two boundary flags vs REF's zero in the same session, validity rows, attribution per phase, gates); the driver
  refuses before the freeze. The earlier VC / VD / VD-2 / VD-3 checks still pass.
- `tools/eval/test_xb.py`: **ALL PASS, 87 checks** (`mobility_node.py` changed additively).

## 3. Not exercised by the dry tests (GPU only; guarded by the validity rules)

The real snapshot layouts (decoder `_feat_map` order, sink / recent K/V regions), `_shift_temporal_rope` on real keys,
fp8 / int4 on bf16 tensors, and V0's digest equality - stage 0 checks them on two cells before anything else runs.

## 4. Final estimated cost

| | runs | GPU (host D) | clips to inspect |
|---|---|---|---|
| if S3 does not resolve P2 | 90 | about 5.0 h | 132 (3 sessions) |
| if S3 resolves P2 | 114 | about 6.3 h | 180 (4 sessions) |

Inspection at roughly 15-20 s per clip: about 35-60 min of viewing in total, split over the sessions.

## 5. Revision for the freeze (review of 2026-10-26)

- Stage 0 = V0, B0, A1, S3 (validity only, no metrics) on dog s1 OT-1 (aligned), train s0 OT-1 (positive deltas),
  butterfly s0 OT-L (negative deltas), audi s1 OT-1 (mixed); `stage0_valid` requires every check on all four cells.
- Stage-1 inspection in two sessions (`aggregate_vd4.STAGE1_SESSIONS`); each (cell, condition) is judged against REF of
  the same cell in its session; a control seen in two sessions is reported (`duplicate_controls`), never summed.
- Tests: `test_vc.py` ALL PASS, **83 checks** (VD-4 section 21: the two above, the closed gate while a stage-0 cell is
  missing, the duplicate-control report); a dry stage 0 on all four cells opens the gate. `test_xb.py` 87 / 87.
- VD-3 frozen artifacts verified: preregistration, thresholds, Phase T data, `vc_schedules.json` and
  `aggregate_vd3.py` byte-identical to the VD-3 freeze record; re-aggregating VD-3 reproduces `vd3_results.{md,json}`
  byte for byte. The changed code files (`vc_emulate`, `vc_metrics`, `vc_schedules`, `run_vc`, `mobility_node`) carry
  VD-4 additions and the VD-3 key-fetch fix (2aaaa94).
- Cost: 95-119 runs (stage 0: 16, about 0.8 h), 5.2-6.5 GPU h, 132-180 clips.
