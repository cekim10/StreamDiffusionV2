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
