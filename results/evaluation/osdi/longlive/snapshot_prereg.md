# LongLive migration feasibility: exact window snapshot + catch-up replay (DRAFT 1, not frozen, nothing run)

## 1. Question

The state-component ablation (`ablation_prereg.md`, Phase 1, 3 / 4 streams so far, measured) found that LongLive's
generation loop depends on the sink and the window K / V only: with both exact the latents are bit-exact on 100 / 100
calls with any VAE cache; the VAE decoder cache feeds nothing back and is rebuilt from the last 12 logged blocks (first
call 80 dB, bit-exact from the second); an approximate window (sink + W12 replay) drifts to 22-31 dB. The candidate
that follows is OTTER's continuity principle with a different exact part:

**Ship one exact snapshot of the sink and window K / V while the source keeps serving, then catch the destination up
by exact teacher-forced replay of the calls made meanwhile; rebuild the VAE decoder from the latent log.**

This study tests whether that works live between two hosts at 1 Gbps. It does not test repeated mobility, staging,
versioned deltas or other bandwidths, and it does not by itself support a claim that OTTER supports LongLive.

## 2. Facts and expectations

- Measured (gate0, gate1, ablation): state sink 0.86 GB, window 2.59 GB, cross-attention 0.09 GB, VAE cache 1.89 GB,
  latent buffer 2.4 MB; a live call 2.11 s (generate 1.37 + decode 0.75); replay from an exact state is bit-exact
  (gate1 replay_all) at about 1.0 s per call with decode; the context pass alone is part of the 1.37 s generate.
- Snapshot shipped: sink + window + counters = 3.22 GiB (+ the last 12 pre-trigger latents, 7 MB); Full ships 5.06 GiB.
- Replay log: one output-latent block per call (0.6 MB; 2.3 Mbps at 2.11 s per call).
- [H] readiness. snap: export about 1 s + transfer about 28 s, during which the source makes about 13 calls; replay
  of those without decode (a few s), then the VAE rebuild (K_v = 12: about 9 s; K_v = 1: under 1 s) while the source
  still serves, then the calls made meanwhile with decode (about 1.0 s per call vs 2.11 s live), then the switch:
  K_v = 12 about 45-52 s, K_v = 1 about 35-42 s. Full: export + 43.5 s transfer + import about 46-48 s. So F4 is
  uncertain for K_v = 12 and expected for K_v = 1.
- [H] delivery gap. snap: the source's call in flight when the switch request arrives + the last replayed call + the
  first destination call, about 2.5-4 s against a 2.11 s call interval; Full about 48 s.
- [H] frames. K_v = 12: bit-exact from the first or second destination call; K_v = 1: complete but not bit-exact for
  a number of calls (ablation Phase 2 winX_vae1 measures this; not used to choose K_v).

## 3. Runs

`python tools/longlive/ll_migrate_runs.py run` on elves-01 (agents; no ssh): two lanes in parallel, A > B (elves-01 to
elves-02) and C > D (elves-03 to elves-04); each job starts the destination, then the source. Streams: the ablation's
prompts 0, 1 x seeds 0, 1; trigger call M = 120; 20 post-cutover calls verified against the source's shadow; 1 Gbps
application-level shaping on the source -> destination link (tools/eval/common Throttle, as every harness experiment).

| arm | what moves | VAE decoder |
|---|---|---|
| snap_k12 | snapshot (sink, window, counters) at M while the source serves; then the replay log | rebuilt from the last 12 logged blocks once the replay has caught up, before the switch |
| snap_k1 | same | rebuilt from the last logged block |
| full | stop-and-copy of the whole state at M (sink, window, cross-attention, VAE cache, latent buffer) | shipped |

Arms are interleaved (rep, stream, arm order); reps 2 (D1) = 4 x 3 x 2 = 24 jobs, about 8 min each with model loading,
about 1.6 h on the two lanes. A snap run that has not caught up `max_catchup_s` = 300 s after the snapshot arrived is
switched anyway and recorded as forced.

**Protocol (snap).** The source exports the snapshot before call M (one device -> host copy; its stall is measured),
queues it, then the 12 pre-trigger latents, then one LOG per call it serves. The destination imports the snapshot
(cross-attention recomputed from the prompt), replays the log context-only until its backlog is <= 1 call, rebuilds
the VAE decoder from the last K_v logged blocks, replays the calls made meanwhile with decode, and sends SWITCH when
caught up again; the source stops after its call in flight, sends its last LOG, STOP (switch call s) and its state
fingerprint at s, then runs 20 shadow calls (never served) and sends their latent and frame digests and the first
call's frames. The destination replays to s and generates calls s..s+19.

## 4. Metrics (destination clock; source times converted with a 9-ping offset estimate)

- **Exactness:** state fingerprint at s (per sink / window tensor: integer sums of the 16-bit patterns and of their
  squares, a strided sample digest) source vs destination; post-cutover latent digests equal the shadow (20 calls);
  frame digests equal (count); first destination call's PSNR vs the shadow's frames.
- **Completeness:** frames per post-cutover call = 12.
- **Readiness:** trigger -> the destination's state at s complete (before it generates call s). TTFO: trigger -> its
  first frame. **Delivery gap:** the source's last served frame -> the destination's first frame (reported with the
  source's call interval). Catch-up: switch request time, replayed calls, VAE rebuild time, forced or not.
- **Source impact:** export stall; source call interval in the 20 calls before M vs while the snapshot is sent.
- **Bytes** sent on the link.

## 5. Rules (written before the runs)

For each snap arm separately (snap_k12, snap_k1):
- **F1 replay exact:** in every run, the state fingerprint at s equals the source's and 20 / 20 post-cutover latents
  equal the shadow.
- **F2 catch-up:** in every run, the destination catches up (no forced switch).
- **F3 cutover correctness:** in every run, frames complete (12 per call, 20 calls) and F1's state equality.
- **F4 readiness:** median readiness < Full's median readiness (same stream, same harness, measured) in >= 3 of 4
  streams.

**Reading (as written):**
- F1-F4 hold for an arm: LongLive keeps service continuity during an exact state reconstruction with shorter readiness
  than Full, in this setting (one move, 1 Gbps, two host pairs) - the second-model case for OTTER's continuity
  principle, to be extended to E10 (repeated mobility, bandwidths) before any paper claim.
- F1-F3 hold, F4 fails: exact continuity (gap) without a readiness gain over Full; reported as such.
- F1 or F3 fails: a runtime / protocol defect first (fix, rerun, keep both records); if it persists, the exact window
  snapshot does not carry over and the cost of the exact window limits OTTER's applicability.
- F2 fails: replay does not outpace generation in this setting; the run is still read for F1 / F3.

Never claimed from this study alone: OTTER supports LongLive; generality across models; equivalent correctness of
any method with Full beyond these runs.

## 6. Open decisions

| # | decision | recommendation |
|---|---|---|
| D1 | reps | 2 (4 streams x 3 arms x 2 = 24 runs; timing spread is small in gate1) |
| D2 | arms | snap_k12 (exact output), snap_k1 (fast), full; K_v fixed now, never chosen from the results |
| D3 | bandwidth | 1 Gbps only here; 10 Gbps later in E10 (snapshot 2.8 s, replay overheads dominate) |
| D4 | lanes | A > B and C > D in parallel (independent pairs; gate1 cross-host determinism) |
| D5 | thresholds | F2 max_catchup 300 s; F4 >= 3 / 4 streams on medians |
| D6 | order | after the ablation's Phase 2 (both use GPU 0 on every host) |

Tools: `tools/longlive/ll_migrate.py` (src / dst), `ll_migrate_runs.py` (run, report). Loopback CPU test
`tools/longlive/test_ll_migrate.py` (tiny model on 127.0.0.1: both methods, a fast and a slow link; state exact,
post-cutover latents 4 / 4 and frames 4 / 4 equal the shadow, frames complete, shaping applied, VAE rebuilt before the
switch): ALL PASS. On the CPU tiny model decode-replay is about as fast as generation, so its snap runs switch by the
max_catchup safeguard (an earlier build without the safeguard caught up naturally at a slow link); GPU timings differ
(gate1: replay with decode about 1.0 s vs 2.11 s live).
