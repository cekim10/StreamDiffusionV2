# Experiment D preparation after D0 (2026-10-16)

Decisions (2026-10-16): (1) preserve the M3 algorithm unchanged and keep the G5 shakedown observation as a known,
unresolved negative observation; (2) implement only the capabilities the frozen preregistration specifies; (3) focused
correctness tests; (4) readiness audit; (5) external baselines on hold. No Experiment D sweep was run; G1-G9 and the
M3 algorithm are unchanged; no existing data was modified.

| # | deliverable | status | where |
|---|---|---|---|
| 1 | implementation summary | done | `implementation_summary.md` |
| 2 | focused correctness tests | **loopback protocol tests: 26/26 PASS; testbed GPU tests written, not run** | `correctness_conditions.md`, `correctness_check__dryrun_d0_gpu.md`; `tools/eval/run_expD_correctness.sh` |
| 3 | updated GPU shakedown report | D0 shakedown 9/9 PASS stands (`../d0/shakedown_check.md`); its re-run on this commit is part of the testbed script (`d0_rerun`) | `../d0/D0_report.md` |
| 4 | planner regression | equivalence PASS (seeds 0-2, 0 differing decisions); loopback replay 40/43 within tolerance, 3 `reuse_dyn` re-plan-count differences | `planner_equivalence_rerun.txt`, `network_regression_loopback_rerun.md` |
| 5 | scenario readiness matrix | done | `readiness_matrix.md` |
| 6 | known G5 observation | documented, preserved | `g5_shakedown_observation.md` |
| 7 | remaining blockers | listed | `readiness_matrix.md` (end) |
| 8 | GO / NO-GO | **NO-GO** (below) | - |

## Planner regression (4)

The planner, the network harness and the fluid model are byte-identical to D0 (`git diff` empty). The decision
equivalence test against the pre-refactor orchestrator (e345ccd) passes on seeds 0, 1, 2 with 0 differing decisions in
plan / dyn_check / prepos / dissem (1542-1595 re-plan states per seed), the same numbers as in D0. The loopback replay
of the 43 pre-refactor configurations: 40 within tolerance; 3 differ, all `reuse_dyn` and all in re-plan count only
(no-change control 0 vs 1; collapse 1 vs 3, T_r 27.3 vs 22.2 s; collapse + recovery 3 vs 1). In D0 the first and last
differed and the collapse-only run matched; this time the collapse-only run differs too. With identical decision code
and identical inputs giving identical decisions (equivalence test), these are run-to-run timing differences of the
loopback event-driven runs (D0 cause: a 2 s window holds ~2 fragments at loopback rates, so measured rates are quantized
by ~50 %); they show that loopback `reuse_dyn` re-plan counts are not reproducible run to run, not that the planner
changed. On the testbed a window holds ~60 fragments.

## Loopback protocol tests (2)

Fake runtime, 64 MiB fake Sink, 100 Mbps, one host: every D0 scenario plus full migration (single, repeated with two
redirects), cold restart (repeated), revisit (four policies), hybrid scenario E (three policies; combined A egress
<= cap, GPU session ~1/4 of it), cold destination, placement (M1 + M2 without / with top-1 on A -> C, oracle), native
(Full migration, OTTER event-driven): 26/26 runs pass the pre-written conditions (NIC, host and GPU-idle checks are
skipped in a loopback test). These test the protocol and accounting only; nothing from them is reported.

## Testbed commands (not run yet)

On elves-01 after `git pull` on all four hosts: `tools/eval/run_expD_correctness.sh` (~2-2.5 h: 15 runs of the new
capabilities + the 9 D0 shakedown runs), then `python tools/eval/check_expD_correctness.py` and
`python tools/eval/check_d0_shakedown.py d0_shakedown_rerun`.

## GO / NO-GO for the full Experiment D sweep

**NO-GO.** Every preregistered scenario except the external C/R comparison can now be executed and every G1-G8 quantity
is recorded, but: the focused GPU correctness tests and the D0 shakedown re-run have not run on the testbed; G9's
steady-state clause has no measurement mode yet; the G1-G9 aggregation script and the sweep driver are not written;
external C/R is blocked by the testbed (no CRIU / cuda-checkpoint / privileges). Recommended order: testbed correctness
tests -> review -> G9 mode + aggregator + driver (dry-run) -> request approval for the sweep (external C/R handled
separately).
