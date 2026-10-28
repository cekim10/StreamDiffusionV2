# VD-5 proposal: joint restoration of recent KV and exact Sink KV (DRAFT 1, 2026-10-27; not frozen, not implemented)

Status: design for review. Nothing here is implemented or run. VD-4 is complete and frozen; no VD-4 stage is added,
and no VD-4 result, form, key, threshold or rule is changed. Like VD-4 this is an **oracle sufficiency** diagnosis:
every condition injects source state copied from the snapshot. It says nothing about whether that state can be
delivered in time (RS3 is about 3.45 GB) or whether it is necessary.

## 1. Question and hypotheses

Does restoring the source recent KV and the exact source Sink KV together fix both the boundary discontinuity at M
(P1) and the Sink-less-window content / motion consistency (P2a, P2b)?

What VD-4 found, on the 12 confirmation cells under VD-3's frozen rules:
- R (recent KV) passes P1 numerically 12 / 12 with 0 jump flags. It leaves P2 at B0's level.
- S3 (exact Sink) moves P2 toward REF: P2a 11 / 12, P2b 11 / 12. It leaves V1 and the visible jump at B0's level.

Predictions, fixed before any run:
- **H0, additive.** Each state keeps its own effect. RS3 then has R's V1 and S3's P2 values. The predicted outcome
  is P1 12 / 12 and P2a / P2b 11 / 12. The two S3 failures would remain: butterfly s1 OT-L on the late-window
  content clause, and dog s1 OT-1 on warp and frame difference. RS3 would then **not** meet the frozen 12 / 12 bar
  for P2.
- **H1, positive interaction.** In R the source recent KV sits next to the temporary TS-in Sink. That KV was
  computed while attending to the source Sink, so the pair is inconsistent. RS3 restores a consistent pair. H1
  predicts that RS3 does better than additivity on P2, closing the two S3 failures, or on P1, by lowering V1 below
  R's.
- **H2, negative interaction.** RS3 does worse than R on P1 or worse than S3 on P2, by more than the tolerance
  defined in section 6.

## 2. Conditions

| condition | Sink slots 0-2 | recent slots 3-5 | decoder | refresh M..B | source |
|---|---|---|---|---|---|
| B0 | TS-in (2 slots), slot 2 zero | zero | DR-2 | frozen | reuse VD-4 stage 1 |
| R | TS-in, slot 2 zero | **source** | DR-2 | frozen | reuse VD-4 stage 1 |
| S3 | **source** (2, 1, 0) | zero | DR-2 | frozen | reuse VD-4 stages 0 and 2 |
| **RS3** | **source** (2, 1, 0) | **source** | DR-2 | frozen | **new** |
| V0 | everything from the snapshot, refresh unfrozen, no bind | | | | reuse 3, new 3 |

- The design is a 2 x 2 factorial: Sink {TS-in, exact} x recent {zero, source}. Both factors use the same snapshot,
  schedule, reset call M, bind call B, DR-2 decoder and frozen refresh. The Sink factor compares B0's temporary
  Sink with the exact Sink. It does not compare "no Sink" with the exact Sink.
- RS3 is one new row in the VD-4 condition tuple: `("RS3", "dr2", True, None, [2, 1, 0], None, False, False)`.
  `vd4_reset` already applies the steps in the order fast path, oracle recent, oracle Sink slots, DR-2, freeze. It
  needs no new reset code. The row goes in a VD-5 overlay so that the frozen VD-4 tuple and schedules stay
  byte-identical.
- **What RS3 still lacks relative to V0.** RS3 restores the whole KV ring, the metadata and the in-flight rows. It
  differs from V0 in four ways:
  1. RS3 uses the DR-2 decoder reconstruction where V0 has the exact decoder cache.
  2. RS3 has a zero VAE encoder cache.
  3. In RS3 refresh stays frozen from M to B.
  4. RS3 has the bind at B.
  If RS3 falls short of V0, these four are the residual suspects. Testing them is a follow-up, not part of VD-5. One
  option would be a DRS3 condition with the oracle decoder.
- **V0 is bit-identical to REF.** VD-4 stage 0 showed this call by call. As a numeric control V0 therefore adds
  nothing beyond REF. In the blinded session it is a hidden duplicate of REF: a catch clip that a calibrated rater
  should not flag.

## 3. Cells

- **Numeric: all 12 VD-4 confirmation cells.** These are dog s1, butterfly s1, train s0 and s1, and audi s0 and s1,
  each under OT-1 and OT-L.
  - The frozen rule needs 12 / 12. VD-4 stage 2b showed that a four-cell subset cannot meet it.
  - Reuse makes the full set cheap: RS3 is the only new candidate.
- **Visual: 6 of the 12 cells, in one session.** The six are dog s1 OT-1, dog s1 OT-L, train s0 OT-1, butterfly s1
  OT-L, audi s0 OT-L and audi s1 OT-1.
  - They cover all four inputs and both schedules.
  - They include every cell where R or S3 failed a rule, plus the cell with the motion-reversal note:
    - audi s0 OT-L: B0, D and S3 fail P1 numerically;
    - dog s1 OT-L: S3 and A1 fail P1;
    - butterfly s1 OT-L: S3 fails P2a;
    - dog s1 OT-1: S3 fails P2b;
    - train s0 OT-1: R fails P2a, and B0 was flagged in all three sessions;
    - audi s1 OT-1: the "car drives backward at M" note.
  - The selection is targeted on known outcomes, which is why the numeric analysis covers all 12 cells.
  - Alternative for review: all 12 cells in two sessions of 6 cells each, with every condition of a cell in the same
    session. This doubles the rater time and puts the between-session drift seen in VD-4 back into the comparison.

## 4. Metrics (unchanged)

- These are VD-3's frozen metrics, thresholds and rules, unchanged: thresholds `vd3_thresholds.json`, SHA-256
  792a6ac77ffbca24, and `aggregate_vd3.rules`.
  - P1: V1 at the reset is at most REF's P99.
  - P2a: whole-window D_c, C_c and dE_cross, plus the late-window D_c and X_late.
  - P2b: warp excess within 10 % of REF and frame difference within plus or minus 10 % of REF.
  - P3: no harm.
- The same playback model and the same per-cell REF are used, so every value is directly comparable with VD-4's B0,
  R and S3.
- **Exploratory, not decision-bearing: motion-direction agreement at M.** The warp and frame-difference metrics do
  not see the direction of motion. This new metric is the cosine between the mean optical-flow vector of the output
  and that of REF over calls M..M+8. It is reported descriptively, and only if it can be computed from the existing
  per-call flow without new model passes.

## 5. Validity checks (all required before any result is read)

1. **Frozen VD-4 checks and supplemental checks for RS3.**
   - Frozen checks, after the last reset operation: recent K, V and positions equal the snapshot; Sink K, V and
     positions equal the snapshot.
   - Supplemental checks, per layer, row and slot: `positions_final_equal_snapshot`, `positions_rows_final_equal_snapshot`,
     `recent_*_equal_per_layer_slot` and `sink_*_equal_per_layer_slot`.
   - Also required: `ts_slots_written` is None and `temp_slots_left_after_bind` is 0.
2. **New: no overwrite and consistent metadata.**
   - `write_snap_slots` writes K and V of the listed slots only. It never writes positions. Positions come from
     the snapshot's metadata through `restore_fast`.
   - The Sink set {0, 1, 2} and the recent set {3, 4, 5} must be disjoint and must together cover the ring.
   - New check: after the reset, the whole live ring (K, V and positions; every layer, row and slot) is bitwise
     equal to the snapshot's ring. This is the same KV state V0 restores.
   - New check: the bind at B writes only Sink slots. The digest of slots 3-5 is taken immediately before and after
     the bind operation, before the next generation call, and must be equal.
   - The bind's re-rotation count is recorded. It should be 0, because no realign happens with refresh frozen.
   - The bound Sink's SHA must equal the one packed at M.
3. **Reuse gate.** The reused B0, R and S3 runs come from earlier commits (f7730207, 4971e1cf). At the VD-5 commit,
   B0, R and S3 are rerun on one cell, dog s1 OT-1, and all three must match the stored runs' frame digests call by
   call. If any differs, all controls are rerun (36 runs, about 2 GPU h) and that gate result is reported.
4. **V0 gate.** V0 frame digests must equal REF on every call for the six visual cells.
5. **Usual checks.**
   - G3 passes.
   - The prefix is identical to REF.
   - The realized resets and binds match the schedule.
   - Preflight finds host D at elves-01's HEAD.
   - NIC isolation is recorded.

## 6. Blinded visual inspection (one session, `vd5`)

**Block A: single clips, fully blinded, inspected first.**
- Six clips per cell (REF, V0, B0, R, S3, RS3) give 36 clips.
- Four clips are repeated under fresh codes to measure within-session test-retest: B0 and R of two cells.
  Block A therefore has 40 clips.
- Order and codes come from a new seed. The key is sealed as in VD-4.
- The markers are the same as in VD-4: M and B borders and the call index.

Fields, using the listed words exactly:

| field | values | window |
|---|---|---|
| boundary jump at M | none / mild / strong | M |
| motion reversal | none / reversed / unclear | M..M+8 |
| content / appearance change | none / change | M..B |
| identity | kept / changed / unsure | M..B |
| color change | none / shift | M..B |
| flicker / temporal instability | none / flicker | M..B |
| new discontinuity at B | none / jump | B |
| notes | free text, never scored | |

- "Mild" and "strong" turn VD-4's unscored "not too bad" note into a scored field. A jump flag counts as mild or
  strong.
- Motion reversal is now a scored field. It was a free-text note in VD-4.

**Block B: paired comparisons, inspected after block A is complete.**
- In each trial, REF is shown labelled as the reference, next to two coded clips in random left / right order.
- Pairs per cell: RS3 vs R, and RS3 vs S3. Over 6 cells that is 12 trials.
- Two catch trials pair REF's own clip with V0, which should give "no difference". Block B therefore has 14 trials.
- Questions in each trial:
  - "Which shows the less visible discontinuity at M?" (left / right / no difference)
  - "Which stays closer to the reference over M..B (content, color, motion)?" (left / right / no difference)
- Paired judgments made inside one trial do not depend on the rater's absolute threshold. VD-4 showed that this
  threshold drifted from session to session.

**Rules.**
- Block A is recorded and committed before block B is opened.
- Both blocks are recorded and committed before the key is fetched, as in VD-4.
- One rater: the same one as VD-4. A second rater is recommended but not required, and would get the same session.
- Raw flag counts are never compared with VD-4's sessions.

## 7. Decision criteria (fixed before any run)

**Formal, per phase, using VD-4's resolution rule.**
- STRICT means numeric 12 / 12 and, on the six inspected cells, flags no greater than REF's in the same session.
- NEAR means numeric 12 / 12 and flags no greater than REF's plus 1.
- A jump flag is mild or strong. P2a flags are identity, content and color. P2b flags are flicker and motion
  reversal.

**Calibration gate on the rater.** The gate fails if any of the following holds:
- V0 receives more flags in any field than REF does plus 1;
- either catch pair in block B is not judged "no difference";
- fewer than 3 of the 4 within-session repeats match.

If it fails, the flag-based criteria are reported as "rater calibration failed". The decision then rests on the
numeric results and block B.

**Primary question: is RS3 sufficient for both P1 and P2?**
- **Yes** if RS3 is STRICT or NEAR on P1 and on at least one of P2a and P2b, with the other P2 phase numerically at
  least 11 / 12.
- **Fully yes** if RS3 is STRICT or NEAR on all three phases.
- **No** otherwise.

**Explicit comparison of RS3 with R and with S3.**
- RS3 vs R on P1:
  - non-inferior if RS3's V1 is at most R's V1 plus 0.10 x REF P99 in 12 / 12 cells;
  - in block B, RS3 must not be judged worse than R at M in more cells than it is judged better.
- RS3 vs S3 on P2:
  - non-inferior if, in 12 / 12 cells, RS3's D_c is at least S3's minus t_DINO, its C_c at most S3's plus t_dE, its
    warp excess at most S3's plus 0.10 x max(eR, 1), and its frame difference within plus or minus 0.10 x dR of
    S3's;
  - block B uses the same rule as for R.
- The tolerances are VD-3's per-cell values. The 0.10 x REF P99 margin for V1 is new and is fixed here.

**Complementary effects vs interaction, per cell and per metric.**
- The interaction is I = (RS3 - S3) - (R - B0), computed for V1, D_c, late D_c, C_c, dE_cross, warp excess and
  frame-difference ratio.
- A cell is **additive** if |I| is at most that metric's tolerance: t_DINO for D_c and late D_c, t_dE for C_c,
  t_dEx for dE_cross, 0.10 x max(eR, 1) for warp, 0.10 for the frame-difference ratio, 0.10 x REF P99 for V1.
  Otherwise it is **synergistic** if I points toward REF and **antagonistic** if it points away.
- The emulation is deterministic: identical configurations give identical digests, as stage 0a2 showed. So there is
  no run-to-run noise term, and the tolerances, not a noise model, set the scale.
- Reading:
  - **Complementary**: additive on at least 10 of 12 cells for every metric.
  - **Interaction**: synergistic or antagonistic on at least 3 of 12 cells for any metric. The metric, the
    direction and the cells are reported.
  - Anything else is mixed and is reported as such.

**What each outcome means for the next step.** Each implication below is oracle evidence only.
- RS3 sufficient and complementary: a practical M1 must deliver or approximate both states, and VD-4's
  per-state findings carry over.
- RS3 sufficient through synergy: the consistency between the two states matters, and a practical M1 should move
  them together.
- RS3 not sufficient: the residual gap to V0 lies in the decoder, the encoder cache, the refresh freeze or the bind.
  That would be the next diagnostic, which needs approval.

## 8. Cost (host D, about 3.3 min per run including metrics, as in VD-4)

| item | runs | GPU |
|---|---|---|
| RS3 on 12 cells | 12 | 0.65 h |
| V0 on dog s1 OT-L, butterfly s1 OT-L, audi s0 OT-L (3 visual cells already have V0) | 3 | 0.15 h |
| reuse gate: B0, R, S3 on dog s1 OT-1 | 3 | 0.15 h |
| **total** | **18** | **about 1.0 GPU h** |

- If the reuse gate fails, rerunning all controls adds 36 runs, about 2 GPU h.
- Rater time is about 40 single clips plus 14 paired trials, roughly one VD-4 session plus 15 minutes.
- RS3 adds 3451 MB of oracle bytes: 1725.6 MB recent plus 1725.6 MB Sink. Idealized transfer is 27.6 s at 1 Gbps
  and 2.76 s at 10 Gbps. This is a lower bound, not a migration latency.
- **Smallest design that separates complementary effects from interaction:** one new condition, RS3, on the 12
  cells, with the reused B0, R and S3 completing the 2 x 2. A smaller cell set would save about 0.4 GPU h. It would
  make the formal criterion unreachable, as in stage 2b, and leave too few cells for the counts in section 7.

## 9. Open points for review

1. Visual cells: the six targeted cells in one session (this proposal) or all 12 cells in two sessions.
2. The new V1 non-inferiority margin of 0.10 x REF P99.
3. Whether the exploratory motion-direction metric is wanted.
4. Whether a second rater is available.
5. Whether DRS3 (RS3 with the oracle decoder) should be added now as a fifth candidate (12 runs, +0.65 h) or held
   for the follow-up.
