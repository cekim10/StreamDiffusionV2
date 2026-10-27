# VD-4 results (diagnostic; oracle sufficiency at the reset; not necessity, not practical migration)

## Stage-0 validity (per cell: V0 = REF, B0 = VD-3, oracle checks, positions)

- dog_s1|OT-1: PASS (8 checks; failed none); source positions [0, 1, 6], A1 deltas [0, 0, None], A1 rotation {'rotated_slot_layers': 18, 'round_trip_max_abs': 0.0625}
- train_s0|OT-1: PASS (8 checks; failed none); source positions [22, 24, 6], A1 deltas [22, 23, None], A1 rotation {'rotated_slot_layers': 34, 'round_trip_max_abs': 0.0625}
- butterfly-feeding-slow-motion_s0|OT-L: PASS (5 checks; failed none); source positions [-29, -10, -39], A1 deltas [-29, -11, None], A1 rotation {'rotated_slot_layers': 38, 'round_trip_max_abs': 0.125}
- audi-snow-trail_s1|OT-1: PASS (8 checks; failed none); source positions [22, 1, 6], A1 deltas [22, 0, None], A1 rotation {'rotated_slot_layers': 34, 'round_trip_max_abs': 0.0625}
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

## Batch-row positions (addendum 1b; recorded finding, separate from the checks above)

- dog_s1|OT-1 A1: PASS; stream valid True; failed none; missing none; output digests = stage-0s A1 True (158 calls, 0 differ); batch rows 2; rows identical {'sink': False, 'recent': False, 'all': False}; A1 row deltas = row 0's False; (layer, row, slot) differing 52
  - layer 0 row 1 slot 4: row 0 35, row 1 32
  - layer 1 row 1 slot 0: row 0 7, row 1 9
  - layer 1 row 1 slot 1: row 0 16, row 1 1
  - layer 1 row 1 slot 2: row 0 8, row 1 6
  - layer 1 row 1 slot 3: row 0 34, row 1 32
  - layer 1 row 1 slot 4: row 0 35, row 1 33
  - layer 1 row 1 slot 5: row 0 33, row 1 34
  - layer 2 row 1 slot 0: row 0 9, row 1 15
  - layer 2 row 1 slot 1: row 0 16, row 1 1
  - layer 2 row 1 slot 3: row 0 33, row 1 32
  - layer 2 row 1 slot 4: row 0 34, row 1 33
  - layer 2 row 1 slot 5: row 0 35, row 1 34
  - layer 3 row 1 slot 0: row 0 9, row 1 22
  - layer 3 row 1 slot 2: row 0 6, row 1 7
  - layer 3 row 1 slot 3: row 0 35, row 1 33
  - layer 3 row 1 slot 4: row 0 33, row 1 34
  - layer 3 row 1 slot 5: row 0 34, row 1 32
  - layer 4 row 1 slot 0: row 0 22, row 1 0
  - layer 4 row 1 slot 3: row 0 35, row 1 34
  - layer 4 row 1 slot 4: row 0 33, row 1 32
  - layer 4 row 1 slot 5: row 0 34, row 1 33
  - layer 5 row 1 slot 1: row 0 17, row 1 1
  - layer 5 row 1 slot 3: row 0 33, row 1 32
  - layer 5 row 1 slot 4: row 0 34, row 1 33
  - layer 5 row 1 slot 5: row 0 35, row 1 34
  - layer 6 row 1 slot 4: row 0 35, row 1 32
  - layer 7 row 1 slot 4: row 0 35, row 1 32
  - layer 8 row 1 slot 0: row 0 9, row 1 0
  - layer 8 row 1 slot 3: row 0 35, row 1 34
  - layer 8 row 1 slot 4: row 0 33, row 1 32
  - layer 8 row 1 slot 5: row 0 34, row 1 33
  - layer 9 row 1 slot 4: row 0 35, row 1 32
  - layer 10 row 1 slot 4: row 0 35, row 1 32
  - layer 11 row 1 slot 4: row 0 35, row 1 32
  - layer 12 row 1 slot 4: row 0 35, row 1 32
  - layer 13 row 1 slot 4: row 0 35, row 1 32
  - layer 14 row 1 slot 4: row 0 35, row 1 32
  - layer 15 row 1 slot 4: row 0 35, row 1 32
  - layer 16 row 1 slot 4: row 0 35, row 1 32
  - layer 17 row 1 slot 4: row 0 35, row 1 32
  - ... 12 more
- train_s0|OT-1 A1: PASS; stream valid True; failed none; missing none; output digests = stage-0s A1 True (158 calls, 0 differ); batch rows 2; rows identical {'sink': False, 'recent': False, 'all': False}; A1 row deltas = row 0's False; (layer, row, slot) differing 57
  - layer 0 row 1 slot 0: row 0 22, row 1 34
  - layer 0 row 1 slot 3: row 0 33, row 1 32
  - layer 0 row 1 slot 4: row 0 34, row 1 33
  - layer 0 row 1 slot 5: row 0 35, row 1 31
  - layer 1 row 1 slot 0: row 0 8, row 1 7
  - layer 1 row 1 slot 2: row 0 9, row 1 8
  - layer 1 row 1 slot 3: row 0 35, row 1 34
  - layer 1 row 1 slot 4: row 0 33, row 1 32
  - layer 1 row 1 slot 5: row 0 34, row 1 33
  - layer 2 row 1 slot 0: row 0 9, row 1 15
  - layer 2 row 1 slot 1: row 0 10, row 1 16
  - layer 2 row 1 slot 5: row 0 35, row 1 32
  - layer 3 row 1 slot 1: row 0 11, row 1 16
  - layer 3 row 1 slot 5: row 0 35, row 1 32
  - layer 4 row 1 slot 0: row 0 15, row 1 22
  - layer 4 row 1 slot 1: row 0 35, row 1 1
  - layer 5 row 1 slot 0: row 0 9, row 1 24
  - layer 5 row 1 slot 1: row 0 10, row 1 16
  - layer 5 row 1 slot 2: row 0 6, row 1 28
  - layer 5 row 1 slot 3: row 0 33, row 1 32
  - layer 5 row 1 slot 4: row 0 34, row 1 33
  - layer 5 row 1 slot 5: row 0 35, row 1 34
  - layer 6 row 1 slot 4: row 0 35, row 1 32
  - layer 7 row 1 slot 4: row 0 35, row 1 32
  - layer 8 row 1 slot 0: row 0 15, row 1 0
  - layer 8 row 1 slot 3: row 0 35, row 1 34
  - layer 8 row 1 slot 4: row 0 33, row 1 32
  - layer 8 row 1 slot 5: row 0 34, row 1 33
  - layer 9 row 1 slot 4: row 0 35, row 1 32
  - layer 10 row 1 slot 4: row 0 35, row 1 32
  - layer 11 row 1 slot 4: row 0 35, row 1 32
  - layer 12 row 1 slot 4: row 0 35, row 1 32
  - layer 13 row 1 slot 4: row 0 35, row 1 32
  - layer 14 row 1 slot 4: row 0 35, row 1 32
  - layer 15 row 1 slot 4: row 0 35, row 1 32
  - layer 16 row 1 slot 4: row 0 35, row 1 32
  - layer 17 row 1 slot 4: row 0 35, row 1 32
  - layer 18 row 1 slot 4: row 0 35, row 1 32
  - layer 19 row 1 slot 4: row 0 35, row 1 32
  - layer 20 row 1 slot 0: row 0 22, row 1 0
  - ... 17 more
- butterfly-feeding-slow-motion_s0|OT-L A1: PASS; stream valid True; failed none; missing none; output digests = stage-0s A1 True (254 calls, 0 differ); batch rows 2; rows identical {'sink': False, 'recent': False, 'all': False}; A1 row deltas = row 0's False; (layer, row, slot) differing 64
  - layer 0 row 1 slot 1: row 0 -10, row 1 1
  - layer 0 row 1 slot 3: row 0 36, row 1 35
  - layer 0 row 1 slot 4: row 0 34, row 1 33
  - layer 0 row 1 slot 5: row 0 35, row 1 34
  - layer 1 row 1 slot 0: row 0 16, row 1 11
  - layer 1 row 1 slot 1: row 0 -35, row 1 21
  - layer 1 row 1 slot 2: row 0 17, row 1 19
  - layer 1 row 1 slot 5: row 0 36, row 1 33
  - layer 2 row 1 slot 0: row 0 16, row 1 22
  - layer 2 row 1 slot 1: row 0 24, row 1 27
  - layer 2 row 1 slot 2: row 0 14, row 1 17
  - layer 2 row 1 slot 3: row 0 36, row 1 34
  - layer 2 row 1 slot 4: row 0 34, row 1 35
  - layer 2 row 1 slot 5: row 0 35, row 1 33
  - layer 3 row 1 slot 1: row 0 -34, row 1 -29
  - layer 3 row 1 slot 3: row 0 36, row 1 33
  - layer 4 row 1 slot 0: row 0 -31, row 1 -3
  - layer 4 row 1 slot 3: row 0 35, row 1 33
  - layer 4 row 1 slot 4: row 0 36, row 1 34
  - layer 4 row 1 slot 5: row 0 34, row 1 35
  - layer 5 row 1 slot 0: row 0 17, row 1 30
  - layer 5 row 1 slot 1: row 0 9, row 1 35
  - layer 5 row 1 slot 2: row 0 33, row 1 22
  - layer 5 row 1 slot 4: row 0 35, row 1 32
  - layer 5 row 1 slot 5: row 0 36, row 1 33
  - layer 6 row 1 slot 5: row 0 36, row 1 33
  - layer 7 row 1 slot 5: row 0 36, row 1 33
  - layer 8 row 1 slot 0: row 0 9, row 1 35
  - layer 8 row 1 slot 1: row 0 10, row 1 22
  - layer 8 row 1 slot 2: row 0 18, row 1 -4
  - layer 8 row 1 slot 3: row 0 35, row 1 32
  - layer 8 row 1 slot 4: row 0 36, row 1 33
  - layer 9 row 1 slot 0: row 0 35, row 1 0
  - layer 9 row 1 slot 4: row 0 36, row 1 35
  - layer 10 row 1 slot 5: row 0 36, row 1 33
  - layer 11 row 1 slot 5: row 0 36, row 1 33
  - layer 12 row 1 slot 5: row 0 36, row 1 33
  - layer 13 row 1 slot 5: row 0 36, row 1 33
  - layer 14 row 1 slot 5: row 0 36, row 1 33
  - layer 15 row 1 slot 5: row 0 36, row 1 33
  - ... 24 more
- audi-snow-trail_s1|OT-1 A1: PASS; stream valid True; failed none; missing none; output digests = stage-0s A1 True (159 calls, 0 differ); batch rows 2; rows identical {'sink': False, 'recent': False, 'all': False}; A1 row deltas = row 0's False; (layer, row, slot) differing 49
  - layer 0 row 1 slot 3: row 0 35, row 1 32
  - layer 1 row 1 slot 1: row 0 10, row 1 16
  - layer 1 row 1 slot 4: row 0 35, row 1 32
  - layer 2 row 1 slot 1: row 0 16, row 1 23
  - layer 2 row 1 slot 5: row 0 35, row 1 32
  - layer 3 row 1 slot 0: row 0 8, row 1 9
  - layer 3 row 1 slot 1: row 0 16, row 1 23
  - layer 3 row 1 slot 5: row 0 35, row 1 32
  - layer 4 row 1 slot 1: row 0 16, row 1 1
  - layer 4 row 1 slot 3: row 0 33, row 1 32
  - layer 4 row 1 slot 4: row 0 34, row 1 33
  - layer 4 row 1 slot 5: row 0 35, row 1 34
  - layer 5 row 1 slot 0: row 0 7, row 1 29
  - layer 5 row 1 slot 1: row 0 32, row 1 16
  - layer 5 row 1 slot 2: row 0 8, row 1 30
  - layer 5 row 1 slot 3: row 0 35, row 1 33
  - layer 5 row 1 slot 4: row 0 33, row 1 34
  - layer 5 row 1 slot 5: row 0 34, row 1 32
  - layer 6 row 1 slot 4: row 0 35, row 1 32
  - layer 7 row 1 slot 4: row 0 35, row 1 32
  - layer 8 row 1 slot 0: row 0 8, row 1 9
  - layer 8 row 1 slot 1: row 0 16, row 1 1
  - layer 8 row 1 slot 3: row 0 33, row 1 32
  - layer 8 row 1 slot 4: row 0 34, row 1 33
  - layer 8 row 1 slot 5: row 0 35, row 1 34
  - layer 9 row 1 slot 4: row 0 35, row 1 32
  - layer 10 row 1 slot 4: row 0 35, row 1 32
  - layer 11 row 1 slot 4: row 0 35, row 1 32
  - layer 12 row 1 slot 4: row 0 35, row 1 32
  - layer 13 row 1 slot 4: row 0 35, row 1 32
  - layer 14 row 1 slot 4: row 0 35, row 1 32
  - layer 15 row 1 slot 4: row 0 35, row 1 32
  - layer 16 row 1 slot 4: row 0 35, row 1 32
  - layer 17 row 1 slot 4: row 0 35, row 1 32
  - layer 18 row 1 slot 4: row 0 35, row 1 32
  - layer 19 row 1 slot 4: row 0 35, row 1 32
  - layer 20 row 1 slot 5: row 0 35, row 1 32
  - layer 21 row 1 slot 4: row 0 35, row 1 32
  - layer 22 row 1 slot 4: row 0 35, row 1 32
  - layer 23 row 1 slot 4: row 0 35, row 1 32
  - ... 9 more
- rows validation gate: True; batch rows identical on every cell: False

## Corrected A1 (addendum 2; row-wise deltas; validity and descriptive records) - first run (stage 0a, 52a1c461): the independent reference's theta ran over the head dim, not the temporal RoPE dim - addendum 2a; preserved, not the gate

- dog_s1|OT-1 A1: FAIL; stream valid False; pre-move = REF True; failed ['supp:a1_k_within_1ulp_of_independent_reference']; missing none; (layer, row, slot) records 120 / 120; non-zero deltas 13 (per row {'0': 9, '1': 4}), layers whose rows needed different deltas 6, K changed where non-zero 13 (min fraction 0.2928927951388889), K changed at zero delta 0, round-trip max 0.0625; independent reference: within 1 ulp False, max abs 20.0625, bitwise-equal element fraction 0.9645008993556357, bitwise-equal (layer, row, slot) 107 / 120; output digests vs stage 0r: pre-move differing 0, post-move differing 124 / 124 (first at call 34)
- train_s0|OT-1 A1: FAIL; stream valid False; pre-move = REF True; failed ['supp:a1_k_within_1ulp_of_independent_reference']; missing none; (layer, row, slot) records 120 / 120; non-zero deltas 29 (per row {'0': 17, '1': 12}), layers whose rows needed different deltas 9, K changed where non-zero 29 (min fraction 0.2935096153846154), K changed at zero delta 0, round-trip max 0.0625; independent reference: within 1 ulp False, max abs 40.75, bitwise-equal element fraction 0.9208102373519854, bitwise-equal (layer, row, slot) 91 / 120; output digests vs stage 0r: pre-move differing 0, post-move differing 124 / 124 (first at call 34)
- butterfly-feeding-slow-motion_s0|OT-L A1: FAIL; stream valid False; pre-move = REF True; failed ['supp:a1_k_within_1ulp_of_independent_reference']; missing none; (layer, row, slot) records 120 / 120; non-zero deltas 37 (per row {'0': 19, '1': 18}), layers whose rows needed different deltas 12, K changed where non-zero 37 (min fraction 0.26515299479166665), K changed at zero delta 0, round-trip max 0.125; independent reference: within 1 ulp False, max abs 39.375, bitwise-equal element fraction 0.8990402421652421, bitwise-equal (layer, row, slot) 83 / 120; output digests vs stage 0r: pre-move differing 0, post-move differing 174 / 174 (first at call 80)
- audi-snow-trail_s1|OT-1 A1: FAIL; stream valid False; pre-move = REF True; failed ['supp:a1_k_within_1ulp_of_independent_reference']; missing none; (layer, row, slot) records 120 / 120; non-zero deltas 31 (per row {'0': 17, '1': 14}), layers whose rows needed different deltas 7, K changed where non-zero 31 (min fraction 0.28964760283119656), K changed at zero delta 0, round-trip max 0.0625; independent reference: within 1 ulp False, max abs 41.0, bitwise-equal element fraction 0.9153573251925303, bitwise-equal (layer, row, slot) 89 / 120; output digests vs stage 0r: pre-move differing 0, post-move differing 125 / 125 (first at call 34)
- corrected-A1 gate: False
Digest differences from stage 0r are descriptive: the rows were rotated differently; they say nothing about quality.

## Corrected A1 (addendum 2; row-wise deltas; validity and descriptive records) - rerun with the corrected reference (stage 0a2, addendum 2a); the gate

- dog_s1|OT-1 A1: PASS; stream valid True; pre-move = REF True; failed none; missing none; (layer, row, slot) records 120 / 120; non-zero deltas 13 (per row {'0': 9, '1': 4}), layers whose rows needed different deltas 6, K changed where non-zero 13 (min fraction 0.2928927951388889), K changed at zero delta 0, round-trip max 0.0625; independent reference: within 1 ulp True, max abs 0.0, bitwise-equal element fraction 1.0, bitwise-equal (layer, row, slot) 120 / 120; output digests vs stage 0r: pre-move differing 0, post-move differing 124 / 124 (first at call 34); output digests vs the stage-0a first run: 0 of 158 calls differ (first run 158 calls; must be 0)
- train_s0|OT-1 A1: PASS; stream valid True; pre-move = REF True; failed none; missing none; (layer, row, slot) records 120 / 120; non-zero deltas 29 (per row {'0': 17, '1': 12}), layers whose rows needed different deltas 9, K changed where non-zero 29 (min fraction 0.2935096153846154), K changed at zero delta 0, round-trip max 0.0625; independent reference: within 1 ulp True, max abs 0.0, bitwise-equal element fraction 1.0, bitwise-equal (layer, row, slot) 120 / 120; output digests vs stage 0r: pre-move differing 0, post-move differing 124 / 124 (first at call 34); output digests vs the stage-0a first run: 0 of 158 calls differ (first run 158 calls; must be 0)
- butterfly-feeding-slow-motion_s0|OT-L A1: PASS; stream valid True; pre-move = REF True; failed none; missing none; (layer, row, slot) records 120 / 120; non-zero deltas 37 (per row {'0': 19, '1': 18}), layers whose rows needed different deltas 12, K changed where non-zero 37 (min fraction 0.26515299479166665), K changed at zero delta 0, round-trip max 0.125; independent reference: within 1 ulp True, max abs 0.0, bitwise-equal element fraction 1.0, bitwise-equal (layer, row, slot) 120 / 120; output digests vs stage 0r: pre-move differing 0, post-move differing 174 / 174 (first at call 80); output digests vs the stage-0a first run: 0 of 254 calls differ (first run 254 calls; must be 0)
- audi-snow-trail_s1|OT-1 A1: PASS; stream valid True; pre-move = REF True; failed none; missing none; (layer, row, slot) records 120 / 120; non-zero deltas 31 (per row {'0': 17, '1': 14}), layers whose rows needed different deltas 7, K changed where non-zero 31 (min fraction 0.28964760283119656), K changed at zero delta 0, round-trip max 0.0625; independent reference: within 1 ulp True, max abs 0.0, bitwise-equal element fraction 1.0, bitwise-equal (layer, row, slot) 120 / 120; output digests vs stage 0r: pre-move differing 0, post-move differing 125 / 125 (first at call 34); output digests vs the stage-0a first run: 0 of 159 calls differ (first run 159 calls; must be 0)
- corrected-A1 gate: True
Digest differences from stage 0r are descriptive: the rows were rotated differently; they say nothing about quality.

Thresholds: VD-3's frozen `vd3_thresholds.json` (SHA-256 792a6ac77ffbca24). Sessions recorded: ['stage1a', 'stage1b']. Validity problems: none.

| condition | phase | numeric pass (of 12) | visual flags (REF same session) | resolution | bytes added | lower bound 1 / 10 Gbps |
|---|---|---|---|---|---|---|
| B0 | P1 | 11 / 12 | 3 (0) | not resolved | 0.4 MB | 0.0 / 0.00 s |
| B0 | P2a | 6 / 12 | 0 (0) | not resolved | 0.4 MB | 0.0 / 0.00 s |
| B0 | P2b | 3 / 12 | 0 (0) | not resolved | 0.4 MB | 0.0 / 0.00 s |
| B0 | P3 | 12 / 12 | 0 (0) | no harm | 0.4 MB | 0.0 / 0.00 s |
| A1 | P1 | 11 / 12 | 4 (0) | not resolved | 0.4 MB | 0.0 / 0.00 s |
| A1 | P2a | 6 / 12 | 0 (0) | not resolved | 0.4 MB | 0.0 / 0.00 s |
| A1 | P2b | 3 / 12 | 0 (0) | not resolved | 0.4 MB | 0.0 / 0.00 s |
| A1 | P3 | 12 / 12 | 0 (0) | no harm | 0.4 MB | 0.0 / 0.00 s |
| D | P1 | 10 / 12 | 3 (0) | not resolved | 1888.6 MB | 15.1 / 1.51 s |
| D | P2a | 6 / 12 | 0 (0) | not resolved | 1888.6 MB | 15.1 / 1.51 s |
| D | P2b | 3 / 12 | 0 (0) | not resolved | 1888.6 MB | 15.1 / 1.51 s |
| D | P3 | 12 / 12 | 0 (0) | no harm | 1888.6 MB | 15.1 / 1.51 s |
| R | P1 | 12 / 12 | 0 (0) | STRICT | 1725.6 MB | 13.8 / 1.38 s |
| R | P2a | 6 / 12 | 0 (0) | not resolved | 1725.6 MB | 13.8 / 1.38 s |
| R | P2b | 2 / 12 | 0 (0) | not resolved | 1725.6 MB | 13.8 / 1.38 s |
| R | P3 | 12 / 12 | 0 (0) | no harm | 1725.6 MB | 13.8 / 1.38 s |
| DR | P1 | 12 / 12 | 0 (0) | STRICT | 3613.8 MB | 28.9 / 2.89 s |
| DR | P2a | 6 / 12 | 0 (0) | not resolved | 3613.8 MB | 28.9 / 2.89 s |
| DR | P2b | 3 / 12 | 0 (0) | not resolved | 3613.8 MB | 28.9 / 2.89 s |
| DR | P3 | 12 / 12 | 0 (0) | no harm | 3613.8 MB | 28.9 / 2.89 s |

STRICT: all 12 numeric passes and visual flags <= REF's in the same session; NEAR: <= REF's + 1. Raw counts are shown; a zero count is not proof of zero risk. Lower bounds are idealized transfers of the added bytes, not migration latency.

## Attribution (P1, P2a, P2b separately)

- P1: sufficient single states ['R']; decoder + recent jointly sufficient: False; not explained by the tested states: False
- P2a: sufficient single states none; decoder + recent jointly sufficient: False; not explained by the tested states: True
- P2b: sufficient single states none; decoder + recent jointly sufficient: False; not explained by the tested states: True
- A Sink-slot effect is reported per slot set (S1 = slot 2; S2 = slots 2, 1; S3 = all); it is not attributed to the number of true slots alone.

## Metric violations vs perceptible artifacts

- P2a: metric fail & flagged 0, metric fail & not flagged 30, metric pass & flagged 0, both clean 30; kappa 0.00
- P2b: metric fail & flagged 0, metric fail & not flagged 46, metric pass & flagged 0, both clean 14; kappa 0.00

## Gates: {"stage0_valid": true, "duplicate_controls": [], "stage2_inspected": false, "s3_resolves_p2": false, "stage2b_cells": null, "stage3_runs": false, "stage0_supp_valid": true, "stage0_rows_valid": true, "batch_rows_identical": false, "stage0_a1_rows_valid": true}
