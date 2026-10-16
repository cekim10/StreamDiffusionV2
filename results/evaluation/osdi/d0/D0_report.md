# D0 GPU integration readiness report (2026-10-16)

Phase 1 (freeze) is complete: Experiment D preregistration v3 frozen at commit 81bb628 (record: `../prereg_freeze.md`).
This report covers Phase 2 (D0). Nothing in D0 is a result of Experiment D; no frozen hypothesis or earlier outcome was
changed.

## Status by item

| item | status | where |
|---|---|---|
| A. Hardware audit | **done** (read-only, through the agents); findings below | `d0/hw_audit/<host>.txt` |
| B. Recover node fragment logs, F6c | **done**: 1947 files (649 per node, 12 experiments) recovered, 0 failures; F6c generated | `d0/node_log_recovery.md`, `paper_figures/eval/F6c_*` |
| C. Shared planner | **done** | `tools/eval/restore_planner.py`; summary in `shared_planner.md` |
| D. Network regression | **PASS** (decision equivalence) with two loopback-timing differences explained below | `tools/eval/test_restore_planner.py`, `run_planner_regression.sh`, `compare_planner_regression.py`; `planner_equivalence_seed2.txt`, `network_regression_loopback.md` |
| E. GPU integration | **done for the D0 shakedown scope**; dry-run validated | `mobility_orchestrate.py`, `mobility_node.py`, `run_gpu_dryrun.sh` |
| F. GPU correctness shakedown | **not run (needs the GPUs)**; commands below | `tools/eval/run_d0_shakedown.sh` |
| G. External C/R readiness | **done: BLOCKED** (no CRIU, no cuda-checkpoint, no sudo, CapEff 0 on all hosts) | `d0/cr_readiness/<host>.txt` |

## A. Hardware audit (2026-10-16 15:28, read-only)

| host | GPUs (L40S) | driver | GPU 0 at audit | kernel | NIC (up) | torch |
|---|---|---|---|---|---|---|
| elves-01 | 2 | 575.51.03 | idle (GPU 1: another user's job, 29 GB, 97 %) | 6.8.0-84 | enp193s0f0np0 10 Gb/s, MTU 9200 | 2.6.0+cu124 |
| elves-02 | 1 | 575.51.03 | idle | 6.8.0-138 | same | same |
| elves-03 | 2 | **575.57.08** | **another user's job, 28 GB, 100 %** (GPU 1 too) | 6.8.0-84 | same | same |
| elves-04 | 2 | **575.57.08** | idle | 6.8.0-64 | same | same |

All: Python 3.10.22, torch 2.6.0+cu124 (CUDA 12.4, cuDNN 9.1), 1.5 TB RAM, >= 4.4 TB free in /home; nvcc only on
elves-02 (12.0, unused); no sudo. Two corrections to earlier records: the driver is not 575.51.03 on all four hosts
(elves-03/04 run 575.57.08; dated errata in the preregistration, `prereg_freeze.md`, `evaluation_plan.md`,
`external_baseline_audit.md`), and elves-02 has one GPU. Neither affects OTTER's transfer path (tensor bytes over TCP);
per-node service times are measured at node start and reported. **Contention:** elves-03 GPU 0 (node C) was in use by
another user; the shakedown script now waits until GPU 0 is idle on all four hosts and all repos are on one commit
before every run (`d0_remote.py gpu_idle`), and stops after 30 min.

## B. Node logs and F6c

`recover_node_logs.sh` copied 649 `fragments.csv` per node (B, C, D) through the agents; nothing local was overwritten.
`verify_node_logs.py`: every receipt at X <= bytes sent into X and short by at most one fragment per flow; 0 failures.
The first version counted only the first verified arrival per fragment and flagged 72 files (24 restart runs under
continuous mobility in Scenario B, where revisited owners receive the Sink again after the drop) plus 3 files (Full E
restart, B received twice); all receipts are now counted and the change is dated in the script. F6c (Full E condition
3, rep 1): fragments at D stacked by sender; at moves A/B/C = 101/155/156 fragments, restored 67.8 s; event-driven
176/155/81 after 2 re-plans, restored 28.0 s.

## G. External C/R readiness

No host has CRIU, the CRIU CUDA plugin or cuda-checkpoint; the account has no sudo and CapEff = 0 (CRIU needs root or
CAP_CHECKPOINT_RESTORE + CAP_SYS_ADMIN); `ptrace_scope` = 1. Per the instructions nothing was installed. The external
baseline is blocked until the administrators install CRIU (>= 4.0 with the CUDA plugin) and grant the capability; the
cuda-checkpoint binary alone is a user-space download but cannot dump the process tree without CRIU. Same-driver pairs
for a cross-node restore test: elves-01/02 (575.51.03) or elves-03/04 (575.57.08); none has the >= 580 migration API.

## D. Network regression

1. **Decision equivalence** (the decisive check). The pre-refactor orchestrator (commit e345ccd, which produced every
   network-level result) and the shared planner were driven through identical randomized states: `plan()` for all ten
   policies x {move, start, flow_done}, `dyn_check()`, `prepos_start()`, `dissem_assign()`. Seeds 0, 1, 2:
   **0 differing decisions** in 3 x 4000 plan states, 3 x 4000 re-plan states (1542-1595 of which triggered a re-plan),
   3 x 1000 placement states and 3 x 1000 dissemination cases. The fluid model reproduces its pre-registered Step 1 table.
2. **End-to-end loopback replay** of all 43 pre-refactor loopback configurations (`_dryrun_{reg,prepos,a3,dissem,e2,fe}`):
   41 match within tolerance (restoration time 0.5 s + 5 %, bytes max(0.02 Sink, 1.5 fragments), per-link fragments
   +-3, re-plans exact). The tolerance on bytes was first set to 0.02 Sink, smaller than one fragment at loopback
   scale (32 fragments per Sink = 0.031 Sink each); three source-only runs differed by exactly one fragment and pass
   at 1.5 fragments - recorded here because the tolerance was changed after seeing the comparison.
   The **two remaining differences** are both `reuse_dyn` runs whose re-plan count differs (no-change control: 0 old vs
   2 new, one of them with one duplicated fragment; collapse+recovery: 3 old vs 1 new). Cause: at loopback rates
   (~33 Mbps per flow) the 2 s throughput window holds ~2 fragments, so measured rates are quantized by ~50 %
   (re-plans fired on 34 vs 17 Mbps and 34 vs 50 Mbps). A dedicated check ran the no-change control 3 times with each
   implementation: re-plans in 0/3 (old) and 1/3 (new); with the original runs 0/4 vs 2/4, Fisher exact p ~ 0.43,
   i.e. not distinguishable. Since the decision code is identical for identical inputs (item 1), these are input
   (timing) differences, not behaviour changes. On the testbed at 1 Gbps a window holds ~60 fragments (E-pilot v2:
   0 re-plans in 3 controls).
   Note (not changed, to preserve the validated harness): the network harness can count one duplicate fragment when a
   re-plan races the cancelled flow's last send; observed once at loopback and, per the recovered node logs, in 2 of the
   126 physical E runs (one 4 MiB fragment each, E-pilot and E-pilot v2, both counted in their summaries; 0 in Full E).
   The E-pilot notes said "no duplicates in any run" (the aggregator showed medians); dated errata appended there.

## E. GPU integration (dry-run validated)

Implemented (details in `shared_planner.md`): OTTER at moves (`reuse_aware_in`) and event-driven (`reuse_dyn`) via the
shared planner; per-node caps and cap events; placement window with the source generating; instrumentation (per-chunk
decode completion and frames, pre/post/total source bytes, holder-forwarded bytes, aggregate bytes, x verified at the
move, retained and reused progress, version-event counter, re-plans with switching costs).

Bugs found and fixed during D0 (GPU harness only):
1. **Move boundary.** "After the final move" latencies were measured from the end of the post-move planning RPCs
   (synchronous flow cancels), not from the handoff request; first output appeared at -0.3 to -0.8 s. Fixed: the
   boundary is the handoff request. **Implication for Phase 1 (GPU, already reported):** its "after final move"
   latencies were measured from up to ~0.3-0.8 s after the move (Phase 1 notes report a 0.28-0.32 s median
   control-plane delay), so they understate the true value by about that amount. Phase 1 data are unchanged; the
   move request times are in its `events.csv` if the values are to be recomputed for the paper.
2. **Skipped late fragments** could stay claimed forever (a holder asked to forward a fragment still in flight to it);
   for the planner policies the claim is now released and re-planned at the flow's end.
3. **Duplicate after a re-plan** (cancelled flow's last fragment reported after the cancel reply); now taken from the
   cancel reply. Dry run after the fix: 0 duplicates.
4. **Retained metric** counted fragments landing after a restart's drop; now defined on fragments verified before the
   owner was abandoned (restart 0, preserving policies 1.0).

Dry-run results (fake runtime, 256 MiB fake Sink, 100 Mbps, 0.2 s per chunk; protocol checks only, never reported):

| scenario | result |
|---|---|
| single migration (event-driven) | first output 0.21 s, Sink bound 5.6 s (64 MiB) |
| repeated A->B->C->D, rho 2 | restart / fixed / at moves / event-driven all ingress-bound at ~22 s; reuse of verified progress 0.94-0.98; restart retained 0 |
| degradation (C -> 12.5 Mbps at D 50 %) | event-driven 27.0 s (1 re-plan, 0 duplicates) < at moves 43.5 s < fixed routing 62.3 s |
| placement, correct (A->B, top-1 B) | Sink bound 1.5 s; x = 0.75 at B |
| placement, incorrect (A->C, top-1 B) | Sink bound 5.4 s; B (never owner) forwards 0.69 Sink; source total 1.06 |
| Phase 1 policies, old vs new orchestrator | identical bytes (2.00 / 2.02-2.05 / 3.00 / 1.00 Sinks); latencies +0.1-0.5 s = the boundary fix |

Known dry-run artifacts: 1-s ingress peaks of 134-168 Mbps at 100 Mbps (four 4 MiB fragments in one bin; ~3 % at
1 Gbps), and `four_hosts_distinct` false on loopback.

## F. GPU correctness shakedown (to run on the testbed)

One representative configuration per test, 1 Gbps, dog seed 0 k = 2, all four hosts on one commit, GPU 0 idle:
`tools/eval/run_d0_shakedown.sh` (single migration; repeated A->B->C->D at rho 2 with M1 only, M1+M2, at moves,
event-driven; Sink verification and binding are checked in every run; progress preservation in the repeated runs;
degradation C -> 62.5 Mbps at D 50 % with at moves and event-driven; correct and incorrect placement). 9 runs,
~30-40 min including node start-up. Pass conditions (correctness only, not Experiment D criteria): every run binds the
verified Sink and rejoins >= 35 dB; 0 version events; 0 duplicates; no fragment lost; NIC peaks within 1.15 x cap;
event-driven re-plans in the degradation run and not in the repeated run; incorrect placement shows holder forwarding
from the never-owner candidate.

## Remaining blockers before the full Experiment D sweep

1. GPU shakedown (F) on the testbed, after GPU 0 on elves-03 is free.
2a. External C/R: administrators must install CRIU + CUDA plugin and grant capabilities (G); otherwise the external
   comparison is reported as not runnable.
2. Not implemented (prereg section 8): full migration and cold restart as repeated-mobility execution policies
   (scenario B), revisit paths (G), hybrid scenario E, OTTER cold-destination (A, external comparison), external C/R
   integration. Without them scenarios A (partly), B (partly), E, G and the external comparison cannot run.
3. `post_chunks` must cover the longest scenario (the generation window ends a run with `window_exhausted`): scenario
   F's fixed-routing case is predicted at ~63 s after a final move at ~14 s; the default 220 chunks x 0.555 s = 122 s
   leaves a small margin; use 300.
4. Decode-interval metric (descriptive) is degenerate by construction (all frames of a chunk share one decode
   completion); decide whether a dated erratum is wanted.
5. Phase 1 move-boundary implication (fix 1 above) should be reflected when Phase 1 numbers are quoted.

## GO / NO-GO for the full Experiment D sweep

**NO-GO.** The shared planner is regression-verified and integrated for the D0 shakedown scope, but the GPU shakedown has
not run, and four of the seven preregistered scenarios need execution policies or modes that are not implemented
(blocker 2), and the external baseline is blocked by missing CRIU and privileges (2a). Recommended next step: run the
shakedown when elves-03 GPU 0 is free, review it, then implement the
blocker-2 items with the same dry-run + shakedown discipline before requesting approval for the sweep.
