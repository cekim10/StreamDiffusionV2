# Concurrent migration on the testbed: feasibility pilot (DRAFT 2, 2026-11-03; not frozen; nothing run or implemented)

DRAFT 2 replaces DRAFT 1 (e83a267a) after the user's update the same day: **GPU 1 is usable on elves-01, 03 and 04
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
- Regression: a coordinator with one session must allocate exactly as today (`test_xb`, Fig. 7 dry run).

Methods:
- C2, C3a, C3b: both sessions run the same method (Full / Full, R-full / R-full, OTTER / OTTER).
- C4: S1 runs OTTER or OTTER w/o M3 (Fig. 11's two OTTER arms); S2 runs OTTER.
- Workload dog for both sessions in the pilot. Triggers aligned at the same wall-clock time.

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
1. Without new code (after a `--gpu` option in the guard and a two-session runner): C1, C2 OTTER, C3a with each of
   the 3 methods. That is 5 runs, about 40 min.
2. With the coordinator: C3b with each of the 3 methods, then C4 with each of the 2 S1 arms. That is 5 runs, about 1 h.

Rules:
- **Fig. 14 first:** no run on elves-01 GPU 1 while Fig. 14 measures throughput on elves-01 GPU 0. A neighbour on
  the same host would perturb the native measurement.
- Stop rules:
  - Stop at the first harness failure; fix it, rerun, and keep the record.
  - If the coordinator cannot hold the shared cap (NIC > 1.15 x cap), C3b and C4 are not run formally.
  - If the pilot fails, the paper states that two-session contention is simulated only (E9).

## 6. Open decisions (user)

| # | decision | recommendation |
|---|---|---|
| P1 | implement the rate coordinator (C3b, C4) | yes |
| P2 | link model of the coordinator | per-host egress / ingress caps shared by every node on the host (= E9 site uplink) |
| P3 | pilot workloads | dog / dog |
| P4 | how long GPU 1 stays available | needed to plan the formal runs; GPU availability is recorded with every run |
| P5 | order vs Fig. 10 long-age | step 1 of the pilot first (no coordinator needed), long-age next, coordinator built meanwhile |
