# Experiment RD (visual recovery diagnosis) - freeze record

- **Freeze commit:** `f8500726e61a142d6eb9bef61e059e31f7892a54` (2026-10-20)
- **Frozen document:** `expRD/preregistration.md` (SHA-256 `29887a40ae518f7b305a4d0b23f3c97492174309e44aff9422b764ab801c6930`): in-place M1 emulation through the real
  `GpuRuntime` path; Sink-less duration x reset structure (r1 / r3c; r3e descriptive) x bind anchors 155 / 175;
  butterfly-feeding-slow-motion, audi-snow-trail, train, dog (seed 0); outcomes at three separate levels; Phase 0 replay
  gate (5 / 5), Phase 1 (100 runs), Phase 2 (real migration, after the user's approval); D / R / I / E rules, workload
  classes, stopping criteria S1-S3; decisions D1-D5.
- **Not frozen here:** the implementation (its commit is recorded in this file after the CPU / dry schedule
  validation). It must not change the frozen schedules, outcomes, thresholds or rules; a correctness bug found later is
  a dated amendment.
- **Prior evidence only:** W2, Experiment A, VACW (fidelity targets in Phase 0). Nothing of them is modified.

## Implementation record (2026-10-20, before any GPU run)

- **Implementation commit:** `24ad3302f82e8792b2a85a0c156c5b8dfba39623`. Files: `tools/eval/rd_schedule.py` (frozen schedules), `rd_emulate.py` (runner),
  `rd_metrics.py` (section 5 outcomes), `aggregate_rd.py` (Phase 0 gate, Phase 1 verdicts), `run_rd.py` (driver),
  `test_rd.py`; `mobility_node.GpuRuntime.step` keeps the decoded frames of the call (read-only, no effect on generation).
- **CPU / dry validation (`python tools/eval/test_rd.py`): ALL PASS.** Phase 1 = 100 runs; every schedule valid; Sink-less
  calls = d in every condition; the five Phase 0 schedules equal the recorded moves and binds of their frozen target
  runs; on the fake runtime every run is valid, r3c packs its Sink once and keeps it through two resets, r3e packs one
  Sink per episode, the stale replay (P0-3) rebinds the trigger Sink three times and the fresh replay (P0-4) binds three
  different Sinks; outcome functions on synthetic traces; no-reference metrics on synthetic frames in an OpenCV 4.10
  environment (output = reference -> ratio 1.00 "comparable"; static output flagged; flicker -> "less consistent").
  The full dry pipeline (`run_rd.py all --dry`) runs end to end (gate and verdicts not meaningful on fake PSNR).
- **Not exercised without a GPU:** the real `GpuRuntime` path in one process (Phase 0 is its test), OpenCV in the hosts'
  environment (checked by `run_rd.py preflight`).
