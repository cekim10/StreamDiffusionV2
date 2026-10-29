# E10: final M2 functional validation (plan fixed before the run, 2026-10-28)

**Scope.** The M1 / M2 implementation of E9, unchanged. The only additions:
- a counter of all refresh events in the owner's tracker (measurement only);
- three deterministic fault-injection test knobs.

No new optimization, retention policy or scheduling. One controlled run per configuration. Every value comes from the
real hosts. Estimates are labelled as such.

**Common settings, as E9** (`tools/eval/run_m2_e10.sh`):

| item | value |
|---|---|
| hosts and link | A -> B -> A on the same host pair, 1 Gbps |
| replay | Replay-12, lag 1; Sink rounds thr 16, rl 1; Sink synchronization on |
| switches | planned at calls 64 and 164; second trigger at call 120; first trigger at call 20 |
| horizon | 100 calls after the second switch |
| frame dumps | per node, after its own switchover |

## A. butterfly s1 end to end

- **baseline** (`--replay_retain`): both migrations use the fresh Sink base. The second migration has no destination
  version (no `--replay_reuse`), so its base is full. Retention and tracking are on only so that the refresh counts are
  recorded in this arm too. They do not change generation.
- **M2** (`--replay_retain --replay_reuse`): the second migration uses the delta base from A's retained Sink.
- **Equivalence:** B's outputs over calls 64 .. 163 must be identical call by call in the two runs.
- **Measured:**
  - refresh events against distinct refreshed entries (tracker, calls 64 .. base boundary);
  - delta-base bytes against fresh-base bytes;
  - total migration traffic;
  - trigger to base ready, and trigger to replay ready;
  - the interruption;
  - Sink equality at the base (DELTAOK with 360 / 360 blocks and positions) and at the cutover (SINKOK);
  - P1 / P2a / P2b at both migrations (VD-3 frozen rules, butterfly_s1 OT-1 thresholds);
  - retained memory and tracking overhead.
- **E8's offline estimate** (393 MB for 100 calls, 64 -> 164) is reported alongside. It is not expected to match: the
  live base boundary is near call 121, about 57 tracked calls.

## B. Real GPU delta-base fallback (dog s1, E9 configuration, `--replay_retain --replay_reuse --replay_test_fault X`)

| fault | injection | expected detection |
|---|---|---|
| advertise_wrong | A advertises a version whose digest is not the one it holds | B's version check: no delta is sent and the base is full |
| held_wrong | A advertises its true version, but the record it holds differs (stale or replaced retention) | A's version check: DELTANO, then the full base |
| corrupt_block | one bit of one retained Sink K block that the delta does not overwrite is flipped before reconstruction | A's Sink digest names exactly that block: DELTANO, then the full base |

**Required in every fault run:**
- the mismatch is detected as above;
- the full Sink base follows and passes its component digest on A;
- the existing M1 cutover check stays active and gives SINKOK at 164;
- the migration completes, with A generating after 164;
- P1 / P2 at the second migration equal E9's fresh-base baseline. Same workload and switch points, and an exact base,
  so the outputs should be identical.

**Measured:** fallback bytes (the rejected delta plus the full base), the additional latency (trigger to base ready
and to replay ready, against E9's baseline and M2), and the interruption.

## Freeze recommendation

M1 / M2 are recommended for freezing only if:
- every butterfly and fault check above holds;
- no correctness failure remains unexplained.

A failure is diagnosed and its root cause fixed before any rerun.
