# Experiment V - M3-v2 holdout evaluation: preregistration (FROZEN 2026-10-19 with M3-v2; record `../m3v2_freeze.md`; nothing run)

Mechanism-motivated follow-up of Experiment N (`../followup_common.md` rules apply: validity, re-runs, censoring,
order-statistic medians, NOT EVALUABLE). **Development data (never evidence for v2):** Experiment N cells 1-10, ExpD
G5 / G7, the loopback and GPU regressions of `m3v2_design.md`. Every condition below is new: no run with these
magnitudes, onsets or placements exists for any policy.

## 1. Question

Does M3-v2 keep the benefit of event-driven re-planning where an alternative provider exists, without the false-positive
re-plans, partial moves and oscillation of M3-v1, on network conditions it was not developed on?

## 2. Design (single move with the placement window of N: L = 10 s, b = 1 Sink; dog seed 0, k = 2, 1 Gbps nominal;
trigger M = 30; `post_chunks` 400, `max_run_s` 900)

**Placements:** `incorrect` (A -> C, top-1 = B: one misplaced holder, as N) and **`proportional`** (A -> C; the budget
spread over B, C, D in proportion to p = 0.6 / 0.3 / 0.1 (`prepos_alloc`): with L = 10 s at 1 Gbps the source can place
0.72 Sink, so B receives 0.43, the true destination C 0.22 and D 0.07 Sink before the move; after the move C lacks
0.78 Sink, held by B (0.43), D (0.07) and only by A (0.28): three providers on C's ingress - untested).

**Degradations** (progress-aligned trigger: fires once when the destination has verified a fraction `q` of the
fragments it lacked at the move; magnitude in Mbps; persistent):

| id | placement | degraded link | Mbps | onset q | class (from the data placement) |
|---|---|---|---|---|---|
| V1 | proportional | none | - | - | no change (two holders + source on one ingress: the false-positive case with three providers) |
| V2 | proportional | holder B egress | 125 | 0.25 | alternative available (A and partly D hold B's fragments) |
| V3 | proportional | destination C ingress | 250 | 0.75 | no alternative |
| V4 | incorrect | holder B egress | 250 | 0.25 | alternative available |
| V5 | incorrect | holder B egress | 31.25 | 0.75 | alternative available (severe, late) |
| V6 | incorrect | destination C ingress | 125 | 0.25 | no alternative |
| V7 | incorrect | source A egress | 250 | 0.75 | no alternative (A's fragments are held only by A) |
| V8 | none (A -> B) | destination B ingress | 31.25 | 0.25 | no alternative (single provider, severe) |

**Policies:** OTTER at moves (`reuse_aware_in`), M1 + M2 (`split`), M3-v1 (`reuse_dyn`), **M3-v2 (`reuse_dyn2`)**, each
with the cell's placement; 3 reps: 8 x 4 x 3 = **96 runs** (~7 h: the 31.25 Mbps cells restore ~0.4 Sink through the
degraded link, ~110 s).

Primary metrics (medians over valid reps; censoring per common section 3): bind-ready after the move; B_source,total;
re-plan count; discarded bytes. Also B_fwd, aggregate network bytes, per-re-plan records (incl. v2's probe flag,
I_est, c_est), trigger record, reaction feasibility.

## 3. Confirmatory hypotheses (thresholds = the frozen N thresholds, origins as there; decision rules fixed at the freeze)

| | V-H1 no change, no action | V-H2 benefit where an alternative exists | V-H3 no harm where no alternative exists | V-H4 v2 not worse than v1 |
|---|---|---|---|---|
| unit | V1 | V2, V4, V5 (separate verdicts) | V3, V6, V7, V8 (separate verdicts) | every cell (separate verdicts) |
| success | re-plans(v2) = 0 (median), abs(bind(v2) - bind(at moves)) <= 1.0 s, B_source(v2) <= B_source(at moves) + 0.02 | bind(v2) <= 0.5 x bind(at moves), re-plans(v2) <= 2, duplicates = 0 | bind(v2) <= bind(at moves) + 1.0 s and B_source(v2) <= B_source(at moves) + 0.05 | bind(v2) <= bind(v1) + 1.0 s and B_source(v2) <= B_source(v1) + 0.05 and re-plans(v2) <= re-plans(v1) |
| failure | any clause violated | any clause violated (a probe counts as a re-plan) | any clause violated | any clause violated |
| NOT EVALUABLE | < 3 valid reps; undecidable under censoring | as V-H1; trigger not fired in >= 2 reps | as V-H2 | as V-H1 |

Recorded predictions (from the design and the development regression, not from holdout data): V-H1 supported; V-H2
supported in V4 and V5 (one probe + one move = 2 re-plans), uncertain in V2 (three providers); V-H3 uncertain in V3 /
V6 (ingress drop with a probe: the probe is a re-plan and may cost up to 4 fragments = 0.01 Sink, inside the 0.05
bound) and in V8 (single provider from the start: the probe adds the source on an ingress-limited link); **V-H4 expected
NOT SUPPORTED in holder-degraded cells (V2, V4, V5)**: in the development cell 9 v2 bound 5.4 s after v1 because v1's
false-positive re-plan had moved fragments to the source before the degradation (`m3v2_design.md` section 6); V-H4 is
kept as written and judged as such.

M3-v1's own verdicts on the same cells are reported with the same rules (descriptive for v1: its development is
closed). No universal M3 claim: the paper's statement is per class, as for N.

## 4. Implementation needed before the freeze

- Trigger onset fraction: `--cap_events frac<q>:<node>:<dir>=<mbps>` (generalizes `half`; emulation only; planners not told).
- Placement `proportional` with a true destination C: already supported by `--prepos` / `--pp_configs` (`prepos_alloc`);
  loopback-tested with two holders.
- Driver: `run_wrn.py v` (cells V1-V8), aggregator `aggregate_wrn.py` section V.

## 5. Freeze and order

Freeze M3-v2 (algorithm, parameters: probe 4 fragments, min 8 fragments per span, 2-fragment margin, v1's thresholds
unchanged) and this plan in one commit after the GPU regression on N cells 7-10 passes its pre-written conditions
(`m3v2_design.md` section 6); then run V1-V8 in order; aggregate; report with every negative result.
