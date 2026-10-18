# W / R / N preregistration freeze record

- **Freeze commit:** `4001882b08306024b07feafcbc223c8dd46a9c60` (pushed to `phase0a-quality-elastic`)
- **Freeze time:** 2026-10-18T23:27Z
- **Status:** W, R and N are mechanism-motivated follow-up evaluations of OTTER. Frozen texts: `expW/preregistration.md`,
  `expR/preregistration.md`, `expN/preregistration.md`, `followup_common.md`, `followup_shakedown_conditions.md`. A
  later correction is a dated amendment appended below the affected text; frozen text is never edited.
- **No W / R / N GPU performance result was used to set any threshold, matrix entry or rule:** no W / R / N GPU run
  existed at the freeze. The only data seen were Experiment D's (prior evidence), the LOVEU input properties (motion
  scores, frame counts) and the loop arithmetic. Experiment D (81bb628), Experiment T (2a781f8d, on hold) and the M1 / M2 /
  M3 implementations are unchanged.

## File hashes at the freeze (SHA-256)

| file | SHA-256 |
|---|---|
| followup_common.md | d34052feb620534c1f8a8fc610bb80d292ae48be5d47a3ee45bc86a783653b79 |
| followup_shakedown_conditions.md | ebcec767429e97c56e3225926b92314505cdb8ec4eb7099274fbb6445043a2b2 |
| expW/preregistration.md | fb837c700f165e2a90813c2e90f8cd06f63186a733f16635357bdb001debfa05 |
| expR/preregistration.md | b4fd0f88e75174e41ced0257b00c73025ab07a2da356219ccfb717b0892a1278 |
| expN/preregistration.md | ed4770fb645799fb5f6cfde4dbac93b46c687452e55bbed1e7a493343f96909c |
| expW/loveu_population.csv (dataset manifest) | a4a2968061b3faf3b96ad45b0d9478323411aff878e69e32a4a6f74e4c807d76 |
| expW/loveu_selection.csv (workload selection) | d7f0098b679429a026b3653064c429315e4f324e7d9e6ef0a6750e417d58a71b |
| expW/loveu_motion_scores.csv | ae0ccdf4e09da3a3e4b5e32be35df212c697d620500e53eaeff5ee8f293986c3 |
| expW/loop_audit.json | c6bf859f8dde583d6ef6a49867b958b7e4fc1ee87a73f536228a1ef89e8a86dc |
| tools/eval/expw_loveu.py | 17b929d67ae47750c2b7c6c3688d9ab49db7a39724586034069c48d458cd744a |
| tools/eval/expw_loop_audit.py | 960c9ba7858f5e0dd7977665480df181ec13851bcc93c57dce8b9738589d7ba1 |
| LOVEU archive `loveu-tgve-2023.zip` (279,628,311 B; not in the repository) | ed2e7166c566c54d92bab1b5c0bae580ac9a3e768b88024e55181413321a0503 |

Per-video mp4 SHA-256 values are in `expW/loveu_population.csv`.

## Experiment matrices

| exp | matrix | runs |
|---|---|---|
| W1 | 20 workloads (dog, bird, boxing, train + 16 LOVEU of `loveu_selection.csv`) x seeds {0, 1}; 330 calls, no migration | 40 |
| W2 | same 40 units x {OTTER event-driven, Cold restart}; A -> B at M = 34; horizon calls 34-133; 1 Gbps | 80 |
| R | rho {0.5, 1, 2, 4, 8} (T_m = 14.05 / rho) x contention {0, 3} x {M1 only, M1 + M2, OTTER event-driven} x 3 reps; A -> B -> C -> D, dog seed 0, M = 30 | 90 |
| N | cells (1) none x 0, (2) none x src, (3) none x in, (4) correct x 0, (5) correct x src, (6) correct x in, (7) incorrect x 0, (8) incorrect x src, (9) incorrect x hold, (10) incorrect x in; x {OTTER at moves, OTTER event-driven, M1 + M2} x 3 reps; 62.5 Mbps, progress-aligned trigger; dog seed 0, M = 30 | 90 |
| W-AR (exploratory) | 4 LOVEU videos (positions 2, 8 of the 32-frame and 1, 3 of the 128-frame group by motion), seed 0, center-band crop; W1 + 2 W2 policies | 12 |
| total | | **312** |

Timeouts: W2 `post_chunks` 130 / `max_run_s` 600; R 300 / 600; N 400 / 900. Censoring, re-runs, aggregation and
NOT EVALUABLE rules: `followup_common.md` section 3.

## Hypothesis thresholds

| hypothesis | success threshold |
|---|---|
| W-H1 | every workload's TTFO (mean of two seeds) <= 1.0 s and spread of the 20 values <= 0.25 x median service time |
| W-H2 | rejoin (single crossing >= 35 dB after bind, by call 133) in >= 80 % of all 40 units; secondaries S1 (no RVC), S2 (no cut-RVC) |
| W-H3 | Cold restart reaches 35 dB in <= 20 % of the units in which OTTER rejoins |
| W1 scope rule | single-version stable at w if P_w <= 0.05 (as fed and within-clip) |
| R-H1 | B_source,total(M1 + M2) <= 1.10 and redundant-byte reduction 1 - R(M1 + M2) / R(M1 only) >= 75 %; NOT EVALUABLE if R(M1 only) < 0.10 |
| R-H2 | discarded(M1 + M2) <= 0.10 Sink |
| R-H3(a) | abs(bind(M1 + M2) - bind(M1 only)) <= 1.0 s at c = 0 |
| R-H3(b) | bind(M1 + M2) <= bind(M1 only) - 1.0 s at c = 3, rho {0.5, 1, 2}; exposure-valid cells only (>= 1 background flow on A's egress, >= 25 % coverage of the GPU restoration interval, > 0 background bytes) |
| R manipulation check | discarded(M1 only) >= 0.75 x 2 / rho at c = 0, rho {2, 4, 8} |
| N-H1 | cells 1, 4, 7: re-plans(ED) = 0, abs(bind(ED) - bind(at moves)) <= 1.0 s, B_source(ED) <= B_source(at moves) + 0.02 |
| N-H2 | cell 9: bind(ED) <= 0.5 x bind(at moves), re-plans <= 2, duplicates = 0 |
| N-H3 | cells 2, 3, 5, 6, 8, 10: bind(ED) <= bind(at moves) + 1.0 s and B_source(ED) <= B_source(at moves) + 0.05 |

Recorded predictions include **N-H1 NOT SUPPORTED in cell 7** (the ExpD G5 mechanism; M3 not tuned).

## Final consistency audit (one bounded pass, 2026-10-18)

Checked: contradictory definitions, missing primary metrics, undefined success / failure criteria, impossible
conditions, units and denominators, timeout handling, matrix consistency, reproducibility metadata.
- No execution-blocking correctness issue in the frozen texts.
- Resolved conservatively during finalization (no new experiment): R-H1's denominator fixed as the redundant source
  bytes R = B_source,total - 1 of M1 only (the earlier formula is algebraically the same); N's two omitted product
  cells named with reasons; the N trigger defined on the fragment set frozen at the move (count, once); W-H1 / W-H2 /
  W-H3 NOT EVALUABLE rules made explicit; exploratory items other than W-AR removed from the run plan.
- Implementation note (not a text issue): the orchestrator ends a Cold-restart run `cold_tail_calls` (60) calls after its
  first output; W2's fixed horizon (call 133) must apply to both policies (implementation item "fixed observation
  horizon", `followup_common.md` section 5).

## Known limitations (stated at the freeze)

- Short clips are repeated with hard cuts; W does not establish long-form Sink stability; within-clip P_w is measurable
  only for some workloads.
- LOVEU licences are collection-level only; no LOVEU frame in publication figures until per-video permission.
- W-AR's crop changes content as well as geometry.
- R-H3(b) is a system-level comparison (policy-coupled background sessions) on one workload and three moves; R does not
  estimate deployment rho frequencies.
- N uses one degradation magnitude and one onset rule; M3's known false-positive re-plan (G5) is expected in cell 7.
- One workload (dog) for R and N; the GPU testbed drivers differ between host pairs (recorded per run).
