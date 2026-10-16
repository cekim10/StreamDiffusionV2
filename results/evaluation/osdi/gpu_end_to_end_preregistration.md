# Experiment D: GPU end-to-end evaluation - preregistration (DRAFT for review, 2026-10-16)

Status: design only. Nothing here has run. Hypotheses and thresholds in section 7 are frozen at the commit that
follows the review and are not edited after results exist. The existing GPU results (single handoff, continuity
timeline, Phase 1 repeated mobility) are inputs to the predictions, not part of this experiment.

## 1. Question

Does the complete OTTER system (M1 + M2 + M3) improve migration interruption and visual continuity of real
StreamDiffusionV2 generation on the physical testbed, under single, repeated, mispredicted, contended, degraded and
revisiting mobility, and at what GPU and network cost? (RQ7, RQ8; GPU confirmation of RQ3, RQ5, RQ6.)

## 2. Hardware, network, workload

- Hosts elves-01..04, one NVIDIA L40S each (GPU 0); A = elves-01 (initial owner and Sink source), B, C, D = elves-02..04.
  GPU must be idle (0 % util, < 1 GiB used by others) before each run (`tools/eval/gpu_watch.py`); a run with another
  process on GPU 0 is invalid.
- Network: per-node egress and ingress shaped to 1 Gbps (max-min fair token buckets, as in all prior runs) and an
  unshaped condition (~9.4 Gbps); TCP_MAXSEG 1400 on every socket; kernel NIC counters sampled at 1 Hz on every host.
- Workload: StreamDiffusionV2, dog clip, prompt "A dog walks on the grass, realistic", seed 0, k = 2, 4 MiB fragments
  (412 per Sink), migration trigger at source chunk 30; generalization set (scenarios A and B only): bird and boxing
  clips, seeds 0-1. Reference: the uninterrupted same-seed run on the same GPU model (bit-exact; PSNR 99 dB).
- One generation session per GPU: a session allocates 25.8-25.9 GiB peak (single-handoff runs), so an L40S (48 GB)
  holds one session. Scenario E's contending sessions are therefore network-level sessions (see 4.E).

## 3. Policies (identical transport, fragment table, Sink version, schedule; they differ only where stated)

| name | execution at a move | Sink restoration | placement |
|---|---|---|---|
| Full migration | stop, transfer 6.02 GiB of GPU state, resume | inside the transfer | - |
| Cold restart | resume at once with fresh caches from the prompt | none (stream diverges) | - |
| M1 only | resume after 2.67 MiB of immediate state | source sends the whole Sink to each new owner; progress at abandoned owners discarded (= restart restoration) | - |
| M1 + M2 | as M1 | verified fragments preserved; newest holder forwards; source sends the rest (`split` / wavefront) | - |
| M1 + M2 + placement | as M1 | as M1 + M2 | top-1 placement with budget b and lookahead L |
| Full OTTER | as M1 | bottleneck-aware fragment assignment re-planned at moves and on measured changes (`reuse_dyn`, E-pilot v2 thresholds unchanged) | top-1 placement |
| External A, B | per their mechanism (see `external_baseline_audit.md`) | inside their checkpoint | - |

Oracle (`direct`, destination known from t = 0, no budget) is reported as an upper bound where meaningful.

## 4. Scenarios

| id | mobility | network | policies | reps |
|---|---|---|---|---|
| A | single A -> B | 1 Gbps, native | all + external | 3 (5 if IQR > 10 % of median) |
| B | repeated A -> B -> C -> D at rho = 2 and 4 | 1 Gbps | all except external (unless they support repeated moves) | 3 |
| C | single move; correct placement (true destination = top-1) | 1 Gbps; L = 10 s, b = 1 Sink, p = 0.6/0.3/0.1 | M1+M2, M1+M2+placement, Full OTTER, oracle | 3 |
| D | single move; incorrect placement (true destination = second candidate) | as C | as C | 3 |
| E | repeated (rho 2) for the GPU session + 3 network-level sessions restoring from A at the same time | 1 Gbps, A egress shared by 4 | M1 only, M1+M2, Full OTTER | 3 |
| F | repeated (rho 2); C's egress drops to 62.5 Mbps when D holds 50 % of the Sink | 1 Gbps then degraded | M1 only, M1+M2, Full OTTER (+ OTTER at moves as an ablation) | 3 |
| G | revisit A -> B -> C -> D -> B (rho 2) | 1 Gbps | M1 only, M1+M2, Full OTTER | 3 |

Scenario E is hybrid by necessity (section 2): the contending sessions run `restore_node.py` sessions with real-size
Sinks from elves-01 at the same time as the GPU session, and only the GPU session's metrics are reported.

## 5. Fairness and timing boundaries

- Destination preparation is identical for every policy: the destination process is started, the model weights are
  loaded, CUDA is initialized and a 250-call warm-up is run *before* the trigger; none of this is timed. External
  baselines get the same: if their restore requires a process image that contains the weights, the run is reported
  twice, "as designed" (weights inside the checkpoint) and, where the system allows it, with weights preloaded.
- Trigger: the orchestrator issues the move when the source finishes chunk 30 (orchestrator clock; per-node offsets from
  the clock-sync handshake are recorded). The same wall-clock move schedule is used for every policy in a scenario.
- Timing boundaries: TTFO = trigger -> first chunk output at the new owner; Sink verified = last fragment checksummed;
  Sink bind-ready = first output generated with the transferred Sink bound; rejoin = first chunk >= 35 dB after bind.
  Network bytes are counted at the senders' token buckets and cross-checked against NIC counters.
- State consistency: the Sink is serialized once at the trigger chunk; every fragment carries session id + Sink version
  (SHA-256 prefix); receivers reject mismatched fragments; the whole-Sink digest is re-checked before bind; adaptive
  Sink refresh is frozen at every destination until bind; RoPE positions are re-rotated at bind. The dog workload has
  no adaptive promotions (audited); a new-version path is not implemented and is a stated limitation.

## 6. Metrics

| metric | definition | unit |
|---|---|---|
| TTFO | trigger -> first output at the destination | s |
| Sink bind-ready | trigger (or final move) -> first output on the bound Sink | s |
| Rejoin | first chunk >= 35 dB PSNR to the reference after bind | s |
| Quality trajectory | PSNR / SSIM per chunk after the trigger | dB |
| Throughput | output chunks per second over [trigger, trigger + 60 s] | chunks/s |
| Output interval | time between consecutive chunk outputs (first = trigger -> first output) | s |
| Inter-frame latency P50/P95/P99 | interval between consecutive decoded frames, each timestamped at decode completion (new logging; not derived by dividing chunk intervals) | s |
| Jitter | P99 - P50 of the inter-frame interval | s |
| Deadline miss rate | share of frames whose inter-frame interval exceeds 1.5 x the median interval of the uninterrupted reference run (threshold fixed now) | % |
| Continuity coverage | share of output chunks in [trigger, end] at >= 35 dB | % |
| Network | source bytes, aggregate bytes, discarded bytes per Sink | Sinks |
| GPU | peak `memory_allocated`, `memory_reserved`, utilization (1 Hz NVML) at source and destination | GiB, % |
| Re-planning | count, detection delay, transition delay, drained bytes | -, s, MiB |

## 7. Hypotheses and criteria (frozen on approval; medians over reps)

- G1 (A, interruption): OTTER's TTFO <= 1.0 s at 1 Gbps and native, and <= 0.1 x full migration's at 1 Gbps.
  Predicted from the single-handoff runs: 0.71 s vs 53.8 s.
- G2 (A, continuity): OTTER's rejoin - bind <= 6 s at both bandwidths. Predicted 4.1 s.
- G3 (B, progress): at rho = 2 and 4, M1+M2's source bytes <= 1.1 Sinks per session while M1-only's >= 1.4; its Sink
  bind-ready after the final move within 1 s of M1-only's (both ingress-bound; Phase 1: 15.3 vs 15.3 s at rho 2).
- G4 (C, correct placement): bind-ready after the move <= no-placement's - 0.5 x (x_placed x T_s), x_placed = Sink
  fraction verified at the destination at the move. Predicted ~5 s vs ~15 s at 1 Gbps.
- G5 (D, incorrect placement): bind-ready within 1.5 s of no placement and source bytes <= 1.02 Sinks (the misplaced
  fragments are forwarded, not resent). Predicted equal (ingress-bound).
- G6 (E, contention): Full OTTER's and M1+M2's bind-ready after the final move <= M1-only's - 3.5 s (0.5 T_m).
  Predicted from Scenario B (net): ~10 s.
- G7 (F, degradation): Full OTTER's bind-ready after the final move <= 0.5 x M1+M2's. Predicted from Full E cond. 3
  (net): 14.0 vs 62.8 s (line-like forwarding from C) plus the bind step.
- G8 (G, revisit): every progress-preserving policy's bind-ready at B <= 0.6 x M1-only's. Predicted 7.4 vs 14.4 s.
- G9 (overhead): steady-state chunk service time with OTTER enabled and no migration within 2 % of unmodified
  generation; destination peak allocated within 1 % across policies (single handoff: 25.8-25.9 GiB).
- External baselines are compared descriptively (no pass threshold): TTFO, bytes, rejoin, success / failure.
- Run validity: all fragments verified; digest match; NIC peaks <= 1.15 x cap; paced egress <= 1.05 x cap over 10 s;
  four distinct hosts on one commit; GPUs idle before the run; reference available. Invalid runs are listed and
  re-run, never dropped.

## 8. Implementation required before any run (not started)

1. Move the restoration planners (`reuse_aware_in`, `reuse_dyn`, pre-positioning) out of `restore_orchestrate.py`
   into a module shared with `mobility_orchestrate.py`, so the GPU and network harnesses run the same decision code.
2. GPU harness: cap events, measured-throughput re-planning hooks, revisit paths, placement window before a move.
3. Full migration and cold restart as repeated-mobility execution policies (exist only in the single-handoff harness).
4. Per-frame output timestamps (decode completion) for inter-frame latency, jitter and deadline misses.
5. Hybrid scenario E: launch `restore_node.py` sessions alongside the GPU nodes (separate ports), shared token buckets
   at the source host.
6. Copy every node's `fragments.csv` back to the run directory.
7. External baselines per the audit.

Each item gets a loopback / single-host test and a one-run-per-policy shakedown (inspected) before the sweep.

## 9. Runs and cost

| scenario | runs (3 reps) |
|---|---|
| A | 6 policies x 2 bandwidths + external (2 x 2) = 16 x 3 = 48 |
| B | 5 x 2 rho = 10 x 3 = 30 |
| C, D | 4 x 2 = 8 x 3 = 24 |
| E | 3 x 3 = 9 |
| F | 4 x 3 = 12 |
| G | 3 x 3 = 9 |
| generalization (A, B on 2 more clips x 2 seeds, OTTER and the strongest baseline) | ~48 |
Total ~180 GPU runs at 2-3 min each after a ~3 min node start: ~8-10 h of exclusive use of four GPUs, plus external
baselines' setup.

## 10. Risks

- GPU sharing with other users on elves-03/04 (GPU 1 is used by others): must not touch GPU 0; checked per run.
- Scenario E is hybrid; it must not be described as four GPU sessions.
- Event-driven re-planning on GPU interacts with generation load on the same host (CPU contention for the sender
  threads); the steady-state overhead run (G9) bounds it.
- External baselines may fail outright on cross-node restore; that is reported as a result, with the error.
- Per-frame timestamps change the logging path; G9 checks it does not change service time.
