# VD-5 record (2026-10-27)

Written after both inspection blocks were recorded (block A 7417a5dc, block B 5a985621, merged 37d360f1), the key was
copied (d71af66d, SHA-256 equal to the forms') and `aggregate_vd5.py` was run. Nothing frozen was changed: not the
preregistration, overlays, thresholds (SHA-256 792a6ac77ffbca24), forms, recorded inspections, key or frozen code. The
numeric, validity, reuse and interaction blocks of `vd5_results.json` are identical before and after the key. The
post-run notes (`vd5_postrun_notes.md`, 2216e5ba) were committed before block A was opened.

VD-5 is an **oracle sufficiency** diagnosis. Every condition injects state copied from the source snapshot. Nothing
here says whether that state can be delivered in time or whether it is necessary.

## 1. Validity

All PASS (details in `vd5_postrun_notes.md` section 1): preflight, reuse gate (B0 / R / S3 on dog s1 OT-1, 158 / 158
calls identical each), RS3 12 / 12 valid including every joint-restoration check (whole ring K, V and positions equal
to the snapshot after the reset; bind writes no recent slot or position), V0 equal to REF on the six visual cells.
Inspection procedure: block A committed in an earlier commit than block B, forms identical in skeleton, codes and key
SHA to the blank forms, no empty cell and no vocabulary error.

## 2. Formal results (frozen rules)

| condition | P1 | P2a | P2b | P3 |
|---|---|---|---|---|
| RS3 numeric | 12 / 12 | 11 / 12 | 11 / 12 | 12 / 12 |
| RS3 flags, six cells (REF) | 1 (1) | 0 (0) | 0 (0) | 0 (0) |

- **Rater calibration gate: FAILED.** V0 flags <= REF + 1 in every field (pass); both catch trials "no difference" on
  both questions (pass); repeats identical on all seven fields 2 / 4 (rule >= 3 / 4, fail). The two differing repeats:
  B0 of audi s0 OT-L, `strong` then `mild` (flagged both times); R of dog s1 OT-L, `mild` then `none` (flag changed).
- **Primary question: no.** By section 7 the answer falls back to the numeric rule; RS3 is 12 / 12 only on P1 and P3.
  The answer would also be no with a passing calibration, since STRICT and NEAR require numeric 12 / 12 (fixed before
  the inspection in the post-run notes).
- RS3 P1: numeric 12 / 12; its flag count equals REF's in the session (the aggregator prints STRICT). Because the
  calibration failed, this flag-based STRICT is reported as **"rater calibration failed"** and not claimed as a
  resolution.
- Remaining P2 failures (S3's two cells, as H0 predicted): butterfly s1 OT-L late-window content (late D_c -0.0286,
  limit -0.027); dog s1 OT-1 warp (eO - eR +0.33, limit 0.27).
- H0 (additive) holds. H1 (positive interaction) is not supported. H2 (negative interaction beyond tolerance) is not
  supported.

## 3. RS3 vs R and RS3 vs S3

| test | numeric | block B | verdict |
|---|---|---|---|
| RS3 vs R on P1 | V1 non-inferior 12 / 12 | at M: 6 no difference | non-inferior |
| RS3 vs S3 on P2 | non-inferior 12 / 12 | closer to REF: 6 no difference | non-inferior |

What RS3 adds (numeric, 12 cells, VD-3 rules):

| condition | P1 | P2a | P2b |
|---|---|---|---|
| B0 | 11 / 12 | 6 / 12 | 3 / 12 |
| R | 12 / 12 | 6 / 12 | 2 / 12 |
| S3 | 10 / 12 | 11 / 12 | 11 / 12 |
| RS3 | 12 / 12 | 11 / 12 | 11 / 12 |

- **Over R:** RS3 keeps R's reset (V1 within +-0.13 of R on 11 / 12 cells, all within the 0.10 x P99 tolerance) and
  adds S3's Sink-less-window behaviour (P2a 6 -> 11, P2b 2 -> 11).
- **Over S3:** RS3 fixes the two P1 failures of S3 (audi s0 OT-L V1 3.03 -> 2.07, P99 2.84; dog s1 OT-L 4.01 -> 1.80,
  P99 3.91) and leaves P2 at S3's level.
- **Interaction: complementary.** Every P2 metric is additive on 12 / 12 cells. V1 is antagonistic on two cells (audi
  s0 OT-1, audi s1 OT-L), where RS3's V1 stays at R's level and S3's own small V1 reduction does not add. No metric is
  synergistic on any cell: pairing the source recent KV with its own source Sink gives nothing beyond the sum.

## 4. Visual results (descriptive; one rater; calibration failed)

Block A flags on the six cells (field: jump at M unless stated):

| | REF | V0 | B0 | R | S3 | RS3 |
|---|---|---|---|---|---|---|
| jump at M (of which strong) | 1 (0) | 0 | 5 (3) | 1 (0) | 4 (2) | 1 (0) |
| motion reversal | 0 | 0 | 0 | 0 | 0 | 0 |
| any P2a field | 0 | 0 | 1 | 0 | 0 | 0 |
| flicker, jump at B | 0 | 0 | 0 | 0 | 0 | 0 |

- The jump at M is the only consistently scored visual defect. It tracks the recent KV: the conditions without it
  (B0, S3) carry 9 of the 11 non-REF jump flags and all 5 `strong` ratings. The rater noted on four of the `strong`
  clips that `strong` means noticeable to them.
- RS3's one flag (`mild`) is on audi s0 OT-L, where REF itself is flagged `mild`; V0, a bit-identical copy of REF, is
  not. R's one flag (dog s1 OT-L, `mild`) is the repeat that was rated `none` the second time.
- **Motion reversal** was not flagged (`reversed` or `unclear`) on any of the 40 clips, including B0 of audi s1
  OT-1, where earlier sessions noted the car driving backward. The audi motion anomaly was not observed in this session.
- **P2 visibility.** The only P2 flag is a content change on B0 of train s0 OT-1. In block B, RS3 vs R was "no
  difference" on closeness to REF in 5 / 6 cells, although R fails P2 numerically on 10 of the 12 cells and RS3 on 2. The two
  numeric P2 failures that RS3 keeps were not visible to this rater in block A or block B.
- **Block B preferences outside the tests:** both on audi s0 OT-L and both annotated "but very slight": RS3 closer to
  REF than R; RS3 less discontinuity at M than S3.
- **Rater consistency on identical videos** (4 repeats + 6 hidden REF / V0 duplicates): the jump-at-M flag agreed on
  8 / 10 and the severity on 7 / 10; the other six fields agreed on 10 / 10. Raw flag counts are not compared with VD-4's
  sessions.

## 5. Remaining continuity problems

- **Outside the KV ring.** RS3 restores the entire ring exactly, yet two cells still fail P2 by small margins. RS3
  differs from V0, which equals REF, only in the DR-2 decoder, the zero VAE encoder cache, the refresh frozen from M to
  B and the bind at B. The residual sits in one or more of these; VD-5 does not separate them.
- **The bind is not bitwise.** After the bind the Sink V is unchanged on 12 / 12 runs; the Sink K differs on the six
  OT-L runs (RoPE re-rotation over the longer interval). P3 is 12 / 12 and no clip was flagged at B.
- **The visual instrument is weak.** One rater, calibration failed, and the scored fields detect the boundary jump
  but not the numeric P2 differences. The flag-based part of every phase rests on this instrument.

## 6. Implications for a practical M1 mechanism (oracle sufficiency only; no M1 work started)

- **Both components are needed, and they do not substitute for each other.** Recent KV addresses the boundary
  discontinuity (P1) and the Sink addresses the Sink-less window (P2); their effects add with no synergy. A mechanism
  that delivers only one of them inherits the other's failure.
- **The cost splits in two, with different timing.** The oracle payload is 3450.5 MB (about half recent, half Sink;
  idealized lower bounds 27.6 s at 1 Gbps, 2.76 s at 10 Gbps; not a migration latency). The Sink is durable over the
  window and can be moved ahead of the cutover; the recent KV changes every call and is the part on the critical path.
  An earlier practical recent-KV handoff test (M1 / M2 follow-up A) found no gain at +0.9 s per slot, so delivering the
  recent KV cheaply is the open design problem.
- **The boundary jump is the perceptually dominant defect** in this session; the remaining numeric P2 gaps were not
  visible. This ranks P1 first for M1 under a one-rater observation, not a measurement.
- **Exact KV is not exact output.** With the full ring exact, two cells still fail P2. Reaching REF exactly would
  involve the decoder and VAE caches, the refresh policy or the bind, which VD-5 did not test.

## 7. Anomalies and notes

- **Aggregator display defect:** the per-cell interaction table of `vd5_results.md` prints both "additive" and
  "antagonistic" as "(a)". The counts, reading and JSON are correct (`vd5_postrun_notes.md` section 5).
- **Weak STATUS check:** `run_vc.py vd5 --phase key` tests for the string "STATUS: RECORDED", which the blank forms
  also contain in their instruction text, so an unfilled form would pass it. Both forms were checked directly here:
  every row filled, status line changed. No effect on this result.
- **Aggregator resolution label:** the resolution table prints STRICT for RS3 P1 without marking the failed
  calibration; section 2 states the preregistered reading.
