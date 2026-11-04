# Concurrent migration on the testbed: feasibility pilot (DRAFT 3, 2026-11-03; not frozen; stage-1 and stage-2 tools implemented, nothing run)

DRAFT 3 adds the user's review of DRAFT 2 (03c8a97e): coordinator verification, C4 flow-overlap evidence, the 2 x 2
M3 comparison, pilot success criteria. DRAFT 2 replaced DRAFT 1 (e83a267a) after the user's update the same day: **GPU 1 is usable on elves-01, 03 and 04
(not on elves-02)**. That makes 7 GPUs, two sessions per host on three hosts, and M3 under concurrency feasible in one
form (C4).

**Question.** Does OTTER keep service continuity when two streaming sessions migrate at the same time and share
hosts and links, and does M3 still help one session while another session's migration competes with it? The frozen
claims and M1 / M2 / M3 are unchanged; this is a pilot, and the formal runs and their rules are decided after it.

## 1. What the testbed allows (facts)

| fact | source |
|---|---|
| GPUs: elves-01 0, 1; elves-02 0; elves-03 0, 1; elves-04 0, 1 (7 L40S; availability as of 2026-11-03) | user [K] |
| one SDV2 session per GPU: a node peaks at 26.6-29.7 GB allocated, 29.8-31.4 GB reserved on a 46 GB L40S; two sessions never share a GPU | Fig. 14 sanity run [V] |
| the harness already places a node on any GPU (`--gpus A=0,B=1`) and port (`--nodes A=host:ctl:data`); the pre-run GPU validity check reads each node's own GPU; agents serve several connections at once | `mobility_orchestrate.node_cmd`, `gpu0_state`, `agent.py` [V] |
| the runner guard `d0_remote.py gpu_idle` checks GPU 0 only | `d0_remote.py` [V]; needs a `--gpu` option before GPU-1 runs |
| every node process loads the model and regenerates the reference at launch | `mobility_node.py` [V] |
| each orchestrator allocates its own session's flows max-min under per-node caps; two orchestrators do not see each other's flows | `mobility_orchestrate.rates` [V] |

Consequences:

1. Two sessions can now share a **host** (different GPUs), so they really share its NIC, PCIe, CPU and host memory.
2. **Emulated link sharing still needs the rate coordinator.** At 1 Gbps each orchestrator's token buckets assume the
   whole emulated link; the physical NIC (9.4 Gbps) is far from full. Without a coordinator, two sessions on one
   host share host resources, but they do not share the 1 Gbps link.
3. **M3 under concurrency:** two 4-host Chains need 8 GPUs (we have 7). One 4-host Chain with M3 (S1, GPU 0 of all
   four hosts, Fig. 11's configuration) next to a second session on GPU 1 of elves-01 / 03 / 04 (S2) fits. S1's
   staging and migrations then compete with S2's migration on shared hosts.

## 2. Conditions

| id | sessions | sharing | needs | purpose |
|---|---|---|---|---|
| C1 | S1 alone: one migration elves-01:0 -> elves-03:0, 1 Gbps | - | nothing new | same-day control (Fig. 7 runs for reference) |
| C2 | S1 01:0 -> 03:0 and S2 04:0 -> 02:0, triggers aligned | none (different hosts) | runner only | runner sanity; no contention claim |
| C3a | S1 01:0 -> 03:0 and S2 01:1 -> 03:1, triggers aligned | same source and destination host: NIC, PCIe, CPU; **each its own 1 Gbps** | runner + guard option | host co-location without link sharing |
| C3b | as C3a | **one shared 1 Gbps egress at elves-01 and ingress at elves-03** (max-min over both sessions' flows) | rate coordinator | link contention: the key two-session condition |
| C4 | S1 = Fig. 11 Chain A -> B -> C -> D (GPU 0 of 01, 02, 03, 04; OTTER with M3) and S2 = one migration 03:1 -> 04:1 timed to overlap S1's move to D | shared host caps (coordinator) | rate coordinator | M3 under concurrency: S1's N, R_D and gap vs Fig. 11 alone; OTTER vs OTTER w/o M3 for S1 |

Rate coordinator (needs approval; a harness change, no mechanism change):
- A small process on elves-01.
- Both orchestrators register their active flows with it. It runs one max-min allocation over all flows under
  per-host egress / ingress caps, so a host is one site uplink, as in E9.
- Each orchestrator pushes the rates it gets back (`FLOW_SET_RATE`), as today.
- Regression: `test_xb` and the Fig. 7 dry run. Any change to the existing allocation code is regression-tested
  against the Fig. 7-12 configurations.
- **Verification 1, shared cap.** At every allocation, the coordinator's rates on each shared host egress / ingress sum
  to <= the cap. This is exact, from its allocation log. The measured NIC rates are compared to the cap after the
  header factor (1.0477 at MSS 1,388):
  - a 1 s sample up to 1.15 x the cap counts as a burst and is reported;
  - a 10 s mean above 1.05 x the cap is sustained excess, and the run does not count.
- **Verification 2, single-session equivalence.** For the same flow events, the coordinator with one session must
  produce exactly the allocation of today's per-orchestrator max-min (`maxmin_caps`):
  - a unit test replays the flow sets of recorded Fig. 7 and Fig. 11 runs through both allocators and requires
    identical rates;
  - a one-session dry run with and without the coordinator must produce identical `flow_rate` events.
  - If this fails, C3b / C4 are not comparable with Fig. 7 / 11, and stage 2 stops.

Methods:
- C2, C3a, C3b: both sessions run the same method (Full / Full, R-full / R-full, OTTER / OTTER).
- C4: S1 runs OTTER or OTTER w/o M3 (Fig. 11's two OTTER arms); S2 runs OTTER.
- Workload dog for both sessions in the pilot. Triggers aligned at the same wall-clock time (`--barrier`).

**C4 design (2 x 2, same day).** S1 runs Fig. 11's Chain (A -> B -> C -> D, moves at 45 / 90 s). Its first M3 plan
fires at the move to C, and A then forwards the retained Sink to D. S2's migration (elves-03:1 -> elves-04:1) is
timed to start with that forward: a barrier offset of +45 s, a stage-2 option. Its flows then share elves-04's
ingress with S1's staging and S1's later move to D.

| S1 arm | S1 alone (same day) | S1 + S2 |
|---|---|---|
| OTTER (with M3) | C4-alone-M3 | C4-M3 |
| OTTER w/o M3 | C4-alone-noM3 | C4-noM3 |

- The M3 effect under concurrency is (alone - concurrent) per arm, and the change in the with / without difference
  between the two columns.
- Fig. 11's runs are a reference only. The pilot re-measures "alone" the same day, so the comparison does not mix
  test environments.

**C4 flow-overlap evidence (required; logged by the coordinator).** Each flow is logged with:
- session and kind: S1 staging forward, S1 migration (each move), S2 migration;
- source and destination hosts;
- start and end;
- every allocated-rate change.
Each shared host's egress / ingress utilization is logged as well. The report computes:
- the seconds in which S1 staging flows and S2 migration flows were active on a common host link;
- the seconds in which either was held below the rate it would get alone.

A C4 run with zero overlap did not test contention. It is reported as such and does not count as evidence of
"M3 under contention"; the offset is adjusted for the next run.

## 3. Metrics (per session, both sessions)

- Max. output gap.
- Readiness.
- Time without local service.
- C4: N and R_D as in Fig. 11.
- Per-session throughput (served calls / s in the migration window).
- Migration completion.
- Link utilization (coordinator allocation log and `node_*/network.csv`).
- GPU memory peak and host RSS (node `--mem_log`).
- Every two-session value is given next to the same session alone (C1, Fig. 11), as an absolute difference.

## 4. Predictions [H] (not used by any rule)

- **OTTER gap:** about 1.6 s in every condition. It is the Sink-snapshot stall, which Fig. 12a shows does not depend
  on the link.
- **C3a:** close to C1. The NIC is far from full; small host effects are possible.
- **C3b, OTTER readiness:** between its 1 Gbps (23 s) and 0.5 Gbps (41 s) values.
- **C3b, Full gap:** up to about 2x (54 -> about 100 s) while the transfers overlap.
- **C3b, R-full:** about unchanged.
- **C4:** S1's gain from M3 shrinks. The forward to D shares elves-04's ingress with S2; how much it shrinks is the
  measurement.

## 5. Pilot size, order and stop rules

Order:
1. Stage 1, without the coordinator: C1 and C3a with each of the 3 methods, and C2 with OTTER. That is 7 runs.
   Tools: `run_conc.sh stage1`, `conc_report.py`, `d0_remote.py gpu_idle --hosts A:1,...`, orchestrator `--barrier`.
   The dry test of two sessions through the barrier gave a trigger offset of 0.000 s.
   Each run carries Fig. 7's reference generation (1,530 calls), so the stage takes about 2 h.
2. Stage 2, with the coordinator: C3b with each of the 3 methods, then C4's four cells. That is 7 runs.

Rules:
- **Fig. 14 first:** no run on elves-01 GPU 1 while Fig. 14 measures throughput on elves-01 GPU 0. A neighbour on
  the same host would perturb the native measurement.
- Stop rules:
  - Stop at the first harness failure; fix it, rerun, and keep the record.
  - If the coordinator cannot hold the shared cap (NIC > 1.15 x cap), C3b and C4 are not run formally.
  - If the pilot fails, the paper states that two-session contention is simulated only (E9).

## 5b. Stage-2 implementation (2026-11-03; harness only, no method change)

- `tools/eval/rate_coord.py`: the coordinator.
  - A TCP JSON-line server on elves-01.
  - One `restore_planner.maxmin` over the active flows of all sessions, under per-site (host) egress / ingress caps.
  - Logs every open / close with the full allocation, the site sums and `cap_ok`.
- Orchestrator `--coord HOST:PORT` (`--coord_sites` for dry tests, `--coord_poll_s` 0.25):
  - Every transfer it starts registers with the coordinator and runs at the coordinator's rate: the XB pre-copy
    task, the recompute input stream, the Full state transfer and every M3 forward.
  - Finished transfers are closed: task end, `full_send_end`, `m3_forward_done`.
  - Changed rates are pushed to the senders: the new node command `COORD_SET_RATE` re-rates the running pacer;
    M3 forwards use the existing `M3_FORWARD_RATE`.
  - `_m3_rerate` is off under `--coord`.
  - Without `--coord`, every path is unchanged.
- `--barrier_offset_s` (C4: S2 at +45 s).
- Runner `run_conc.sh stage2 / c3b / c4`: it starts and stops one coordinator per condition, logged to
  `coord_<cond>_*.jsonl`. Report `conc_report.py`: verification 1 (allocation level and host NIC), the seconds two
  sessions shared a site link by flow kind, and the time a shared flow was held below the cap.
- Verification results:
  - **Verification 2, replay** (`test_rate_coord.py`): ALL PASS.
    - Fig. 7 / 12a: 48 migration tasks, each alone on its link; coordinator rate = cap = today's.
    - Fig. 11: 180 M3 allocation points; 0 rates differ from today's cap-conserving equal shares; 0 cap violations.
  - **Two-session dry test through the coordinator** (`dry_coord`): the first flow got 1,000 Mbps; both got
    500 / 500 Mbps while sharing; the survivor got 1,000 Mbps back after the other closed. The re-rate was applied
    on the node, every site sum was <= cap, and both migrations completed.
  - **Verification 2, live** (`run_conc.sh dry_coord1`): one session, Fig. 11 Chain dry (Full, R-full, OTTER, and
    OTTER with M3) through the coordinator. All 34 allocations equal today's rule on the same flows.
    - The first try found 2 allocations where a task that had just ended (a switch or a cancel) was still
      registered when the next opened. The new task got half the cap for at most one poll (0.25 s).
    - Fixed: ended transfers are closed before every open, and a Full redirect closes the cancelled transfer.
    - Rerun: 34 / 34 identical.
  - **Regression:** `test_xb` ALL PASS (87 checks), rerun after the fix.

## 6. Pilot success criteria (feasibility, not performance)

1. Both sessions run normally on their own GPUs.
2. No GPU OOM and no abnormal throughput loss on a shared host (served calls / s vs C1).
3. The coordinator tracks both sessions' flows (every flow in its log, with start and end).
4. The shared 1 Gbps cap holds (verification 1).
5. Both migrations complete.
6. C4: real overlap of staging and migration traffic is shown (flow-overlap evidence).

An OTTER gap larger than the predicted 1.6 s is **not** a pilot failure by itself: it may be the contention the
pilot is meant to expose. Workloads, repetitions and contention levels of a formal experiment are decided only after
the pilot, and nothing is frozen before then.

## 7. Relation to E9 (how results are labelled)

- **Measured:** the 7-GPU testbed's concurrent migrations (this pilot and any formal follow-up).
- **Calibrated:** bandwidth / compute contention parameters fitted from these measurements, if the simulator needs
  them.
- **Simulated:** the 16-128 GPU cluster results.

Two sessions do not validate the whole cluster-scale contention model. They test the equal max-min sharing
assumption on two sessions only, and the paper says so.

## 8. Decisions (user, 2026-11-03)

| # | decision |
|---|---|
| P1 | rate coordinator: approved |
| P2 | per-host shared egress / ingress caps, equal max-min: approved |
| P3 | dog / dog: approved |
| P4 | proceed on GPU 1's current availability; re-check before any formal experiment; no long-term booking |
| P5 | order: Fig. 14 -> stage-1 tools -> pilot stage 1 (C1 / C2 / C3a) -> Fig. 10 long-age -> Fig. 13 strips -> coordinator + regression -> pilot stage 2 (C3b / C4) -> decide the formal experiment -> E9 contention calibration and scalability sweeps |
| added | C4 must show real flow overlap; M3 compared as with / without M3 x alone / concurrent (2 x 2, same day) |

## 9. Open decisions (superseded table of DRAFT 2, kept for the record)

| # | decision | recommendation |
|---|---|---|
| P1 | implement the rate coordinator (C3b, C4) | yes |
| P2 | link model of the coordinator | per-host egress / ingress caps shared by every node on the host (= E9 site uplink) |
| P3 | pilot workloads | dog / dog |
| P4 | how long GPU 1 stays available | needed to plan the formal runs; GPU availability is recorded with every run |
| P5 | order vs Fig. 10 long-age | step 1 of the pilot first (no coordinator needed), long-age next, coordinator built meanwhile |

## 10. Stage 1 outcome (2026-11-03, measured; runs 5aa95705, report `conc_pilot_results.md`)

Seven conditions-methods ran (C1 x 3, C2 OTTER, C3a x 3), 11 sessions. In C3a, S2's nodes ran on GPU 1 (`host_info.json`
gpu_id 1, ports 29841/29842), S1's on GPU 0.

| criterion | result |
|---|---|
| 1. both sessions run on their own GPUs | met: C2 and C3a, every pair completed; barrier trigger offset 0.000 s, windows overlap 100 % |
| 2. no OOM, no abnormal throughput loss | met: no OOM in any record; GPU reserved per node identical to C1 (Full 26.0 / 29.4, OTTER 29.2 / 30.7, R-full 26.0 / 29.2 GB); served calls/s in the window OTTER 1.42-1.44 (C1 1.43), R-full 0.81 (0.81), Full 0 (stop-and-copy, as in C1) |
| 5. both migrations complete | met: every session, bytes as C1 (Full 6.463, OTTER 1.763, R-full 0.084-0.085 GB) |
| 3, 4, 6 | stage 2 (coordinator) |

Values vs C1 (absolute differences): OTTER gap +0.00 to +0.08 s (1.61 -> 1.62-1.69 s), TTFO -0.68 to +0.25 s;
Full TTFO / gap +0.32 to +0.36 s; R-full TTFO -1.06 to +0.15 s, gap -0.51 to +0.37 s. Prediction C3a "close to C1"
held. One run per session: these are not effect estimates.

**Validity flag in C3a (report issue, not a run failure).** The four C3a Full / OTTER sessions carry `valid False`
from the inherited single-session rule (`xb_validity` / `expD_validity`: host NIC peak or 10 s mean > 1.15 x cap).
The rule reads the host NIC, which in C3a carries both sessions, each shaped to its own 1 Gbps by design (section 2).
Host NIC 10 s mean = 1.972-1.975 x cap, i.e. 0.986-0.987 x (2 x cap); C1 single sessions 0.985-0.988 x cap. Per-session
bytes / TTFO match C1 (Full 6.463 GB in 54.5 s vs 54.2 s). The flags are kept in the record; a C3a-aware check
(host NIC vs n_sessions x cap) is proposed, not applied, pending the user's decision.

**GPU-1 neighbour.** During C1 (18:53) GPU 1 of elves-01 / 03 / 04 ran another user's process (44 GB each,
`gpu1_state_C1_*.txt`); C1 shared the hosts (not the GPU) with it. C2 (19:48) found GPU 1 idle; C3a's guard required
A:1 and C:1 idle. C1 OTTER vs C2 S1 OTTER: TTFO 23.71 vs 23.67 s, gap 1.61 vs 1.62 s, calls/s 1.43 vs 1.44: no visible
effect, but C1 Full / R-full have no neighbour-free repeat.
