# E5 record: replay-aware Sink synchronization, first validation (2026-10-28)

## Sources

- **Run:** `results/evaluation/expM1S/` (pushed b27d729c), at 7712a994.
- **Continuity metrics:** `e5_metrics.json`, computed on host B (merged from 9b4936a5).
- **Plan:** `e5_plan.md`.
- **Conditions:** as E3: host A to host B, 1 Gbps, dog seed 1, trigger at call 30, Replay-12. The comparisons are E3's
  `precopy_replay` and `precopy_sink` runs. One run, so this is a functional validation, not a distribution.

## 1. Correctness

| check | result |
|---|---|
| cross-host Sink digest | **equal**: 0 of 180 (layer, K / V, row, slot) blocks differ; Sink positions equal |
| fallback | not triggered (verdict SINKOK) |
| refresh patches | 2 (calls 34 and 60, 1 entry each, 19.2 MB); both landed in the slot the replayed call wrote; patches sent = applied = 2 |
| order | 33 / 33 calls replayed in order, every post-call metadata digest equal, no lost / duplicated / reordered calls (source last 63, destination first 64) |
| metadata at the switch | consistent |
| source unaffected | its outputs equal the reference on 34 / 34 calls |
| post-run recent-KV error | 0.53 % (K) / 1.18 % (V); E3: 0.74 % / 1.49 %. The replay now runs against an exact Sink. |

**Validity:** GPU 0 was idle on both hosts and both ran the same commit.

## 2. Latency and bytes

| | E5 replay + Sink sync | E3 replay | E3 M1 (`precopy_sink`) |
|---|---|---|---|
| user-visible interruption | **1.56 s** | 8.80 s | 8.05 s |
| source stop to first output | 1.55 s | 8.80 s | 8.05 s |
| trigger to the destination's first output | 23.65 s | 30.97 s | 24.94 s |
| bytes at the switch | **3.2 MB** (in-flight 0.4, metadata 2.4, DR-2 0.4) | 730 MB | 726 MB |
| bytes before the switch | 1.728 GB Sink base + 32.3 MB log (13.2 MB inputs + 19.2 MB patches) | 1.728 GB + 13.2 MB | 1.725 GB |
| total | 1.76 GB | 2.47 GB | 2.45 GB |

**Where the 1.56 s goes:**
- Waiting for the chunk boundary (0.44 s) comes before the stop, so it is not part of the interruption.
- Inside the interruption:
  - source Sink digest 0.065 s;
  - destination digest 0.064 s and verdict round trip (0.107 s seen by the source);
  - restore 0.66 s, of which DR-2 is 0.52 s;
  - first destination call 0.74 s.
- DR-2 and the first call are now most of the interruption.

## 3. Overhead

**Source:**
- Per-call service time is 0.566 s (median), as in E3 with logging (0.566 s) and the M1 run (0.559 s).
- The patches add one device-to-host copy of 9.58 MB per refreshed entry, on 2 calls.
- The Sink digest at the switch takes 0.065 s.

**Destination:**
- Replay costs 0.120 s per call, as in E3.
- Patch application is a device copy right after its call.
- The digest takes 0.064 s.
- Log entries queued for up to 15 s while the Sink base was in flight, as in E3.

**Network:** the shadow window carries 19.2 MB of patches on top of the 13.2 MB of inputs.

## 4. Continuity (VD-3 frozen rules, dog_s1 OT-1 thresholds, REF P99 3.91, window [M, M + 24))

| | P1: V1 at M | P2a | P2b |
|---|---|---|---|
| E5 | pass, 1.936 | pass (D_c -0.0003, C_c 0.085) | fail (warp excess 0.281, frame-difference ratio 1.105) |
| E3 replay | pass, 1.938 | pass | fail (0.280, 1.105) |
| E3 M1 | fail, 4.33 | pass | fail (1.06, 1.32) |

Synchronizing the Sink this way loses no continuity: E5 equals E3's replay to the third decimal. The P2b gap is the
residual on dog s1 OT-1 that the oracle experiments also showed (outside the KV ring).

## 5. Remaining correctness risks

- **The digest is a checksum, not a cryptographic hash.** It is an int64 weighted sum per block with fixed
  pseudo-random weights. A random difference goes unnoticed with probability about 2^-64 per block. A
  adversarially structured difference could cancel, which is not a concern for numerical drift.
- **Cross-host determinism was shown for this host pair only.** Same GPU model and software stack, one run. A different
  GPU type, driver or kernel selection could break bitwise reproduction of the realignment. The digest then catches
  it, and the run falls back to E3's resend and E3's interruption.
- **The GPU fallback path is not exercised.** It is tested only on dry nodes (forced mismatch). Its latency on GPU
  would be E3's (about 8.8 s at 1 Gbps) plus one verdict round trip.
- **Workload coverage.** One workload with 2 refreshes in 33 calls. E4's "other" category was empty here. A workload
  with other kinds of Sink change would be caught by the digest and fall back. Refresh-heavy inputs raise the patch
  bandwidth during the shadow, not the cutover.
- **What the protocol trusts.** It assumes nothing modifies the destination's shadow ring outside the replay and the
  patches. The order checks and the digest guard this at the switch only.
