# Fig. 14 preregistration: OTTER's overheads (DRAFT 1, not frozen, nothing run)

Plan: `osdi/eval_plan/plan.md` (Fig. 14, RQ2, P0; "overhead is measured, never assumed negligible"). Follows Fig. 8b:
F8-H2 was NOT SUPPORTED. OTTER on B ran 5.4 % slower than native, but the harness path without any OTTER code was
already +5.0 %, and tracking measured 0.57 ms per call. Fig. 14a separates OTTER's own cost from that harness gap by
putting OTTER's tracking into the native loop. The user asked for this "native-integrated measurement" on 2026-11-01.

Labels: [V] verified in code or records, [H] hypothesis, [R] recommendation, [K] seen while drafting (computed from
existing runs before this draft).

## 1. Questions

- **Q1 (14a, steady state).** What does OTTER's per-call tracking cost inside the unmodified native StreamDiffusionV2
  loop?
- **Q2 (14a, phases).** How much slower is a served call while OTTER moves state (source during a transfer) or stages
  it (owner during staging)?
- **Q3 (14b).** How much GPU and host memory does OTTER use, split by:
  - source GPU,
  - destination peak,
  - retained host copy,
  - replay log,
  - switch metadata,
  - cluster-wide staged state,
  - GPU vs CPU?

## 2. Facts

| fact | source | label |
|---|---|---|
| Native (upstream `inference.py --profile`), median per-chunk time in processed 40-159: A 0.5309 / 0.5323 s, B 0.5277 / 0.5281 s (dog / butterfly) | `osdi/fig8/fig8_report.md` | [V] |
| OTTER's steady-state tracking per call: M2 `GpuRuntime.sink_track_step` and M3 `m3_path.gpu_track_events` + `LineageHistory.record`. Both read only the Sink slot positions (`kv_cache1[*]["pos"]`) and `kv_cache_starts` | `mobility_node.py`, `m3_path.py` | [V] |
| The native pipeline (`models/wan/causal_stream_inference.py`) has the same `kv_cache1` slot positions and `kv_cache_starts`, updated inside `inference_stream`, which upstream calls once per chunk | code | [V] |
| The tracker bound to a stand-in over a fake pipeline gives the harness's events: one refresh, one shift by -1 | local check while drafting | [V] |
| GPU peaks per node are already recorded (`summary.node_end[*].peak_allocated_mb`); process host memory is not. `network.csv` has only machine-wide memory | `mobility_orchestrate.py`, `common.ResourceSampler` | [V] |
| Existing runs, analysed while drafting with `fig14_report.phases()`: source during transfer / its reference session +1.6 % (dog) / +2.0 % (butterfly), Fig. 7 OTTER, 10 runs; owner during staging / outside staging +1.7 % / +0.9 %, Fig. 11 Chain OTTER runs | `fig14_report.py` | [K] |

## 3. Conditions and runs

**14a native (new, 30 runs).**
- One host (D1: A), CUDA device 0, the Fig. 8b command and looped inputs (`fig8_native.prepare`).
- Variants:
  - `native`: upstream unmodified, the same command as Fig. 8b.
  - `wrap`: `fig14_native_track.py` patches `CausalStreamInferencePipeline.inference_stream` in its own process, with
    no tracking.
  - `track`: the same patch plus OTTER's M2 + M3 tracking after every call, starting at the first call.
- Grid: dog and butterfly x 5 reps x 3 variants. The variant order is rotated per rep.
- Wall time [H]: about 3 min per run, about 1.5 h.

**14a phases (no new runs):**
- Fig. 7 OTTER runs (10): the source's per-call time over the migration window, calls 30 to the switch, divided by its
  own uninterrupted reference session (`node_A/baseline_record.json` `service_s`, calls 40-159). The window's maximum
  (the round-1 snapshot stall) is reported separately, along with the destination's replay time per call.
- Fig. 11 Chain OTTER runs with staging (6): after the first move, the owner's per-call time while a staging flow is
  active (`m3_forward_done` intervals) divided by its per-call time outside them.

**14b memory (new, 10 runs).**
- New node flag `--mem_log` (record only, default off). At 2 Hz it records:
  - process RSS (`/proc/self/status` VmRSS),
  - torch GPU allocated and reserved,
  - the retained Sink bytes,
  - the staged Sink entries (M3 entry store payload bytes and count),
  - written to `node_<X>/memory.csv`. The sampler stops at the start of RUN_END, before anything is released.
- Runs:
  - Single: the Fig. 7 OTTER configuration, A -> B, 3 reps x dog / butterfly.
  - Chain: the Fig. 11 OTTER with staging, A -> B -> C -> D at 45 / 90 s, 2 reps x dog / butterfly.
- Wall time [H]: about 1 h.

**First step:** one `track` run (dog, rep 1) and one memory run (single, dog, rep 1), then `--sanity`.

## 4. Metrics (all measured unless labelled)

- **14a native:** per run, the median of upstream's per-chunk wall time over processed 40-159 (Fig. 8b parser), and
  tracking ms per call (median in the same window, from the wrapper). Per (workload, variant): the median over reps.
- **14a phases:** the ratios in section 3. Reported per workload as the median over runs.
- **14b, per node:** RSS at the first sample and its peak, GPU allocated / reserved peak, retained-Sink peak and end,
  staged-entry peak and end.
- **14b, per run:**
  - Sink size (`source_prepared.sink_nbytes`),
  - replay-log bytes sent (`xb_precopy_switch.log_bytes`; an upper bound on the resident log, which the destination
    drains as it applies),
  - switch bytes (`final_bytes`: in-flight state + metadata),
  - cluster-wide held state (the sum over nodes of retained + staged, at the end and at the peak).

## 5. Hypotheses [H]

| id | rule | prediction |
|---|---|---|
| F14-H1 | track / native <= 1.01 (median per-chunk time) on both workloads | about 1.001 (0.57 ms on 528 ms per call) |

**Reported, not tested:** track / wrap, wrap / native, 14a phases, all of 14b.
- If wrap / native > 1.01, the wrapper itself costs and H1's comparison is conservative. track / wrap is then the
  tracking cost; this is stated, and H1 is not re-evaluated.
- Predictions for 14b:
  - Destination GPU peak within 10 % of the source's steady allocation. Fig. 7 node_end: A 28.7 GB, B 30.3 GB
    peak allocated [V].
  - Retained Sink = 1.73 GB (dog) host per former owner.
  - Chain cluster-wide held state <= 3 x Sink.

## 6. Validity

- **14a native:** rc 0, all 120 window chunks present (as Fig. 8b), the looped input verified equal to the repeated
  original.
- **14a track:** the tracker recorded every call (`n_tracked` = calls).
- **14b:** the Fig. 7 / Fig. 11 validity of each run, and `memory.csv` present on every node used.
- Harness defect: fix, rerun, keep both records.

## 7. Procedure

1. Tooling:
   - `fig14_native_track.py`, `run_fig14.sh`, `fig14_report.py`, `plot_fig14.py`;
   - the node flag `--mem_log` and the orchestrator write of `memory.csv` on both RUN_END paths.
   - Regression: the five tests. Dry run of the memory runs (single and chain): `memory.csv` on every node, retained
     and staged bytes recorded.
2. Review D1-D5, then freeze.
3. On the testbed: `d0_remote.py pull`, `run_fig14.sh preflight`, `first`, `fig14_report.py --sanity`, then `native`,
   then `memory`. A's GPU is shared, so the two run one after the other.
4. Report and figures.

## 8. Plot specification (Fig. 6a canvas and axes box, style font sizes, no mechanism names)

- **fig14a_overhead:** per-call time increase (%) in three groups (Tracking, Transfer, Staging), two bars each
  (Low-refresh / High-refresh), median printed.
- **fig14b_memory:** Source and Destination, GPU allocated peak and host RSS peak (GB), with the retained Sink marked
  in the host bar.
- **fig14b_cluster:** Chain, retained + staged Sink per node at the run end (GB).
- Dry renders fit at 28 / 25 pt (no rotation).

## 9. Decisions (open)

| # | decision | recommendation |
|---|---|---|
| D1 | 14a host: A (simple, local to the run terminal) vs B (Fig. 8b's headline host) | [R] A, with native re-measured in the same session. Fig. 8b's B values stay as a reference |
| D2 | Reps: 5 per variant (as Fig. 8b) | [R] 5 |
| D3 | H1 threshold 1.01 (Fig. 8's integrated rule was 1.03) | [R] 1.01. Isolated tracking is predicted at about 0.1 %; native run-to-run IQR is about 0.1 % |
| D4 | 14a phases: existing Fig. 7 / 11 runs, descriptive (values already seen [K]), vs new runs with an unseen hypothesis | [R] existing runs, descriptive. They are frozen protocol runs; a test on them would not be blind |
| D5 | 14b: OTTER only, vs also the baselines' memory (GPU peaks of Full / P-full / R-full already exist in Fig. 7 node_end; host RSS would need new runs) | [R] OTTER with --mem_log, plus the baselines' existing GPU peaks as a reference row; no new baseline runs |
