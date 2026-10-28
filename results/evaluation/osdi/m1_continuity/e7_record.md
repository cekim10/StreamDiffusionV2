# E7 record: retained-Sink reuse across A -> B -> A (offline feasibility probe, 2026-10-28)

- **Source:** `e7_reuse_probe.json`, run on host B (L40S) at 2c31a598, recorded in 6d644c68. Plan: `e7_plan.md`.
- **Setup:** dog s1, base at c0 = 31, first migration at M1 = 64, B generating 60 calls to M2 = 124.
- **Scope:** an offline reconstruction in one process, not a migration protocol.
- **Values:** everything in sections 1-3 is measured. Section 4 is estimated and labelled as such.

## 1. Is exact reuse feasible? Yes

B was built exactly as E5's destination. Its Sink digest equals A's at M1.

**Interval M1 .. M2:**
- 2 refresh writes, at calls 78 and 82, on 2 distinct (layer, row, slot) entries;
- 1 realignment, at calls 93 / 94, shifting 75 Sink entries once each, including both refreshed entries;
- 77 of the 360 Sink blocks (layer, K / V, row, slot) differ from A's retained snapshot.

| reconstruction from the retained Sink | Sink digest | blocks equal | update bytes |
|---|---|---|---|
| ordered: every event in call order (shifts, then the refresh values as written) | **equal** | **360 / 360** | 19.17 MB |
| current_values: refreshed entries <- B's values at M2; other entries <- the recorded shifts | **equal** | **360 / 360** | 19.17 MB |
| summed_shift: as above, one shift by the sum of the deltas | equal | 360 / 360 | 19.17 MB |
| last_written: refreshed entries <- their last written value, without the shifts that followed | not equal | 358 / 360 (the K of both refreshed entries) | 19.17 MB |
| patches_only: no shifts | not equal | 287 / 360 (73 shifted K blocks) | 19.17 MB |

**What exact reconstruction needs, and what can be dropped:**
- **The refreshed entries' current K / V.** The value written at refresh time is not enough: a later realignment
  rotated it (last_written fails on exactly those blocks).
- **The realignment shifts** of the unrefreshed entries, applied deterministically: (layer, row, slot, delta) per event,
  a few bytes each. Without them 73 blocks are wrong.
- **The Sink positions at M2** (metadata).
- **Intermediate refresh values: not needed.** Only the current value of each refreshed entry is.
- **Intermediate shifts: not decided.** Every entry was shifted once in this interval, so summing the deltas is
  trivially exact here. Whether several realignments in a longer interval may be summed or must be applied in sequence
  is untested. RoPE re-rotation is not bitwise reversible (Task B), so the sequence should be kept until tested.

## 2. Network traffic and synchronization cost (measured bytes and GPU times)

| | fresh Sink base (M1 baseline) | reuse of the retained Sink |
|---|---|---|
| Sink bytes for the second migration | 1,725,236,640 B (1.73 GB) | 19,171,920 B (19.2 MB: 2 entries x 9.58 MB + about 2.6 KB of shifts and positions); **90x less** |
| bring the retained Sink to the GPU | - | 0.075 s (host -> GPU, 1.73 GB) |
| apply the update on the GPU | - | 0.007-0.008 s |
| B's per-call tracking (refreshed entries, shift deltas) | - | 0.76 ms per call against a 0.563 s call (0.13 %) |
| A's retention | - | 1.73 GB of host memory per retained session (copy at M1 took 0.17 s); alternatively the same on the GPU |

The update is bounded by the Sink itself. At most 180 entries can be refreshed (30 layers x 2 rows x 3 slots,
9.58 MB each = 1.73 GB), so reuse never sends more Sink bytes than a fresh base.

## 3. Correctness

- Two strategies reproduce B's Sink exactly, block for block and in digest: ordered and current values.
- The cheaper, current values, needs only the refreshed entries' current values, the shift events and the positions.
- The required order is "the retained Sink, then the shifts of the unrefreshed entries in event order, then overwrite
  the refreshed entries with their current values". Refresh values must not be applied before later shifts unless the
  shifts are replayed after them; that is the ordered strategy.
- No missing state was found for this interval: B's metadata already holds everything needed.

## 4. Estimated effect on the second migration (B -> A at 1 Gbps; estimates from E5's measured timeline)

| | fresh base (E5 protocol) | reuse |
|---|---|---|
| Sink preparation | about 13.8 s (1.73 GB at 1 Gbps; E5's log queue peaked at 15 s) | about 0.25 s (19.2 MB at 1 Gbps = 0.15 s, plus 0.08 s host -> GPU and apply) |
| destination readiness (trigger to switch decision) | about 22 s (E5 measured 22.4 s) | about 7 s: limited by the 12-call replay window (12 x 0.57 s) instead of the base transfer |
| total traffic for the second migration | about 1.76 GB | about 25-30 MB on this workload (update + about 12-13 log entries + patches) |
| user-visible interruption | about 1.56 s (E5) | unchanged: the cutover is the same |

The benefit is in preparation time and bytes, not in the interruption.

The savings shrink as refresh activity grows. butterfly refreshed 54 times in 34 calls in E6, so a long interval there
could approach the 1.73 GB bound. Each refreshed entry still costs only one 9.58 MB current value, however many times
it was refreshed.

## 5. Tradeoffs and open questions

- **Memory.** 1.73 GB per retained session, in host memory or on the GPU. Retaining for many sessions or hosts needs a
  retention policy. That is M2 design and not studied here.
- **Version identity.** A must know which version it holds (M1 here), and B must track changes since that version.
  The tracking costs 0.13 % per call. The existing digest check at the cutover remains the guard, with the fresh base
  as the fallback.
- **Intermediate shifts.** One realignment only in this interval. A longer interval should test whether several shifts
  may be summed.
- **Coverage.** One workload, one interval length, offline, in one process. Cross-host determinism of the shifts is the
  same assumption E5 / E6 verified for this host pair.

## 6. Does the evidence support developing M2?

**Yes.**
- Exact reuse of the retained Sink is feasible with small, already-available metadata: refreshed-entry current values,
  shift events and positions.
- It cut the Sink bytes 90x for a 60-call interval on dog s1, and its synchronization cost is milliseconds.
- The expected gain is in readiness time, about 22 s to about 7 s at 1 Gbps (estimate), and in traffic, not in the
  interruption.
- **Before an M2 protocol:** test a longer interval (several realignments) and a refresh-heavy workload such as
  butterfly. Those decide the multi-shift rule and the realistic savings.
