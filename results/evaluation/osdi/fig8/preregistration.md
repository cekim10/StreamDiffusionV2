# Fig. 8 preregistration: streaming continuity and native performance (RQ1-2)

**Status: DRAFT 1 (2026-10-30). Not frozen. Nothing run.** Open decisions D1-D5 (section 10) must be settled before
the freeze. Plan: `osdi/eval_plan/plan.md` (Fig. 8: a cumulative delivered frames vs wall time with the migration
marked; b steady-state FPS, native vs OTTER tracking on, no migration, + during staging if possible). Fig. 7 (frozen
00f2dd92, complete e1ba1940) is the source of the migration runs.

## 1. Objective and scope

Fig. 7 reports one number per run for the stall (the longest gap). Fig. 8 asks two different questions:

- **8a, continuity.** Over the whole migration, how much of the output stream does each method lose, and when? A
  method can have a short longest gap but several stalls (P-full's snapshot stalls, OTTER's snapshot stall plus its
  cutover).
- **8b, native performance.** Does OTTER slow down StreamDiffusionV2 when no migration is running, and after a
  migration while it tracks Sink versions (M2) and lineage (M3)?

Out of scope: WAN latency during remote serving (network / mobility evaluation, user 2026-10-30); throughput during
transfer and staging and all memory overhead (Fig. 14, see D4); quality (Fig. 13).

## 2. Facts this protocol rests on

| fact | source | tag |
|---|---|---|
| Before the first migration no OTTER code runs per call: the M1 replay log runs only inside a migration task, M2 tracking starts at the new owner after SINKOK (`sink_track_start`), M3 lineage only after M3_TRACK, `--sink_fp` is off. An idle OTTER node runs the same per-call path as a node without OTTER flags. | `mobility_node.py` `_generate`, lines ~2610, 3205-3260 | [V] code |
| In the Fig. 7 OTTER runs, B tracks the retained version after the switch (`tracking_version: true`). R-full and Full do no tracking. | Fig. 7 events | [V] |
| The harness generates through upstream `SingleGPUInferencePipeline.run_stream_batch` (`streamv2v/inference.py`): VAE encode, `inference_stream`, decode, the same steps as upstream `run_inference`. Upstream's own FPS = frames per chunk / per-chunk wall time (`--profile`). | `state_ablation.Runner.step`, `streamv2v/inference.py:296-409` | [V] code |
| Node A of every Fig. 7 run first generates an uninterrupted reference session of 1,530 calls and records each call's CUDA-synchronized generation time (`baseline_record.json`, `service_s`). Nothing migrates during it. | Fig. 7 runs (40 records) | [V] |
| Per call, `chunk_s` = generation time (CUDA-synchronized, excludes the harness's PSNR, metrics and tracking); `t_out` = output time, so the call period includes everything in the loop (tracking, snapshot requests). | `mobility_node.py` `step`, `_generate` | [V] code |
| Fig. 7 runs end at different times after the trigger: OTTER 83-87 s, R-full 97 s, Full 132 s, P-full 274-304 s (`--horizon_calls 130` counts the final owner's calls). | Fig. 7 metrics | [V] |
| Fig. 7 runs record `git_commit.txt` as `00f2dd92 (dirty)`; earlier frozen runs show the same marker. Before the freeze, check that the marker is untracked result files, not tracked code changes. | run dirs | [V] marker, cause unchecked |

**Numbers seen while drafting (disclosed; any rule that uses them is not blind).** B's median call period after the
switch, Fig. 7 runs (calls switch + 10 to the end): dog Full 0.597 s, P-full 0.601, R-full 0.605, OTTER 0.603;
butterfly 0.598, 0.601, 0.604, 0.604. A's median call period while it serves: P-full 0.611 / 0.610, R-full
0.610 / 0.611, OTTER 0.616 / 0.624. OTTER's and P-full's stall components (1.56-1.65 s start stall; P-full later
snapshot stalls 2.3-2.5 s) were found in the Fig. 7 analysis. The first `service_s` values of one baseline record
(0.54-0.55 s) were seen. No N1 measurement and no M3 run exists.

## 3. Panel a: continuity (re-analysis of the 40 Fig. 7 runs, no new runs)

**Data.** The Fig. 7 delivery log (`xb_delivery.load_run`, the same log as TTFO-local and the gap): every chunk
delivered to the user from any host, A (remote) or B (local), with its time since the trigger.

**Metrics (per run).**
- **Reference period** T_ref: the run's median delivery interval over all delivered chunks after the trigger.
- **Stall**: a delivery interval longer than 1.5 x T_ref. Its excess is (interval - T_ref).
- **Cumulative stall time** S(t): sum of stall excesses up to time t since the trigger. **Total stall** = S at the
  run's last delivered chunk.
- **Frames behind** F(t) = 4 x S(t) / T_ref: output frames the user has not received at time t, relative to an
  uninterrupted stream at the same cadence (4 frames per call). The harness resumes at the next call and never drops
  input chunks, so a stall delays the rest of the stream; it does not skip frames [V: resume at stop call + 1].
- **Number of stalls** and the time of each.

Interval jitter below 1.5 x T_ref is not counted, so S does not drift with run length. Every curve ends at its run's
last delivered chunk; nothing is extrapolated.

**F8-H3 (total stall, medians, each workload).** median total stall(OTTER) <= 0.25 x min over Full, P-full, R-full of
median total stall. Not blind: the stall components are known from Fig. 7 (section 2). It summarizes all stalls, where
Fig. 7's H1 used only the longest one. Predictions [H]: OTTER ~2 s (start stall ~1 s + cutover ~1 s excess), R-full
~18 s, Full ~54 s, P-full ~52-58 s.

## 4. Panel b: steady-state throughput

**Conditions.**

| id | condition | host | data |
|---|---|---|---|
| N1 | **native StreamDiffusionV2**: upstream `streamv2v/inference.py --profile`, unmodified, same model configuration and input, no harness | A and B | **new** |
| N2 | **OTTER idle** = harness node, no migration (code path identical to a node without OTTER flags, section 2) | A | existing: Fig. 7 `baseline_record.json` `service_s` (calls 30-159, all 40 runs) |
| T2 | **OTTER tracking, M2**: new owner B after the cutover, version tracking on | B | existing: Fig. 7 OTTER runs |
| T3 | **OTTER tracking, M2 + M3**: as T2 with M3 lineage (`--m3 --m3_owner`, M3-S3 flags) | B | **new** (see D3) |
| C | **control**: new owner B after an R-full resume, no tracking, same host, same calls | B | existing: Fig. 7 R-full runs |

**Metrics.** Generation throughput = 4 / median `chunk_s` (frames/s); delivered throughput = 4 / median call period.
Steady-state window: B from switch + 10 calls to the run's end; N2 calls 30-159; N1 the same chunk range (upstream
skips its warm-up the same way, `processed_offset`).

**F8-H1 (OTTER idle vs native).** median generation time per call, N2 <= 1.03 x N1 on host A, each workload.
**F8-H2 (tracking overhead, new runs only).** median call period, T3 <= 1.03 x C on host B, each workload.
**Descriptive.** T2 vs C (already seen, section 2); N1 on A vs B (host difference); N1 vs real time (16 fps output).

If F8-H1 fails, OTTER-idle is not native-equivalent in this harness and the text reports the measured difference;
it does not substitute a different native number.

## 5. New runs

| set | runs | estimate |
|---|---|---|
| N1 native | 2 workloads x 5 reps x hosts A, B = 20 | ~1 h |
| T3 M2 + M3 tracking | Fig. 7 OTTER scenario (A -> B, call 30, 1 Gbps) + `--m3 --m3_owner`, 2 workloads x 5 reps = 10 | ~1.5 h |

Same commit on all hosts, GPU 0 idle (`d0_remote.py gpu_idle`) before each set. T3 runs must meet the Fig. 7 OTTER
validity and C1 (SINKOK or verified fallback, 0 / 360) to be counted.

## 6. Validity

- Panel a: the Fig. 7 validity verdicts (40 / 40 valid); no new rule.
- N1: the run completes the chunk range; logged FPS for every chunk; GPU 0 idle before; same commit.
- T3: as Fig. 7 OTTER. A cell with fewer than 5 valid reps is NOT EVALUABLE.

## 7. Statistics

Medians and IQR over reps; per-call values pooled within a run first (run median), then across reps. Every rep shown.
Each rule must hold on dog and on butterfly separately.

## 8. Plot specification

Style: the Fig. 7 / EC-LLM e3 style (7.70 x 4.80 in, axes [0.19, 0.20, 0.78, 0.73], 28 pt, OTTER blue, baselines gray).
- **8a.** x: time since the trigger (s); y: frames behind an uninterrupted stream (F(t)); one step line per method
  (median-total-stall rep; the other reps thin); each curve ends at its run's end, marked. Layout per D1.
- **8b.** Bars of generation throughput (frames/s) for N1, N2, T2, T3, C (D2 decides which appear), median + IQR + reps;
  a dashed line at native N1.

## 9. What Fig. 8 must not claim

- "No overhead" from F8-H1 alone: idle OTTER runs no OTTER code by construction; the overhead claim is F8-H2.
- Frames lost: the harness delays, it does not drop; "frames behind" is a delay expressed in frames.
- Throughput during migration or staging (Fig. 14).
- WAN-level user latency during remote serving.

## 10. Open decisions

- **D1, 8a form.** (i) frames behind vs time (recommended: OTTER's predicted ~13 frames and Full's ~350 [H] are both
  readable on a log axis), or (ii) the plan's cumulative delivered frames vs time (at 300 s
  ~2,000 frames, OTTER's deficit is invisible without an inset). And: both workloads as two panels, or dog in the main
  figure and butterfly in the appendix.
- **D2, native.** N1 = upstream `inference.py --profile` (recommended: the number StreamDiffusionV2's authors report),
  or a session-API loop without the harness, or both.
- **D3, M3 tracking runs (T3).** New 10 runs (recommended: the full OTTER configuration has not been measured in
  steady state), or report T2 only and leave M3 to Fig. 14.
- **D4, Fig. 8b vs Fig. 14a.** The plan has steady-state FPS in 8b and throughput loss (idle, during transfer,
  staging) in 14a. Recommended: 8b = steady state only (this document); 14a = during transfer / staging + memory,
  its own preregistration, reusing the Fig. 7 source-side data (A's call period during pre-copy vs A under R-full).
- **D5, thresholds.** 1.03 for F8-H1 / H2 and 1.5 x T_ref for a stall; 0.25 for F8-H3 (as Fig. 7's H1).
