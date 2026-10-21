# Experiment WX - workload expansion of the core mobility experiments: preregistration DRAFT (2026-10-20)

Status: **DRAFT, not frozen. Nothing implemented or run.** Roadmap step 2 (`../evaluation_roadmap.md`). No frozen result
(ExpD, W / R / N, V, A, B, VACW, RD, M3E) is modified. Open decisions in section 9.

## 1. Purpose

Every repeated-mobility and network-adaptation result so far (ExpD B / E / F / G, R, N, V, M3E) uses one workload:
`examples/original.mp4` (a tabby **cat** video) with the prompt "A dog walks on the grass, realistic" ("dog"), whose Sink
changes rarely (W1, seed 0: 16 promotions in 330 calls). WX re-runs the core configurations on three further inputs whose Sinks
change often, to test whether the M2 (progress preservation) and M3-v2 (provider reassignment) results depend on the
workload. WX replicates existing frozen hypotheses; it introduces no new mechanism, threshold or metric.

## 2. Workloads (seed 0)

| workload | source | why | W1 promotions / 330 calls | figures |
|---|---|---|---|---|
| butterfly-feeding-slow-motion | LOVEU-TGVE (Videvo, 32 frames) | refresh-heaviest clip used in A / B / VACW / RD | 200 | no LOVEU frames in figures |
| audi-snow-trail | LOVEU-TGVE (YouTube, 128 frames) | refresh-active; W2 never-sustained | 120 | no |
| train | repository | refresh-heavy repo clip (usable in figures); W2 never-sustained | 80 | yes |

Dog (the frozen results) is the reference workload; its numbers are cited from R / M3E, not re-run.

## 3. Scope (unchanged from ExpD / R / M3E)

Frozen M2 restores one Sink snapshot per restoration. Only rho >= 1 is used, where no intermediate owner binds before
it is left (R: B binds at 14.4-15.0 s > T_m = 14.05 s at rho 1). A run with an owner-side Sink promotion before the
final bind, a fragment-version rejection or a digest mismatch is **inapplicable** (W / R / N rule) and NOT EVALUABLE for
every hypothesis comparing it. Refresh-heavy inputs make this check more likely to bind than on dog; the count is
reported.

## 4. Configurations (A -> B -> C -> D, trigger at chunk 30, 1 Gbps, warm destinations, `--post_chunks 400`)

| id | replicates | condition | policies | hypotheses (frozen texts, unchanged thresholds) |
|---|---|---|---|---|
| X1 | R c = 0, rho 1 | no contention | M1 only, M1 + M2 | R-H1, R-H2, R-H3(a) |
| X2 | R c = 0, rho 4 | no contention | M1 only, M1 + M2 | R-H1, R-H2, R-H3(a) |
| X3 | M3E S4 (+ R c = 0, rho 2) | rho 2, no change | M1 only, M1 + M2, M3-v2 | R-H1, R-H2, R-H3(a); M3E H4, H6, H7 |
| X4 | M3E S1 (ExpD E, G6) | rho 2, 3 network-level M3-v1 sessions on A's egress | M1 only, M1 + M2, M3-v2 | M3E H1 (same scope limits as M3E S1) |
| X5 | M3E S2 (ExpD F, G7) | rho 2, `D>=0.5:C:out=62.5` | M1 + M2, M3-v2, OTTER at moves | M3E H2 |
| X6 | M3E S3 | rho 2, `D>=0.5:D:in=62.5` | M1 + M2, M3-v2 | M3E H3 |

M3E S5 (source bottleneck) is not replicated (D2). M3-v1 is not re-run.

## 5. Hypotheses and decision rule

Each hypothesis listed in section 4 is evaluated **per workload** exactly as frozen (R: `expR/preregistration.md`
section 7; M3E: `expM3E/preregistration.md` section 6), with the same NOT EVALUABLE, censoring and validity rules.

**Generality statement (fixed now):** for each hypothesis, the paper reports "supported on k of 4 workloads" (dog from
the frozen R / M3E results plus the three WX workloads), with every NOT SUPPORTED and NOT EVALUABLE cell listed. A claim
is stated without a workload qualifier only if it is supported on all four; otherwise it is stated with the workloads on
which it holds. No pooling of runs across workloads.

**Recorded predictions:** R-H1 / R-H2 hold on every workload (progress preservation does not depend on content);
R-H3(a) holds (ingress-bound); M3E H1, H2, H4 behave as on dog; H3 at risk where refresh-heavy inputs change the GPU
service time (H7). The applicability flag may remove cells on audi-snow-trail (frequent promotions after the final
bind are fine; before it they should not occur at rho >= 1).

## 6. Metrics

As R and M3E: bind-ready after the final move, TTFO, source and total network bytes, discarded bytes, re-plans and
probes, chunk service time (move -> bind), validity, applicability, network-session completion (X4).

## 7. Runs, runtime, occupancy

| config | policies | runs per workload (3 reps) |
|---|---|---|
| X1 | 2 | 6 |
| X2 | 2 | 6 |
| X3 | 3 | 9 |
| X4 | 3 | 9 |
| X5 | 3 | 9 |
| X6 | 2 | 6 |
| per workload | | **45** |
| **total (3 workloads)** | | **135** |

~2-3 min per run plus one node start per (configuration, workload) invocation (18 x ~4 min): **~6.5-7.5 h of exclusive
use of GPU 0 on all four hosts**; can be split into three sessions, one per workload. Shakedown before the sweep: one
run per policy of X3 and X5 on each workload (18 runs, ~50 min; not evidence).

## 8. Implementation

Driver entries reusing `run_wrn.py` (R and M3E argument builders with the workload's `node_extra`), an aggregator that
applies the frozen R and M3E rule code per workload and adds the generality table. No change to M1, M2, M3-v2 or the
harness.

## 9. Open decisions (close before the freeze)

- **D1** - three workloads (135 runs, ~7 h) or two (butterfly + train, 90 runs, ~4.5 h)? Recommended: three.
- **D2** - add M3E S5 (+18 runs)? Recommended: no (H5's question is about the planner, not the content).
- **D3** - add R at c = 3 for rho 1 (+18 runs) to replicate R-H3(b) at both rho values? Recommended: no; X4 covers rho 2.
- **D4** - run WX before or after the M3E result? Recommended: after, so that X3-X6 replicate hypotheses whose dog
  result is known (no change to WX's rules either way).
