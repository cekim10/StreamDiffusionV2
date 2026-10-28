# E8 record: multiple realignments and a refresh-heavy workload (offline reuse probes, 2026-10-28)

**Sources and setup**
- Data: `e8_dog_s1.json` and `e8_bfly_s1.json`, run on host B at adbe9fe9 and recorded in d09392fd.
- Probe: E7's probe with per-entry statistics added. Each run is offline, in one process.
- Calls: c0 = 31, M1 = 64, interval 100 calls, M2 = 164. Both intervals contain two realignments, at calls 93 / 94
  and 138 / 139.
- In both runs B, built as E5's destination, has a Sink digest equal to A's at M1.

## 1. Exact reconstruction results (against B's exact Sink at M2: 360 blocks and the Sink digest)

| strategy | dog s1 | butterfly s1 |
|---|---|---|
| ordered (every event in call order) | digest equal, 360 / 360 | digest equal, 360 / 360 |
| **current values + shifts in their original order** | **digest equal, 360 / 360** | **digest equal, 360 / 360** |
| current values + one summed shift | not equal: 287 / 360 | not equal: 301 / 360 |
| last written value (no later shifts) | not equal: 359 / 360 | not equal: 344 / 360 |
| no shifts | not equal: 287 / 360 | not equal: 301 / 360 |

## 2. Do multiple realignments require ordered replay? Yes

The summed shift fails on exactly the unrefreshed entries that were shifted twice: 73 on dog, 59 on butterfly. Those
equal the `unrefreshed_entries_shifted_2plus` counts. One RoPE rotation by the summed delta is not bitwise equal to two
sequential rotations. Each entry's shifts must be applied in their original order.

Refreshed entries are unaffected: their current value already contains every shift after their last refresh. The
summed and no-shift strategies fail on the same blocks, so with two shifts per entry the sum is no closer to bitwise
than no shift at all.

## 3. Refresh events against distinct refreshed entries

| | dog s1 | butterfly s1 |
|---|---|---|
| refresh events in 100 calls | 3 | 130 |
| distinct refreshed entries (of 180) | 2 | 41 |
| repeated refreshes of an already-refreshed entry | 1 | 89 (up to 9 on one entry) |
| refreshes per entry | 1 x 1, 1 x 2 | 14 x 1, 8 x 2, 7 x 3, 3 x 4, 1 x 5, 1 x 6, 2 x 7, 3 x 8, 2 x 9 |
| shift events (entries shifted) | 150 (75; all twice) | 197 (100; 97 twice) |

## 4. Synchronization bytes and GPU time

| | dog s1 | butterfly s1 |
|---|---|---|
| latest K / V per refreshed entry | 19.17 MB | 392.97 MB |
| shift metadata + positions | 2.4 KB + 1.4 KB | 3.2 KB + 1.4 KB |
| **update total** | **19.17 MB (98.9 % less than the base)** | **392.97 MB (77.2 % less)** |
| every refresh event instead (ordered) | 28.75 MB | 1,246 MB |
| fresh Sink base | 1,725 MB | 1,725 MB |
| GPU reconstruction (current values, ordered shifts) | 15.4 ms | 13.6 ms |
| retained Sink host -> GPU | 77 ms | 76 ms |
| B's per-call tracking | 0.76 ms of 0.566 s | 0.70 ms of 0.564 s |
| transfer at 1 Gbps (estimate from bytes) | 0.15 s | 3.1 s (base: 13.8 s) |

Sending only the latest value per entry saves 69 % (butterfly) against sending every refresh event. Repeated refreshes
of the same entry are the reason.

## 5. Do the results support Versioned Sink State Reuse? Yes

Exact reuse held in both cases, with two realignments and on the refresh-heavy workload. It needs:
- the refreshed entries' current K / V;
- the ordered shift events of the unrefreshed entries;
- the positions.

**Update bytes** scale with distinct refreshed entries, not refresh events, and are bounded by the Sink: 180 entries =
1.73 GB.

**Ordered shifts are required.** The summed form is not bitwise.

## 6. Minimal M2 protocol for a first real A -> B -> A migration (proposal, not implemented)

The M1 protocol of E5 / E6 stays unchanged except for the base of the second migration.

1. **Retain at the first switch.** When A hands the session to B (SINKOK at M1), A keeps a host copy of its Sink at
   M1 as version V = (session, call M1, Sink digest): 1.73 GB, 0.17 s. B's Sink at M1 is digest-equal to V, which the
   switch already proves.
2. **Track on the new owner.** B records, since V:
   - a refreshed-since-V flag per (layer, row, slot) entry;
   - the shift events (call, layer, row, slot, delta) of the entries not refreshed since;
   - the positions it already keeps.
   This costs about 0.7 ms per call.
3. **Delta base at the second migration.** A advertises V (its digest) to B when the B -> A task starts. At its base
   boundary c0', B sends, instead of the full Sink round:
   - the current K / V of the refreshed entries;
   - the ordered shift list of the unrefreshed entries;
   - the metadata component;
   - its Sink digest at c0'.
4. **Rebuild on A.**
   - A loads V into the shadow ring (about 0.08 s) and checks that V's digest is the one B expects.
   - It then applies the shifts in order, overwrites the refreshed entries and takes the positions from the metadata.
   - It compares its Sink digest with B's at c0'.
   - If equal, the shadow base is ready (recent zero). If not equal, or V is missing or stale, A requests the existing
     full Sink round (fallback).
5. **From here on, unchanged M1:** the input log with refresh patches, shadow replay, the Sink digest at the cutover,
   and the dirty-fragment fallback.

**Changes needed for the first real run:**
- The orchestrator must allow a path that returns to A. `Run` currently asserts the path never returns to A.
- The replay policy must run twice in one session.
- Call-based switch points, so the reuse and fresh-base runs start from equivalent states (fixed M1 and M2).
- The node needs the retention, tracking, delta-base and rebuild steps above.

**First validation:**
- One A -> B -> A run on dog s1 with reuse, against one with the fresh base, from the same M1 and M2.
- Measure:
  - delta-base bytes and Sink-digest equality at the base and at the cutover;
  - readiness time;
  - interruption;
  - P1 / P2 at the second migration.

**Main risks to address in that run:**
- Version identity: the wrong session or a stale V. The digest check at the base guards it.
- Retained memory per session.
- On refresh-heavy inputs with long intervals the delta approaches the full base. A simple rule: send the full base
  when the delta exceeds it.
