# Fig. 8 preregistration: streaming continuity and native performance (RQ1-2)

**Status: FROZEN (2026-10-30), before any Fig. 8 run and before the 8a re-analysis of the Fig. 7 runs.** DRAFT 1 was
398ded8f. Decisions D1-D5 by the user (2026-10-30), section 9. Plan: `osdi/eval_plan/plan.md`.

Roles: Fig. 7 = migration efficiency; **Fig. 8 = streaming continuity and native performance**; Fig. 14 = runtime
overhead during migration and staging, and memory.

## 1. Questions and messages

- **8a, continuity.** Over the whole migration, how much output interruption does each method accumulate? Fig. 7's
  gap is the longest single interruption; 8a adds up every stall. Message to test: OTTER reduces the cumulative
  interruption, not only the longest one.
- **8b, native performance.** Does OTTER, with M2 version tracking and M3 lineage tracking on, generate as fast as
  native StreamDiffusionV2 when no migration or staging is running? Message to test: OTTER's integrated execution adds
  only a small overhead.

Out of scope: WAN latency while the source serves remotely (network / mobility evaluation); throughput during transfer
or staging and all memory (Fig. 14); quality (Fig. 13).

## 2. Facts this protocol rests on

| fact | source | tag |
|---|---|---|
| Fig. 7: 40 / 40 runs valid; per-run delivery log (`xb_delivery`), the same log as TTFO-local and the gap. | Fig. 7 report | [V] |
| The harness resumes at the next call and never drops input chunks: a stall delays the rest of the stream. | Fig. 7 / XB protocol | [V] |
| Before the first migration no OTTER code runs per call. After a switch, the new owner runs M2 tracking (`sink_track_step`) and, with `--m3_owner`, M3 lineage tracking (`_m3_after_step`), both after the generation call. | `mobility_node.py` `_generate`, `m3_path.py` | [V] code |
| Generation in the harness: upstream `SingleGPUInferencePipeline.run_stream_batch` (VAE encode, `inference_stream`, decode to uint8), CUDA-synchronized = `chunk_s`. The harness sets deterministic algorithms (`cudnn.deterministic`, `use_deterministic_algorithms`, CUBLAS workspace); upstream `inference.py` does not. | `state_ablation.Runner.step`, `proto_handoff.build_runtime`, `streamv2v/inference.py` | [V] code |
| Upstream native throughput (`inference.py --profile`): per chunk, frames per chunk / wall time of encode + DiT + decode + copy to host, synchronized. | `streamv2v/inference.py:296-409` | [V] code |
| The harness call period (~0.60 s) exceeds its generation time (~0.556 s) by ~45 ms, mostly the reference scoring (PSNR, SSIM against the uninterrupted reference) that exists only for evaluation. | Fig. 7 metrics | [V] |
| Inputs are short (dog 81 frames, butterfly 32); upstream processes an input once. The harness repeats the decoded video in memory. | ffprobe; `build_runtime` | [V] |
| H.264 packets copied N times without re-encoding (PyAV remux) decode to exactly the original frames repeated: dog 10 loops, butterfly 24 loops, 741 frames each checked equal (PyAV, Mac). The run host checks again through upstream's loader. | `fig8_native.py prepare` | [V] |
| Instrumentation added for Fig. 8: per-call `track_ms` = time of the M2 / M3 tracking calls (timing only; no behavioural change). Regression: section 7. | `mobility_node.py`, `mobility_orchestrate.py` | [V] |
| Dry run of the 8b OTTER configuration (A -> B, `--m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2`): B tracks both M2 (`tracking_version: true`) and M3 lineage (`m3_owner_begin`); no staging flow after the switch on a one-hop path. | `_dryrun_expF8_*` | [V] dry |

**Numbers seen before the freeze (disclosed; rules using them are not blind).** B's median call period after the
switch in Fig. 7 (Full 0.597-0.598 s, P-full 0.601, R-full 0.604-0.605, OTTER 0.603-0.604); B's median generation time
(`chunk_s`) after the switch (0.553-0.560 s for all methods) and A's baseline-record generation time (0.556-0.557 s);
the stall components of OTTER (start stall 1.56-1.65 s, cutover 1.49-1.80 s) and P-full (start stall 1.6-1.7 s, later
snapshot stalls 2.3-2.5 s) from the Fig. 7 analysis. No total stall, no native and no M2 + M3 tracking number has been
computed.

## 3. Panel 8a: cumulative stall time (re-analysis of the 40 Fig. 7 runs, no new runs)

**Per run** (`fig8_report.py`):
- delivery times after the trigger, t_0 = 0 (the trigger) and every delivered chunk from any host (Fig. 7 log);
- T_ref = median delivery interval of the run;
- a **stall** = an interval longer than 1.5 x T_ref; its excess = interval - T_ref;
- **cumulative stall time** S(t) = sum of the excesses of the stalls that ended by t; **total stall** = S at the run's
  last delivered chunk; the number and times of the stalls.

Jitter below 1.5 x T_ref is not counted, so S does not grow with run length. The longest interval equals the Fig. 7
delivery gap (checked per run). Every curve ends at its run's last chunk; nothing is extrapolated.

**F8-H1 (total stall, medians, each workload).** median total stall(OTTER) <= 0.25 x min(median total stall of Full,
P-full, R-full). SUPPORTED only if it holds on dog and on butterfly. Predictions [H] (not blind, section 2): OTTER ~2 s,
R-full ~18 s, Full ~54 s, P-full ~52-58 s.

## 4. Panel 8b: steady-state throughput

| condition | what runs | host | runs |
|---|---|---|---|
| **Native** | upstream `streamv2v/inference.py --profile`, unmodified; Fig. 7 model configuration (`configs/wan_causal_dmd_v2v.yaml`, T2V-1.3B, 480 x 832, 2 steps, noise 0.8, seed 0); input looped (section 2) | A and B | 2 workloads x 5 reps each = 20 |
| **OTTER (M2 + M3 tracking)** | Fig. 7 OTTER flags + `--m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2` (the M3-S3 configuration); one migration A -> B at call 30, 1 Gbps | measured on B | 2 workloads x 5 reps = 10 |

**Measurement windows.** Native: chunks 40-159 (upstream "Processed" index; warm-up excluded). OTTER: B's calls from
its first call + 10 to the run's end (no migration or staging work: section 6).

**Metric.** Time per call (4 output frames); throughput = 4 / time per call (frames/s).
- Native: upstream's per-chunk wall time.
- OTTER: B's generation time (`chunk_s`) + its M2 / M3 tracking time (`track_ms`) per call.

The OTTER time is the integrated execution in this system (harness generation path including its deterministic
settings, plus OTTER's per-call tracking). It excludes the harness's reference scoring and logging, which exist only
for evaluation. The delivered call period (which includes them) is reported alongside, descriptive.

**F8-H2 (native performance, medians, each workload).** median OTTER time per call (B) <= 1.03 x median native time
per chunk (B). Run medians first, then the median over 5 reps. SUPPORTED only if it holds on both workloads.

**Descriptive.** Native on A vs B; OTTER generation alone vs generation + tracking; tracking time (median, max); the
delivered call period; real-time ratio (16 fps output).

## 5. Statistics

Per cell: median and IQR over valid reps (5 required; otherwise NOT EVALUABLE). Every rep shown. No metric combines
8a and 8b.

## 6. Validity

- **8a.** The Fig. 7 validity verdict of each run (unchanged).
- **Native.** Return code 0; all 120 window chunks logged; looped input verified on the run host (PyAV and upstream's
  loader); GPU is an L40S; GPU 0 idle before the set (`d0_remote.py gpu_idle`); one commit on A and B.
- **OTTER.** The Fig. 7 OTTER validity and C1 (SINKOK or verified fallback, 0 / 360 Sink blocks mismatching);
  `track_ms` recorded on every window call; no migration or staging event (`xb_task*`, `xb_precopy*`, `replay_*`,
  `flow*`, `frag*`, `m3_*`, `staging*`, `migration*`) after the window's first output.
- A failing run is excluded and listed with its reason. No rerun unless a harness defect is found (then the Fig. 7
  precedent: fix, rerun under the same rules, keep both records).

## 7. Procedure

1. Regression and dry run, then this freeze is committed with the tools. Done: `test_xb` ALL PASS (87), `test_m1_live` ALL PASS; `run_fig8.sh dry` rc 0 (dog and butterfly: OTTER valid, C1 pass, `track_ms` on every call, no migration / staging event in the window); `fig8_native.py parse` on a synthetic log.
2. elves-01: `d0_remote.py pull` on all hosts, `run_fig8.sh preflight`.
3. `run_fig8.sh native`: A runs its 10 native runs locally while B runs its 10 through its agent;
   `fig8_native.py remote status` / `remote fetch` for B.
4. After B's native runs end: `run_fig8.sh otter` (10 runs, reps interleaved across workloads).
5. `fig8_report.py` (8a and 8b, the rules as written), then the figure.
The native and OTTER sets never overlap on a GPU.

## 8. Plot specification

Style: Fig. 7 / EC-LLM e3 (7.70 x 4.80 in canvas, axes [0.19, 0.20, 0.78, 0.73], 28 pt text, 19 pt values; OTTER blue,
baselines gray).
- **8a** (two panels: Low-refresh, High-refresh). x: time since the trigger (s); y: cumulative stall time (s), linear
  (curves start at 0). One step line per method: the rep with the median total stall, the other reps thin and light.
  Each curve ends at its run's last chunk (marked); the total stall printed at the end of each median curve.
- **8b.** Grouped bars per workload: native (B) and OTTER (B), throughput (frames/s); bar = median, whisker = IQR,
  dots = reps, value printed; y linear from 0.

## 9. Decisions (user, 2026-10-30)

| | decision |
|---|---|
| D1 | 8a = cumulative stall time vs time, both workloads (not frames behind, not cumulative frames) |
| D2 | native = upstream StreamDiffusionV2 (`inference.py`); no session-API baseline |
| D3 | 10 OTTER runs with M2 + M3 tracking |
| D4 | Fig. 8 = steady state only; Fig. 14 = overhead during migration / staging |
| D5 | thresholds kept: 1.5 x T_ref, 0.25 (F8-H1), 1.03 (F8-H2) |
| - | no tracking-on / off paired control; native and OTTER on the same model, inputs and GPU (host B) |

## 10. What Fig. 8 must not claim

- That the 8b difference is the pure cost of tracking: native and OTTER run different execution paths (harness,
  deterministic settings); it is the integrated execution overhead.
- "No overhead", or overhead during migration or staging (Fig. 14).
- Frame loss: the harness delays the stream; it does not drop frames.
- WAN-level user latency during remote serving.
- A cumulative-stall advantage beyond the two workloads and the single A -> B migration measured.
