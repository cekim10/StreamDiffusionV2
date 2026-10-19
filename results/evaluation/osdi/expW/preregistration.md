# Experiment W - Workload diversity: preregistration (FINAL; frozen, record `../followup_prereg_freeze.md`)

Common rules (validity, re-runs, censoring, aggregation, metadata): `../followup_common.md`. Dataset and subset:
`loveu_tgve_verification.md`, `loveu_population.csv`, `loveu_selection.csv`. Loop arithmetic: `loop_audit.md` /
`loop_audit.json` (`tools/eval/expw_loop_audit.py`). Experiment D is prior evidence only. History: drafts v1-v3
(c765876, 773afe0, 4ae375b); decisions D1-D3 recorded 2026-10-18 (section 11).

## 1. Question

M1 rests on one premise: *a small execution-critical state (2.67 MiB) is enough to resume generation at once, and the
stream returns to the uninterrupted one after the late-arriving Sink binds.* W tests it across 20 inputs and measures,
without migration, how often the Sink changes (adaptive promotion), the scope limit of single-version restoration.
Three outcomes are kept apart: TTFO stability, visual rejoin, Sink-version stability. **Limitation stated in advance:**
the harness repeats short clips, so W does not establish Sink stability of long-form video; within-clip statistics are
reported only where measurable.

## 2. Prior evidence (recorded predictions only)

| source | observation |
|---|---|
| ExpD G1, generalization (1 Gbps) | TTFO 0.675 s (dog), 0.67-0.72 s (bird, boxing; seeds 0-1); rejoin 3.58 s / 6 calls (dog), 7.7-9.6 s (bird), 3.6-4.8 s (boxing) |
| state ablation (2026-10-06/09) | without the Sink ~19-20 dB; rejoin stretches with the adaptive-refresh rate |
| ExpD scope audit | dog shows no promotion in the measured window; bird and boxing promote after bind |
| loop audit (2026-10-18) | dog cuts at calls 19, 39, 59, ...: ExpD's dog restoration window contained a cut (call 39); recorded, ExpD unchanged |

## 3. Workloads, units, input feeding

- **20 workloads:** dog (`examples/original.mp4`, "A dog walks on the grass, realistic"), bird, boxing, train (repository
  clips and prompt files) and the 16 LOVEU-TGVE-2023 videos of `loveu_selection.csv` (DAVIS 5, Videvo 6, YouTube 5, each
  with its selected edit caption). Seeds 0 and 1: **40 units**. k = 2, 1 Gbps, model input 480x832 with the existing
  preprocessing (LOVEU 480x480 is stretched to 480x832 by the existing loader; primary, unchanged). Groups: repo;
  LOVEU 32-frame (11); LOVEU 128-frame (5).
- **Feeding (code-audited):** the clip is repeated end-to-end (hard cut); the session starts from frames 0-4; call c gets
  frames [5 + 4c, 9 + 4c) of the repeated tensor; output at call c = input chunk c - 1. **Cut call** = a call whose input
  contains a repeated-tensor frame f > 0 with f mod T = 0; **boundary-adjacent** = a cut call and the 2 calls after it;
  other calls are **within-clip**: **first-pass** if all input frames have index < T, else **repeated-input**. Per
  workload: `loop_audit.json`.

## 4. W1 - Sink stability (no migration)

- One run per unit: calls 0-329 of the unmodified pipeline on one GPU (`Runner.start()` + `step(c)`, fed as above).
- Logged per call: sink-slot positions; per layer and sink slot, a fingerprint of the **value** cache (float64 sum of the
  slot's value tensor; values are not RoPE-rotated, so a t_refresh realignment does not change them); the call class.
- **Promotion** = a call c >= 1 at which any layer's sink-slot value fingerprint differs from call c - 1 (call 0 and the
  first batch fill the 3 slots; filling is not a promotion). A promotion is a **version change**.
- **Reported per unit and per group, each with numerator and denominator:** (a) first-pass within-clip promotions per
  100 first-pass within-clip calls (calls 1 .. end of first pass; counts only below 10 calls); (b) repeated-input
  within-clip promotions per 100 repeated-input within-clip calls in 30-329; (c) loop-boundary-associated promotions
  (at boundary-adjacent calls in 30-329) and the boundary promotion probability (share of cut calls followed by >= 1
  promotion in their adjacency window).
- **P_w** (w = 6, 25, 52 calls): *as fed* = share of trigger calls c in [30, 330 - w] with a promotion in [c, c + w];
  *within-clip* = the same over windows without a boundary-adjacent call, computed only where >= 10 such windows exist,
  otherwise "not measurable" (`loop_audit.md`).
- **Scope classification (rule):** a unit is single-version stable at w if P_w <= 0.05 (judgment value), separately for
  as-fed and within-clip P_w. The dog units' as-fed result is used by R (`../expR/preregistration.md` section 6).

## 5. W2 - migration and continuity

- Scenario A shape: one move A -> B at trigger call **M = 34** (chosen from the loop arithmetic alone: no workload's
  trigger is a cut or boundary-adjacent call; at ExpD's M = 30 every LOVEU clip has a cut in the first post-migration
  call; no W result existed). Loop cuts still occur during restoration: trigger -> ~26-call bind: 3 cuts (32-frame
  clips), 2 (dog), 1 (train), 0 (128-frame, bird, boxing); within the horizon: 12, 5, 6, 3, 2.
- Policies: **OTTER event-driven** (`reuse_dyn`; single move: M1 + Sink restoration) and **Cold restart** (`cold`) as
  the control. Warm destination, 1 Gbps. One run per (unit, policy): **80 runs**.
- **Horizon:** the destination generates through call M + 99 = 133 (100 post-trigger calls), whatever the rejoin;
  `post_chunks` = 130, `max_run_s` = 600.
- **Reference and alignment:** the destination node's uninterrupted baseline (calls 0-163; same model, seed, per-call
  noise seed `seed x 100003 + c + 1`, repeated input tensor), cached per configuration. The source runs calls 0..M-1 and
  hands off; the destination continues at the source's next call index c0 (recorded); call c of the run is compared with
  call c of the reference (same input chunk, noise and lag). PSNR(c) = mean over the chunk's 4 output frames of
  10 log10(1 / MSE) on RGB in [0, 1] at 480x832 (99 dB if identical); SSIM on the last frame.
- **Rejoin (primary rule, = ExpD):** the first call c >= the bound call b with PSNR(c) >= 35 dB; a single crossing is a
  success; no crossing by call 133 = right-censored. Cold restart has no bind: "Cold reaches 35 dB" = any call in
  34-133 with PSNR >= 35 dB.
- **RVC (diagnostic):** a promotion in the **reference** (value fingerprints logged in the node baseline) at a call in
  [c0, b]; each RVC event is recorded with its call, calls before bind and whether it is boundary-adjacent
  (*cut-induced*) or not (*within-clip*). A unit with any cut-induced RVC is "cut-RVC"; RVC is never a failure and never
  an exclusion from the primary analysis.

## 6. Metrics and per-unit report

TTFO (s); service time (median per run); rejoin success; rejoin calls (b -> c) and rejoin delay (s) or censored;
sustained rejoin = first c >= b starting 10 consecutive calls >= 35 dB, censored if none starts by call 124; final-call
PSNR (call 133); median PSNR of calls 124-133; minimum PSNR after the first crossing; RVC events; cut calls between c0
and the rejoin (or 133); for Cold restart the same PSNR fields and "reaches 35 dB".

## 7. Confirmatory hypotheses

| item | W-H1 TTFO stability | W-H2 rejoin within the horizon | W-H3 rejoin depends on the Sink |
|---|---|---|---|
| 1 question | does execution resume as fast for every input? | does the output return to the reference after bind? | is the 35 dB rejoin due to the restored Sink rather than input-driven convergence? |
| 2 unit | workload (20) | unit (40) | unit in which OTTER rejoins |
| 3 independent variable | workload | workload, seed | policy (OTTER vs Cold restart) |
| 4 primary metric | TTFO of the OTTER run (s) | rejoin success (single crossing, section 5) | Cold restart reaches 35 dB within calls 34-133 |
| 5 success | every workload's TTFO (mean of its two seeds) <= 1.0 s **and** max - min of the 20 workload values <= 0.25 x the median service time of all OTTER runs | rejoin success in >= 80 % of **all 40 units** | Cold reaches 35 dB in <= 20 % of the units in which OTTER rejoins |
| 6 failure | any workload > 1.0 s, or spread > 0.25 service time | < 80 % | > 20 % |
| 7 NOT EVALUABLE | > 2 workloads without any valid OTTER run | > 4 units without a valid OTTER run | > 10 % of the qualifying units without a valid Cold run, or < 10 qualifying units |
| 8 aggregation | per workload: mean of the two seeds' TTFO (= their median); a workload with one valid run uses it | share over units; censored = no success | share over qualifying units |
| 9 repetitions | 2 seeds x 1 run | 1 run per unit (re-runs per common section 3) | 1 Cold run per unit |
| 10 artifacts | run dirs (`summary.json`, `events.csv`, `metrics.csv`, node logs); `w2_table.csv` per unit; aggregate JSON / MD | same + KM data | same |

Threshold origins: 1.0 s = G1 (frozen 2026-10-16, before ExpD ran); 0.25 call, 80 %, 20 % = judgment values. Recorded
predictions: W-H1 supported; W-H2 uncertain; W-H3 supported for dog, unknown elsewhere.

**Secondary analyses of W-H2 (reported next to the primary, never replacing it), with N and excluded counts stated:**
S1 = units without any RVC; S2 = units without a cut-RVC. Same 80 % rule; with fewer than 10 units, counts only.

## 8. Descriptive analyses (no pass / fail)

Kaplan-Meier curves of rejoin calls (censored at 133) overall, per group and per RVC class; share rejoined within 8
calls (ExpD G2's bound as a reference line); W1 promotions by cause, boundary promotion probability, P_w as fed and
within-clip; rejoin calls against cuts between c0 and rejoin and against motion score (Spearman, units listed); PSNR /
SSIM trajectories with cut calls marked; units where Cold reaches 35 dB listed as non-discriminating.

## 9. W-AR - exploratory crop-based preprocessing sensitivity (not in any verdict)

- Four videos: within each LOVEU frame-length group, sorted by motion score, positions floor((j + 0.5) n / 2), j = 0, 1
  (32-frame: positions 2, 8; 128-frame: positions 1, 3), each with its selected prompt; seed 0.
- Variant input: center band of rows 102-377 (276 x 480) of the original, lossless H.264 (qp 0), outside version control;
  the unchanged loader scales it to 480x832 (model input resolution unchanged); originals untouched. Fidelity of the
  re-encode (PSNR vs the cropped frames) reported.
- Runs: W1 + W2 (both policies) on the variant = 12 runs; paired against the same units' primary runs.
- Reported as a **crop-based preprocessing sensitivity**: the crop removes 42 % of each frame's content, so it does not
  isolate aspect-ratio distortion.

## 10. Validity and scope

Common section 3. In W2 an owner-side version event before bind cannot occur (the source stops at the handoff; B's
refresh is frozen until bind). Loop cuts are a harness property, identical in run and reference; marked and analysed,
not removed. PSNR against the reference measures continuity, not perceptual quality. No LOVEU frame appears in a
publication figure until its reuse permission is established.

## 11. Decisions (recorded 2026-10-18, before any W data)

D1 M = 34 (loop arithmetic). D2 W-H2 primary over all 40 units; S1, S2 secondary; RVC diagnostic. D3 W-AR center-band
crop, exploratory, 480x832.

## Amendment 1 (2026-10-19, after the GPU shakedown, before any W measurement run; the frozen text above is unchanged)

**Correctness of the promotion definition (section 4).** The frozen text says call 0 and the first batch fill the 3 sink
slots, so promotions are counted from call 1. The GPU shakedown (mbike-trick seed 0, W1, commit c240ff7) shows that the
third slot is written at **call 1**: at call 1 the value fingerprint of slot 2 changes in all 30 layers while every
slot position stays [0, 1, 2], and nothing changes at calls 2-3 (with the 2-step Stream Batch, chunk 0's keys / values
are committed one call later). Counting call 1 would classify sink filling as a promotion in every unit.
**Correction:** promotions are counted from **call 2** on; the first-pass within-clip denominator is calls 2 .. end of
first pass. Nothing else changes (P_w and its windows start at call 30; RVC is evaluated at calls >= c0 = 34; owner-side
detection compares calls within one ownership of a transferred Sink). Implemented in `tools/eval/expw_w1.py` (analysis
only; the recorded fingerprints are unchanged). Observation, not a rule change: a single refresh can change fingerprints
on two consecutive calls (the two Stream-Batch rows are written one call apart, e.g. calls 4-5); the frozen per-call
definition is kept, and runs of consecutive changed calls are reported descriptively next to it.
