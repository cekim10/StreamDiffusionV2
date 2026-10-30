# M3-S3 report: lineage across an ownership change

Preregistration: `preregistration.md` (frozen ada30317; Note 1 at 73dfc084, rules unchanged).
Results: `m3s3_results_corrected.json` (Corrected set `expM3S3c*`, this report), `m3s3_results_original.json`
(Original set `expM3S3{A,B}_*`, kept as recorded). Tool: `python3 tools/eval/m3s3_report.py` (`--set c` default).

## 0. Status

| phase | Original (27d42a63) | Corrected (c34e6eb9) |
|---|---|---|
| P0 (offline) | pass, both workloads (N not exercised) | not rerun (does not use the handover build) |
| A exactness after the owner change | **fail** (handover built 0 entries; Note 1) | **pass**, both workloads |
| C live switchovers | pass | **pass**, both workloads |
| B faults | version_mismatch vacuous pass; other two fail | **pass**, all three |
| D performance | not run | first set **invalid** (hosts on different commits, Note 2); rerun on one commit: **R-D1, R-D2 hold** |

**Verdict (frozen mapping): SUPPORTED** — exact, fault-safe and live across an ownership change; remote serving
≤ 0.80 × and total bytes ≤ 1.30 × the frozen M1 / M2 baseline on both workloads (Phase D rerun, section 7).
Sections 1–5 are single runs (correctness); only section 7 is a performance measurement.

## 1. Scenario (both workloads, all Corrected runs) [V]

A → B switch at call 80 (SINKOK); move 1 B → C starts at call 110 (c0_BC 112) and is cancelled by move 2;
B → D base boundary at call 132 (133 in two fault runs, 148 in corrupt_retained, see 3); second switch B → D SINKOK.
Handover A → B: 180 entries built from A's M2 retained copy at version 80 (build 1.84–1.94 s, of which waiting for
A's retain to finish 0.17–0.21 s), history merged contiguously (calls 31–110, 49 merged calls), version equal,
180 retained hashes issued by B. The import happens at the first S2 plan (first move), 18.3–18.5 s after the switch.

## 2. A and C (exactness and liveness) [V]

| | dog | butterfly |
|---|---|---|
| D's final Sink: entries from A (issued A, v80) | **148** | **108** |
| from C (issued B at c0_BC 112, sent by C) | 1 | **11** |
| fresh from B at 132 (final base) | 31 | 61 |
| blocks mismatching / positions / conditioning | 0 / 360, equal, equal | 0 / 360, equal, equal |
| shift ops at assembly | 63 | 49 |
| switches (call, verdict) | 80 SINKOK, 145 SINKOK | 80 SINKOK, 149 SINKOK |
| sink_sync at the second switch | match, 0 mismatches | match, 0 mismatches |
| calls contiguous and unique, owner per interval | yes | yes |
| A pass / C pass | **pass / pass** | **pass / pass** |

D's Sink combines three lineages: the old owner A's retained state (version 80, from before the owner change),
the new owner's cancelled partial at C (version 112), and fresh entries from B, and equals B's live Sink bitwise.

Diagnostics (not criteria): readiness 8.2 / 10.6 s, first output 10.1 / 12.5 s, interruption 1.40 / 1.55 s.
Bytes into D: forward A→D 1.42 / 1.07 GB, C→D 0.01 / 0.13 GB, final base B→D 0.30 / 0.58 GB.

## 3. B (faults; dog) [V]

| fault | what happened | rule | verdict |
|---|---|---|---|
| version_mismatch | B's import saw a different retained digest: version_equal false, **0** retained hashes issued; D's Sink 0 from A, 65 from C (v112), 115 fresh | 0 entries from A | **pass** |
| corrupt_retained | entry 0 of A's copy corrupted after hashing: rejected at D on receipt (bad hash, flow A→D); never held, never assembled from A's bytes; D 147 from A, 1 from C, 32 fresh | rejected on receipt | **pass** |
| old_owner_fail | A's flow to D dropped mid-payload at entry 41: 40 from A, 36 from C, 104 fresh; nothing left waiting | ≥ 1 lost, nothing waiting | **pass** |

All three: valid, both switches SINKOK, final base `m3` accepted with 0 of 360 blocks mismatching.

Observation (descriptive, not a rule): in corrupt_retained D still counted the rejected entry as expected from A's
forward, so the stop-and-advertise waited its 10 s timeout (missing_expected 1) before the final base, which started
at call 148 instead of 132–133. Safe, but a rejected entry costs the advertisement timeout; a fix (drop rejected
entries from "expected") is left for later and does not affect D (no faults there).

## 4. Original vs Corrected (descriptive; one run each, same seed and schedule)

| | Original dog | Corrected dog | Original bfly | Corrected bfly |
|---|---|---|---|---|
| handover entries / accepted | 0 / no | 180 / yes | 0 / no | 180 / yes |
| D's Sink from A / C / fresh | 0 / 64 / 116 | 148 / 1 / 31 | 0 / 57 / 123 | 108 / 11 / 61 |
| final base (GB) | 1.11 | 0.30 | 1.18 | 0.59 |
| second switch call | 156 | 145 | 162 | 149 |
| final readiness (s) | 15.1 | 8.2 | 18.9 | 10.6 |
| remote serving (s) | 58.9 | 52.3 | 63.7 | 55.3 |
| total bytes (GB) | 6.03 | 5.25 | 6.88 | 6.27 |

With A as a holder, C's partial is mostly not needed on dog (A's version 80 entries are still valid and arrive
first); on butterfly both holders contribute. These are single runs; Phase D is the measurement.

## 5. Predictions vs observed (A/C, not evidence)

- P0 pass: held.
- dog: predicted D reuses 170–179 from A, final base ≤ 10 entries. Observed 148 from A, 31 fresh: **missed**
  (more of A's version-80 entries were refreshed under B by call 132 than A0's single-owner counts implied).
- butterfly: predicted 130–150 from A, C 5–20, final base 15–45. Observed 108 / 11 / 61: **A and final base missed**,
  C within.
- readiness at the Replay-12 floor (7.5–9 s): dog 8.2 s held; butterfly 10.6 s above.
- faults: version_mismatch and old_owner_fail as predicted; corrupt_retained: the entry was re-provided by
  sending, as predicted, but with the 10 s wait (not predicted).

## 6. Phase D, first set: INVALID (prereg Note 2)

All 18 runs (`expM3S3cDmix_*`) fail the frozen XB validity with one reason only: nodes on different commits
(A 79d107b0, B/C/D 73dfc084; `tools/` identical between them). No verdict is drawn from them. Descriptive numbers
(validity skipped, `m3s3_D_commitmix_descriptive.json`), medians of 3 reps, **not evidence for R-D1/R-D2**:

| | dog | butterfly |
|---|---|---|
| remote serving base / ctl / s2 (s) | 67.5 / 66.3 / 52.3 | 71.1 / 70.5 / 54.1 |
| s2 / base remote; total bytes | 0.774; 1.098 | 0.762; 1.056 |
| ctl / base remote; s2 / ctl remote | 0.98; 0.79 | 0.99; 0.77 |
| first move to final switch, s2 / base | 0.61 | 0.59 |
| final readiness base / s2 (s) | 21.6 / 8.3 | 22.7 / 9.7 |
| s2 final Sink: from A / from C | 150 / 1 | 107 / 11 |

## 7. Phase D rerun (one commit 20a955f on all four hosts; `expM3S3cD_*`): R-D1, R-D2 hold [V]

18 / 18 runs valid by the frozen XB validity; scenario valid in all. Medians of 3 reps:

| | dog | butterfly |
|---|---|---|
| remote serving base / ctl / s2 (s) | 67.5 / 65.9 / 52.0 | 72.4 / 70.5 / 54.0 |
| **s2 / base remote** (R-D1 ≤ 0.80) | **0.771** | **0.747** |
| **s2 / base total bytes** (R-D1 ≤ 1.30) | **1.098** | **1.051** |
| **s2 / ctl remote** (R-D2 ≤ 0.85) | **0.789** | **0.767** |
| ctl / base remote (entry path + owner lineage, no staging) | 0.977 | 0.974 |
| first move → final switch, s2 / base | 0.607 (21.9 vs 36.2 s) | 0.563 (23.3 vs 41.4 s) |
| before the first switch, all conditions (s) | 31.7–32.8 | 32.4–33.0 |
| final readiness base / ctl / s2 (s) | 21.3 / 21.9 / 8.2 | 24.7 / 26.0 / 9.7 |
| final base base / s2 (MB) | 1,728 / 300 | 1,728 / 597 |
| forwarded (s2, all links, MB) | 1,898 | 1,840 |
| s2 final Sink: from A (v80) / from C (v112) / fresh | 148 / 1 / 31 | 107 / 11 / 62 |
| interruption base / s2 (s) | 1.50 / 1.39 | 1.65 / 1.54 |

Spread: s2 reps are within 0.4 s of each other (52.0–52.1 dog, 53.8–54.1 bfly); the worst rep pairing (slowest s2 vs
fastest base) is 0.779 dog / 0.768 bfly, still ≤ 0.80. Provenance is the same in every s2 rep (± 1 entry).

Reading (descriptive): the gain comes entirely from the window between the first move and the final switch (s2 needs
0.56–0.61 of base there); ≈ 32 s of serving before the first switch is common to all conditions and dilutes the
whole-run ratio, as preregistered. Total bytes rise 5–10 %: M3 forwards 1.8–1.9 GB to holders (including to C and
A) to remove 1.1–1.4 GB from the final base, so this is not a traffic reduction. ctl ≈ base (0.97–0.98): owner lineage
and the entry path cost nothing by themselves; the gain is staging.

Agreement with the invalid first set (section 6, same code): s2 / base 0.774 / 0.762 there vs 0.771 / 0.747 here.

Predictions vs observed: s2 / base 0.76–0.82: dog 0.771 inside, butterfly 0.747 below the range (better); total
1.0–1.15: held; ctl / base 0.95–1.0: held; first-move window 0.45–0.6: dog 0.607 just above, butterfly 0.563 inside;
s2 readiness 7.5–9 s: dog 8.2 inside, butterfly 9.7 above; base / ctl readiness 22–26 s: dog base 21.3 just below,
others inside.

Comparison with M3-S2 (single owner A until the final switch): s2 / base 0.722 / 0.743 there. With an ownership change
the whole-run ratio is 0.771 / 0.747, i.e. holds by the same margins, but is diluted on dog by the common pre-switch
period.

Limitations (declared in the preregistration and still true): one seed, two workloads, faults on dog only, scheduled
moves (A → B at a planned call, then two user moves), one ownership change, 1 Gbps links, no frame comparison.

## 8. Next

M3-S3 is complete. Candidates: a second model (LongLive) for generality; faults on butterfly; more than one ownership
change; seeds.
