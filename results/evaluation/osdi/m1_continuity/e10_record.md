# E10 record: final M2 functional validation (2026-10-29)

## Sources

- Runs: `results/evaluation/expM2E10_{bfly_baseline,bfly_m2,dog_fault_advertise,dog_fault_held,dog_fault_corrupt}`
  (pushed 8a7456ce), at commit 47acbe44. The plan `e10_plan.md` was committed in 47acbe44, before the runs.
- Continuity: `e10_metrics_<run>_mig{1,2}.json`, computed on host B (3607bd17). VD-3 frozen rules; butterfly with
  `butterfly-feeding-slow-motion_s1|OT-1` thresholds (REF P99 1.25), dog with `dog_s1|OT-1`.
- Bitwise frame comparison: `e10_frames_bitwise.json` (`tools/eval/m2_e10_frames.py`). **PENDING** (section 4).
- Report: `e10_report.json` (`tools/eval/m2_e10_report.py`).
- Setup as E9:
  - A -> B -> A on elves-01 / elves-02, 1 Gbps, Replay-12, Sink synchronization on;
  - switches planned at calls 64 and 164, second trigger at 120.
- Every run switched exactly at 64 and 164 (`switch_call_missed` false everywhere).
- One run per configuration, so this is a functional validation, not a performance distribution.

Unless marked otherwise, all values below are measured. Estimates are labelled.

## 1. Butterfly s1 end to end: baseline (fresh base twice) vs M2 (delta base at the second migration)

### Equivalent source states

The second migration starts from the same B state in both arms:
- **Sink version digests are identical:** the SHA-256 over the 360-block Sink checksums plus positions is
  `8dd34d53...` at call 64 (A's retained version) and `a2d73305...` at call 164 (B's Sink at the switch), in both
  arms.
- **Outputs are identical:** per-call PSNR / SSIM against the reference are identical over A 20 .. 63 (44 calls),
  B 64 .. 163 (100 calls) and A 164 .. 264 (101 calls).
- **First migration:** identical in both arms (full base, 1,727.6 MB; SINKOK; interruption 1.86 s).

### Second migration (B -> A)

| | baseline: M1 fresh base | M2: delta base from A's retained Sink |
|---|---|---|
| base | full, 1,727.6 MB | **delta, 357.0 MB** (37 entries 354.6 MB + 63 shifts, metadata, digest) |
| base verification on A | component digest OK | **DELTAOK**: version, metadata, 360 / 360 block checksums, positions equal; `mismatched_blocks` [] |
| log incl. refresh patches | 562.7 MB (57 patches, 546.3 MB) | 562.7 MB (same) |
| total migration bytes | 2,293.5 MB | **922.9 MB** (-59.8 %) |
| trigger to base ready on A | 19.73 s | **5.59 s** (rebuild 0.42 s incl. H2D 0.09 s, digest 0.06 s) |
| trigger to replay ready | 23.98 s (call 156) | **8.97 s** (call 134) |
| interruption | 1.61 s | 1.53 s |
| cutover at 164 | SINKOK, 0 / 360 block mismatches | SINKOK, 0 / 360 block mismatches |

On this workload M2 removes 79 % of the base, but only 60 % of the traffic. The refresh patches of the Replay-12
log (546 MB) are part of M1 and M2 does not change them. They are now the largest component.

### Against E8's offline estimate (393 MB)

The two are not expected to be equal, and they are not.
- **E8 (offline):** tracked 100 calls (64 .. 163) and found 130 refresh events on 41 distinct entries, about 393 MB.
- **E10 (live):** the delta covers only the calls from the switch to the base boundary (64 .. 122, 59 calls), with
  73 events on 37 entries, 354.6 MB of values and 357.0 MB in total.
- The difference is the shorter tracked interval: E8 counted 41 entries in 100 calls, the live tracker 37 in 59.
- The calls after the base boundary reach A as replayed log entries with exact patches, not through the delta.

## 2. Refresh events vs distinct refreshed entries (owner's tracker, B, calls 64 .. 122)

| workload | tracked calls | refresh events | distinct entries (sent) | shift events kept | delta value bytes |
|---|---|---|---|---|---|
| butterfly s1 (both arms) | 59 | 73 | 37 | 63 | 354.6 MB |
| dog s1 (fault runs = E9) | 59 | 2 | 2 | 73 | 19.2 MB |

- On butterfly, 36 of the 73 events rewrote an entry that had already been refreshed in the interval.
- Only the latest value of each entry is sent, so the delta grows with distinct entries (9.58 MB each), not with
  events.
- Tracking cost: 0.021 s over 59 calls (about 0.35 ms per call) on both workloads.

## 3. Cross-host Sink correctness

Every migration of every run (10 migrations) passed the following.

**Base check.** The full base passed its component digest on the destination. For the M2 delta base, the destination
also compared every block (`n_block_mismatch` 0, positions equal).

**Cutover check at the switch call.** The destination compared the 360 per-block checksums and the Sink positions
against the source's: SINKOK, 0 mismatched blocks, positions equal. No cutover fallback was used.

**Across runs:**
- Each source's Sink version at 64 and at 164 is the same in all runs of a workload:
  - butterfly: `8dd34d53` / `a2d73305`;
  - dog, the three fault runs and E9 M2: `0e1787ef` / `b82268bb`.
- A's Sink after a delta reconstruction (bfly_m2) therefore equals the Sink B held at the base boundary block for
  block. After replay, it reaches the same 164 Sink as the fresh-base arm.
- Corruption is caught block by block, not only through the aggregate digest: the corrupt_block run reported exactly
  the injected block (section 5).

## 4. Continuity (VD-3 frozen rules, window [M, M + 24))

| run | migration 1 (M 64) P1 / P2a / P2b | V1 (REF same call) | migration 2 (M 164) P1 / P2a / P2b | V1 (REF same call) |
|---|---|---|---|---|
| bfly_baseline | pass / pass / pass | 1.011 (0.989) | pass / pass / pass | 0.819 (0.558) |
| bfly_m2 | pass / pass / pass | 1.011 (0.989) | pass / pass / pass | 0.819 (0.558) |
| dog_fault_advertise | pass / pass / **fail** | 1.934 (1.027) | pass / pass / pass | 1.321 (0.827) |
| dog_fault_held | pass / pass / **fail** | 1.934 (1.027) | pass / pass / pass | 1.321 (0.827) |
| dog_fault_corrupt | pass / pass / **fail** | 1.934 (1.027) | pass / pass / pass | 1.321 (0.827) |
| E9 dog baseline / M2 (reference) | pass / pass / fail | | pass / pass / pass | 1.321 (0.827) |

- Every metric (V1, D_c, C_c, late D_c, warp excess, frame-difference ratio) is identical, to every printed digit:
  - between bfly_m2 and bfly_baseline at both migrations;
  - between each dog fault run and E9's fresh-base baseline at the second migration.
- **The dog first-migration P2b fail** is the dog s1 residual already present in E9's baseline (and E3 / E5). It is not
  caused by M2: the first migration of every run uses the fresh base.
- **Bitwise frames:** PENDING (`e10_frames_bitwise.json`, run on B). The comparisons are
  - bfly_m2 against bfly_baseline;
  - each fault run against E9's baseline;
  - all on stores OUT_B, OUT_A, REF_B and REF_A.

## 5. Real GPU delta-base fallback (dog s1, E9 configuration)

| fault | injection | detection | base actually used | Sink at 164 |
|---|---|---|---|---|
| advertise_wrong | A advertises digest `000...0` instead of `0e1787ef...` | **B, before sending:** "the destination's version is not the tracked one"; no delta sent | full, verified | SINKOK, 0 / 360 |
| held_wrong | A advertises its true version; its held record is altered | **A:** `version_ok` false, then DELTANO in 0.68 s | full, verified | SINKOK, 0 / 360 |
| corrupt_block | one bit flipped in retained block (layer 15, K, row 0, slot 0), which the delta does not overwrite | **A:** `version_ok` and `meta_ok` true, `n_block_mismatch` 1, `mismatched_blocks` = [[15, k, 0, 0]] = the injected block; DELTANO in 0.86 s | full, verified | SINKOK, 0 / 360 |

Every fault run:
- completed;
- switched at 164;
- had A generating to the end of the run;
- used no cutover fallback (the M1 cutover check was active and passed);
- matched E9's fresh-base baseline in per-call PSNR / SSIM for A 20 .. 63, B 64 .. 163 and A 164 .. 264 (44 / 100 /
  101 calls).

**Cost of the fallback** (second migration):

| | E9 baseline (fresh base) | E9 M2 (delta accepted) | advertise_wrong | held_wrong | corrupt_block |
|---|---|---|---|---|---|
| base bytes | 1,727.6 MB | 21.6 MB | 1,727.6 MB | 1,749.2 MB (21.6 rejected + 1,727.6) | 1,749.2 MB |
| total migration bytes | 1,756.8 MB | 50.7 MB | 1,756.8 MB | 1,778.4 MB | 1,778.4 MB |
| trigger to base ready | 18.30 s | 2.46 s | 18.58 s (+0.28) | 19.10 s (+0.80) | 19.48 s (+1.18) |
| trigger to replay ready | 22.17 s | 8.74 s | 22.46 s (+0.29) | 23.12 s (+0.95) | 23.58 s (+1.41) |
| interruption | 1.54 s | 1.41 s | 1.55 s | 1.58 s | 1.52 s |

- The +x values are measured against the E9 baseline. With one run each, a difference of about 0.3 s is within E10's
  run-to-run spread: the two butterfly first migrations, which were identical, differ by 0.39 s in base ready.
- **advertise_wrong** costs nothing beyond the fresh base: the mismatch is caught before any delta byte is sent.
- **A rejected delta** (held_wrong and corrupt_block) costs the delta bytes (21.6 MB) plus the wait for the verdict.
  The full base is sent only after DELTANO, so the fallback is sequential.
- The interruption is unaffected: the fallback happens during pre-copy, before the switch.

## 6. Limitations

- **One run per configuration**, one host pair, 1 Gbps, two workloads (dog, butterfly), one A -> B -> A path.
- **Untested:**
  - version scope across more than two hosts (A -> B -> C -> A);
  - a stale retained version after a third owner;
  - migrations under contention or concurrent sessions.
- **Faults are synthetic:**
  - a single altered version record;
  - a single-bit corruption in a block the delta does not overwrite.
  - A corruption inside a block the delta overwrites is replaced by the delta value. It is harmless and therefore
    invisible to the check. The checksum is an int64 weighted sum per block, not cryptographic. The SHA-256 covers only
    the vector of checksums.
- **Retention is unbounded:**
  - every node keeps the last retained Sink (1.73 GB of host memory per host);
  - eviction, multi-session and memory pressure are out of scope (no retention policy, as instructed).
- **The rejected-delta fallback is sequential** (verdict, then full base). Its added latency (+0.8 .. 1.4 s here) grows
  with the delta size.
- **Refresh-heavy workloads:** on butterfly the M1 log patches (546 MB per migration) now dominate M2's traffic.
  Reducing them would be a new optimization and is outside E10.
- **Continuity rules:** VD-3 rules over a 24-call window, with frame dumps covering 100 calls after the second switch.

## 7. Recommendation

**PENDING the bitwise frame comparison.**

If it shows all frames bitwise equal (bfly_m2 vs bfly_baseline, each fault run vs E9 baseline), the recommendation is:
- freeze M1 (input-log replay with replay-aware Sink synchronization);
- freeze M2 (versioned Sink reuse with a digest-verified delta base and full-base fallback) as implemented at 47acbe44.

The reasons:
- every planned check of E10 holds;
- no correctness failure occurred, so no fix or rerun was needed;
- the measured gains of E9 generalize to a refresh-heavy workload with the expected scaling (distinct entries, not
  events);
- every injected fault was detected at the intended point and recovered with an exact Sink, at small cost.

The open items of section 6 are evaluation scope or policy (retention, version scope, patch volume). They are not
correctness defects of the frozen mechanism.
