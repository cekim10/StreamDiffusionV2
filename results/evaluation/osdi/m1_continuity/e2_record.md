# M1 E2 record: input-log replay vs S3 and RS3 (2026-10-28)

Runs on host D at 9a564651 (recorded ed45f5d6, merged 64c82625). Blinded inspection: block A 5d2d8ace, block B
d5419e13, key aadab236 (merged on the Mac). Rules: `e2_plan.md`, fixed before the run. Full tables:
`e2_results.md` / `.json`. Oracle and replay conditions are emulations at the same snapshot. This says nothing yet about a
deployed protocol.

## 1. Validity

- Preflight clean (GPU 0 idle at start). GPU 0 log (`e2_gpu_watch.csv`, 312 samples): only E2's own processes, one at
  a time.
- Gate: VD-4's S3 on dog s1 OT-1, re-emulated with the overlay and hooks installed, equals the stored run on 158 / 158
  calls.
- 36 / 36 Replay runs valid: G3, prefix identical to REF, S3-path oracle checks, and every E2 check (window recorded,
  refresh frozen before and after, conditioning equal to the source, metadata equal per call and at M).
- The ring errors at M equal E1's on 36 / 36 runs.
- Merging the metrics changed no existing condition.
- **Deviation (form recognition, decided before the ratings were read):** both recorded forms changed the status to
  `RECORDED` but kept the instruction text after it. The aggregator required the bare line `STATUS: RECORDED`. It now
  accepts a line starting with `STATUS: RECORDED`; `NOT RECORDED` never matches. The substantive guard is unchanged:
  every row filled with the allowed words. Both forms pass it, with no vocabulary errors. Commit order checked: A
  before B before the key. The key's SHA-256 equals the forms'.

## 2. Numeric results (12 cells; VD-3's frozen rules)

| condition | P1 | P2a | P2b | P3 | V1 non-inferior to RS3 | P2 non-inferior to S3 | V1 gap S3 -> RS3 closed (median, range) |
|---|---|---|---|---|---|---|---|
| S3 | 10 / 12 | 11 / 12 | 11 / 12 | 12 / 12 | - | - | - |
| RS3 | 12 / 12 | 11 / 12 | 11 / 12 | 12 / 12 | - | - | - |
| Replay-3 | 12 / 12 | 11 / 12 | 11 / 12 | 12 / 12 | 12 / 12 | 12 / 12 | 0.93 (0.75-0.98) |
| Replay-6 | 12 / 12 | 11 / 12 | 11 / 12 | 12 / 12 | 12 / 12 | 12 / 12 | 0.99 (0.92-1.04) |
| Replay-12 | 12 / 12 | 11 / 12 | 11 / 12 | 12 / 12 | 12 / 12 | 12 / 12 | 1.00 (0.99-1.03) |

- **P1:** replay restores P1 at every window, including S3's two failures (audi s0 OT-L, dog s1 OT-L).
- **Closeness to RS3:** the median of (V1 - V1(RS3)) / P99 is 0.011 for w = 3, 0.004 for w = 6, and 0.000 for w = 12.
  Replay-12's V1 matches RS3's to two decimals on 9 / 12 cells.
- **P2:** no additional degradation. The P2 outcomes equal S3's and RS3's cell by cell. The two remaining failures
  (butterfly s1 OT-L late window, dog s1 OT-1 warp) are the ones VD-5 placed outside the KV ring.
- **Sink contamination:** refreshes inside the window wrote replayed frames into Sink slots, 0-14 per cell. The Sink K
  relative error at M is at most 0.035, 0.028 and 0.032 for w = 3, 6 and 12. It caused no P2 difference, and the bind
  at B replaces the Sink.
- **Most promising window (selection rule): Replay-12.** It ranked first on the two count criteria tied with the
  others, then on the closest V1 to RS3.

## 3. Cost

| window | replay, median total | log shipped |
|---|---|---|
| Replay-3 | 0.36 s | 1.2 MB |
| Replay-6 | 0.73 s | 2.4 MB |
| Replay-12 | 1.47 s | 4.8 MB |
| RS3, shipping the recent KV | 13.8 s at 1 Gbps, 1.38 s at 10 Gbps (idealized) | 1.73 GB |

- Replay costs 0.121-0.123 s per call, against a source call interval of about 0.55 s, so a shadow keeps up.
- **Predicted move:** the replay overlaps the source's last w calls, so nothing is added to the critical path.
- **Unpredicted move:** the replay is on the critical path. Replay-12 then costs 1.47 s, against 13.8 s to ship the
  recent KV at 1 Gbps. Replay-3 costs 0.36 s and already meets every numeric criterion.

## 4. Blinded inspection (Replay-12; one rater; VD-5's design)

- **Rater calibration: PASS.** V0 had no flag in any field (REF also none), both catch trials were "no difference" on
  both questions, and 4 / 4 repeats were identical.

| | REF | V0 | S3 | RS3 | Replay-12 |
|---|---|---|---|---|---|
| jump at M (six cells) | 0 | 0 | 5 (all mild) | 1 (mild, dog s1 OT-1) | 0 |
| any P2 or P3 field | 0 | 0 | 0 | 0 | 0 |

- **Block B, Replay-12 vs RS3:** "no difference" on all 6 cells for both the discontinuity at M and closeness to the
  reference.
- **Block B, Replay-12 vs S3:** Replay-12 has the less visible discontinuity on audi s0 OT-L; the other 5 cells are "no
  difference". Closeness to the reference: 6 "no difference".
- No notes were written.

## 5. Recommendation (e2_plan.md section 6): log-only replay

All four conditions hold for Replay-12:
- (a) P1 12 / 12;
- (b) V1 non-inferior to RS3 on 12 / 12;
- (c) P2 non-inferior to S3 on 12 / 12;
- (d) with a passing calibration, jump flags 0, against RS3's 1 + 1, and block B judging Replay-12 worse than RS3 at M
  in 0 cells.

Exact-base replay is not needed for the quality measured here.

Caveats:
- One rater, six inspected cells, the oracle-equivalent setting (Sink exact at M - w), and one model.
- The E2 numbers say any w >= 3 meets the numeric bar. The choice of 12 for the inspection follows the selection rule.
  A shorter window's visual quality was not inspected.
