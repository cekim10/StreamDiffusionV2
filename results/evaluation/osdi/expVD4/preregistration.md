# Experiment VD-4 - which source-derived temporal state explains the remaining discontinuity: preregistration DRAFT 1 (2026-10-26)

Status: **DRAFT 1 for review. Not frozen; nothing implemented or run.** Diagnostic, emulator only, one GPU (host D).
Oracle conditions inject the source's exact state at the reset; they measure what each state component *would* fix,
never a practical migration latency. M1 / M2 / M3-v2 and every frozen result (including VD-3) stay as recorded.

**Question.** Which source-derived temporal states account for (primary) the perceptible migration-boundary jump that
remained in 7 of 16 VD-3 DR2+TSin clips, and (secondary) the Sink-less content (P2a) and temporal (P2b) deviations -
and do the P2a / P2b metric violations correspond to perceptible artifacts?

## 1. What VD-3 left, and a positional finding

- VD-3 DR2+TSin: P1 within REF P99 in 11 / 12 cells but a visible jump in 7 / 16 clips; P2a fails on train (content
  just outside REF's window variation) and butterfly (color, C_c +1.4-1.6); P2b fails in 9 / 12 (frame difference
  +13-23 %, warp up to +26 %); P3 passes; identity kept visually in 16 / 16.
- **Positional finding (2026-10-26, from the code and the source runs' logs).** Cached keys are stored after RoPE
  (`causal_rope_apply` before caching; `_realign_kv_positions` and the bind re-rotate them by position deltas). The
  TS-in prepare fills sink slots 0-1 with keys rotated at the prepare session's positions, and VD-2 / VD-3 wrote those
  keys into slots whose recorded positions are the source's. At the move the source's sink positions are [0, 1, .] on
  dog (aligned), [22, 24, .] on train OT-1 and audi s0 OT-1, [16, 35, .] on butterfly OT-1, [-29, -10, .] on butterfly
  s0 OT-L, [22, 1, .] / [30, 1, .] on audi s1 OT-1 / s0 OT-L (copied-schedule cells: to be logged). So VD-3's temporary
  Sink was **positionally misaligned by 16-34 frames** wherever the source had promoted or realigned a sink slot. The
  VD-3 pattern does not follow it cleanly (misaligned audi s0 OT-1 passed every phase; aligned dog failed P2b), so it is
  a hypothesis, tested here (condition A1). VD-3's frozen results are unchanged; its report gets this note.

## 2. Source-state capture (timing, consistency, completeness)

- **One snapshot per reset**, `serialize_live()` after call m-1 completes and before call m, the same instant from
  which the frozen fast path (meta, in-flight) and the withheld exact Sink are packed. Every oracle component comes
  from that snapshot, so components are mutually consistent and equal to what the source holds at the handoff.
- Components (bytes measured per run; estimates from earlier experiments): exact Sink K/V, 3 slots x 30 layers,
  about 0.575 GB per slot (1.725 GB); recent KV (slots 3-5) about 1.7 GB; VAE decoder cache about 1.8 GB (CACHE_T = 2
  per layer); VAE encoder cache (V0 only); fast path 2.8 MB; DR-2 latents 0.4 MB.
- **Completeness checks per stream:** every injected component's per-layer tensor count equals the snapshot's (30 DiT
  layers for KV; the decoder layer list), and the SHA-256 of the live injected tensors equals the snapshot's.
- **Positional checks per stream:** the source's sink and recent slot positions, the prepare's slot positions, and the
  per-slot delta are logged; oracle K/V are written with the source's positions (no re-rotation needed: same
  instant); temporary-Sink keys are written as in VD-3 unless the condition aligns them (A1).
- **Refresh:** frozen until the exact Sink binds (adapt_sink_thr = -1), as in frozen M1 and VD-3, in every diagnostic
  condition; REF's own promotions inside each Sink-less window are counted to interpret oracle-Sink conditions.
- **V0 (validity, not a condition):** injecting every component (Sink 3 / 3, recent, decoder and encoder caches, meta,
  in-flight) with refresh unfrozen (`restore_full`) must reproduce REF's output digests on every call after the move.
  This verifies capture timing, consistency and RoPE alignment of the oracle path. VD-4 stops if V0 fails.

## 3. Conditions (paired REF and the VD-3 DR2+TSin control on every cell)

| id | state at the reset (on top of the frozen fast path) | role |
|---|---|---|
| B0 | DR2+TSin exactly as in VD-3 (re-run; must reproduce VD-3's digests) | baseline / control |
| A1 | B0 with the temporary-Sink keys re-rotated to the source's slot positions (`_shift_temporal_rope`, delta = source pos - prepare pos) | positional hypothesis (section 1) |
| D | B0 with the DR-2 reconstruction replaced by the **oracle decoder cache** (encoder cache zero, as M1) | P1: decoder state |
| R | B0 + **oracle recent KV** (slots 3-5 with the source's positions) | P1 / P2b: recent temporal context |
| DR | B0 with oracle decoder cache + oracle recent KV | P1: both |
| S1 | B0 + oracle Sink slot 2 (the slot TS-in leaves empty); TS slots 0-1 kept | P2: one true slot, additive |
| S2 | B0 + oracle Sink slots 1-2 (replaces TS slot 1; TS slot 0 kept) | P2: two true slots |
| S3 | oracle Sink slots 0-2 (no temporary Sink left; DR-2 kept) | P2: full true Sink at the reset, refresh frozen |
| Q8 / Q4 (exploratory) | S3 with the Sink K/V quantized and dequantized: fp8 e4m3 per tensor (about 0.86 GB) / int4 group-wise, group 64 (about 0.43 GB + scales) | precision needed |

Slot replacement order is fixed: the empty slot first, then from the highest index down, so each step adds one true
slot and removes at most one temporary one. S1 and S2 keep B0's temporary-Sink keys as written in VD-3 (unaligned)
unless A1 is adopted at the Stage-1 gate (section 5), in which case S1 / S2 use A1's keys.

## 4. Outcomes (P1, P2a, P2b kept separate; VD-3's frozen definitions and thresholds; nothing re-tuned)

- **P1:** V1 at the reset vs REF P99 (set by VD-3); and the blinded visual "boundary jump at M".
- **P2a:** R2a (D_c, C_c, window dE) and R3 (late excess drift) with VD-3's set-A thresholds; visual "appearance
  drift", "identity", "color".
- **P2b:** R2b (warp <= 1.10 x REF, frame difference within +/- 10 %, near-zero safeguard); visual "flicker / jitter"
  and "motion consistency".
- **P3** reported (VD-3's rule) to show no condition harms the bind.
- **Bytes** added by each condition and the **transfer lower bound** at the line rate (bytes x 8 / rate; 1 Gbps and
  10 Gbps): e.g. one Sink slot 4.6 s / 0.46 s, decoder cache 14.4 s / 1.4 s, recent KV 13.8 s / 1.4 s. Reported as
  lower bounds of an idealized transfer, never as a migration latency; oracle states arrive instantly here.

**Decision statements (diagnostic; per state, on the 12 VD-3 confirmation cells):**
- a condition **resolves P1** if V1 <= REF P99 in 12 / 12 cells **and** its clips' boundary-jump flags are no more
  than REF's flags in the same inspection session + 1;
- **resolves P2a** if R2a and R3 hold in 12 / 12 and appearance / identity / color flags <= REF's + 1;
- **resolves P2b** if R2b holds in 12 / 12 and flicker / motion flags <= REF's + 1;
- attribution: a state is **sufficient** for a phase if the condition adding only that state resolves it; decoder
  cache and recent KV are **jointly sufficient** if DR resolves a phase that neither D nor R resolves alone; if no
  tested condition resolves a phase, the report states that the phase is **not explained by the tested states**.
- **Correspondence (secondary):** over every inspected clip, 2 x 2 tables of P2a metric violation vs any appearance /
  identity / color flag, and P2b metric violation vs any flicker / motion flag: agreement and Cohen's kappa, reported
  descriptively.

## 5. Staged execution (gates fixed now; each stage stops for the user's blinded inspection)

| stage | conditions x cells | runs | GPU (about 3.5 min / run incl. metrics) | gate to the next stage |
|---|---|---|---|---|
| 0 validity | V0 + B0 on dog s1 OT-1 and train s0 OT-1 | 4 | 0.3 h | V0 reproduces REF; B0 reproduces VD-3's digests; logs complete |
| 1 P1 + position | DR, A1 on 12 cells | 24 | 1.4 h | inspection 1 (REF, B0, DR, A1). If DR resolves P1: stage 1b. A1 adopted for S1 / S2 if it changes any P2 outcome class on >= 3 cells |
| 1b attribution | D, R on 12 cells (only if DR resolved P1) | 24 | 1.4 h | inspection 2 (D, R with REF, B0) |
| 2 P2 | S3 on 12 cells | 12 | 0.7 h | inspection 3. If S3 resolves P2a and / or P2b: stage 2b |
| 2b partial Sink | S1, S2 on 12 cells (only if S3 resolved a P2 phase) | 24 | 1.4 h | inspection 4 |
| 3 exploratory | Q8, Q4 on 4 cells (dog s1 OT-1, train s0 OT-1, butterfly s1 OT-1, audi s1 OT-1), only if S3 resolved a P2 phase | 8 | 0.5 h | - |

Worst case 96 runs, about 5.7 GPU hours, plus four inspection sessions (36-48 clips each, about 20-30 min). Best case
(DR does not resolve P1, S3 does not resolve P2): 40 runs, about 2.4 h. Stage 2 is independent of stage 1's P1 outcome
and may run right after stage 1.

## 6. Blinded visual assessment (all inspected clips; the user)

As VD-3 (random codes, randomized order and grid positions, M / B markers in every clip including REF, sealed key with
its SHA-256 in the form, form committed before the key is opened). Fields:
identity (kept / changed / unsure); appearance drift M..B (none / drift); color (no shift / shift); boundary jump at M
(no visible jump / jump); flicker / jitter M..B (none / flicker); motion consistency M..B (natural / unnatural);
new discontinuity at the exact Sink bind B (no visible jump / jump); notes. REF and B0 are in every session, so each
session has its own false-positive baseline.

## 7. What VD-4 can and cannot show

It can show which of the tested states, injected exactly at the reset, remove each remaining deviation, how much
precision the Sink needs (exploratory), and whether the metric violations are perceptible. It cannot show that any
state can be transferred in time (the lower bounds alone exceed several Sink-less windows at 1 Gbps), nor that a
practical approximation would work; either needs its own mechanism experiment and a testbed validation.

## 8. Open items for review

- Condition set and slot replacement order (section 3), the A1 adoption rule, the resolution criteria and the
  "REF flags + 1" visual allowance (section 4), the stage gates (section 5), the new inspection fields (section 6).
