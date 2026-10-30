# M3-S2 report: lineage-aware forwarding and mixed-version Sink reconstruction on GPU

Preregistration: `preregistration.md` (frozen 5bcb05b0; Note 1 at 7d438875, before any data). Judged by
`tools/eval/m3s2_report.py` as written; output `m3s2_results.json`. All numbers below are **measured** on the testbed
(elves-01..04, L40S, 1 Gbps caps, rho 1) unless labelled predicted. One run per configuration in A, B, C.

## 0. Status (2026-10-29)

| phase | rule | dog | butterfly | verdict |
|---|---|---|---|---|
| A0 offline exactness | E, S all exact; N all detected | pass | pass | **pass** |
| A end-to-end exactness | m3 base accepted, 0 mismatches, positions, cond, B's state reused | pass | pass | **pass** |
| C live migration | one verified switch to D, SINKOK, replay checks, no refused switch | pass | pass | **pass** |
| B faults (dog) | advertise_wrong / corrupt_held / holder_fail handled and safe | 3 / 3 | — | **pass** |
| D performance (3 reps, medians) | R-D1: s2 remote ≤ 0.80, total ≤ 1.30 x base | 0.722 / 1.017 | 0.743 / 0.954 | **holds** |
| | R-D2: s2 remote ≤ 0.85 x ctl | 0.736 | 0.773 | **holds** |

Report verdict: **SUPPORTED** — exact, fault-safe and live; remote serving ≤ 0.80 and total bytes ≤ 1.30 of the frozen
M1 / M2 baseline on both workloads (18 / 18 Phase D runs valid).

## 1. Phase A0: offline mixed-version exactness (GPU 0 of elves-01, commit 7d438875)

Versions 30, 43, 56, 68, 81, 100, 120; targets 56, 81, 100, 120, 140; 180 entries (30 layers x 2 rows x 3 slots).

| check | dog | butterfly |
|---|---|---|
| E: lineage-valid (version, target) entries, bitwise equal after ordered shifts | 4,281 / 4,281 | 3,594 / 3,594 |
| E: refreshed entries, content changed (rule correctly says invalid) | 39 / 39 | 726 / 726 |
| S: assembled Sinks with 0 of 360 block mismatches (single 24, mixed 25, M3-S1 shape 5) | 54 / 54 | 54 / 54 |
| S: most versions in one assembled Sink | 8 | 8 |
| N: reused without its shifts, detected | 1,537 / 1,537 | 1,389 / 1,389 |
| N: one stale entry in a Sink, detected (exactly its K and V block named) | 5 / 5 | 5 / 5 |
| summed shift bitwise equal to ordered shifts (informative) | 57 % | 61 % |

The one failure mode predicted (a refresh that leaves the position unchanged) did not occur. Ordered shifts remain
necessary: a summed shift is not bitwise for about 40 % of shifted entries.

## 2. Phases A and C: end-to-end A -> B -> C -> D (S2 staging, order fwd)

What happened, in both workloads (dog numbers; butterfly in the table):

1. A's base to B (c0 = 32) was cancelled by the move at 14 s; B had verified 140 entries of version 32.
2. The S2 planner at that move forwarded B's 139 lineage-valid entries to D (B -> D, 1.33 GB, 10.8 s). D verified
   each entry against the source-issued SHA-256 on receipt.
3. A's base to C (c0 = 53) was cancelled at 28 s. C's partial base is never used for D (as in Corrected M3-S1).
4. At the move to D, D advertised 139 entries of version 32; the source accepted 138 (1 refreshed since 32) and sent
   42 fresh entries of version 75. D assembled 138 entries of v32 + 42 of v75 with 58 ordered shift ops.
5. All 360 blocks, positions and conditioning equal; DELTAOK; switch at call 88 with SINKOK (0 mismatches).

| | dog | butterfly |
|---|---|---|
| valid (frozen XB validity) | yes | yes |
| entries of B's abandoned version (32) in D's final Sink | **138** | **95** |
| fresh entries from the source (version) | 42 (v75) | 85 (v74) |
| shift ops at D | 58 | 40 |
| block mismatches / positions / conditioning | 0 / equal / equal | 0 / equal / equal |
| SINKOK at switch (call) | yes (88) | yes (93) |
| final base bytes | 405 MB | 817 MB |
| D assembly total (H2D / shifts / digest) | 0.50 s (0.19 / 0.006 / 0.064) | 0.49 s (0.18 / 0.004 / 0.064) |
| framing headers / entry bytes, final base | 14.8 KB / 403 MB (0.004 %) | 29.9 KB / 815 MB (0.004 %) |
| remote serving | 36.4 s | 39.6 s |
| readiness / first output / interruption (diagnostic) | 8.1 / 10.0 / 1.43 s | 12.1 / 13.9 / 1.51 s |

This is the requested demonstration: B's verified partial state reaches D and combines bitwise with the source's
latest delta, inside a live migration that switches with SINKOK.

**Against the predictions** (written before the runs):
- dog matched: 138 reused (predicted ≈ 137), 405 MB (≈ 405), readiness 8.1 s (≈ 8.1), D-side cost < 0.5 s.
- butterfly reused **95, not ≈ 108**, and the final base is 817 MB, not ≈ 692 MB. B held only 121 entries when its
  base was cancelled (butterfly's log patches share A's link: 248 MB vs 18 MB for dog), 107 of them were valid at the
  move to D, and 12 more were refreshed before c0 = 74. Readiness 12.1 s (predicted ≈ 12.6).
- framing overhead 0.004 % (predicted < 0.1 %).

**Continuity** is a diagnostic only. The frame comparison with a fresh-base run was not done; the A/C frames are on
the testbed in `/home/ckim151/m3s2_frames/A_{dog,bfly}`.

## 3. Phase B: faults (dog)

| fault | injected | detected by | outcome | final mode | SINKOK | remote |
|---|---|---|---|---|---|---|
| advertise_wrong | D advertised entries 0, 1, 2 as v33 (held v32) | source: hash not issued for (e, 33) | 3 not reused (`not_issued` 3), re-sent; 137 reused | m3, accepted | yes (88) | 36.4 s |
| corrupt_held | byte 0 of held entry 0 flipped at assembly | D: 360-block check | rejected, exactly block (layer 0, K, row 0, slot 0) named; DELTANO; frozen full-base fallback | full | yes (118) | 55.5 s |
| holder_fail | B's forward stops mid-entry after 40 entries | D: short read | entry 41 recorded lost, not advertised, no wait; 39 reused, 141 sent | m3, accepted | yes (103) | 45.3 s |

Each fault cost time, not correctness: corrupt_held pays one full base (+19 s remote vs the A run), holder_fail
loses most of the reuse (+9 s).

## 4. Observations for Phase D (not rules)

- [V] On the live source, per-entry D2H averages ≈ 82 ms (dog final base: 3.46 s for 42 entries); offline (A0) the
  first entry took 1.4 ms. Per-entry send time is ≈ 91 ms, about 84 % of the 1 Gbps line rate.
- [H] The live D2H waits behind generation kernels on the same GPU and may pace the entry path near the link rate.
  Phase D's ctl vs base comparison measures this effect; nothing is changed before D. **Resolved by D:** ctl is not
  slower than base (remote 0.98 / 0.96 x base, readiness equal within 0.4 s), so the entry path costs nothing at 1 Gbps.
- [V] At the move to D the S2 planner also stages C's entries to B (9 entries, 86 MB in dog). This is pre-ownership
  staging for a possible next move and counts in total bytes.

## 5. Phase D: performance (2 workloads x {base, ctl, s2} x 3 reps, all 18 valid)

Conditions: **base** = frozen M1 / M2 path (4 MiB fragments, full base); **ctl** = M3 entry path with no staging (full
base as 180 entries); **s2** = M3 entry path with S2 staging. Medians of 3 reps.

| | dog base | dog ctl | dog s2 | bfly base | bfly ctl | bfly s2 |
|---|---|---|---|---|---|---|
| remote serving (s) | 50.8 | 49.9 | **36.7** | 55.5 | 53.3 | **41.2** |
| final base (MB) | 1,728 | 1,728 | 405 | 1,728 | 1,728 | 855 |
| entries reused at D | 0 | 0 | 138 | 0 | 0 | 91 |
| forwarded holder -> holder (MB) | 0 | 0 | 1,419 | 0 | 0 | 1,073 |
| discarded cancelled bases + logs (MB) | 2,812 | 2,830 | 2,791 | 2,966 | 2,868 | 2,849 |
| total bytes (MB) | 4,572 | 4,591 | 4,649 | 5,216 | 5,081 | 4,977 |
| readiness at D (s) | 21.9 | 22.1 | **8.3** | 25.6 | 25.2 | **12.9** |
| interruption (s, diagnostic) | 1.55 | 1.42 | 1.43 | 1.61 | 1.48 | 1.59 |

| ratio (medians) | dog | bfly | rule |
|---|---|---|---|
| s2 / base remote | **0.722** | **0.743** | ≤ 0.80 (R-D1) |
| s2 / base total bytes | **1.017** | **0.954** | ≤ 1.30 (R-D1) |
| s2 / ctl remote | **0.736** | **0.773** | ≤ 0.85 (R-D2) |
| ctl / base remote (entry path's own effect) | 0.982 | 0.961 | reported |
| framing headers / entry bytes | 0.0036 % | 0.0029 % | reported |

Decomposition: the whole gain is the final base. S2 moves B's abandoned entries to D before the move (1.07–1.42 GB
off the critical path), so the source sends 405 / 855 MB instead of 1,728 MB and readiness drops by 13.6 / 12.7 s.
Total bytes stay about equal because the forwarded bytes replace the final-base bytes they save. The entry path alone
(ctl) is not slower than the frozen path, so R-D2 attributes the gain to forwarding, not to framing.

Spread across reps (informative, not a rule):
- dog is tight (s2 remote 36.2–36.8 s, base 50.5–50.9 s); every s2 rep / every base rep ≤ 0.729.
- butterfly has one fast base rep (51.4 s vs 55.5 / 55.9 s; c0 75 vs 76 / 77). The worst pairing, slowest s2 rep vs
  that base rep, is 0.803, just above 0.80. The rule is on medians and holds; this pairing shows the butterfly margin
  is small.
- reuse per rep: dog 137–139, butterfly 91–93.

Against the predictions (written before the runs):
- s2 / base remote predicted 0.73–0.78: dog 0.722 just below the range, butterfly 0.743 inside.
- total predicted 1.0–1.05 x base: dog 1.017 inside, butterfly 0.954 below. Butterfly's base condition discards more
  log bytes in this sample.
- ctl predicted up to ≈ 2 s faster than base: dog 0.9 s, butterfly 2.2 s faster (median).
- framing < 0.1 %: 0.003–0.004 %.
- GPU vs the network-level M3-S1 Corrected result (S2 / S0 remote 0.734 / 0.781): 0.722 / 0.743. The GPU path
  reproduces the network result and is slightly better on butterfly.

## 6. Conclusion

[V] On GPUs, OTTER assembles an exact Sink at the destination from partial, differently versioned entries held on
another GPU plus the source's latest delta: 360 / 360 blocks bitwise equal, SINKOK at the switch, under live
generation. Wrong advertisements, corrupted held entries and holder failure are caught and fall back safely. With S2
staging, remote serving is 0.72 / 0.74 x the frozen M1 / M2 path at about equal total bytes.

Limitations (as declared, plus one observed):
- The source A owns the session until the final switch; lineage after an ownership change is not exercised.
- One seed per workload, two workloads, rho 1, 1 Gbps caps, static forward rates, 3 reps in D, 1 run per A/B/C cell.
- Faults were tested on dog only. Frame-level continuity against a fresh-base run was not measured.
- Butterfly's R-D1 margin is small at the rep level (worst pairing 0.803).
