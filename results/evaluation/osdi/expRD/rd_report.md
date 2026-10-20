# Experiment RD results: visual recovery diagnosis (GPU, 2026-10-20)

Frozen preregistration `preregistration.md` (f850072; freeze record `../expRD_freeze.md`), implementation 24ad330. Runs
on elves-01..04 GPU 0 (commit 454cc03): Phase 0 5 runs, Phase 1 100 runs (`results/evaluation/expRD_phase{0,1}/`),
**105 / 105 valid, no re-run**. Verdicts by `tools/eval/aggregate_rd.py` (`phase0_gate.md`, `rd_results.{md,json}`);
nothing in the rules, thresholds or schedules was changed after the freeze. Phase 2 not run (needs approval).

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

## 2. What the data show (descriptive; not used to revise any verdict)

- **Repeated resets have no lasting effect.** Each extra reset inside a Sink-less window perturbs the output (up to
  2.4-6.6 dB for a few calls) and the trajectory returns to the one-reset trajectory (median per-call difference
  0.01 dB in the window, 0.02-0.10 dB after the bind; terminal T within 0.2 dB in 31 / 32 refresh-heavy and dog pairs).
  Migration count per se is not what prevents recovery in these workloads.
- **Sink-less duration is strongly associated with recovery from d = 10 on.** For d >= 10, terminal T is non-increasing
  in d (within 1 dB) for butterfly and audi at both anchors, with a threshold between 25 and 50 Sink-less calls
  (14-28 s at 0.556 s per call): butterfly sustains 35 dB up to d = 25 and not from d = 50 (28.2-31.6 dB); audi crosses
  up to d = 10-25 and not from d = 50 (26.7-28.1 dB). Train depends on the anchor (b155: 44-46 dB up to d = 25, 32-34 dB
  after; b175: 34-36 dB at every d). The pre-registered D rule fails because of the d = 0 point (next bullet) and
  train's anchor dependence; this paragraph is an exploratory reading, not a verdict.
- **Immediate Sink bind after an M1 reset (d = 0) is worse than a 10-call delay** in butterfly (34.6 / 34.1 vs 37.2 /
  39.9 dB), audi at b175 (32.4 vs 33.8) and dog (45.0 / 46.7 vs 49.6 / 49.6); not in train. Cause not examined.
- **Episodic Sink loss behaves like the same total contiguous loss.** r3e at d = 75 (three 25-call episodes with bound
  gaps) ends at 28.4 / 29.4 dB on butterfly vs 28.8 / 29.7 for r3c d = 75, although a single 25-call episode recovers
  (33.5-36.3 dB). This matches the VACW rho 0.5 failure (three ~24-call episodes) and rho 1 failure (71 calls).
- **No-reference temporal consistency (section 5.2):** in the last 10 calls of the horizon the warp-error ratio E_O / E_R
  is 0.97-1.02 and the motion ratio 0.97-1.01 in every condition shown, including non-recovered ones (28 dB): the
  diverged stream follows the input's motion as consistently as the uninterrupted one. The Sink-less window is less
  consistent (ratio 1.23-1.60 on refresh-heavy inputs, 1.77-3.12 on dog), and resets produce a visible transition
  (frame-difference spike at the reset median 5.5x the local median, max 16.6x; reference 1.0x); binds 1.6x. These
  metrics do not establish perceptual continuity (section 5.2).

## 3. Consequences

- For the paper: the cause of the three-hop butterfly failure is **not repeated migration**; it is associated with the
  **total time the session generates without its Sink** (threshold 25-50 calls on two of three refresh-heavy inputs;
  workload- and position-dependent), i.e. with restoration latency. This supports the planned direction (M2 / M3 and
  placement shorten Sink-less time) over a new M1 cache mechanism; it does not establish a general bound.
- Claims-list update (`../paper_claims.md`, M1-2 / E2E-4): "after one move the stream returns ... how late the Sink may
  arrive is not established" can now cite RD as exploratory evidence of a 25-50-call threshold on two refresh-heavy
  inputs and no lasting effect of repeated resets; the pre-registered classification remains not established.
- Phase 2 (real one-hop / three-hop validation, 18 runs) was planned to test whether the emulation carries over to real
  migration. Phase 0 already shows exact per-call equality with five real runs; Phase 2 would add a bandwidth-limited
  one-hop run (d ~ 75) that has no real counterpart yet. Decision pending.

## 4. Limitations

Seed 0 only; three refresh-heavy inputs; two anchors; PSNR-to-reference and the section 5.2 metrics only; the d = 0
anomaly and train's anchor dependence are unexplained.
