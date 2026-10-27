# VD-4 stage 2 record (2026-10-27)

Written after the stage-2 inspection was recorded (897f1d50, merged 5ffdd30d), the key copied (ba3ed8f8) and the
aggregate computed. Nothing frozen was modified: not the preregistration, schedules, thresholds (SHA-256
792a6ac77ffbca24), the inspection forms or their recorded copies, the keys, or the aggregator's inspection /
resolution / attribution / correspondence logic. The stage-1 results and inspection decisions are unchanged (numeric
and validity blocks identical before and after this aggregate). Sections 2-3 read the recorded material
descriptively; they recompute nothing.

Stage 2 ran S3 (all three Sink slots restored from the source, 1725.6 MB; idealized transfer 13.8 / 1.38 s at 1 / 10
Gbps) on the 12 confirmation cells: 9 new runs plus the three stage-0 S3 runs reused by `--skip_done` (as
preregistered); 12 / 12 valid (frozen checks, G3), B0 reused from stage 1. The blinded session `stage2` showed REF,
B0 and S3 of every cell (36 clips, one rater).

## 1. Formal preregistered results (frozen rules)

| condition | P1 numeric | P1 flags (REF, same session) | P2a numeric | P2b numeric | P3 | resolution |
|---|---|---|---|---|---|---|
| S3 | 10 / 12 | 7 (1) | 11 / 12 | 11 / 12 | 12 / 12 no harm | **none** |

- **S3 resolves no phase.** P1: 10 / 12 numeric (audi s0 OT-L V1 3.03 > P99 2.84; dog s1 OT-L 4.01 > 3.91 - the
  same two cells as B0 / A1 / D fail) and 7 jump flags against REF's 1. P2a: 11 / 12 (butterfly s1 OT-L fails R3's
  late-window clause, late D_c -0.028 < -0.027). P2b: 11 / 12 (dog s1 OT-1 fails the warp clause, eO - eR +0.59 >
  0.27). The rule requires 12 / 12; both P2 phases miss by one cell, as noted before the inspection
  (`vd4_stage1_exploratory_notes.md` section 5). No P2a / P2b / P3 field was flagged on any stage-2 clip.
- **Attribution unchanged:** P1 - R sufficient (stage 1); P2a, P2b - not explained by the tested states (B0, A1, D,
  R, DR, S3). The Sink-slot result is reported for the slot set S3 (all slots); it is not attributed to the number of
  slots.
- **Gates:** `stage2_inspected` true, `s3_resolves_p2` false, so stage 2b takes its "S3 did not resolve" form (S1, S2,
  A1S1, A1S2 on the four-cell subset dog s1 OT-1, train s0 OT-1, butterfly s1 OT-1, audi s1 OT-1: 16 runs, about
  0.9 GPU h, session stage2b with 24 clips) and **stage 3 does not run**. Stage 2b needs explicit approval.
- `duplicate_controls` lists the 24 stage-2 REF / B0 entries: by construction of the frozen section-5 design (noted
  before the inspection); nothing is counted twice and S3's baseline is the stage-2 REF of the same cell.

## 2. Paired comparisons (numeric; descriptive)

S3 against B0 on the 12 cells: V1 within +-0.4 of B0 on every cell (S3 restores no recent KV, so the reset spike is
B0's; R / DR lower it on all 12). In the Sink-less window S3 moves every P2 quantity toward REF on every cell: D_c from
-0.011..-0.086 (B0) to -0.008..+0.001; C_c and dE_cross lower on 12 / 12; frame-difference excess over REF from +11
..+23 % (B0) to -2..+12 % (lower on 11 / 12; audi s1 OT-1 +0.5 pt); the warp excess lower on 11 / 12 (dog s1 OT-1 the
exception, still failing). R and DR leave these quantities at B0's level. Numerically P1 and P2 are addressed by
different states (R: P1 only; S3: P2 nearly, P1 not); no condition addresses both, and none meets the frozen
12 / 12 bar for P2.

## 3. Visual findings (exploratory; recorded form fields and notes read after unblinding)

**3.1 P1 flags in stage 2.** 18 of 36 clips carry a jump flag: B0 10 / 12, S3 7 / 12, REF 1 / 12 (audi s1 OT-L).
Within the session S3 is flagged on no cell where B0 is not (both flagged 7, B0 only 3: dog s1 OT-L, audi s1 OT-1,
audi s0 OT-1; neither 2: both butterfly cells). Exploratory 2 x 2 for S3 (numeric P1 vs flag): fail & flagged 1 (audi
s0 OT-L), fail & not flagged 1 (dog s1 OT-L), pass & flagged 6, both clean 4.

**3.2 Test-retest of the rater on identical clips.** The 24 stage-2 control clips (REF, B0 of every cell) are the
same videos the rater saw in stage 1 under other codes. 16 / 24 were rated identically; the 8 differences are all in
one direction - `no visible jump` in stage 1, `jump` in stage 2: B0 of dog s1 OT-1, dog s1 OT-L, train s1 OT-1, train
s1 OT-L, audi s1 OT-1, audi s1 OT-L, audi s0 OT-1, and REF of audi s1 OT-L. B0's P1 flag count on the same clips is
3 in stage 1 and 10 in stage 2. The other six fields agreed on all 24 clips. Reading: the rater's threshold for
"jump at M" was stricter in stage 2 (the session shows three clips per cell, and the notes "but the jump is not too
bad" on six of the new flags describe mild events); the stage-1 and stage-2 flag counts are therefore **not on a
common scale**, and the frozen per-session REF baseline is what keeps each session's comparison internally
consistent. Consequences: (i) stage 1's P1 STRICT for R and DR rests on 0 flags against REF 0 in sessions whose
threshold was the laxer one; whether R / DR would carry flags under the stage-2 threshold was not observed (they
were not shown in stage 2) and is **unknown**; (ii) the S3-vs-B0 difference inside stage 2 (7 vs 10) is on one
scale and is the only within-session comparison for S3; (iii) a flag count of one rater in one session is an
observation, not a measurement.

**3.3 Notes.** "car drives backward at M" appears once in stage 2: on B0 of audi s1 OT-1, consistent with the
stage-1 note and the unblinded re-watch on that clip; it was not written on S3 or REF of that cell. "But the jump is
not too bad" qualifies six of the new jump flags (B0 dog s1 OT-1, dog s1 OT-L, train s1 OT-L; S3 dog s1 OT-1, train
s1 OT-1, train s0 OT-L, train s1 OT-L). The rule counts every jump as a flag; the notes qualify them as mild.

**3.4 Correspondence (secondary, frozen tables).** P2a: metric fail & flagged 0, fail & not flagged 31, pass &
flagged 0, both clean 41; P2b: 0 / 47 / 0 / 25; kappa 0.00 in both, degenerate because no P2 field was flagged on any
of the 72 scored clips (the REF omission noted in the stage-1 record stands).

## 4. Interpretation (oracle sufficiency; not feasibility)

- Restoring the Sink slots alone (S3) does **not** meet the preregistered criterion for any phase. Numerically it
  removes nearly all of the Sink-less-window content, colour and motion excess over REF (11 / 12 cells for P2a and
  P2b) but leaves the reset spike and its visible jump (P1) at B0's level; restoring the recent KV (R) does the
  opposite. Under the frozen rules no tested state, singly or in the tested pairs (DR), resolves P2a or P2b, and
  the states that address P1 and P2 are different.
- This is a diagnosis of which oracle state suffices for which preregistered criterion. It says nothing about
  necessity, about perceptual continuity beyond the scored fields (the rater's P1 threshold moved between sessions;
  the audi motion anomaly is unresolved), or about practical migration (S3 and R are 1.7 GB each as oracles).
- Stage 2b (S1, S2 and the exploratory A1S1, A1S2 on the four-cell subset) tests whether fewer Sink slots change the
  P2 picture (non-monotonicity check); it runs only with explicit approval.
