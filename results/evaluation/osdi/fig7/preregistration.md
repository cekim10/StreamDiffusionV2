# Fig. 7 preregistration: OTTER's single-migration performance (DRAFT 1, 2026-10-30; not frozen, nothing run)

Plan: `../eval_plan/plan.md` (Fig. 7, RQ1, P0). Status: draft for review. Items marked **[decide]** need the user's
choice before the freeze. Labels: [V] verified in code or earlier records, [H] hypothesis / expectation, [R] recommendation.

## 1. Objective and scope

Compare user-visible interruption, time to local service and transmitted bytes of one migration A -> B under four
methods: Full, Llumnix-style pre-copy (P-full), ServerlessLLM-style recompute (R-full) and current OTTER.

**Scope (fixed).** In one migration only M1 acts:
- M2 (versioned reuse) needs an earlier version at the destination, which exists only from the second migration on.
- M3 (lineage staging) needs holders, which exist only after a move or a cancelled migration.

Fig. 7 is therefore **OTTER's single-migration performance, i.e. M1's end-to-end effect**. It is not evidence for M2 or
M3; those are Figs. 10 and 11. The caption and text say so.

Not used: XB's OTTER numbers (0.67 s etc.). They come from `reuse_dyn2` (M1 + M2 + M3-v2 of 2026-10-23), which
resumed Sink-less at the destination, a different mechanism from the current M1 [V].

## 2. Methods (one harness, one commit, same nodes, transport and caps)

All four run through `mobility_orchestrate.py` / `mobility_node.py` (the XB harness) [V].

| label in the figure | policy | setting (frozen where it exists) | what happens after the trigger | completion |
|---|---|---|---|---|
| Full | `full` | none | stop; copy all state (6.02 GiB); resume at B | always completes |
| Llumnix-style | `precopy_full` | `thr=256:rl=10`, no-shrink rule < 10 % (XB freeze) | A keeps serving; rounds of changed 4 MiB fragments; stop-and-copy of the remaining dirty set at a chunk boundary; B verifies digests of every component, then resumes | see section 5 |
| ServerlessLLM-style | `recompute_full` | `lag=1:rl=1` (XB freeze); inputs FFV1 lossless | A keeps serving; B re-runs the session from call 0 from transferred input frames; after the round limit A stops and B finishes catching up while nothing is delivered | see section 5 |
| OTTER | `precopy_replay` | `thr=16:rl=1`, `--replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse` (frozen M1 / M2, 47acbe44) | A keeps serving; Sink base + per-call input log (+ refresh patches) to B; B replays in shadow; switch when replayed >= 12 and lag <= 1; Sink digest check (SINKOK, else fallback) | always completes (fallback on SINKNO) |

**[decide] D1, OTTER flags.** [R] Use the frozen M1 + M2 flags exactly as in M3-S3 Phase D `base` (retain / reuse on;
`--m3` off). In one migration `--replay_retain` only keeps a host copy at A after the switch (~1 s, off the critical
path) and `--replay_reuse` has nothing to reuse. Alternative: M1 flags only.

**Code state [V].** Since 47acbe44, `mobility_node.py` gained guarded M3 entry points (taken only with `--m3`) and
record-only instrumentation (fragment hashes kept for events). Pre-run check P1 (section 9) confirms that the M1 / M2
and XB paths behave as before.

## 3. Workloads, trigger, network, repetitions

| item | value |
|---|---|
| workloads | dog (`examples/original.mp4`) = Low-refresh; butterfly-feeding-slow-motion = High-refresh; both seed 0 (as XB1 and M3-S3) |
| refresh labels | justified by Fig. 5 (n = 20): dog among the lowest refresh rates, butterfly the highest [V] |
| path | A (elves-01) -> B (elves-02), `--hops 1 --tm 1e9` (no further moves) |
| trigger | the user moves to B at generation call 30 (`--migration_chunk 30`), as XB1 and M1 E3-E6 |
| horizon | `--xb_horizon 100 --horizon_calls 130 --post_chunks 1500 --max_run_s 2400` (XB1 values) |
| network | 1 Gbps emulated cap (`--bw 1000`); sub-ms LAN; GPU 0 of each host |
| repetitions | 5 valid reps per (method, workload): 4 x 2 x 5 = 40 runs |
| additional inputs | not in Fig. 7; candidates for Fig. 12 / generality |

Expected run time [H]: about 5-6 h, dominated by P-full (~4 min per run plus node start-up per cell); estimated from XB
and M3-S3 cell times, to be replaced by the shakedown's measurement.

## 4. Metrics (one definition for every method)

All three are computed by `tools/eval/xb_delivery.py` from the delivered-chunk log (orchestrator `metrics.csv`,
`t_out_rel` relative to the trigger) [V].

| metric | definition (code) | event basis |
|---|---|---|
| **TTFO-local** (7a) | trigger -> first chunk delivered by the user's current edge B (`ttfo_local_final_s`) | delivery log; A's chunks after the trigger count as remote |
| **delivery gap** (7b) | longest interval with no chunk delivered from any host, from the trigger to the last delivered chunk (`delivery_gap_s`) | delivery log; includes the normal cadence (~0.57 s), so it is never below one call interval |
| **transmitted bytes** (7c) | bytes the harness actually sent for the migration (MEASURED; output stream excluded) | see below |

They answer different questions and are never combined: the gap is what the user sees as a stall; TTFO-local is how
long the user is served from a remote GPU (A) before B serves; bytes is network cost.

**Relation to the M3 reports [V].** `m3s2_report.py` / `m3s3_report.py` use the same `delivery_metrics` for remote
serving (`remote_wall_s`), so they are consistent with XB. Their other quantities use different events and are **not**
Fig. 7 metrics:
- `readiness_s` = source `replay_ready` - task start (exists only for `precopy_replay`);
- `first_output_s` = destination `first_output` - task start;
- `interruption_s` = destination first output - source last output at the cutover (orchestrator `cutover`).
For OTTER `interruption_s` and the delivery gap measure the same stall from different logs; both are reported for
OTTER as a cross-check (expected within one call interval) [H].

**Byte accounting: a defect to fix before any run [V].** `aggregate_xb.py:transmitted_bytes` sums, for every
`precopy*` policy, the pre-copy round bytes and the switch's `final_bytes`. For `precopy_replay` that omits
`log_bytes` (input log and Sink refresh patches; 0.02-0.52 GB in M1 E6). Fix [R]: for `precopy_replay`, add
`log_bytes` from the `xb_precopy_switch` event, i.e. Sink base + log (incl. patches) + bytes at the switch (as M1 E6
reports, 1.76-2.26 GB). Full, P-full and R-full keep XB's accounting (state stream; rounds + final copy; encoded
inputs). The fix lands as a separate commit before the freeze, with a dry test.

**Cross-check (diagnostic, not validity) [R].** The destination's NIC receive counter (`node_B/network.csv`) over the
migration window, compared with the accounted bytes; report the ratio per run.

## 5. Completion, non-convergence and timeout (fixed)

- **P-full** ends its rounds by the round limit (10) or the no-shrink rule (a round's dirty bytes shrink by < 10 %);
  then it stops A and copies the remaining dirty set. That is a completed migration with a long stop-and-copy, and
  its measured TTFO-local and gap are reported. Non-convergence is **not** a failure and is never replaced by an
  assumed time. XB measured 3 rounds, no convergence, a final stop-and-copy of about 5 GiB (gap ~51 s) [V].
- **R-full** ends its replay by the lag threshold (lag 1) or the round limit (1); then A stops, B finishes catching up
  and resumes at A's stop call + 1 with the whole state reproduced. Completed.
- **OTTER** completes by the replay switch rule; a SINKNO verdict takes the frozen fallback (resend of dirty Sink
  fragments) and the run is still complete; fallbacks are counted and reported.
- **Failure / timeout.** A run in which B never serves before `--max_run_s` (2400 s), or the orchestrator aborts, is a
  failed run: counted per cell, excluded from the medians, listed with its reason. No imputed value.

## 6. Correctness and quality: two separate conditions

**C1, state correctness (gates validity; per method, as the method claims).**

| method | claim | check |
|---|---|---|
| Full | whole state exact | switchover verified; output after the switch bit-exact vs the uninterrupted reference (`ref_match`) |
| P-full | whole state exact | per-component digests at the stop-and-copy boundary verified at B; output after the switch bit-exact |
| R-full | whole state exact | decoded inputs bit-exact (per segment); output after the switch bit-exact |
| OTTER | **Sink exact** at the switch; recent KV rebuilt by replay | source verdict SINKOK (or verified fallback), 0 / 360 Sink blocks mismatching, positions and conditioning equal, replay order ok, no lost or duplicated calls (frozen replay validity) |

OTTER's claim is Sink K/V exactness, **not** bitwise-identical output frames: its frames after the switch are not
bit-exact to the reference (e.g. M3-S3 base dog rep 1: first call after the switch 27.9 dB, later 45-49 dB) [V]. A run
is not invalid because its frames differ from the reference when the method does not claim bitwise output.

**C2, output fidelity (reported for every valid run; not a validity gate).** Per-call PSNR at B against the
uninterrupted reference of the same input and seed (`metrics.csv` `psnr`), reported as:
- first call after the switch, minimum over the first 24 calls after the switch, terminal median (last 10 calls);
- the number of bit-exact calls (`ref_match`).

**[decide] D2, fidelity gate.** [R] C2 is descriptive in Fig. 7 and evaluated in full in Fig. 13 (frames, perceptual
and temporal metrics). Alternative: a drift guard, e.g. terminal median >= 35 dB (XB's rejoin threshold) as a
condition for including OTTER's numbers. Recommendation: descriptive, because a threshold would mix the quality question
into a latency figure.

## 7. Validity (same rule for every method)

Frozen XB validity (`xb_validity.run_validity_xb`) [V]:
- all nodes on one commit;
- GPU 0 idle before the run;
- every switchover verified;
- NIC cap respected (no 10 s mean above 1.15 x the cap).

Plus C1 of section 6. The run script refuses to start unless `d0_remote.py gpu_idle` reports one commit and idle GPUs
(the guard added after M3-S3 Note 2). Invalid runs are kept, listed with reasons, and rerun once; the cell needs 5
valid reps.

## 8. Hypotheses, statistics and predictions

Statistics: per (method, workload), median and IQR (Q1-Q3) over the 5 valid reps; every rep plotted. Failed and
invalid runs reported separately. No figure of merit combines the three metrics.

**[decide] D3, the rules.** [R] Proposed, written before any run:
- **F7-H1 (gap).** OTTER's delivery gap <= 0.25 x the smallest gap among Full, P-full and R-full, on both workloads.
- **F7-H2 (TTFO-local).** OTTER's TTFO-local < the smallest among Full, P-full and R-full, on both workloads.
- **F7-D (bytes).** Descriptive: OTTER's bytes against each method, with ratios. No direction is claimed.

| outcome | conclusion |
|---|---|
| H1 and H2 hold | OTTER's single migration stalls far less and reaches local service sooner than every exact baseline |
| H1 holds, H2 fails | stalls far less, but not sooner local; reported as such |
| H1 fails | no single-migration advantage on stalls; reported |

**Predictions [H]** (from M1 E6 and XB1, other code versions; not evidence):
- OTTER: gap ~1.6 s; TTFO-local 23-25 s; bytes ~1.8 GB dog, ~2.3 GB butterfly.
- Full: gap = TTFO-local ~54 s, 6.46 GB.
- P-full: TTFO-local ~214-220 s, gap ~51-52 s, 22.9-23.6 GB.
- R-full: TTFO-local ~37 s, gap ~18 s, 0.06-0.08 GB.

Consequences, stated now:
- H1 is expected to hold by a wide margin (~1.6 vs ~18 s).
- H2 is expected to hold narrowly against R-full (~24 vs ~37 s).
- On bytes OTTER is expected to send ~25-30 x more than R-full and less than Full or P-full; the figure shows it.
- OTTER's TTFO-local is ~24 s because A serves remotely until the replay switch. Remote serving is cheap only on a
  low-latency network; WAN latency is not emulated (stated in the caption).

## 9. Pre-run checks (before the freeze; no GPU measurement counted)

1. **P1 regression (dry).** `test_xb` and `test_m1_live` at the freeze commit; the four policies in dry mode end to
   end; the byte-accounting fix tested on dry runs (log bytes appear for `precopy_replay` only).
2. **P2 shakedown (GPU, 8 runs, not counted).** One rep per (method, workload) at the freeze commit:
   - every method completes;
   - C1 checks are readable;
   - the metrics compute;
   - run time is measured.
   Reviewed with the user before the main runs.
3. **P3 reference coverage.** `psnr` / `ref_match` come from the uninterrupted reference each node records at start-up
   (`--post_chunks 1500`, as XB1); confirm in the shakedown that it covers every call compared after the switch for all
   four methods (P-full switches latest, ~call 400).

## 10. Plot specification (Fig. 7a-c)

- **Layout.** Three panels side by side, same height, the m123 figure style (`plot_background_m123.py` helpers).
- **Panels.** a TTFO-local (s), b delivery gap (s), c transmitted bytes (GB).
- **x axis.** Method, in this order: Full, Llumnix-style, ServerlessLLM-style, OTTER.
- **Workloads.** Two bars per method: Low-refresh (dog) and High-refresh (butterfly).
- **Marks.** Bar = median; whisker = IQR; dots = the 5 reps.
- **y axis.** Log scale on all three panels (values span ~1.6-220 s and ~0.07-24 GB), with the median printed on each bar.
- **Encoding.** OTTER in the accent color; baselines in grays. A failed cell is shown as "n/a" with its count, never as a bar.
- **Caption.** Must state:
  - single migration, so M1 only;
  - 1 Gbps, LAN, remote serving not charged for WAN latency;
  - baselines are re-implementations "in the style of" their source systems;
  - OTTER's state claim is Sink exactness (C1), not bitwise output;
  - bytes are measured harness bytes.

## 11. What Fig. 7 must not claim

- XB's 0.67 s as current OTTER.
- P-full non-convergence as a failure or a made-up time.
- Sink exactness as bitwise-identical output.
- Estimated network bytes (the XB remote-delivery estimate) as transmitted bytes.
- The Fig. 7 gains as effects of M2 or M3.
