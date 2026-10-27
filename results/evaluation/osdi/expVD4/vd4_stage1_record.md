# VD-4 stage 1 record (2026-10-27)

Written after the stage-1 inspections were recorded (ca59da94), the keys copied (c108db0d) and the aggregate computed
(ff8dd2b1), before stage 2 was started. Nothing frozen was modified for this record: not `preregistration.md`,
`vd4_schedules.json`, VD-3's `vd3_thresholds.json` (SHA-256 792a6ac77ffbca24), the two inspection forms and their
recorded copies, the keys, or `aggregate_vd4.py`'s inspection / resolution / attribution / correspondence logic
(unchanged since the freeze f7730207). Sections 2-3 are descriptive readings of the recorded material; they recompute
nothing and change no result.

Stage 1 ran B0, A1, D, R, DR on the 12 confirmation cells (6 inputs x OT-1 / OT-L): 60 runs, 60 / 60 valid (every
frozen check, every supplemental check, G3), no duplicate control across the two sessions. The A1 runs are the
row-wise implementation validated in stage 0a2; the stage-0 A1 runs are preserved as `VD4x-A1.stage0`.

## 1. Formal preregistered results (frozen rules; `vd4_results.md`)

| condition | P1 numeric | P1 flags (REF) | P2a numeric | P2b numeric | P3 | resolution |
|---|---|---|---|---|---|---|
| B0 | 11 / 12 | 3 (0) | 6 / 12 | 3 / 12 | 12 / 12 no harm | none |
| A1 | 11 / 12 | 4 (0) | 6 / 12 | 3 / 12 | 12 / 12 no harm | none |
| D | 10 / 12 | 3 (0) | 6 / 12 | 3 / 12 | 12 / 12 no harm | none |
| R | 12 / 12 | 0 (0) | 6 / 12 | 2 / 12 | 12 / 12 no harm | **P1 STRICT** |
| DR | 12 / 12 | 0 (0) | 6 / 12 | 3 / 12 | 12 / 12 no harm | **P1 STRICT** |

P2a and P2b carried no visual flag on any clip of any condition (see section 3); their non-resolution is numeric.

- **R and DR achieve P1 STRICT**: V1 at the reset <= REF P99 in 12 / 12 cells and no "boundary jump at M" flag on any
  of their 12 clips (REF: 0 flags in the same sessions).
- **A1 and D do not resolve P1**: A1 11 / 12 numeric (dog s1 OT-L, V1 3.999 > P99 3.908) with 4 flags; D 10 / 12
  (audi s1 OT-L 3.41 > 3.22, audi s0 OT-L 3.12 > 2.84) with 3 flags; B0 11 / 12 (audi s0 OT-L 2.97 > 2.84) with 3
  flags. A1 is B0's numeric twin (V1 within +-0.3 on every cell, one cell gained, one lost).
- **No condition resolves P2a or P2b.** P2a fails on the four train cells and the two butterfly cells for every
  condition (6 / 12 each); P2b passes only on audi cells (B0, A1, D, DR 3 / 12; R 2 / 12 - R breaks audi s0 OT-1, dO
  +11 %).
- **Attribution (frozen rule):** P1 - sufficient single state R; "decoder + recent jointly sufficient" false (R alone
  resolves); not explained by the tested states: false. P2a, P2b - no sufficient single state, DR does not resolve,
  "not explained by the tested states" true. D alone is not sufficient for any phase.
- **Bytes added (oracle payload; idealized transfer lower bounds at 1 / 10 Gbps, not a migration latency):** D 1888.6
  MB (15.1 / 1.51 s), R 1725.6 MB (13.8 / 1.38 s), DR 3613.8 MB (28.9 / 2.89 s), B0 / A1 0.4 MB.
- **Paired comparison vs B0 (numeric, descriptive):** R and DR lower V1 on all 12 cells (DR lowest on every cell); D is
  inconsistent (lower on 7, higher on 5, two new P1 failures); A1 within +-0.3 of B0.

## 2. Exploratory visual observations (recorded material read after unblinding; not scored by the rule)

Detail in `vd4_stage1_exploratory_notes.md`.

**2.1 The audi "car drives backward at M" notes.** The notes column is not scored. The note appears on the reset clips
of the two audi OT-1 cells and nowhere else: audi s1 OT-1 (stage1b): B0, A1, D, **R, DR**; audi s0 OT-1 (stage1a):
B0, A1, D (not R, DR). It is absent on all four audi REF clips and on all audi OT-L clips. On every noted clip the
scored fields read `natural` (motion) and `no visible jump` (boundary at M): the note is an **unscored motion
anomaly**, distinct from a formal jump flag, and R's / DR's P1 STRICT on these cells is a scored-field result that
carries this note as a caveat. An unblinded re-watch by the same rater (input clip: forward only; audi s1 OT-1 REF
forward; **R forward**; B0 backward) contradicts the blinded note on R; the blinded note is not withdrawn and the two
observations are not reconcilable from the record. The anomaly is absent from the input and from REF, so it is tied to
the reset at M in the OT-1 schedule on this input, not to the input or the model alone; whether R / DR remove it is
**open**.

**2.2 Formal jump flags vs unscored anomalies.** P1 counts only the field "boundary jump at M". The 10 jump flags fall
on train (s0 OT-1: B0, A1, D; s0 OT-L: B0, D; s1 OT-1: A1, D), dog (s1 OT-1: A1; s1 OT-L: A1) and audi s0 OT-L (B0).
Numeric P1 and the flags agree only partly (exploratory 2 x 2 over the 60 scored clips): numeric fail and flagged 2;
numeric fail, not flagged 2 (both D on audi OT-L); numeric pass and flagged 8 (train and dog cells, where V1 sits far
below the inputs' high P99 of 6.2-6.5 and 3.9); both clean 48.

**2.3 The train sharpening notes.** Six of the train jump flags carry the note "the jump doesn't mean the resolution
is broken; it just makes the guy look clearer at M" (train s0 OT-1: B0, A1, D; train s0 OT-L: D; train s1 OT-1: A1,
D); four others carry "a jump at M is not too bad" (dog s1 OT-1 A1, dog s1 OT-L A1, audi s0 OT-L B0, train s0 OT-L
B0). The rule counts each as a flag; the notes qualify them as an apparent sharpening at the migration call rather
than a break of continuity. This qualification is the rater's description and does not change the counts.

## 3. Correspondence-analysis limitations

- **REF omitted.** The preregistration's correspondence analysis is "over every inspected clip (REF and B0 included)";
  the frozen aggregator counts the clips of conditions that have numeric rules (B0, A1, D, R, DR: 60 clips) and leaves
  the 12 REF clips out. REF carried no flags in any field, so the flag columns would not change; the counts are
  nevertheless not the preregistered population. This is reported, not corrected.
- **Degenerate kappa.** Every P2a (identity, appearance, color), P2b (flicker, motion) and P3 (jump at B) field is
  unflagged on all 72 clips. The tables are P2a: metric fail & flagged 0, metric fail & not flagged 30, metric pass &
  flagged 0, both clean 30; P2b: 0 / 46 / 0 / 14. With zero visual flags kappa is 0 by construction; it is not evidence
  of agreement or disagreement between the metrics and the rater and must not be cited as either.
- The frozen analysis is **not recomputed or changed** post hoc; any re-analysis including REF or a different flag
  definition would be a new, separately preregistered analysis.

## 4. Interpretation

- Under oracle restoration, **R (the recent KV) is sufficient for the preregistered P1 criterion**: restoring the
  source's recent KV at the reset keeps the reset spike within REF's P99 on all 12 cells with no formal jump flag. DR
  does the same; D alone does not.
- This **does not establish complete perceptual continuity** (the audi motion anomaly is unresolved under R; the
  flags are one rater's observations; zero flags is not zero risk), **nor necessity** (VD-4 tests sufficiency of
  added oracle state, never that R is required), **nor practical migration feasibility** (R is 1.73 GB of state
  delivered as an oracle; whether it can arrive in time is outside VD-4).
- **P2a and P2b remain unresolved** by every tested state (B0, A1, D, R, DR); the late-window drift and warp /
  frame-difference criteria fail on the train and butterfly inputs for every condition, and R worsens P2b on one audi
  cell. Stage 2 tests whether the Sink slots (S3) change this.

## 5. Stage 2 (approved 2026-10-27; frozen schedule)

S3 (all oracle Sink slots) on the 12 confirmation cells (B0 reused by `--skip_done`), metrics, checks, and the blinded
session `stage2` (REF, B0, S3: 36 clips). Stage 2b and stage 3 need explicit approval after the stage-2 inspection is
recorded and aggregated. Thresholds and attribution rules unchanged; stage-1 results and inspection decisions preserved.
