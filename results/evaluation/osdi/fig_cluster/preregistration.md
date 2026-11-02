# Cluster-scale evaluation (E9): what OTTER buys at service level — preregistration DRAFT 1 (not frozen; simulation smoke-tested only)

**Everything in this experiment is SIMULATED.** The simulator is calibrated from measured single-migration records of
this repository and gated against held-out measured multi-move records. Every figure, caption, table and sentence that
uses its output says "simulated (calibrated from testbed measurements)". No simulated number is ever pooled with, or
plotted as, a measured one.

Labels: [V] verified in code or records, [H] hypothesis / expectation, [A] modelling assumption, [D] open decision.

## 1. Question

At cluster scale (many concurrent sessions, user mobility, site drains, finite GPUs and links), how much does OTTER improve
service compared with external migration methods?
- **Local-service share:** session time served by the GPU at the user's edge.
- **Stalls:** stalls longer than X s per session-hour.
- **Delay per move:** time without local service after a move.

At what network and memory cost does it do so (traffic per session-hour, peak and per-link bandwidth, retained / staged
memory per site)? Does versioned staging beat **budgeted naive replication** under the same memory budget (the M3
scalability question)?

## 2. Relation to existing work (disclosed)

- **Experiment T** (trace-driven M3, prereg v3.1 FROZEN 2a781f8, ON HOLD since 2026-10-18, `../expT/`) is not resumed or
  amended. Its trace findings carry over as facts [V]:
  - Lumos5G `tower_id` changes are connectivity transitions, not handovers.
  - MAWI samplepoint-F is a transit link.
  - Berlin V2X (RRC PCell) and UCC 4G are the closest public serving-cell traces (`../expT/mobility_trace_comparison.md`).
- **Measured inputs (calibration):** Figs. 5, 7, 8, 10. **Held out for validation:** Fig. 11 (Chain / Cancel, five methods, two workloads).
- **Numbers seen before this draft:** the validation and smoke results in section 8 (simulated; not results).

## 3. Model (`tools/sim/cluster_sim.py`)

| element | model | basis |
|---|---|---|
| sites | E edge sites on a grid; G GPU slots each, one session per GPU | SDV2: one session per L40S [V] (Fig. 8) |
| network | per-site egress / ingress links of capacity C, non-blocking core; flows share links by weighted max-min (fluid) | the testbed's per-node token buckets with one max-min allocation [V] (`../expT/deployment_model.md`) |
| memory | per-site host-memory budget M for retained / staged Sink versions, LRU eviction | M2 retains on the host [V] (`mobility_node.py` "host copy") |
| sessions | closed population N; exponential lifetime (mean 20 min) [A1]; refresh intensity drawn uniformly from the 20 inputs of Fig. 5 [V]; time per call t_call [V]; age advances only while served | Fig. 5, Fig. 8 |
| mobility | grid random walk, exponential dwell (mean `dwell_s`) [A2]; trace option in D1 | - |
| drains | each site drains at 0.1 / site-hour for 10 min [A3]; its sessions move to the nearest site with a slot | - |
| target | the user's site if it is up and has a slot; else the current site; else the nearest site with a slot (load fallback) | - |
| service states | local (owner = user's site), remote (served elsewhere: migration in progress or displaced), stall | Fig. 11 definitions [V] |

**Methods** (Fig. 7 / 11 semantics [V]):

| method | label | stall-free phase (remote) | stalled phase | reuse |
|---|---|---|---|---|
| Full | Full | - | whole state S (6.46 GB) at link rate, then overhead | - |
| Llumnix-style P-full | Llumnix | rounds S, fS, fS at the achieved rate | final fS, overhead | - |
| ServerlessLLM-style R-full | SLLM | inputs a0 · b_in; recompute a0 calls (o1 + a0 t_call) | the calls made meanwhile × t_call (+ o2) | - |
| OTTER w/o staging | Unstaged | base (full Sink, or a versioned delta vs a version the target retains) + input log / patch flow at its measured rate; readiness = max(start + floor, base done + tail) | the last `interruption` s before readiness | old owner retains its version |
| OTTER | OTTER | the same | the same | + staging at every user move: forward versions from non-owner holders to the k sites nearest the user (all non-user, non-owner sites in the testbed replay), versioned deltas, one flow at a time per holder |
| budgeted naive replication | Replicate | OTTER's migration | the same | at every user move the owner pushes full Sink copies to the same k sites under the same budget; a copy is usable only if the Sink has not refreshed since it was made |

A migration in its stop / switch phase completes before a new move redirects it, as the harness does (`_xb_cancel`
cancels only tasks in `copy`) [V]. Full's stop-and-copy is redirected (Fig. 11 Full "resends whole") [V].

## 4. Calibration (`tools/sim/calib.py` -> `calibration.json`; every value computed from a record, path per value)

| parameter | value (dog / bfly) | record | derivation |
|---|---|---|---|
| t_call | 0.556 / 0.557 s | fig8 `8b.otter_per_call` | median per call, OTTER on B |
| Full state S, overhead | 6.463 GB; 2.53 / 2.52 s | fig7 `full.tx_gb`, `delivery_gap_s` | gap − S / 1 Gbps |
| P-full dirty fraction f, efficiency | 0.845 / 0.881; 0.854 / 0.858 | fig7 `precopy_full.tx_gb`, `remote_wall_s` | tx = S (1 + 3f); pre-copy bytes / 1 Gbps / remote time |
| R-full o1, o2, input bytes / call | 1.72 / 1.71 s; ~0; 1.33 / 1.01 MB | fig7 `recompute_full` | remote − a0 t_call (a0 = 30); gap − n t_call |
| OTTER Sink, base efficiency, base overhead | 1.728 GB; 0.850; 2.34 s | fig10 full / ver `base_ready_s` | two-point fit (full base vs age-10 delta) |
| OTTER tail, floor, interruption | 3.87 / 4.36; 8.83 / 9.07; 1.48 / 1.54 s | fig10 `readiness_s`, `interruption_s` | medians over ages |
| OTTER delta bytes vs version age | dog 12 / 22 / 22 / 50 MB, bfly 98 / 328 / 395 / 434 MB at ages 10 / 60 / 150 / 240 | fig10 `ver.base_bytes` | measured points |
| OTTER patch rate | 1.5 / 20.9 MB/s | fig7 `precopy_replay.tx_gb` | (bytes − Sink) / TTFO |
| refresh intensity | 20 inputs, 3.6-128.2 / 100 calls | m123 `fig5_inputs` | - |

Inputs between the two calibrated workloads are placed by log refresh intensity [A4].

**Assumptions.**
- **[A5] Delta bytes.** Versioned delta bytes are linear between the measured ages, extrapolated past 240 calls with the
  150-240 slope, and capped at the Sink size. Long-lived versions are not measured (D5).
- **[A6] Base efficiency.** OTTER's base uses the dog (patch-free) efficiency; patches are a separate rate-capped flow.
- **[A7] In-flight staging.** A staging flow already in flight into the destination completes first and is part of the base.
- **[A8] Staging sequence.** Staging flows of one session from one holder run one at a time, as the planner sequences them.
- **[A9] Commit phase.** A migration in its commit phase is not cancelled.
- **[A10] P-full dirty fraction.** f does not depend on round length. At 10-25 Gbps a round is shorter than the 6-call
  ring, so this may overstate P-full's cost (D6).

## 5. Validation gate (before any cluster result counts)

`cluster_sim.py validate` replays the testbed scenarios:
- **Setup:** four sites, 1 Gbps; trigger at call 30; A → B at 0 s.
- **Chain:** then C at 45 s and D at 90 s. **Cancel:** then C at 48 s and D at 60 s.
- **Staging candidates:** every non-user, non-owner site, as the testbed planner.

**Gate.** Every held-out Fig. 11 quantity must be within **max(15 % of measured, 2 s)** for every method × scenario ×
workload (76 quantities):
- the median per-move TTFO-local where the move completed;
- N;
- R_D.

Fig. 7 is calibration data and is reported only as a fit check. **If the gate fails:**
- no cluster result counts;
- the cause is diagnosed from the event logs;
- a model change is made before freezing, recorded with its reason, and the gate is rerun.

The tolerance is D3.

## 6. Metrics (window: after a 30-min warm-up)

1. **Local-service share** (% of session time); remote and stall shares.
2. **Stalls > X s per session-hour**, primary X = 1 s (D4, decided); X = 2, 5, 10 s as sensitivity. OTTER's cutover
   interruption is ~1.5 s, so X = 1 s counts every OTTER migration as a stall: the conservative choice (X = 2 s would drop
   them all and favour OTTER). X is an operational threshold, not a validated perceptual one.
   **Total stalled seconds per session-hour** is reported with every count.
3. **Delay per move:** time without local service after a user move, truncated at the next move (Fig. 11 rule; censored
   moves kept as truncated); share of moves reaching local service.
4. **Traffic** per session-hour by kind (migration, patch/log, staging); peak aggregate Gb/s; per-link utilization p50 / p99.
5. **Retained / staged memory** per site (time mean, peak).
6. **Reuse ratio** (migrations whose base was a delta / fresh copy) and **GPU-seconds** of destination slots per session-hour.

## 7. Sweep (`GRIDS["primary"]`, D2)

| knob | values |
|---|---|
| E (sites) | 16 (4 × 4) |
| G (GPUs per site) | 8 |
| N (sessions) | 32, 64, 96, 120 (load 0.25-0.94) |
| C (site link) | 1, 10, 25 Gbps |
| M (memory budget per site) | 0, 8, 32, 128 GB |
| mean dwell | 60, 180, 600 s (60 / 20 / 6 moves per hour) |
| k (staging candidates) | 4 |
| seeds | 3 |
| methods | Full, Llumnix, SLLM, Unstaged, OTTER, Replicate |

- **Runs:** 2,592, each 2.5 simulated hours.
- **Wall time:** measured 0.6-6.7 s per run at the heaviest point (N 120, dwell 60 s), so about 1-3 h on the Mac.
- **Primary point** (figure, hypotheses): N 64, C 10 Gbps, M 32 GB, dwell 180 s.

**Hypotheses (DRAFT, [H]; D7):**
- **CL-H1 (service).** At the primary point, OTTER's stalls > 1 s per session-hour ≤ 0.1 × the minimum over Full, Llumnix and
  SLLM, and OTTER's local-service share ≥ that of each of them.
- **CL-H2 (versioned vs naive under one budget).** At every M > 0, OTTER's mean delay per move ≤ Replicate's, and OTTER's
  staging bytes per session-hour ≤ Replicate's.
- **CL-H3 (where staging helps; descriptive).** The region of (C, dwell, M) where OTTER's delay per move < Unstaged's by ≥ 10 %.
  The smoke test already shows OTTER *worse* than Unstaged at 1 Gbps (staging competes with migrations). This is reported
  as a map, not a win.

## 8. Smoke test (2026-11-01; simulated; NOT results; nothing here is a hypothesis test)

**Validation: gate FAIL, 70 / 76 within tolerance.**
- **Within tolerance:** all Full, Llumnix, Unstaged and OTTER quantities, and R-full Cancel.
  - Errors: Full ≤ 3 %, Llumnix ≤ 1 %, Unstaged ≤ 6 %, OTTER −14 to +8 %.
  - OTTER's first move is 7-11 % low because the model omits M3's entry-path cost, Fig. 11 §3b.
- **Misses (6): R-full Chain** (dog and bfly: N, R_D, D's TTFO; +16 to +56 %).
- **Diagnosis** (event log of `expF11_chain_dog/policy=recompute_full_..._rep=1`):
  - At the move to D the B → C task was already finishing (the source had stopped at 89.4 s), so it completed (C resumes
    at 129.3 s), as the harness rule says (`_xb_cancel` cancels only `copy` tasks). The simulator follows that rule.
  - The next task C → D then started with round-1 **target 30** (`xb_task_start` x3) instead of C's current call (145).
    Its round 1 lasted 16.4 s, and the stall recomputed 146 calls (82 s).
  - Target 30 is consistent with a stale source call read at the instant of C's resume (`_xb_src_call`). This is a
    suspected harness defect, not modelled: the simulator uses the method's definition (target = current call).
  - This affects only R-full Chain's measured R_D / N, in R-full's favour. Fig. 11's verdicts compare against the best
    external method, which is Full, so they are not affected.
  - **Confirmed and fixed (2026-11-01, D8).** `_xb_src_call` returned `migration_chunk` (30) whenever the source had
    reported no METRIC yet, i.e. a task started right after the source's own resume. A scan of every recompute run in
    `results/evaluation` finds it in all 6 Fig. 11 Chain R-full runs (dog, bfly x 3 reps; task x3, C -> D, target 30
    instead of 145 / 146) and in no other measured experiment (Fig. 11 Cancel, Fig. 7 and earlier R-full runs: none). The
    fix takes the later of the last METRIC + 1 and the source's last resume call. R-full Chain dog / bfly are re-measured
    on the testbed; the old runs are kept; Fig. 11 is corrected with the new runs; the gate is re-run on them
    (section 10). Expected direction [H]: the correct round 1 recomputes ~145 calls while C serves, so R-full Chain gets
    slower, not faster.
- **Fig. 7 fit:** Full / Llumnix / SLLM within 0.3 %, OTTER −3 % / +6 %.

**Validation after the D8 re-measurement (2026-11-02): gate PASS, 76 / 76 within tolerance** (`validation.json`).
- Fig. 11 R-full Chain re-measured at run commit cca4ebda (6 runs; every C -> D task now targets C's resume call
  146 / 147). Measured N 286.2 / 285.8 s, R_D 204.4 / 204.2 s (dog / bfly; 226.0 / 225.3 and 143.7 / 143.5 before).
- The simulator and `calibration.json` are unchanged since 43a8ef46 (no refit after seeing the new runs); the whole
  corrected Fig. 11 table is used, not selected values. The 6 former misses are now within tolerance: dog N +7 %,
  R_D / D's TTFO +10 %; bfly N -8 %, R_D / D's TTFO -12 %. The two workloads measure the same (204 s), while the model
  splits them (225 vs 180 s): the per-workload R-full constants calibrated from Fig. 7 (t_call, round-1 and finish
  overheads) differ, which the Chain measurements do not show; noted, not changed.

**Smoke sweep:** E 16, G 4, N 48, C 1 / 10 Gbps, M 0 / 16 GB, dwell 60 / 180 / 600 s, 1 seed, 1.5 h; 72 runs in 36 s.
- **Model sanity:** R-full is compute-bound (identical at 1 and 10 Gbps); Full stalls > 2 s about 14 times per session-hour at
  10 Gbps (14.3 at dwell 180 s, M 16 GB); OTTER and Unstaged have 0 stalls > 2 s.
- **Staging hurts at 1 Gbps:** delay per move OTTER 73 s vs Unstaged 59 s.
- **No staging gain at 10 Gbps / 16 GB:** readiness is bound by the replay floor (~9 s), and displacement by full sites
  dominates delay per move.

## 9. Figure plan (one figure, three panels; Fig. 6a canvas 5.83 × 4.78 in, axes box [0.18, 0.22, 0.79, 0.75]; 28 / 19 / 25 pt; legend as its own file)

- **(a) Local service (%)** vs moves per hour, six methods, at the primary point.
- **(b) Delay per move (s, log)** vs link capacity.
- **(c) Delay per move (s)** vs memory budget: Unstaged, OTTER, Replicate.
- **Caption:** begins "Simulated (calibrated from testbed measurements, validated against Fig. 11)". Traffic and memory go
  in the text or a table.
- **Labels:** method names Full, Llumnix, SLLM, Unstaged, OTTER, Replicate; no internal mechanism names.
- **Tools:** `tools/sim/plot_cluster.py`. The smoke figures (`_smoke_figures/`) are a layout check only.

## 10. Procedure

1. `python3.11 tools/sim/calib.py` → `calibration.json` (committed with the freeze).
1b. D8: re-measure Fig. 11 R-full Chain (dog, bfly; 3 reps each) with the fixed harness (`run_fig11.sh rfull_chain`); the
    gate uses the new runs; the old ones stay on disk and in Fig. 11's corrections section. **Done 2026-11-02** (gate PASS 76 / 76).
2. `python3.11 tools/sim/cluster_sim.py validate` → `validation.json`: gate PASS required (section 5).
3. Freeze (after D1-D9).
4. `python3.11 tools/sim/cluster_sim.py sweep --grid primary`, then `plot_cluster.py --grid primary`, then a report.

## 11. Decisions (D1, D4, D8 decided 2026-11-01; D2, D3, D5, D6, D7, D9 after Fig. 12a / 14 are prepared)

| # | decision | options / recommendation [R] |
|---|---|---|
| D1 | mobility source | **DECIDED (user, 2026-11-01): parametric grid random walk with exponential dwell (implemented) is primary.** Public traces (Berlin V2X / UCC 4G) later as a sensitivity block if time allows. The paper says "simulated mobility" and does not claim it represents real user movement. |
| D2 | sweep ranges and primary point | section 7; real edge links are 10-100 Gbps (ExpT deployment model) |
| D3 | gate tolerance | max(15 %, 2 s) |
| D4 | stall threshold X for CL-H1 | **DECIDED (user, 2026-11-01): primary X = 1 s** (counts OTTER's ~1.5 s cutovers; X = 2 s would exclude them all and favour OTTER); sensitivity 2 / 5 / 10 s; total stalled seconds per session-hour reported with them. Operational threshold, not a validated perceptual one. |
| D5 | delta bytes beyond 240 calls | extrapolate (implemented) vs measure Fig. 10 at ages 1,000 / 3,000 on the testbed first. [R] measure (cheap; affects reuse at minute-scale dwell) |
| D6 | P-full dirty fraction at high bandwidth | constant (implemented) vs round-length-dependent; [R] constant + sensitivity, or a measured round at 2.5 Gbps from Fig. 12a |
| D7 | hypotheses CL-H1 to H3 | confirmatory vs descriptive |
| D8 | R-full Chain gate miss | **DECIDED (user, 2026-11-01): (a)** confirm, fix, regression, re-measure Fig. 11 R-full Chain dog / bfly, keep both records, re-run the gate on the new runs. If the new runs change Fig. 11's R-full numbers, Fig. 11 is corrected; measured values are never swapped selectively to pass the gate. Defect confirmed and fixed (section 8). |
| D9 | staging candidate rule at scale | k = 4 nearest sites to the user (implemented; the testbed planner stages every non-user, non-owner node, infeasible at 16 sites); staging traffic at equal max-min weight (harness) vs lower priority |
