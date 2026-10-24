# EXEC_START disposition (approved 2026-10-24)

Decision of 2026-10-24 on `exec_start_impact_report.md`. No frozen raw log, result or verdict is modified. This
document records the root cause, the affected runs and metrics, the evidence behind retaining the N / V verdicts,
the exact code changes, and the approved ExpD C / D reproduction.

## 1. Root cause (code, read; confirmed by the data of every affected run)

`EXEC_START` (`tools/eval/mobility_node.py`, `cmd_exec_start`) starts the source's generation thread after
SOURCE_PREP. The run state after SOURCE_PREP says "Sink verified, not bound", so the thread's first iteration tried to
unpack and bind the source's own Sink: `_unpack_sink` -> `GpuRuntime.unpack` -> `unpack_into_snapshot(snap=None)`.
The source has no receive snapshot, so the call raised in a daemon thread and the thread ended before the first chunk.
The fake runtime used by every loopback test accepted the unpack, which is why no dry test caught it.

**Classification: execution-correctness defect.** The protocol step "the source keeps generating during the window"
did not run. Timestamps and aggregation were correct for what ran; what ran differs from the specified scenario.

## 2. Affected runs and what is affected

312 frozen GPU runs on the two paths that call EXEC_START; the source delivered 0 chunks after the trigger in every
one (orchestrator metrics log), `A:exec_start` present and `A:first_output` absent (events log), move call equal to
the trigger call (`exec_start_audit.md`).

| family | runs | original commit | role |
|---|---|---|---|
| ExpD A cold destination | 6 | 656dde6 | descriptive external group |
| ExpD C / D | 24 | 656dde6 | G4, G5 |
| ExpD correctness | 7 | 4b68622 | checks |
| N cells 1-10 | 90 | ca7c951 | N-H1..H3 |
| V holdout; V amendment-1 re-runs | 96; 48 | 91faa0a; f731bd9 | V-H1..H4 |
| m3dev, shakedowns | 30 | 0613e0f and others | not evidence |
| XB (voided) | 11 | before 0b034dd | none |

Not affected: every path without EXEC_START (Phase 1, W1 / W2, R, M3E, WX, VACW, RD, Task A, ExpD scenario A's warm
runs, XB main 99 / 99 and OTTER's 0.67 s TTFO-local); the `restore_*` network-only experiments.

What differs from the specified scenario (certain): no user-visible output during the window; the handoff at call
30 rather than ~48 (placement) / ~155 (cold); no chunk-boundary wait at the handoff (a generating source adds median
0.205 s, P90 0.42 s, max 0.64 s); the transferred Sink never stale. What might differ (unmeasured): the post-bind
trajectory under a stale Sink; placement throughput under generation load on the source.

## 3. N and V: verdicts retained (decision), with the evidence

- Every N / V metric is timed from the move or measured after it (bind-ready, bytes, re-plans, duplicates, version
  events). None reads the source's chunks during the window.
- Every compared policy within a cell ran under the same idle-source condition, so the comparisons that decide
  N-H1..H3 and V-H1..H4 were made under equal conditions; the defect shifts absolute latencies, not their differences
  in expectation.
- The only measurable shift is the missing chunk-boundary wait, at most 0.64 s per handoff. Applied as a worst case to
  every 1.0 s band and 0.5 x ratio, it flips no verdict on expected values. Three verdicts are **fragile** to it and are
  cited with their margins: V-H2 in V4 (19.12 s vs the 19.16 s bound, margin 0.04 s), V-H3 in V8 (0.44 s of 1.0 s),
  N-H3 in cell 3 (0.53 s of 1.0 s).
- The paper states, where these results are used, that the placement window ran with an idle source, that absolute
  latencies on these paths are optimistic by up to 0.64 s, and that the three fragile verdicts are fragile.
- The cold-destination summary field `source_kept_generating` was a hard-coded constant (True); it is false in all 7
  cold-destination runs. Any text claiming that the user was served during the destination's boot is removed. The
  boot timings (destination side) stand.

## 4. ExpD C / D reproduction (approved; `run_expD_sweep.py --repro`)

- Same configurations as the frozen runs (`--pp_configs split:none,split:top1,reuse_dyn:top1,reuse_dyn:oracle`,
  path A,B for C and A,C for D, lookahead 10 s, budget 1, 1 Gbps, trigger chunk 30, post_chunks 300, 3 reps), with
  the corrected code; results under `expDR_C` and `expDR_D`; the frozen `expD_C` / `expD_D` untouched.
- The reproduction needs GPU 0 on all four hosts (placement candidates B, C, D), so it runs only when VD-2 is not
  using host D.
- Checks (`compare_expD_repro.py`): the source delivers chunks before the move (count recorded per run), the move
  call advances past the trigger, the event order A:exec_start < A:first_output < move < A:exec_stop holds, the
  chunk-boundary wait is recorded; the frozen expD validity rules are applied unchanged; G4 / G5 are judged on the
  reproduction by `aggregate_expD.py --prefix expDR`; original and reproduced latency, bytes, x, validity and verdicts
  are compared side by side, and any changed conclusion is stated explicitly.
- Which set the paper cites is decided after the reproduction report is reviewed.

## 5. Code changes (reproducibility record)

| commit | file | change |
|---|---|---|
| 0b034dd (2026-10-22) | `tools/eval/mobility_node.py` `cmd_exec_start` | new optional `source_bound` flag: when set, the run state is marked bound and Sink-unpacked before the generation thread starts (the source's live Sink is its own). Without the flag the behavior is unchanged. Also: the fake runtime refuses `unpack` without provisioned buffers, as the GPU runtime does |
| 0b034dd | `tools/eval/mobility_orchestrate.py` `execute_xb` | XB passes `source_bound=True` |
| this commit | `tools/eval/mobility_orchestrate.py` placement-window and cold-destination call sites | both pass `source_bound=True` (the two lines shown in the commit diff); the cold-destination field `source_kept_generating` is now measured, and `validation.source_chunks_before_move` is recorded for every run. Frozen validity rules (`expD_validity.py`, `wrn_validity.py`) are not changed |
| this commit | `tools/eval/run_expD_sweep.py` | `--repro`: scenarios C and D under the `expDR` prefix, same arguments |
| this commit | `tools/eval/compare_expD_repro.py` | the comparison report |

No mechanism code (M1 / M2 / M3-v2, `tools/proto_handoff.py`, `tools/state_ablation.py`, `models/`) and no
experiment configuration is changed by these commits beyond the flag at the two call sites.
