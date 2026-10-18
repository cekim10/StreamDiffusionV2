# Experiment T: trace-driven evaluation of OTTER M3 - preregistration (DRAFT v2, 2026-10-17, NOT FROZEN)

**Status: draft for review.** Nothing in this study has run; no trace has been downloaded or examined beyond its
public description. v1 (a720b5d) is superseded; changes in `prereg_v2_changes.md`. After the freeze, corrections are
dated errata and results are judged against the frozen text.

## 0. Relation to Experiment D and freeze scope

- Experiment D (prereg v3, frozen 81bb628; results `../expD/expD_report.md`) is complete and is not re-tested,
  reinterpreted or replaced: G1-G4, G6-G8 supported; G5, G9 not supported; external C/R not run. Experiment T has its
  own directories (`results/evaluation/expT_*`), hypotheses T1-T6 and aggregation. It evaluates the **same frozen M3**
  (rules and thresholds unchanged) and the M3 code is not modified.
- **Frozen at the freeze, before any formal Experiment T outcome is examined:** hypotheses and thresholds (section 6),
  trace selection rules (section 3), cell-to-site mapping and trigger rules (section 3), residual-capacity rules
  (section 3), validity (section 7), analysis and counterfactual procedures (sections 8-9).
- **After the freeze:** download and preprocessing (deterministic scripts implementing the frozen rules; the generated
  segment list is committed before any run), harness implementation (`harness_plan.md`), loopback tests and a
  correctness shakedown (one run per block, not used for T1-T6). A measurement bug found then is fixed and recorded as a
  dated erratum; criteria are not changed.

## 1. Question

Under measured mobility timing and measured traffic variability applied as inter-edge residual capacity, does OTTER's
event-driven re-planning (M3) shorten restoration relative to re-planning only at moves, how often does it re-plan
without benefit or with harm, and what does that cost in latency and traffic?

## 2. Setting

- Deployment model: `deployment_model.md`. Placement is disabled (the traces give no destination prediction), so
  "Full OTTER" = OTTER event-driven and "Full OTTER at moves" = OTTER at moves (prereg v3 section 3 definition).
- Policies: M1 only (`restart`), M1 + M2 (`reuse_fixed`; GPU `split`), OTTER at moves (`reuse_aware_in`, "AM"), OTTER
  event-driven (`reuse_dyn`, "ED").
- Harness: network-level primary (four hosts, `restore_orchestrate.py` / `restore_node.py`), GPU confirmation subset
  (`mobility_orchestrate.py`, dog workload). Site uplinks 1 Gbps nominal per direction; Sink 1,725,236,640 B (412 x
  4 MiB fragments).

## 3. Traces, mapping, trigger and residual capacity (rules frozen; data examined only after the freeze)

### 3.1 Mobility (Lumos5G 1.0; `trace_candidates.md` M-a)

- Unit: a run file of the dataset as a per-second sequence of `tower_id`. Rows with a missing `tower_id` take the
  previous value; a run with more than 10 % missing rows is not used.
- **Handover:** second t is a handover if tower_id(t) differs from tower_id(t - 1).
- **Cell-to-site mapping (cluster size k).** Within a run file, distinct tower IDs are ranked by first appearance
  (rank 0, 1, 2, ...). Site(tower) = floor(rank / k). **Default k = 1** (one edge site per tower). k = 2 and k = 4 are
  pre-specified sensitivity analyses (section 6.3), reported separately from the primary evaluation.
- **Migration trigger:** a move is issued at second t when site(tower_id(t)) differs from site(tower_id(t - 1)); no
  hysteresis or dwell filter (the trace as measured). Moves less than 1 s apart cannot occur (1 s resolution).
- **Site-to-node assignment:** a segment starts at a handover; the site before it is the source **A** (the Sink
  version is taken there at t0 = the first move). Later sites are mapped to testbed nodes B, C, D in order of first
  appearance in the segment, cyclically (B, C, D, B, ...) when a segment has more than three distinct non-source sites;
  a return to an already mapped site maps to the same node (a revisit). A return to the source site maps to the next
  node in the cycle (the harness never moves execution back to A); such returns are counted and reported.
- **Segment:** a 120 s window starting at a handover and containing >= 2 moves under the given k. The final move is the
  last move inside the window; the run continues until restoration completes or the deadline.

### 3.2 Inter-edge residual capacity (MAWI samplepoint-F; `trace_candidates.md` X-a)

- **What MAWI is used as:** a *measured source of traffic variability* on a real 1 Gbps link (WIDE's transit link to
  its upstream ISP). It is **not** a representative trace of an edge-metro network, of edge-site uplinks, or of any
  operator's backhaul. It provides realistic second-scale fluctuations of a shared link's load; the claim of this study
  is limited to "M3 under measured load variability of this kind".
- **Days:** samplepoint-F traces before 2023-07-01 (the transit link only; the 10 Gbps BBIX link was added later),
  chosen by the seeded rule below.
- **Utilization:** per second and direction, u(t) = bytes in that second x 8 / 1 Gbps, from the packet headers
  (frame lengths as captured).
- **Residual capacity (assumptions R1-R4).** For a site uplink of nominal capacity C = 1 Gbps:
  available(t) = max(C x (1 - u(t)), C_min), C_min = 50 Mbps.
  R1 utilization is scale-free (a utilization fraction measured on one 1 Gbps link is applied to another 1 Gbps link);
  R2 cross-traffic is open-loop (it does not yield to OTTER's flows, and OTTER cannot take capacity from it);
  R3 the floor C_min keeps a link usable when u(t) > 0.95 (each clamped second is counted and reported);
  R4 the four site uplinks receive independent MAWI windows (no cross-site correlation).
- **Limitations stated with every result:** transit-link traffic composition and aggregation differ from edge-metro
  traffic; per-second averaging hides sub-second bursts; open-loop replay overstates rigidity; independence across
  sites may understate correlated congestion; capacity scaled to the testbed's 1 Gbps.
- **Windows and assignment:** 120 s windows; for each run the windows for A, B, C, D (egress from one direction,
  ingress from the other) are drawn without replacement by the seeded rule.

### 3.3 Selection (seeded, from trace statistics only)

- Mobility strata: tertiles of the median inter-move time of eligible segments (k = 1).
- Cross-traffic strata: tertiles of the coefficient of variation of available(t) over the windows a run assigns to the
  nodes on its path.
- 2 (mobility, cross-traffic) pairs per cell of the 3 x 3 strata = **18 segment pairs**, chosen with seed 20261017; the
  list (file hashes, offsets, k) is generated by the frozen script and committed before the first run. Segments are
  never replaced after a run.

## 4. Runs

| block | content | runs |
|---|---|---|
| P primary (network level, N = 1, k = 1) | 18 pairs x 4 policies x 3 reps | 216 |
| C contention (network level, N = 4, Scenario B v2 layout) | the 6 high-CV pairs x 4 policies x 3 | 72 |
| NC1 negative control: trace mobility, no cross-traffic | 6 mobility segments (2 per tertile) x {AM, ED} x 3 | 36 |
| NC2 negative control: cross-traffic only on A's ingress (unused by restoration) | 6 pairs x {AM, ED} x 3 | 36 |
| PC positive control: Experiment D scenario F's step at network level | {AM, ED} x 3 | 6 |
| G GPU confirmation | 3 pairs (one per CV tertile, mobility middle tertile) x 4 policies x 3 | 36 |
| S sensitivity k = 2 and k = 4 (section 6.3) | 18 pairs per k (re-derived by the same rule) x {AM, ED} x 3 | 216 |

Order: NC1, NC2, PC, then P, C, S, G. Policy order within a rep randomized (seed recorded).

## 5. Metrics (definitions)

- **T_r** (restoration time): final move's handoff request -> the Sink is complete and verified at the final owner
  (network level: the `restored` event; GPU: Sink verified). **Bind-ready** (GPU): first chunk with the Sink bound.
- **S** (source bytes): bytes sent by A for the session / Sink size. **B_tot**: all fragment bytes / Sink size.
- **Re-plans**: event-driven re-plan decisions (count; per minute of run).
- Per configuration: medians over valid reps. Per segment pair s: R_s = T_r(ED) / T_r(AM), dS_s = S(ED) - S(AM)
  (each from the medians).

## 6. Hypotheses, thresholds and decision rules

### 6.1 Primary (block P, k = 1)

- **T1 - benefit under measured variability.**
  Metric: R_s per pair. Decision: T1 is SUPPORTED iff (a) the median of R_s over the 6 pairs of the high-CV tertile is
  <= 0.90, and (b) in each of the three CV tertiles, the median of R_s is <= 1.05. Otherwise NOT SUPPORTED; NOT
  EVALUABLE if any tertile has fewer than 4 pairs with valid medians.
  Why these values: (b) 1.05 is a non-inferiority margin about the size of the measured run-to-run spread of
  restoration time in Experiment D's repeated scenario (bind-ready ranges of 15.04-15.82 s, about 5 %); (a) 0.90 asks
  for a benefit about twice that spread, the smallest effect that would not be attributable to run-to-run variation.
  Both are judgement-based choices informed by Experiment D, not derived from a model.
- **T2 - no spurious re-planning.**
  Metric: ED re-plans and |T_r(ED) - T_r(AM)| in NC1 and NC2. Decision: SUPPORTED iff in both controls the median ED
  re-plan count is 0 and the median over segments of |T_r(ED) - T_r(AM)| is <= 1.0 s. Thresholds inherited unchanged
  from Experiment D G7's no-change clause.
- **T3 - traffic cost.**
  Metric: dS_s per pair. Decision: SUPPORTED iff in each CV tertile the median of dS_s is <= 0.05 Sink. Why: 0.05 is
  about the run-to-run spread of OTTER's source bytes in Experiment D's repeated scenario (1.02-1.06 Sinks); a larger
  median difference is extra source traffic beyond measurement variation. For scale, Experiment D's incorrect-placement
  re-plan added 0.22 Sink.
- **T4 - harmful re-planning (event level).**
  Metric: the share of classified ED re-plans (section 9) that are *harmful*, over all P runs. Decision: SUPPORTED iff
  that share is <= 20 % and section 9's model-validation gate passes; NOT EVALUABLE if the gate fails or fewer than 20
  re-plans are classifiable. Why 20 %: no prior data on re-planning under trace variability exists; 20 % means at most
  one in five decisions that can be judged makes restoration worse, a tolerance chosen by judgement (a minority of
  decisions, small enough to be dominated by beneficial ones if T1 holds). The other classes are reported in full.
- **T5 - positive control.** Decision: SUPPORTED iff median T_r(ED) <= 0.5 x median T_r(AM) in block PC (as
  Experiment D G7's primary clause; network-level E results predict about 14.0 vs 53.8 s).
- **T6 - GPU carries over.** Decision: SUPPORTED iff for each of the 3 GPU pairs, sign(median bind-ready(ED) -
  median bind-ready(AM)) equals sign(network-level T_r(ED) - T_r(AM)) on the same pair, or both absolute differences
  are <= 1.0 s.

### 6.2 Contention (block C, N = 4)

The same T1 and T3 rules applied to the 6 high-CV pairs with N = 4 sessions, reported as T1-C and T3-C, separate from
the primary.

### 6.3 Sensitivity (block S, k = 2 and k = 4)

T1 (rule (a) on the k-specific high-CV tertile, rule (b) on all tertiles), T3 and the re-plan rate are reported per k
as sensitivity results, labelled as such. They never change a primary verdict.

### 6.4 Mandatory reporting (no threshold)

Every segment pair where ED increases median T_r or S relative to AM (values listed), every harmful re-plan
(section 9), M1 only and M1 + M2 on the same segments, the number of clamped seconds (R3), and every run with a
Sink-version event (section 10).

## 7. Validity

Experiment D's rules (`tools/eval/expD_validity.py`) plus: paced egress <= 1.05 x the time-averaged cap per node per
10 s window; NIC peaks <= 1.15 x the window's maximum cap; every scheduled cap change and move applied within 1 s of its
trace time; GPU 0 idle before each GPU run. Invalid runs are kept, listed with reasons and re-run (`--skip_done`);
none is deleted.

## 8. Analysis

Per configuration: medians over >= 3 valid reps (otherwise NOT EVALUABLE). Per tertile: the medians of R_s and dS_s,
with a seeded bootstrap 95 % interval (10,000 resamples of pairs) and a Wilcoxon signed-rank p-value, both descriptive;
the decision rules use the medians only. No outcome-dependent re-selection of segments, thresholds, policies or k.

## 9. Event-level counterfactual: procedure, validation, classification, cost aggregation

1. **State capture.** At every ED re-plan decision the harness logs the full state (fragments verified per node, in
   flight, assignment per provider, flow rates, caps) (`harness_plan.md` item 4).
2. **Two branches.** The fluid model (`tools/eval/restore_model.py`, state-injected) simulates from that state under
   the recorded remaining cap trace and move schedule: branch K (keep the pre-re-plan assignment; later triggers
   behave as in AM) and branch A (apply the re-plan; later triggers as in ED). dT = T_r(A) - T_r(K);
   dS = S(A) - S(K).
3. **Model validation (per run).** The model also simulates each executed run from its start (all logged decisions
   applied); e_run = |T_r,model - T_r,measured| / T_r,measured.
   **Gate:** the event-level analysis is valid only if the median e_run over P runs is <= 0.10 and the model's
   executed-branch error bound eps = the 90th percentile of |T_r,model - T_r,measured| (seconds) over P runs is fixed
   before any re-plan is classified. If the gate fails, T4 is NOT EVALUABLE and only policy-level results are reported.
4. **Classification (per re-plan).** If its run's own error |T_r,model - T_r,measured| > eps, the re-plan is
   *ambiguous* (model unreliable for that run). Otherwise: **beneficial** if dT < -eps; **harmful** if dT > +eps;
   **costly without benefit** if |dT| <= eps and dS > 0.05 Sink; **neutral** if |dT| <= eps and dS <= 0.05 Sink.
   "Classified" (T4's denominator) = beneficial + harmful + costly + neutral.
5. **Cost aggregation.** Reported over P: counts per class; for harmful re-plans the sum and median of dT (seconds) and
   dS (Sinks); for costly re-plans the sum and median of dS; both also per run and per hour of trace time; and the
   share of each run's restoration-time difference (R_s) attributable to classified re-plans (sum of dT of its re-plans
   divided by the measured T_r(ED) - T_r(AM), descriptive). A policy-level difference is never used to label a single
   re-plan.
6. **Cross-check.** In NC1 and NC2 every ED re-plan (expected none) is classified the same way; in PC the model's dT
   for the step re-plan is compared with the measured paired difference (descriptive).

## 10. Sink-version events (applicability study kept separate)

The frequency of Sink promotions during restoration windows is a separate applicability study
(`sink_stability_plan.md`) with its own report; it does not gate T1-T6. In Experiment T, the network-level runs carry
no generation (no promotions possible); the GPU block uses the dog workload. Any run with a Sink-version event is
flagged, excluded from T1-T6 as Experiment D's scope rule requires, and **listed** with its count, timing and affected
state volume in the results; none is dropped silently.

## 11. Scope

Placement disabled; no last-mile modelling; non-blocking metro core; open-loop residual capacity from MAWI (section
3.2); synthetic cell-to-site mapping (k); one Sink version per restoration; 1 Gbps emulated uplinks. Star/Line/Tree/
Butterfly are not part of this study.

## 12. Open items for the review before the freeze

1. The thresholds and their rationale (6.1), the gate (9.3: 10 %, P90), the classification margin (9.4: eps; 0.05
   Sink for costly), C_min = 50 Mbps (3.2).
2. Block sizes (18 pairs; S adds 216 runs; total 582 network runs (P 216, C 72, NC1 36, NC2 36, PC 6, S 216) + 36 GPU
   runs; roughly 16 h network level at ~1.5 min per run + ~2.5 h GPU).
3. Download approvals: Lumos5G (IEEE DataPort login by the user), MAWI pcaps (large), optionally the UCC 5G archive.
