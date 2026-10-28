# VD-4 stage 2b record (2026-10-27)

Written after the stage-2b inspection was recorded (d67fdf21, merged 2c4df116), the key copied (f9a75bf5; SHA-256
2b8e2eb0... = the form's) and the aggregate computed. Nothing frozen was modified: not the preregistration, schedules,
thresholds (SHA-256 792a6ac77ffbca24), inspection forms, recorded inspections, keys, or the aggregator's inspection /
resolution / attribution / correspondence logic. The stage-1 and stage-2 results and inspection decisions are
unchanged: the B0, A1, D, R, DR and S3 numeric and condition blocks, the attribution, the validity list and every
gate except the duplicate-controls list are identical before and after this aggregate. The numeric outcome and the
design consequences below were written down before the inspection (`vd4_stage1_exploratory_notes.md` section 6,
f7247879).

Stage 2b took the preregistered "S3 did not resolve P2" branch: S1 (oracle Sink slot 2), S2 (slots 2, 1) and the
exploratory A1S1 / A1S2 (the same slot sets with A1's RoPE-aligned keys in the remaining TS slots) on the four-cell
subset dog s1 OT-1, train s0 OT-1, butterfly s1 OT-1, audi s1 OT-1. B0, R, DR and S3 values below are the stage-1 /
stage-2 runs of the same cells. Stage 3 is disabled by the frozen gate and was not run.

## 1. Run validity and completeness

- 16 / 16 new runs valid on host D at 99d08937 (preflight clean): every frozen oracle check (Sink K / V / positions
  equal to the source, TS keys as written, TS values unrotated) and every supplemental per-layer / per-row check is
  true; A1S1 / A1S2 also pass the row-wise A1 checks (deltas applied per row, K within 1 ulp of the independent
  reference, zero-delta rows unchanged). G3 passes on all four units; the prefix is identical to REF; resets and binds
  were realized as scheduled (bind at call 58, audi 59).
- Blinded session `stage2b`: 24 clips (REF, B0, S1, S2, A1S1, A1S2 per cell), one rater, all 24 rows filled with the
  form's vocabulary, no notes written.
- Added bytes (oracle payload; idealized transfer at 1 / 10 Gbps, not a migration latency): S1 575.5 MB (4.6 / 0.46
  s), S2 1150.6 MB (9.2 / 0.92 s); S3 1725.6 MB (13.8 / 1.38 s).

## 2. Formal preregistered results (frozen rules)

| condition | P1 numeric | P1 flags (REF, same session) | P2a numeric | P2b numeric | P3 | resolution |
|---|---|---|---|---|---|---|
| S1 | 4 / 4 | 4 (0) | 3 / 4 | 1 / 4 | 4 / 4 no harm | not resolved |
| S2 | 4 / 4 | 3 (0) | 4 / 4 | 1 / 4 | 4 / 4 no harm | not resolved |
| A1S1 (exploratory) | 4 / 4 | 4 (0) | 3 / 4 | 1 / 4 | 4 / 4 no harm | not resolved |
| A1S2 (exploratory) | 4 / 4 | 3 (0) | 4 / 4 | 1 / 4 | 4 / 4 no harm | not resolved |

- **No stage-2b condition resolves any phase.** The frozen `resolution()` requires 12 / 12 numeric passes; on a
  four-cell subset that is unreachable, so "not resolved" is by construction (noted before the inspection). The
  P1 flags would also prevent STRICT / NEAR on their own: 3-4 jump flags against REF's 0 in the same session.
- **Attribution unchanged:** P1 - R sufficient (stage 1); P2a, P2b - not explained by the tested states (B0, A1, D,
  R, DR, S3, and now S1, S2). No P2a / P2b / P3 field was flagged on any stage-2b clip.
- **Gates unchanged:** `s3_resolves_p2` false, `stage3_runs` false. `duplicate_controls` grew from 24 to 32 entries:
  the stage-2b REF / B0 of the four cells, by construction of preregistration section 5 (each condition's baseline is
  the stage-2b REF; nothing is counted twice).
- The P2a / P2b statements in sections 3-4 are descriptive readings of four cells; they are not 12-cell outcomes. In
  particular S2's P2a 4 / 4 on the subset does not say what S2 would do on the 12 cells (S3, 4 / 4 here, is 11 / 12
  there).

## 3. Per-cell numerical results (descriptive; values of the frozen metrics)

V1 = reset-boundary visual change (P1 limit: REF P99). D_c / C_c / dE_cross over the whole Sink-less window, late D_c
and X_late over its last 8 calls (P2a: D_c and late D_c >= -t_DINO, C_c <= t_dE, dE_cross <= t_dEx, X_late <= t_DINO).
P2b: warp excess eO - eR <= 0.10 x max(eR, 1) and frame difference dO / dR within 0.90-1.10. Rules column: y = the
frozen rule holds.

**dog s1 OT-1** (REF P99 3.91; t_DINO 0.037, t_dE 0.90, t_dEx 1.56)

| condition | V1 reset | D_c | late D_c | X_late | C_c | dE_cross | warp eO - eR (limit) | frame diff dO / dR | P1 P2a P2b P3 |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 3.55 | -0.017 | -0.013 | -0.012 | 0.78 | 1.17 | +0.69 (0.27) | 1.211 | y y n y |
| S1 | 3.45 | -0.011 | -0.008 | -0.008 | 0.82 | 1.09 | +0.55 (0.27) | 1.166 | y y n y |
| S2 | 3.51 | -0.005 | -0.003 | -0.006 | 0.79 | 1.32 | +0.49 (0.27) | 1.165 | y y n y |
| S3 | 3.46 | -0.001 | -0.000 | -0.004 | 0.46 | 0.49 | +0.59 (0.27) | 1.117 | y y n y |
| A1S1 | 3.52 | -0.011 | -0.009 | -0.006 | 0.49 | 1.10 | +0.59 (0.27) | 1.164 | y y n y |
| A1S2 | 3.58 | -0.005 | -0.003 | -0.006 | 0.58 | 1.36 | +0.54 (0.27) | 1.160 | y y n y |
| R | 2.04 | -0.013 | -0.013 | -0.001 | 0.67 | 1.06 | +0.47 (0.27) | 1.195 | y y n y |
| DR | 1.34 | -0.013 | -0.013 | -0.001 | 0.53 | 0.92 | +0.35 (0.27) | 1.154 | y y n y |

**train s0 OT-1** (REF P99 6.49; t_DINO 0.036, t_dE 1.06, t_dEx 2.66)

| condition | V1 reset | D_c | late D_c | X_late | C_c | dE_cross | warp eO - eR (limit) | frame diff dO / dR | P1 P2a P2b P3 |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 1.89 | -0.056 | -0.044 | -0.042 | 0.83 | 1.68 | +1.01 (0.68) | 1.226 | y n n y |
| S1 | 1.87 | -0.033 | -0.022 | -0.030 | 0.59 | 1.23 | +0.72 (0.68) | 1.171 | y y n y |
| S2 | 1.71 | -0.020 | -0.007 | -0.026 | 0.49 | 0.94 | +0.86 (0.68) | 1.191 | y y n y |
| S3 | 1.71 | -0.007 | +0.000 | -0.023 | 0.15 | 0.20 | +0.26 (0.68) | 1.030 | y y y y |
| A1S1 | 1.83 | -0.034 | -0.026 | -0.019 | 0.40 | 1.18 | +0.73 (0.68) | 1.166 | y y n y |
| A1S2 | 1.68 | -0.020 | -0.009 | -0.015 | 0.33 | 0.98 | +0.87 (0.68) | 1.187 | y y n y |
| R | 1.01 | -0.037 | -0.044 | +0.010 | 0.67 | 1.29 | +0.89 (0.68) | 1.223 | y n n y |
| DR | 1.00 | -0.037 | -0.044 | +0.011 | 0.72 | 1.33 | +0.80 (0.68) | 1.210 | y n n y |

**butterfly s1 OT-1** (REF P99 1.25; t_DINO 0.047, t_dE 0.59, t_dEx 3.65)

| condition | V1 reset | D_c | late D_c | X_late | C_c | dE_cross | warp eO - eR (limit) | frame diff dO / dR | P1 P2a P2b P3 |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 1.16 | -0.086 | -0.091 | +0.002 | 1.40 | 3.52 | +0.54 (1.14) | 1.129 | y n n y |
| S1 | 1.13 | -0.067 | -0.083 | +0.027 | 0.53 | 1.98 | +0.22 (1.14) | 1.114 | y n n y |
| S2 | 1.11 | -0.035 | -0.039 | +0.008 | 0.20 | 1.55 | +0.17 (1.14) | 1.109 | y y n y |
| S3 | 1.05 | -0.005 | -0.001 | -0.012 | 0.12 | 0.31 | +0.40 (1.14) | 1.028 | y y y y |
| A1S1 | 1.14 | -0.069 | -0.084 | +0.017 | 0.61 | 2.06 | +0.56 (1.14) | 1.134 | y n n y |
| A1S2 | 1.10 | -0.034 | -0.037 | +0.002 | 0.32 | 1.69 | +0.40 (1.14) | 1.120 | y y n y |
| R | 0.90 | -0.080 | -0.091 | +0.024 | 1.23 | 3.23 | +0.51 (1.14) | 1.136 | y n n y |
| DR | 0.81 | -0.080 | -0.091 | +0.025 | 1.22 | 3.21 | +0.47 (1.14) | 1.133 | y n n y |

**audi s1 OT-1** (REF P99 3.22; t_DINO 0.148, t_dE 4.86, t_dEx 8.28)

| condition | V1 reset | D_c | late D_c | X_late | C_c | dE_cross | warp eO - eR (limit) | frame diff dO / dR | P1 P2a P2b P3 |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 2.01 | -0.089 | -0.023 | -0.121 | 0.01 | 0.76 | -0.43 (0.94) | 0.942 | y y y y |
| S1 | 2.04 | -0.080 | -0.024 | -0.102 | 0.07 | 0.46 | -0.33 (0.94) | 1.012 | y y y y |
| S2 | 1.93 | -0.063 | -0.016 | -0.094 | 0.08 | 0.46 | -0.46 (0.94) | 1.042 | y y y y |
| S3 | 1.82 | -0.005 | +0.000 | -0.007 | 0.10 | 0.20 | +0.41 (0.94) | 0.991 | y y y y |
| A1S1 | 2.02 | -0.083 | -0.025 | -0.104 | 0.12 | 0.52 | -0.07 (0.94) | 1.032 | y y y y |
| A1S2 | 1.95 | -0.063 | -0.017 | -0.088 | 0.16 | 0.48 | -0.05 (0.94) | 1.039 | y y y y |
| R | 0.85 | -0.067 | -0.023 | -0.053 | -0.13 | 0.77 | +0.10 (0.94) | 1.047 | y y y y |
| DR | 0.46 | -0.067 | -0.023 | -0.052 | -0.11 | 0.75 | -0.02 (0.94) | 1.034 | y y y y |

## 4. Paired S1 / S2 / S3 comparisons and monotonicity (descriptive)

Order B0 -> S1 -> S2 -> S3 is the preregistered fixed replacement order (slot 2, then 1, then 0). An effect is
reported per slot set; it is not attributed to the number of slots, since the slots differ in identity and age
(preregistration section 3).

- **Monotone on all four cells: the content drift.** The whole-window D_c moves toward REF with every slot set (dog
  -0.017 / -0.011 / -0.005 / -0.001; train -0.056 / -0.033 / -0.020 / -0.007; butterfly -0.086 / -0.067 / -0.035 /
  -0.005; audi -0.089 / -0.080 / -0.063 / -0.005). The late-window D_c does too, except audi S1 (-0.024 vs B0 -0.023,
  a tie). The P2a counts follow: B0 2, S1 3, S2 4, S3 4 of 4. On these cells the partial sets recover content
  roughly in proportion to the slots restored, and S3's last slot closes most of the remaining gap (D_c within
  0.007 of REF on all four).
- **Flat: the reset spike.** V1 stays within 0.2 of B0 for every slot set on every cell; R and DR are the only states
  that lower it (stage 1). The Sink slots do not address P1, as in stage 2.
- **Not monotone: motion and warp.** The warp excess is non-monotone on all four cells (dog +0.69 / +0.55 / +0.49 /
  +0.59; train +1.01 / +0.72 / +0.86 / +0.26; butterfly +0.54 / +0.22 / +0.17 / +0.40; audi -0.43 / -0.33 / -0.46 /
  +0.41). The frame-difference ratio is non-monotone on train (1.226 / 1.171 / 1.191 / 1.030) and audi (0.942 / 1.012
  / 1.042 / 0.991). Smaller non-monotone steps: dE_cross on dog (1.17 / 1.09 / 1.32 / 0.49), C_c on dog, X_late on
  butterfly (S1 raises the late excess above B0's: +0.027 vs +0.002).
- **S3's P2b gain is not foreshadowed by S1 or S2.** P2b: B0 1, S1 1, S2 1 (audi only), S3 3 of 4. S1 and S2 leave
  the frame-difference ratio at 1.11-1.19 on dog, train and butterfly; S3 brings train and butterfly to 1.03 (dog
  stays at 1.117 and also fails the warp clause). The step comes with slot 0; whether it is that slot's identity (the
  oldest) or the completed set is not separable in this design.
- **Relative to B0 and S3.** S1 and S2 are between B0 and S3 on content and colour (S2 closer to S3 on train and
  butterfly colour: C_c 0.49 / 0.20 vs S3 0.15 / 0.12), at B0's level on V1, and at B0's level on motion except
  audi. R and DR (stage 1) do the opposite: V1 lowest, content and motion at B0's level.

## 5. A1S1 / A1S2 (exploratory)

- Rule outcomes equal S1's / S2's on every cell, numerically and in the flag counts (A1S1 4, A1S2 3).
- Values move both ways relative to S1 / S2: C_c lower on dog and train (train A1S1 0.40 vs S1 0.59), higher on
  butterfly and audi (butterfly A1S1 0.61 vs S1 0.53); the warp excess higher on butterfly (A1S1 +0.56 vs S1 +0.22;
  A1S2 +0.40 vs S2 +0.17) and audi (A1S1 -0.07 vs S1 -0.33); V1 within 0.07 of S1 / S2 everywhere.
- Run-to-run scale: on dog the layer-0 A1 deltas are 0 and the zero-delta rows are unchanged, so dog A1S1 / S1 and
  A1S2 / S2 are close to same-configuration repeats (A1 rotates the remaining nonzero-delta slots; 13 slot-layers
  were rotated on dog, so the identity is not exact). Their differences (V1 <= 0.08, D_c <= 0.0003, C_c 0.22-0.33,
  warp excess 0.03-0.05, frame-difference ratio <= 0.005) bound what can be read into the A1 differences on the other
  cells: the warp shifts on butterfly and audi (0.23-0.41) exceed that scale; the C_c and D_c differences on
  train, butterfly and audi do not (dog's own C_c difference of 0.22-0.33 may partly be A1's effect, so the C_c
  scale is an upper bound).
- Reading: the RoPE alignment of the remaining TS keys does not change any rule outcome when combined with partial
  Sink restoration, consistent with A1 alone in stage 1 (B0's numeric twin). Two pairs on one cell give a scale, not a
  noise model.

## 6. Blinded visual findings (stage2b session; read after unblinding)

**6.1 Within the session.** REF 0 / 4 jump flags; B0 4 / 4; S1 4 / 4; S2 3 / 4; A1S1 4 / 4; A1S2 3 / 4. The only
unflagged non-REF clips are S2 and A1S2 of train s0 OT-1. No field other than "boundary jump at M" was flagged on any
of the 24 clips: identity kept, no appearance drift, no colour shift, no flicker, natural motion, no new
discontinuity at B, everywhere. No notes were written.

**6.2 The two unflagged train clips.** On train the S2 / A1S2 V1 values (1.71 / 1.68) are the lowest of the
Sink-only conditions, but the differences from B0 / S1 / A1S1 (1.83-1.89) are small and all are far below REF P99
6.49. S3 (V1 1.71, the same as S2) was flagged on this cell in stage 2. Earlier train notes described the jump as
the person "looking clearer at M" rather than a break. With one rater and one clip each, the two unflagged clips are
an observation; they do not establish that S2 removes the train jump.

**6.3 Test-retest across the three viewings of the same control clips.** REF of the four cells: "no visible jump" in
all three sessions (12 / 12 consistent). B0's jump flag: train flagged in all three; dog and audi unflagged in stage
1, flagged in stages 2 and 2b; butterfly unflagged in stages 1 and 2, flagged in 2b. B0's count on the same four clips
is 1 (stage 1), 3 (stage 2), 4 (stage 2b). Every change is toward "jump"; none reverses. The rater's threshold for a
jump at M kept tightening across sessions (stage-2 record section 3.2) while the REF judgment stayed fixed. The
flag counts of stages 1, 2 and 2b are therefore **not on a common scale** and are not compared here. Within stage 2b
every Sink-only condition sits at B0's level (3-4 of 4), which is the only comparison this session supports.

**6.4 Notes.** The audi "car drives backward at M" note, written in stages 1b and 2 on B0 of audi s1 OT-1, was not
written in stage 2b on any clip; no notes were written at all, so its absence carries no information.

**6.5 Correspondence (secondary, frozen tables, now including the 16 stage-2b candidate clips).** P2a: metric fail
& flagged 0, fail & not flagged 33, pass & flagged 0, both clean 55; P2b: 0 / 59 / 0 / 29. Kappa is 0 by
construction: no P2 field was flagged on any scored clip in any session. The REF omission noted in the stage-1 record
stands.

## 7. Non-monotonic behaviour and anomalies

- The warp excess and the frame-difference ratio are non-monotone in the slot order (section 4); S3's P2b improvement
  is a step at slot 0, not a trend.
- On butterfly, S1 raises the late excess drift X_late above B0's (+0.027 vs +0.002) while lowering the
  whole-window drift; the late-window content is where S1's P2a fails (late D_c -0.083).
- A1 changes colour and warp in both directions on top of partial Sink restoration, beyond the dog run-to-run scale.
- The rater's jump threshold drifted monotonically toward "jump" over three sessions on identical control clips.
- No validity anomaly: every run, check and gate is as expected.

## 8. Interpretation (oracle sufficiency; not feasibility)

- Formally, stage 2b adds no resolved phase: P1 is resolved only by R and DR (stage 1); P2a and P2b by no tested
  state. The four-cell subset could not resolve anything by the frozen rule; it was preregistered as a
  non-monotonicity check.
- Descriptively, the Sink slots act on content and colour in the Sink-less window in a monotone, slot-by-slot way,
  and on motion / warp only when all three are restored (and then not on dog). They do not touch the reset spike,
  and the visible jump at M remains on every Sink-only clip but one cell, at B0's level within the session. The
  states that move P1 (recent KV) and P2 (Sink slots) remain different; no single oracle state tested in VD-4
  addresses both.
- None of this concerns practical migration: every condition here is an oracle injection of source state (575-1726
  MB of Sink, 1726 MB of recent KV), and the diagnosis says which oracle states suffice for which criterion on these
  cells, not whether any of them can be delivered in time, nor whether they are necessary.
- VD-4's preregistered stages are complete (stage 3 disabled). Next steps need the user's decision: a targeted causal
  experiment or the design of a practical continuity-preserving M1 mechanism.
