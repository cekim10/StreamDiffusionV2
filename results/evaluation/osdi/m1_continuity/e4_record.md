# E4 record: why ~727 MB of the Sink is dirty at the E3 switchover (2026-10-28)

**Source.** `e4_sink_dirty.json`: run on host B at 854a3b7e, recorded in 2889db28. Rules in `e4_plan.md`.

**Reconciliation: exact.** The deterministic reproduction gives 174 dirty fragments, 726,992,288 B. That equals E3's
final switch bytes (730,191,056) minus the DR-2 latents (399,360), the in-flight component (399,360) and the metadata
component (2,400,048). No dirty fragment is unexplained. The window is c0 = 31 to M = 64: 33 calls, 412 fragments of
4 MiB, Sink 1.725 GB.

## 1. Dirty Sink breakdown (fragment level; each fragment counted once)

| category | fragments | bytes | reproduced by the existing replay | exact source values needed |
|---|---|---|---|---|
| realign only | 142 | 595.6 MB (81.9 %) | yes: 72 / 72 blocks bitwise | no |
| position table only | 24 | 97.8 MB (13.5 %) | yes: Sink positions equal at M; metadata digest equal on every call | no |
| refresh | 8 | 33.6 MB (4.6 %) | no: 2 / 4 blocks bitwise, max relative error 5.8 % | yes |
| other | 0 | 0 | - | - |
| **total** | **174** | **727.0 MB** | | |

At block level, (layer, row, slot) K or V, 4.79 MB each:
- realign only: 72 blocks, 345.0 MB;
- refresh: 4 blocks, 19.2 MB. This is the K and V of 2 entries.
- 284 blocks were unchanged.

**Events in the window:**
- 2 refreshes, at calls 34 and 60, one (layer, row, slot) entry each. One of the refreshed K blocks was realigned
  afterwards. It is counted under refresh, not twice.
- 1 realignment pair, at calls 48 and 49 (one call per Stream-Batch row; the t_refresh rewind).

**Granularity amplifies the bytes.** Only 98.8 MB of bytes actually differ. They lie inside 364.2 MB of changed blocks,
and 4 MiB fragments that do not align with the blocks inflate this to 727 MB. The position table (48 B per layer)
alone makes 24 otherwise-clean fragments dirty, 97.8 MB.

## 2. Estimated minimum remaining transfer at the switch

| scheme | Sink bytes at the switch | at 1 Gbps |
|---|---|---|
| E3 (dirty fragments) | 727.0 MB | 5.82 s |
| (a) only fragments containing a refresh | 33.6 MB | 0.27 s |
| (b) only refreshed entries, exact K / V | 19.2 MB | 0.15 s |
| (c) refreshed entries shipped with the log right after their call | 0 MB in this run (last refresh at call 60 < M - 1) | 0 s |

The in-flight component, the metadata and the DR-2 latents (3.2 MB) remain in every scheme.

95.4 % of the resent Sink bytes (693.4 MB) are changes the destination's replay already reproduces bitwise.

## 3. Proposed optimization (supported by this run)

Treat the destination's shadow Sink as authoritative for the deterministic changes, and ship only the
non-deterministic ones.

1. **Exact refresh patches in the log.** When a source call makes a refresh decision, its log entry also carries the
   exact K / V of the refreshed (layer, row, slot) entry: 9.58 MB per entry. Right after replaying that call and before
   the next one, the destination overwrites the replayed entry with the exact value. Later realignments of that entry
   then act on exact values. As a side benefit, the replayed recent slots no longer attend to an approximate Sink
   entry.
2. **No Sink resend at the switch.** The PSWITCH message carries a digest of the source's Sink at M. The destination
   compares it with its shadow Sink. If they are equal, it uses the shadow Sink as is, with no fragment resend and no
   bind of a pre-copied buffer. If not, it falls back to the existing dirty-fragment resend.
3. **Expected effect.** The ~5.8 s Sink transfer leaves the critical path. The source would also no longer need the
   full-state serialization plus dirty hashing at the switch, about 1.5 s in E3. The in-flight and metadata transfer,
   verification, DR-2 and the first call remain. This is an estimate from this run, not a measurement.

## 4. Main correctness risk

**Bitwise determinism of the realignment across hosts.** The 72 / 72 bitwise result was measured in one process on one
GPU. Cross-host bit-exactness was observed earlier (Phase 1, E0 replay determinism), but not for this rotation on two
hosts.
- If one ulp differs, the shadow Sink drifts silently from the source's.
- The digest check at the switch, with fallback to the resend, is therefore required, not optional.

**Secondary risks:**
- **Patch ordering.** A refresh patch must be applied after its call and before the next replayed call, or a later
  realignment rotates the approximate value.
- **Refresh-heavy inputs.** This workload refreshed twice in 33 calls. E2 saw up to 14 refresh writes per 12 calls on
  butterfly. Patches would then add about 11 MB per call (about 160 Mbps) during the shadow, still far below the resend.
- **Sample size.** This is a single run on one workload.
