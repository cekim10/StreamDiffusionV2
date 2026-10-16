# Experiment D: GPU end-to-end evaluation - preregistration (v3, FROZEN 2026-10-16)

**FROZEN.** G1-G9 (section 7) are frozen exactly as written in v3 (reviewed at commit 490ac98, approved 2026-10-16).
The freeze commit hash and date are recorded in `prereg_freeze.md`. No threshold, metric definition or comparison
group in sections 2-7 may change after this point; a later correction is added as a dated erratum below the freeze
record, and results are always judged against the frozen text. Scope conditions fixed at the freeze:
1. Frame-delivery SLO claims are out of scope (no consumer process); chunk-output latency is the primary latency metric.
2. Decode-level metrics (t_decode intervals, jitter, decode-deadline proxy) are descriptive.
3. External C/R comparisons are descriptive and never part of a primary speedup claim.
4. Cross-node C/R must be verified empirically on driver 575.51.03 before any external run; until then no external
   system counts as a successful migration baseline; failures go to the compatibility table.
5. Repeated mobility assumes a stable Sink version during a restoration.
6. Concurrent Sink-version evolution is unsupported and not claimed.
7. All earlier frozen network-level hypotheses and outcomes (section 0) are preserved unchanged, in particular
   H8a NOT SUPPORTED and H8c NOT SUPPORTED AS WRITTEN.

Status: design frozen; nothing here has run. v1 (7800261) and v2 (5267075) are superseded;
changes are listed in `prereg_v2_changes.md` (v1 -> v2) and `prereg_v3_changes.md` (v2 -> v3). The existing GPU results (single handoff, continuity timeline, Phase 1 repeated
mobility) and the network-level results are inputs to the predictions, not part of this experiment.

## 0. Relation to earlier frozen hypotheses

Experiment D re-measures some network-level effects on GPU; it does **not** re-test, reinterpret or replace any earlier
frozen hypothesis. The following outcomes stand as recorded, whatever Experiment D shows: H1 (progress loss in bytes:
yes; latency clause ill-posed), H2 (latency rejected; traffic supported), H3a supported, H3b rejected, P0/H4a/H4b
supported, H4c failed at (N=1, 500 Mbps) then the corrected rule met every Step 1 pass condition, A-pilot GO, H5d FAIL,
H5e 3 of 4 clauses PASS (slow-holder aware clause FAIL by 0.2 s), H6a-e supported, H6f supported on the four tested
conditions only, **H8a NOT SUPPORTED, H8b SUPPORTED, H8c NOT SUPPORTED AS WRITTEN**. A G-hypothesis that agrees or
disagrees with one of them is reported as a GPU observation next to the network-level outcome, not as a revision of it.

## 1. Question

Does the complete OTTER system (M1 + M2 + M3) reduce migration interruption and preserve visual continuity of real
StreamDiffusionV2 generation on the physical testbed, under single, repeated, mispredicted, contended, degraded and
revisiting mobility, and at what GPU and network cost? (RQ7, RQ8; GPU confirmation of RQ3, RQ5, RQ6.)

## 2. Hardware, network, workload, state-consistency scope

- Hosts elves-01..04, two NVIDIA L40S each, driver 575.51.03 on all four (confirmed 2026-10-16); experiments use GPU 0
  only (GPU 1 belongs to other users). A = elves-01 (initial owner and Sink source); B, C, D = elves-02..04. GPU 0 must be
  idle (0 % utilization, < 1 GiB used by others) before each run (`tools/eval/gpu_watch.py`), otherwise the run is invalid.
- Network: per-node egress and ingress shaped to 1 Gbps (max-min fair token buckets, as in all prior runs) and an
  unshaped condition (~9.4 Gbps); TCP_MAXSEG 1400 on every socket; kernel NIC counters sampled at 1 Hz on every host.
- Workload: StreamDiffusionV2 (PyTorch 2.6.0+cu124), dog clip, prompt "A dog walks on the grass, realistic", seed 0,
  k = 2, 4 MiB fragments (412 per Sink), trigger at source chunk 30. Generalization set (**scenario A only**, see the
  scope below): bird and boxing clips, seeds 0-1. Reference: the uninterrupted same-seed run on the same GPU model
  (bit-exact; PSNR reported as 99 dB).
- One generation session per GPU: a session allocates 25.8-25.9 GiB peak (single-handoff runs); an L40S (48 GB)
  holds one. Scenario E therefore uses hybrid contention (section 4).
- **State-consistency scope.** The evaluation is restricted to restoration of the single Sink version frozen at the
  trigger: the source serializes the Sink once at chunk 30; every fragment carries session id + Sink version (SHA-256
  prefix); receivers reject mismatched fragments; the whole-Sink digest is re-checked before bind; adaptive Sink
  refresh is frozen at every destination until it binds; RoPE positions are re-rotated at bind. Consequences:
  (i) repeated-mobility scenarios (B, E, F, G) use the dog workload only, which has no adaptive promotions over the
  measured window (audit in EXPERIMENT_PLAN.md); (ii) at rho = 2 and 4 no intermediate owner binds before being left
  (T_m < T_s), so no owner can create a new version that holders would then hold stale fragments of; (iii) the
  generalization clips (which do promote after bind) are used only in single-move scenario A; (iv) a run that logs
  any `fragment_rejected_version`, a digest mismatch, or a promotion at an owner before the session's final bind is
  flagged, excluded from every G criterion, and reported with its count. A new-version / re-fetch path is not
  implemented and is a stated limitation; no result here speaks to Sinks that change during restoration.
- **Explicit evaluation assumption (stated in the paper):** *repeated-mobility evaluation assumes a stable Sink version
  for the duration of a restoration; OTTER's preservation and reuse of verified fragments (M2) and its provider
  assignment, placement and re-planning (M3) are evaluated only within one Sink version.* Concurrent Sink-version
  evolution (a promotion that invalidates fragments held elsewhere, followed by re-planning and transfer of the new
  version) is not supported and not claimed. How often promotions occur on other workloads during a restoration window
  is an open measurement, not part of Experiment D.

## 3. Policies (identical transport, fragment table, Sink version and move schedule; they differ only where stated)

| name | execution at a move | Sink restoration | placement |
|---|---|---|---|
| Full migration | stop, transfer 6.02 GiB of GPU state, resume | inside the transfer | - |
| Cold restart | resume at once with fresh caches from the prompt | none (stream diverges) | - |
| M1 only | resume after 2.67 MiB of immediate state | source sends the whole Sink to each new owner; fragments at abandoned owners discarded (= Phase 1 `restart`) | - |
| M1 + M2 | as M1 | verified fragments preserved; newest holder forwards; source sends the rest (= Phase 1 `split`) | - |
| OTTER at moves | as M1 | M1 + M2 + bottleneck-aware fragment assignment re-planned at moves only (`reuse_aware_in`) | as the scenario says |
| OTTER event-driven | as M1 | as OTTER at moves + re-planning on measured throughput changes (`reuse_dyn`, E-pilot v2 thresholds unchanged) | as the scenario says |
| External C/R (cuda-checkpoint + CRIU; GCR adapted) | per their mechanism (see `external_baseline_audit.md`) | inside their checkpoint image | - |

"Full OTTER" = OTTER event-driven with top-1 placement where the scenario provides a prediction (C, D); in scenarios
without a prediction (A, B, E, F, G) placement is disabled for every policy, so Full OTTER = OTTER event-driven there.
Oracle (`direct`: destination known from t = 0, no budget) is reported as an upper bound where meaningful.

## 4. Scenarios

| id | mobility | network | policies | reps |
|---|---|---|---|---|
| A | single A -> B | 1 Gbps, native | Full migration, Cold restart, M1 only, OTTER event-driven; OTTER cold-destination (sensitivity, section 5); external C/R (both comparisons) | 3 (5 if IQR > 10 % of median) |
| B | repeated A -> B -> C -> D at rho = 2 and 4 | 1 Gbps | Full migration, Cold restart, M1 only, M1 + M2, OTTER at moves, OTTER event-driven | 3 |
| C | single move; correct placement (true destination = top-1) | 1 Gbps; L = 10 s, b = 1 Sink, p = 0.6/0.3/0.1 | M1 + M2 (no placement), M1 + M2 + top-1, Full OTTER, oracle | 3 |
| D | single move; incorrect placement (true destination = second candidate) | as C | as C | 3 |
| E | **hybrid GPU/network contention**: one GPU generation session moving A -> B -> C -> D at rho 2, plus three network-level restoration sessions (no generation; `restore_node.py`, real-size Sinks) restoring from the same source host A at the same time | 1 Gbps, A's egress shared by the four restorations | M1 only, M1 + M2, OTTER event-driven | 3 |
| F | repeated (rho 2); C's egress drops to 62.5 Mbps when D holds 50 % of the Sink | 1 Gbps then degraded | **OTTER event-driven and OTTER at moves (primary)**; M1 + M2 and M1 only (secondary) | 3 |
| G | revisit A -> B -> C -> D -> B (rho 2) | 1 Gbps | M1 only, M1 + M2, OTTER at moves, OTTER event-driven | 3 |

Scenario E is never described as four GPU generation sessions: only one session generates; G6 and every GPU metric in
E refer to that session; the three network-level sessions' fragment-completion times are reported separately.

## 5. Fairness and timing boundaries

- **OTTER and the in-repo baselines (warm destination):** the destination process is started, the model weights are
  loaded, CUDA is initialized and a 250-call warm-up is run *before* the trigger; none of this is timed. This holds for
  Full migration, Cold restart, M1 only, M1 + M2, OTTER at moves / event-driven.
- **Two comparison groups, reported in separate figures/tables and never combined into one speedup claim:**
  1. **Primary migration comparison (warm destination, in-repo).** OTTER (warm destination), Full migration (warm
     destination), Cold restart (warm destination), and the M1/M2/M3 ablations. All headline OTTER numbers (G1-G9)
     come from this group only.
  2. **External system comparison (deployment as designed).**
     - *External C/R as designed*: the destination host has the same binary, libraries, model files on disk and the
       NVIDIA driver in persistence mode, but no running process; the checkpoint image (process memory including
       weights held in host memory, staged GPU memory, CUDA state) is dumped at the trigger, transferred over the same
       shaped link, and restored; timed from trigger to first output, with dump / transfer / restore reported separately.
     - *OTTER cold destination*: the destination starts the process and loads the weights after the trigger, then OTTER's
       M1 handoff runs; this is the OTTER configuration comparable to C/R as designed (both pay process creation and
       weight loading).
     - *External C/R lower bound, where applicable*: image transfer + restore time excluding the weights, labelled as a
       lower bound, for systems that cannot restore into a warm destination (CRIU recreates the process).
     OTTER warm-destination timings are never divided by, or plotted on the same speedup axis as, as-designed C/R
     timings.
  3. **Compatibility results.** Cross-node restore with cuda-checkpoint on driver 575.51.03 is unverified (its
     GPU-migration API needs 580). If a system fails to restore on another host, the failure (system, configuration,
     error) goes to a separate compatibility table; it is not plotted on the performance axes next to systems that
     completed a migration. Where same-node C/R plus a measured image transfer is reported instead, it is labelled
     "not a cross-node migration" and kept in the external group.
- Trigger: the orchestrator issues the move when the source finishes chunk 30 (orchestrator clock; per-node offsets from
  the clock-sync handshake are recorded). The same wall-clock move schedule is used for every policy in a scenario.
- Timing boundaries (all relative to the trigger, or to the final move in repeated scenarios):
  TTFO = first chunk completed at the new owner; Sink verified = last fragment checksummed at the owner;
  Sink bind-ready = first chunk completed with the transferred Sink bound; rejoin = first chunk >= 35 dB after bind.

## 6. Metrics

Timestamps (three distinct events per output, all on the generating host's clock, offset-corrected):
- **t_chunk**: chunk completion = the model call returns and the GPU stream is synchronized (exists today).
- **t_decode(f)**: frame decode completion = VAE decode of frame f finished and synchronized (new logging).
- **t_deliver(f)**: frame delivery = frame f's bytes handed to and acknowledged by a consumer process. **No consumer
  exists in the harness today.** Until one is implemented with defined semantics (transport, buffering, playout clock),
  no delivery or frame-level SLO metric is reported and no SLO-compliance claim is made.

| metric | definition | unit | status |
|---|---|---|---|
| TTFO | trigger -> first t_chunk at the new owner | s | hypothesis (G1) |
| Sink bind-ready | trigger (or final move) -> first t_chunk with the Sink bound | s | hypotheses |
| Rejoin delay (wall clock) | t_chunk of the first chunk >= 35 dB after bind minus t_chunk of the first bound chunk | s | G2 |
| Rejoin calls | number of generation calls from the first bound chunk to the first chunk >= 35 dB | calls | G2 |
| Quality trajectory | PSNR / SSIM per chunk after the trigger | dB | descriptive |
| Throughput | chunks completed per second over [trigger, trigger + 60 s] | chunks/s | descriptive |
| Chunk interval | t_chunk differences (first = trigger -> first chunk) and its P50 / P95 / P99 / max | s | descriptive |
| Decode interval | t_decode differences between consecutive frames, P50 / P95 / P99, jitter = P99 - P50 | s | descriptive |
| Decode-deadline miss rate (proxy) | share of frames whose decode interval exceeds 1.5 x the median decode interval of the uninterrupted reference run | % | descriptive; explicitly not an SLO |
| Continuity coverage | share of chunks in [trigger, end] at >= 35 dB | % | descriptive |
| Pre-move source bytes B_pre | bytes sent by the original source A for this session before the move (placement) / Sink size | Sinks | G5 |
| Post-move source bytes B_post | bytes sent by A for this session after the move (restoration) / Sink size | Sinks | G3, G5 |
| Total source bytes | B_source,total = B_pre + B_post | Sinks | G3, G5 |
| Holder-forwarded bytes B_fwd | bytes received and checksum-verified at the owner whose sender is not A (orchestrator `fragments.csv`, `recv` rows: `src` != A, `ok` = True, `dup` = False) / Sink size | Sinks | G5 |
| Aggregate network bytes | B_network,total = B_source,total + B_fwd + bytes forwarded to non-owners (all links) / Sink size | Sinks | reported (G3, G5) |
| Discarded bytes | bytes delivered to an owner that neither bound nor forwarded them (Phase 1 definition a) / Sink size | Sinks | G3 |
| Verified progress retained | fragments checksum-verified at an owner at the moment it is abandoned that are still held (not dropped) at the next move, divided by fragments verified there | fraction | descriptive |
| Verified progress reused | distinct fragments verified at an abandoned owner that the final owner received and verified from an abandoned owner (`recv` rows at the final owner with `src` in the abandoned owners), divided by distinct fragments verified at abandoned owners | fraction | descriptive |
| x (placement) | fraction of the Sink's fragments fully received **and checksum-verified** at the misplaced holder at or before the move trigger (`recv` rows with `ok` = True and t <= t_move); fragments in flight at the trigger are excluded | fraction | G4, G5 |
| GPU | peak `memory_allocated`, `memory_reserved`, utilization (1 Hz NVML) at source and destination | GiB, % | G9 |
| Re-planning | count, detection delay, transition delay, drained bytes, duplicates | -, s, MiB | G7 |

## 7. Hypotheses and criteria (NOT YET FROZEN; medians over valid reps)

Predictions come from committed measurements (GPU where available, otherwise network-level) and are written before
the run; network-level predictions add the GPU bind step (~0.3-0.4 s at 1 Gbps, continuity notes).

- **G1 (A, interruption):** OTTER event-driven's TTFO <= 1.0 s at 1 Gbps and native, and <= 0.1 x Full migration's at
  1 Gbps. Prediction (single handoff, GPU): 0.71 s vs 53.8 s.
- **G2 (A, continuity recovery):** at both bandwidths, OTTER's rejoin delay <= 6.0 s wall clock **and** rejoin calls
  <= 8. Both values are reported for every run. Prediction (GPU): 4.1 s and 6 calls at 1 Gbps; 6 calls at every
  bandwidth in the single-handoff table.
- **G3 (B, progress preservation; consistent with Phase 1):** at rho = 2 and 4, all of
  (a) source bytes: M1 + M2 <= 1.10 Sinks per session and M1 only >= 1.40 (Phase 1: split 1.06 / 1.02, restart 2.01 / 1.51);
  (b) discarded bytes: M1 + M2 <= 0.10 Sink and M1 only >= 0.40 (Phase 1: 0.07 / 0.04 vs 1.01 / 0.51);
  (c) Sink bind-ready after the final move: M1 + M2 within 1.0 s of M1 only (both ingress-bound; Phase 1: 15.3 vs
  15.3 s at rho 2, 14.8 vs 15.4 s at rho 4).
  Descriptive (no pass threshold): verified progress retained and verified progress reused (section 6). For reference,
  reused is directly measurable from the Phase 1 per-fragment logs (`repeated_mobility/policy=split_*/fragments.csv`,
  read-only analysis 2026-10-16): 0.974-0.983 at rho 2 (3 sweep reps + the shakedown rep) and 0.961-0.967 at rho 4;
  restart 0 by construction. These are reported next to the Experiment D values, not used as a criterion.
  Aggregate network bytes are reported and **not** a pass condition: Phase 1 measured them equal at rho >= 2 (2.02 vs
  2.01, 1.51 vs 1.51), because forwarding a held fragment costs the same link bytes as sending it from the source. The
  hypothesis is that preservation removes discarded work and source load, not total traffic or single-ingress latency.
- **G4 (C, correct placement):** bind-ready after the move <= no-placement's - 0.5 x (x x T_s), with x the fraction of
  the Sink fully received and checksum-verified at the (correct) destination at or before the move trigger. Prediction (A-pilot, net): x_placed 0.71; 4.0 vs 14.0 s
  (+ bind step).
- **G5 (D, incorrect placement):** with x = fraction of the Sink fully received and checksum-verified at the misplaced
  holder at or before the move trigger (in-flight fragments excluded), all of
  (a) bind-ready within 1.5 s of no placement;
  (b) B_source,total = B_pre + B_post <= 1.02 Sinks;
  (c) B_post <= (1 - x) + 0.02;
  (d) B_fwd >= 0.9 x x. This clause is a pass criterion because B_fwd is measured directly from per-fragment `recv`
  records at the owner that carry the sender (`src`) and checksum result (`ok`), as the GPU harness already logs them
  (`repeated_mobility/*/fragments.csv`); if a run lacks those records for any fragment, (d) is reported as not
  evaluable for that run rather than inferred.
  Reported separately in every run: B_pre, B_post, B_source,total, B_fwd, B_network,total (expected 1 + x: the
  misplaced fraction crosses two links). These accounting identities hold only if each pre-positioned fragment is
  delivered to the owner once; duplicates are counted and reported. Prediction (A-pilot, net): B_pre 0.71, x 0.71,
  B_post 0.29, B_source,total 1.00, B_fwd 0.72, B_network,total 1.72; bind-ready equal to no placement (ingress-bound).
- **G6 (E, hybrid GPU/network contention):** for the one GPU generation session, M1 + M2's and OTTER event-driven's
  Sink bind-ready after the final move <= M1 only's - 3.5 s (0.5 T_m). Prediction (Scenario B v2, net, N = 4 one move):
  9.7 s lower. The claim is limited to source-egress contention created by network-level sessions; it says nothing
  about four concurrent GPU generations.
- **G7 (F, mid-restoration degradation):** primary: OTTER event-driven's Sink bind-ready after the final move <= 0.5 x
  OTTER at moves', with <= 2 re-plans and 0 duplicates; and in scenarios B and G (no change) OTTER event-driven makes
  0 re-plans and is within 1.0 s of OTTER at moves. Secondary (reported, not a pass condition): OTTER event-driven vs
  M1 + M2 and vs M1 only. Prediction (Full E cond. 3, net): 14.0 vs 53.8 s (at moves), 62.8 s (line-like M1 + M2
  forwarding from C), 14.0 s (M1 only, idle source), each + bind step.
- **G8 (G, revisit):** every progress-preserving policy's Sink bind-ready at the revisited B <= 0.6 x M1 only's.
  Prediction (Full E cond. 4, net): 7.0 vs 14.0 s + bind step; 0.50 Sink still at B on return.
- **G9 (overhead):** steady-state chunk service time with OTTER enabled and no migration within 2 % of unmodified
  generation (same GPU, same seed, 3 reps of 200 chunks); destination peak `memory_allocated` within 1 % across
  in-repo policies (single handoff: 25.8-25.9 GiB).
- **External C/R:** descriptive only (no pass threshold), in the external-system group of section 5 (C/R as designed,
  OTTER cold destination, C/R lower bound where applicable): TTFO, dump / transfer / restore times, bytes, rejoin;
  failures go to the compatibility table. No primary-claim speedup is computed against external systems.
- **Run validity:** all fragments verified; digest match; NIC peaks <= 1.15 x cap; paced egress <= 1.05 x cap over 10 s;
  four distinct hosts on one commit; GPU 0 idle before the run; reference available; no version events (section 2).
  Invalid runs are listed and re-run, never dropped.

## 8. Implementation required before any run (not started)

1. Move the restoration planners (`reuse_aware_in`, `reuse_dyn`, pre-positioning) out of `restore_orchestrate.py`
   into a module shared with `mobility_orchestrate.py`; regression-check it against the network-level pilots.
2. GPU harness: cap events, measured-throughput re-planning hooks, revisit paths, placement window before a move,
   the "OTTER at moves" policy.
3. Full migration and cold restart as repeated-mobility execution policies.
4. t_decode logging per frame (t_chunk exists); a consumer process for t_deliver only if delivery metrics are kept.
5. Hybrid scenario E: `restore_node.py` sessions alongside the GPU nodes (separate ports), shared token buckets at A.
6. Metrics: pre-move vs post-move source bytes, verified-progress-reused, rejoin calls, version-event counters.
7. OTTER cold-destination variant (process start + weight load after the trigger) for scenario A.
8. Copy every node's `fragments.csv` back to the run directory.
9. External C/R per the audit, after a two-host restore test on driver 575.51.03.

Each item gets a loopback / single-host test and a one-run-per-policy shakedown (inspected) before the sweep.

## 9. Runs and cost

| scenario | runs (3 reps) |
|---|---|
| A | (4 in-repo + OTTER cold-destination) x 2 bandwidths = 10 x 3 = 30; external C/R 2 systems x 2 comparisons x 2 bandwidths = 8 x 3 = 24 |
| B | 6 x 2 rho = 12 x 3 = 36 |
| C, D | 4 x 2 = 8 x 3 = 24 |
| E | 3 x 3 = 9 |
| F | 4 x 3 = 12 |
| G | 4 x 3 = 12 |
| generalization (scenario A only; 2 clips x 2 seeds; OTTER event-driven and Full migration; 1 Gbps) | 8 x 3 = 24 |
| G9 steady state | 2 x 3 = 6 |
Total ~177 GPU runs at 2-3 min each after a ~3 min node start: ~8-10 h of exclusive use of four GPU 0s, plus external
baseline setup.

## 10. Risks

- Other users on GPU 1 of every host: never touch it; GPU 0 idle check per run.
- Scenario E is hybrid; any description as four GPU sessions is wrong.
- Event-driven re-planning competes for CPU with generation on the same host; G9 bounds steady-state cost only.
- External C/R cross-node restore may fail on driver 575.51.03; reported as a result.
- t_decode logging adds synchronization points; G9 must be measured with it enabled.

## Errata (dated; appended after the freeze; no criterion, metric or comparison changed)

- 2026-10-16 (D0 hardware audit): section 2 and scope condition 4 say "driver 575.51.03 on all four". Measured: driver 575.51.03 on elves-01 and elves-02 but **575.57.08 on elves-03 and elves-04**; elves-02 shows one L40S, the others two (D0 hardware audit, `results/evaluation/osdi/d0/hw_audit/`). The earlier statement "575.51.03 on all four" (user report, commit f3ad3ca) was wrong.
  Consequences: (a) external C/R pairs must be same-driver host pairs (elves-01/02 or elves-03/04) or the driver
  difference is stated with the result; (b) CRIU and cuda-checkpoint are not installed on any host and the account has
  no sudo and no capabilities, so external C/R needs the administrators (`osdi/d0/cr_readiness/`); (c) GPU-level
  results continue to report per-node service times, which absorb any driver difference.
- 2026-10-16: section 6's per-frame decode interval is degenerate by construction (one VAE call decodes every frame of a
  chunk); the descriptive metric is reported per chunk (`osdi/d0/shared_planner.md`).
