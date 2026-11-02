# Fig. 14 preregistration: OTTER's overheads (FROZEN 2026-11-02; DRAFT 1 + user D1-D5; nothing run)

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

**14a three configurations (user, 2026-11-02): native, tracking-only, OTTER integrated.** Tracking-only (the `track`
variant above, host A) measures the metadata bookkeeping only; it never stands for OTTER's whole cost. Fig. 8b found
OTTER integrated about 5.4 % slower than native while tracking was about 0.1 %, so the integrated cost is measured in
the same session and decomposed:
- `native_only` on host B (`LB=B`, 5 reps x 2 workloads = 10 runs, at the same time as A's runs): B's native baseline.
- `integrated` (10 runs, after both): Fig. 8b's OTTER command unchanged (M1 + M2 + M3 flags, one migration A -> B,
  1,500 post calls), experiments `expF14_int_<w>`; B's steady-state per-call time after the cutover = generation +
  tracking (Fig. 8b's window and validity, `fig8_report.otter_run`), and A's uninterrupted harness reference session
  (no OTTER code, `node_A/baseline_record.json`, calls 40-159).
- Each ratio uses its own host's native, measured in this session: tracking-only A / native A; integrated B /
  native B; harness without OTTER A / native A. The last separates the harness's own cost from OTTER's within the
  integrated gap; if integrated B / native B stays about 1.05, its source is analysed (reported, not hypothesised).

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

**Reported, not tested:** track / wrap, wrap / native, integrated B / native B, harness A / native A, 14a phases,
all of 14b. H1 tests tracking-only; it is never reported as OTTER's overall overhead.
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

## 9. Decisions (user, 2026-11-02)

| # | decision |
|---|---|
| D1 | 14a tracking-only on host A with native re-measured on A in the same session; the integrated configuration on B with native re-measured on B in the same session (each comparison on one host) |
| D2 | 5 reps per variant |
| D3 | F14-H1 tracking-only / native <= 1.01 |
| D4 | 14a phases from the existing Fig. 7 / 11 runs, descriptive |
| D5 | 14b OTTER with --mem_log. The baselines' GPU peaks from Fig. 7 `node_end` are a reference row only: their workload length, instrumentation and sampling differ, so they are not a direct comparison and no claim compares them with OTTER's |
| added | three configurations native / tracking-only / OTTER integrated, each against its own host's native |
