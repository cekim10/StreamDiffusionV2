# Experiment WX - workload expansion of the core mobility experiments: preregistration DRAFT (2026-10-20)

Status: **FROZEN** (freeze record `../expWX_freeze.md`), after the M3E result (D4). Revised before the freeze by the
policy-matrix audit of section 4.1 (X5 gains M1 only; 144 runs). Nothing implemented or run at the freeze. M3E's frozen
results and its seven verdicts are not changed. Roadmap step 2 (`../evaluation_roadmap.md`). No frozen result (ExpD, W / R / N, V, A,
B, VACW, RD, M3E) is modified.

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
every hypothesis comparing it; the count is reported.

**Promotion frequency characterizes the workload; it does not by itself make a run invalid or inapplicable.** The W1
promotion counts in section 2 describe how often each input's Sink changes when it is generated on. Snapshot-version
validity is decided per run by the rule above: refresh is frozen at an owner until it binds, and at rho >= 1 no
intermediate owner binds before it is left, so promotions at the source before the trigger are inside the snapshot and
promotions at the final owner after its bind do not affect the restored version. A frequently promoting input may still
yield fully applicable runs, and only the per-run check decides.

## 4. Configurations (A -> B -> C -> D, trigger at chunk 30, 1 Gbps, warm destinations, `--post_chunks 400`)

| id | replicates | condition | policies | hypotheses (frozen texts, unchanged thresholds) |
|---|---|---|---|---|
| X1 | R c = 0, rho 1 | no contention | M1 only, M1 + M2 | R-H1, R-H2, R-H3(a) |
| X2 | R c = 0, rho 4 | no contention | M1 only, M1 + M2 | R-H1, R-H2, R-H3(a) |
| X3 | M3E S4 (+ R c = 0, rho 2) | rho 2, no change | M1 only, M1 + M2, M3-v2 | R-H1, R-H2, R-H3(a); M3E H4, H6, H7 |
| X4 | M3E S1 (ExpD E, G6) | rho 2, 3 network-level M3-v1 sessions on A's egress | M1 only, M1 + M2, M3-v2 | M3E H1 (same scope limits as M3E S1) |
| X5 | M3E S2 (ExpD F, G7) | rho 2, `D>=0.5:C:out=62.5` | M1 only, M1 + M2, M3-v2, OTTER at moves | M3E H2 |
| X6 | M3E S3 | rho 2, `D>=0.5:D:in=62.5` | M1 + M2, M3-v2 | M3E H3 |

M3E S5 (source bottleneck) is not replicated (D2). M3-v1 is not re-run.

### 4.1 Policy-matrix audit (every imported hypothesis can be evaluated as frozen)

| imported hypothesis (frozen text) | configs | policies the frozen rule needs | present |
|---|---|---|---|
| R-H1 redundant source traffic (B_source(M1 + M2) <= 1.10 and reduction >= 75 %; NE if R(M1 only) < 0.10) | X1, X2, X3 | M1 only, M1 + M2 | yes |
| R-H2 discarded work (<= 0.10 Sink) + manipulation check (M1 only discarded >= 0.75 x 2 / rho at rho 2, 4) | X1, X2, X3 | M1 only, M1 + M2 | yes |
| R-H3(a) latency without contention (abs difference <= 1.0 s) | X1, X2, X3 | M1 only, M1 + M2 | yes |
| M3E H1 contention | X4 | M1 only, M1 + M2, M3-v2 | yes |
| M3E H2 holder bottleneck (<= 0.5 x at moves and <= 0.5 x M1 + M2; <= 2 re-plans, <= 1 probe of <= 4 fragments, 0 duplicates; B_source <= 1.35, "approximately 65 % of M1 only's ~1.0 redundant Sink") | X5 | M1 + M2, M3-v2, at moves; **M1 only** for the source-byte rationale | **added** (the draft omitted M1 only; M3E S2 included it) |
| M3E H3 no harm, ingress | X6 | M1 + M2, M3-v2 | yes |
| M3E H4 no change | X3 | M1 + M2, M3-v2 | yes |
| M3E H6 TTFO / H7 GPU service time | X3-X6 | M1 + M2, M3-v2 | yes; scope note below |

Notes fixed at the freeze: (i) H2's source-byte threshold stays the frozen absolute 1.35 Sinks; the M1-only runs of X5
report, per workload, the fraction of M1 only's redundant source bytes (B_source(M1 only) - 1) that M3-v2 removes,
next to the verdict, so the threshold's rationale is checked on every input. (ii) M3E's H6 / H7 were frozen over
S1-S5; WX evaluates them per configuration on X3-X6 with the same thresholds, and the WX-level H6 / H7 statement covers
X3-X6 only (S5 is not replicated, D2).

## 5. Hypotheses and decision rule

Each hypothesis listed in section 4 is evaluated **per workload** exactly as frozen (R: `expR/preregistration.md`
section 7; M3E: `expM3E/preregistration.md` section 6), with the same NOT EVALUABLE, censoring and validity rules.

**Generality statement (fixed now):** for each hypothesis, the paper reports "supported on k of 4 tested inputs" (dog,
i.e. the cat video with the dog prompt, from the frozen R / M3E results, plus the three WX inputs), with every NOT
SUPPORTED and NOT EVALUABLE cell listed. **Generalization claims are limited to these four video inputs with their
prompts, seed 0, the one model and the tested configurations**; no claim extends to other inputs, seeds, models or
network conditions. A claim is stated without a per-input qualifier only if it is supported on all four; otherwise it
is stated with the inputs on which it holds. No pooling of runs across inputs.

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
| X5 | 4 | 12 |
| X6 | 2 | 6 |
| per workload | | **48** |
| **total (3 workloads)** | | **144** |

~2-3 min per run plus one node start per (configuration, workload) invocation (18 x ~4 min): **~7-8 h of exclusive use
of GPU 0 on all four hosts**; can be split into three sessions, one per workload. Shakedown before the sweep: one run per
policy of X3 and X5 on each workload (7 x 3 = 21 runs, ~1 h; harness checks only, not evidence).

## 8. Implementation

Driver entries reusing `run_wrn.py` (R and M3E argument builders with the workload's `node_extra`), an aggregator that
applies the frozen R and M3E rule code per workload and adds the generality table. No change to M1, M2, M3-v2 or the
harness.

## 9. Decisions (closed 2026-10-20)

- **D1** - all three additional workloads (144 runs after the section 4.1 audit).
- **D2** - M3E S5 is not replicated.
- **D3** - R at c = 3 is not added (X4 covers contention at rho 2).
- **D4** - WX runs after the M3E result; it is frozen at that point without changing its rules.
