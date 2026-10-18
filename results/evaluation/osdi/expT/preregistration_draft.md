# Experiment T: trace-driven evaluation of OTTER M3 - preregistration (DRAFT v1, 2026-10-17, NOT FROZEN)

**Status: draft for review. Nothing in this study has run; no trace has been downloaded or examined beyond its public
description.** Thresholds marked [proposed] are open for review before the freeze. After the freeze, a later
correction is a dated erratum and results are judged against the frozen text.

## 0. Relation to Experiment D

Experiment D (prereg v3, frozen 81bb628; results `../expD/expD_report.md`) is complete and is not re-tested,
reinterpreted or replaced. Its outcomes stand: G1-G4, G6-G8 supported; G5 and G9 not supported; external C/R not run.
Experiment T is a separate study with its own directories (`results/evaluation/expT_*`), hypotheses (T1-T6) and
aggregation; it evaluates the **same frozen M3** (no change to rules or thresholds) under trace-driven mobility and
inter-edge variability. Agreement or disagreement with a G-outcome is reported as a new observation next to it.

## 1. Question

Under realistic mobility timing and realistic inter-edge capacity variability, does OTTER's event-driven re-planning
(M3) shorten restoration relative to re-planning only at moves, how often does it re-plan when it should not, and what
does that cost in latency and traffic?

## 2. Setting

- Deployment model: `deployment_model.md` (site uplinks with time-varying available capacity; non-blocking core; moves
  at handovers; placement disabled).
- Traces: mobility from Lumos5G 1.0 (`tower_id` changes), cross-traffic from MAWI samplepoint-F (per-second utilization
  of the 1 Gbps transit link, traces before July 2023) (`trace_candidates.md`); M-b is a secondary mobility source only
  if its fields and data license are confirmed.
- Harness: network-level primary, GPU confirmation subset (`harness_plan.md`); four hosts, 1 Gbps site uplinks,
  Sink 1,725,236,640 B (412 x 4 MiB fragments), dog workload for the GPU subset (stable Sink version).
- Policies: M1 only, M1 + M2, OTTER at moves (= Full OTTER at moves), OTTER event-driven (= Full OTTER, placement off).

## 3. Trace preparation and selection (fixed before any run)

- Mobility segments: 120 s windows of Lumos5G runs that contain >= 2 site changes for the chosen k; the site sequence
  maps clusters of k consecutive tower IDs cyclically onto B, C, D (A = the session's first site, the source). k = 1
  primary; k = 2, 4 sensitivity.
- Cross-traffic segments: 120 s windows of MAWI per-second utilization, one direction pair per window; each of A, B, C, D
  receives an independent window (egress from one direction, ingress from the other), drawn without replacement.
- Strata computed from trace statistics only: mobility by median inter-move time (tertiles), cross-traffic by the
  coefficient of variation of available capacity on the windows assigned to the sites a run uses (tertiles).
- Selection: 2 segment pairs per (mobility tertile x cross-traffic tertile) cell, 18 pairs, seeded (seed recorded),
  listed with offsets and file hashes in `segments.json`, committed with the freeze. No segment is replaced after any
  run.

## 4. Runs

| block | content | runs |
|---|---|---|
| primary (network level, N = 1) | 18 segment pairs x 4 policies x 3 reps | 216 |
| contention (network level, N = 4, Scenario B v2 layout, same traces) | 6 segment pairs (the high-variability tertile) x 4 policies x 3 reps | 72 |
| negative control 1: no cross-traffic, trace mobility | 6 mobility segments x {OTTER at moves, OTTER event-driven} x 3 | 36 |
| negative control 2: cross-traffic only on the source's ingress (never used by restoration) | 6 segment pairs x {at moves, event-driven} x 3 | 36 |
| positive control: Experiment D scenario F's step (C egress -> 62.5 Mbps when D holds 50 %), network level | {at moves, event-driven} x 3 | 6 |
| GPU confirmation | 3 segment pairs (one per cross-traffic tertile) x 4 policies x 3 reps | 36 |

Order: controls first (they validate the setup), then primary, contention, GPU. Policy order within a rep randomized
(seeded). Estimated ~10 h network level + ~2.5 h GPU.

## 5. Metrics

Per run: restoration completion after every move and after the final move (T_r; GPU: bind-ready), coverage, source
bytes, total bytes, duplicates; re-plans (count, per-minute rate, timestamps, moved fragments, drained bytes, detection
delay relative to the nearest preceding cap change of the bottleneck provider); assignment changes (fragments per
provider before/after each plan). Per re-plan (offline, `harness_plan.md` item 5): model-estimated effect on completion
time dT_cf and bytes dB_cf; class beneficial / harmful / indistinguishable against the model's validated error bound.
Model fidelity: |predicted - measured| T_r of the executed branch, per run.

## 6. Hypotheses [thresholds proposed]

- **T1 (benefit under realistic variability).** In the high cross-traffic-variability tertile, the median over segment
  pairs of the paired ratio T_r(event-driven) / T_r(at moves) <= 0.90; and in every tertile that median ratio <= 1.05
  (event-driven not worse by more than 5 %). [proposed: 0.90, 1.05]
- **T2 (no spurious re-planning: negative controls).** In both negative controls, OTTER event-driven's median re-plan
  count is 0 and its median T_r is within 1.0 s of OTTER at moves (Experiment D G7's no-change clause, same thresholds).
- **T3 (traffic cost).** In every tertile, the median paired difference in source bytes, event-driven minus at moves,
  is <= 0.05 Sink. [proposed: 0.05]
- **T4 (unnecessary re-plans, event level).** Among re-plans whose counterfactual is distinguishable, the share
  classified harmful is <= 20 %. The share indistinguishable and the distribution of dT_cf are reported regardless.
  [proposed: 20 %]
- **T5 (positive control).** OTTER event-driven's T_r <= 0.5 x OTTER at moves' in the step condition (reproduces the
  network-level E result and Experiment D G7's primary clause).
- **T6 (GPU carries over).** For each of the 3 GPU segment pairs, the sign of the paired median difference (event-driven
  minus at moves) in bind-ready equals the sign of the network-level T_r difference on the same pair, or both
  differences are within 1.0 s.

Mandatory reporting regardless of T1-T6: every segment pair where OTTER event-driven increases median T_r or source
bytes relative to OTTER at moves (with the values), every harmful re-plan, and M1 only / M1 + M2 results on the same
segments.

## 7. Validity

A run is valid under Experiment D's rules (`tools/eval/expD_validity.py`) plus: paced egress <= 1.05 x the
time-averaged cap per 10 s window; NIC peaks <= 1.15 x the window's maximum cap; every scheduled cap change and move
applied within 1 s of its trace time; GPU 0 idle (GPU block). Runs with a Sink-version event are flagged, excluded from
T1-T6 and listed with counts and timing (`sink_stability_plan.md`). Invalid runs are kept, listed and re-run; none are
deleted.

## 8. Analysis

Per (segment pair, policy): median over >= 3 valid reps (otherwise not evaluable). Paired ratios / differences per
segment pair; per tertile: median over pairs with a seeded bootstrap 95 % interval (10,000 resamples) and a Wilcoxon
signed-rank p-value, both descriptive (the criteria use the medians). Counterfactual classes use the model error bound
fixed from the executed-branch validation before classification. No outcome-dependent re-selection of segments,
thresholds or policies.

## 9. Scope and limitations

Open-loop cross-traffic; non-blocking metro core; 1 Gbps emulated uplinks with utilization scaling; synthetic
cell-to-site mapping (k); one Sink version per restoration; placement disabled; no last-mile modelling; the MAWI link is
a transit link used as a proxy for an edge-site uplink (stated as such). Star/Line/Tree/Butterfly are not part of this
study.

## 10. Before the freeze (open items for review)

1. Thresholds in T1, T3, T4.
2. Whether k = 2, 4 sensitivity runs are needed (adds ~2 x 216 network runs) or k = 1 only.
3. Download approval and access: Lumos5G (IEEE DataPort login by the user), MAWI pcaps (large; pre-July-2023 days to be
   chosen by the seeded rule), optionally the UCC 5G archive (to confirm fields and data license).
4. Implementation of `harness_plan.md` items 1-5 and its loopback tests, then a one-run-per-block shakedown, before the
   freeze is used for any reported run.
5. Sink-stability measurement (`sink_stability_plan.md`) runs before or alongside; it does not gate T1-T6 (dog workload
   in the GPU block).
