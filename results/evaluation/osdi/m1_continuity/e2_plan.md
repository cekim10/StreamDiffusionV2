# M1 input-log replay, E2: plan, selection and recommendation rules (fixed before the run, 2026-10-28)

Approved 2026-10-28 after the E0 / E1 review. Question: is Recent KV rebuilt by input-log replay sufficient to keep
the migration boundary continuous? No new mechanism, no conditions beyond those listed, no migration protocol. Tool:
`tools/eval/m1_e2.py` (dry pipeline on the fake runtime passes). Nothing frozen is modified: the Replay conditions live
in `e2_schedules.json` (an overlay generated from the frozen S3 conditions), added to `vc_schedules.unit_sched` only
inside the E2 processes; vc_emulate, vc_check and vc_metrics run unchanged.

## 1. Conditions and cells

| condition | Sink at the move | recent KV at the move | run id | source |
|---|---|---|---|---|
| S3 | exact source (slots 2, 1, 0) | zero | `VD4x-S3` | VD-4, reused |
| RS3 | exact source | exact source | `VD5x-RS3` | VD-5, reused |
| Replay-w, w = 3, 6, 12 | exact source at M - w; refreshes in the window write replayed frames | rebuilt by replaying calls M - w .. M - 1 | `E2x-Lw` | new, 36 runs |

- Replay-w = S3's run (same schedule, M1 reset at M, DR-2 decoder, refresh frozen to the exact bind at B, bind of the
  exact Sink at B). Its ring is then rebuilt after the reset exactly as in E1:
  - the ring at M - w is restored with the recent slots zeroed (Sink, positions, indices, current_step and eviction
    queues exact);
  - the source's logged generator inputs for calls M - w .. M - 1 are replayed with the source's cache decisions
    forced.
- Cells: the 12 confirmation cells (train s0 / s1, audi s0 / s1, dog s1, butterfly s1; OT-1 M = 34, OT-L M = 80).

## 2. Validity (each must hold or the run is invalid)

- VC stream checks (G3, prefix identical to REF) and VD-4's S3-path oracle checks at the reset.
- E2 checks (`checks_supp`):
  - the window's inputs and the ring at M - w were recorded;
  - refresh was frozen before and after the replay;
  - the destination's prompt embeddings and cross-attention cache equal the source's;
  - every replayed call's metadata equals the source's after that call;
  - the ring metadata after the replay equals the source's at M.
- Gate (before any Replay run): VD-4's S3 on dog s1 OT-1 is re-emulated with the E2 overlay and hooks installed, and
  its output digests must equal the stored run call by call. If it fails, nothing else runs.
- Recorded, not required: the ring errors at M equal E1's for the same cell and window (same replay, now in the
  destination session).

## 3. Metrics (VD-3's frozen metrics, thresholds SHA-256 792a6ac77ffbca24, rules, playback model)

- P1: V1 at the reset against REF P99.
- P2a: D_c, C_c, dE_cross, late D_c, X_late.
- P2b: warp excess and frame difference.
- P3: no harm.

Also reported per window:
- recent and Sink relative error at M (from the run log);
- refresh writes inside the window;
- replay time per call and in total;
- log bytes.

## 4. Analysis (the four questions)

1. **P1 restored:** Replay-w P1 numeric passes against S3 (10 / 12) and RS3 (12 / 12).
2. **Closeness to RS3:**
   - V1 non-inferiority to RS3: V1(Replay-w) <= V1(RS3) + 0.10 x REF P99 (VD-5's margin), per cell.
   - The V1 gap closed, (V1(S3) - V1(Replay-w)) / (V1(S3) - V1(RS3)), as median and range.
   - (V1(Replay-w) - V1(RS3)) / P99, median.
3. **Additional P2 degradation:**
   - P2 non-inferiority to S3 with VD-5's tolerances (D_c, C_c, warp excess, frame difference), per cell.
   - P2a / P2b passes against S3's and RS3's.
   - Sink contamination at M (relative error, refresh writes).
4. **Cost:**
   - replay time per call and per window, and log bytes;
   - against shipping RS3's recent KV (1.73 GB; idealized 13.8 s at 1 Gbps, 1.4 s at 10 Gbps; about 2.7 s native in
     follow-up A).

## 5. Selection of the most promising window w* (numeric, before the inspection)

Order the windows by:
1. the most cells with both V1 non-inferior to RS3 and P2 non-inferior to S3;
2. then the most P1 passes;
3. then the smallest median (V1 - V1(RS3)) / P99;
4. then the smaller w.

The first is w*. The rule is applied by the aggregator, and the clips are made for that w only.

## 6. Blinded inspection (one rater, one session, two blocks; VD-5's design and vocabulary)

- **Cells:** VD-5's six visual cells (dog s1 OT-1, dog s1 OT-L, train s0 OT-1, butterfly s1 OT-L, audi s0 OT-L,
  audi s1 OT-1).
- **Block A:** REF, V0 (hidden REF duplicate), S3, RS3 and Replay-w* per cell, with random codes and grids (30 clips).
  It also has four repeats (S3 and Replay-w* of two cells, fresh codes). Fields are VD-5's seven.
- **Block B:**
  - 12 paired trials with the labelled reference: Replay-w* vs RS3, and Replay-w* vs S3.
  - 2 catch trials: REF vs V0.
  - Questions are VD-5's two.
- **Procedure:**
  1. Record and commit block A.
  2. Then open block B, record it and commit it in a later commit.
  3. Then copy the sealed key into `m1_continuity/e2_blind_key.json` and commit it in a later commit.
  - The aggregator checks the key's SHA-256 against the forms and checks the commit order.
- **Rater calibration (VD-5's rule):** it fails if any one of these holds:
  - V0 has more flags than REF + 1 in any field;
  - a catch trial is not "no difference" on both questions;
  - fewer than 3 of the 4 repeats are identical on all seven fields.

**Recommendation**
- **Log-only replay** if w* meets all four of:
  - (a) P1 numeric 12 / 12;
  - (b) V1 non-inferior to RS3 on 12 / 12;
  - (c) P2 non-inferior to S3 on 12 / 12;
  - (d) with a passing calibration and a valid procedure, Replay-w*'s jump-at-M flags on the six cells are at most
    RS3's + 1, and in block B Replay-w* is judged worse than RS3 at M in no more cells than better.
- If calibration fails or the procedure is violated, (d) is reported but not applied (numeric only).
- **Exact-base replay** otherwise.
- Raw flag counts are not compared with earlier sessions.

## 7. Cost and procedure

- About 37 runs on host D (36 Replay runs and 1 gate run), each with checks and metrics: about 2 GPU h.
- One command on D: `m1_e2.py run --frames_dir ... --clips_dir ...`. It runs the preflight (clean tree, idle GPU,
  committed overlay equal to the one built from the frozen schedules), the gate, the 6 units, the numeric aggregate
  with w*, and the blinded material.
- No commits or pulls on the testbed while it runs. Clips stay on D.
