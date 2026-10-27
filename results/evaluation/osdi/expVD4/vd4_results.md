# VD-4 results (diagnostic; oracle sufficiency at the reset; not necessity, not practical migration)

## Stage-0 validity (per cell: V0 = REF, B0 = VD-3, oracle checks, positions)

- dog_s1|OT-1: PASS (5 checks; failed none); source positions [0, 1, 6], A1 deltas [0, 0, None], A1 rotation {'rotated_slot_layers': 18, 'round_trip_max_abs': 0.0625}
- train_s0|OT-1: PASS (5 checks; failed none); source positions [22, 24, 6], A1 deltas [22, 23, None], A1 rotation {'rotated_slot_layers': 34, 'round_trip_max_abs': 0.0625}
- butterfly-feeding-slow-motion_s0|OT-L: PASS (5 checks; failed none); source positions [-29, -10, -39], A1 deltas [-29, -11, None], A1 rotation {'rotated_slot_layers': 38, 'round_trip_max_abs': 0.125}
- audi-snow-trail_s1|OT-1: PASS (5 checks; failed none); source positions [22, 1, 6], A1 deltas [22, 0, None], A1 rotation {'rotated_slot_layers': 34, 'round_trip_max_abs': 0.0625}
- duplicate controls across sessions: none

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

## Gates: {"stage0_valid": true, "duplicate_controls": [], "stage2_inspected": false, "s3_resolves_p2": false, "stage2b_cells": null, "stage3_runs": false}
