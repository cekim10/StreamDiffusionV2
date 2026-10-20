# Version-aware Continuity Wavefront v0 (M2 extension) - freeze record

- **Freeze commit:** `9137bc9dff869e81cd809b1108e38c1177a29b0f` (2026-10-20T18:12Z, pushed to `phase0a-quality-elastic`)
- **Frozen document:** `expM2/vacw_v0_design.md` (SHA-256 `68698ded8cca4b1973c5b4c157faf03d204e540be9f76ee851f98a4f389af4e3`):
  state machine, invariants I1-I7, minimal code-change plan, overhead analysis, the 36-run matrix
  (A -> B -> C -> D, rho {0.5, 1}, dog / butterfly seed 0, `restart_fresh` / `split` / `split_va`, 3 reps),
  hypotheses H1a / H1b / H2 / H3 with thresholds, the exposure criterion, GO / CONDITIONAL / NO-GO.
- **Not frozen here:** the implementation (to be written after this freeze; its commit is recorded in this file when the
  loopback invariant tests pass), which must not change the frozen hypotheses, thresholds, matrix or rules. A
  correctness bug found later is a dated amendment to the design document.
- **Unchanged:** M1 (Experiment A frozen NO-GO), M3-v1 / M3-v2, the frozen policies `split` / `restart`, all frozen
  results (ExpD, W / R / N, V, A, B). Key canonicalization and rolling synchronization are out of scope.
- **Development data:** Task B measurements (`../m1m2_results.md`), R rho 0.5 / 1 runs (version events), loopback runs
  with injected promotions. No evaluation run exists.
