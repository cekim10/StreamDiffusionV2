# Fig. 7 preregistration: OTTER's single-migration performance (FROZEN 2026-10-30, before any Fig. 7 run)

Plan: `../eval_plan/plan.md` (Fig. 7, RQ1, P0). Draft 1 (80f5805d) reviewed by the user; decisions D1-D3 and the
additions of the review are applied below. Labels: [V] verified in code or earlier records, [H] hypothesis /
expectation, [R] recommendation. Tools: `tools/eval/run_fig7.sh`, `tools/eval/fig7_report.py`.

**Central message (to be tested, not assumed).** OTTER minimizes streaming disruption while preserving exact Sink
state, without full-state transfer or full-session recomputation.

## 1. Objective and scope

Compare user-visible interruption, time to local service and transmitted bytes of one migration A -> B under four
methods: Full, Llumnix-style pre-copy (P-full), ServerlessLLM-style recompute (R-full) and current OTTER.

**Scope (fixed).** In one migration only M1 acts:
- M2 (versioned reuse) needs an earlier version at the destination, which exists only from the second migration on.
- M3 (lineage staging) needs holders, which exist only after a move or a cancelled migration.

Fig. 7 is therefore **OTTER's single-migration performance, i.e. M1's end-to-end effect**. It is not evidence for M2 or
M3 (Figs. 10 and 11). The caption and text say so.

Not used: XB's OTTER numbers (0.67 s etc.). They come from `reuse_dyn2` (M1 + M2 + M3-v2 of 2026-10-23), which
resumed Sink-less at the destination, a different mechanism from the current M1 [V].

## 2. Methods (one harness, one commit, same nodes, transport and caps)

All four run through `mobility_orchestrate.py` / `mobility_node.py` (the XB harness) [V].

| label | policy | setting | after the trigger | completion |
|---|---|---|---|---|
| Full | `full` | none | stop; copy all state (6.02 GiB); resume at B | always completes |
| Llumnix-style | `precopy_full` | `thr=256:rl=10`, no-shrink rule < 10 % (XB freeze) | A keeps serving; rounds of changed 4 MiB fragments; stop-and-copy of the remaining dirty set at a chunk boundary; B verifies every component's digest, then resumes | section 5 |
| ServerlessLLM-style | `recompute_full` | `lag=1:rl=1` (XB freeze); inputs FFV1 lossless | A keeps serving; B re-runs the session from call 0 from transferred input frames; after the round limit A stops and B finishes catching up while nothing is delivered | section 5 |
| OTTER | `precopy_replay` | `thr=16:rl=1`, `--replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse`; `--m3` off | A keeps serving; Sink base + per-call input log (+ refresh patches) to B; B replays in shadow; switch when replayed >= 12 and lag <= 1; Sink digest check (SINKOK, else fallback) | always completes (fallback on SINKNO) |

**D1 (decided): OTTER flags.** The frozen M1 + M2 flags exactly as in M3-S3 Phase D `base`; `--m3` off. In one migration
`--replay_retain` only keeps a host copy at A after the switch (~1 s, off the critical path), and `--replay_reuse` has
nothing to reuse.

**Code state [V].** Since 47acbe44, `mobility_node.py` gained guarded M3 entry points (taken only with `--m3`) and
record-only instrumentation. Regression at the freeze commit: `test_xb` ALL PASS (87), `test_m1_live` ALL PASS, four
policies end to end against dry-run nodes (section 9).

**What is compared (stated in the text).** Full, P-full and R-full reconstruct the **whole state**. OTTER reconstructs
the **Sink exactly** and the recent state **by replay**. They do not give the same output equivalence, so Fig. 7 never
claims "faster at equivalent correctness". Output fidelity is measured and reported next to the latency results
(section 6, C2).

## 3. Workloads, trigger, network, repetitions

| item | value |
|---|---|
| workloads | dog (`examples/original.mp4`) = Low-refresh; butterfly-feeding-slow-motion = High-refresh; both seed 0 (as XB1 and M3-S3) |
| refresh labels | Fig. 5 (n = 20): dog among the lowest refresh rates, butterfly the highest [V] |
| path | A (elves-01) -> B (elves-02), `--hops 1 --tm 1e9` (no further moves) |
| trigger | the user moves to B at generation call 30 (`--migration_chunk 30`), as XB1 and M1 E3-E6 |
| horizon | `--xb_horizon 100 --horizon_calls 130 --post_chunks 1500 --max_run_s 2400` (XB1 values) |
| network | 1 Gbps emulated cap (`--bw 1000`); sub-ms LAN; GPU 0 of each host |
| repetitions | 5 valid reps per (method, workload): 4 x 2 x 5 = 40 runs; reps interleaved across methods |
| additional inputs | not in Fig. 7; candidates for Fig. 12 / generality |

Expected run time [H]: about 5-6 h, dominated by P-full; the first run's time is recorded.

## 4. Metrics (one definition for every method)

Fig. 7 metrics, computed by `xb_delivery.py` and `aggregate_xb.py` from the delivered-chunk log (orchestrator
`metrics.csv`, `t_out_rel` relative to the trigger) and the byte events [V]:

| metric | definition | event basis |
|---|---|---|
| **TTFO-local** (7a) | trigger -> first chunk delivered by the user's current edge B | delivery log; A's chunks after the trigger count as remote |
| **delivery gap** (7b) | the **largest output delivery interval observed after the trigger**: the longest interval with no chunk delivered from any host, up to the last delivered chunk | delivery log; never below one call interval (~0.57 s) |
| **transmitted bytes** (7c) | bytes the harness actually sent for the migration (MEASURED; output stream excluded) | byte events, below |

They answer different questions and are never combined. The gap is what the user sees as a stall. TTFO-local is how
long the user is served from a remote GPU (A) before B serves. Bytes is network cost.

**Diagnostics (reported, not Fig. 7 metrics).**
- **Cutover interruption**, every method: last chunk delivered by A before B's first chunk -> that first chunk
  (delivery log). The delivery gap is the user-visible quantity. The cutover interruption checks that the gap is the
  migration's stall and not an unrelated slowdown. When the two differ, the run lists where the gap occurred
  (`delivery_gap_at_s`).
- **OTTER only:** the orchestrator's `cutover.interruption_s` (source last output -> destination first output),
  cross-checked against the delivery-log cutover.
- **Remote serving** (`remote_wall_s`, same code as the M3 reports).

The M3 reports' `readiness_s`, `first_output_s` and `interruption_s` use other events (source `replay_ready`,
destination `first_output`, orchestrator cutover) and are not Fig. 7 metrics [V].

**Byte accounting (fixed before the freeze) [V].**

The defect: `aggregate_xb.py:transmitted_bytes` omitted `precopy_replay`'s `log_bytes` (input log and Sink refresh
patches).

The fix:
- It now adds `log_bytes` of the `xb_precopy_switch` (and `xb_precopy_cancelled`) events, for `precopy_replay` only.
- Full, P-full and R-full keep XB's accounting (state stream; rounds + final copy; encoded inputs).

Verification:
- **XB unchanged.** Re-aggregating XB gives byte-identical `xb_results.{md,json}`.
- **M1 E6 records reproduced.** On the four E6 runs the accounted bytes equal the E6 record (Sink base + log incl.
  patches + switch bytes): audi 1.839, butterfly 2.262, train 1.926, dog-fallback 2.490 GB.
- **NIC cross-check (diagnostic).** The destination NIC receive counter, from the trigger to B's first chunk, is 1.0477
  x the accounted bytes in all four runs. That equals the per-segment header overhead at the measured MSS, (1388 + 66)
  / 1388 = 1.0476 (TCP/IP and Ethernet headers). After that factor the ratio is 0.9991-0.9992. Reported per run.

## 5. Completion, non-convergence and timeout (fixed)

- **P-full** ends its rounds by the round limit (10) or the no-shrink rule (a round's dirty bytes shrink by < 10 %).
  Then it stops A and copies the remaining dirty set. That is a completed migration with a long stop-and-copy; its
  measured TTFO-local and gap are reported. Non-convergence is **not** a failure and is never replaced by an assumed
  time. XB measured 3 rounds, no convergence, a final stop-and-copy of about 5 GiB (gap ~51 s) [V].
- **R-full** ends its replay by the lag threshold (lag 1) or the round limit (1). Then A stops, B finishes catching up
  and resumes at A's stop call + 1 with the whole state reproduced. Completed.
- **OTTER** completes by the replay switch rule. A SINKNO verdict takes the frozen fallback (resend of dirty Sink
  fragments) and the run is still complete. Fallbacks are counted and reported.
- **Failure / timeout.** A run in which B never serves before `--max_run_s` (2400 s), or the orchestrator aborts, is a
  failed run. It is counted per cell, excluded from the medians and listed with its reason. No imputed value.

## 6. Correctness and quality: two separate conditions

**C1, state correctness (gates validity; per method, as the method claims).**

| method | claim | check (`fig7_report.py`) |
|---|---|---|
| Full | whole state exact | `full_state_digests_ok`, `final_sink_digest_matches_source`, `full_bit_exact_after_resume` |
| P-full | whole state exact | switchover verified (per-component digests at the boundary); every scored call after the switch bit-exact (`ref_match`) |
| R-full | whole state exact | switchover; decoded inputs bit-exact and input check; every scored call after the switch bit-exact |
| OTTER | **Sink exact** at the switch; recent KV rebuilt by replay | resumed on a digest-equal Sink or a verified fallback (SINKOK or fallback); 0 / 360 Sink blocks mismatching (`sink_sync_check`); positions and conditioning equal; base verified; replay order ok; no lost or duplicated calls; metadata consistent at the switch |

OTTER's claim is Sink K/V exactness, **not** bitwise-identical output frames. Its frames after the switch are not
bit-exact to the reference (M3-S3 base dog rep 1: first call 27.9 dB, later 45-49 dB; M1 E6 butterfly: first call
35.6 dB, minimum over 24 calls 24.7 dB, terminal 42.0 dB) [V]. A run is not invalid because its frames differ from the
reference when the method does not claim bitwise output.

**C2, output fidelity (D2 decided: descriptive, mandatory reporting).** Not a validity gate. Every Fig. 7 result table
and the Fig. 7 text report, per method and workload (medians and IQR), per-call PSNR at B against the uninterrupted
reference of the same input and seed:
- first call after the switch;
- minimum and median over the first 24 calls after the switch;
- terminal median (last 10 calls);
- the number of bit-exact calls.

If OTTER's fidelity is severely degraded, the latency results alone do not support an advantage, and the text says so.
Fig. 13 evaluates quality in full: reference fidelity, perceptual and temporal consistency.

## 7. Validity (same principle for every method)

- **P-full, R-full, OTTER:** frozen XB validity (`xb_validity.run_validity_xb`) [V]:
  - all nodes on one commit;
  - GPU 0 idle before the run;
  - switchover verified, or for R-full a switchover with exact inputs;
  - the source served until the switch;
  - codecs present;
  - the final edge served;
  - not cut by `max_run_s`;
  - NIC cap respected (no 10 s mean above 1.15 x the cap).
- **Full:** not an XB method. It uses the rule the XB aggregation applied to it (W / R / N validity: same commit,
  digests, NIC cap) [V].
- **All methods:** plus C1 of section 6.
- **Start guard.** `run_fig7.sh` refuses to start unless `d0_remote.py gpu_idle` reports one commit and idle GPUs.
- **Invalid runs** are kept, listed with reasons and rerun once; a cell needs 5 valid reps.

Note on the M1 E6 runs [V]: they fail the NIC rule because of a 9.8 Gbps burst at t ~ 88 s, after the migration. It
comes from E6's post-run `--replay_verify` state transfer, which Fig. 7 does not use. Their migration window was
paced at 1.03 Gbps (headers included), and the M3-S3 runs at the current commit pass the rule.

## 8. Hypotheses, statistics and predictions (D3 decided)

**Statistics.**
- Per (method, workload): median and IQR (Q1-Q3) over the 5 valid reps; every rep plotted.
- Failed and invalid runs reported separately.
- No figure of merit combines the three metrics.
- A workload whose cells do not all have 5 valid reps is NOT EVALUABLE.

**Rules (medians; each must hold on dog and on butterfly separately to be SUPPORTED).**
- **F7-H1 (gap).** median gap(OTTER) <= 0.25 x min(median gap(Full), median gap(P-full), median gap(R-full)).
- **F7-H2 (TTFO-local).** median TTFO-local(OTTER) < min(median TTFO-local of Full, P-full, R-full).
- **F7-D (bytes).** Descriptive: OTTER's median bytes over each method's. No direction is claimed.

| outcome | conclusion |
|---|---|
| H1 and H2 hold | OTTER's single migration stalls far less and reaches local service sooner than every full-state baseline |
| H1 holds, H2 fails | stalls far less, but not sooner local; reported as such |
| H1 fails | no single-migration advantage on stalls; reported |

**Predictions [H]** (from M1 E6 and XB1, other code versions; not evidence):

| method | delivery gap | TTFO-local | bytes |
|---|---|---|---|
| OTTER | ~1.6 s | 23-25 s | ~1.8 GB dog, ~2.3 GB butterfly |
| Full | ~54 s (= TTFO-local) | ~54 s | 6.46 GB |
| P-full | ~51-52 s | ~214-220 s | 22.9-23.6 GB |
| R-full | ~18 s | ~37 s | 0.06-0.08 GB |

What these predictions imply, written down before any run:
- H1 should hold by a wide margin (~1.6 vs ~18 s).
- H2 should hold narrowly against R-full (~24 vs ~37 s).
- OTTER should send ~25-30 x more bytes than R-full, and fewer than Full or P-full.
- OTTER's TTFO-local is ~24 s because A serves remotely until the replay switch. Remote serving is cheap only on a
  low-latency network, and WAN latency is not emulated (stated in the caption).

This is the trade-off Fig. 7 shows: OTTER optimizes the stall and exact Sink state, not time to local service or
bytes.

## 9. Procedure

**1. Byte-accounting fix + regression (done before the freeze, no GPU).**
- `aggregate_xb.py` fixed (section 4).
- XB re-aggregation unchanged.
- E6 records reproduced; NIC difference explained.
- `test_xb` ALL PASS (87); `test_m1_live` ALL PASS.
- `run_fig7.sh dry`: all four policies against dry-run nodes, then `fig7_report.py`.
- `fig7_report.py` checked on recorded GPU runs: XB1 Full / P-full / R-full rep 1 and M1 E6 butterfly. C1, metrics,
  bytes and C2 all readable.

**2. Freeze** (this document, committed with the tools).

**3. Main runs.**
1. Sync all four hosts (`d0_remote.py pull`), then `run_fig7.sh preflight`.
2. `run_fig7.sh first` runs dog OTTER rep 1. Check it with `fig7_report.py --sanity`:
   - correctness: SINKOK, 0 / 360, normal cutover;
   - metrics: TTFO-local, gap, PSNR recorded;
   - traffic: Sink base + log + patch + switch bytes all counted.
   It counts as data if it meets the preregistered conditions.
3. `run_fig7.sh rest` runs the other 39 runs:
   - dog baselines rep 1;
   - dog reps 2-5, methods interleaved;
   - butterfly reps 1-5, methods interleaved.
   P-full's and R-full's correctness are checked on their first runs (`--sanity` on the partial data). If a problem
   needs a code or protocol change, the affected runs are excluded and rerun on the changed version, recorded as a
   note here.

## 10. Plot specification (Fig. 7a-c)

- **Layout.** Three panels side by side, same height, the m123 figure style.
- **Panels.** a TTFO-local (s), b delivery gap (s), c transmitted bytes (GB).
- **x axis.** Method, in this order: Full, Llumnix-style, ServerlessLLM-style, OTTER.
- **Bars.** Two per method: Low-refresh (dog) and High-refresh (butterfly).
- **Marks.** Bar = median; whisker = IQR; dots = the 5 reps; the median printed on each bar.
- **y axis.** Log scale by default on all three panels. The axis may change only for readability, by this rule: if a
  panel's medians span less than one decade, that panel uses a linear axis. Both versions of panel b are kept in the
  record, and the choice is stated with the rule.
- **Encoding.** OTTER in the accent color, baselines in grays. A failed cell is shown as "n/a" with its count, never
  as a bar.
- **Caption.** Must state:
  - single migration, so M1 only;
  - 1 Gbps, LAN; remote serving not charged for WAN latency;
  - baselines are re-implementations "in the style of" their source systems;
  - OTTER's state claim is Sink exactness (C1), not bitwise output, and its fidelity numbers (C2);
  - bytes are measured harness bytes.

## 11. What Fig. 7 must not claim

- XB's 0.67 s as current OTTER.
- P-full non-convergence as a failure or a made-up time.
- Sink exactness as bitwise-identical output.
- "Equivalent correctness" between OTTER and the full-state baselines.
- Estimated network bytes (the XB remote-delivery estimate) as transmitted bytes.
- The Fig. 7 gains as effects of M2 or M3.
