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

## 10. Outcome (2026-11-03; all runs on commit ccc6c06, analysed against sections 4-6 unchanged)

**Runs and validity.** 14a native: A native / wrap / track 5 reps x dog / butterfly, B native_only 5 x 2; all with
rc 0, 120 window chunks each, and every call tracked. Integrated: 10 of 10 valid. 14b memory: 10 of 10 valid under the
Fig. 7 / Fig. 11 rules (switchovers verified, SINKOK, no fallback, M3 checks true in the chain runs), `memory.csv` on
every node used. The `fig14_results.md` written on elves-01 lacked B's native files (pushed separately from
elves-02); the report was rerun on the merged data (no code change).

**F14-H1 SUPPORTED.** track / native = 1.0009 (dog), 1.0006 (butterfly) <= 1.01. wrap / native = 0.9998 / 0.9994,
so the wrapper costs nothing measurable. Tracking 0.39 / 0.40 ms per call (prediction 0.57 ms, about 1.001).

**Reported, not tested (14a).**

| quantity | dog | butterfly |
|---|---|---|
| tracking-only A / native A | 1.0009 | 1.0006 |
| OTTER integrated B / native B | 1.0555 | 1.0528 |
| harness without OTTER A / native A | 1.0457 | 1.0472 |
| integrated B per call: generation + tracking | 0.5561 s + 0.57 ms | 0.5552 s + 0.58 ms |
| source during transfer / own reference (Fig. 7, n 5 each) | 1.016 (1.012-1.022) | 1.020 (1.017-1.024) |
| owner during staging / outside (Fig. 11, n 3 each) | 1.017 (1.016-1.018) | 1.009 (1.008-1.009) |

Analysis of integrated about 1.05 (section 3 asked for it): tracking is 0.1 %; the harness's uninterrupted session
without any OTTER code is already 4.6-4.7 % slower than native on A. In absolute time the integrated generation on B
(dog 0.5561 s) equals A's harness session without OTTER (0.5563 s); B's native is 0.9 % faster than A's. So most of
the 5.4 % is the harness serving path, not OTTER. The remaining 0.6-0.8 points are a cross-host comparison and are not
attributed.

**14b memory (measured).** All MB are MiB (2^20 bytes).

- Retained Sink: 1,645.3 MiB = 1.73 GB per former owner, on both workloads: prediction met. It is held in host memory
  (RSS rises by the same amount at the switch; GPU allocation does not).
- Source after its switch: GPU allocated drops to 20.15 GB (model only).
- Destination GPU peak vs the source's steady serving allocation (26.49 GB, single runs): 1.064-1.121 (dog 1.121,
  1.104, 1.081; butterfly 1.084, 1.087, 1.064). The prediction "within 10 %" holds in 4 of 6 runs; dog reps 1 and 2
  exceed it (12.1 %, 10.4 %). After the switch the destination stays at 28.05 GB (+1.57 GB, 1.059 x the source) for
  the rest of the run. Candidate cause (not verified): the destination keeps its replayed recent-slot clones
  (`replay_switch` `self._replayed`) after writing them back.
- Chain: the intermediate owners B and C peak at 34.46-36.61 GB allocated (1.30-1.38 x), each when it starts its own
  outbound migration (B at about 49 s, C at about 94 s); reserved peak 37.8 GB of the L40S's 46 GB. The first source
  (A) peaks at 27.0-28.0 GB and the last destination (D) at 28.1-29.4 GB. The prediction did not cover a re-migrating
  owner; the extra 6.4 GB is measured, its cause is not analysed.
- Chain cluster-wide held state: 11,517 MiB = 7 x Sink at the run end, and the same at the simultaneous peak
  (retained on A, B, C + staged entries on A, B, C, D). The prediction "<= 3 x Sink" is NOT met. Each former owner
  holds the same Sink version twice (retained buffer and staged entry store), and D holds a staged copy it never used
  as an owner before the run end. Nothing is released before RUN_END in this configuration.
- Process RSS includes the harness (the reference session's frames in RAM): first samples 25.6-27.3 GB in single runs
  (1,530-call reference) vs 14.1-15.1 GB in chain runs (830-call reference). The RSS increase is the comparable
  number: single source +5.1-5.3 GB, chain A/B/C +5.2-5.8 GB, chain D +1.8-2.1 GB.

**Wall time.** The estimate [H] "about 1 h" for 14b was wrong: each run regenerates the uninterrupted reference on
every warm node before the run (single about 31 min, chain about 19 min per run); the 9 remaining memory runs took
about 4 h. No criterion depends on it.

**Figures** (`figures/`, section 8 spec, fonts unchanged): fig14a_overhead, fig14b_memory, fig14b_cluster. The host
bar of fig14b_memory is the RSS peak as specified, which includes the harness reference frames; see the open question
below.

**Open (user decision):** fig14b_memory host bar as RSS peak (spec) or RSS increase (comparable across scenarios).

## 11. Memory audit (2026-11-03; code and existing logs only, no new runs, no change to M1 / M2 / M3)

Requested by the user before Fig. 14 is final. Units: MiB as logged (`memory.csv`, torch allocated / 2^20), GiB =
MiB / 1024.

**Erratum to section 10.** Section 10 calls 26.49 GB "the source's steady serving allocation". That is wrong: 26,489 MiB
is the source while it holds its transfer snapshot (below). The source serving without migration state allocates
20,164 MiB (median of its samples before `source_prepared`; 20,163-20,165 in all 10 runs, now in
`fig14_results.json` as `src_serving_alloc_mb`). Section 10's GPU figures are also MiB / 1000 labelled GB (e.g.
"34.46-36.61 GB" = 34,455-36,608 MiB = 33.6-35.8 GiB). The numbers below replace them.

**A1. GPU allocation, decomposed (verified: code path + allocation steps in every run).**

| component | MiB | where it comes from | lifetime in these runs |
|---|---|---|---|
| model + live session | 20,164 | serving | whole run |
| full-state snapshot | 6,311-6,334 | `state_ablation.serialize_state`: a GPU deep copy of every component (KV Sink + recent, VAE feature caches, cross-attention, latents) | source: from the round-1 snapshot until the round-1 send ends (A about 17 s; a re-migrating owner about 18 s) and about 1 s at the switch. Destination: `provision()` at launch (the receive snapshot), held until RUN_END |
| replay clone (`replay_switch` `self._replayed`) | 1,645 clone, net +1,572 after the switch | the destination's recent-slot clones, written back at the switch | until RUN_END: released only in `replay_verify`, which these runs do not enable (`--replay_verify` off) |
| Sink clone (`replay_switch` `sk`) | 1,645 | the destination's Sink clone during the switch | deleted at the switch (the 29,698 MiB single-run destination peak = 28,053 + 1,645) |

Every plateau matches the sum:
- source serving 20,164; source during round 1: 20,164 + 6,334 = 26,498 (measured 26,479-26,516);
- warm destination before the switch: 20,164 + 6,311 = 26,481 (measured 26,481 on every warm node);
- destination after the switch: 26,481 + 1,572 = 28,053 (measured 28,053-28,062, to the run end);
- re-migrating owner (chain B, C) during its round-1 send: 28,053 + 6,334 = 34,387 (measured plateau 34,397-34,493).
- Unexplained: a transient up to +2.2 GiB for under 1 s at the end of chain dog rep 1's base send on B (36,608 MiB);
  the other 7 re-migrating owners peak at 34,455-34,747. Not identified.

Reading: the extra GPU memory is the harness / frozen implementation holding whole-session deep copies, not state
that M1-M3 need. M1's round 1 sends only the Sink and metadata (1,645 MiB of the 6,334 MiB snapshot); the receive
snapshot is allocated for every policy (Full needs all components, OTTER does not); the replay clone is a dead
reference after the write-back. A minimal implementation's footprint is NOT measured; any number for it is an
estimate.

Prediction "destination GPU peak within 10 % of the source's steady allocation", three readings (reported, not
tested; no verdict changes):
- vs the source serving without migration state (20,164 MiB): destination peaks 28,173-29,698 = 1.40-1.47 x, 0 of 6.
- vs the source during its transfer (26,489, section 10's reading): 1.064-1.121, 4 of 6.
- vs the source's peak (the prereg's [V] evidence compared peaks, 28.7 vs 30.3 GB): 1.030-1.115, 5 of 6.

**A2. Re-migrating owner (+6.3 GiB).** Fully explained by A1: the owner still holds its receive snapshot and replay
clone from the inbound migration and adds the outbound transfer snapshot. Its round-1 send is longer than the first
source's (the M3 base is sent entry by entry, 180 entries, 17.7 s), so the plateau lasts about 18 s per hop. Reserved
peak 37,826 MiB (36.9 GiB) of the L40S's 46,068 MiB.

**A3. Retained / staged Sink on the testbed (verified in code).**
- M2 retained copy: `retain_sink(snap)` -> host buffer `r["retained"]["buf"]` at the switch; released only at
  RUN_END (`r.pop("retained")`).
- M3 entry store: `_m3_handover_build` reads that retained buffer and puts every entry into `EntryStore` as a new
  `bytes(bk) + bytes(bv)` payload (role "retained"). So each former owner holds the same version twice (buffer +
  entry store). Staged entries from forwards go to the same store.
- `EntryStore` keeps one version per entry (newer replaces older) with no budget, no eviction and no drop when the
  node becomes the owner; D keeps its staged copy while it serves the live Sink.
- Hence 7 x Sink at the chain's end: A, B, C (retained + entry store) and D (entry store).

**A4. E9 memory accounting vs the testbed.** `cluster_sim.Store`: one entry per (site, session), the retained or the
staged version (a put replaces it), the new owner drops its entry (`store[owner].drop`), LRU under the per-site
budget M. For this chain it would hold 3 x Sink (A, B, C), the testbed 7 x. E9 models host memory only (GPU snapshots
are outside its model; one session per GPU). So E9's memory results and its budget sweep (M = 0 / 8 / 32 / 128 GB,
CL-H2, panel (c)) describe a deduplicated, budgeted store that the testbed does not implement. This is an unstated
modelling assumption of E9, now labelled [A11] here; nothing in E9 is re-run or re-judged by this audit.

Options (user decision; none started):
1. State [A11] in E9 and report the testbed's 7 / 3 factor next to E9's memory numbers.
2. E9 sensitivity: count 2 x Sink at each former owner and no drop at the new owner (the testbed's accounting); a
   new simulation, needs approval.
3. A separate optimization on the testbed (share the retained buffer with the entry store; drop staged entries when
   the node becomes the owner; release the receive snapshot / replay clone; snapshot only Sink + metadata for
   round 1), with regression and a short new measurement. It does not change any frozen result.
