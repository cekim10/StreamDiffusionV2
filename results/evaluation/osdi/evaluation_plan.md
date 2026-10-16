# OTTER OSDI evaluation plan (DRAFT for review, 2026-10-16)

Companion documents: `existing_results_inventory.md` (what has been measured, with frozen outcomes),
`figure_manifest.md` (every figure: question, axes, data, status), `gpu_end_to_end_preregistration.md` (Experiment D),
`external_baseline_audit.md` (external systems). Preliminary figures: `results/evaluation/paper_figures/`
(`tools/eval/plot_paper_figures.py`; measured data only).

## Design as evaluated (claims are bounded by what is implemented)

- M1 Temporal State Decomposition: implemented in the GPU harness (immediate 2.67 MiB first, Sink asynchronous,
  ephemeral reconstructed).
- M2 Continuity Wavefront: verified-fragment tracking and preservation across moves; implemented in both harnesses
  (`split` on GPU, every reuse policy on net).
- M3 Progress-Aware Topology Morphing: bottleneck-aware fragment-level provider assignment (`reuse_aware_in`),
  event-driven re-planning with hysteresis (`reuse_dyn`), budgeted placement (`--prepos`); implemented in the
  network harness only. OTTER builds a fragment-level transfer graph from verified availability and capacities; it
  does not select among Star / Line / Tree / Butterfly (those are baselines), and there is no general graph optimizer
  or real mobility predictor.

## Research questions -> experiments -> figures

| RQ | question | experiments (status) | figures |
|---|---|---|---|
| RQ1 | why decomposition is possible | state characterization, ablation, 31-run sweep (done, GPU) | F1a-d |
| RQ2 | interruption reduction | single handoff x 6 bandwidths (done, GPU); external baselines (missing) | F2a-c, F3a |
| RQ3 | progress preservation under repeated mobility | Phase 1 (done, GPU); Scenario B v2 (done, net); Full E revisit (done, net); Experiment D B/E/G (missing, GPU) | F4a-e |
| RQ4 | why fixed topologies are insufficient | B subset (done, net); Full E (done, net) | F5a-c, D1 |
| RQ5 | response to network changes | E-pilot v2, Full E cond. 3 (done, net); Experiment D F (missing, GPU) | F6a-d |
| RQ6 | proactive placement under uncertainty | A-pilot, A3, holder diagnostic (done, net); A1/A2 (missing); Experiment D C/D (missing, GPU) | F7a-e |
| RQ7 | end-to-end on GPU | single handoff (done, partial); Experiment D A-G (missing) | F8a-e, F3c |
| RQ8 | overheads | destination GPU memory (done); sessions scaling (done, net); steady-state overhead (missing); re-planning costs (done, net) | F9a-e |

## Frozen outcomes carried into the paper (not redefined)

H1 (Phase 1): progress loss in bytes yes; latency clause ill-posed. H2: latency rejected, traffic supported.
H3a supported; H3b rejected. P0, H4a, H4b supported; H4c failed at (N=1, 500 Mbps) and fixed by the corrected rule
(Step 1, all pass conditions met). A-pilot GO. H5d FAIL; H5e 3/4 clauses PASS (slow-holder aware FAIL by 0.2 s).
H6a-e supported; H6f supported on the four tested conditions only. **H8a NOT SUPPORTED; H8b SUPPORTED; H8c NOT
SUPPORTED AS WRITTEN.**

## Recommended execution order (each step stops for review)

1. Review and freeze `gpu_end_to_end_preregistration.md` (thresholds, scenarios, fairness).
2. Copy per-fragment logs back from elves-02..04 for the existing network runs (no new runs; enables F6c).
3. Shared planner module + GPU harness ports (prereg section 8, items 1-6), with loopback and single-host tests.
4. Experiment D shakedown: one run per policy in scenario A and B; inspect traces.
5. Experiment D sweep (A, B, C, D, F, G; then hybrid E).
6. Steady-state overhead (G9).
7. External baselines: the two recommended in the audit, scenario A first (single migration), then B if they support
   repeated moves.
8. Optional, only if the paper keeps the claims: A1 reduced (placement budget x lookahead), A2 (calibration), B full
   grid (H6f beyond the subset).

## Cost summary

Experiment D ~180 GPU runs (~8-10 h exclusive GPUs); steady-state overhead ~1 h; external baselines: integration
effort dominates (see audit); A1 reduced ~4 h net-level; A2 ~2 h net-level; B full grid ~2 h net-level.

## External baselines (from `external_baseline_audit.md`)

Feasible: NVIDIA cuda-checkpoint + CRIU (CUDA plugin; cross-node by image transfer + device map, same chip type).
Requires adaptation: GCR (FAST '26; single-node artifact, sm_80 build, replacement libcuda, no license). Infeasible
with public code: PhoenixOS (CUDA 11.3; cross-node path unreleased), Cricket, Singularity. Driver 575.51.03 (one host
confirmed 2026-10-16): cuda-checkpoint's cross-GPU migration API needs 580, so cross-node restore is unverified on the
testbed; first action is a two-host empirical restore test (or a driver upgrade decision with the administrators).

## Highest-risk items

1. External C/R systems restoring a CUDA process on a different physical node with a different GPU instance (see audit).
2. Porting M3 to the GPU harness without changing its validated decisions (shared module, regression on the network
   harness's pilots).
3. Scenario E cannot be four GPU sessions on one L40S (25.8 GiB per session); it is hybrid and must be described so.
4. Frame-level timestamps (new logging) must not perturb the service time (G9 guards it).
5. Other users on elves-03/04 (GPU 1) and occasional external NIC traffic (two contaminated runs so far): per-run
   GPU and NIC validity checks stay mandatory.
