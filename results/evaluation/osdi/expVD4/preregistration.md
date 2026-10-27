# Experiment VD-4 - which source-derived temporal state explains the remaining discontinuity: preregistration DRAFT 2 (2026-10-26)

Status: **DRAFT 2 (review of draft 1 applied; implementation and dry tests done, `implementation_plan.md`). Not frozen;
no GPU run.** Diagnostic, emulator only, one GPU (host D). Oracle conditions inject the source's exact state at the
reset: they show what a state *would* fix (oracle sufficiency), never that it can be migrated in time (practical
feasibility). M1 / M2 / M3-v2 and every frozen result, including VD-3's artifacts and thresholds, stay as recorded.

Changes from draft 1: A1 is an independent diagnostic and S1 / S2 are fixed relative to B0 (A1+S1, A1+S2 separate and
exploratory); oracle validity extended (bytes, digests, positions for every injected component; no later overwrite; K
re-rotation checked apart from V); Sink-slot results are not attributed to the slot count alone; strict and near
resolution with raw counts; D and R are mandatory; a preregistered non-monotonicity subset when S3 fails P2; P1, P2a,
P2b and oracle sufficiency vs practical feasibility kept apart.

**Question.** Which source-derived temporal states account for (primary) the perceptible migration-boundary jump that
remained in 7 of 16 VD-3 DR2+TSin clips and (secondary) the Sink-less content (P2a) and temporal (P2b) deviations, and
do the P2a / P2b metric violations correspond to perceptible artifacts?

## 1. What VD-3 left, and a positional finding

- VD-3 DR2+TSin: P1 within REF P99 in 11 / 12 cells but a visible jump in 7 / 16 clips; P2a fails on train (content just
  outside REF's window variation) and butterfly (color, C_c +1.4-1.6); P2b fails in 9 / 12 (frame difference +13-23 %,
  warp up to +26 %); P3 passes; identity kept visually in 16 / 16.
- Cached keys are stored after RoPE and re-rotated by position deltas (`causal_rope_apply`, `_realign_kv_positions`,
  the bind). The TS-in prepare fills sink slots 0-1 with keys rotated at the prepare session's positions (0, 1), and
  VD-2 / VD-3 wrote them into slots whose recorded positions are the source's: aligned on dog ([0, 1, .]), misaligned by
  16-34 frames on train OT-1 and audi s0 OT-1 ([22, 24, .]), butterfly OT-1 ([16, 35, .]), butterfly s0 OT-L
  ([-29, -10, .]), and in slot 0 on audi s1 OT-1 / s0 OT-L ([22, 1, .] / [30, 1, .]); copied-schedule cells are logged
  at run time. VD-3's pattern does not follow it cleanly, so it is a hypothesis (A1). VD-3's results stand.

## 2. Source-state capture and oracle validity

- **One snapshot per reset**: `serialize_live()` after call m-1 completes and before call m - the instant from which
  the frozen fast path (meta, in-flight) and the withheld exact Sink are packed. Every oracle component comes from it.
- **Per injected component, verified after the last reset operation** (so nothing later - the temporary-Sink write,
  the DR-2 decode, the refresh freeze - overwrote it): SHA-256 of K and of V separately equal to the snapshot's (or to
  the quantized copy's, Q8 / Q4); recorded positions equal to the snapshot's; per-layer completeness (30 DiT layers;
  the decoder layer list); bytes recorded. The live meta's positions equal the snapshot's.
- **Temporary-Sink slots that remain**: K equal to what was written (unrotated in B0; rotated in A1), V equal to the
  prepare's V (never rotated) - K and V checked separately. A1 additionally: K differs from the unrotated K wherever a
  delta is non-zero, and the rotate / rotate-back error is reported (RoPE re-rotation is not bitwise).
- **Refresh** frozen until the exact Sink binds in every diagnostic condition (as frozen M1 and VD-3); REF's own
  promotions in each Sink-less window are counted to interpret S3.
- **V0 (hard gate, stage 0)**: every component from the snapshot with refresh unfrozen and no bind must reproduce
  REF's output digests on every call after the move. **B0** must reproduce VD-3's DR2+TSin digests call by call.
  VD-4 stops if either fails.

## 3. Conditions (paired REF, the frozen-M1 control and B0 on every cell)

| id | state at the reset (on top of the frozen fast path) | role |
|---|---|---|
| B0 | DR2+TSin exactly as VD-3 | baseline / control |
| A1 | B0 with the temporary-Sink keys re-rotated to the source's slot positions (delta = source - prepare, per layer and slot; V untouched) | independent positional diagnostic |
| D | B0 with DR-2 replaced by the **oracle decoder cache** (encoder cache zero, as M1) | P1 |
| R | B0 + **oracle recent KV** (slots 3-5) | P1 / P2b |
| DR | B0 with the oracle decoder cache + oracle recent KV | P1 |
| S1 | B0 + oracle Sink slot 2 (the slot TS-in leaves empty); TS slots 0-1 as in B0 | P2 |
| S2 | B0 + oracle Sink slots 2, 1 (TS slot 0 as in B0) | P2 |
| S3 | oracle Sink slots 2, 1, 0 (no temporary Sink; DR-2 kept) | P2 |
| A1S1, A1S2 (exploratory) | S1 / S2 with A1's keys in the remaining TS slots | positional x Sink |
| Q8, Q4 (exploratory) | S3 with the Sink K / V quantized and dequantized: fp8 e4m3 per tensor / int4 groups of 64 | precision |
| V0 (validity) | everything from the snapshot, refresh unfrozen, no bind | gate |

S1 -> S2 -> S3 is a fixed replacement order (the empty slot first, then from the highest index down). A Sink effect is
reported **per slot set**; it is not attributed to the number of true slots alone, since the slots differ in identity
and age. If S1 resolves a phase, a separate slot-identity ablation (one true slot at each index) is proposed in a new
preregistration.

## 4. Outcomes (P1, P2a, P2b, P3 separately; VD-3's frozen definitions, thresholds and rules unchanged)

- **P1**: V1 at the reset <= REF P99; visual "boundary jump at M".
- **P2a**: R2a (D_c, C_c, window dE) and R3 (late excess drift), set A of `expVD3/vd3_thresholds.json`; visual
  "identity", "appearance drift", "color".
- **P2b**: R2b (warp <= 1.10 x REF, frame difference within +/- 10 %, near-zero safeguard); visual "flicker / jitter",
  "motion consistency".
- **P3**: VD-3's no-harm rule; visual "new discontinuity at the exact Sink bind".
- **Bytes and transfer lower bounds** (bytes x 8 / line rate at 1 and 10 Gbps): idealized, never a migration latency.

**Resolution of a phase by a condition (12 confirmation cells; raw counts always reported):**
- **STRICT**: the phase's numeric rules hold in 12 / 12 cells **and** the condition's clips carry no more flags for the
  phase than REF's clips in the same inspection session;
- **NEAR**: 12 / 12 numeric **and** flags <= REF's + 1;
- otherwise **not resolved**. A count of zero flags is an observation of one rater on these clips, not proof of zero
  risk.

**Attribution (per phase):** a state is **sufficient** if the condition adding only that state resolves the phase
(strict or near, stated which); decoder cache and recent KV are **jointly sufficient** if DR resolves a phase that
neither D nor R resolves; a failure of DR is never read as evidence that D or R alone is ineffective (they are run and
judged on their own); if no tested condition resolves a phase, it is **not explained by the tested states**. Every
statement is **oracle sufficiency**; practical feasibility (whether the state can arrive in time) is outside VD-4.

**Correspondence (secondary):** over every inspected clip (REF and B0 included), 2 x 2 counts of P2a metric violation
vs any identity / appearance / color flag and of P2b metric violation vs any flicker / motion flag, with Cohen's kappa;
descriptive.

## 5. Staged execution (gates fixed now; one blinded inspection session per stage with clips)

| stage | conditions x cells | runs | GPU (about 3.3 min / run incl. metrics) | inspection session | gate |
|---|---|---|---|---|---|
| 0 | V0, B0 on dog s1 OT-1, train s0 OT-1 | 4 | 0.2 h | - | V0 = REF and B0 = VD-3 digests on both cells, every oracle check true; otherwise stop |
| 1 | B0 (remaining 10 cells), DR, D, R, A1 on the 12 cells | 58 | 3.2 h | stage1: REF, B0, DR, D, R, A1 (72 clips) | - (D and R are mandatory) |
| 2 | S3 on the 12 cells | 12 | 0.7 h | stage2: REF, B0, S3 (36 clips) | S3 resolves P2a or P2b (strict or near)? |
| 2b, if S3 resolved | S1, S2 on the 12 cells; A1S1, A1S2 on the 4-cell subset | 32 | 1.8 h | stage2b (56 clips) | - |
| 2b, if S3 did not resolve | S1, S2, A1S1, A1S2 on the 4-cell subset (non-monotonicity check) | 16 | 0.9 h | stage2b (24 clips) | - |
| 3, only if S3 resolved | Q8, Q4 on the 4-cell subset | 8 | 0.45 h | stage3 (16 clips) | - |

The 4-cell subset is fixed now: dog s1 OT-1, train s0 OT-1, butterfly s1 OT-1, audi s1 OT-1 (one OT-1 cell per input,
the realized schedules). Totals: **90 runs, about 5.0 GPU h and 132 clips** (S3 does not resolve P2) to **114 runs,
about 6.3 GPU h and 180 clips** (it does). Stage 2 does not depend on stage 1's outcome. `run_vc.py vd4` enforces the
freeze, the stage-0 gate and the stage-2 gate (`vd4_gates.json`, written by `aggregate_vd4.py`).

## 6. Blinded visual assessment (the user; every session)

As VD-3: random codes, randomized cell order and grid positions, M / B markers in every clip including REF, sealed key
per session with its SHA-256 in the form, form committed before the key is opened (`run_vc.py vd4 --stage N --phase
key` refuses otherwise). REF and B0 are in every session, so each session has its own false-positive baseline. Fields:
identity (kept / changed / unsure); appearance drift M..B (none / drift); color (no shift / shift); boundary jump at M
(no visible jump / jump); flicker / jitter M..B (none / flicker); motion consistency M..B (natural / unnatural); new
discontinuity at the exact Sink bind B (no visible jump / jump); notes.

## 7. Interpretation limits

P1, P2a and P2b are reported and attributed separately. Oracle sufficiency is distinct from practical feasibility:
the added bytes' lower bounds alone exceed the Sink-less window at 1 Gbps for most states (decoder cache 14.4 s, recent
KV 13.8 s, one Sink slot 4.6 s vs about 14 s for OT-1). A resolving state motivates a mechanism experiment (what to send
or reconstruct, and when) with its own preregistration and a testbed validation. One model, four inputs, two seeds,
emulated schedules (three copied, counterfactual), one rater.

## 8. Open items for review

The condition table and fixed slot order (section 3), the strict / near definitions and the attribution wording
(section 4), the stage plan and the 4-cell subset (section 5), the inspection fields (section 6), and the freeze.
