# Fig. 10 preregistration: versioned Sink reuse vs version age (M2, RQ4)

**Status: DRAFT 1 (2026-10-31), not frozen. Nothing run, no code changed.** Plan: `osdi/eval_plan/plan.md` (Fig. 10, RQ4,
P1). Open decisions: section 10. Labels: [V] verified in code or earlier records, [H] hypothesis / expectation,
[R] recommendation.

Roles: Fig. 9 = why M1; **Fig. 10 = how much M2 saves, and how that depends on the age of the reused version**;
Fig. 11 = M3 under repeated mobility.

## 1. Questions and messages

RQ4: how effectively does versioned Sink reuse reduce migration costs?

- **10a, bytes.** When the destination still holds an older Sink version, how many Sink bytes must move, as the version
  ages? Message to test: versioned reuse (refreshed entries' current values + ordered shifts) sends far less than a full
  Sink, and less than reusing only the entries whose stored bytes are unchanged, because realignment changes the stored
  bytes of entries whose values M2 can reproduce from shift events.
- **10b, readiness.** Does the byte saving shorten the destination's readiness, and for how long does it keep doing so?

Out of scope: M3 staging (Fig. 11); bandwidth (Fig. 12); output quality beyond the cutover checks (Fig. 13).

## 2. Facts this protocol rests on

| fact | source | tag |
|---|---|---|
| Sink: 180 entries (layer, row, slot), 360 blocks (K, V), one entry = 9,584,640 B; full Sink base 1,727.6 MB. | E9 / E10; Fig. 5 | [V] |
| M2 (frozen 47acbe44): the source retains its Sink version at a digest-equal switch (`--replay_retain`); the new owner tracks, per call, the entries refreshed since that version (set) and the ordered position shifts of the others (`sink_track_step`; a refreshed entry's earlier shifts are dropped, so the two sets are disjoint). A destination advertising that version gets a delta base: the refreshed entries' current K / V, the ordered shifts, metadata and the Sink digest; it rebuilds from its retained copy and checks 360 / 360 blocks + positions (DELTAOK) or falls back to the full base (DELTANO). | `mobility_node.py` `_replay_send_base`, `sink_track_*`, `reuse_base`; E9 / E10 | [V] code |
| The delta covers the calls from the retained version to the second migration's base boundary (round 1); later calls reach the destination as replayed log entries with exact patches (E10). | E10 record | [V] |
| Realignment: `t_refresh = 50` rewinds the stream position every ~45 calls (calls 48-49, 93-94, 138-139, ...); it changes the stored K of most non-refreshed entries (E4: realign-only fragments are dirty). Ordered shifts reproduce them exactly; summed shifts do not (E8). | `streamv2v/inference.py:100,234`; E4, E8 | [V] |
| Readiness (E9 definition): second migration's task start (the trigger) -> the source's `replay_ready` (the destination has replayed W = 12 calls past the base boundary). With M2 it is bounded below by that replay rule (E9: base ready 2.46 s, readiness 8.74 s). | `m2_report.py` `migration` | [V] |
| Fixed switch calls (`--replay_switch_calls s1,s2`) make B's outputs identical between the arms before the second migration (E9: 100 / 100 calls identical), so the arms differ only in the base. | E9 | [V] |
| The run records the refreshed-entry count and the shift-event count, not the number of distinct shifted entries (an entry shifted at two realignments is two events). | `_replay_send_base` `dinfo` | [V] code |

**Numbers seen before this draft (disclosed).** Seed 1, trigger 20, switches 64 / 164, second trigger 120 (age 56 by
the definition of section 3): dog delta base 21.6 MB (2 entries, 73 shifts) vs 1,727.6 MB, total 50.7 vs 1,756.8 MB,
readiness 8.74 vs 22.17 s, interruption 1.41 vs 1.54 s; butterfly delta 357.0 MB (37 entries, 63 shifts), total 922.9
vs 2,293.5 MB (readiness not reported in E10). E8 (offline, 100 calls): butterfly 41 distinct refreshed entries (393 MB),
dog 2. Fig. 5 (20 inputs, snapshot at call 30): refresh-required entries at age 50 median 4.2 %, modified ~47 %.
(An earlier chat message called E9 "age 100"; it was 56.)

## 3. Scenario and conditions

**Path A -> B -> A**, 1 Gbps, Fig. 7 workloads with seed 0 (dog = Low-refresh, butterfly = High-refresh).
- First trigger at call 30 (Fig. 7); first switch planned at **s1 = 74** (44 calls after the trigger, as E9's 20 -> 64;
  Fig. 7's natural switches were at 63-67).
- **Version age a** = second trigger call - s1 (A's retained version is B's Sink at s1). Second trigger at s1 + a,
  second switch planned at s1 + a + 44.
- Ages (D1): **a = 10, 60, 150, 240** calls. Realignments fall at calls 93, 138, 183, 228, 273, 318, i.e. ages 19, 64,
  109, 154, 199, 244 after s1: a = 10 crosses none, 60 one ... (exact count recorded per run).

| arm | flags (both: Fig. 7 OTTER flags with `--replay_switch_calls`, `--move_calls`, `--path A,B,A --allow_return`) | base at the second migration |
|---|---|---|
| **Full** | `--replay_retain` (no `--replay_reuse`; B still tracks, for the counts) | the full Sink (1,727.6 MB) |
| **Versioned (M2)** | `--replay_retain --replay_reuse` | delta from A's retained version (DELTANO -> full) |
| Unchanged-only (computed, not run) | - | (distinct refreshed + distinct shifted entries) x 9,584,640 B + metadata: what reusing every entry whose stored bytes did not change would send, at entry granularity |

Runs: 2 workloads x 4 ages x 2 arms x 3 reps (D3) = **48**; arms and ages interleaved per rep. Estimate [H] ~15 min per
run (the longest age reaches call ~360): ~12 h.

**Instrumentation needed (record only, D2):** one field in `replay_base_sent`, the number of distinct shifted entries
(and the entry lists), so the unchanged-only bytes are exact. Regression before the freeze (section 8).

## 4. Panel 10a: Sink base bytes vs version age

Per run, second migration: base bytes (measured), total migration bytes (base + log incl. patches + switch), delta
entries / shift events / distinct shifted entries, and the unchanged-only bytes (computed).

**F10-H1 (versioned < unchanged-only).** At every age that crosses >= 1 realignment (60, 150, 240), median versioned base
bytes < median unchanged-only bytes, both workloads. Predictions [H]: dog ratio ~0.03-0.1 (few refreshes, many shifts);
butterfly ~0.3-0.6, rising with age. At a = 10 (no realignment) the two are expected to be equal (descriptive).

**F10-H2 (versioned < full).** Median versioned base bytes < 1,727.6 MB at every age, both workloads (no fallback
counted as versioned). Prediction [H]: holds; butterfly at a = 240 the largest share (~0.4-0.7 of full).

## 5. Panel 10b: readiness vs version age

Per run: readiness (section 2), base ready, interruption at the second cutover, DELTAOK / SINKOK, fallbacks.

**F10-H3 (readiness).** median readiness(Versioned) <= 0.6 x median readiness(Full) at every age, both workloads.
Predictions [H]: dog ~0.4 at all ages (bounded by the replay rule); butterfly ~0.45-0.6, rising with age.

**Descriptive.** Interruption (expected equal between arms, ~1.4-1.6 s); B's tracking time per call; A's rebuild
(retained H2D, apply, digest); retained memory (1.73 GB per retaining host); the equivalence check of section 7.

## 6. Statistics

Per cell: median and range over 3 valid reps (3 required, else NOT EVALUABLE); every rep shown. Bytes are expected to be
identical across reps (deterministic generation, fixed switch calls); timing varies.

## 7. Validity and correctness

- Frozen XB validity; one commit on A-D; GPU 0 idle before the set.
- Both switches at their planned calls (`switch_call_missed` false); first migration SINKOK.
- Versioned arm: DELTAOK (360 / 360 blocks, positions equal) at the second base; a DELTANO run is valid but reported as a
  fallback (its bytes are full + the rejected delta) and excluded from the versioned medians only if the fallback is a
  harness defect.
- Second cutover SINKOK in both arms; no readiness timeout.
- Equivalence: B's per-call outputs between s1 and s2 identical between the arms of the same (workload, age, rep)
  (per-call PSNR to every digit, and `ref_match`).

## 8. Procedure and tools (to be written before the freeze)

`tools/eval/run_fig10.sh preflight | first | rest | dry`, `tools/eval/fig10_report.py` (generalized `m2_report.migration`
for any switch calls), `tools/eval/plot_fig10.py`. Regression: `test_xb`, `test_m1_live`, `test_m2_live`,
`test_m2_track_cpu`; dry run of both arms at two ages. First run = dog Versioned a = 60 rep 1 as the sanity check.

## 9. Plot specification

Canvas of Fig. 6a / Fig. 9 (5.83 x 4.78 in, same axes box; OTTER blue, others gray).
- **10a**: x = version age (calls), y = Sink base bytes (MB, log); Full (gray line, constant), Unchanged-only (gray
  dashed, computed), Versioned (blue); one panel per workload or both workloads in one (D5); realignments marked.
- **10b**: x = version age, y = readiness (s); Full vs Versioned, both workloads; points = reps.

## 10. Open decisions (user)

| | question | options | [R] |
|---|---|---|---|
| D1 | ages | 10 / 60 / 150 / 240 (0-5 realignments) / fewer (3) / more | 10 / 60 / 150 / 240 |
| D2 | unchanged-only | computed from the tracked entry sets with one record-only field (exact) / from Fig. 5 data (estimate) / implemented as a live policy (code change) | computed, one field |
| D3 | reps | 3 / 5 (+32 runs, ~8 h) | 3 |
| D4 | rules | F10-H1-H3 as above / H3 descriptive / other thresholds | as above |
| D5 | 10a layout | one panel per workload / both in one panel | one per workload |
| D6 | seed / trigger | seed 0, trigger 30 (Fig. 7) / seed 1, trigger 20 (E9 / E10) | seed 0, trigger 30 |

## 11. What Fig. 10 must not claim

- A total-traffic reduction beyond the second migration's base: the input log and patches are M1 and unchanged by M2.
- Savings without a retained version (first migration), or under a retention budget (Fig. 14).
- That unchanged-only was executed (it is computed from the tracked sets).
- Exactness beyond what DELTAOK / SINKOK verify; behavior beyond two workloads, one return path and 1 Gbps.
