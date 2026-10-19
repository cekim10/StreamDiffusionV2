# W / R / N shakedown check (GPU)

| id | pass | detail |
|---|---|---|
| W-a | PASS | 330 calls; fingerprint values per call [90] (expected 90 = 30 layers x 3 slots on GPU) |
| W-b | PASS | output-frame digests W1 vs node B baseline, calls 0-163: 0 differ |
| W-c | PASS | value fingerprints W1 vs node B baseline, calls 0-163: 0 differ |
| W-g | PASS | reference fingerprints for calls 34-163: 164 baseline calls |
| W-d | PASS | promotions [4, 5, 6, 7, 8, 13, 14, 15, 32, 34, 77, 78, 79, 85, 86, 139, 182, 235, 261, 303]; position-only changes (realignments, not counted) at [48, 93, 138, 183, 228, 273, 318]; position+value changes at [4, 77] |
| W-e | PASS | cut calls [6, 14, 22, 30, 38, 46]... vs loop_audit [6, 14, 22, 30, 38, 46]... |
| W-f | PASS | cold: c0 34, last 134, stop horizon, calls without PSNR []; reuse_dyn: c0 34, last 134, stop horizon, bind call 58, rejoin event 68 vs recomputed 68, calls without PSNR [] |
| R-a | PASS | restart: move gaps [28.1, 28.13] (T_m 28.10), valid True []; reuse_dyn: move gaps [28.14, 28.11] (T_m 28.10), valid True []; split: move gaps [28.13, 28.11] (T_m 28.10), valid True [] |
| R-b' | PASS | restart drops at ['B', 'C'], B_fwd 0.000; split reused 1.0, bound-before-leaving owners [] |
| R-c | PASS | restart: {'mean_active_background_flows_from_A': 3.0, 'coverage_fraction': 1.0, 'exposure_valid': True}; reuse_dyn: {'mean_active_background_flows_from_A': 1.003, 'coverage_fraction': 0.939, 'exposure_valid': True}; split: {'mean_active_background_flows_from_A': 0.0, 'coverage_fraction': 0.0, 'exposure_valid': False} |
| R-d | PASS | restart: 0 before final bind; reuse_dyn: 0 before final bind; split: 0 before final bind |
| N-a | PASS | reuse_aware_in: cap changes [[17.24604105949402, 'B', 'out', 62.5]], |S| 412, verified at trigger 206 (need 206), after-trigger 105.32883358001709, feasible True, available 206, valid (True, []); reuse_dyn: cap changes [[17.287582635879517, 'B', 'out', 62.5]], |S| 412, verified at trigger 206 (need 206), after-trigger 6.9779887199401855, feasible True, available 206, valid (False, ['NIC B out > 1.15 x degraded cap after the change']) |
| N-b | PASS | trigger record fields |
| N-c | PASS | known_caps (planner view) unchanged |

Overall: PASS
