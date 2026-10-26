# Experiment VD-3 - report (2026-10-26)

Frozen plan: `preregistration.md` (FINAL, `../expVD3_freeze.md`, 9de6258). Thresholds `vd3_thresholds.json` (set A;
SHA-256 matches the freeze). 96 candidate streams on host D (8 units x 2 schedules x 6 conditions), **all valid**, G3
pass on every unit. Blinded inspection by the user recorded and committed (7372b06) **before** the key was opened
(232a4112; the key's SHA-256 equals the one printed in the form). Aggregation `aggregate_vd3.py` ->
`vd3_results.{md,json}`. Emulator results; no testbed claim.

## 1. Verdicts (frozen rules)

| candidate | continuity | identity preservation | why (confirmation cells) |
|---|---|---|---|
| **DR2+TSin** | **NO-GO** | **NO-GO** | quantitative FAILs: P1 in 1 cell, P2a in 6, P2b in 9; inspection vetoes in 8 confirmation cells (boundary jump 7 of 16 cells, appearance 2, Sink-less drift 1) |
| **TSinKC** | **NO-GO** | **NO-GO** | as DR2+TSin plus P1 in 7 cells (V1 3.3-9.5) |

Sensitivity sets B and C: NO-GO for both candidates as well. The preregistered general claim "DR-2 + TS-in preserves
continuity across the confirmation workloads and schedules" is **rejected**.

Component and control hypotheses: **C1 SUPPORTED** (12 / 12: the combination keeps DR-2's boundary benefit and TS-in's
content benefit), **C2 SUPPORTED** (10 / 12: TS-in alone leaves the boundary jump above REF P99), **C3 SUPPORTED**
(12 / 12: the correct latent history beats the stale and the noise decoder caches, so DR-2's effect is attributed in
part to temporal information), **C4**: TSinKC (the prepare's own cache) does not fix the boundary (P1 fails in 7 of
12 cells), consistent with C3.

## 2. Where continuity fails (DR2+TSin; phase by phase, confirmation cells)

**P1 boundary.** Quantitatively restored in 11 of 12 cells (V1 0.79-3.16 vs REF P99 1.25-6.49; ratio to frozen M1
0.35-0.55); fails on audi s0 OT-L (2.97 vs 2.84). **Visually not restored**: the user saw a jump at M in 7 of 16 DR2+TSin
clips (frozen M1: 16 of 16; REF: 2 of 16, the inspection's own false-positive rate). REF's P99 of V1 is not a
perceptual threshold: a jump under it is still visible in about half the cells.

**P2a content / appearance.** The Sink-less content gap to REF closes 40-97 % (DINO D_c -0.011 to -0.089 vs frozen M1
-0.137 to -0.444), and the late window shows no excess drift. It still fails:
- train (4 / 4 cells): D_c -0.042 to -0.056, just outside REF's natural window variation (0.024-0.046);
- butterfly (2 / 2): a **color shift introduced by the temporary Sink** (C_c +1.40 / +1.59 vs t_dE 0.59 / 0.75; TS-in
  alone does the same, +1.67 / +1.76; frozen M1 +0.24 / +0.26).
Visually the identity is kept in 16 of 16 DR2+TSin clips (frozen M1: changed in 8 of 16) and the Sink-less interval is
stable in 15 of 16 (frozen M1: drifts or breaks in 12 of 16); appearance changed in 2 (train).

**P2b motion / temporal consistency.** Fails in 9 of 12 cells: frame-to-frame change exceeds REF by 13-23 % (motion
ratio 1.13-1.23 on dog, butterfly, train; 1.11 on audi s0 OT-L) and warp error by up to 26 % (dog). Frozen M1: motion
1.01-1.38, warp 1.20-2.04. The Sink-less stream is more temporally active than REF even where its content matches.

**P3 no-harm.** Passes in all 12 cells: bind V1 within REF P99, the first 20 post-bind calls non-inferior to frozen M1,
terminal restoration to REF; no visible jump at the exact Sink bind in any clip (0 / 16).

**Cost.** Serial 1.29-1.30 s (TS-in prepare 0.78 s + DR-2 decode 0.52 s), 0.4 MB: within the 1.5 s / 1 MB limits;
overlap was not validated, so no lower figure is claimed.

## 3. Reading under the preregistered failure mapping (section 7)

- **P1 fails visually** (and once quantitatively): decoder-side reconstruction from the source's latent history halves
  the jump but does not remove it; more latent history did not help (VD-2 DR-4), and the history's content matters
  (C3). The next question is additional source-derived decoder state; nothing is run without a new preregistration.
- **P2 fails in content (train, small; butterfly, color from the temporary Sink) and in temporal consistency
  (dog, butterfly, train).** The temporary Sink restores most of the content but not REF's temporal behaviour or color
  on every input. Section 7 names source-derived temporal state for the Sink (an approximate or partial Sink) as the
  question for P2 failures; P2b failures were not mapped separately.
- **P3 passes**: the temporary Sink does not interfere with the exact bind, so TS-in is not dropped on that ground.
- **No continuity-preserving M1 is claimed.** Descriptively, on these inputs and schedules, DR2+TSin halves the
  boundary jump, closes most of the Sink-less content gap, keeps the identity visually in every clip and binds the
  exact Sink without a visible discontinuity, at 1.3 s of serial destination GPU time - an improvement over frozen M1,
  not continuity preservation.

## 4. Data and limits

All 12 confirmation cells and 4 replication cells are in `vd3_results.md` (per phase and cell, failures included).
Emulator only (one GPU, frozen-M1 schedules, three copied schedules labelled counterfactual, audi seed-0 OT-1 a
counterfactual stress condition); one model; four inputs; two seeds. The inspection is one rater's, unblinded only
after recording; its false-positive rate on REF was 2 boundary flags and 1 appearance flag in 16 REF clips.
