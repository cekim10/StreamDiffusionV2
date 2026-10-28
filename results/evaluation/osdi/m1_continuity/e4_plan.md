# E4: attribution of the E3 final dirty Sink (plan fixed before the run, 2026-10-28)

**Question.** How much of the ~730 MB Sink resend at the E3 switchover could the destination reproduce through the
deterministic transformations its shadow replay already performs?

This is analysis only. It runs one deterministic reproduction on one GPU host. No protocol change, no new run of
E3, no M2 or M3.

## Method

`tools/eval/m1_sink_dirty.py` reproduces the E3 replay run's source in one process:
- dog seed 1, the E3 node's arguments;
- base boundary c0 = 31 and switch M = 64, both from E3's summary;
- 4 MiB fragments of the exact `pack_component("sink")` serialization.

It records every call's cache decisions in [c0, M) and classifies every changed (layer, row, slot) K or V block:

| category | definition |
|---|---|
| refresh | the entry received newly generated K / V in the window. It counts here whether or not it was realigned later. |
| realign_only | not refreshed; only K changed, and the source's sequence of RoPE shifts applied to the c0 value reproduces the M value bitwise |
| other | everything else that changed |
| position | the int64 Sink position table inside the serialization (metadata) |

**Fragment counting.** Each dirty fragment is counted once, under the highest-priority category among the ranges it
overlaps, in the order refresh > other > realign_only > position. This avoids double-counting overlaps, such as a
fragment that holds a refreshed block and a realigned block, or an entry refreshed and then realigned.

**Reconciliation.** The reproduced dirty fragment bytes must equal E3's final bytes minus the DR-2 latents, the
in-flight component and the metadata component. If they do not, the reproduction is not E3's and the attribution is
reported as unreconciled.

**Can the destination reproduce it?** The same process runs E3's log-only replay: the ring at c0 with the recent slots
zeroed, calls c0 .. M-1, decisions forced. Per category it counts the blocks where the destination's Sink equals the
source's bitwise, plus the maximum relative error.

## Reported

- Fragments and bytes per category, at fragment granularity (what E3 sends).
- Changed block bytes per category, at (layer, row, slot) granularity.
- Refresh events by call.
- Reproduction by replay.

**Estimated minimum remaining transfer:**
- (a) the fragments in refresh and other;
- (b) the block bytes of refresh and other, sent as exact entries;
- (c) with per-call exact patches during the shadow, only the entries refreshed by the last call remain at the switch.

The proposed optimization is reported only if the evidence supports it.
