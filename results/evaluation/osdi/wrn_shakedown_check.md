# W / R / N shakedown check (GPU)

| id | pass | detail |
|---|---|---|
| W-a | PASS | 330 calls; fingerprint values per call [90] (expected 90 = 30 layers x 3 slots on GPU) |
| W-b | **FAIL** | output-frame digests W1 vs node B baseline, calls 0-163: 1 differ |
| W-c | PASS | value fingerprints W1 vs node B baseline, calls 0-163: 0 differ |
| W-g | PASS | reference fingerprints for calls 34-163: 164 baseline calls |
| W-d | PASS | promotions [1, 4, 5, 6, 7, 8, 13, 14, 15, 32, 34, 77, 78, 79, 85, 86, 139, 182, 235, 261]...; position-only changes (realignments, not counted) at [48, 93, 138, 183, 228, 273, 318]; position+value changes at [4, 77]; NOTE promotion at call 1 (inspect: sink filling vs promotion) |
| W-e | PASS | cut calls [6, 14, 22, 30, 38, 46]... vs loop_audit [6, 14, 22, 30, 38, 46]... |
| W-f | PASS | cold: c0 34, last 134, stop horizon, calls without PSNR []; reuse_dyn: c0 34, last 134, stop horizon, bind call 58, rejoin event 68 vs recomputed 68, calls without PSNR [] |
| R | **FAIL** | runs present: [] |
| N | **FAIL** | runs present: [] |

Overall: FAIL
