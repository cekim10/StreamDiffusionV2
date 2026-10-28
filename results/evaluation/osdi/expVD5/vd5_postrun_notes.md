# VD-5 post-run notes (written before block A of the blinded inspection is opened, 2026-10-27)

Written after the run commit fd3a799f and before any clip of the session `vd5` was watched. Nothing frozen is changed:
not the preregistration, the overlays, the thresholds (SHA-256 792a6ac77ffbca24), the forms, the sealed key or the
code listed in `expVD5_freeze.md`. Everything below is read from `vd5_results.{md,json}` and the run summaries.

## 1. Validity

- Preflight: host D at 78d73af4, GPU 0 idle, no problems. NIC isolation recorded (`vd5_isolation.json`): no traffic on
  the data-plane NICs.
- Reuse gate (dog s1 OT-1, VD-4's B0 / R / S3 re-run at 78d73af4): 158 / 158 calls identical for each. The reused
  B0 / R / S3 rule outcomes and V1 equal VD-4's aggregate.
- RS3: 12 / 12 valid. Stream (G3), VD-4's frozen oracle checks and every joint-restoration check of preregistration
  section 5.2 are true: the whole live ring (K, V, positions; every layer, row and slot) equals the snapshot after the
  reset, the slot sets are disjoint and cover the ring, no temporary Sink, and the bind writes no recent slot and no
  position.
- V0 equals REF after the move on the six visual cells.
- Recorded, not required (section 5.2): the bind re-rotated 73-98 Sink entries in every RS3 run. After the bind the Sink
  V equals the restored one on 12 / 12 runs; the Sink K equals it on the six OT-1 runs and differs on the six OT-L runs
  (RoPE re-rotation is not bitwise). P3 is 12 / 12.

## 2. Numeric outcome under the frozen rules

| condition | P1 | P2a | P2b | P3 |
|---|---|---|---|---|
| RS3 | 12 / 12 | 11 / 12 | 11 / 12 | 12 / 12 |

- The two failing cells are S3's failing cells, as H0 predicted:
  - butterfly s1 OT-L fails P2a on the late window: late D_c -0.0286 against the limit -0.027 (B0 -0.034, R -0.035,
    S3 -0.028).
  - dog s1 OT-1 fails P2b on warp: eO - eR +0.33 against the limit 0.27 (B0 +0.69, R +0.47, S3 +0.59).
- **Consequence for the primary answer.** STRICT and NEAR both require numeric 12 / 12 (VD-4's rule, section 7), so
  neither P2 phase can be STRICT or NEAR. The primary answer is therefore **no**, whatever the inspection and the
  calibration gate show; the numeric fallback for a failed calibration also gives no. The inspection still decides
  RS3's P1 resolution, the block-B parts of the two non-inferiority tests, and the descriptive visual findings.

## 3. Comparisons and interaction (numeric parts)

- RS3 vs R (P1): V1 non-inferior on 12 / 12 cells. RS3 vs S3 (P2): non-inferior on 12 / 12 cells. Both verdicts are
  final only with block B.
- Interaction reading: **complementary** (additive on >= 10 / 12 cells for every metric; no metric has 3 synergistic
  or 3 antagonistic cells). Every P2 metric is additive on 12 / 12 cells.
- V1 is antagonistic on two cells: audi s0 OT-1 (I +0.334, tolerance 0.284) and audi s1 OT-L (I +0.393, tolerance
  0.322). On both, RS3's V1 is close to R's (0.80 vs 0.82; 2.20 vs 2.07) and S3's own small V1 reduction does not add
  on top of R's.
- H1 (positive interaction) is not supported numerically; H2 (negative interaction beyond the tolerances) is not
  supported numerically.

## 4. Remaining failures are not in the KV ring

The two failures remain with the entire KV ring exact at the reset (section 1). RS3 differs from V0, which equals REF,
only in the decoder (DR-2 instead of the exact cache), the zero VAE encoder cache, the refresh frozen from M to B and
the bind at B (preregistration section 2). The residual is therefore carried by one or more of these; VD-5 does not
test which, by design.

## 5. Display defect in the aggregate report (not a result change)

The per-cell interaction table of `vd5_results.md` prints each class by its first letter, so "additive" and
"antagonistic" both print as "(a)". The counts table, the reading and `vd5_results.json` are correct; the two
antagonistic cells are the ones named in section 3. The aggregator is frozen (SHA-256 in `expVD5_freeze.md`, checked by
`run_vc.py vd5`), so it is not changed; the VD-5 record will name the classes from the JSON.
