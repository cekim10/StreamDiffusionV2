# VD-5 preregistration: joint restoration of recent KV and exact Sink KV (FINAL, 2026-10-27)

Approved for implementation and execution on 2026-10-27 on the basis of `proposal.md` (draft 1, cebcb516). This
document fixes the open points of the proposal and the implementation details. VD-4 is complete and frozen; nothing of
it is changed. VD-5 is an **oracle sufficiency** diagnosis: every condition injects source state copied from the
snapshot taken at the move. It says nothing about whether that state can be delivered in time, or whether it is
necessary.

## 1. Question and predictions

Does restoring the source recent KV and the exact source Sink KV together (RS3) fix both the boundary discontinuity at
M (P1) and the Sink-less-window content and motion consistency (P2a, P2b)?

Fixed before any run, from VD-4 (12 confirmation cells, VD-3's frozen rules):
- **H0, additive.** RS3 has R's V1 and S3's P2 values. Predicted: P1 12 / 12; P2a and P2b 11 / 12, with S3's two
  failures remaining (butterfly s1 OT-L, late-window content; dog s1 OT-1, warp and frame difference). Under H0 RS3
  does not meet the 12 / 12 bar for P2.
- **H1, positive interaction.** R pairs the source recent KV, computed while attending to the source Sink, with the
  temporary Sink; RS3 restores the consistent pair. H1 predicts RS3 better than additive on P2 or on P1.
- **H2, negative interaction.** RS3 worse than R on P1 or worse than S3 on P2, beyond the tolerances of section 7.

## 2. Conditions

2 x 2: Sink {temporary TS-in (B0's), exact source} x recent {zero, source}, all with the same snapshot, schedule, reset
call M, bind call B, DR-2 decoder and frozen refresh from M to B.

| condition | Sink slots 0-2 | recent slots 3-5 | run id | source |
|---|---|---|---|---|
| B0 | TS-in, slot 2 zero | zero | `VD4x-B0` | VD-4 stage 1, reused |
| R | TS-in, slot 2 zero | source | `VD4x-R` | VD-4 stage 1, reused |
| S3 | source (2, 1, 0) | zero | `VD4x-S3` | VD-4 stages 0 and 2, reused |
| RS3 | source (2, 1, 0) | source | `VD5x-RS3` | new |
| V0 | everything from the snapshot, refresh unfrozen, no bind | | `VD4x-V0` | VD-4's definition; 3 runs exist, 3 new |

- RS3 is the VD-4 condition tuple `(dec "dr2", oracle_recent True, ts None, oracle_sink_slots [2, 1, 0])` with a
  `vd5` flag that adds the checks of section 5. It runs through VD-4's `vd4_reset` unchanged: fast path, oracle
  recent KV, oracle Sink slots, DR-2 decode, refresh frozen. It lives in its own overlay
  (`expVD5/vd5_schedules.json`), so `vc_schedules.json` and `vd4_schedules.json` stay byte-identical.
- V0 is bit-identical to REF (VD-4 stage 0). It is not a numeric condition; it is the positive control and, in the
  blinded session, a hidden duplicate of REF.
- RS3 differs from V0 only in the decoder (DR-2 instead of the exact cache), the zero VAE encoder cache, the frozen
  refresh from M to B, and the bind at B. Testing these is not part of VD-5.

## 3. Cells

- Numeric: the 12 VD-4 confirmation cells (train s0 and s1, audi s0 and s1, dog s1, butterfly s1; OT-1 and OT-L).
- Visual: one session, six cells: dog s1 OT-1, dog s1 OT-L, train s0 OT-1, butterfly s1 OT-L, audi s0 OT-L, audi s1
  OT-1. They cover the four inputs, both schedules, every cell where R or S3 failed a VD-4 rule, and the audi
  motion-reversal cell. The selection is targeted, which is why the numeric analysis covers all 12 cells.

## 4. Metrics

VD-3's frozen metrics, thresholds (`vd3_thresholds.json`, SHA-256 792a6ac77ffbca24) and rules (`aggregate_vd3.rules`),
unchanged, with the same playback model and per-cell REF as VD-4: P1 V1 at the reset; P2a D_c, C_c, dE_cross, late
D_c, X_late; P2b warp and frame difference; P3 no harm. The exploratory motion-direction metric of the proposal is
**not** included.

## 5. Validity (required before any result is read)

1. **RS3 runs:** stream valid (resets and binds as scheduled, prefix identical to REF, G3); VD-4's frozen oracle
   checks (meta positions, recent K / V / positions, Sink K / V / positions equal to the snapshot after the last reset
   operation) and supplemental per-layer / per-row checks, all present and true.
2. **Joint-restoration checks (new, `checks_supp`, each must be true or the run is invalid):**
   `vd5_slot_sets_disjoint` and `vd5_slot_sets_cover_ring` (Sink {0, 1, 2} and recent {3, 4, 5});
   `vd5_no_temporary_sink`; `vd5_ring_k_equal_snapshot`, `vd5_ring_v_equal_snapshot` and
   `vd5_ring_positions_rows_equal_snapshot` (the whole live ring, every layer, row and slot, equals the snapshot's
   after the reset); `vd5_bind_recent_k_unchanged`, `vd5_bind_recent_v_unchanged` and `vd5_bind_positions_unchanged`
   (the bind at B writes no recent slot and no position).
   - Recorded, not required: the bind's re-rotation count and whether the Sink after the bind equals the Sink just
     before it. On the GPU the bind re-rotates Sink entries by the position delta in every VD-4 condition (73-98
     (layer, row, slot) entries in B0, R and S3), and RoPE re-rotation is not bitwise. The bound Sink's SHA must equal
     the one packed at M (frozen emulator check).
3. **Reuse gate:** VD-4's B0, R and S3 on dog s1 OT-1 are re-run at the VD-5 commit (root `results/evaluation/expVD5g`)
   and their output frame digests must equal the stored runs call by call. If any differs, VD-5 stops before RS3; the
   controls would have to be re-run, which needs a decision.
4. **V0 gate:** on the six visual cells V0's outputs equal REF on every call after the move.
5. Preflight (host D at elves-01's HEAD), NIC isolation recorded.

## 6. Blinded inspection (one rater; one session in two blocks)

**Block A, single clips, fully blinded, inspected and committed first.** Six groups (one per visual cell: REF, V0, B0,
R, S3, RS3, random codes and grid positions) and a seventh group of four repeats (B0 and R of two cells chosen by the
order seed) under fresh codes: 40 clips. Window [M - 16, B + 20], VD-4's markers.

| field | values | flag | phase |
|---|---|---|---|
| boundary jump at M | none / mild / strong | mild, strong | P1 |
| motion reversal M..M+8 | none / reversed / unclear | reversed | P2b |
| content / appearance change M..B | none / change | change | P2a |
| identity M..B | kept / changed / unsure | changed | P2a |
| color change M..B | none / shift | shift | P2a |
| flicker / temporal instability M..B | none / flicker | flicker | P2b |
| new discontinuity at B | none / jump | jump | P3 |
| notes | free text | never scored | |

**Block B, paired comparisons, opened only after block A is committed.** Per visual cell RS3 vs R and RS3 vs S3, plus
two catch trials (REF vs V0): 14 videos [LEFT | REFERENCE | RIGHT], random sides and order. Questions: "less visible
discontinuity at M" and "closer to the reference over M..B (content, color, motion)", each left / right / no
difference.

**Procedure.** Both forms carry the SHA-256 of one sealed key. Block A is recorded and committed in an earlier commit
than block B (`run_vc.py vd5 --phase key` checks the ancestry), and the key is fetched only after both are committed.
Raw flag counts are never compared with VD-4's sessions.

## 7. Analysis and decision criteria

**Formal (RS3), VD-4's rule.** STRICT = numeric 12 / 12 and flags on the six inspected cells <= REF's in the same
session; NEAR = numeric 12 / 12 and flags <= REF's + 1. B0, R and S3 are reported the same way as within-session
descriptive rows (their formal VD-4 outcomes stand).

**Rater calibration gate.** It fails if V0 has more flags than REF + 1 in any field over the six cells, if either catch
trial is not "no difference" on both questions, or if fewer than 3 of the 4 repeats are identical to their first
rating on all seven fields. If it fails, the flag-based results are reported as "rater calibration failed" and the
primary answer uses the numeric rule only (numeric 12 / 12 in place of STRICT / NEAR).

**Primary question.** Yes: RS3 STRICT or NEAR on P1 and on at least one of P2a and P2b, with the other P2 phase
numerically >= 11 / 12. Fully yes: STRICT or NEAR on P1, P2a and P2b. No: otherwise.

**RS3 vs R (P1)** non-inferior: V1(RS3) <= V1(R) + 0.10 x REF P99 on 12 / 12 cells, and in block B RS3 judged worse at M
in no more cells than better. **RS3 vs S3 (P2)** non-inferior: on 12 / 12 cells D_c(RS3) >= D_c(S3) - t_DINO, C_c(RS3)
<= C_c(S3) + t_dE, warp excess(RS3) <= warp excess(S3) + 0.10 x max(eR, 1), |dO(RS3) - dO(S3)| <= 0.10 x dR; and in
block B RS3 judged further from the reference in no more cells than closer.

**Interaction.** Per cell and metric, I = (RS3 - S3) - (R - B0) on the lower-is-closer form of each metric: V1, -D_c,
-late D_c, C_c, dE_cross, warp excess eO - eR, |dO / dR - 1|. Additive if |I| <= the metric's tolerance (0.10 x REF
P99; t_DINO; t_DINO; t_dE; t_dEx; 0.10 x max(eR, 1); 0.10); synergistic if I is below -tolerance, antagonistic if
above. The emulation is deterministic, so the tolerances set the scale. Reading: complementary if additive on >= 10 /
12 cells for every metric; interaction if synergistic or antagonistic on >= 3 / 12 cells for any metric (metric,
direction and cells reported); mixed otherwise.

## 8. Cost

18 runs on host D (RS3 12, V0 3, reuse gate 3), about 1.0 GPU h at 3.3 min per run including metrics; clips on D.
RS3's oracle payload is about 3451 MB (idealized 27.6 / 2.76 s at 1 / 10 Gbps; not a migration latency).

## 9. Not included

DRS3 or any other condition; the motion-direction metric; a second rater; any M1 mechanism work.
