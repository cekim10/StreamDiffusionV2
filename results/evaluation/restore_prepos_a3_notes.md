# Experiment A3: pre-positioning under shared-source contention (H5d, H5e), 30 runs (2026-10-15)

Arrangement and model predictions were committed before the run (TOPOLOGY_PLAN.md G.1 "A3"; criteria frozen in F,
v3). Session s0 executes at source A and pre-positions b = 0.5 Sink to the top-1 candidate B during L = 10 s, then
moves to the true destination (B = correct, C = incorrect); three other sessions restore their own Sinks from the same
source A, starting either at t0 (H5d: active during the pre-positioning) or at s0's move (H5e: contention after the
fragments landed). 1 Gbps caps; holders at 1 Gbps or 125 Mbps; restoration `reuse_aware_in` (and `reuse_fixed` in the
slow-holder pair); 3 reps. Raw runs `restore_prepos_a3/`; tables and verdicts `summary.csv`, `summary_by_config.csv`,
`criteria.md` (`tools/eval/aggregate_prepos.py --experiment restore_prepos_a3 --a3`).

## Run validity

29/30 valid. The invalid run (`reuse_fixed`, 125 Mbps, none, rep 3) saw external traffic of 4.5-6.9 Gbps from
elves-01 to elves-04 between 24.8 and 33 s of the run (kernel NIC counters; our own flows stayed within their caps,
paced egress 999.9 Mbps worst at A). Its results are identical to the other two reps (T_r 55.5 s, others 65.5 s) but it
is excluded from the medians per the frozen rule and the condition is to be re-run (one run). All other runs: every
fragment verified, paced egress within cap, NIC peaks <= 1064 Mbps, four distinct hosts, no early rate/cancel events.
Rep spread 0.0-0.2 s everywhere.

## Measurements (medians; T_r = s0's move -> all fragments verified; "others" = makespan of the three other sessions)

| arrangement | N | holders | policy | pre-positioning | s0 T_r (s) | others (s) | verified at B at the move | fwd by B (never owner) | s0 post-move source | source total (Sinks) | total traffic |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H5d: others from t0 | 4 | 1 Gbps | aware_in | none -> B | 45.5 | 52.1 | 0 | 0 | 1.00 | 4.00 | 4.74 |
| H5d: others from t0 | 4 | 1 Gbps | aware_in | top-1 -> B (correct) | **32.1** | **55.4** | 0.18 | 0 | 0.82 | 4.00 | 4.56 |
| H5e: others from L | 4 | 1 Gbps | aware_in | none -> C | 55.4 | 65.4 | 0 | 0 | 1.00 | 4.00 | 4.57 |
| H5e: others from L | 4 | 1 Gbps | aware_in | top-1 -> C (incorrect) | **27.8** | 58.5 | 0.50 | **0.50** | 0.50 | 4.00 | 5.07 |
| ingress-bound | 1 | 1 Gbps | aware_in | none -> C | 14.0 | - | 0 | 0 | 1.00 | 1.00 | 1.00 |
| ingress-bound | 1 | 1 Gbps | aware_in | top-1 -> C (incorrect) | 14.0 | - | 0.50 | 0.50 | 0.50 | 1.00 | 1.50 |
| slow holder, others from L | 4 | 125 Mbps | fixed | none -> C | 55.4 | 65.4 | 0 | 0 | 1.00 | 4.00 | 4.57 |
| slow holder, others from L | 4 | 125 Mbps | fixed | top-1 -> C (incorrect) | **79.9** | 71.2 | 0.50 | 0.50 | 0.50 | 4.00 | 5.07 |
| slow holder, others from L | 4 | 125 Mbps | aware_in | none -> C | 55.4 | 65.5 | 0 | 0 | 1.00 | 4.00 | 4.57 |
| slow holder, others from L | 4 | 125 Mbps | aware_in | top-1 -> C (incorrect) | **48.6** | 63.8 | 0.50 | 0.12 | 0.88 | 4.38 | 5.07 |

## Frozen verdicts (TOPOLOGY_PLAN F; model value from G.1 beside each)

| clause | measured | model | threshold | verdict |
|---|---|---|---|---|
| H5d interference: others' makespan, top-1 minus none, others active during pre-positioning | +3.3 s | +3.3 | >= 3.5 s | **FAIL** (predicted borderline) |
| H5d idle source: same, others start at L | -6.9 s | -6.9 | < 1 s | PASS |
| H5e shared source: T_r none - top-1 -> C, N = 4, 1 Gbps holders | **27.7 s** (55.4 -> 27.8) | 27.6 | >= 7.0 s | **PASS** |
| H5e ingress-bound: same, N = 1 | 0.0 s | 0.0 | < 1 s | PASS |
| H5e slow holder, fixed: same, 125 Mbps | -24.5 s (worse) | -24.4 | < 1 s | PASS |
| H5e slow holder, aware_in: same, 125 Mbps | 6.8 s | 6.8 | >= 7.0 s | **FAIL** (predicted borderline) |

H5d: FAIL on the main clause. H5e: three of four clauses pass; the slow-holder aware clause fails by 0.2 s.

## Model prediction error

Every measured median is within 0.2 s of the fluid-model prediction written before the run (T_r, others' makespan,
verified bytes within 0.01 Sink, source bytes within 0.01 Sink). The two FAILs are the model's borderline predictions,
not surprises; the frozen **analytical** values that set the thresholds (7.0 s interference, 18.7 s slow-holder gain)
were wrong for stated reasons, see below.

## Reading

1. **Wrongly placed fragments are worth as much as correctly placed ones when the source is the bottleneck and the
   holder is fast (H5e main).** With the source shared by four sessions, s0 restores in 27.8 s whether its 0.5 Sink
   sits at the destination or at B: B forwards all of it (0.50 Sink, B was never an owner) while A sends the other half
   at its 250 Mbps share, and the whole-Sink restore would have taken 55.4 s. The gain (27.7 s) equals the D.1b
   prediction (28 s) and the measured 32.1 vs 27.8 s difference between the H5d and H5e arrangements is the realized
   placement (0.18 vs 0.50 Sink), not correctness.
2. **The same fragments are worth nothing at the ingress bound (N = 1: 14.0 vs 14.0 s)** and are **harmful under
   unconditional reuse when the holder is slow**: fixed forwarding from a 125 Mbps holder makes T_r 79.9 s against
   55.4 s with no pre-positioning (+24.5 s). Bottleneck-aware selection turns the same placement into a 6.8 s gain
   (48.6 s) by moving 0.38 Sink back to the source (source bytes 4.38 instead of 4.00), with 0.12 Sink still forwarded
   by B. The frozen 7.0 s threshold is missed by 0.2 s; the analytic 18.7 s (D.1b) ignored that the other sessions
   also move and re-plan, which the model captured (6.8 s).
3. **Interference (H5d) exists but is smaller than the frozen analytic.** With the others active, s0's pre-positioning
   flow gets the 4-way share, so only 0.18 Sink lands in 10 s; the others' makespan rises by 3.3 s (threshold 3.5 s,
   analytic 7.0 s), while s0's own T_r falls by 13.4 s (45.5 -> 32.1). The analytic counted the whole 0.5 Sink as
   extra source work and ignored that s0's post-move work shrinks by what was pre-positioned; the net cost to the
   others is the share they lose during the lookahead. When the pre-positioning finishes before the others start, they
   finish 6.9 s *earlier* (s0 competes less afterwards). Source bytes are 4.00 Sinks in every 1 Gbps configuration:
   pre-positioning never adds source traffic, it moves it.
4. Total network traffic rises with pre-positioning to a wrong candidate (4.57 -> 5.07 Sinks for four sessions: the
   0.5 Sink is carried twice, A -> B and B -> C); that is the price of the 27.7 s gain under contention and of nothing at
   the ingress bound.

## Unexpected findings

- None in the mechanism. The external 4.5-6.9 Gbps transfer from elves-01 to elves-04 during one run is the second
  contamination event of the project (the first invalidated two Scenario B v1 runs); the NIC check caught it.

## Implications for OTTER's M3

- Supported claim (measured): *speculative placement is not wasted when the mobility prediction is wrong, provided the
  restoration is source-bound and the holder can forward at least as fast as the source's share; the
  bottleneck-aware provider rule is what keeps a wrong placement from becoming harmful when the holder is slow.* This
  ties pre-positioning to progress preservation and to the Step 2 rule rather than to prediction accuracy alone.
- Not supported as written: the interference threshold (H5d) and the slow-holder gain threshold; both because the
  frozen analytics were too coarse, not because the effects are absent. Report as FAIL with the model explanation.
- Design consequence: pre-positioning should spend idle source capacity (lookahead before contention), since under
  contention it only reorders the source's work (s0 gains, others lose a share); and its fragments must be routed by the
  same backlog/ingress-aware rule as every other fragment.

## Follow-ups (not run; proposed)

- Re-run the one invalid configuration (`reuse_fixed`, 125 Mbps, none, rep 4) to restore three valid reps.
- Diagnostic holder-bandwidth sensitivity for the slow-holder clause (62.5 / 125 / 250 / 500 / 1000 Mbps, aware_in vs
  fixed, H5e arrangement), reported separately from the pre-registered A3 results, to locate the holder speed at which
  a wrong placement stops paying.
