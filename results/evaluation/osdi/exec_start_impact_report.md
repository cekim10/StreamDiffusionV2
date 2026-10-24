# EXEC_START impact report (2026-10-23; for review; no frozen log, result or verdict changed)

Inputs:
- `exec_start_audit.md` / `.json` (`tools/eval/audit_exec_start.py`; per-run evidence and the affected run IDs);
- a code reading of every aggregator, validity rule and check script of the affected experiments, with file:line
  references in the session record;
- the frozen reports' margins (ExpD, W / R / N, V).

Recommended dispositions are in section 5. Nothing is re-run or re-judged until this report is reviewed.

## 1. What EXEC_START is and what went wrong

`EXEC_START` (`mobility_node.cmd_exec_start`) tells the source A, after SOURCE_PREP has run the session to the trigger
call (30), to keep generating. The orchestrator uses it in two frozen paths: the **placement window** (A keeps
generating for L = 10 s while it places fragments; the move happens at t0 + L) and the **cold destination** (A keeps
generating while the destination process boots, ~70 s). The later handoff stops A at a chunk boundary, serializes
its live in-flight / meta state and sends GO with A's current call.

**Cause (read from the code):**
1. After SOURCE_PREP, A's run state is "Sink verified, not bound".
2. On the first loop iteration, `_generate` therefore calls `_unpack_sink` -> `GpuRuntime.unpack` ->
   `unpack_into_snapshot(snap=None)`. A was never provisioned as a receiver, so `snap["kv"]` raises a TypeError in a
   daemon thread.
3. The generation thread ends before A's first chunk.
4. The fake runtime used by loopback tests accepted the unpack, so no dry test caught it. It now refuses, as the GPU
   runtime does.

**Classification:** an **execution-correctness problem**. The protocol step "the source keeps generating" did not run.
It is not a logging error or an aggregation error. Every number in the affected runs was computed correctly from what
actually happened; what happened differs from the specified scenario.

## 2. Affected runs (independent evidence per run)

From three independent records per run:
- the orchestrator's delivered-chunk log has 0 chunks from A after the trigger;
- the relayed node events contain `A:exec_start` but no `A:first_output`;
- the handoff call equals the trigger call (30), although a generating source would have advanced about 18 calls in
  L = 10 s.

| family | runs | role of the data |
|---|---|---|
| ExpD A, OTTER cold destination | 6 | descriptive external group (no G hypothesis) |
| ExpD C (correct placement), D (incorrect placement) | 12 + 12 | G4, G5 |
| ExpD correctness | 7 (6 placement + 1 cold) | correctness checks |
| N cells 1-10 | 90 | N-H1, N-H2, N-H3 |
| V holdout (cells 1-8) and V amendment-1 re-runs (cells 1-3, 8) | 96 + 48 | V-H1 .. V-H4 |
| m3dev, m3dev_r2 | 24 | M3-v2 development (not evidence) |
| d0 / N shakedowns | 6 | harness checks (not evidence) |
| XB before the fix (already voided) | 11 | none |
| **total** | **312** | in all 312, A delivered nothing after the trigger |

Not affected, because these paths do not call EXEC_START:
- Phase 1 single handoff, W1 / W2, R, M3E, WX, VACW, RD, Task A;
- ExpD scenario A's warm runs (OTTER, Full, Cold, M1 only);
- **every XB main run (99 / 99)**, including OTTER's 0.67 s TTFO-local. XB's own pre-copy and recompute sources
  generate correctly after the fix (121 / 121 runs).
- The `restore_*` experiments (118 runs) use a network-only harness without generation, so the question does not
  apply.

## 3. What differs from the specified scenario, and which metrics it reaches

| channel | certain or inferred | affects | does not affect |
|---|---|---|---|
| **No user-visible output during the window** (L = 10 s, or ~70 s cold boot) | certain | any claim that the user was served during placement or cold boot. The cold-destination summary field `source_kept_generating: True` is a hard-coded constant, not a measurement, and is false in all 7 cold-destination runs | none of the G / N / V metrics: they are timed from the move, or from destination-side events |
| **Handoff at call 30 instead of ~48 (placement) or ~155 (cold)** | certain | PSNR-by-call comparisons and rejoin calls / delay at the destination (reported, not judged); the call window available before censoring (about 18 calls more room than intended) | bind-ready time, bytes, re-plans |
| **No chunk-boundary wait at the handoff** (the source was idle) | certain | every latency measured from the move: bind-ready, TTFO, per-move timing. A generating source adds a wait measured at later moves of OTTER runs: median 0.205 s, P90 0.42 s, max 0.64 s | bytes, re-plans, duplicates, version events |
| **Transferred Sink never stale at the handoff** (the source's live Sink equals the trigger snapshot) | certain, consequences inferred | post-bind trajectory. A generating dog source promotes at call 34, inside the window, so the bound snapshot would be one version old; and `owner_promotions_before_final_bind` would be >= 1 (N and V only list it; ExpD prereg section 2(iv) would exclude such runs, but `expD_validity` does not implement that rule) | bind-ready time, bytes |
| **No generation load on A while it sent placement fragments** | inferred, unmeasured | placement throughput during the window, hence `x_verified_at_move`, the G4 threshold, G5 (c) / (d), and the N / V placement set S. Applies only to placement policies other than `none` | cold destination (no fragments flow before its move) |
| **No validity rule checks that the source generated** | certain | - | - |

Independent of the defect (read from the code): post-move source-byte accounting, re-plan decisions (M3's inputs are
post-move), duplicates, version events, NIC / pacing checks, discarded bytes, and the cold destination's boot timings.

## 4. Verdict robustness (old values; the counterfactual values are not computable without new runs)

Bounds use the measured boundary-wait distribution (0-0.64 s). Within an experiment, every compared policy ran under
the same idle-source condition, so between-policy comparisons were made under equal conditions. Their expected shift is
zero, and the worst-case shift is one boundary wait.

| hypothesis | frozen value | worst-case effect of a boundary wait | verdict at risk? |
|---|---|---|---|
| ExpD G4 | Full OTTER bind-ready 4.94 s <= 10.39 s | <= 5.58 s | no (margin 5.45 s) |
| ExpD G5 | NOT SUPPORTED: clause (a) passes by 0.07 s (15.46 vs 15.53); (b)-(d) fail on bytes | (a) could flip | **no** for the verdict (already NOT SUPPORTED through (b)-(d), which are byte clauses); clause (a)'s pass is fragile |
| N-H1 / N-H3 (abs bind difference <= 1.0 s) | differences 0.00-0.53 s in the supported cells (cell 3: 0.53 s) | +-0.64 s worst case | cell 3 fragile in the worst case; others no |
| N-H2, cells 7 / 8 / 10 failures | decided by re-plans, bytes, a 0.5 x ratio | - | no |
| V-H1 / V-H3 (within 1.0 s) | differences 0.02-0.44 s (V8: 0.44 s, 335.29 vs 335.73) | +-0.64 s | V8 fragile in the worst case; others no |
| V-H2 (bind <= 0.5 x at moves) | ratios 0.18-0.27 in V2 / V5; **V4: 19.12 s vs 0.5 x 38.32 = 19.16 s (margin 0.04 s)** | +-0.64 s | **V4 fragile**: a boundary wait on either side can flip it |
| V-H4 (v2 vs v1) | failures in V4 / V5 at +4.1 s | +-0.64 s | no |
| Sink staleness and placement contention | not measured | unknown | **unknown**: these are the channels a re-run would test |

## 5. Recommended dispositions (for review)

| family | recommendation | why |
|---|---|---|
| XB main (99 runs) | **retain** | not on the affected path; sources verified generating |
| XB voided (11) | already invalidated | `expXB/void_runs.md` |
| ExpD A cold destination (6) | **retain the numbers, correct the description**: "the source was idle during the destination's boot". Remove any claim that the user was served meanwhile. Optional re-run (6 runs) if the paper needs that claim | descriptive group; boot timings unaffected |
| ExpD C / D (24), G4 / G5 | **retain verdicts with a stated limitation**: the placement window ran with an idle source. **Recommend a small replication with the fixed code** (C and D, 3 reps x 2 policies x 2 = 24 runs, ~2 h) as a separate robustness experiment, not overwriting the frozen runs | it tests the two unmeasured channels (staleness, contention) on the experiment whose claims most depend on placement during live generation |
| N (90), V (144) | **retain verdicts; document** the idle-source window and the missing boundary wait (absolute latencies optimistic by <= 0.64 s; comparisons made under equal conditions). Mark three verdicts as fragile to it: V-H2 in V4 (margin 0.04 s), V-H3 in V8 and N-H3 in cell 3 (worst case only) | no verdict flips on expected values. A fragile verdict is cited with its margin, or confirmed by the replication below if the paper relies on it |
| ExpD correctness (7) | **retain; document** that its checks never exercised a generating source during the window | - |
| m3dev, shakedowns (30) | no action | not evidence |

For any future run on these paths, both frozen call sites should pass `source_bound=True` (the XB fix), and a
validity rule should require that the source generated until the handoff. These changes apply to new experiments only,
because the frozen runs stay as recorded.

## 6. Related design property found during the audit (not the bug)

A handoff waits for the generating owner to finish its current chunk. At the **first** move of every OTTER-style run,
the source has just finished SOURCE_PREP and is idle at a boundary, so the wait is ~0: median 0.002 s over 892 first
moves. At later moves it is median 0.205 s, P90 0.42 s, max 0.64 s, over 924 moves.

Hence every single-move OTTER TTFO, including XB1's 0.67 s, Phase 1's and W2's, excludes the boundary wait, while
OTTER's later-move values (XB3 / XB4: 0.83-0.85 s) include it. Adding the maximum wait does not change XH1a: OTTER at
most 1.31 s vs R-full 36.7 s, a ratio of 0.036 against a threshold of 0.25. The paper should state that single-move
TTFO is measured from a chunk boundary, and report the later-move values next to it.
