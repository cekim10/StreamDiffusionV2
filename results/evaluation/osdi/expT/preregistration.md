# Experiment T: trace-driven evaluation of OTTER M3 - preregistration (v3.1, FROZEN 2026-10-17)

**FROZEN.** Hypotheses, thresholds, decision rules, trace eligibility, mapping, trigger, residual-capacity and selection
rules, validity, analysis and the exploratory counterfactual procedure are frozen exactly as written below (v3.1,
approved 2026-10-17 conditional on the three v3.1 wording changes, which are included). The freeze commit and date are
recorded in `prereg_freeze.md`. Later corrections are dated errata appended at the end; results are judged against
this text. Nothing in this study had run, and no trace had been downloaded, at the freeze. History: v1 a720b5d,
v2 f799a74, v3 79c0505 (changes: `prereg_v2_changes.md`, `prereg_v3_changes.md`, `prereg_v3.1_changes.md`).

## 0. Relation to Experiment D and freeze scope

- Experiment D (prereg v3, frozen 81bb628; results `../expD/expD_report.md`) is complete and is not re-tested,
  reinterpreted or replaced: G1-G4, G6-G8 supported; G5, G9 not supported; external C/R not run. Experiment T has its
  own directories (`results/evaluation/expT_*`), hypotheses and aggregation. It evaluates the **same frozen M3** (rules
  and thresholds unchanged); the M3 code is not modified.
- **Frozen before any formal Experiment T outcome is examined:** hypotheses, thresholds and decision rules (section 6),
  trace eligibility, mapping, trigger, residual-capacity and selection rules (section 3), validity (section 7), analysis
  and aggregation units (section 8), the exploratory counterfactual procedure (section 9).
- **After the freeze:** download and deterministic preprocessing implementing the frozen rules (the generated segment
  list and the eligibility statistics are committed before the first run), harness implementation (`harness_plan.md`),
  loopback tests and a correctness shakedown (one run per block, not used for any hypothesis). A measurement bug found
  then is fixed and recorded as a dated erratum; criteria are not changed.

## 1. Question

Under measured mobility timing and measured traffic variability applied as inter-edge residual capacity, does OTTER's
event-driven re-planning (M3) shorten restoration relative to re-planning only at moves, at what traffic cost, and does
it stay quiet when nothing changes? (Event-level re-planning costs are estimated by a model and reported as
exploratory.)

## 2. Setting

- Deployment model: `deployment_model.md`. Placement is disabled (the traces give no destination prediction), so
  "Full OTTER" = OTTER event-driven and "Full OTTER at moves" = OTTER at moves (prereg v3 of Experiment D, section 3).
- Policies: M1 only (`restart`), M1 + M2 (`reuse_fixed`; GPU `split`), OTTER at moves (`reuse_aware_in`, **AM**), OTTER
  event-driven (`reuse_dyn`, **ED**).
- Harness: network-level primary (four hosts, `restore_orchestrate.py` / `restore_node.py`), GPU confirmation subset
  (`mobility_orchestrate.py`, dog workload). Site uplinks 1 Gbps nominal per direction; Sink 1,725,236,640 B (412 x
  4 MiB fragments).

## 3. Traces, mapping, trigger, residual capacity, selection (rules frozen; data examined only after the freeze)

### 3.1 Mobility (Lumos5G 1.0; `trace_candidates.md` M-a)

- **Trace unit:** a run file of the dataset = a per-second sequence of `tower_id`. A missing `tower_id` takes the
  previous value; a run file with more than 10 % missing rows is not used.
- **Tower handover vs edge migration.** A tower handover is a change of `tower_id` between consecutive seconds. An edge
  migration is a change of *edge site* that persists: with cluster size k and hysteresis H,
  - site(tower) = floor(rank(tower) / k), rank = order of first appearance of the tower in the run file;
  - a migration to site s is issued at second t + H when the site changed to s at second t and stayed s for every
    second of [t, t + H]; a change that does not persist H seconds issues no migration (ping-pong suppressed). The
    migration happens **at t + H**, when the dwell has been observed; it is never backdated to t (a deployed system
    cannot use future information), and every timing metric starts at t + H.
  **Primary: k = 1, H = 3 s.** H = 3 s is a judgement-based minimum dwell that suppresses ping-pong handovers of a few
  seconds while keeping the move close to the handover; the migration is delayed by H relative to the handover
  (the restoration clock starts at the migration). **Pre-specified sensitivity (block S, section 6.3):** k = 2 and
  k = 4 (with H = 3 s); H = 0 s (every tower handover is a migration) and H = 10 s (with k = 1).
- **Origin and persistent site-to-node mapping.** The source **A** is the origin edge where the Sink version was taken
  (the session's home before the window); it is not one of the trace's cells. At t0 (the window start) the session
  migrates from A to the first site of the window (the first move, as in Experiment D). Each distinct site of the
  window is mapped to one of B, C, D in order of first appearance and **keeps that node for the whole run**: a return
  to a site is a revisit of the same node, so its holder's verified fragments are reused (M2) exactly as the frozen
  policies do.
- **Eligibility (needed for persistence with three edge nodes):** a window is eligible if it has <= 3 distinct sites
  under the given (k, H) and >= 2 migrations after the first move. Windows with more sites are not used, which biases the
  sample towards less dispersed mobility; the eligible fraction and the site-count and migration-rate distributions of
  eligible vs all windows are computed from the traces and reported with the segment list, before any run.
- **Window:** 120 s starting at a second where the site is stable for H seconds; the last migration inside the window
  is the final move; the run continues until restoration completes or the deadline.
- **What this is (paper wording):** "We derive edge migration schedules from measured cellular mobility traces using a
  deterministic cell-to-site mapping and handover hysteresis." It does not reproduce measured edge migrations.

### 3.2 Inter-edge residual capacity (MAWI samplepoint-F; `trace_candidates.md` X-a)

- **What MAWI is used as:** a *measured source of traffic variability* on a real 1 Gbps link (WIDE's transit link to
  its upstream ISP). It is **not** a representative trace of an edge-metro network, of edge-site uplinks, or of any
  operator's backhaul; the conclusions are limited to "M3 under measured load variability of this kind".
- **Days:** samplepoint-F traces before 2023-07-01 (the transit link only).
- **Utilization:** per second and direction, u(t) = bytes in that second x 8 / 1 Gbps, from the captured frame lengths.
- **Residual capacity:** for a site uplink of nominal capacity C = 1 Gbps: available(t) = max(C (1 - u(t)), C_min),
  **C_min = 50 Mbps primary**. Assumptions: R1 utilization is scale-free across 1 Gbps links; R2 cross-traffic is
  open-loop; R3 the floor C_min is required by the harness (a rate of 0 means "unshaped" in both node types' token
  buckets) and keeps a link usable when u(t) > 0.95; R4 the four sites receive independent windows. **C_min is a
  sensitivity variable:** every run reports its clamped seconds (count, share, per link) and the restoration bytes sent
  on clamped links during clamped seconds, and block S repeats a subset with C_min = 10 Mbps (section 6.3). Both 50 and
  10 Mbps are lower bounds of the experiment's capacity model, not values measured in the trace.
- **Limitations stated with every result:** transit-link traffic composition and aggregation differ from edge-metro
  traffic; per-second averaging hides sub-second bursts; open-loop replay overstates rigidity; independence across
  sites may understate correlated congestion; capacity scaled to the testbed's 1 Gbps; the floor removes the deepest
  degradations.
- **Window assignment:** 120 s windows; per run, A's egress and the egress and ingress of B, C, D each receive a window
  direction, drawn without replacement, preferring distinct MAWI days (a day is reused only when the eligible days are
  exhausted; reuse is reported).

### 3.3 Variability metric, strata and selection (from trace statistics only)

- **Variability V of a run's capacity schedule:** for each of the 7 series a run uses (A egress; B, C, D egress and
  ingress), sigma_i = standard deviation over the 120 s of available_i(t) / C (normalized by the **nominal** capacity,
  not by the mean, so V does not blow up when the mean is low); V = the mean of the 7 sigma_i. The mean level
  L = mean over series and time of available(t) / C is reported next to V.
- **Strata:** tertiles of V over all candidate capacity schedules (cross-traffic strata) and tertiles of the median
  inter-migration time of eligible mobility windows (mobility strata).
- **Selection:** 2 (mobility window, capacity schedule) pairs per cell of the 3 x 3 strata = **18 pairs**, seed
  20261017, with at most one mobility window per Lumos5G run file per cell and capacity windows from distinct MAWI days
  where possible. The list (file hashes, offsets, k, H, V, L, clusters) is generated by the frozen script and committed
  before the first run; pairs are never replaced after a run.
- **Clusters for aggregation:** each pair records its mobility cluster and capacity cluster (the set of MAWI days it
  uses). Mobility cluster = the measurement session when the dataset's metadata identifies sessions (run files of one
  session form one cluster), otherwise the run file; which applies is decided from the metadata before selection and
  recorded with the segment list.
- **Used-link variability (descriptive):** V_used = the mean standard deviation (nominal-normalized) over the series
  that actually carried restoration traffic in a run, reported next to V; V (all 7 series) stays the stratification
  metric.
- **Feasibility rule:** if, after download, fewer eligible windows, clusters or MAWI days exist than the selection
  needs, or the metadata differ from this text's expectations (e.g. no per-second `tower_id`), the shortfall is
  reported as a feasibility issue for review; the frozen rules are not changed to make the data fit.

## 4. Runs

| block | content | runs |
|---|---|---|
| P primary (network level, N = 1, k = 1, H = 3 s, C_min = 50 Mbps) | 18 pairs x 4 policies x 3 reps | 216 |
| C contention (N = 4: the pair's session + 3 sessions on other eligible mobility windows of the same stratum cell, seeded, each with its own persistent mapping onto B, C, D; one shared capacity schedule) | the 6 high-V pairs x 4 policies x 3 | 72 |
| NC1 negative control: trace mobility, constant capacity (no cross-traffic) | 6 mobility windows (2 per mobility tertile) x {AM, ED} x 3 | 36 |
| NC2 negative control: cross-traffic only on A's ingress (unused by restoration) | 6 pairs x {AM, ED} x 3 | 36 |
| PC positive control: Experiment D scenario F's step (C egress -> 62.5 Mbps when D holds 50 %) | {AM, ED} x 3 | 6 |
| V counterfactual validation: ED limited to its first re-plan (then AM rules), section 9 | the 6 high-V pairs x 3 | 18 |
| S sensitivity: k = 2; k = 4; H = 0 s; H = 10 s; C_min = 10 Mbps | 9 pairs (one per stratum cell, re-derived per condition by the same rules) x {AM, ED} x 3, per condition | 270 |
| GC GPU calibration (noise band only) | 1 pair x {AM, ED} x 3 | 6 |
| G GPU confirmation | 3 pairs (one per V tertile, middle mobility tertile) x 4 policies x 3 | 36 |

Total 654 network-level runs (~16 h at ~1.5 min) + 42 GPU runs (~3 h). Order: NC1, NC2, PC, P, C, V, S, GC, G; policy
order within a rep randomized (seed recorded).

## 5. Metrics

- **T_r** (restoration time): final migration's handoff request -> the Sink complete and verified at the final owner
  (network level: the `restored` event; GPU: Sink verified). **Bind-ready** (GPU): first chunk with the Sink bound.
- **S** (source bytes): bytes sent by A for the session / Sink size; **B_tot**: all fragment bytes / Sink size.
- **Re-plans**: ED re-plan decisions (count; per minute).
- Per configuration: medians over >= 3 valid reps. Per pair p: **R_p** = T_r(ED) / T_r(AM) and **dS_p** = S(ED) - S(AM)
  from those medians.
- **Trace-level aggregation:** per mobility cluster (Lumos5G run file), the median of R_p (and dS_p) over its pairs in
  the stratum considered; the trace-level statistic is the median of these cluster medians.

## 6. Hypotheses, thresholds and decision rules

### 6.1 Primary (block P unless stated)

- **T1 - benefit under measured variability.**
  Decision: SUPPORTED iff, in the high-V tertile, the median of R_p over pairs is <= 0.90 **and** the trace-level
  median (section 5) is <= 0.90; and in every V tertile both the pair-level and the trace-level medians are <= 1.05.
  NOT EVALUABLE if any tertile has fewer than 4 pairs with valid medians or fewer than 3 mobility clusters.
  Rationale: 1.05 is a non-inferiority margin of about the run-to-run spread of restoration time in Experiment D's
  repeated scenario (bind-ready 15.04-15.82 s, ~5 %); 0.90 asks for about twice that spread. Judgement informed by
  Experiment D, not derived from a model.
- **T2 - no spurious re-planning.** Decision: SUPPORTED iff in NC1 and in NC2 the median ED re-plan count is 0 and the
  median over windows of |T_r(ED) - T_r(AM)| is <= 1.0 s (Experiment D G7's no-change clause).
- **T3 - traffic cost.** Decision: SUPPORTED iff in every V tertile the pair-level and the trace-level medians of dS_p
  are <= 0.05 Sink. Rationale: about the run-to-run spread of OTTER's source bytes in Experiment D's repeated scenario
  (1.02-1.06 Sinks); for scale, Experiment D's incorrect-placement re-plan added 0.22 Sink.
- **T5 - positive control.** Decision: SUPPORTED iff median T_r(ED) <= 0.5 x median T_r(AM) in block PC (Experiment D
  G7's primary clause).
- **T6 - GPU direction.** The GPU block confirms direction only; no magnitude is claimed from it, and with 3 pairs it
  is a limited consistency check, not a statistical test. Noise band from a **separate calibration block GC** (one
  additional pair from the middle stratum cell, chosen by the same seeded rule and distinct from G's pairs, AM and ED,
  3 reps each, run before block G): n_GPU = 2 x the median over GC's two configurations of the range (max - min) of
  bind-ready over its 3 reps. GC runs are used only for n_GPU and never for the T6 decision. Decision: SUPPORTED iff for each of the 3 GPU pairs either
  sign(median bind-ready(ED) - median bind-ready(AM)) = sign(network-level T_r(ED) - T_r(AM)) on the same pair, or
  both absolute differences are <= max(1.0 s, n_GPU).

(T4 of v2 moved to the exploratory analysis, section 9.)

### 6.2 Contention (block C, N = 4)

T1 and T3 rules applied to the 6 high-V pairs with N = 4, reported as T1-C and T3-C (pair-level; trace-level where >= 3
clusters), separate from the primary.

### 6.3 Sensitivity (block S)

For each condition (k = 2, k = 4, H = 0 s, H = 10 s, C_min = 10 Mbps): the medians of R_p and dS_p over its 9 pairs,
the re-plan rate, the migration rate, and (for C_min) the change in R_p and dS_p on the pairs shared with block P.
Labelled as sensitivity; never changes a primary verdict.

### 6.4 Mandatory reporting (no threshold)

Every pair where ED increases median T_r or S relative to AM (values listed); M1 only and M1 + M2 on every pair;
clamped seconds per run (R3); excluded mobility windows (eligibility statistics); MAWI-day reuse; every run with a
Sink-version event (section 10).

## 7. Validity

Experiment D's rules (`tools/eval/expD_validity.py`) plus: paced egress <= 1.05 x the time-averaged cap per node per
10 s window; NIC peaks <= 1.15 x the window's maximum cap; every scheduled cap change and migration applied within
1 s of its schedule; GPU 0 idle before each GPU run. Invalid runs are kept, listed with reasons and re-run; none is
deleted.

## 8. Analysis

Per configuration: medians over >= 3 valid reps (otherwise NOT EVALUABLE). Pair level and trace level (section 5) both
computed for every tertile. Uncertainty (descriptive): a cluster bootstrap 95 % interval (10,000 resamples of mobility
clusters, pairs within a resampled cluster kept together, seed 20261017) and a Wilcoxon signed-rank p-value over
cluster medians. Decisions use the medians only. No outcome-dependent re-selection of segments, thresholds, policies,
k, H or C_min.

## 9. Exploratory: model-estimated re-planning effects (no hypothesis verdict)

Event-level effects are **model-estimated**, not causal claims, unless section 9.3 validates the model counterfactually.

1. **State capture** at every ED re-plan (verified fragments per node, in flight, assignment per provider, rates,
   caps; `harness_plan.md` item 4).
2. **Two branches** simulated by the fluid model (`restore_model.py`, state-injected) under the recorded remaining
   schedule: K (keep the pre-re-plan assignment, later triggers as AM) and A (apply the re-plan, later triggers as
   ED); dT = T_r(A) - T_r(K), dS = S(A) - S(K).
3. **Validation, two kinds.**
   - *Factual:* the model replays each executed P run from its start with the logged decisions;
     e_run = |T_r,model - T_r,measured| / T_r,measured. Passes if the median e_run <= 0.10 **and** the 90th percentile
     e_run <= 0.20 (tail check). eps = the 90th percentile of |T_r,model - T_r,measured| in seconds, fixed before any
     classification.
   - *Counterfactual (controlled):* block V runs ED limited to its first re-plan (after it, AM rules); on the same pair,
     the AM run of block P is the measured no-re-plan branch and the V run the measured re-plan branch, so the measured
     effect of the first re-plan is dT_meas = T_r(V) - T_r(AM). Passes if, over the 6 pairs with a first re-plan,
     sign(dT_model) = sign(dT_meas) or both |.| <= eps in >= 5 of 6 pairs, and the median |dT_model - dT_meas| <= eps.
     The limited variant is a validation instrument; it is not an OTTER policy and is not compared in any hypothesis.
     **Scope of this validation:** it measures the effect of enabling the first event-driven re-plan under a policy
     that afterwards follows at-moves scheduling. That is not identical to the effect of a first re-plan inside full ED
     (the first re-plan changes the fragment distribution and with it the conditions of later re-plans), so it validates
     the model on that limited policy only; passing it does not establish that the model predicts every unexecuted
     policy.
   If both pass, event-level results are labelled "model-estimated, counterfactually validated on first re-plans";
   otherwise "model-estimated, not counterfactually validated".
4. **Classes** (each re-plan): *ambiguous* if its run's factual error > eps; else *beneficial* (dT < -eps), *harmful*
   (dT > +eps), *costly without benefit* (|dT| <= eps and dS > 0.05 Sink), *neutral* (|dT| <= eps, dS <= 0.05 Sink).
5. **Aggregation** over P: counts and shares per class; for harmful re-plans the sum and median of dT and dS; for costly
   re-plans the sum and median of dS; per run and per hour of trace time; the share of each pair's measured
   T_r(ED) - T_r(AM) attributable to its re-plans' dT (descriptive). A policy-level difference never labels a single
   re-plan; no threshold and no verdict.
6. Controls: re-plans in NC1 and NC2 (expected none) are classified the same way; PC's step re-plan model dT is
   compared with its measured paired difference.

## 10. Sink-version events (separate applicability study)

The frequency of Sink promotions during restoration windows is a separate applicability study
(`sink_stability_plan.md`) with its own report; it does not gate any hypothesis. Network-level runs carry no generation
(no promotion possible); the GPU block uses the dog workload. Any run with a Sink-version event is flagged, excluded from
T1-T6 as Experiment D's scope rule requires, and listed with its count, timing and affected state volume; none is
dropped silently.

## 11. Scope

Placement disabled; no last-mile modelling; non-blocking metro core; open-loop residual capacity from MAWI as a
variability source (3.2); synthetic cell-to-site mapping (k), migration hysteresis (H) and the <= 3-site eligibility
(3.1); one Sink version per restoration; 1 Gbps emulated uplinks. Star/Line/Tree/Butterfly are not part of this study.

## 12. Decisions at the freeze (2026-10-17 review)

Approved as written: deployment model; persistent site-to-node mapping; k = 1, H = 3 s primary with k = 2, 4 and
H = 0, 10 s sensitivity; <= 3-site eligibility with its selection effect reported; V and trace-level aggregation;
T1-T3 and T5 thresholds; section 9 as exploratory; T6 with a separate calibration block; counterfactual validation
limited to the first-re-plan policy; C_min = 50 Mbps with a 10 Mbps sensitivity; 654 network-level and 42 GPU runs.
Still required before any run, without changing the rules above: download approvals (Lumos5G via the user's IEEE
DataPort login; MAWI pcaps; optionally the UCC 5G archive), the deterministic preprocessing and segment list, the
harness implementation and its correctness shakedown.

## Errata (dated; appended after the freeze)

- none
