# Experiment N - Network adaptation: preregistration DRAFT v1 (2026-10-18; not frozen; nothing implemented or run)

Common rules, testbed, definitions, implementation items and cost: `../followup_common.md`. Experiment D is prior
evidence only (common rule 1). The M3 implementation and every `dyn_*` threshold stay exactly as frozen (E-pilot v2:
`dyn_period` 0.5 s, `dyn_window` 2.0 s, `dyn_warmup` 2.0 s, `dyn_eps` 2.0, `dyn_rel` 0.10, `dyn_ctrl` 0.3).

## 1. Question

When does M3's event-driven re-planning shorten restoration, when does it change nothing, and when does it cost
(unnecessary re-plans, extra source traffic)? Experiment D found both sides: a large gain under mid-restoration holder
degradation (G7) and an unnecessary re-plan under incorrect placement with no network change (G5, not supported). N
crosses placement correctness with network degradation, with **no degradation** as a primary condition, so that both
results become points of one map. N does not claim that M3 improves performance in general (common rule 4).

## 2. Prior evidence (predictions only)

| source | observation |
|---|---|
| ExpD G5 + `../expD/g5_shakedown_observation.md` | incorrect placement (A -> C, x = 0.716 at B), no network change: OTTER event-driven re-plans 2.3 s after the move, moving 89 fragments from B to A; B_source,total 1.23 vs 1.01 for M1 + M2 + top-1; bind-ready unchanged (ingress-bound). Cause: measured rates on a shared destination ingress are assumed to persist |
| ExpD G7 (scenario F) | C's egress -> 62.5 Mbps when D holds 50 %: OTTER event-driven 15.80 s vs at moves 51.58 s, 2 re-plans, 0 duplicates; no re-plan in B (rho 2, 4) or G |
| ExpD G4 | correct placement: Full OTTER bind-ready 4.94 s vs 15.42 s without placement (re-plan counts of scenario C not re-read for this draft) |

## 3. Design (primary matrix)

Single move with the placement window of ExpD scenarios C/D (L = 10 s, b = 1 Sink, p = 0.6 / 0.3 / 0.1 for B / C / D;
the same move schedule for every policy), dog workload, k = 2, 1 Gbps.

**Factor P - placement:** `none` (A -> B, no prediction), `correct` (A -> B, top-1 = B), `incorrect` (A -> C, top-1 = B).

**Factor D - degradation** (one link role per cell; magnitude 62.5 Mbps = 1/16 of nominal, the value of ExpD scenario F
fixed before ExpD ran; onset at the move + 4 s = after `dyn_warmup` + `dyn_window`, so the event-driven rule has one full
measurement window before the change; persistent to the end of the run):
- `0` - no change (**primary condition**);
- `src` - the source A's egress;
- `hold` - the misplaced holder B's egress (exists only under `incorrect`);
- `in` - the destination's ingress.

Cells: none x {0, src, in}; correct x {0, src, in}; incorrect x {0, src, hold, in} = **10 cells**.

**Policies** (each with the cell's placement): OTTER at moves (`reuse_aware_in`), OTTER event-driven (`reuse_dyn`) - the
M3 re-planning comparison - and M1 + M2 (`split`) as the reference without bottleneck-aware assignment. 3 reps:
10 x 3 x 3 = **90 runs**.

**Cell classes (fixed now from the data placement, not from outcomes):**
- *no change*: D = 0 (3 cells);
- *alternative available*: the degraded provider's remaining fragments are also held by an undegraded provider:
  incorrect x hold (the source A holds every fragment) (1 cell);
- *no alternative*: the degradation hits a provider whose fragments exist nowhere else, or the destination's ingress:
  none x src, none x in, correct x src, correct x in, incorrect x src, incorrect x in (6 cells).

## 4. Metrics

- **Unnecessary re-plans:** in *no change* cells every re-plan is unnecessary by definition (no network change
  occurred); counted per run.
- **Restoration latency:** Sink bind-ready after the move; Sink verified time.
- **Source traffic:** B_pre, B_post, B_source,total; also B_fwd, aggregate network bytes, x (verified at the placement
  target at the trigger).
- Per re-plan record (descriptive): time after the move and after the degradation, the logged ETA before / after,
  fragments moved and their direction (towards or away from the source), drained bytes, duplicates.
- **Cell effect of event-driven re-planning** (ED vs at moves, medians): *beneficial* if bind-ready(ED) <=
  bind-ready(at moves) - 1.0 s; *harmful* if bind-ready(ED) >= bind-ready(at moves) + 1.0 s or B_source(ED) >=
  B_source(at moves) + 0.05; otherwise *neutral* (a cell can be beneficial in latency and still flagged for traffic;
  both are reported).

## 5. Confirmatory hypotheses (medians over 3 valid reps; decision rules fixed at the freeze)

- **N-H1 (no change, no action)** - each of the three *no change* cells separately: OTTER event-driven makes 0 re-plans
  (median), |bind-ready(ED) - bind-ready(at moves)| <= 1.0 s, and B_source(ED) <= B_source(at moves) + 0.02.
  Origins: 0 re-plans and the 1.0 s band are G7's no-change clause (frozen before ExpD); 0.02 Sink is G5(b)'s slack over
  1.00 (frozen before ExpD). **Recorded predictions:** none - supported; correct - supported; **incorrect - NOT
  supported** (the G5 mechanism: a shared destination ingress read as a persistent provider rate). The hypothesis states
  the design intent; the prediction records the known failure; neither is adjusted to the other.
- **N-H2 (benefit where an alternative exists)** - incorrect x hold: bind-ready(ED) <= 0.5 x bind-ready(at moves), with
  <= 2 re-plans and 0 duplicates. Origin: G7's primary bound (frozen before ExpD). Recorded prediction: supported
  (at moves keeps ~0.6 Sink on a 62.5 Mbps holder, > 100 s; ED can move it to the source).
- **N-H3 (no harm where no alternative exists)** - each of the six *no alternative* cells: bind-ready(ED) <=
  bind-ready(at moves) + 1.0 s **and** B_source(ED) <= B_source(at moves) + 0.05. Origin: the 1.0 s band as above; 0.05
  Sink is a judgment value (~20 fragments). Recorded prediction: uncertain; ingress degradation (`in`) lowers every
  provider's measured rate at once and may trigger re-plans that change nothing.

Reporting rule: N-H1 to N-H3 are reported per cell (10 verdicts), never as one pooled "M3 works" verdict. The paper's
M3 statements are limited to the classes whose hypothesis is supported, and every *harmful* cell is reported with its
traffic and latency cost.

## 6. Descriptive analyses

- The adaptation map: per cell, bind-ready and B_source for the three policies, the cell effect class and the re-plan
  counts of every rep.
- Per re-plan table (section 4) for every ED run; how many re-plans moved fragments towards the source.
- M1 + M2 vs both OTTER variants in each cell (what bottleneck-aware assignment adds without event-driven re-planning).

## 7. Exploratory sensitivity sweeps (separate; after the primary matrix; never change a primary verdict)

- Magnitude: 500, 250, 125 Mbps in incorrect x hold and in incorrect x in.
- Onset: move + 1 s (inside the warm-up) and move + 8 s.
- Duration: transient degradations of 2 s and 8 s (a second cap event restores 1 Gbps).
- Repeated mobility: scenario F's layout (rho 2, C's egress degraded when D holds 50 %) at 250 / 125 / 62.5 Mbps.
- 2 reps per configuration, OTTER at moves and OTTER event-driven only; reported as a separate table labelled
  exploratory. The `dyn_*` thresholds are not varied anywhere in N.

## 8. Validity

ExpD run-validity rules (`../followup_common.md` section 2). The NIC-peak and paced-egress checks use the degraded cap
for the degraded link after the change. A run whose cap change did not fire (no `cap_change` event) is invalid.

## 9. What the outcomes mean for the paper

- N-H2 supported: M3 recovers latency when a degraded provider's data are available elsewhere (the G7 class).
- N-H1 per placement: whether M3 is free when nothing changes; the expected failure under incorrect placement is reported
  as a limitation of the ETA model, with its cost (traffic, no latency change), not hidden.
- N-H3: whether M3 is safe when it cannot help; any harmful cell is reported with its cost.
- A summary sentence of the form "M3 helps in class X, is neutral in Y, costs Z in W" is the only general M3 claim.
