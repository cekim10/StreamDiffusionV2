# M1 input-log replay, E3: first end-to-end validation of the protocol (plan fixed before the run, 2026-10-28)

Approved 2026-10-28: integrate log-only input replay into the M1 migration path and validate one predicted migration
between two hosts. Default window Replay-12. Replay-3 (emergency mode) is not optimized or evaluated. No M2, M3,
repeated migration or multi-tenant runs.

## 1. Protocol (implemented as the XB pre-copy policy `precopy_replay`)

Everything runs on the existing node / orchestrator transport (MSS-capped TCP data connections, per-task token-bucket
rate, chunk-boundary switchover). The policy is `precopy_sink` with replay added.

1. **Trigger at call T.** The source keeps generating and serving.
2. **Sink pre-copy.** Round 1 runs at the next boundary c0 with the same settings as `precopy_sink` (frozen XB
   calibration: thr = 16 MiB, rl = 1). It sends the Sink fragments plus the ring metadata of that boundary
   (positions, end indices, eviction queues). A PROUND marker carries the component digests and the prompt-conditioning
   digest.
3. **Input log.** Logging is armed before the round-1 snapshot. From call c0 on, every source generator call is
   recorded read-only and shipped in call order on the same connection, as one entry per call:
   - the inputs of both Stream-Batch rows, exactly as fed;
   - the timesteps;
   - the row starts and ends;
   - the refresh decisions;
   - the digest of the ring metadata after the call.
4. **Shadow replay.** The destination verifies the base, builds the shadow ring (Sink and metadata of c0, recent slots
   zero), then applies the entries strictly in order with forced decisions. It checks the metadata digest after every
   call and acknowledges each call to the source.
5. **Switch.** The switch happens only when the replay has applied at least W = 12 calls and is within lag = 1 call of
   the source. The source then stops at the next boundary M, waits until the log through M - 1 is on the wire, and sends:
   - the final dirty Sink fragments;
   - the existing fast path (in-flight rows and metadata);
   - the last two decoder latents (DR-2).
6. **Cutover at the destination.**
   1. Wait until the replay has applied M - 1, and check the order: base call, no gaps or duplicates, every
      post-call digest equal.
   2. Check that the shadow metadata equals the source's final metadata.
   3. Run the M1 fast restore, keeping the replayed recent slots.
   4. Bind the exact Sink, then run DR-2, then resume at M.
   - If any check fails, the destination does not resume. The run is then invalid.
7. **Post-run check, untimed.** After generation stops, the source sends its recent KV at M and the destination compares
   it with the replayed recent KV.

## 2. Run (one migration per method; host A -> host B; existing XB1 setting)

| item | value |
|---|---|
| workload | dog, seed 1 (unit dog_s1; frozen VD-3 thresholds dog_s1, OT-1) |
| link | 1 Gbps emulated (per-task token bucket), MSS cap as in XB |
| trigger | call 30 |
| horizon | 100 calls after the switchover; reference window 1500 calls (as XB, for the long precopy_full rounds) |
| methods | `precopy_replay` (W 12, lag 1, Sink rounds thr 16, rl 1); `precopy_sink` (M1 baseline for a predicted move: Sink pre-copied, zero recent, fast path); `precopy_full` (exact-state migration: Llumnix-style rounds of every component; frozen thr 256, rl 10) |
| reps | 1 each |
| frames | the destination dumps its output frames and the reference frames from 16 calls before its first output to its last call (host-local, never committed) |

## 3. What is measured and reported

- **Works end to end** if every replay validation flag is true:
  - base verified, conditioning equal;
  - order (no lost, duplicated or reordered calls; source's last call M - 1, destination's first call M);
  - every post-call digest equal, metadata consistent at the switch;
  - no refused switch, no readiness timeout;
  - the source's outputs equal the reference call by call;
  - the switchover verified.
- **Latency per method:**
  - trigger to the destination's first output;
  - interruption (destination first output minus source last output);
  - switch decision to first output;
  - source stop to first output.
  - For replay, the readiness wait, the log flush, the replay wait at the switch, the restore and DR-2 are also broken
    out.
- **Network bytes per method:**
  - Sink rounds;
  - the log (per call and total);
  - the final switch bytes;
  - DR-2.
- **Replay overhead:**
  - replay time per call and in total;
  - the destination's queueing;
  - the source's per-call service time while logging, against before the trigger.
- **Continuity:** P1 (V1 at M against REF P99) and P2a / P2b over [M, M + 24) with VD-3's frozen rules
  (`tools/eval/m1_live_metrics.py`, on host B). Also reported: the post-run recent-KV error of the replay.
- **Synchronization bottleneck:** if the replay cannot catch up before the switch, the readiness wait or timeout and
  the replay wait at the switch are reported as they are. The switch is never forced onto an unreplayed state.

One run per method is a functional validation, not a distribution. Bandwidth, workload and repetition sweeps are out
of scope.
