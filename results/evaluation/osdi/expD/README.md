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

## Testbed focused correctness tests (2026-10-16/17, commits 4b68622 / 3556ea5; results pushed in dc287e7)

`correctness_check_expD_correctness.md`: 18 run directories. Full migration (single, repeated), cold restart (single,
repeated), revisit (4 policies), hybrid (3 policies), cold destination, M1 + M2 without placement, oracle placement,
native (Full migration, OTTER event-driven): PASS. D0 shakedown re-run (`../d0/shakedown_check_d0_shakedown_rerun.md`):
9/9 PASS. Not passing / not clean, all kept as recorded:

1. `...184202` (first cold-destination attempt): INCOMPLETE. Bug: a cold node never ran a session, so the canonical
   denoising schedule was not recorded and provisioning failed. Fixed in 3556ea5; the re-run (`...223452`) passes.
2. `split ... pp=top1 ... 20261016-224842` (M1 + M2 + top-1, incorrect placement): passed the written conditions but its
   placement flow was cancelled after 2 of 299 fragments (M1-family policies re-planned during the placement window and
   cancelled flows "not headed to the owner"). The written conditions did not check placement; a dated condition was
   added (`correctness_conditions.md`) and the run is FAIL under it. Fixed: no M1-family planning before the first move.
   The same symptom was visible in the loopback dry run (2 of 16 fake fragments at B) and was misread as reuse.
3. Full migration was slower than Phase 1's (1 Gbps: TTFO 57.25 s vs Phase 1 53.8 s; native 10.23 s vs 7.85 s): the
   destination allocated a new multi-GB buffer per component while receiving (effective 931 Mbps at 1 Gbps). Phase 1
   receives into two preallocated buffers; the GPU harness now does the same (allocated at MANIFEST, untimed). The
   three Full-migration runs passed every check but their timings are superseded; they must be re-run.
4. Scenario E construction (decided 2026-10-17: Scenario B v2 layout, implemented; loopback 3/3 PASS): in all three hybrid runs the GPU session's bind-ready after
   the final move is ~56 s for every policy (M1 only 56.8, M1 + M2 57.2, OTTER event-driven 56.9 s), because all four
   sessions move together B -> C -> D and share D's ingress (each gets ~250 Mbps). The run measures destination-ingress
   contention, not the source-egress contention G6 is about (its prediction comes from Scenario B v2, whose sessions
   sit on different edges). This follows from an implementation choice made here, not from the preregistration text.
5. Descriptive: in the re-run, OTTER at moves' first chunk at D took 1.70 s (D0: 0.59 s; identical output); one sample.
6. G5 observation reproduced in the re-run (`g5_shakedown_observation.md`, addendum).

To re-run on the testbed after the fixes: `full_single full_repeated native placement hybrid`. The earlier runs stay in
`expD_correctness/` as recorded (superseded, not deleted).

## Re-run after the fixes (2026-10-17, commit 7b35294; results 6e553b3)

All 10 re-run directories pass (`correctness_check_expD_correctness.md`; the two earlier non-passing directories stay
listed as recorded). Single runs, correctness only; nothing here is an Experiment D result.

| test | outcome |
|---|---|
| Full migration, single, 1 Gbps | TTFO 54.09 s (Phase 1 single-handoff `full`: 53.8 s); was 57.25 s before the receive-pool fix; bit-exact, digests ok |
| Full migration, single, native | TTFO 7.24 s (Phase 1: 7.85 s); was 10.23 s |
| Full migration, repeated rho 2 | after the final move 53.41 s; two cancelled transfers, one complete A -> D transfer |
| M1 + M2 + top-1, incorrect (A -> C) | x = 0.72 at B; B_pre / B_post / B_source,total = 0.72 / 0.29 / 1.01; B_fwd 0.72; bind-ready 15.55 s = M1 + M2 without placement (15.55 s) |
| oracle (A -> B) | x = 0.72; bind-ready 4.90 s |
| OTTER event-driven, native | TTFO 0.69 s, bind-ready 3.19 s |
| hybrid (Scenario B v2 layout), GPU session bind-ready after the final move | M1 only 56.83 s, M1 + M2 43.15 s, OTTER event-driven 42.89 s; network sessions restored after their last move in 53.0-55.1 s (M1 only) vs 36.3-39.9 s (M1 + M2, OTTER event-driven); source A per network session 1.31 vs 1.00 Sinks |

The Full-migration timings now match Phase 1's single-handoff baseline (within 0.3-0.6 s), M1 + M2 + top-1 places and
forwards as the network-level A-pilot predicted (B_pre 0.71, B_post 0.29, B_source,total 1.00, B_fwd 0.72), and the
hybrid scenario now creates source-egress contention (A's egress, not one destination's ingress, is shared).

## Sweep tooling (2026-10-17): G9 steady-state mode, aggregator, driver

- `tools/eval/steady_state.py` (G9 first clause): unmodified generation vs OTTER-enabled generation (decode-completion
  hook, per-chunk slot read and metrics row; PSNR off in both), same GPU and seed, ABBA order over reps, chunk intervals
  over 200 chunks after 30 warm-up chunks, frames hashed to confirm identical output, GPU 0 state recorded.
- `tools/eval/expD_validity.py`: the prereg's run-validity rules, shared by the aggregator and `--skip_done`.
- `tools/eval/aggregate_expD.py` + `aggregation_spec.md` (written before any sweep data; interpretations of the frozen
  text marked for review): G1-G9 verdicts, configuration table, invalid runs, scenario A extra-rep list.
  Checked on real GPU data (D0 shakedown re-run): discarded bytes M1 only 1.02 / M1 + M2 0.036 Sink (Phase 1: 1.01 /
  0.07), all four runs valid.
- `tools/eval/run_expD_sweep.py`: the 147-run matrix (A 30, B 36, C 12, D 12, E 9, F 12, G 12, generalization 24) +
  G9, 14 orchestrator invocations, GPU 0 idle gate before each, `--skip_done` resume, `--extra` for scenario A reps 4-5;
  estimate ~7.5 h. Orchestrator additions: `--skip_done`, `--rep_start`, `--pp_configs`.
- Loopback dry sweep (1 rep each, fake runtime): every step ran end to end through the driver, orchestrator, validity
  and aggregator; with `--min_reps 1` every criterion path produced a verdict (numbers meaningless at fake scale); with
  the default 3 reps every criterion is NOT EVALUABLE on 1 rep, as specified; a re-start skipped all valid
  configurations. One dry-only driver bug (argument removal for `--node_extra`) was found and fixed.
- Not yet run on GPUs: `steady_state.py` and the driver in real mode (it calls the already tested orchestrator
  invocations with `--launch`).

## GO / NO-GO for the full Experiment D sweep

**Ready to request approval.** The G9 tool's GPU smoke test passed (2026-10-17, `expD_G9_smoke/`, 1 rep x 20
chunks on elves-01 GPU 0, idle before: median chunk interval 554.8 ms unmodified vs 559.1 ms OTTER-enabled, identical
frames; a smoke test, not the G9 measurement). Previously: one short GPU smoke test of the G9 tool (`steady_state.py --reps 1 --chunks 20
--experiment expD_G9_smoke`, ~3 min, kept out of the sweep data). Every in-repo capability passes its focused GPU test,
the planner regression passes, the aggregation rules are fixed in writing before any data, and the driver resumes
safely. Open items that do not block the in-repo sweep: external C/R (blocked, reported as not run); the aggregation
interpretations in `aggregation_spec.md` (G4/G5 subject = Full OTTER, "within" = absolute, T_s = 14.05 s, scenario A
IQR metrics, G9 chunk interval) await review. Known risks from correctness runs (single runs, not results): G5 for Full
OTTER (`g5_shakedown_observation.md`); G9 memory spread (destination peaks 27.9-28.7 GB across policies in the focused
tests, > 1 %).

## Sweep execution log (2026-10-17)

The sweep ran on commit 656dde6 (results 572cfca). Execution anomalies, all kept as recorded:
1. `expD_A/...colddest_rep=2_20261017-180438` and `...native..._colddest_rep=2_20261017-181205`: incomplete. Harness
   bug: the cold destination is shut down after every run, and the closed control socket of the previous run's node was
   reported as "node B lost", aborting the next run before its trigger (and the invocation, so rep 3 never ran). The
   dry sweep ran one rep per configuration and missed it. Fixed (an intentionally closed connection no longer reports
   a loss); no measurement code changed. Re-run of the missing reps on the fixed commit.
2. `expD_A/policy=reuse_dyn_bw=1000_..._rep=1_20261017-173408`: invalid by the frozen rule (NIC receive peak at B
   1168.7 Mbps in one 1 s sample > 1.15 x 1 Gbps, while A sent 1039.9 Mbps and paced egress was 990 Mbps / 10 s; extra
   traffic into B's NIC or a sampling artefact). Re-run under --skip_done.
