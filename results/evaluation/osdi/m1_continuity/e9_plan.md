# E9: first end-to-end M2 (Versioned Sink State Reuse), A -> B -> A (plan fixed before the run, 2026-10-28)

Approved 2026-10-28 on E7 / E8. The M1 protocol (log-only replay, refresh patches, Sink digest at the cutover with the
dirty-fragment fallback) is unchanged. M2 changes only the base of a migration toward a host that holds a retained
version.

## 1. Protocol (precopy_replay with --replay_retain --replay_reuse)

1. **Retain.** At a cutover the destination confirms with SINKOK. The source then keeps a host copy of its Sink at M
   (the exact serialization the pre-copy uses). Its version is (session, call M, SHA-256 of the Sink digest it sent).
   This is the Sink version verified at that cutover.
2. **Track.** The new owner computes the same version from its own, digest-equal Sink and tracks from then on:
   - the entries refreshed since the version;
   - the ordered shifts (call, layer, row, slot, delta) of the entries not refreshed since.
   A refresh discards the entry's earlier shifts. Later shifts of a refreshed entry are not needed, because its current
   value contains them. A copy of the tracker is taken at the same boundary as the base snapshot.
3. **Delta base.** At the next migration the destination's retained version is advertised (RETAINED_VERSION). If it
   equals the tracked version, round 1 sends:
   - the metadata component;
   - the current exact K / V of the distinct refreshed entries;
   - the ordered shift list;
   - the source's Sink digest at the base boundary.
   No intermediate refresh values are sent. Otherwise, or if the delta would not be smaller, the full Sink base is
   sent, as in M1.
4. **Reconstruct and verify.** The destination:
   1. loads its retained Sink;
   2. restores the metadata;
   3. applies the shifts in order;
   4. overwrites the refreshed entries;
   5. compares its Sink digest (360 blocks + positions) with the source's.
   - Equal: DELTAOK, and the shadow base is ready.
   - Not equal, or no / another version: DELTANO, and the source sends the full Sink base (fallback).
5. **The rest is M1:** the input log with refresh patches, shadow replay, the Sink digest at the cutover, and the
   dirty-fragment fallback.

## 2. Run (`tools/eval/run_m2_e9.sh`)

| item | value |
|---|---|
| workload | dog s1, the E5 / E6 node arguments |
| path and link | A -> B -> A (`--path A,B,A --allow_return`), 1 Gbps |
| replay | Replay-12, lag 1; Sink rounds thr 16, rl 1 |
| switches | planned at calls 64 and 164: the source stops exactly at that boundary once the destination is ready, and a late switch is recorded as missed |
| triggers | call 20 for the first migration (the trigger leaves room for the ~14 s Sink base at 1 Gbps), call 120 for the second |
| horizon | 100 calls after the second switch |

| run | first migration (A -> B) | second migration (B -> A) |
|---|---|---|
| baseline | M1, fresh base | M1, fresh base |
| M2 | M1, plus retain on A and track on B | delta base from A's retained Sink |

- **Equivalence of the two runs:** the same first migration and the same switch calls. B's outputs over calls 64..163
  are compared call by call (PSNR to the reference).
- **Frame dumps:** each node dumps its outputs after its own switchover plus reference frames, kept on the hosts.
  Continuity of the second migration uses B's actual outputs before 164 and A's from 164 on.

## 3. Reported (`tools/eval/m2_report.py`, `m1_live_metrics.py`)

For each migration of each run:
- the base mode and bytes, plus the delta's entries, shifts, value bytes and verdict;
- the reconstruction digest equality, mismatching blocks and timings (retained host -> GPU, rebuild, digest);
- Sink-round, log, patch and final bytes, and the total;
- readiness: the task start to the base being ready and to the replay being ready;
- the cutover verdict and digest equality, and the fallbacks;
- the interruption;
- restore and DR-2;
- retention (bytes, time) and tracking (calls, time);
- P1 / P2 with VD-3's frozen rules and the dog_s1 OT-1 thresholds.

Also reported: whether the first migration is unaffected (baseline against M2: timings, bytes, continuity), and the
equivalence check.

**If the protocol fails,** the first correctness mismatch is diagnosed before anything else is changed.
