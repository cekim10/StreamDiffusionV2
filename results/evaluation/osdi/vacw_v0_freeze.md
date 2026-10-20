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

## Implementation record (2026-10-20, before any GPU run)

- **Implementation commit:** `47243de7940b5c39ee7364c2f8c6e91de7361af4` (2026-10-20T18:43Z). Files: `tools/eval/mobility_node.py`
  (fragment store, hash acceptance, fresh capture, `MANIFEST_UPDATE`, bind gating, FakeRuntime dirty fragments),
  `tools/eval/mobility_orchestrate.py` (manifest install, `split_va` / `restart_fresh`, bind records, `summary.vacw`),
  `tools/eval/restore_planner.py` (`holder_order(..., source=)`, default unchanged), `tools/eval/run_wrn.py` (`vacw`),
  `tools/eval/test_vacw.py`.
- **Design Amendment 1** (recorded in `expM2/vacw_v0_design.md` before implementation): I3 / I4 realized by copying a
  fragment to a private `bytes` under the node lock immediately before it is sent and replacing received bytes in place
  under the same lock, with every flow pinning its manifest and buffer object at flow start; no bind-time assembly.
  Hypotheses, thresholds, matrix and rules unchanged.
- **Loopback validation (`python tools/eval/test_vacw.py`, 4 fake nodes, 16 x 4 MiB fake Sink, 100 Mbps, dry promotions
  at calls 60 / 65 / 70 / 115 / 120 / 125 / 170 / 175, 3 fragments dirtied per promotion): ALL PASS, 70 checks + 6 unit
  checks, two full repetitions.**
  - rho 0.5 (`split_va`): fresh transitions 2 / 3 moves; S_1 (by B) and S_2 (by C) each differ from the image the owner
    bound by exactly 3 x 3 = 9 fragments (I5 chain); every bind (B, C, D) is of the snapshot active at bind time and
    follows a whole-digest `sink_verified` of that version (I2 / H1a); no fragment sent under a superseded manifest after
    the next became active (I1); no hash failure other than by-design stale rejections (I3 / I4); at the final move the
    previous owner B holds 7 / 16 valid fragments, all 7 delivered by B and the capturing owner C sent exactly the 9 dirty
    ones (I6; realized = available = 0.438, potential 0.438); capture 0.03 s, manifest wait 0.03-0.04 s on the fake Sink.
  - rho 0.5 (`restart_fresh`): fresh transitions 2 / 3; the source role sent S_K whole after the final move (1.00 Sink;
    3.00 over the run), nothing reused; binds all intended. (`split`): one snapshot, three binds of S_0, no rejections.
  - rho 1 (all policies): the first owner is never bound at T_m = T_s on the loopback, so no fresh transition occurred
    (S_k = S_{k-1} path exercised; the final owner binds S_0) - consistent with the recorded prediction that rho = 1 cells
    may be NOT EVALUABLE for the freshness hypotheses.
  - **Paths not reachable on the A -> B -> C -> D loopback and covered by the in-process unit test only:** a fragment
    of a superseded snapshot arriving after the manifest change (accepted iff its hash equals the new entry, else
    `hash_stale`), the stale-flow `FLOW_HELLO` classification, and the sender skipping stale fragments after its own
    update. The orchestrator's cancellation of superseded flows at a manifest install is implemented but was not
    triggered (no flow is active toward an owner once it is bound; 0 flows cancelled in every run). **I7** (positions
    inside the snapshot) is a property of the GPU Sink pack (`ring/pos_sink` tensors are part of the component) and is
    not exercised without torch.
- **Byte-identical frozen policies:** `split` / `restart` take the same code paths with a single manifest (hash test ==
  the former version test; `holder_order` default unchanged; source role == A); `tools/eval/test_m3v2.py` ALL PASS.
- **Next:** the 36-run GPU matrix (`python tools/eval/run_wrn.py vacw`), nothing else run before it.
