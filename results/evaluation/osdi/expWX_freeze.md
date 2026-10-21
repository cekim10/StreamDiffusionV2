# Experiment WX (workload expansion) - freeze record

- **Freeze commit:** `a181126c3a8c8c9bddd29c5236376557c2e34959` (2026-10-20, after the M3E result)
- **Frozen document:** `expWX/preregistration.md` (SHA-256 `9060f07e17893c67bfbeb151e28d4736df284a6e36b80fb31fe276d9d262d296`): configurations X1-X6 replicating R (rho 1, 4, 2) and
  M3E (S4, S1, S2, S3) on butterfly-feeding-slow-motion, audi-snow-trail and train (seed 0); imported frozen hypotheses
  R-H1 / R-H2 / R-H3(a) and M3E H1-H4, H6, H7 per workload; generality reported as "supported on k of 4 tested inputs"
  (dog from frozen R / M3E); 144 runs; policy-matrix audit section 4.1.
- **Not frozen here:** driver, aggregator and shakedown check (commit recorded below). M1, M2, M3-v2 and every prior
  result (including M3E's seven verdicts) unchanged.

## Implementation record (2026-10-20, before any GPU run)

- **Implementation commit:** `e576643b0976e80a7ed9f5eadae0477ad6203fde` (`run_wrn.py wx_shk / wx`, `aggregate_wx.py`, `check_wx_shakedown.py`). No change to
  M1, M2, M3-v2, the harness or any prior result.
- **Loopback shakedown (fake runtime, X3 and X5 x 3 workloads, 21 runs): PASS 21 / 21** - valid, completed, bind
  observed, applicable, path A-B-C-D at rho 2, TTFO and chunk service measurable, no duplicates, cap event once in every
  X5 run, configured probe size. Aggregator exercised on the dry tree (dog frozen verdicts read correctly).
- **GPU:** `run_wrn.py wx_shk` -> `check_wx_shakedown.py`; on PASS `run_wrn.py wx` -> `aggregate_wx.py`.

## Shakedown check correction (2026-10-21; harness check only, no frozen rule changed)

The GPU shakedown (21 runs, `expWX_shk_*`) was valid in every run under the W / R / N rules, with the bind observed, the
cap event fired once in every X5 run and every run applicable; the shakedown check nevertheless reported 0 / 21 because
its "completed" item required the run to end by rejoin + tail. On these three inputs the final owner never reached
35 dB after three moves under any policy (maximum 30.2-34.1 dB; consistent with RD), so every run ended by the call
window at call 429 (~242 s). The item was corrected to "not cut by max_run_s" (window end and rejoin are recorded);
re-checked on the same runs: PASS 21 / 21. No mechanism, configuration, hypothesis, threshold or validity rule changed.
Consequence: every WX run lasts the full window (~4.5 min including setup), so the 144-run sweep takes ~11-12 h.
