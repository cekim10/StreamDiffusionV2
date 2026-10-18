# Experiment W - Workload diversity: preregistration DRAFT v1 (2026-10-18; not frozen; nothing implemented or run)

Common rules, testbed, definitions, implementation items and cost: `../followup_common.md`. Dataset verification and
the subset rule: `loveu_tgve_verification.md`. Experiment D is prior evidence only (common rule 1).

## 1. Question

M1 rests on one premise: *a small execution-critical state (2.67 MiB) is enough to resume generation at once, and the
stream returns to the uninterrupted one after the late-arriving Sink binds.* Does this hold across inputs, and how often
does the Sink change (an adaptive promotion) inside a restoration window, which is the scope limit of M2/M3's
single-version restoration? W separates three things that Experiment D measured on one workload:
1. **TTFO stability** - execution resumes as fast regardless of the input (a property of the immediate state's size);
2. **visual rejoin** - whether and when the output returns to the reference after bind (a property of the content and of
   the Sink's refresh history);
3. **Sink-version stability** - how often promotions change the Sink, without any migration.

## 2. Prior evidence (predictions only; not data of W)

| source | observation |
|---|---|
| ExpD G1 (dog, 1 Gbps) | OTTER event-driven TTFO 0.675 s; native 0.680 s |
| ExpD generalization (scenario A, 1 Gbps) | TTFO 0.67-0.72 s for bird and boxing, seeds 0-1; rejoin 7.7-9.6 s (bird), 3.6-4.8 s (boxing); dog 3.58 s / 6 calls |
| state ablation (2026-10-06/09) | without the Sink a stream stays at ~19-20 dB; rejoin stretches with the adaptive-refresh rate; losing recent KV + VAE together fails to heal within 40 chunks on bird k = 2 / k = 4 |
| ExpD scope audit | the dog clip shows no promotion in the measured window; bird and boxing promote after bind |
| clip lengths (measured 2026-10-18) | dog (`original.mp4`) 81 frames, bird 254, boxing 251, train 65; the harness repeats a clip with a hard cut, one call = 4 frames, so dog cuts every ~20 calls and train every ~16 |

## 3. Workloads and units

- **W-repo** (4): dog (`original.mp4`, "A dog walks on the grass, realistic"), bird, boxing, train, each with its
  repository prompt file.
- **W-loveu** (16): the LOVEU-TGVE-2023 subset fixed by the rule in `loveu_tgve_verification.md` section 4 (input
  properties only: source folder, frame count, motion score; prompt types balanced 4 x style / object / background /
  multiple). Downloaded and fixed on 2026-10-18 (`loveu_selection.csv`: DAVIS 5, Videvo 6, YouTube 5; chosen before any
  OTTER run on them); the videos are not redistributed and no LOVEU frame appears in a publication figure until its
  reuse permission is established (`loveu_tgve_verification.md` section 2).
- **Unit** = (workload, seed), seeds 0 and 1: 20 workloads x 2 = **40 units**. k = 2, 480x832 (LOVEU's 480x480 is
  resized by the existing loader, an aspect stretch, stated as a property of the workload), 1 Gbps.
- Groups for descriptive breakdowns (fixed now): repo; LOVEU 32-frame (DAVIS, Videvo); LOVEU 128-frame (YouTube).

## 4. W1 - Sink-version stability (uninterrupted, no migration)

- One run per unit: the unmodified pipeline for 330 calls on one GPU (the reference path, no OTTER transfer).
- Logged per call: sink-slot positions (existing); a content fingerprint of each sink slot per layer computed on the
  **value** cache (not rotated by RoPE, so a t_refresh realignment does not change it); eviction-queue insertions that
  target a sink slot; the input frame index and whether the call's input chunk crosses a loop boundary.
- **Promotion** = a change of any layer's sink-slot value fingerprint between consecutive calls. A **version change** =
  a call with at least one promotion (any change invalidates the transferred Sink's digest).
- Derived per unit: promotions per 100 calls (calls 30-329); call indices and spacing; layers and slots affected and
  the affected bytes; promotions within 2 calls after a loop boundary reported separately as *loop-adjacent* (also kept
  in the totals); **P_w** = share of hypothetical trigger calls c in [30, 330 - w] with a version change in [c, c + w],
  for w = 6 (native rejoin-ready ~3.1 s), 25 (1 Gbps T_ref 14.05 s / 0.556 s) and 52 (bind after the final move of a
  rho = 2 schedule), the windows fixed in `../expT/sink_stability_plan.md` (2026-10-17).
- **Scope classification (rule, not a hypothesis):** a unit is *single-version stable at w* if P_w <= 0.05 (judgment
  value). The fraction of units stable at each w is the scope statement for repeated mobility (ExpD scope conditions
  5-6). The dog units' P_w also decides R's rho <= 1 cells (`../expR/preregistration_draft.md` section 6).

## 5. W2 - single migration across workloads

- Scenario A shape: one move A -> B at source chunk M = 30, warm destination, 1 Gbps, the ExpD harness.
- Policies: **OTTER event-driven** (`reuse_dyn`; a single move with no holders, so M1 + Sink restoration) and **Cold
  restart** (`cold`; fresh caches, no Sink) as the control that tells whether a workload's 35 dB rejoin needs the Sink.
- **Fixed observation horizon:** every run generates at B through call M + 100 (~56 s after the trigger; ~74 calls after
  a ~26-call bind at 1 Gbps), whether or not it rejoins. Reference = the same-seed uninterrupted run (node baseline of
  M + 130 calls).
- One run per (unit, policy) = 80 runs. Seeds are the replication; timing is summarized per workload over its two seeds.

## 6. Metrics

| metric | definition | role |
|---|---|---|
| TTFO | trigger -> first chunk at B | W-H1 |
| service time | per-call model call + synchronize at B (the nodes' `service_s`), median per run | W-H1 normalizer |
| rejoin calls | calls from the first bound chunk to the first chunk >= 35 dB (ExpD definition); **right-censored** at call M + 100 if never reached | W-H2, KM |
| rejoin delay | wall-clock counterpart of rejoin calls (censored likewise) | descriptive |
| sustained rejoin | first call from which >= 35 dB holds for 10 consecutive calls (censored likewise) | descriptive |
| Cold reaches 35 dB | any Cold-restart chunk >= 35 dB in calls M + 1 .. M + 100 | W-H3 |
| continuity coverage | share of chunks in M + 1 .. M + 100 at >= 35 dB | descriptive |
| promotions after bind | W1-style fingerprints at B after bind, and in the reference at the same calls | descriptive |

## 7. Confirmatory hypotheses (decision rules fixed at the freeze)

- **W-H1 (TTFO stability).** For every workload, the median TTFO over its two OTTER runs <= 1.0 s, **and** the spread
  (max - min) of the 20 workload medians <= 0.25 x the median service time over all OTTER runs.
  Origins: 1.0 s is G1's bound (frozen 2026-10-16, before ExpD ran); 0.25 call is a judgment value meaning "no workload
  costs an extra quarter of a generation call", motivated by the mechanism (the immediate state's size does not depend
  on content). Recorded prediction: supported (prior TTFO 0.67-0.72 s on three clips).
- **W-H2 (rejoin within the horizon).** OTTER rejoins (rejoin calls not censored) in >= 80 % of the 40 units.
  Origin: 80 % is a judgment value for "generally holds"; it is deliberately below 100 % because prior evidence already
  shows workload-dependent healing. Recorded prediction: uncertain (all three prior clips rejoined; LOVEU untested).
- **W-H3 (rejoin depends on the Sink).** Among units in which OTTER rejoins, Cold restart reaches 35 dB within the same
  horizon in <= 20 % (i.e. the 35 dB criterion discriminates Sink restoration from input-driven convergence in >= 80 %).
  Origin: judgment value, symmetric to W-H2. Recorded prediction: supported for dog (prior ~19-20 dB without the Sink);
  unknown elsewhere. Units in which Cold restart reaches 35 dB are listed as *non-discriminating*, and W-H2 is also
  reported over the discriminating units only (descriptive).

Each hypothesis is evaluated over all 40 units (W-repo alone if LOVEU is not approved, with N stated); a unit lacking a
valid run of either policy makes W-H3 not evaluable for that unit; if more than 10 % of the units (4 of 40) are not evaluable, the
hypothesis is NOT EVALUABLE (the same 10 % rule applies when W runs on W-repo alone).

## 8. Descriptive analyses (reported in full; no pass/fail)

- Kaplan-Meier curve of rejoin calls (censored at the horizon), overall and per group (repo / LOVEU 32 / LOVEU 128);
  KM median and the share rejoined within 8 calls (ExpD G2's bound, shown as a reference line, not judged).
- Relation of rejoin calls to the motion score, W1 promotions per 100 calls, promotions after bind in W2, and distance of
  the bind call to the nearest loop boundary (Spearman coefficients with the units listed; no test).
- W1 distributions: promotions per 100 calls, P_6 / P_25 / P_52, affected bytes per promotion, loop-adjacent share.
- PSNR / SSIM trajectories per unit; continuity coverage; sustained rejoin vs first rejoin.
- Exploratory (after the primary set, if time allows): W-repo at k = 1 and 4; native bandwidth; Full migration as a
  bit-exact check on two LOVEU units.

## 9. Validity and scope

- ExpD run-validity rules apply (`../followup_common.md` section 2). In W2 a version event before bind cannot occur by
  construction (the source stops generating at the handoff; B's adaptive refresh is frozen until bind); promotions after
  bind are the workload's normal behaviour and are counted, not excluded.
- Loop boundaries are a property of the harness (hard repeat of short clips), identical in the run and its reference;
  they are marked, not removed. The 32-frame LOVEU clips cut every 8 calls, so their results are always also reported
  as a separate group.
- PSNR against the reference measures continuity with the uninterrupted stream, not generic quality (state-ablation
  note); W makes no perceptual-quality claim.

## 10. Runs

W1 40 runs (330 calls each); W2 80 runs (40 invocations); see `../followup_common.md` section 5.

## 11. What the outcomes mean for the paper

- W-H1 supported: "execution resumes within one call regardless of input" can be stated for the tested workloads.
- W-H2 / W-H3: the rejoin claim is stated with its KM distribution and the share of non-rejoining and
  non-discriminating units; if W-H2 is not supported, the paper states that continuity recovery is workload-dependent and
  names the workload classes (from the descriptive analyses) where it fails.
- W1: the scope sentence on single-version restoration is given as measured fractions (P_w), not as an assumption.
