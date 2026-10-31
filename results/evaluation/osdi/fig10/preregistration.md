# Fig. 10 preregistration: versioned Sink reuse vs version age (M2, RQ4)

**Status: FROZEN (2026-10-31), before any Fig. 10 run.** DRAFT 1 was 89aab33b; the user's review (2026-10-31) is applied:
changed-block baseline, fallbacks inside the Versioned results, H3 relaxed, both workloads in one panel, refreshed-entry
annotations, a preregistered extra-rep rule. Plan: `osdi/eval_plan/plan.md` (Fig. 10, RQ4, P1). Decisions: section 10. Labels: [V] verified in code or earlier records, [H] hypothesis / expectation,
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
| A shift re-rotates only the entry's **K** block (`reuse_base`: `_shift_temporal_rope` on `k`); V is untouched. A refresh rewrites K and V. So the bytes that differ from the retained version are, per entry: K + V if refreshed, K only if shifted. | `mobility_node.py` `reuse_base` | [V] code |
| The destination already holds both 360-block checksum sets at the delta check: the retained version's (computed by the source at the first switch for the Sink digest) and the source's at the base boundary (`sink_ck` in the delta's PROUND). | `_precopy`, `_replay_base_delta` | [V] code |

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
| **Changed-block** (computed, not run) | - | (blocks whose bytes differ from the retained version) x 4,792,320 B + the delta's metadata: what reusing every unchanged K / V block would send. **The baseline of F10-H1** (the stronger one: a shifted entry costs its K block only). Measured block set, computed bytes |
| Unchanged-only, entry granularity (computed, not run) | - | (distinct refreshed + distinct shifted entries) x 9,584,640 B + the same metadata; reported in the table, not tested |

Runs: 2 workloads x 4 ages x 2 arms x 3 reps (D3) = **48**; arms and ages interleaved per rep. Estimate [H] ~15 min per
run (the longest age reaches call ~360): ~12 h.

**Instrumentation (record only, D2; no behavioral change, no extra GPU work, no protocol change):**
- A keeps the retained version's 360 block checksums (already computed at the first switch) with its retained copy;
- `replay_delta_base` (A) records `changed_vs_retained`: the number of blocks (K / V) whose checksum differs between the
  retained version and the source's Sink at the base boundary;
- `replay_base_sent` (B) records `distinct_shifted_entries`.
The changed-block bytes come from the Versioned run of the same (workload, age, rep); B's state is identical in the Full
run (section 7). Run settings: `--post_chunks 500` (reference covers the longest run, call ~458), `--xb_horizon 100`.

## 4. Panel 10a: Sink base bytes vs version age

Per run, second migration: base bytes (measured), total migration bytes (base + log incl. patches + switch), delta
entries / shift events / distinct shifted entries, and the unchanged-only bytes (computed).

**F10-H1 (versioned < changed-block).** At every age that crosses >= 1 realignment (60, 150, 240), median Versioned
base bytes < median changed-block bytes, both workloads. Predictions [H]: dog ratio ~0.05-0.2 (few refreshes, many
shifted K blocks); butterfly ~0.5-0.8, rising with age. At a = 10 (no realignment) the two are expected to be about equal
(descriptive). The refreshed-entry count per age is reported and annotated in the figure, so growth with age can be
read as growth of refreshes vs shifts.

**F10-H2 (versioned < full).** Median Versioned base bytes < median Full base bytes (1,727.6 MB) at every age, both
workloads. **DELTANO fallbacks stay in the Versioned results** with their actual bytes (rejected delta + full base) and
readiness; a run is set aside only if a harness defect is found (then the Fig. 7 precedent: fix, rerun, keep both).
Prediction [H]: holds; butterfly at a = 240 the largest share (~0.4-0.7 of full).

## 5. Panel 10b: readiness vs version age

Per run: readiness (section 2), base ready, interruption at the second cutover, DELTAOK / SINKOK, fallbacks.

**F10-H3 (readiness, user: relaxed).** median readiness(Versioned) < median readiness(Full) at every age, both workloads;
the ratio is reported per age, not thresholded. Readiness includes the base transfer, the rebuild, the replay of 12 calls
and the catch-up, so it shrinks less than the bytes. Predictions [H]: dog ratio ~0.4 at all ages (bounded by the replay
rule); butterfly ~0.45-0.7, rising with age. Base ready is recorded; Fig. 10b shows end-to-end readiness only.

**Descriptive.** Interruption (expected equal between arms, ~1.4-1.6 s); B's tracking time per call; A's rebuild
(retained H2D, apply, digest); retained memory (1.73 GB per retaining host); the equivalence check of section 7.

## 6. Statistics

Per cell: median and range over 3 valid reps (3 required, else NOT EVALUABLE); every rep shown. Bytes are expected to be
identical across reps (deterministic generation, fixed switch calls); timing varies.

**Extra-rep rule (fixed now, user).** After the 48 runs, a (workload, age) cell whose readiness ranges overlap between the
arms (max Versioned >= min Full) gets 2 more reps of both arms (`run_fig10.sh extra <w> <age>`); its H3 pair is then
judged on the 5 reps. No other cell is extended, and nothing is extended for bytes.

## 7. Validity and correctness

- Frozen XB validity; one commit on A-D; GPU 0 idle before the set.
- Both switches at their planned calls (`switch_call_missed` false); first migration SINKOK.
- Versioned arm: DELTAOK (360 / 360 blocks, positions equal) at the second base. A DELTANO run is valid, counted in the
  Versioned results with its real bytes and readiness, and listed as a fallback (an M2 failure is a result, not an
  exclusion). Age 240 (5 realignments) is the longest ordered-shift reconstruction verified so far (E8: 2).
- Second cutover SINKOK in both arms; no readiness timeout.
- Equivalence: B's per-call outputs between s1 and s2 identical between the arms of the same (workload, age, rep)
  (per-call PSNR to every digit, and `ref_match`).

## 8. Procedure and tools

Tools: `tools/eval/run_fig10.sh preflight | first | rest | extra <w> <age> | dry`, `tools/eval/fig10_report.py`
(`--sanity`), `tools/eval/plot_fig10.py`; instrumentation in `mobility_node.py` (section 3).

1. Regression and dry run, then this freeze is committed with the tools. Done (sequentially, with the instrumentation):
   `test_xb` ALL PASS (87), `test_m1_live` ALL PASS (50), `test_m2_live` ALL PASS (45), `test_m2_track_cpu` ALL PASS;
   `run_fig10.sh dry` rc 0: dog and butterfly x ages 10 / 60 x both arms, 8 / 8 valid, both switches at their planned
   calls, first and second cutover SINKOK, Versioned DELTAOK (0 mismatching blocks), `changed_vs_retained` and
   `distinct_shifted_entries` recorded; report and figures produced (dry: arm equivalence not applied, PSNR is random).
2. elves-01: `d0_remote.py pull` on all hosts, `run_fig10.sh preflight`.
3. `run_fig10.sh first` (dog, age 60, Versioned, rep 1) + `fig10_report.py --sanity`; counted if it meets section 7.
4. `run_fig10.sh rest` (47 runs; reps outermost, then ages, workloads, arms).
5. `fig10_report.py`; the extra-rep rule (section 6) if listed; `plot_fig10.py`.

## 9. Plot specification

Canvas of Fig. 6a / Fig. 9 (5.83 x 4.78 in, same axes box; OTTER blue, others gray).
- **10a (Sink transfer vs version age)**: x = version age (calls), y = Sink base transferred (MB, log); both workloads
  in one panel (D5). Method by color and line style, following Figs. 7-9 (Versioned blue solid, Changed-block gray
  dashed, Full light gray solid; Full is one line, identical for both workloads); workload by marker (Low-refresh filled
  circle, High-refresh open triangle); the refreshed-entry count annotated at each Versioned point; realignment ages as
  faint vertical lines. Caption: "Changed-block is computed from the measured block sets, not executed." If the panel is
  unreadable, one panel per workload.
- **10b (readiness vs version age)**: x = version age, y = destination readiness (s); Full vs Versioned, both
  workloads (same encoding); line = median, points = reps.

## 10. Decisions (user, 2026-10-31)

| | decision |
|---|---|
| D1 | ages 10 / 60 / 150 / 240 |
| D2 | record-only fields; changed-block (K / V block granularity) as the tested baseline, entry-level unchanged-only reported |
| D3 | 3 reps, plus the preregistered extra-rep rule (section 6) |
| D4 | H1 / H2 kept (H1 against changed-block), H3 relaxed to Versioned < Full with ratios reported |
| D5 | both workloads in one panel (encoding in section 9: method by color as in Figs. 7-9, workload by marker) |
| D6 | seed 0, trigger 30 (Fig. 7) |

## 11. What Fig. 10 must not claim

- A total-traffic reduction beyond the second migration's base: the input log and patches are M1 and unchanged by M2.
- Savings without a retained version (first migration), or under a retention budget (Fig. 14).
- That changed-block or unchanged-only was executed (both are computed from measured sets).
- A readiness reduction of a fixed size: only Versioned < Full is tested; ratios are measured.
- Exactness beyond what DELTAOK / SINKOK verify; behavior beyond two workloads, one return path and 1 Gbps.
