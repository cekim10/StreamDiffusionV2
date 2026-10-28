# M1 input-log replay, E3 record: first end-to-end validation (2026-10-28)

## Sources and scope

- **Runs:** `results/evaluation/expM1R/` (pushed 195a14bf).
- **Continuity metrics:** `e3_metrics.json`, computed on host B (merged from 83d85c2f).
- **Plan:** `e3_plan.md`, fixed before the run.
- **Setup:** host A to host B, 1 Gbps emulated link, dog seed 1, trigger at call 30, one run per method, same
  harness and transport.
- **Scope:** this is a functional validation, not a distribution.

## 1. Does the protocol work end to end? Yes

Every replay validation item holds:
- the base was verified and the prompt conditioning was equal;
- the log arrived in order with no gaps or duplicates;
- every replayed call's metadata digest equalled the source's (33 of 33);
- the shadow metadata equalled the source's at the switch;
- the source's last call was M - 1 and the destination's first call was M, with no lost, duplicated or reordered calls;
- the source's outputs equalled the reference on 34 of 34 calls (logging changes nothing);
- the switchover was verified, with no refused switch and no readiness timeout.

Replay covered calls 31 to 63 (33 calls) and the switch came at M = 64. Untimed after the run, the replayed recent
KV differed from the source's by 0.74 % (K) and 1.49 % (V) relative error. This is below E1's 12-call values because
33 calls were replayed.

The run was valid: GPU 0 was idle on both hosts, both ran the same commit, and only E2's own processes touched GPU 0.

## 2. Latency

| | replay (precopy_replay) | M1 (precopy_sink) | exact state (precopy_full) |
|---|---|---|---|
| switch call M | 64 | 56 | 278 |
| trigger to the destination's first output | 31.0 s | 24.9 s | 214.1 s |
| user-visible interruption (destination first output minus source last output) | 8.80 s | 8.05 s | 50.88 s |
| source stop to first output | 8.80 s | 8.05 s | 50.88 s |
| of which the source stops and sends the final components | 7.30 s | 7.09 s | 49.20 s |
| destination: verify / restore (incl. DR-2) / first call | 0.10 / 0.66 / 0.70 s | 0.09 / 0.12 / 0.69 s | 0.29 / 0.36 / 0.97 s |

- The source keeps serving until the switch decision, so "trigger to first output" is not user-visible. Only the
  interruption is.
- Replay adds 0.75 s to the interruption over M1. Of that, 0.52 s is the DR-2 decode. Waiting for the replay at the
  switch took 0.00002 s.

## 3. Network bytes

| | replay | M1 | exact state |
|---|---|---|---|
| before the switch | 1.728 GB Sink round + 13.2 MB log (33 calls, 0.40 MB each) | 1.725 GB Sink round | 17.40 GB (3 full-state rounds) |
| at the switch | 730 MB (final dirty Sink, in-flight, metadata, 0.4 MB DR-2 latents) | 726 MB | 5.45 GB |
| total | 2.47 GB | 2.45 GB | 22.9 GB |

The Recent KV (1.73 GB) is never transferred.

## 4. Replay synchronization overhead

- Replay costs 0.119 s per call (median), 3.99 s in total for 33 calls. The source's call interval is 0.566 s; it
  was 0.559 s in the M1 run without logging.
- Log entries queued up to 14.5 s at the destination while the Sink base was in flight (1.73 GB at 1 Gbps).
- After the base arrived, the replay caught up 33 calls in about 4 s. The switch decision waited 4.3 s for the
  replay to be within one call. The source served during that wait, so it is not user-visible.
- At the switch the replay was already caught up: wait 0.00002 s, log flush 0.000004 s.

## 5. Continuity

VD-3 frozen rules with dog_s1 OT-1 thresholds and REF P99 3.91. P2 is computed over [M, M + 24).

| | P1: V1 at M (REF at that call) | P2a | P2b | PSNR to REF at M..M+3 | first call >= 35 dB | PSNR, last 10 calls |
|---|---|---|---|---|---|---|
| replay | **pass**: 1.94 (1.03) | pass (D_c -0.0003, C_c 0.08) | fail (warp excess 0.28, frame-difference ratio 1.105) | 29.3, 26.6, 28.3, 28.5 | M + 7 | 49.1 |
| M1 | **fail**: 4.33 (0.83) | pass (D_c -0.0135, C_c 0.58) | fail (warp excess 1.06, ratio 1.32) | 18.2, 18.7, 17.6, 19.6 | M + 8 | 49.6 |
| exact state | identical to REF: all 101 destination calls bit-equal to the reference (PSNR 99) | identical | identical | 99 | - | 99 |

- Replay restores P1, the migration-boundary continuity, which M1 fails.
- Replay is about 10 dB closer to the reference over the first calls.
- Replay improves the P2b quantities sharply (warp excess 1.06 -> 0.28, frame-difference ratio 1.32 -> 1.105), but
  P2b still fails narrowly. This matches the oracle: on dog s1 OT-1, RS3 and every Replay-w also failed P2b in E2 and
  VD-5, the residual VD-5 placed outside the KV ring.
- **Deviation:** exact state's frame metrics were not computed. The frame dump stopped at call 230 (`--dump_calls 200`
  was left at its default) while that run switched at call 278. Its continuity is established instead by the per-call
  reference digests (101 / 101 bit-equal).

## 6. Synchronization bottleneck

The interruption is not set by replay. It is the final dirty Sink resend: 730 MB (42 % of the Sink) of fragments
changed between the round-1 snapshot (call 31) and the switch (call 64), sent at 1 Gbps in about 5.8 s of the 7.3 s
source-side switch. The M1 baseline pays the same cost (726 MB). The likely cause is the refreshes and t_refresh
realignments of the ~33 calls in between; Task B measured realign re-rotating 50-64 % of the Sink fragments over 50
calls. This run did not attribute the dirty set.

## 7. Remaining limitations

- **One run per method:** one workload, one bandwidth, host pair A -> B.
- **Replay-3 emergency mode** was not evaluated.
- **Not covered:** unpredicted moves and repeated moves.
- **The final Sink resend dominates the interruption.** The replay already reproduces realign rotations
  deterministically and knows each refresh decision, so the source could send only the exact refreshed Sink entries
  instead of the dirty fragments. This is not implemented or tested.
- **DR-2 is on the critical path:** 0.52 s.
- **The residual P2b gap on dog s1 OT-1** is outside the KV ring, as in the oracle experiments.
- **Source-side cost:** the source keeps one extra full-state snapshot per Sink round (existing pre-copy behaviour),
  and with `--replay_verify` it holds its state at the switch until the run ends (validation only).
