# Experiment RD results: visual recovery diagnosis (GPU, 2026-10-20)

Frozen preregistration `preregistration.md` (f850072; freeze record `../expRD_freeze.md`), implementation 24ad330. Runs
on elves-01..04 GPU 0 (commit 454cc03): Phase 0 5 runs, Phase 1 100 runs (`results/evaluation/expRD_phase{0,1}/`),
**105 / 105 valid, no re-run**. Verdicts by `tools/eval/aggregate_rd.py` (`phase0_gate.md`, `rd_results.{md,json}`);
nothing in the rules, thresholds or schedules was changed after the freeze. The pre-registered Phase 2 was not run (section 3).

## 1. Pre-registered outcomes

| item | result |
|---|---|
| Phase 0 fidelity gate | **PASS 5 / 5**: per-call PSNR of the emulation equals the real runs exactly (median and max abs dPSNR 0.00 dB) for W2 one-hop, VACW rho 1 three-hop, VACW rho 0.5 stale and fresh episodic, and dog rho 1 |
| determinism (S2) | median abs dPSNR 0.00 dB (repeat vs first, every workload) |
| dog control (S3) | r1 d = 0: 45.0 / 46.7 dB; crosses and sustains in all 24 dog conditions |
| butterfly | **EPHEMERAL** (E: T(r1, d = 0) = 34.6 / 34.1 dB < 35 at both anchors); D false (non-monotone: d = 0 -> 10 rises 2.6 / 5.8 dB); R false |
| audi-snow-trail | **UNCLASSIFIED** (drop d0 -> d100 7.8 / 4.9 dB, but a 1.4 dB rise d0 -> d10 at b175; R false) |
| train | **UNCLASSIFIED** (drop 12.7 dB at b155, 2.0 dB at b175; R false) |
| overall (section 7 rule) | no class shared by the three refresh-heavy workloads except UNCLASSIFIED (2 / 3): **no pre-registered cause class is established** |
| reset effect R | **absent in every refresh-heavy workload**: dR median 0.0 dB, 3-6 of 8 positive |

## 2. Descriptive findings (exploratory; none revises a verdict above)

- **Repeated resets show a negligible lasting effect under the tested conditions.** Each extra reset inside a Sink-less
  window perturbs the output for a few calls (up to 2.4-6.6 dB) and the trajectory then returns to the one-reset
  trajectory (median per-call difference 0.01 dB inside the window, 0.02-0.10 dB after the bind; terminal T within
  0.2 dB in 31 of 32 matched r1 / r3c pairs). This is what the R rule measured as absent; it is a statement about these
  workloads, anchors and reset spacings, not about migration count in general.
- **Sink-less duration is associated with reduced terminal PSNR for butterfly and audi-snow-trail.** For d >= 10, T is
  non-increasing in d (within 1 dB) at both anchors for both workloads; butterfly holds 35 dB up to d = 25 and ends at
  28.2-31.6 dB from d = 50, audi crosses up to d = 10-25 and ends at 26.7-28.1 dB from d = 50. Train depends on the
  anchor (b155: 44-46 dB up to d = 25, 32-34 dB after; b175: 34-36 dB at every d).
- **The 25-50-call transition is exploratory**, observed on two inputs, one seed and two anchors; it is not a general
  recovery threshold and is not used as one.
- **d = 0 can perform worse than d = 10**: butterfly 34.6 / 34.1 vs 37.2 / 39.9 dB, audi at b175 32.4 vs 33.8 dB, dog
  45.0 / 46.7 vs 49.6 / 49.6 dB; not train. This non-monotonicity is why the pre-registered D rule fails for butterfly
  and audi; its cause was not examined.
- **Episodic Sink loss ended like contiguous loss of the same total length** on butterfly (r3e d = 75: 28.4 / 29.4 dB;
  r3c d = 75: 28.8 / 29.7 dB), although a single 25-call episode recovers (33.5-36.3 dB).
- **Reference-trajectory recovery and temporal consistency are distinct.** In the last 10 calls of the horizon the
  input-motion-conditioned warp-error ratio E_O / E_R is 0.97-1.02 and the motion ratio 0.97-1.01 in every condition
  shown, including streams that never return to the reference (28 dB): a stream can leave the reference trajectory and
  still follow the input's motion as consistently as the uninterrupted one. During the Sink-less window the ratio is
  1.23-1.60 (refresh-heavy) and 1.77-3.12 (dog); a reset produces a frame-difference spike of median 5.5x the local
  median (max 16.6x; reference 1.0x), a bind 1.6x. None of these metrics establishes perceptual continuity.

## 3. Consequences and decisions (2026-10-20)

- Pre-registered conclusion: **no established cause class.** Descriptively, under the tested conditions, recovery
  failure tracks the total Sink-less generation time rather than the number of resets, which is consistent with
  restoration latency (M2 / M3, placement) being the lever; the paper may state this only as a descriptive,
  exploratory observation with its conditions.
- **The pre-registered Phase 2 (18 runs) is not run** (user decision): Phase 0 already shows exact per-call equality of
  the emulation with five real runs. A separate, explicitly exploratory real-migration follow-up (RD-X: one hop at
  320 Mbps, butterfly / audi-snow-trail / dog, seed 0, 2 reps, each compared with an emulation replay of its realized
  schedule) is planned in `followup_rdx.md`; it is not part of this preregistration's verdicts.
- Next priority after RD-X: M3-v2 end-to-end validation, ahead of further M1 development.

## 4. Limitations

Seed 0 only; three refresh-heavy inputs; two anchors; PSNR-to-reference and the section 5.2 metrics only; the d = 0
anomaly and train's anchor dependence are unexplained.
