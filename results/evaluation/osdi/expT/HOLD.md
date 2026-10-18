# Experiment T - ON HOLD (2026-10-18)

**Status: paused by the user's decision of 2026-10-18 (evaluation prioritization). Not cancelled, not amended, not run.**

## Why

The evaluation effort moves to three controlled follow-up experiments that test the paper's core claims more directly
(`../followup_common.md`): W (workload diversity: M1's continuity premise and Sink-version stability), R (repeated
mobility: the operating region of M2) and N (network adaptation: when M3's re-planning helps, does nothing or hurts).
The reasons recorded at the decision:
- ExpT's purpose was M3 generalization, but Experiment D already shows a controlled-condition trade-off (G7 supported,
  G5 not supported) that ExpT's trace mix would not explain;
- the Step 1B inspection showed that Lumos5G's `tower_id` changes only at or outside 5G coverage (connectivity
  transitions, not handovers; 0 of 1,298 changes while 5G-connected) and that eligible windows migrate every ~40 s
  (rho ~ 0.3-0.4), and MAWI samplepoint-F is a transit link, not an inter-edge link: the traces would cost tens of GB
  and still not settle deployment realism;
- the more basic open question is whether the temporal state decomposition holds across streaming workloads (W).

No ExpT result exists; this decision was made from trace statistics and Experiment D outcomes only, never from ExpT data.

## What is preserved unchanged

| item | file | state |
|---|---|---|
| preregistration v3.1 | `preregistration.md` (freeze commit 2a781f8d, record `prereg_freeze.md`) | FROZEN, unchanged |
| change logs v2, v3, v3.1 | `prereg_v2_changes.md`, `prereg_v3_changes.md`, `prereg_v3.1_changes.md` | unchanged |
| planning documents | `deployment_model.md`, `trace_candidates.md`, `harness_plan.md`, `sink_stability_plan.md` | unchanged (`trace_candidates.md` gets one dated erratum, see below) |
| Step 1A access report | `step1a_access_report.md` (81f7924) | unchanged |
| Step 1B feasibility report and scripts | `step1b_feasibility_report.md`, `step1b_inspection_scripts/` (31ea9d8) | unchanged |
| Amendment A1 | `amendment_A1_draft.md` (DRAFT v2, 19b1fa3) | **not adopted**; stays a draft |
| mobility trace comparison | `mobility_trace_comparison.md` (19b1fa3) | unchanged; no trace substituted |

Downloaded inspection data (the Lumos5G archive and the 20 MiB MAWI prefix) were kept outside the repository and are
not part of any result. Experiment D and the M3 implementation are not modified by this hold.

## Resuming

ExpT can resume from its current state: the frozen v3.1 text, A1 (to be reviewed and adopted or replaced before any
MAWI download) and the open feasibility items of `step1b_feasibility_report.md`. Any amendment must still be dated and
made before any ExpT data exist. The Sink-version stability measurement of `sink_stability_plan.md` moves into
Experiment W (W1) and is no longer an ExpT prerequisite.
