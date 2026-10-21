# Experiment M3E results: final OTTER (M3-v2) end-to-end (GPU, 2026-10-20)

Frozen preregistration `preregistration.md` (abf74d6; record `../expM3E_freeze.md`), implementation 14551bd (+ b5b0625:
`--cells` for re-runs only). GPU shakedown 16 / 16 PASS (`shakedown_check.md`). Main sweep 48 runs on elves-01..04 GPU 0
(dog = the tabby-cat video with the prompt "A dog walks on the grass, realistic", seed 0, A -> B -> C -> D, rho 2,
1 Gbps); **47 / 48 valid at first**; the invalid run (S3, M3-v2, rep 1: a 1 s NIC sample of 773 Mbps into D while the
run's own verified traffic into D was 60.4 Mbps, i.e. traffic not from the run) was kept and re-run once under the
frozen rule; the re-run is valid. Verdicts by `tools/eval/aggregate_m3e.py` (`m3e_results.{md,json}`); nothing in the
scenarios, thresholds or rules changed after the freeze.

## 1. Verdicts (medians over 3 valid reps; bind-ready = first chunk with the Sink bound, after the final move)

| hypothesis | scenario | result | verdict |
|---|---|---|---|
| H1 contention | S1: one M3-v2 GPU session + 3 network-level M3-v1 sessions on A's egress | M3-v2 43.08 s vs M1 only 57.23 s (-14.1 s) and M1 + M2 43.23 s; B_source 1.015 vs 1.017; 0 re-plans | **SUPPORTED** |
| H2 holder bottleneck | S2: C's egress -> 62.5 Mbps when D holds 50 % | M3-v2 20.71 s vs at moves 52.13 s (0.40 x) and M1 + M2 78.53 s (0.26 x); 2 re-plans incl. 1 probe in every rep; 0 duplicates; B_source 1.18 | **SUPPORTED** |
| H3 no harm, ingress | S3: D's ingress -> 62.5 Mbps | M3-v2 118.40 s vs M1 + M2 117.52 s (+0.88 s, threshold +1.0 s); 0 re-plans, 0 probes; B_source 1.036 vs 1.034 | **SUPPORTED** |
| H4 no change | S4 | 0 re-plans and probes in every rep; 15.33 vs 15.38 s; B_source 1.027 vs 1.036 | **SUPPORTED** |
| H5 no harm, source | S5: A's egress -> 62.5 Mbps | 0 re-plans; 30.44 vs 29.93 s (+0.51 s); B_source 1.034 vs 1.034 | **SUPPORTED** |
| H6 resumption | S1-S5 | M3-v2 TTFO 1.01-1.08 s, within +0.08 s of M1 + M2 in every scenario | **SUPPORTED** |
| H7 GPU interference | S1-S5 | chunk service time move -> bind 0.540-0.545 s for every policy; M3-v2 within 0.2 % of M1 + M2 | **SUPPORTED** |

**Overall (section 6 rule): M3-v2 is reported as the paper's end-to-end M3** (H1, H2, H4 supported; H3, H5 supported).
No regression against frozen M2 in any scenario.

## 2. Descriptive (not pass conditions)

- **S2 vs M1 only:** M1 only binds at 15.50 s (it never uses the degraded holder) at 2.02 Sinks of source traffic;
  M3-v2 is 5.2 s slower at 1.18 Sinks. Against the historical M3-v1 result for this configuration (ExpD F, cross-commit:
  15.80 s) M3-v2 is ~4.9 s slower: the probe-and-confirm reaction cost recorded in V (V4 / V5, ~4 s).
- **Where M3-v1 failed, M3-v2 did nothing:** S3 (N cell 10 class: v1 re-planned 28-32 times) and S5 (N cell 8 class: v1
  +3.5 s) - 0 re-plans and 0 probes in all 6 M3-v2 runs; S4 (no change) 0 as well. H3 passed with +0.88 s against a
  1.0 s threshold (ingress-bound restoration of ~118 s; the difference is not attributable to re-planning, which did not
  occur).
- **S1:** the three network-level sessions finished in ~72 s with M1 only and ~56 s with M1 + M2 / M3-v2 (their planner
  is M3-v1 per the frozen mapping; reported separately, never merged with the GPU session).
- Total network bytes were equal across progress-preserving policies (2.02-2.03 Sinks in S2-S5; 1.38 in S1).
- Historical comparison (cross-commit, descriptive): S1 matches ExpD E (M1 + M2 43.09 / v1 42.82 / M1 only 57.07 s); S4
  matches ExpD B rho 2 (15.1-15.5 s).

## 3. Limitations

One input (dog clip) and seed; one magnitude and onset per degradation; rho 2 only; S1's competing sessions are
network-level and run M3-v1; emulated caps on one LAN. Workload breadth is the next roadmap step (WX).
