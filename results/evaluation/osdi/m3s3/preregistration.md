# M3-S3: lineage-aware staging across an ownership change (preregistration, 2026-10-29)

Fixed before any GPU run of this study. Background: `../m3s2/m3s2_report.md` (M3-S2 SUPPORTED, 9918de3d). The frozen
M1 / M2 (47acbe44) are not changed in behaviour; the M3-S2 path keeps its behaviour unless the two new flags of this
study are given (section 3.4).

## 1. Question

M3-S2 showed exact mixed-version reconstruction while the original source A served until the final switch. Its
declared limitation: lineage after an ownership change was not exercised and the old source never acted as a holder.

*After a completed live migration A -> B makes B the owner, can OTTER restore D exactly from (i) the old owner A's
retained Sink, (ii) a newer partial Sink that B left at C in a cancelled migration, and (iii) B's latest delta, with
B's lineage deciding what is valid, and switch live?* Only once that holds: does it reduce remote serving against the
frozen M1 / M2 baseline by the M3-S2 margin?

## 2. Design decisions

1. **The source of truth moves with ownership.** The new owner starts its own lineage history at its switch call s1,
   from the Sink positions it holds at that boundary (equal to the old owner's: SINKOK at the switch). Every validity
   decision after s1 is the new owner's.
2. **The old owner becomes a holder only through a verified version.** At the switch the old owner already retains a
   host copy of the Sink verified at s1 (frozen M2 retain). It cuts that copy into the 180 entries, hashes them and
   holds them at version s1 (no GPU work, off the critical path). The new owner issues those hashes under its own
   lineage only if the retained version (session, call, Sink digest) is exactly the version it verified at the switch
   (its M2 tracking version). Otherwise they stay not issued and are never reused.
3. **History handover is contiguous or refused.** The old owner's history and issued table are prepended to the new
   owner's only if the old history ends at s1 - 1. A gap is refused: versions older than s1 then stay invalid. (In the
   preregistered mobility no holder has a version older than s1, so this path is checked offline in P0 and by the dry
   tests only.)
4. **Both holders are used only for what they hold verified and valid.** The planner never assumes an entry's
   presence from a started transfer (the M3-S2 states: verified-held, in flight, lost). The old owner A (version s1)
   and C (B's version c0_BC, received in the cancelled B -> C base) are providers at the same time; per entry the
   newest valid version is chosen. D's Sink is accepted only if all 360 block checksums, positions and conditioning
   equal the owner's at the base boundary; otherwise the frozen full-base fallback.
5. **Staging is re-planned while another move can come.** C's partial Sink exists only during the B -> C pre-copy, so
   plans at moves alone (M3-S2) could never stage it before the next handoff. With `--m3_replan_s 2` the S2 planner
   (unchanged rule) also runs every 2 s between the first and the last move; each re-plan re-rates every active
   forward flow to equal shares that never exceed a node cap (flows started earlier are slowed, a new flow is never
   added on top of a full link). After the last move no periodic plan runs (there is no next handoff).

## 3. Mechanism and implementation

### 3.1 Mobility (all phases on the testbed)
A -> B -> C -> D, trigger call 30, 1 Gbps caps, precopy_replay with Replay-12, lag 1, Sink sync, retain, reuse
(M3-S2 settings), but moves by call instead of T_m:
- A -> B starts at the trigger and switches at the planned call **s1 = 80** (`--replay_switch_calls 80`);
- the user moves to C when the owner B reaches call **110** (B -> C starts), and to D when B reaches call **130**
  (B -> C is cancelled before it can complete: a full base needs ≈ 22 s, 20 calls ≈ 13 s; B -> D starts).
Scenario validity (checked per run): the completed migrations are exactly A -> B then B -> D; A -> B switches before
the first move; B -> C is cancelled.

### 3.2 Protocol additions (M3-S3 only)
- `M3_OWNER_ARM` (all nodes, run start). A node that becomes the owner through a switch (`_xb_become_owner`) starts a
  new `LineageHistory` at the switch call before its first generator call; the previous history object is kept aside.
- At a completed switch the orchestrator sends `M3_HANDOVER_BEGIN` to the old owner (background build from the M2
  retained copy, `m3_path.retained_entries`). Before the next advertisement or plan it collects the result
  (`M3_HANDOVER`: retained version, entry hashes, history export) and sends it to the new owner
  (`M3_LINEAGE_IMPORT`: version check, contiguous merge).
- Periodic re-plan and re-rating (`M3_FORWARD_RATE`).
- D records the provenance of every assembled entry: (issuer, sender, version).

### 3.3 Staging policy
The M3-S2 S2 rule unchanged: at each plan, every node that is neither the user's edge nor the owner is a candidate;
for each entry a candidate lacks in a valid version, a holder that holds it verified sends it (newest version, then
fewest assignments). The old owner is a holder like any other. Plans: at each move (as M3-S2) and every 2 s between
the first and the last move.

### 3.4 Code (commit of this preregistration)
- `tools/eval/m3_path.py`: `LineageHistory.export / merge_prefix`, `retained_entries`, mixin commands M3_OWNER_ARM,
  M3_HANDOVER_BEGIN, M3_HANDOVER, M3_LINEAGE_IMPORT, M3_FORWARD_RATE, `_m3_become_owner`; forward flows keep their
  throttle; D's `m3_base` event gains `provenance`. M3-S2 runs never call the new commands.
- `tools/eval/mobility_node.py`: 2 lines in `_xb_become_owner`, guarded (`if run has M3 state:`); the hook does nothing
  unless the node was armed. Without `--m3` nothing changes; with `--m3` but without `--m3_owner` nothing changes.
- `tools/eval/mobility_orchestrate.py`: `--m3_owner`, `--m3_replan_s` (default 0 = M3-S2 behaviour), three faults
  (`version_mismatch`, `corrupt_retained`, `old_owner_fail`), handover at completed switches, periodic re-plan,
  re-rating, `owner_change` accounting; run-id suffix `_own`, `_rp2`.
- `tools/eval/m3s3_p0.py` (Phase P0), `tools/eval/m3s3_report.py` (rules), `tools/eval/run_m3_s3.sh`.

### 3.5 Dry tests (Mac, fake runtime; before freezing)
See section 9 (filled before the freeze commit). The fake runtime checks protocol, versions and accounting only.

## 4. Phases and measurements

| phase | where | runs | what |
|---|---|---|---|
| **P0** | elves-01 GPU 0 | dog, butterfly (seed 0), one generation each | offline checks of the two new pieces (below) |
| **A** | elves-01..04 | dog, butterfly, M3-S3 (`--m3 --m3_owner --m3_staging S2 --m3_replan_s 2`), 1 run each | exactness after the ownership change |
| **C** | same runs as A | | both live switchovers |
| **B** | elves-01..04 | dog, M3-S3, one run per fault | version_mismatch, corrupt_retained, old_owner_fail (`--m3_fail_after 40`) |
| **D** | elves-01..04 | dog, butterfly × {base = frozen M1 / M2, ctl = M3 entry path + owner lineage without staging, s2 = M3-S3} × 3 reps | performance |

**P0 (offline, one GPU; switch call 80, A-era version 50, targets 100, 120, 140).** R: entries cut from the M2
retained copy equal `gpu_entry_payload` and the live ring (metadata and bytes, 180 / 180). M: the merged history is
contiguous; an export missing its last call is refused (and version 50 then invalid). E: (a) retained entries at 80
with ordered shifts of [80, t) equal the live entries at t; (b) entries at version 50 with ordered shifts of [50, t),
spanning both owners, equal the live entries at t. N: a new-owner history missing the switch call's events must yield
a detectable difference for every entry whose call-80 event it missed (reported "not exercised" if there is none).
S: Sinks assembled from retained-80, version-50 and target entries (all-retained shape + 5 random mixes per target):
360 / 360 checksums equal.

Measured in A–D: everything M3-S2 measured, plus the handover (build time, sizes, import result), D's provenance
(old owner at s1, C at c0_BC, fresh from B), re-rates, per-switch checks, remote serving per phase.

## 5. Rules (applied by `tools/eval/m3s3_report.py` as written)

- **P0 pass** (each workload): R, M, E(a), E(b), S all exact / as stated; N all detected.
- **A pass** (each workload): run valid by the frozen XB validity; scenario valid; handover A -> B accepted
  (contiguous, version equal); final base (B -> D) mode `m3` accepted with 0 block mismatches, positions equal,
  conditioning equal; **≥ 1 entry issued by the old owner A at version s1** in D's final Sink; on butterfly also
  **≥ 1 entry issued by B at version c0_BC and sent by C** (dog: reported only; its Sink is rarely refreshed, so A's
  entries cover almost everything and C may have nothing to add).
- **C pass** (each workload): both switches (A -> B, B -> D) with source verdict SINKOK, base verified, conditioning
  equal, Sink digest equal, metadata consistent at resume, replay order ok; generator calls contiguous and unique
  across all owners, each call served by the owner of its interval; no refused switch. Continuity (interruption,
  first output, readiness) is a diagnostic, not a criterion.
- **B pass** (each fault; valid, scenario valid, both switches as in C, final base `m3` accepted with 0 mismatches):
  version_mismatch — import refuses the retained hashes (version not equal, 0 issued) and **0** entries from A in D's
  Sink; corrupt_retained — the corrupted entry is rejected on receipt from A (bad hash), so it is never held or
  assembled from A's bytes; old_owner_fail — ≥ 1 entry from A lost mid-payload, no expected entry left waiting.
- **D** (medians of 3 valid reps; runs with an invalid scenario are excluded and reported; only if P0, A, B, C pass):
  **R-D1** s2 remote ≤ 0.80 × base and s2 total bytes ≤ 1.30 × base, both workloads (the M3-S2 margins, unchanged).
  **R-D2** (attribution) s2 remote ≤ 0.85 × ctl, both workloads. Reported: remote serving per phase (before the first
  switch; from the first move to the final switch), final readiness, final base bytes, provenance, forward bytes by
  link, re-rates, handover cost.

| outcome | conclusion |
|---|---|
| P0 or A fails | exactness across an ownership change not shown: M3's scope stays "source serves until the final switch" |
| P0, A pass; B or C fails | correctness incomplete: fix before any performance claim (no D run) |
| P0, A, B, C pass; R-D1 holds | **SUPPORTED**: exact, fault-safe and live across an ownership change, by the M3-S2 margins |
| P0, A, B, C pass; R-D1 fails | correct but not faster by the margin; reported with the decomposition |

## 6. Predictions (written before the runs; not evidence)

Seed 0 runs repeat the A0 trajectory, so A0's refresh counts apply.
- P0 passes (same detection rule and shift as A0; the retained copy is the frozen M2 serialization).
- A, dog: A's version-80 entries stay valid almost entirely (A0: 179 / 180 from 81 to 140), so D reuses ≈ 170–179
  entries from A and C adds 0–2; the final base is ≤ 10 entries. Butterfly: ≈ 155 of A's entries are valid at the move
  to C (A0: 161 at 100, 149 at 120), ≈ 25 are refreshed under B; C receives most of those in B's cancelled base and
  forwards 5–20 of them to D; D reuses ≈ 130–150 from A; the final base is 15–45 entries.
- The final migration's readiness hits the Replay-12 floor (≈ 13 calls after the base boundary, ≈ 7.5–9 s) in s2;
  ≈ 22–26 s in base and ctl.
- D: remote serving includes ≈ 30–33 s before the first switch, identical in every condition, so the ratio is diluted:
  s2 / base ≈ 0.76–0.82 (R-D1 is at risk); total ≈ 1.0–1.15 × base; ctl ≈ base (0.95–1.0). Reported separately, the
  window from the first move to the final switch: s2 / base ≈ 0.45–0.6.
- Faults: version_mismatch — D's Sink has 0 entries from A, C contributes its partial entries, the rest is sent;
  corrupt_retained — one entry rejected at D, re-provided by C or sent; old_owner_fail — A's flow stops after 40
  entries, A advertises nothing afterwards, C and the source cover the rest.

## 7. Limitations (declared)

- One mobility pattern (one completed + one cancelled migration after the ownership change), planned first switch,
  moves by call, 1 Gbps caps, one seed per workload, two workloads, faults on dog only, 1 run per A/B/C cell.
- Versions older than the switch are exercised only offline (P0 E(b)) and in dry tests: no holder has one in this
  mobility.
- Equal-share re-rating is not max-min; base and log flows are not counted against the forward shares (as M3-S2).
- Frame-level continuity is not compared with a fresh-base run (diagnostic only, as M3-S2).

## 8. Discipline

No GPU run before this file is committed; rules, thresholds and predictions do not change after a run. Phases run in
order and a failing phase stops the later ones. Every number in the report is labelled measured or predicted.

## 9. Dry tests (Mac, fake runtime, before the freeze; protocol, versions and accounting only, not evidence)

- Frozen regressions: `test_m2_live.py` (E9 / E10: delta, fallback, three faults) ALL PASS (45 checks); the six M3-S2
  dry cases (none, control, S2, advertise_wrong, corrupt_held, holder_fail) behave exactly as recorded in the M3-S2
  preregistration (S2: 170 reused; corrupt_held: rejected naming block [0, k, 0, 0], full fallback; holder_fail: 39
  reused). `test_xb.py` ALL PASS (87 checks).
- M3-S3 dry scenario (A -> B switch at 80, moves at B's calls 120 and 130 because a dry base takes < 1 s; on the testbed
  110 and 130), `--m3_replan_s 1`:
  - S2: handover A -> B accepted (contiguous, 49 merged calls, version equal, 180 retained hashes issued); at the
    move to C the planner forwarded A's 138 valid entries to D; a re-plan forwarded C's 42 newer entries to D and A
    (re-rated to 50 / 50 Mbps on C's egress); D assembled 128 entries from A (version 80) + 42 from C (B's version 122)
    + 10 fresh (132), accepted; switches A -> B and B -> D both SINKOK.
  - ctl: owner lineage without staging, D's base all fresh, accepted.
  - version_mismatch: import refused the retained hashes (version not equal, 0 issued); D's Sink has 0 entries from A.
  - corrupt_retained: entry 0 from A rejected on receipt at D (bad hash), C supplied it; accepted.
  - old_owner_fail: A's flow cut mid-entry after 40 entries (entry 52 lost); A then advertised nothing; C supplied 132
    entries; accepted.
- Report tool end to end on 11 dry runs (A ×2, B ×3, D ×6 with 1 rep; `--move_calls 120,130`, `--m3_replan_s 2`):
  executes; B 3 / 3 pass, C pass; with a 2 s re-plan interval the dry move-to-move window (2.05 s) ended before the
  first periodic plan, so C's entries did not reach D and the butterfly C-rule read false. On the testbed the window is
  20 calls (≈ 13 s, ≈ 6 re-plans). Dry byte ratios are meaningless (4 KiB fake entries vs fragment-sized fake Sink).

## Note 1 (2026-10-29, after the first P0 / A / C / B runs; rules, thresholds and predictions unchanged)

**Harness defect, found in the first runs (Original set, commit 27d42a63, `m3s3_results_original.json`).** The
orchestrator starts the old owner's handover when the new owner resumes. On the GPU the old owner's switch thread is
still copying its retained Sink to host memory at that moment (≈ 1.0 s, `retain_s` 0.99–1.10 s in all five runs), so
the handover found no retained copy and built 0 entries (dry runs did not show it: the fake retain is instantaneous).
Consequence in all five testbed runs: A held nothing, B could not issue A's version (version_equal false because the
retained version was null), and the old-owner holder path, the hypothesis under test, was never exercised.

**Original verdict, as written:** P0 pass on both workloads (with N not exercised: no Sink event at call 80; and no
entry had shifts on both sides of the switch in E(b)); A fails on both (handover not accepted, 0 entries from A);
C passes on both (A -> B and B -> D SINKOK, calls contiguous); B: version_mismatch passes only vacuously,
corrupt_retained and old_owner_fail fail (nothing from A to corrupt or lose). Frozen mapping: "exactness across an
ownership change not shown". Recorded, not overwritten.

**What the Original runs do show (descriptive):** after the ownership change, B's partial Sink left at C (version 112,
issued by the new owner B) was forwarded by C to D and reused: dog 64, butterfly 57 entries, combined with 116 / 123
fresh entries at 133, 0 of 360 blocks mismatching, both switches SINKOK. Because A held nothing, C also forwarded
1.26 / 1.05 GB to A (a candidate under the unchanged S2 rule).

**Fix (Corrected set).** `_m3_handover_build` waits (bounded, 120 s) until the old owner's switch thread has finished
(retained copy present, or switch done without one) before reading the retained copy; the wait is recorded
(`retain_wait_s`). Unit-tested with a retain that arrives 1 s late (waits 1.03 s, then 180 entries) and with a switch
without a retain (no wait). No other change. The Corrected runs use experiment names `expM3S3c{A,B,D}_*`
(`run_m3_s3.sh` default; `m3s3_report.py --set c`, the default); the Original runs stay under `expM3S3{A,B}_*`
(`--set ""`). P0 is not rerun: `m3s3_p0.py` does not use the handover build. Phases A/C and B are rerun in full on the
corrected harness; D only after they pass.

## Note 2 (2026-10-30, after the first Phase D runs; rules, thresholds and predictions unchanged)

**Procedure defect: the first Phase D set ran with the hosts on different commits.** Before D only elves-01 was
updated (to 79d107b0, which added the A/C/B report); elves-02..04 stayed on 73dfc084. `tools/` is identical between the
two commits (0 diff lines; 79d107b0 changed only result files), but the frozen XB validity requires one commit on all
nodes, so all 18 runs are **invalid** and Phase D has **no verdict** from them. The runs are kept, renamed to
`expM3S3cDmix_*`; numbers computed without validity (descriptive only) are in `m3s3_D_commitmix_descriptive.json`.
Rerun: all four hosts synced (`d0_remote.py pull`), preflight must report one commit, then `run_m3_s3.sh perf` into
`expM3S3cD_*`, judged by the rules as written.
