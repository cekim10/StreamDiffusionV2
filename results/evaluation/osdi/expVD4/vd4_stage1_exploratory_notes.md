# VD-4 stage 1: exploratory notes after unblinding (not part of the preregistered procedure)

Status: descriptive. Nothing here changes the recorded inspection forms (`vd4_inspection_stage1a.md`,
`vd4_inspection_stage1b.md`, commit ca59da94), the keys, `vd4_results.*` (ff8dd2b1) or any frozen VD-4 document. The
resolution of every (condition, phase) stands as computed from the recorded form fields by the frozen rule.

## 1. The free-text note "car drives backward at M" (audi-snow-trail)

The form's notes column is not scored by the frozen rule (only the seven fixed fields are). After unblinding, the note
appears on these clips and on no other input:

| cell | REF | B0 | A1 | D | R | DR |
|---|---|---|---|---|---|---|
| audi s1 OT-1 (stage1b cell 01) | - | noted | noted | noted | noted | noted |
| audi s0 OT-1 (stage1a cell 02) | - | noted | noted | noted | - | - |
| audi s1 OT-L (stage1a cell 01) | - | - | - | - | - | - |
| audi s0 OT-L (stage1b cell 02) | - | - | - | - | - | - |

On every one of these clips the scored fields are `natural` (motion) and `no visible jump` (boundary at M), so the note
did not count as a flag. In particular R's and DR's **P1 STRICT** on these cells is a scored-field result; the note is
reported next to it as a caveat whose cause is undetermined by the blinded record.

## 2. Unblinded re-watch by the same rater (2026-10-27; exploratory, not blinded)

Question raised by the rater: the audi input shows a partly visible car on a snow trail, so the reversed motion could
be a property of the input or of StreamDiffusionV2 itself rather than of the reset. The rater then watched, knowing
the labels:

- the input clip `data/loveu_tgve_2023/audi-snow-trail.mp4` (LOVEU, internal only; 128 frames at 14 fps, looped
  during the runs): the car **only drives forward**;
- audi s1 OT-1, REF (`715610`): forward at M;
- audi s1 OT-1, R (`EEA399`): **forward at M** - this contradicts the blinded note on the same clip;
- audi s1 OT-1, B0 (`973075`): **backward at M** - consistent with the blinded note.

Readings:
- The reversed motion is **not in the input** and was not seen in REF, in either the blinded or the unblinded
  viewing. On the evidence available it is tied to the reset at M in the OT-1 schedule, on this input, not to the input
  or the model alone. Whether it is a reset effect that some states remove (B0 shows it, R may not) is **open**: the
  blinded record says R shows it, the unblinded re-watch says it does not, and these two observations cannot be
  reconciled from the record.
- The unblinded re-watch is the weaker of the two observations: the rater knew that `EEA399` is R and that R resolved
  P1, so expectation bias cannot be excluded. It is recorded here as an observation, not as a correction of the form.
  The blinded note is not withdrawn.
- The observation is from one rater on one cell; it is not a measurement and no numeric metric in VD-3 / VD-4 is
  sensitive to the direction of motion (warp and frame-difference metrics are direction-blind).

## 3. If this question matters for the paper

A resolution would need a **new blinded viewing** of the audi OT-1 clips (both seeds; REF, B0, A1, D, R, DR; fresh
codes and order from a new seed), with "direction of motion at M (forward / backward / unclear)" as a scored field, by
the same rater and, ideally, a second one. That is a new preregistered addendum, not a re-scoring of stage 1; it would
be run only with explicit approval and would not alter the stage-1 record. Until then the paper text should say: the
reversed motion was noted on the reset clips of the audi OT-1 cells and not on REF or the input; its presence under R
is unresolved between the blinded note and an unblinded re-watch.

## 4. Other notes not scored by the rule

- train s0 OT-1 (B0, A1, D), train s0 OT-L (D), train s1 OT-1 (A1, D): "the jump doesn't mean the resolution is
  broken; it just makes the guy look clearer at M" - these ARE scored as `jump` flags (P1) by the rule; the note
  qualifies the flag as a sharpening, not a break.
- dog s1 OT-1 (A1), dog s1 OT-L (A1), audi s0 OT-L (B0), train s0 OT-L (B0): "a jump at M is not too bad" - scored as
  `jump` flags.
- No clip of any session carried a flag in the P2a (identity / appearance / color), P2b (flicker / motion) or P3 (jump
  at B) fields; the P2 correspondence tables therefore have zero visual flags and kappa 0 is degenerate, not evidence of
  disagreement or agreement.
- The correspondence tables count the five scored conditions (60 clips); the preregistration said "REF and B0
  included". REF carries no flags, so the flag columns would not change; noted as a difference between the aggregator
  and the text.

## 5. Noted before the stage-2 inspection (2026-10-27, after the S3 runs, before any stage-2 form was filled)

Numeric stage-2 outcome (frozen rules): S3 P1 10 / 12, P2a 11 / 12, P2b 11 / 12, P3 12 / 12. Two consequences of
the frozen design are recorded here before the inspection so that they are not read as post-hoc interpretation:

- **The frozen resolution rule needs 12 / 12 numeric passes.** S3's P2a (fails butterfly s1 OT-L on R3's late-window
  clause: late D_c -0.028 < -t_DINO -0.027; X_late +0.022 passes) and P2b (fails dog s1 OT-1 on the warp clause:
  eO - eR +0.59 > 0.10 x eR = 0.27) each miss by one cell, so by the frozen rule S3 cannot be STRICT or NEAR for P2a or P2b whatever the
  inspection shows; `s3_resolves_p2` will be false and stage 2b takes its "S3 did not resolve" form (S1, S2, A1S1,
  A1S2 on the four-cell subset) and stage 3 does not run. The rule is not changed; 11 / 12 is reported descriptively.
- **The stage-2 session shows REF and B0 again (preregistration section 5: "stage2: REF, B0, S3").** The aggregator
  reports any control inspected in two sessions under `duplicate_controls` ("protocol error", section 4). Both are
  frozen; the section-5 design requires per-session REF baselines, so the stage-2 REF / B0 entries will appear in
  that list by construction. Nothing is counted twice: each (cell, condition) keeps its first session, and S3's
  baseline is the stage-2 REF of the same cell. The list is a reporting artifact of the frozen design, not a protocol
  error, and the code is not changed.
- Stage 2 made 9 new S3 runs; the S3 runs of the three stage-0 confirmation cells (train s0 OT-1, dog s1 OT-1, audi s1
  OT-1) are the stage-0 runs reused by `--skip_done` (as the preregistered count of 9 says). They carry the frozen
  checks only (no supplemental `checks_supp`, which were introduced for A1 / D / R in addendum 1 and do not gate S3).

## 6. Noted before the stage-2b inspection (2026-10-27, after the S1 / S2 / A1S1 / A1S2 runs, before any stage-2b form was filled)

Stage 2b ran the "S3 did not resolve P2" branch (preregistration section 5): S1, S2 and the exploratory A1S1, A1S2 on
the four-cell subset (dog s1 OT-1, train s0 OT-1, butterfly s1 OT-1, audi s1 OT-1), 16 new runs on host D at 99d08937
(preflight clean), B0 reused. All 16 are valid: the frozen oracle checks and the supplemental checks are true on every
run, G3 passes on all four units, the prefix is identical to REF and the resets / binds were realized as scheduled.
Bytes: S1 575.5 MB (one slot; 4.6 / 0.46 s idealized at 1 / 10 Gbps), S2 1150.6 MB (two slots; 9.2 / 0.92 s), S3
1725.6 MB. The aggregate (acf2e975) leaves every stage-1 and stage-2 block identical (B0, A1, D, R, DR, S3 numeric and
condition blocks, attribution, correspondence, the duplicate-controls list); the only other change is the host path
recorded under `root` of the stage-0 supplemental / batch / A1 blocks, because this aggregate ran on elves-01.

Three consequences of the frozen design, recorded before the inspection:

- **The frozen resolution rule cannot be met on the four-cell subset.** `resolution()` requires `of == 12` numeric
  passes; the stage-2b conditions have four cells, so S1, S2, A1S1 and A1S2 will read "not resolved" after the
  inspection whatever it shows. This is by construction: the preregistration calls this branch a "non-monotonicity
  check", and S1 / S2 on the 12 cells belonged only to the "S3 resolved" branch. The rule is not changed; the stage-2b
  outcome is descriptive (numeric per cell, and the blinded flags against the same session's REF).
- **Numeric outcome (frozen rules, four cells).** P1 4 / 4 and P3 4 / 4 for B0, S1, S2, S3, A1S1 and A1S2 (V1 at the
  reset 1.05-3.58 against REF P99 1.25-6.49). P2a: B0 2 / 4 (train D_c -0.056 < -0.036 and late D_c -0.044; butterfly
  D_c -0.086 < -0.047 and late -0.091), S1 3 / 4 (butterfly: D_c -0.068 and late D_c -0.083, both < -0.047), S2 4 / 4,
  S3 4 / 4; A1S1 passes S1's cells, A1S2 S2's. P2b: B0 1 / 4, S1 1 / 4, S2 1 / 4 (audi only), S3 3 / 4 (dog: warp
  excess +0.59 > 0.27 and frame difference 1.117 x REF). S1 / S2 fail P2b on dog (warp +0.55 / +0.49 > 0.27; frame
  difference 1.166 / 1.165 x), train (warp +0.72 / +0.86 > 0.68; frame difference 1.171 / 1.191 x) and butterfly (warp
  passes, +0.22 / +0.18 < 1.14; frame difference 1.114 / 1.109 x against the 1.10 limit). On these cells S2 matches S3
  on P2a and S1 misses by one cell; on P2b neither partial set approaches S3.
- **The stage-2b session shows REF and B0 of the four cells a third time** (stage1a / 1b, stage2, stage2b).
  `duplicate_controls` will grow by eight entries by construction; nothing is counted twice, each condition's baseline
  is the stage-2b REF, and the three viewings of the same control clips can be read as a test-retest only
  descriptively (stage-2 record section 3.2: the counts are not on a common scale across sessions).

Monotonicity across B0 -> S1 -> S2 -> S3 (descriptive; a slot-set effect, not a slot-count effect, preregistration
section 3):

- Monotone toward REF on all four cells: the whole-window D_c (dog -0.017 / -0.011 / -0.005 / -0.001; train -0.056 /
  -0.033 / -0.020 / -0.008; butterfly -0.086 / -0.068 / -0.036 / -0.005; audi -0.089 / -0.080 / -0.063 / -0.005) and
  the late-window D_c (audi S1 -0.024 equals B0's -0.023 within 0.001). V1 at the reset is flat (within 0.2 of B0 on
  every cell): the Sink slots do not touch the reset spike, as in stage 2.
- Not monotone: the warp excess eO - eR on all four cells (dog +0.69 / +0.55 / +0.49 / +0.59; train +1.01 / +0.72 /
  +0.86 / +0.26; butterfly +0.54 / +0.22 / +0.18 / +0.40; audi -0.43 / -0.34 / -0.46 / +0.41): S3 sits above S2 on dog,
  butterfly and audi, S2 above S1 on train. Also the frame-difference ratio on train (1.226 / 1.171 / 1.191 / 1.030)
  and audi (0.942 / 1.012 / 1.042 / 0.991); dE_cross on dog (1.17 / 1.09 / 1.32 / 0.49); C_c on dog (0.78 / 0.82 /
  0.79 / 0.46) and audi (0.007 / 0.072 / 0.083 / 0.095, all far below t_dE 4.86); X_late on butterfly (+0.002 / +0.027
  / +0.008 / -0.012, S1 raising the late excess above B0's). On the frame-difference ratio S3 is the only set within
  10 % on train and butterfly.
- Reading, pending the inspection: the content drift improves with each slot set in the fixed order, the motion / warp
  quantities do not; S3's P2b gain over S2 (frame difference 1.19 -> 1.03 on train, 1.11 -> 1.03 on butterfly) comes
  with slot 0 and is not foreshadowed by S1 or S2. Whether that is the slot's identity (slot 0, the oldest) or the
  count is not separable here (section 3 of the preregistration).

A1S1 / A1S2 (exploratory): the rule outcomes equal S1's / S2's on every cell; the values shift both ways (C_c lower
on dog and train, the warp excess higher on butterfly: +0.56 for A1S1 against S1's +0.22). On dog the layer-0 A1
deltas are [0, 0] (the prepare's TS positions already equal the source's) and the recorded checks state that
zero-delta rows are unchanged (`a1_zero_delta_rows_unchanged`); to the extent the alignment is then the identity, the
dog pairs A1S1 / S1 and A1S2 / S2 are same-configuration repeats and their differences (V1 0.08 / 0.07, D_c 0.0003 /
0.0002, C_c 0.33 / 0.22, dE_cross 0.01 / 0.03, warp excess 0.03 / 0.05, frame-difference ratio 0.002 / 0.005) give a
run-to-run scale for reading the other differences. Two pairs on one cell: a scale, not a noise model.

After the inspection the frozen aggregate adds the stage-2b flags (REF baseline of the same session); the stage-2b
record will keep the formal "not resolved" outcomes apart from these descriptive readings.
