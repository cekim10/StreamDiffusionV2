# Experiment M3E (final OTTER with M3-v2, end-to-end) - freeze record

- **Freeze commit:** `abf74d66df1ff21c97e407003556858defb40d91` (2026-10-20)
- **Frozen document:** `expM3E/preregistration.md` (SHA-256 `d0d88a28db75fcf65c35ebb074fe418032d1c935470729a522e05ba3ee3b9c1b`): scenarios S1 (one M3-v2 GPU session vs three
  network-level M3-v1 sessions on the source's egress), S2 (holder bottleneck), S3 (destination-ingress bottleneck),
  S4 (no change), S5 (source bottleneck); policies M1 only, M1 + frozen M2, M3-v2 (+ OTTER at moves in S2); H1-H7;
  48 runs; decisions D1-D5.
- **Not frozen here:** the driver, aggregator and shakedown check (their commit is recorded below). They must not change
  the frozen scenarios, metrics, thresholds or rules; M1, M2 and M3-v2 are not modified.
- **Evidence classes:** historical M3-v1 (ExpD, N), M3-v2 development / holdout (N regressions, V) and new M3E data are
  never pooled.

## Implementation record (2026-10-20, before any GPU run)

- **Implementation commit:** `14551bda52ec4486d2762b93144aa86369d78830`: `tools/eval/run_wrn.py` (`m3e_shk`, `m3e`), `tools/eval/aggregate_m3e.py`,
  `tools/eval/check_m3e_shakedown.py`. No change to M1, M2, M3-v2, the orchestrator or the node.
- **Loopback shakedown (fake runtime, 16 runs, one per policy per scenario): PASS 16 / 16** - every run valid under the
  W / R / N rules, completed (rejoin + tail), bind observed, applicable, path A-B-C-D at rho 2, TTFO and the
  move-to-bind chunk service time measurable, no duplicate bytes; the progress-triggered cap event fired exactly once
  in every S2 / S3 / S5 run; S1 carried 3 network sessions, all restored; M3-v2 ran with the configured probe size.
- **GPU shakedown and sweep:** `python tools/eval/run_wrn.py m3e_shk` -> `check_m3e_shakedown.py`; on PASS
  `run_wrn.py m3e` -> `aggregate_m3e.py`.
