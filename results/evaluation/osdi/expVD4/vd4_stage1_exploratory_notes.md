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
