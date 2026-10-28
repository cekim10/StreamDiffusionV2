# E6: robustness validation of the completed M1 mechanism (plan fixed before the run, 2026-10-28)

**Scope.** Log-only input replay (Replay-12) with replay-aware Sink synchronization, exactly as in E5. No new
mechanism, no threshold change, no M2 or M3. One run per case, so this is a functional validation.

## 1. Workload generalization (E5 settings unchanged)

| item | value |
|---|---|
| hosts and link | host A -> host B, 1 Gbps emulated |
| trigger and window | trigger call 30, W = 12, lag 1 |
| Sink rounds | thr 16, rl 1 |
| run length | horizon 100, reference window 400 calls |
| units | train s0 (repository clip); butterfly s1 (refresh-heavy: up to 14 refresh writes per 12 calls in E2); audi s1 (motion reversal noted in VD-4) |

dog s1 is E5. All four units have frozen VD-3 thresholds for OT-1. Per workload:
- cross-host Sink digest equality and the verdict;
- refresh patches: number, bytes, calls, slot check, sent = applied, order;
- the replay keeping up: replay time per call against the source call interval, the readiness wait, the maximum queue
  wait, the replay wait at the switch;
- the cutover: bytes at the switch, no Sink resend unless SINKNO;
- the interruption, trigger to first output, total bytes;
- P1 / P2 (`m1_live_metrics.py`, VD-3 frozen rules, `<unit>|OT-1` thresholds, window [M, M + 24));
- the post-run recent-KV error.

## 2. Real GPU fallback (dog s1, E5 conditions)

`--replay_sink_sync_test_perturb_dst` flips the lowest bit of one bf16 element of one shadow-Sink block at the
destination right before its digest (layer L / 2, K, row 0, slot 1). Pass requires all of:
1. the digest reports exactly that block, and the verdict is SINKNO;
2. the source resends the dirty Sink fragments, the existing path;
3. the resent Sink passes its digest;
4. after the bind the destination's Sink digest equals the source's, which means it resumed from the exact Sink;
5. the destination resumes and generates, the order checks hold, and P1 / P2 are reported.

Also reported: its interruption and bytes, against E5 (1.56 s, 3.2 MB) and E3 (8.80 s, 730 MB).

## 3. What would keep M1 from being complete

- Any digest mismatch without the test perturbation, a refused switch, a readiness timeout, or a patch or order failure.
- A replay slower than the source call interval.
- P1 failing on a unit where the oracle (RS3 / Replay-12, E2) passed.

Each is reported as found. The digest check is never bypassed.
