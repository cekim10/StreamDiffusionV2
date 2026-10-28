# E5: replay-aware Sink synchronization, first validation (plan fixed before the run, 2026-10-28)

Approved 2026-10-28 on the evidence of E4 (`e4_record.md`). The change goes into the M1 log-only replay protocol
(`precopy_replay`) behind `--replay_sink_sync`. One end-to-end migration under E3's conditions. No M2, M3 or larger
matrix.

## 1. Mechanism (E4's proposal)

1. **Sink base.** Round 1 sends the exact Sink and the ring metadata of the base boundary c0, unchanged from E3.
2. **Deterministic changes.** The shadow replay reproduces them: realignments (RoPE re-rotation) and positions.
3. **Refresh patches.** When a source call refreshes a Sink entry (a write into a Sink slot), that call's log entry also
   carries the exact K / V of every refreshed (layer, row, slot) entry, 9.58 MB each.
4. **Patch timing.** The destination applies each patch right after replaying its call and before the next call. It
   checks that the slot holds that call's frame position, which means the replay wrote it.
5. **Digest at cutover.**
   - The source does not resend the dirty Sink. The switch message carries a digest of the source's Sink at M: per
     (layer, K / V, row, slot) an int64 checksum with fixed pseudo-random weights in wrapping integer arithmetic,
     identical on every host, plus the Sink positions.
   - The destination computes the same over its shadow Sink and replies SINKOK or SINKNO.
6. **Match.** The destination keeps the shadow Sink. The replayed recent slots and the Sink survive the fast restore.
   There is no bind and no fragment resend; refresh resumes. Then DR-2 and the resume.
7. **Mismatch.** The destination records the mismatching blocks and the source resends the dirty Sink fragments (E3's
   path). The destination verifies them against the source's digest, binds them and resumes. An approximate Sink is
   never accepted.

All E3 checks stay, and the patches are added to the order check: patches sent equals patches applied, and every patch
is in its written slot.

## 2. Run

| item | setting |
|---|---|
| hosts and link | E3's: host A -> host B, 1 Gbps emulated |
| workload | dog seed 1, trigger call 30 |
| replay | Replay-12 (W = 12, lag 1); Sink rounds thr 16, rl 1 |
| other | horizon 100; frame dump on B; post-run recent-KV verification |
| runs | one, `precopy_replay` with `--replay_sink_sync` |
| comparisons | E3's `precopy_replay` and `precopy_sink` runs, reused, not rerun |

## 3. Reported

- Cross-host Sink digest equality: match / mismatch, the mismatching blocks, positions.
- Refresh patches: number, bytes, calls, slot check; patches sent = applied; order.
- Fallback triggered or not, and its bytes.
- Bytes at cutover, against E3's 730 MB.
- User-visible interruption and TTFO, against E3 replay (8.80 s) and M1 (8.05 s).
- P1 / P2 with `m1_live_metrics.py`: VD-3 frozen rules, dog_s1 OT-1 thresholds, window [M, M + 24).
- Source overhead (the digest, the patches, per-call time) and destination overhead (patch apply, digest).
- If the digests do not match: the mismatching blocks and their (layer, row, slot) histories, the category per E4
  (realign / refresh), and whether the fallback restored a verified Sink. The mismatch is reported as a protocol
  finding; the digest check is never bypassed.

## 4. Validation done before the run

- `test_m1_sinksync_cpu.py` runs the GPU runtime's own code on a tiny real CausalWanModel. It checks:
  - one patch per refresh;
  - every patch lands in its written slot;
  - metadata is equal on every call;
  - the replayed Sink checksum equals the source's;
  - a patch changed by 1 ulp changes the checksum.
- `test_m1_live.py` runs on dry nodes. It checks the E3 path, the digest-equal path (no Sink bytes at the switch) and a
  forced-mismatch path (fallback verified, then resume).
- `test_xb` passes.
