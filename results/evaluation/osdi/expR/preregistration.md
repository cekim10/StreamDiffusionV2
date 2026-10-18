# Experiment R - Repeated mobility: preregistration (FINAL; frozen, record `../followup_prereg_freeze.md`)

Common rules (validity, re-runs, censoring, aggregation, metadata): `../followup_common.md`. Experiment D is prior
evidence only. History: drafts v1-v2 (c765876, 4ae375b).

## 1. Question

Over which ratio of restoration time to dwell time (rho) does progress preservation (M2) remove redundant source
traffic and discarded work, and does it shorten restoration under source contention (as a system-level effect)? R does
not estimate how often rho > 1 occurs in deployments.

## 2. Prior evidence (recorded predictions only)

| source | observation |
|---|---|
| ExpD G3 (rho 2 / 4, c = 0) | B_source M1 + M2 1.03 / 1.02 vs M1 only 2.01 / 1.52; discarded 0.049 / 0.036 vs 1.014 / 0.515; bind-ready 15.11 vs 15.52 s, 15.66 vs 15.17 s |
| ExpD G6 (rho 2, three background sessions) | GPU-session bind-ready M1 + M2 43.09 s, OTTER event-driven 42.82 s vs M1 only 57.07 s |
| node code (2026-10-18) | a node keeps the received Sink after bind (a bound owner can forward); M1 only drops it at the move (`SINK_DROP`) |

## 3. Design and matrix

- Path A -> B -> C -> D (three moves; the first at source chunk M = 30, dog's trigger is not a loop cut), dog workload,
  seed 0, k = 2, 1 Gbps, warm destinations; `post_chunks` 300, `max_run_s` 600.
- **rho** in {0.5, 1, 2, 4, 8}; T_m = 14.05 / rho = 28.10, 14.05, 7.025, 3.5125, 1.75625 s between moves (schedule
  parameter; the effective ratio = final-owner restoration time / T_m is reported).
- **Contention c** in {0, 3}: c = 3 adds three network-level restoration sessions from A (`tools/eval/hybrid_net.py`,
  Scenario B v2 layout: they start at the GPU session's first move and move on its T_m schedule). **Policy coupling:**
  the background sessions run the policy mapped from the GPU session's (`NET_POLICY`: restart -> restart, split ->
  reuse_fixed, reuse_dyn -> reuse_dyn); R-H3(b) is therefore a **system-level** comparison (all sessions on M1 only vs
  all on M1 + M2), not an isolated per-session M2 effect.
- **Policies:** M1 only (`restart`), M1 + M2 (`split`), OTTER event-driven (`reuse_dyn`; frozen thresholds; no
  placement). 3 reps: **5 x 2 x 3 x 3 = 90 runs**.

## 4. Metrics (all bytes of the GPU session, in Sinks)

- (a) **total source bytes** B_source,total = bytes sent by A for the GPU session / Sink size;
- (b) **redundant source bytes** R = B_source,total - 1 (A's bytes beyond one Sink; all 412 fragments originate at A and
  no placement is used, so B_source,total >= 1 by construction);
- (c) **redundant-byte reduction** = 1 - R(M1 + M2) / R(M1 only) (in %), defined when R(M1 only) >= 0.10;
- **discarded bytes** (Phase 1 definition (a)); note fixed in advance: at rho <= 1 an abandoned owner that already bound
  the Sink is not counted as discarded, so at rho <= 1 M2's effect appears in (a)-(c) only;
- **bind-ready** after the final move (s), reported separately from (a)-(c) and never combined with them;
- also: B_fwd, aggregate network bytes, verified progress retained / reused, re-plans (OTTER), version events per policy.
- **Contention exposure** (c = 3, per run): shared bottleneck identity = **A's egress** (the link every background
  session's source flows and the GPU session's source flows traverse); GPU restoration interval I = [final move, Sink
  verified at the final owner] (if censored: [final move, end of run]); recorded: mean number of active background
  source flows on A's egress over I, background bytes sent by A during I, the fraction of I covered by >= 1 active
  background flow from A. A run is **exposure-valid** if (1) at least one background flow from A is active during I,
  (2) background flows from A cover >= 25 % of I (a preregistered engineering judgment, not an empirically validated
  contention threshold), and (3) background bytes from A during the covered part of I are > 0. A c = 3 cell is
  exposure-valid for a policy if a majority of its valid reps are.

## 5. Analytic model (basis for the manipulation check; stated before data)

Without contention each abandoned owner receives min(1, 1/rho) Sink before it is left; M1 only re-sends from A to every
new owner: R(M1 only) = 2 min(1, 1/rho) (rho 0.5: 2.0; 1: ~2.0; 2: 1.0; 4: 0.5; 8: 0.25); discarded(M1 only) = 2/rho for
rho > 1, ~0 at rho < 1. M1 + M2: R ~ 0, discarded ~ 0. Hypotheses use each cell's own M1-only measurement.

## 6. Version events (applicability)

At rho <= 1 an intermediate owner binds before it is left and generates with adaptive refresh on; a promotion there is
an owner-side version event (common section 3): the run is **inapplicable** to M2 claims, kept, and listed per policy
with its events. Version events are recorded for every policy and run. A configuration whose valid reps are all
inapplicable is NOT EVALUABLE (version event) for every hypothesis comparing it; the number of inapplicable runs per
policy and cell is reported, and the dog W1 result (as-fed P_w) is shown next to it. Refresh behaviour is not changed.

## 7. Confirmatory hypotheses (medians over 3 valid reps; common section 3 for censoring)

| item | R-H1 redundant source traffic | R-H2 discarded work | R-H3(a) latency, no contention | R-H3(b) latency under contention (system level) |
|---|---|---|---|---|
| 1 question | does M2 remove the source bytes M1 only re-sends? | does M2 avoid discarded deliveries? | does M2 leave latency unchanged without contention? | does the M2 system restore faster when A's egress is contended? |
| 2 unit | rho x c cell (10) | rho x c cell (10) | rho cell at c = 0 (5) | rho in {0.5, 1, 2} at c = 3 (3) |
| 3 independent variable | policy (M1 only vs M1 + M2) | policy | policy | policy (system) |
| 4 primary metric | B_source,total (a), R (b), reduction (c) | discarded bytes (Sinks) | bind-ready after the final move (s) | bind-ready after the final move (s) |
| 5 success | B_source,total(M1 + M2) <= 1.10 **and** reduction >= 75 % | discarded(M1 + M2) <= 0.10 | abs(bind(M1 + M2) - bind(M1 only)) <= 1.0 s | bind(M1 + M2) <= bind(M1 only) - 1.0 s |
| 6 failure | either clause violated | > 0.10 | > 1.0 s | not met |
| 7 NOT EVALUABLE | R(M1 only) < 0.10 (nothing to remove); < 3 valid applicable reps of either policy | < 3 valid applicable reps | as R-H2; censoring per common section 3 | as R-H3(a); or the cell not exposure-valid for either policy |
| 8 aggregation | medians of B_source,total per policy; R and reduction from the medians | median per policy | medians | medians |
| 9 repetitions | 3 per policy and cell | 3 | 3 | 3 |
| 10 artifacts | run dirs, `fragments.csv` (orchestrator and nodes), `r_table.csv`, aggregate JSON / MD | same | same | same + exposure record per run |

Origins: 1.10 (G3(a)), 0.10 (G3(b)), 1.0 s (G3(c)) were frozen before ExpD ran; 75 % and 25 % are judgment values.
Recorded predictions: R-H1, R-H2, R-H3(a) supported at c = 0; R-H3(b) supported at rho 2 (G6 prior), unknown at 0.5, 1.
**Manipulation check (baseline, not an OTTER claim):** at c = 0, rho in {2, 4, 8}: discarded(M1 only) >= 0.75 x 2/rho;
reported as MET / NOT MET. rho 4 and 8 at c = 3 latency is descriptive. OTTER event-driven is reported next to M1 + M2 in
every cell (bytes, discarded, bind-ready, re-plans) and is not part of R-H1-R-H3.

## 8. Descriptive analyses

Operating-region figure (R and discarded bytes vs rho per policy and c, analytic model overlaid; bind-ready in a separate
panel); verified progress retained / reused; effective rho; exposure metrics for every c = 3 run; version events per
policy and cell.
