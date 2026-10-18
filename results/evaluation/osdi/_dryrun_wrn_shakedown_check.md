# W / R / N shakedown check (loopback dry run)

| id | pass | detail |
|---|---|---|
| W-a | PASS | 330 calls; fingerprint values per call [1] (expected 90 = 30 layers x 3 slots on GPU) |
| W-b | PASS | output-frame digests W1 vs node B baseline, calls 0-163: 0 differ |
| W-c | PASS | value fingerprints W1 vs node B baseline, calls 0-163: 0 differ |
| W-g | PASS | reference fingerprints for calls 34-163: 164 baseline calls |
| W-d | PASS | promotions []; position-only changes (realignments, not counted) at []; position+value changes at [] |
| W-e | PASS | cut calls [6, 14, 22, 30, 38, 46]... vs loop_audit [6, 14, 22, 30, 38, 46]... |
| W-f | PASS | cold: c0 34, last 134, stop horizon, calls without PSNR []; reuse_dyn: c0 34, last 134, stop horizon, bind call 61, rejoin event 61 vs recomputed 61, calls without PSNR [] |
| R-a | PASS | restart: move gaps [10.83, 10.8] (T_m 10.80), valid True []; reuse_dyn: move gaps [10.81, 10.79] (T_m 10.80), valid True []; split: move gaps [10.84, 10.76] (T_m 10.80), valid True [] |
| R-b' | PASS | restart drops at ['B', 'C'], B_fwd 0.000; split reused 0.9375, bound-before-leaving owners [] |
| R-c | PASS | restart: {'mean_active_background_flows_from_A': 3.0, 'coverage_fraction': 1.0, 'exposure_valid': True}; reuse_dyn: {'mean_active_background_flows_from_A': 0.106, 'coverage_fraction': 0.067, 'exposure_valid': False}; split: {'mean_active_background_flows_from_A': 0.122, 'coverage_fraction': 0.078, 'exposure_valid': False} |
| R-d | PASS | restart: 0 before final bind; reuse_dyn: 0 before final bind; split: 0 before final bind |
| N-a | PASS | reuse_aware_in: cap changes [[6.6637797355651855, 'B', 'out', 6.25]], |S| 16, verified at trigger 8 (need 8), after-trigger 42.59736609458923, feasible True, available 8, valid (True, []); reuse_dyn: cap changes [[6.668398141860962, 'B', 'out', 6.25]], |S| 16, verified at trigger 8 (need 8), after-trigger 14.200234174728394, feasible True, available 8, valid (True, []) |
| N-b | PASS | trigger record fields |
| N-c | PASS | known_caps (planner view) unchanged |
| N-d (loopback) | PASS | {"stop_reason": "deadline", "elapsed_s": 15.050924062728882, "timed_out": true, "sink_verified": false, "bind_observed": false, "rejoin_observed": false, "last_progress_final_owner": 0.625, "first_call_final_owner": 50, "last_call_final_owner": 103, "horizon_calls": null} |

Overall: PASS
