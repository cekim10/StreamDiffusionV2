# VD-4 results (diagnostic; oracle sufficiency at the reset; not necessity, not practical migration)

## Stage-0 validity (per cell: V0 = REF, B0 = VD-3, oracle checks, positions)

- dog_s1|OT-1: PASS (5 checks; failed none); source positions [0, 1, 6], A1 deltas [0, 0, None], A1 rotation {'rotated_slot_layers': 18, 'round_trip_max_abs': 0.0625}
- train_s0|OT-1: PASS (5 checks; failed none); source positions [22, 24, 6], A1 deltas [22, 23, None], A1 rotation {'rotated_slot_layers': 34, 'round_trip_max_abs': 0.0625}
- butterfly-feeding-slow-motion_s0|OT-L: PASS (5 checks; failed none); source positions [-29, -10, -39], A1 deltas [-29, -11, None], A1 rotation {'rotated_slot_layers': 38, 'round_trip_max_abs': 0.125}
- audi-snow-trail_s1|OT-1: PASS (5 checks; failed none); source positions [22, 1, 6], A1 deltas [22, 0, None], A1 rotation {'rotated_slot_layers': 34, 'round_trip_max_abs': 0.0625}
- duplicate controls across sessions: none

## Stage-0 supplemental validity (addendum 1; separate from the original stage-0 checks above)

- dog_s1|OT-1 A1: PASS; stream valid True; failed none; missing none; layers 30, layers with layer 0's sink positions 24; output digests = stage-0 A1 True (158 calls, 0 differ); (layer, slot) records 60: non-zero delta 9, K changed there 9 (min fraction 0.2928927951388889), K changed at zero delta 0, round-trip max 0.0625, K as expected 60, V unrotated 60, positions = snapshot 60; deltas slot 0 [0, 7, 9, 22], slot 1 [0, 15, 16]
  - sink positions (slots 0-2) across layers: [(0, 1, 6), (7, 16, 8), (9, 1, 6), (9, 16, 6), (9, 17, 6), (22, 1, 6)]
- train_s0|OT-1 A1: PASS; stream valid True; failed none; missing none; layers 30, layers with layer 0's sink positions 2; output digests = stage-0 A1 True (158 calls, 0 differ); (layer, slot) records 60: non-zero delta 17, K changed there 17 (min fraction 0.2969776642628205), K changed at zero delta 0, round-trip max 0.0625, K as expected 60, V unrotated 60, positions = snapshot 60; deltas slot 0 [0, 8, 9, 15, 22], slot 1 [0, 9, 10, 15, 23, 34]
  - sink positions (slots 0-2) across layers: [(0, 1, 6), (8, 10, 9), (8, 11, 6), (9, 10, 6), (15, 1, 6), (15, 35, 6), (22, 16, 6), (22, 24, 6)]
- butterfly-feeding-slow-motion_s0|OT-L A1: PASS; stream valid True; failed none; missing none; layers 30, layers with layer 0's sink positions 1; output digests = stage-0 A1 True (254 calls, 0 differ); (layer, slot) records 60: non-zero delta 19, K changed there 19 (min fraction 0.29683827457264955), K changed at zero delta 0, round-trip max 0.125, K as expected 60, V unrotated 60, positions = snapshot 60; deltas slot 0 [-39, -37, -31, -29, 0, 9, 16, 17, 24, 27, 35], slot 1 [-36, -35, -30, -11, 0, 8, 9, 23, 34]
  - sink positions (slots 0-2) across layers: [(-39, -29, 15), (-37, -34, -39), (-31, 1, -39), (-29, -10, -39), (0, 1, -39), (9, 10, 18), (16, -35, 17), (16, 24, 14), (17, 9, 33), (24, 1, -39), (27, 35, 17), (35, 1, -39)]
- audi-snow-trail_s1|OT-1 A1: PASS; stream valid True; failed none; missing none; layers 30, layers with layer 0's sink positions 1; output digests = stage-0 A1 True (159 calls, 0 differ); (layer, slot) records 60: non-zero delta 17, K changed there 17 (min fraction 0.28964760283119656), K changed at zero delta 0, round-trip max 0.0625, K as expected 60, V unrotated 60, positions = snapshot 60; deltas slot 0 [0, 6, 7, 8, 15, 22], slot 1 [0, 9, 15, 22, 31]
  - sink positions (slots 0-2) across layers: [(0, 1, 6), (6, 16, 7), (7, 10, 8), (7, 32, 8), (8, 16, 6), (15, 16, 6), (22, 1, 6), (22, 23, 6)]
- train_s0|OT-1 D: PASS; stream valid True; failed none; missing none; layers 30, layers with layer 0's sink positions 2; decoder {'entries_live': 33, 'entries_snapshot': 33, 'tensors': 32, 'bytes': 1888573440, 'layout_mismatch': [], 'unequal': [], 'attrs': {'_conv_idx': True, 'first_decode': True}}
  - sink positions (slots 0-2) across layers: [(0, 1, 6), (8, 10, 9), (8, 11, 6), (9, 10, 6), (15, 1, 6), (15, 35, 6), (22, 16, 6), (22, 24, 6)]
- train_s0|OT-1 R: PASS; stream valid True; failed none; missing none; layers 30, layers with layer 0's sink positions 2; recent KV bytes 1725235200
  - sink positions (slots 0-2) across layers: [(0, 1, 6), (8, 10, 9), (8, 11, 6), (9, 10, 6), (15, 1, 6), (15, 35, 6), (22, 16, 6), (22, 24, 6)]
- supplemental gate: True

Thresholds: VD-3's frozen `vd3_thresholds.json` (SHA-256 792a6ac77ffbca24). Sessions recorded: none. Validity problems: none.

| condition | phase | numeric pass (of 12) | visual flags (REF same session) | resolution | bytes added | lower bound 1 / 10 Gbps |
|---|---|---|---|---|---|---|

STRICT: all 12 numeric passes and visual flags <= REF's in the same session; NEAR: <= REF's + 1. Raw counts are shown; a zero count is not proof of zero risk. Lower bounds are idealized transfers of the added bytes, not migration latency.

## Attribution (P1, P2a, P2b separately)

- P1: sufficient single states none; decoder + recent jointly sufficient: False; not explained by the tested states: True
- P2a: sufficient single states none; decoder + recent jointly sufficient: False; not explained by the tested states: True
- P2b: sufficient single states none; decoder + recent jointly sufficient: False; not explained by the tested states: True
- A Sink-slot effect is reported per slot set (S1 = slot 2; S2 = slots 2, 1; S3 = all); it is not attributed to the number of true slots alone.

## Metric violations vs perceptible artifacts

- P2a: metric fail & flagged 0, metric fail & not flagged 0, metric pass & flagged 0, both clean 0; kappa -
- P2b: metric fail & flagged 0, metric fail & not flagged 0, metric pass & flagged 0, both clean 0; kappa -

## Gates: {"stage0_valid": true, "duplicate_controls": [], "stage2_inspected": false, "s3_resolves_p2": false, "stage2b_cells": null, "stage3_runs": false, "stage0_supp_valid": true}
