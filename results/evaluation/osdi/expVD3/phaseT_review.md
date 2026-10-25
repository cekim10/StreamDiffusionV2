# VD-3 Phase T review (2026-10-25; for the threshold decision; no threshold is frozen here)

Phase T ran on host D (commit 31f5ad9; `vd3_phaseT.{md,json}`). No VD-3 candidate condition exists. Everything below
comes from REF streams and frozen-M1 controls; the frozen-M1 values are context, not a threshold source.

## 1. Validity

- Seed-1 units (dog, train, butterfly, audi): REF + frozen-M1 OT-1 / OT-L emulated; **G1 PASS on all four** (the
  emulated OT-1 equals the real W2 seed-1 run on 101 calls, max |dPSNR| 0.000 dB); **G3 PASS** on every stream.
- **Measurement noise is zero**: the same REF frames embedded twice give identical DINO similarities (per call and per
  window, max |difference| 0.00000), and the emulation reproduces the real runs exactly (G1). Thresholds are therefore
  bounded below by natural variation only.
- The overlap measurement (`vd3_overlap.json`) is **missing**: the step did not produce its output (log on host D,
  section 5). The serial costs stand until it is re-run.

## 2. Distributions (per cell; full table in `vd3_phaseT.md`)

Natural REF variation of the 10-call window statistics (P95 - P5 width over the span), lag-10 window change (P95),
cross-seed difference (P95, sensitivity only); representative confirmation cells:

| cell | DINO width / lag-10 / cross-seed | dE-to-anchor width / lag-10 / cross-seed | e_R rel. width / cross-seed | d_R rel. width / cross-seed | REF V1 P99 |
|---|---|---|---|---|---|
| dog s1 OT-1 | 0.037 / 0.037 / 0.004 | 0.90 / 0.71 / 0.14 | 0.62 / 0.05 | 0.75 / 0.07 | 3.39 |
| train s0 OT-1 | 0.036 / 0.018 / 0.014 | 1.06 / 1.00 / 0.73 | 0.23 / 0.08 | 0.27 / 0.11 | 6.45 |
| butterfly s1 OT-1 | 0.047 / 0.026 / 0.016 | 0.59 / 0.54 / 0.54 | 0.23 / 0.07 | 0.27 / 0.04 | 1.25 |
| audi s1 OT-L | 0.244 / 0.224 / 0.045 | 8.40 / 7.66 / 0.51 | 0.81 / 0.07 | 0.68 / 0.12 | 3.30 |

Ranges over all 12 confirmation cells: DINO width 0.024-0.244 (dog / train / butterfly 0.024-0.056; audi 0.14-0.24,
the scene changes), cross-seed 0.003-0.045; dE width 0.59-8.67, cross-seed 0.14-0.73; warp / motion relative widths
0.22-0.86 (cross-seed 0.04-0.12). REF's own early-to-late DINO change over the Sink-less calls: -0.15 to +0.03.

## 3. Threshold options (not chosen) and what frozen M1 does under each (context)

- **A** natural REF variation: per cell, t = the P95 - P5 window width (content, color, warp, motion), t_dEx = P95 of
  REF's window dE to the anchor.
- **B** temporal natural variation: per cell, t = P95 of the lag-10 window change.
- **C** cross-seed difference (decided: sensitivity only; listed to show the contrast).

Frozen M1 against R1-R4 (F = violates, . = passes) per option:

| cell | A | B | C |
|---|---|---|---|
| dog s1 OT-1 / OT-L | FFF. / FFF. | FFF. / FFF. | FFFF / FFFF |
| train s0 OT-1 / OT-L | .FF. / FFF. | .FF. / FFF. | .FF. / FFF. |
| train s1 OT-1 / OT-L | .FF. / FFF. | .FF. / FFF. | .FFF / FFF. |
| butterfly s1 OT-1 / OT-L | FFF. / FFF. | FFF. / FFFF | FFF. / FFFF |
| audi s0 OT-1 / OT-L | FF.. / **F...** | FF.. / **F...** | FFF. / FFF. |
| audi s1 OT-1 / OT-L | FF.. / **F...** | **F...** / **F...** | FFF. / FFF. |

Under every option frozen M1 violates at least one rule in every confirmation cell, so no cell is non-discriminative
at the cell level. But on audi OT-L (A, B) and audi s1 OT-1 (B) frozen M1 violates **only R1** (the boundary jump): the
Sink-less content and color change that VC-1 found visible on audi is inside REF's natural window variation there,
because audi's scene itself changes by that much. A candidate pass in those cells shows the boundary is fixed; it does
not show the Sink-less change is fixed.

Observations for the decision:
1. A and B are close for content and color (B tighter on train / butterfly). Both are loose for warp and motion
   (a 22-86 % change in the warp-error ratio would pass), which draft 4 had as a fixed 10 %.
2. Frozen M1 passes R4 almost everywhere (the exact bind recovers), so R4 is a no-harm check, not a discriminating one.

## 4. Proposed refinement of the D1c overall rule (for decision)

Discrimination per phase instead of per cell: for a candidate, a pass in a cell counts as resolving phase P1 (R1) or
P2 (R2 / R3) only where frozen M1 violates that phase's rule. GO requires no FAIL, no veto, and **for every
confirmation input at least one cell discriminative in P1 and at least one discriminative in P2**; P3 (R4) must pass
everywhere but needs no discrimination. Otherwise INCONCLUSIVE (with the phases that could not be shown). Under A, audi
keeps P2-discriminative cells (OT-1 at both seeds); under B only audi s0 OT-1.

## 5. Open items

- Threshold option (A, B, or another REF-only definition), including whether warp / motion use the same option.
- The per-phase refinement of section 4.
- The overlap measurement: re-run on D after the cause is known (`vd3_*_overlap.log` on host D).
- Then: `vd3_thresholds.json`, the freeze, Phase C.

## 6. The audi seed-0 reproduction (for D2b)

`../expW/audi_s0_repro_report.md`: verified (valid; launch tokens and the audi input hash on both nodes; node A
digests equal the genuine audi seed-0 generation, not train seed 1). Its schedule: move 34, **bind 58** (Sink bound
14.75 s after the move), recorded for the sensitivity analysis; the VD-3 confirmation cell keeps the copied schedule
(move 34, bind 59) as a counterfactual stress condition.
