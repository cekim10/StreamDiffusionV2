# Follow-up experiments W, R, N - common rules (DRAFT, 2026-10-18; not frozen, nothing implemented or run)

Approved scope (2026-10-18): pause Experiment T (`expT/HOLD.md`) and prepare prospective preregistration drafts for
- **W - Workload diversity** (`expW/preregistration_draft.md`): M1's continuity premise and Sink-version stability across inputs;
- **R - Repeated mobility** (`expR/preregistration_draft.md`): the operating region of M2 over rho and source contention;
- **N - Network adaptation** (`expN/preregistration_draft.md`): when M3's event-driven re-planning helps, does nothing or hurts.

Each draft is reviewed separately and frozen only on approval. Nothing in this document or the drafts changes Experiment
D (frozen v3, 81bb628; results `expD/expD_report.md`), the M3 implementation, or any earlier frozen outcome.

## 1. Scientific-integrity rules (apply to W, R, N)

1. **Experiment D is prior evidence, not new data.** Its numbers appear only as predictions and as the reason a
   condition was included. No ExpD run is re-analysed, pooled with, or counted as a W/R/N observation. Cells that repeat an
   ExpD configuration (e.g. R at rho 2 and 4 without contention) are new runs, judged on their own data.
2. **Thresholds are not tuned to reproduce ExpD.** Every threshold carries its origin in the drafts: (a) a requirement or
   bound frozen before ExpD ran (e.g. TTFO <= 1.0 s, G7's 1.0 s no-change band, both frozen 2026-10-16), (b) an
   analytic model of the mechanism stated in the draft, or (c) an explicit judgment value, labelled as such. Where ExpD
   suggests an outcome (including a failure), that is written down as a **recorded prediction** next to the hypothesis,
   never folded into the threshold.
3. **Negative findings are preserved.** Every confirmatory outcome is reported as SUPPORTED / NOT SUPPORTED / NOT
   EVALUABLE with its medians and rep counts; G5 and G9 of Experiment D stay NOT SUPPORTED whatever W/R/N show.
4. **No universal M3 claim.** N is designed to map where M3 helps, where it is neutral and where it costs; the paper may
   state M3's benefit only for the condition classes in which N's corresponding hypothesis is supported, and must report
   the classes in which it is not.
5. **Confirmatory vs descriptive.** Each draft lists its confirmatory hypotheses (decision rules fixed at the freeze)
   separately from its descriptive analyses (reported in full, never turned into a pass/fail after the data are seen).
   Exploratory sensitivity sweeps are run only after the primary matrix and never alter a primary verdict.
6. **Workload choice without outcome inspection.** The LOVEU-TGVE subset is fixed by a rule over input properties
   (`expW/loveu_tgve_verification.md`), computed before any OTTER run on those videos.

## 2. Shared testbed, definitions and validity

- Hosts elves-01..04, GPU 0 only, A = elves-01 (source), B, C, D = elves-02..04; per-node egress and ingress shaped to
  1 Gbps (max-min fair token buckets), TCP_MAXSEG 1400; warm destinations (process, weights, CUDA and a 250-call
  warm-up before the trigger), as in Experiment D section 5.
- Workload defaults (R, N, and W's repository clips): StreamDiffusionV2 1.3B, k = 2, 480x832, 4 MiB fragments
  (412 per Sink, 1,725,236,640 B), immediate state 2.67 MiB, trigger at source chunk M = 30.
- **Reference restoration time T_ref = 14.05 s**: the Phase 1 measured Sink transfer-ready time at 1 Gbps, the value every
  ExpD T_m used. It is fixed (not re-measured) so that rho = T_ref / T_m denotes the same schedule in every experiment.
- Timing boundaries and metrics as frozen in Experiment D section 5-6: TTFO, Sink bind-ready, rejoin (first chunk
  >= 35 dB PSNR against the uninterrupted same-seed reference after bind), B_pre, B_post, B_source,total, B_fwd,
  discarded bytes (Phase 1 definition (a)), re-plan count, duplicates.
- Run validity: `tools/eval/expD_validity.py` rules (all fragments verified, digest match, NIC peaks <= 1.15 x cap,
  paced egress <= 1.05 x cap over 10 s, four distinct hosts on one commit, GPU 0 idle, reference available). A run
  with a Sink-version event before the final bind is flagged; how each experiment treats it is stated in its draft.
  Invalid runs are kept, listed and re-run; a configuration whose runs are invalid for a **deterministic** reason (the
  same version event in every rep) is reported NOT EVALUABLE with the reason, not re-run indefinitely.
- Aggregation: medians over 3 valid reps per configuration (W: see its draft); "within X" = absolute difference.

## 3. Order and dependencies

1. **W1** (uninterrupted Sink-stability runs) first: it needs no network, and its dog-workload promotion count decides
   whether R's rho <= 1 cells are inside the single-version scope (an owner that binds before it is left keeps
   generating with adaptive refresh on; a promotion there is a version event).
2. Then W2, R and N in any order, each after its implementation items pass a loopback test and a one-run-per-policy
   GPU shakedown on pre-written correctness conditions (as in D0).

## 4. Implementation required before any run (none started)

| exp | item | why |
|---|---|---|
| W | per-call Sink fingerprint on the **value** cache of each sink slot per layer (values are not RoPE-rotated, so a t_refresh realignment does not change them) plus eviction-queue insertions that target sink slots | separate promotions (content change) from realignments (position change) |
| W | standalone uninterrupted runner for W1 (reuses `tools/state_ablation.py` Runner; 330 calls; one GPU) | W1 needs no orchestrator |
| W | fixed observation horizon in the orchestrator: the final owner generates until trigger + 100 calls whether or not it rejoins (today a run stops 12 calls after rejoin) | censoring needs a fixed window |
| W | loop-boundary marking per call (input frame index modulo the clip length) in `metrics.csv` | the harness repeats short clips (hard cut); dog is 81 frames (cut every ~20 calls) |
| W | LOVEU-TGVE preprocessing (archive to per-video mp4 + prompt files) and the motion-score script | subset rule |
| W | call-class labels (cut / boundary-adjacent / first-pass / repeated-input) in W1 and W2 logs; value fingerprints during the node baseline (reference Sink changes, RVC); the W-AR center-band variant script | W draft v2 sections 3.1, 5.1, 9 |
| R | GPU shakedown of rho <= 1 (an owner that bound the Sink forwards it as a holder under M1 + M2; M1 only drops it at the move) | never exercised on GPU; the node keeps `sink_buf` after bind, so no change is expected |
| R | hybrid network sessions at rho other than 2 (layout follows T_m) | ExpD ran E at rho 2 only |
| N | cap events relative to the move (today `t=` counts from migration start; with the 10 s placement window the move is at ~10 s) and `in`-direction caps in `--cap_events` | degradation timing and ingress degradation |
| N | per-run classification script (beneficial / neutral / harmful; per-re-plan records) | pre-specified analysis |

No change to the planner, its thresholds (`dyn_period`, `dyn_window`, `dyn_warmup`, `dyn_eps`, `dyn_rel`, `dyn_ctrl`),
the placement rules or the transfer path is part of these items.

## 5. Cost estimate (GPU 0 of four hosts; ~0.556 s per call)

| exp | primary runs | estimate |
|---|---|---|
| W1 | 40 uninterrupted runs (20 workloads x 2 seeds) | ~3 h on one GPU, ~45 min on four |
| W2 | 80 runs (40 units x 2 policies), 40 orchestrator invocations (the clip is a node argument) | ~6 h |
| W-AR | 12 runs (4 videos: W1 + W2 on the aspect-preserving variant; descriptive) | ~1 h |
| R | 90 runs (5 rho x 2 contention levels x 3 policies x 3 reps) | ~4.5 h |
| N | 90 runs (10 cells x 3 policies x 3 reps), 10 invocations (cap events are per invocation) | ~4.5 h |
| total | 300 GPU runs | ~16 h, plus exploratory sweeps listed in each draft |
