# M3 audit: what exists, what it shows, and its fit with the frozen M1 / M2 (2026-10-29)

Read-only audit. No code, run, result or verdict is changed. M1 / M2 below are the frozen mechanisms of
`m1_continuity/` (input-log replay with replay-aware Sink synchronization; versioned Sink reuse with digest-verified
delta bases), frozen at 47acbe44 (E10, `m1_continuity/e10_record.md`).

The older OTTER documents use "M1" and "M2" for different mechanisms:
- **old M1:** "Temporal State Decomposition". Immediate state goes on a fast path, the destination generates without
  the Sink, and a trigger-time Sink snapshot is bound later.
- **old M2:** "Continuity Wavefront". Verified fragments are preserved across moves.

This audit writes **oldM1 / oldM2** for those and **M1 / M2** for the frozen pair.

Markers: **[V]** verified from repository files or logs (path given); **[H]** hypothesis or inference;
**[R]** recommendation.

---

## 1. Inventory of M3 work

### 1.1 Lineage (commits and documents) [V]

| stage | date | where | what |
|---|---|---|---|
| M3 research plan, TOPOLOGY_PLAN v1-v3 | 10-15 | `results/evaluation/TOPOLOGY_PLAN.md` (e3dd1f8, 7d1e916, 67a32b1: criteria H5 / H6 / H8 frozen) | "Progress-Aware Topology Morphing (M3) stays **provisional**"; Experiments A (pre-positioning), B (dissemination plans), E (topologies under mobility), C (re-planning on deadline changes) |
| Experiment A (pre-positioning), network level | 10-15 | `restore_prepos_pilot*`, `restore_prepos_a3*`, `restore_holder*` notes | placement policies none / oracle / top1 / greedy / proportional / coverage |
| Experiment B (dissemination: star / line / tree / multipath / aware), network level | 10-15 | `restore_dissem_pilot_notes.md` (5 runs), `restore_dissem_hetero_notes.md` (45 runs) | commits 4787218, ccd57d6 |
| E.4 event-driven re-planning `reuse_dyn` (M3-v1), E-pilot v1 / v2, network level | 10-15 | `restore_epilot_notes.md`, `restore_epilot_v2_notes.md` (21 + 21 runs) | commits 7d759dd, 85588c6 |
| Full Experiment E: restart / pp_star / fixed_line / fixed_tree / fixed_butterfly / aware / dyn, network level | 10-16 | `restore_fulle_notes.md` (84 runs, commit 55c3a07) | H8a-c |
| Shared planner `restore_planner.py` (both harnesses) | 10-16 | `osdi/d0/shared_planner.md`, `tools/eval/test_restore_planner.py` | equivalence with e345ccd: 0 diffs |
| Experiment D (GPU end to end; M3-v1) | 10-17 | `osdi/expD/expD_report.md` | G4, G5, G7 (+ scenario C / D reproduction `expDR_*`, a0fbae6) |
| Experiment T (traces) | 10-17 | `osdi/expT/` (frozen 2a781f8), **on hold** (`expT/HOLD.md`, c765876) | nothing run |
| Experiment N (GPU, M3-v1 network adaptation, 10 cells) | 10-18/19 | `osdi/expN/preregistration.md`, `osdi/wrn_report.md`, `osdi/wrn_results.md` (90 runs) | |
| Root cause of M3-v1 failures | 10-19 | `osdi/expN/m3_root_cause.md` (eb54d99) | |
| M3-v2 `reuse_dyn2` (design, development, GPU regression on N cells 7-10) | 10-19 | `osdi/expN/m3v2_design.md`, `m3v2_gpu_regression{,_r2}.md`; frozen **e39609a** (`osdi/m3v2_freeze.md`) | development data, not evidence |
| Experiment V (M3-v2 holdout, 96 runs) | 10-19/20 | `osdi/expN/m3v2_holdout_plan.md` (+ Amendment 1), `osdi/expN/expV_report.md` | `expV_cell4..7`, `expV_a1_cell{1,2,3,8}` |
| Experiment M3E (final OTTER with M3-v2, repeated moves) | 10-20 | `osdi/expM3E/` (frozen abf74d6), `m3e_report.md` | 48 runs (+1 re-run) |
| Experiment WX (workload expansion of R / M3E) | 10-21 | `osdi/expWX/` (frozen a181126), `wx_report.md` | 144 runs |
| EXEC_START defect audit and disposition | 10-23/24 | `osdi/exec_start_impact_report.md`, `exec_start_disposition.md` | N / V ran with an idle source |
| Claims list (M3 = "Restoration Graph Morphing") | 10-20/21 | `osdi/paper_claims.md` | M3-1, M3-2, M3-3 |

Run counts checked in this audit (number of `summary.json` files) [V]: `expN_cell*` 90; `expV_cell*` 96 plus
`expV_a1_cell*` 48. The verdict set is 96 runs: `expV_cell4-7` 48 plus `expV_a1_cell1,2,3,8` 48.
Further counts: `m3dev*` 24. `expM3E_S1-S5` has 58 files, which is 49 runs: 48 plus 1 re-run; each hybrid S1 run also
carries a nested network-session summary. `expWX_*_X*` has 171 files, which is 144 runs; the hybrid X4 runs are
nested the same way. Then `expD_F` 12; `expD_D` 12; `expDR_*` 24; `restore_fulle` 84; `restore_epilot*` 42;
`restore_dissem_hetero` 45; `restore_dissem_pilot` 5.

### 1.2 Status of each item

| item | status | evidence |
|---|---|---|
| **M3-v1** (`reuse_dyn`: bottleneck provider's fragments re-assigned when dT > C_switch + max(eps, rel · ETA); E-pilot v2 hysteresis) | **Implemented and validated, with negative results; frozen** | Network: E-pilot v2 has 0 premature re-plans and 0 oscillations in 21 runs; Full E H8b SUPPORTED. GPU: ExpD G7 SUPPORTED, G5 NOT SUPPORTED. N: cells 7, 8, 9 (re-plan clause) and 10 NOT SUPPORTED |
| **M3-v2** (`reuse_dyn2`: ingress-aware bottleneck estimator, fragment-count windows, 2-fragment margins, max-min fluid ETA, 4-fragment single-provider probe) | **Implemented and validated; frozen e39609a** | V holdout (96 runs): V-H1 1/1, V-H2 3/3, V-H3 4/4, V-H4 6/8. M3E: H1-H7 SUPPORTED. WX: supported on 4 inputs |
| **Star / Line / Tree / Butterfly**, dissemination form (`dissem_assign`: star, line, tree, multipath, aware) | **Implemented and validated at network level only** | B pilot and heterogeneous subset (50 runs); every plan individually measured. No GPU, no generation. Full-grid H6f never run |
| **Star / Line / Tree / Butterfly**, mobility form (`pp_star`, `fixed_line`, `fixed_tree`, `fixed_butterfly` in `assign_providers`) | **Implemented and validated at network level only** | Full E (84 runs; every topology individually, 4 conditions × 3 reps). **Not available in the GPU orchestrator** (`mobility_orchestrate.py` has no fixed-plan policy; `AWARE` = `reuse_aware_in`, `reuse_dyn`, `reuse_dyn2`) |
| Adaptive restoration-graph construction: per-(fragment, destination) provider assignment over every verified holder (`reuse_aware`, `reuse_aware_in`) | **Implemented and validated**: network (B, E) and GPU (ExpD, V and M3E "at moves" arm) | "Butterfly" here means every past holder forwards, with the fragments split evenly. In B it is the disjoint-fragment multipath plan |
| **Explicit topology selection / "morphing"** as its own mechanism | **Designed, not implemented; the evidence argues against it** | Proposed in `TOPOLOGY_PLAN.md`. Two readings reject it. `restore_dissem_hetero_notes.md` reading 4: "no separate topology-selection mechanism justified". `restore_fulle_notes.md` "Implications": "Nothing in Full E required a topology abstraction". The graph changes only implicitly, through re-assignment of fragments |
| Shared-ingress handling: at plan time | **Implemented and validated** | `reuse_aware_in` H4c correction (`restore_holder_h4c_notes.md`) |
| Shared-ingress handling: in re-planning | **v1: absent** (root cause of the N failures). **v2: implemented and validated** | `m3_root_cause.md` causes 1-3; V (V1, V3, V6), M3E S3, WX X6 |
| Fragment-level progress preservation across moves (oldM2: verified fragments stay at holders; re-plans cancel flows and drain one fragment) | **Implemented and validated for oldM1 / oldM2**. **Not implemented for M1 / M2** (section 3.3) | R: discarded ≤ 0.061 Sink; ExpD G3 / G8; duplicates 0 in N, V, M3E; E-pilot: one 4 MiB fragment drained per re-plan |
| Re-planning and oscillation prevention | v1 hysteresis validated at network level (0 oscillations / 21) but **failed on GPU** (N cell 10: 28-32 re-plans). v2 **validated** (0 false positives in V, M3E, WX) | `restore_epilot_v2_notes.md`, `wrn_results.md`, `expV_report.md` |
| Pre-positioning (`prepos_alloc`, budgeted placement) | **Implemented and validated** (network A; GPU ExpD G4 SUPPORTED, G5 NOT SUPPORTED) | `expD_report.md`; scenario C / D reproduced (`expDR_*`) under corrected EXEC_START, G4 / G5 unchanged |
| Regression tests | **Exist** | `tools/eval/test_restore_planner.py` (pre-refactor equivalence); `test_m3v2.py` (units, fluid ETA, estimator, probe cycle, replay of frozen N streams; development); `run_planner_regression.sh` (loopback); `check_m3dev.py` (GPU regression conditions) |
| **96-run holdout** | **Executed** (not merely planned). First run 96 runs (91faa0a); Amendment 1 re-ran V1-V3 and V8 (48 runs, f731bd9); verdict set 96 valid | `expV_report.md` |
| Experiment C (re-planning on deadline changes) | **Planned, never executed**; no criteria written. It was conditional on a ≥ 15 % model gain | `TOPOLOGY_PLAN.md` D.4, line 326 |
| Experiment T (trace-driven M3) | **Frozen, never executed** (on hold) | `osdi/expT/HOLD.md` |
| Full-grid H6f; A1 / A2 pre-positioning items | **Planned, never executed** | `restore_dissem_hetero_notes.md`; memory and `TOPOLOGY_PLAN.md` |
| Four concurrent M3-v2 GPU sessions | **Never executed**. M3E S1 and WX X4 used network-level M3-v1 competitors | `m3e_report.md` section 3 |
| Fixed topologies on GPU | **Never executed** (not implemented in the GPU orchestrator) | above |
| **Any M3 policy with M1 / M2** (`precopy_replay`) | **Never executed; not implemented** | section 3 |

---

## 2. Measured results [V]

### 2.1 Fixed topologies vs adaptive assignment (network level, no generation, 4 hosts, 1 Gbps caps unless stated)

**Dissemination: one Sink from A to B, C and D.** Makespan in seconds; source Sinks in brackets.
Sources: `restore_dissem_pilot_notes.md`, `restore_dissem_hetero_notes.md`.

| condition | star | line | tree | multipath ("butterfly") | aware |
|---|---|---|---|---|---|
| uniform | 41.7 [3.00] | 14.1 [1.00] | 27.9 [1.00] | 14.0 [1.00] | 14.0 [1.00] |
| B_f = 500 | 41.7 | 28.0 | 55.6 | 18.6 | **16.9** [1.20] |
| B_f = 125 | **41.7** | 111.0 | 221.1 | 73.8 | 42.1 [2.18] |
| B_s = 250 | 166.0 | 55.6 | 55.6 | 55.4 | 55.4 |

**Mobility: A → B → C → D, rho 2.** T_r at the final owner in seconds; source Sinks in brackets.
Source: `restore_fulle_notes.md`, 84 / 84 valid.

| condition | restart | pp_star | line | tree | butterfly | aware (at moves) | dyn (M3-v1) |
|---|---|---|---|---|---|---|---|
| slow B (125 Mbps) | 14.0 [2.00] | 14.0 | 14.0 | 56.0 | 52.5 | 14.0 [1.38] | 14.0 [1.38] |
| shared source, N = 4 | 54.6 | 54.6 | 38.7 | 45.7 | 38.4 | 38.7 | 38.8 |
| C degrades to 62.5 Mbps | 14.0 [2.00] | 14.0 | 62.8 | 14.0 | 53.2 | 53.8 | **14.0** [1.18], 2 re-plans |
| revisit B | 14.0 | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 |

Reading:
- Each fixed topology fails in some condition: tree 56.0 s and butterfly 52.5 s with slow B; line 62.8 s under C's
  degradation.
- Aware assignment is never slower than the best fixed plan by more than 0.3 s in conditions 1, 2 and 4.
- The dynamic rule is on the Pareto frontier in all 4 conditions.
- Re-planning cost (E-pilot): transition 0.04-0.07 s, one 4 MiB fragment drained per re-plan, detection 2.26 s.

### 2.2 GPU (StreamDiffusionV2 generating; oldM1 / oldM2 execution model)

| experiment | M3 | key numbers | verdict |
|---|---|---|---|
| ExpD G7, scenario F (holder C degrades) | v1 | event-driven 15.80 s vs at moves 51.58 s (**3.26×**); 2 re-plans; 0 duplicates; no-change runs 0 re-plans | SUPPORTED |
| ExpD G5, incorrect placement | v1 | false-positive re-plan 2.28-2.30 s after the move; B_source 1.23 > 1.02 | NOT SUPPORTED |
| N cell 9 (holder egress 62.5 Mbps) | v1 | bind 15.072 vs 113.398 s (**7.52×**), 3 re-plans > 2, B_src 1.45 | **NOT SUPPORTED** (re-plan clause) |
| N cells 7 / 8 / 10 | v1 | +0.22 Sink; +3.5 s; 28-32 re-plans (+0.23 Sink) | NOT SUPPORTED |
| N cells 1-6 | v1 | 0 re-plans, neutral | SUPPORTED |
| V holdout (dog s0, single move, 96 runs) | v2 | V2 12.24 vs 44.95 s (3.7×), V4 19.12 vs 38.32 (2.0×), V5 21.57 vs 122.08 (5.7×); 0 false positives (v1: up to 9 re-plans); v2 is 4.1 s slower than v1 in V4 / V5 | V-H1 1/1, V-H2 3/3, V-H3 4/4, V-H4 6/8 |
| M3E (dog, rho 2, A→B→C→D) | v2 | S2 holder bottleneck 20.71 s vs at moves 52.13 (2.5×) and M1 + M2 78.53 (3.8×), 2 re-plans incl. 1 probe; S3 / S4 / S5 0 re-plans; TTFO within +0.08 s; service time within 0.2 % | H1-H7 SUPPORTED |
| WX (butterfly, audi-snow-trail, train; seed 0) | v2 | X5 20.39-20.79 vs 50.96-52.24 s; 0 re-plans in X3 / X4 / X6 | all imported hypotheses SUPPORTED |

### 2.3 Checks of previously quoted figures

- **"~7.5× improvement."** Supported by the logs (`wrn_results.md` row 9: 113.398 / 15.072 = 7.52). It is the
  **M3-v1, N cell 9** result, and that cell's frozen verdict is NOT SUPPORTED (3 re-plans > 2, B_source 1.45).
  It is development data for M3-v2. `m3_root_cause.md` line 59 groups it with "ExpD G7", but G7 measured
  **3.26×**. The holdout numbers for the final M3 are 2.0-5.7× (V), plus 2.5× vs at-moves and 3.8× vs M1 + M2 (M3E S2).
- **"G7 GPU experiment."** Supported: SUPPORTED, 15.80 vs 51.58 s, 3 reps. It used **M3-v1**, it is not affected by
  EXEC_START (scenario F is not on the affected list), and it ran under the oldM1 / oldM2 execution model.
- **Star / Line / Tree / Butterfly individually.** Yes at network level (B: star / line / tree / multipath; Full E:
  pp_star / line / tree / butterfly), each measured separately with 3 reps. Never on GPU.
- **EXEC_START caveat.** N and V ran with an idle source during the placement window. Verdicts are retained by the
  2026-10-24 disposition. Absolute latencies are optimistic by ≤ 0.64 s. V-H2 in V4 is fragile (margin 0.04 s), as are
  V-H3 in V8 and N-H3 in cell 3. M3E, WX, Full E and G7 are not affected.

### 2.4 Missing experiments

- Experiment C (deadline-driven re-planning).
- Experiment T (traces).
- Full-grid H6f.
- Concurrent M3-v2 GPU sessions.
- Fixed topologies on GPU.
- V on any input other than dog.
- More than one degradation magnitude or onset per cell.
- **Every M3 experiment under the frozen M1 / M2** (section 3).

---

## 3. Compatibility with the frozen M1 / M2

### 3.1 Is the restoration workload the same? **No** [V]

| | workload of every M3 experiment (oldM1 / oldM2) | frozen M1 / M2 workload |
|---|---|---|
| execution at the trigger | moves at once (TTFO 0.67 s); the destination generates **without the Sink** | **source keeps generating**; the destination resumes only at an atomic cutover after base + replay catch-up (interruption 1.4-1.9 s, E9 / E10) |
| restored object | one **immutable trigger-time snapshot** of the Sink (412 × 4 MiB fragments, SHA-256 each), bound late; stale versions tolerated | a **versioned, mutating** state: Sink base at boundary c0, **ordered** per-call input log with refresh patches, DR2 latents, in-flight / meta at the switch; Sink digest equality required at the cutover (SINKOK) |
| what restoration latency costs | Sink-less, diverged output until the bind (gap ~17 dB) | remote serving from the old edge until readiness. Output stays bitwise exact (E10) |
| moves | T_m 3.5-7 s < restoration time: many partial holders (past owners, pre-positioned nodes) | E3-E10 move only after a completed migration. In the XB path a move during a migration **cancels** it (`_xb_cancel`), and the new target starts from an empty store (`cmd_xb_prepare` resets `xb_store`) |
| holders | any node with verified fragments (`holders`, `FLOW_START` from its `r["sink"]["buf"]`) | only the running source sends (`PRECOPY_START`, one PFRAG connection). M2 retains one host copy of the last SINKOK version per node; a delta is sent only to the node that holds it |
| orchestrator path | `EXEC_MODE` "fast"; `plan()` / `plan_aware()`; `tick()` → `dyn_check{,_v2}` | `EXEC_MODE` "xb"; `execute_xb()` / `_xb_start()`; no planner and no flows |

Consequences:
- No M3 measurement transfers numerically to M1 / M2. This covers Full E, B, G7, N, V, M3E and WX.
- What transfers are the mechanism-level lessons (shared-ingress modelling, quantized rates, the probe) and the frozen
  decision code.
- WX also shows why the old workload is not the paper's current one: under oldM1 the three refresh-heavy inputs never
  returned to the reference after three moves (0 of their runs reached 35 dB). That failure is what M1 / M2 replace.

### 3.2 State objects: could each go through a restoration graph?

Sizes are measured in E9 / E10 [V]. Assessments are marked [H].

| M1 / M2 object | size per migration (measured) | multi-provider? |
|---|---|---|
| Sink base, full | 1,727.6 MB = 360 blocks of 4,792,320 B (K / V × 30 layers × 2 rows × 3 slots) + 1,440 B positions. It is 97 % of dog's first migration (1,776.8 MB) and 73 % of butterfly's (2,361.4 MB) | **Yes, the only object where a graph can matter** [H]. Valid providers: (a) a node holding fragments of the **same base version** (e.g. an abandoned target's partial copy); (b) a node holding an **older retained version**, for blocks that are unrefreshed (K of shifted entries become valid only after the ordered shifts are applied, E8). (b) needs the current owner's tracker |
| M2 delta (refreshed entries + ordered shifts) | dog 21.6 MB; butterfly 357.0 MB (37 entries) | Only the current owner's tracker knows it; source-only, relayable [H] |
| Input log + refresh patches | dog 26.0-45.9 MB; butterfly 562.7-630.6 MB (patches 546-613 MB) | Generated live and **strictly ordered** (replay is sequential, `_replay_enqueue`); not a fragment set. Only relaying is possible, with no gain unless the source's egress is the bottleneck [H] |
| DR2 latents, in-flight, meta at the switch | 0.4 MB + 3.2 MB final | Critical path at the cutover; source-only |
| Retained version (M2) | 1.73 GB host memory per node | It is itself a holder of type (b) |

### 3.3 Answers to the five questions

1. **Transferable objects.** Only the Sink base (full, or the retained-version part of it) can be multi-provider.
   Log, patches, delta and switch state are ordered or owner-specific and stay on the source's connection [H, from
   3.2].
2. **Fragment abstraction.**
   - Partly compatible [V]. Both paths split the same serialization (`pack(snap, "sink")`) into 4 MiB fragments with
     SHA-256 (`frag_table`; `_xb_send_dirty` / `cmd_flow_start`).
   - Not compatible in three ways:
     - (i) An oldM2 holding is valid only for one immutable manifest. VACW's hash-valid holdings (47243de) are the only
       cross-version form, and VACW is NO-GO by its frozen rule, though H1a correctness held 24 / 24.
     - (ii) The 412 × 4 MiB fragments do not align with the 360 × 4.57 MiB blocks that M2 verifies, reconstructs and
       shifts. A refreshed entry (K + V of one slot-row) dirties ≈ 4 fragments.
     - (iii) RoPE-shifted K blocks are never hash-equal to the retained copy, so hash reuse misses them. M2's ordered
       shifts recover them exactly.
   - Logs and patches are ordered streams, not fragments.
3. **Multiple GPU holders and relays.**
   - Supported in the oldM1 GPU path [V]: any node with verified fragments forwards (`FLOW_START`), pre-positioned
     holders, pipelined relay (`relay_pipe`), max-min emulation with per-node caps, `hybrid_net` contention.
   - **Not supported in the M1 / M2 path** [V]: one source → one destination; a mid-migration move discards progress;
     the M2 delta is limited to "destination = holder of the retained version".
4. **Exact reconstruction and cutover verification.** They can be preserved [H] if three things hold:
   - the destination verifies the assembled base against the source's base before `shadow_base` (360 block checksums
     and positions for the Sink component, component digests for the rest);
   - the log and patches remain one ordered stream from the source;
   - the cutover Sink check (SINKOK / SINKNO + fallback) is untouched.

   M3 would change only who sends which base fragment. E10 already exercised the detection and full-base fallback
   path on GPU [V].
5. **Integration work.** Section 5, I1-I4.

---

## 4. Research assessment

**Problem.**
- Under repeated mobility the user moves before a migration completes [V]:
  - M1's single-migration readiness is 21.6-24.0 s at 1 Gbps (E9 / E10);
  - in XB3 / XB4 the pre-copy family cancelled every pre-final migration, wasted two ~1.3 GB rounds to abandoned
    targets at rho 1, and served the user remotely for 44.8 s (rho 1) and 30.2 s (rho 2) (`expXB/xb_report.md`
    section 4, P-sink).
- With one source and one path, the base is limited by the slowest link and restarted at every move.

**Observations (measured; the old workload unless stated).**
- O1. No fixed topology is right everywhere (Full E, B). A per-fragment assignment over all holders matches or beats
  the best fixed plan (≤ 0.3 s behind in Full E; 9 % ahead at B_f = 500).
- O2. Preserved progress is reusable: discarded work ≤ 0.06 Sink (R); revisit 7.0 vs 14.0 s (Full E).
- O3. An assignment fixed at the move stalls when a provider degrades mid-restoration: 53.8 s (Full E), 51.6 s
  (G7), 113.4 s (N cell 9), 122.1 s (V5).
- O4. Re-planning that treats shared-ingress shares as independent capacities produces false positives and
  oscillation (N cells 7, 8, 10; `m3_root_cause.md`).
- O5 (M1 / M2, E9 / E10). The base is 73-97 % of migration bytes. Between migrations it changes little (dog 2 / 180
  entries; butterfly 37 / 180 over 59 calls). Version-verified reuse is exact (block-level and bitwise frames).
- O6. Under uniform links, restoration is ingress-bound and multi-provider delivery does not shorten it (B uniform,
  Full E conditions 1 / 4, V3, V6-V8, M3E S3 / S4). The gains are source offload and robustness to a degraded provider.

**Challenges.**
- C1. Provider rates share the destination's ingress.
- C2. Deciding when to change providers from quantized, uncertain rates.
- C3 (new with M1 / M2). Holders hold **different versions**. Only content equal to the target base, or reconstructible
  from a verified version plus ordered shifts and a delta, may be used, and the result must be verified before replay.
- C4 (new). Part of the state is an ordered live stream that cannot be scheduled as fragments.

**Solution (kept: Restoration Graph Morphing).**
- The restoration graph is not chosen from a topology catalogue. It is the set of per-fragment provider assignments
  over every verified holder; star, line, tree and butterfly are special cases.
- The graph morphs only when bottleneck evidence (M3-v2: ingress-aware estimator, fragment-count windows, probe) shows
  that a reassignment helps.
- For M1 / M2 it must be generalized to **versioned holders** (C3), with the ordered stream kept on the source (C4)
  [R].
- No evidence found a fundamental incompatibility. The base is a fragment set with exact verification at both ends
  [H].

**Strongest supported insight [V].** Restoration graphs should be built from per-fragment provider assignment and
changed only on ingress-aware bottleneck evidence:
- fixed topologies each fail somewhere (Full E, B);
- aware assignment equals the best fixed plan within 0.3 s;
- M3-v2 keeps a 2.0-5.7× gain where an alternative provider exists, and makes zero unneeded re-plans across V, M3E and
  WX (4 inputs).

**Weaknesses for OSDI.**
- W1. Every M3 result is on the superseded oldM1 / oldM2 workload; M3 with M1 / M2 is unimplemented and unmeasured.
- W2. The gain is conditional: it requires a provider degrading mid-restoration (one synthetic magnitude and onset per
  cell); otherwise the effect is neutral (O6).
- W3. The topology evidence is network-level only; Star / Line / Tree / Butterfly were never on GPU.
- W4. N / V ran with an idle source (EXEC_START); V-H2 in V4 has a 0.04 s margin.
- W5. V-H4: v2 is 4.1 s slower than v1 when the degraded holder is alone.
- W6. Narrow surface: V is dog-only; WX is 4 inputs, seed 0; one model; emulated caps on one LAN; no traces (T on
  hold).
- W7. With M1 / M2, faster base delivery shortens remote serving and migration completion, not the quality gap. The
  motivation must be restated in those terms, and **it is not yet measured for `precopy_replay` under repeated
  mobility** (XB3 / XB4 measured P-sink).

---

## 5. Minimal plan to complete M3 [R]

Ordered by dependency. The frozen M3-v2 decision code (`restore_planner.dyn_decide_v2`, `assign_providers`) is
reused unchanged. No new scheduling mechanism.

**A. Characterize the problem in the M1 / M2 system (≈ 4-6 GPU runs, no new code).**
- `precopy_replay` with Sink sync and retain / reuse on A → B → C → D at rho 1 and 2, dog and butterfly, using the
  existing XB3 / XB4 configuration.
- Measure:
  - whether the final migration completes;
  - cancelled bytes to abandoned targets;
  - remote-serving seconds;
  - readiness;
  - whether any M2 reuse fires (only on revisits).
- This replaces the P-sink evidence with the actual M1 / M2. It is not a re-run of XB3 / XB4, which measured
  `precopy_sink`. It is the baseline for everything below.

**B. M1 / M2 integration (implementation; each item with dry tests and E10-style fault tests).**
- I1. **Progress preservation of the base across moves.** An abandoned target keeps its received base fragments
  tagged with the base version instead of resetting `xb_store`, and reports its holdings.
- I2. **Versioned holders, block-level validity.**
  - Holdings are (version, per-block checksums).
  - The Sink component's fragments are aligned to its 360 blocks (other components keep 4 MiB fragments).
  - A block may come from:
    - a holder of the same base version; or
    - a holder of a retained version, with the current owner's tracker supplying the refreshed entries and ordered
      shifts (generalizes M2's `reuse_base`, whose retained buffer must now be local, to one fetched from a third node).
- I3. **Multi-provider base delivery in the XB path.**
  - The base's fragments go through the existing `FLOW_START` / `FLOW_ADD` / `FLOW_CANCEL` machinery, planned by the
    frozen `assign_providers` + `dyn_decide_v2`.
  - The log, patches, delta, DR2 and switch state stay on the source's ordered connection.
- I4. **Verification order unchanged.**
  - The assembled base is verified (360 block checksums and positions; component digests) before `shadow_base`.
  - A mismatch falls back per block, then to the full base, using the existing fallback paths.
  - The cutover SINKOK check is untouched.

**C. Functional validation of the integration (as E9 / E10; one run per configuration).**
- A → B → C with a versioned holder.
- A mid-migration move followed by a resume from the preserved partial base.
- Faults: a stale holder version, a corrupted holder block, a holder lost mid-flow.
- Required: an exact Sink at the base and the cutover (block-level); outputs bitwise equal to the single-provider run;
  completion.

**D. Performance evaluation (preregistered; only the configurations that are new for M1 / M2).**
- **Repeated mobility** (rho 1 / 2): M1 + M2 vs M1 + M2 + M3. Measure completion, remote serving, source bytes and
  readiness.
- **Holder bottleneck** (the M3E S2 analogue).
- **No-change, ingress and source negative cases** (no harm, 0 re-plans).
- Inputs: dog and butterfly.
- Do not re-run N / V / M3E / WX. They stand as evidence for the planner on the oldM1 workload and must be labelled
  that way.

**E. New mechanism only if A shows it is needed.**
- If A shows that `precopy_replay` cannot complete under repeated mobility even with I1-I3 (e.g. the ordered log alone
  outpaces T_m), that is a new problem, needing a new design and preregistration.
- Third-party delta reconstruction (I2) is the one item that extends M2's protocol. It should be preregistered as an
  M2 extension, not as M3.

Decisions for the user before B:
1. **Which system the paper presents.** The paper may present M1 / M2 (exact) as the system and oldM1 / oldM2 only as
   history. If so, the M3 claims (M3-1, M3-2, M3-3) must be re-established on M1 / M2 through D, and the old results
   cited as planner evidence on the old workload.
2. **Scope of I2.** Third-party versioned holders (graph across past sources) or same-version holders only (graph
   across abandoned targets). Same-version only is smaller and needs no M2 protocol change.
