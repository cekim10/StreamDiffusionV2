# Experiment N - Network adaptation: preregistration (FINAL; frozen, record `../followup_prereg_freeze.md`)

Common rules (validity, re-runs, censoring, aggregation, metadata): `../followup_common.md`. Experiment D is prior
evidence only. The M3 implementation and every threshold stay as frozen (E-pilot v2: `dyn_period` 0.5 s, `dyn_window`
2.0 s, `dyn_warmup` 2.0 s, `dyn_eps` 2.0, `dyn_rel` 0.10, `dyn_ctrl` 0.3). History: drafts v1-v2 (c765876, 4ae375b).

## 1. Question

When does M3's event-driven re-planning shorten restoration, change nothing, or cost (unnecessary re-plans, extra
source traffic)? N maps the known ExpD outcomes (G7 supported; G5 not supported, a false-positive re-plan) onto one
placement x degradation matrix. N makes no claim that M3 improves performance in general; the known G5 failure is
preserved and M3 is not tuned.

## 2. Prior evidence (recorded predictions only)

| source | observation |
|---|---|
| ExpD G5 (`../expD/g5_shakedown_observation.md`) | incorrect placement, no network change: event-driven re-plans 2.3 s after the move, moving 89 fragments from B to A; B_source,total 1.23; bind-ready unchanged |
| ExpD G7 (scenario F) | holder egress -> 62.5 Mbps mid-restoration: event-driven 15.80 s vs at moves 51.58 s; 2 re-plans; 0 duplicates |
| ExpD G4 | correct placement: Full OTTER bind-ready 4.94 s vs 15.42 s without placement |

## 3. Design and matrix

- Single move with the placement window of ExpD scenarios C / D (L = 10 s, b = 1 Sink, p = 0.6 / 0.3 / 0.1 for B / C /
  D; same move schedule for every policy), dog workload, seed 0, k = 2, 1 Gbps, trigger M = 30; `post_chunks` 400,
  `max_run_s` 900.
- **Placement P:** `none` (A -> B, placement policy none), `correct` (A -> B, top-1 = B), `incorrect` (A -> C, top-1 = B).
- **Degradation D:** `0` none; `src` = A's egress; `hold` = the misplaced holder B's egress; `in` = the destination's
  ingress. Magnitude **62.5 Mbps** (ExpD F's value), persistent to the end of the run, one link per cell.
- **The 10 declared cells:** (1) none x 0, (2) none x src, (3) none x in, (4) correct x 0, (5) correct x src,
  (6) correct x in, (7) incorrect x 0, (8) incorrect x src, (9) incorrect x hold, (10) incorrect x in.
  **Not included (2 of the 3 x 4 product):** none x hold (no placement, so there is no holder whose egress could be
  degraded) and correct x hold (the placement target is the destination itself, whose egress carries no restoration
  traffic: the condition would equal correct x 0).
- **Policies (each with the cell's placement):** OTTER at moves (`reuse_aware_in`), OTTER event-driven (`reuse_dyn`) - the
  M3 re-planning comparison - and M1 + M2 (`split`) as the reference without bottleneck-aware assignment. 3 reps:
  **10 x 3 x 3 = 90 runs**.
- **Progress-aligned degradation trigger** (a network intervention aligned to restoration progress, not a simultaneous
  wall-clock failure): at the move, the set S of fragments the destination has **not** verified is frozen; the cap
  change fires once, when the destination has verified ceil(|S| / 2) fragments of S (fragment count, not bytes). It is
  implemented in the orchestrator's network emulation (cap events); the planners are not told and M3 receives no signal
  from it. Recorded per run: the trigger time, |S|, verified fragments of S at the trigger, time from the trigger to Sink
  verified, and **reaction feasibility** = (Sink verified - trigger time) >= `dyn_window` + `dyn_period` (2.5 s; the
  shortest time for the rule to observe a full window after the change and run one check). Runs are never excluded for
  finishing before M3 could react.
- **Provider availability (from data placement, independent of M3's choices):** at the trigger, the count of fragments
  still missing at the destination that are held, verified, by at least one provider other than the degraded one.
  Cell classes are fixed from the placement: *no change* = cells 1, 4, 7; *alternative available* = cell 9 (the source
  A holds every fragment the degraded holder B still has to send); *no alternative* = cells 2, 3, 5, 6, 8, 10 (the
  degraded provider's remaining fragments exist nowhere else, or the destination's ingress is degraded). The per-run
  availability count is reported for every cell.

## 4. Metrics

Sink bind-ready and Sink verified after the move (s; censored per common section 3); re-plans (count, times after the
move and after the trigger, ETA before / after, fragments moved and their direction, drained bytes); duplicates;
B_pre, B_post, B_source,total, B_fwd, aggregate network bytes (Sinks); the trigger record (section 3); timeout status and
last observed progress. **False-positive re-plan** = a re-plan in a *no change* cell (no network change occurred): an
explicit diagnostic outcome, counted per run. **Cell effect of event-driven re-planning** (ED vs at moves, medians):
beneficial if bind(ED) <= bind(at moves) - 1.0 s; harmful if bind(ED) >= bind(at moves) + 1.0 s or B_source(ED) >=
B_source(at moves) + 0.05; else neutral (descriptive).

## 5. Confirmatory hypotheses (medians over 3 valid reps; common section 3 for censoring)

| item | N-H1 no change, no action | N-H2 benefit where an alternative exists | N-H3 no harm where no alternative exists |
|---|---|---|---|
| 1 question | does event-driven re-planning stay idle and free when nothing changes? | does it shorten restoration when the degraded provider's data are available elsewhere? | does it avoid measurable overhead when no provider can help? |
| 2 unit | cells 1, 4, 7 (separate verdicts) | cell 9 | cells 2, 3, 5, 6, 8, 10 (separate verdicts) |
| 3 independent variable | ED vs at moves | ED vs at moves | ED vs at moves |
| 4 primary metric | re-plans (ED); bind-ready; B_source,total | bind-ready; re-plans; duplicates | bind-ready; B_source,total; re-plans reported |
| 5 success | re-plans(ED) = 0 **and** abs(bind(ED) - bind(at moves)) <= 1.0 s **and** B_source(ED) <= B_source(at moves) + 0.02 | bind(ED) <= 0.5 x bind(at moves) **and** re-plans(ED) <= 2 **and** duplicates = 0 | bind(ED) <= bind(at moves) + 1.0 s **and** B_source(ED) <= B_source(at moves) + 0.05 |
| 6 failure | any clause violated (a false-positive re-plan fails clause 1) | any clause violated | any clause violated |
| 7 NOT EVALUABLE | < 3 valid reps of either policy; undecidable under censoring | as N-H1; a cell whose trigger did not fire in a majority of reps (harness failure) | as N-H2 |
| 8 aggregation | medians per policy | medians per policy | medians per policy |
| 9 repetitions | 3 per policy and cell | 3 | 3 |
| 10 artifacts | run dirs, `events.csv` (replan, cap_change), `fragments.csv`, `n_table.csv`, aggregate JSON / MD | same + trigger record | same + availability and reaction feasibility |

Origins: 0 re-plans and the 1.0 s band (G7's no-change clause), 0.02 Sink (G5(b)'s slack), 0.5 x and <= 2 re-plans (G7's
primary bound) were frozen before ExpD ran; 0.05 Sink is a judgment value. **Recorded predictions:** N-H1 supported in
cells 1 and 4, **NOT SUPPORTED in cell 7** (the G5 mechanism; preserved, M3 not tuned); N-H2 supported; N-H3 uncertain.
Reporting: 10 verdicts per cell, never pooled into one "M3 works" verdict; the paper's M3 statements are limited to the
classes whose hypothesis is supported, and every harmful cell is reported with its cost. For N-H3, "measurable overhead"
= violating its success clauses; latency, re-plans and source bytes are reported for every no-alternative cell.

## 6. Validity

Common section 3. NIC-peak and paced-egress checks use the cap in force on each link at each time. A run in which the
trigger did not fire although the destination verified ceil(|S| / 2) fragments of S is invalid (harness failure) and
re-run; a run that times out is kept and censored.
