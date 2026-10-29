# M3-S2: GPU validation of lineage-aware forwarding and mixed-version Sink reconstruction (preregistration, 2026-10-29)

Fixed before any GPU run of this study. Background: `../m3s1/m3s1_report.md` (Corrected M3-S1: GO at the network
level), `../m3_topology_research.md`. The frozen M1 / M2 (47acbe44) and the M3-v2 planner are not changed in
behaviour (section 3.3).

## 1. Question

*Can OTTER assemble an exact Sink from partially restored, differently versioned blocks held across GPUs, while
preserving live-generation continuity?* And, only once that holds: does it reduce remote serving against the frozen
M1 / M2 baseline on real GPUs by the margin M3-S1 measured on the network?

Exactness and fault safety come first; performance is judged only after them (section 5).

## 2. Design decisions (the user's, 2026-10-29)

1. **Entry-aligned, M3-only transfer path.** The frozen M1 path ships the Sink in 4 MiB fragments that are not block
   aligned (412 fragments vs 180 entries); a fragment could mix versions. M3 ships entries: the K and V blocks of one
   (layer, row, Sink slot), with its version (the snapshot call it was serialized at) and the SHA-256 of its bytes,
   both issued by the source that serialized it. Holders forward entries unchanged; every receiver verifies the hash.
   The metadata component, the input log, the replay, the Sink digest at the switch (SINKOK / SINKNO) and the cutover
   are the frozen M1 / M2 ones.
2. **A separate per-entry lineage tracker beside the frozen M2 tracker.** Per call: refreshed entries and shifts (the
   M2 tracker's detection rule, copied, not shared); the table of (entry, version) -> hash the source issued. M2's
   tracker is not touched; M1 / M2 runs never enter this code.
3. **Holder location: source-known vs holder-verified.** A node advertises only entries it holds verified. Entries a
   stopped forward flow had fully written toward it are waited for (bounded, 10 s) before the advertisement and are
   never advertised unverified; an entry whose connection failed mid-payload is *lost* and is never waited for. The
   source reuses an advertised (entry, version, hash) only if it issued exactly that triple and the entry was not
   refreshed since that version; every other entry is sent at the base boundary.

## 3. Mechanism and implementation

### 3.1 Protocol (round 1 of an M1 replay pre-copy with `replay_m3`)
- Before the pre-copy to a target, the orchestrator stops every forward flow toward it, the target waits for the
  entries those flows fully wrote (in flight, expected), and advertises its verified entries; the advertised bytes are
  frozen for the assembly.
- Source at boundary c0: per advertised entry, reuse iff issued and not refreshed in calls [v, c0); plan = reused
  entries with their ordered K shifts of [v, c0) + entries to send. It sends the metadata component (frozen path), the
  plan, the entries to send (each tagged c0, hash issued and recorded), and the boundary's 360 block checksums.
- Destination: assemble every entry into the receive snapshot, restore the shadow ring (frozen `shadow_base`), apply
  each reused entry's ordered RoPE shifts (the frozen M2 shift), compute the 360 block checksums. Accept (DELTAOK)
  only if all 360 checksums and the Sink positions equal the source's at c0 and the conditioning digest matches;
  otherwise DELTANO and the source sends the full base on the frozen path. Then the frozen replay, SINKOK check and
  switch.
- A move before readiness cancels the migration between entries; the abandoned destination keeps its verified
  entries with their versions.

### 3.2 Staging policy (the Corrected M3-S1 S2)
At each move: every node that is neither the user's edge nor the source is a candidate (order A, B, C, D); for each
entry a candidate lacks in a still-valid version (the source answers validity), a holder that holds it verified sends
it (newest version, then fewest assignments). Holders are abandoned destinations; the source never stages. Per-flow
rate = min(holder egress, candidate ingress) / concurrent flows at that node (static; stated limitation). Unlike the
network harness, no staging is planned after the final ownership (there is no next move), so total bytes exclude the
≈ 250 MB post-ownership staging M3-S1 counted.

### 3.3 Code (commit of this preregistration)
- `tools/eval/m3_path.py` (new): `LineageHistory`, `EntryStore`, `FakeSinkModel` (dry runs only), GPU helpers
  (`gpu_track_events`, `gpu_entry_payload`, `gpu_assemble`), `M3NodeMixin` (M3_TRACK / M3_VALID / M3_HELD / M3_FORWARD /
  M3_FORWARD_STOP / M3_STATE, MENTRY / MPLAN receive, `_m3_send_base` with serialization prefetch, `_m3_replay_base`).
- `tools/eval/mobility_node.py`: 9 lines, each guarded (Node inherits the mixin; `replay_m3` / `m3_held` copied into
  the replay task; round 1 calls `_m3_send_base` only if `replay_m3`; two tracking hooks in `_generate` only if the run
  has M3 state; MENTRY / MPLAN / PROUND mode `m3` dispatch). Without `--m3` the behaviour is unchanged.
- `tools/eval/mobility_orchestrate.py`: `--m3`, `--m3_staging none|S2`, `--m3_order`, `--m3_test_fault`,
  `--m3_fail_after`, `--m3_held_wait_s`; advertisement before each pre-copy, S2 planner at each move, `m3` summary and
  validity keys. Without `--m3` unchanged.
- `tools/eval/m3s2_assemble.py` (Phase A0), `tools/eval/m3s2_report.py` (rules), `tools/eval/run_m3_s2.sh`.

### 3.4 Dry protocol tests (Mac, fake runtime; before freezing)
Frozen regressions unchanged: `test_m2_live.py` (E9 / E10 delta, fallback and three faults) ALL PASS; the M3-E0 dry
test ALL PASS. M3 (A → B → C → D, T_m 1.2 s, two cancellations): S2 — D assembled 170 entries of B's version 32 + 10 at
42 with 37 shift operations, accepted, SINKOK; control (no forwarding) — accepted; advertise_wrong — the 3 altered
entries re-sent, accepted; corrupt_held — rejected naming exactly the corrupted entry, full fallback, SINKOK;
holder_fail — the entry cut mid-payload is lost, not advertised, not waited for, the source sent the rest, accepted;
cancellation in the middle of an M3 base — the 2 entries received before the cancel were forwarded and reused. The
fake runtime checks protocol and versions only, not GPU exactness.

## 4. Phases and measurements

| phase | where | runs | what |
|---|---|---|---|
| **A0** | elves-01 GPU 0 | dog, butterfly (seed 0), one generation each | offline mixed-version exactness (below) |
| **A** | elves-01..04 | dog, butterfly, ρ = 1, M3 S2, 1 run each (frame dumps kept for diagnostics) | end-to-end exactness of the final base |
| **C** | same runs as A | | live switchover and continuity |
| **B** | elves-01..04 | dog, ρ = 1, M3 S2, one run per fault | advertise_wrong, corrupt_held, holder_fail (`--m3_fail_after 40`) |
| **D** | elves-01..04 | dog, butterfly, ρ = 1 × {base = frozen M1 / M2 (no `--m3`), ctl = M3 entry path without forwarding, s2} × 3 reps, no dumps | performance |

Settings for A–D: the M3-E0 settings (A → B → C → D, trigger call 30, T_m = 14.05 s, 1 Gbps caps, precopy_replay with
Replay-12, lag 1, Sink sync, retain, reuse).

**A0 (offline, one GPU).** One deterministic generation; the M3 lineage history from call 30; at boundaries
{30, 43, 56, 68, 81, 100, 120} and targets {56, 81, 100, 120, 140} all 180 entries copied to host, at targets the
360 block checksums. E: for every (v < t) pair and entry the history calls valid, entry(v) + ordered shifts of [v, t)
must equal entry(t) bitwise (K and V). S: for each target, Sinks assembled from one older version (each), from a random
version per entry (5 seeds; ≥ 3 versions in one Sink), and in the M3-S1 shape (139 entries from version 30), written
into the live ring and shifted in place: 360 / 360 checksums equal. N (negative controls): shifted entries reused
without shifts must differ; a refreshed entry reused stale must be caught by the 360-block digest; the summed shift
as one rotation is reported only.

Measured in A–D: remote serving (XB delivery accounting), per-migration timeline, the final base (mode, reused
entries and their versions, shift operations, block mismatches, positions, conditioning), the switch (SINKOK, replay
checks, interruption, first output), bytes (base, log, forward, discarded, header bytes of entry messages), entries
lost / bad, advertisement wait.

## 5. Rules (applied by `tools/eval/m3s2_report.py` as written)

- **A0 pass** (each workload): E all exact; S all exact; N: every no-shift reuse and every stale-entry Sink detected.
- **A pass** (each workload): run valid by the frozen XB validity; final base mode `m3` accepted with 0 block
  mismatches, positions equal, conditioning equal; ≥ 1 entry of the first destination's version (B's abandoned partial
  base) in the final Sink.
- **C pass** (each workload): one verified switchover to D, SINKOK at the switch, every replay check true (base
  verified, conditioning, order, metadata at the switch, no lost or duplicated call, Sink digest), no refused switch.
  Continuity (interruption, first output, readiness; VD-3 frame metrics and frame comparison with a fresh-base run when
  done) is reported as a diagnostic, **not** a criterion: M1 does not reproduce uninterrupted outputs bitwise.
- **B pass** (each fault): valid; one verified switchover, SINKOK, base verified; and advertise_wrong — the 3 altered
  entries not reused and the M3 base accepted; corrupt_held — the assembled Sink rejected (≥ 1 block mismatch) and the
  final base the full fallback; holder_fail — ≥ 1 entry lost, the M3 base accepted, no expected entry left waiting.
- **D** (medians of 3 valid reps; only if A0, A, B, C pass): **R-D1** s2 remote ≤ 0.80 × base and s2 total bytes
  ≤ 1.30 × base, both workloads (the M3-S1 R1 margins). **R-D2** (attribution) s2 remote ≤ 0.85 × ctl, both
  workloads. Reported: ctl vs base (the entry path's own effect), header bytes / entry bytes (framing), readiness,
  interruption, reused entries; and the M3-S1 Corrected network numbers as reference.

| outcome | conclusion |
|---|---|
| A0 or A fails | exactness not shown: M3 stays a network-level result; the cause reported (no D run) |
| A0, A pass; B or C fails | correctness incomplete: fix before any performance claim (no D run) |
| A0, A, B, C pass; R-D1 holds | **SUPPORTED**: exact, fault-safe, live, and ≤ 0.80 remote / ≤ 1.30 bytes vs M1 / M2 |
| A0, A, B, C pass; R-D1 fails | correct but not faster by the margin; reported with the decomposition |

## 6. Predictions (written before the runs; not evidence)

- A0 passes: the detection rule and the ordered RoPE shift are those E9 / E10 validated for one retained version;
  mixing versions changes only which shifts each entry gets. The one way it can fail is a refresh write that leaves a
  slot's position unchanged (invisible to the position-based rule); it would appear as an E mismatch.
- A: dog reuses ≈ 137 entries of version ≈ 30 (network: 137–138), butterfly ≈ 108; final base ≈ 405 / 692 MB;
  readiness ≈ 8.1 / 12.6 s (network). The GPU adds per-entry D2H + SHA-256 at the source (overlapped by prefetch) and
  H2D + shifts at the destination (< 0.5 s expected).
- B: as in the dry tests.
- D: s2 / base remote ≈ 0.73–0.78 (network S2 / S0: 0.734 / 0.781); total ≈ 1.0–1.05 × base (no post-ownership
  staging). ctl may be *faster* than base by up to ≈ 2 s per migration because the entry path hashes per entry instead
  of all 412 fragments up front (M3-S0 fitted 2.36 s startup); this is the path's own effect, which R-D2 separates from
  forwarding. Framing overhead < 0.1 % of entry bytes.

## 7. Limitations (declared)

- The source A owns the session until the final switch, so lineage after an ownership change is not exercised; the
  old source as a holder is not implemented.
- Static per-flow forward rates; one run per configuration in A, B, C; frame-level continuity is diagnostic only.
- One seed per workload; two workloads.

## 8. Discipline

No GPU run before this file is committed; rules, thresholds and predictions do not change after a run. Phases run in
order and a failing phase stops the later ones. Every number in the report is labelled measured (testbed / GPU) or
predicted.
