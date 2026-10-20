# Experiment V results: M3-v2 holdout (GPU, 2026-10-19/20)

Frozen plan `m3v2_holdout_plan.md` (freeze e39609a, record `../m3v2_freeze.md`) with Amendment 1 (harness placement-window
guard; V8 run window). Verdicts by `tools/eval/aggregate_wrn.py` section V (`../wrn_results.md`). Runs: first run 96
(`expV_cell*`, commit 91faa0a, 2026-10-19 16:03-18:51 + ~2.8 h), amendment re-runs 48 (`expV_a1_cell{1,2,3,8}`, commit
f731bd9); the first-run V1-V3 and V8 directories are kept and superseded; V4-V7 are first-run results. All 96 runs in
the verdict set are valid; no timeouts after the amendment. M3-v2's algorithm and parameters were not changed between the
freeze and these runs. Development data (N cells 1-10, ExpD G5 / G7, the regression rounds) are not part of the evidence.

## 1. Outcomes (medians over 3 valid reps; bind-ready after the move in s; B_source in Sinks)

| cell | class | at moves | M1 + M2 | M3-v1 (bind / B_src / re-plans) | **M3-v2** (bind / B_src / re-plans, probes) | v2 vs at moves | V-H4 v2 vs v1 |
|---|---|---|---|---|---|---|---|
| V1 proportional x no change | no change | 12.10 / 1.010 | 12.1 / 1.010 | 12.08 / 1.073 / 1 | **12.08 / 1.010 / 0** | **V-H1 SUPPORTED** | SUPPORTED |
| V2 proportional x holder B 125 Mbps @ 0.25 | alternative available | 44.95 / 1.000 | 44.2 / 1.007 | 12.13 / 1.299 / 2 | **12.24 / 1.306 / 1 (0)** | **V-H2 SUPPORTED** (0.27 x; <= 2 re-plans; 0 dups) | SUPPORTED |
| V3 proportional x ingress 250 Mbps @ 0.75 | no alternative | 20.37 / 1.000 | 20.3 / 1.007 | 20.30 / 1.073 / 1 | **20.26 / 1.010 / 1 (1)** | **V-H3 SUPPORTED** | SUPPORTED |
| V4 incorrect x holder B 250 Mbps @ 0.25 | alternative available | 38.32 / 1.000 | 37.6 / 1.010 | 15.06 / 1.411 / 3 | **19.12 / 1.367 / 2 (1)** | **V-H2 SUPPORTED** (0.50 x) | **NOT SUPPORTED** (+4.1 s; B_src -0.04; re-plans 2 vs 3) |
| V5 incorrect x holder B 31.25 Mbps @ 0.75 | alternative available | 122.08 / 1.000 | 121.1 / 1.010 | 17.43 / 1.338 / 3 | **21.57 / 1.231 / 2 (1)** | **V-H2 SUPPORTED** (0.18 x) | **NOT SUPPORTED** (+4.1 s; B_src -0.11) |
| V6 incorrect x ingress 125 Mbps @ 0.25 | no alternative | 87.75 / 1.000 | 87.6 / 1.007 | 86.82 / 1.253 / 5 (5-9) | **87.59 / 1.000 / 0** | **V-H3 SUPPORTED** | SUPPORTED |
| V7 incorrect x source 250 Mbps @ 0.75 | no alternative | 15.09 / 1.000 | 15.1 / 1.010 | 15.61 / 1.170 / 2 | **15.24 / 1.000 / 0** | **V-H3 SUPPORTED** | SUPPORTED |
| V8 none x ingress 31.25 Mbps @ 0.25 | no alternative | 335.73 / 1.000 | 335.6 / 1.000 | 335.43 / 1.000 / 0 | **335.29 / 1.000 / 0** | **V-H3 SUPPORTED** | SUPPORTED |

Degradation triggers fired once in every degraded run at ceil(q |S|); every run valid; the placement under
`proportional` delivered B 0.42-0.43, C 0.22-0.25, D 0.06-0.07 Sink for every policy (amended runs).

## 2. Reading

- **No false positives (V1, V6, V7, V8; V3 one probe).** With three providers on one ingress (V1) v2 makes no re-plan
  where v1 makes one (+0.06 Sink); under ingress degradation (V6) v2 makes none where v1 makes 5-9 (+0.25 Sink); under
  source degradation with nothing movable (V7) none where v1 makes 2 (+0.17 Sink). In V3 v2 pays one 4-fragment probe
  (B_source 1.010) because, with the ingress degraded late (q = 0.75), A and D had finished and B alone looked like a
  slow provider; the probe shared the degraded ingress and was withdrawn.
- **The benefit where an alternative exists is kept (V2, V4, V5): 3.7 x, 2.0 x, 5.7 x faster than at moves**, within
  the frozen <= 2 re-plans bound, with 0.04-0.11 Sink less source traffic than v1 in V4 / V5.
- **v2 is 4.1 s slower than v1 in V4 and V5 (V-H4 NOT SUPPORTED there), as recorded before the holdout.** Under
  top-1 placement the source finishes its own fragments about when the holder degrades, so the holder is alone and v2
  must probe (steady span ~2.5 s + probe ~0.5 s + the full move), whereas v1's false-positive re-plan at +2.3 s had
  already moved fragments to the source before the degradation. In V2, where the degradation arrives while A and D are
  still active, v2 attributes the bottleneck from two-provider evidence without a probe and matches v1 (12.2 vs 12.1 s)
  with one re-plan instead of two.
- Statement the data support: *M3-v2 removes M3-v1's false-positive re-plans and oscillation in every tested class
  (no change, ingress-, source-limited, multi-holder) at zero or one-probe cost, and keeps the large gain when a
  degraded holder's fragments are available elsewhere; it reacts ~4 s later than v1 when the degraded holder is the only
  active provider, the cost of acting on confirmed evidence.* No universal claim beyond the tested conditions (one
  workload, one magnitude per cell, one onset per cell).

## 3. Amendment history (first-run V1-V3 and V8 superseded)

First run (commit 91faa0a): V1 V-H1 SUPPORTED, V2 V-H2 NOT SUPPORTED, V3 V-H3 SUPPORTED - on a condition that was not the
preregistered one for the AWARE policies (placement truncated to 0.08 Sink at B by a harness bug in `plan_aware`; M1 + M2
had the full placement); V8 NOT EVALUABLE for every policy (call window shorter than the restoration). Both corrected by
Amendment 1 (`m3v2_holdout_plan.md`), re-run on 2026-10-20; the superseded directories are kept.

## 4. Limitations

One workload (dog, seed 0); one magnitude and one onset per cell; single move; M3-v1's development was closed, so its
verdicts here are descriptive; the probe cost (4 fragments) and the ~4 s reaction delay in the single-provider case are
properties of the frozen parameters (`min_frags` 8, two-fragment margins, probe 4), not explored further.
