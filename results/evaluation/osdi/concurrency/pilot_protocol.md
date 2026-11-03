# Concurrent migration on the testbed: feasibility pilot (DRAFT 1, 2026-11-03; not frozen; nothing run or implemented)

**Question.** Does OTTER keep service continuity when two streaming sessions migrate at the same time and share a
bottleneck? The frozen claims and M1 / M2 / M3 are unchanged; this is a pilot, and the formal runs and their rules
are decided after it.

## 1. What the testbed allows (facts; read this first)

| fact | source |
|---|---|
| 4 hosts, **one usable GPU each** (GPU 1 of every host belongs to other users) | testbed rule [V] |
| one SDV2 session per GPU: a node peaks at 26.6-29.7 GB allocated, 29.8-31.4 GB reserved on a 46 GB L40S | Fig. 14 sanity run, node `--mem_log` [V] |
| every node process loads the model on GPU 0 at launch, and a warm node also generates the reference | `mobility_node.py` [V] |
| the orchestrator allocates every flow of its session max-min under per-node egress / ingress caps and pushes the rates to the senders, as the E9 simulator does per site | `mobility_orchestrate.rates`, `cluster_sim.Net` [V] |
| an existing two-tier option (scenario E, `--hybrid_net`) shares caps with GPU-less network sessions, but those run the old restore policies (restart / split / reuse_dyn), not Full / R-full / OTTER | `hybrid_net.py` [V] |

Consequences:

1. **Two sessions cannot share a GPU** (about 2 x 30 GB > 46 GB) [derived]. So the user's "shared destination" with
   two sessions arriving at one GPU is infeasible. It is recorded as a feasibility result (F0), not forced.
2. **At most two concurrent sessions, each on a two-host path** (A -> B and C -> D).
3. **M3 cannot be exercised under concurrency here.** One move has nothing to stage. A session needs at least three
   hosts on its path for staging, and two such sessions need 6 GPUs. "OTTER without Wavefront" equals OTTER in this
   pilot. M3 under concurrency is evaluated only in E9 (simulated; `fig_cluster/scalability_draft.md`), unless more
   GPUs become available (open question for the user).
4. **Contention must come from a shared link.** The two pairs have separate NICs and separate per-sender token buckets.
   Running them at once (C2) is two single migrations in parallel and supports no contention claim, as the user noted.
   Fig. 12 and Fig. 13 already ran P1 and P2 at once, but their triggers were not aligned, so they are not C2 data.

## 2. Conditions

| id | sessions | bottleneck | purpose |
|---|---|---|---|
| F0 | try to start a second node on one GPU 0 | - | records the memory infeasibility (expected OOM); one attempt, stopped at the first error |
| C1 | one migration A -> B, 1 Gbps | own | baseline (Fig. 7 runs reused; one fresh rep in the pilot session as a same-day control) |
| C2 | A -> B and C -> D, triggers aligned | independent 1 Gbps each | parallel without contention (sanity of the two-session runner) |
| C3 | A -> B and C -> D, triggers aligned | **one shared 1 Gbps link** that both migrations' flows cross (max-min over both sessions' flows) | contention: the key condition |

**C3 implementation (needs approval; a harness change, no mechanism change).** Add a rate coordinator, a small
process on elves-01. Both orchestrators register their active flows with it, and it runs one max-min allocation over
both sessions' flows under the per-node caps plus one shared link cap. Each orchestrator pushes the rates it gets back
(`FLOW_SET_RATE`), as it does today. This is the E9 simulator's fluid model with a shared link, so C3 also checks the
simulator's sharing model on two sessions. Regression afterwards: `test_xb` and the Fig. 7 dry run (a coordinator with
one session must allocate exactly as today).

Alternatives considered:
- A static 0.5 Gbps cap. This equals Fig. 12a's 0.5 Gbps cell, which is already measured, and is used as the
  reference for "a competitor active the whole time". No new run.
- Scenario E. Not used: its network sessions run other policies.

**Methods:** both sessions run the same method each time (Full / Full, R-full / R-full, OTTER / OTTER). Workload dog
for both sessions in the pilot. Triggers are aligned at the same wall-clock time (offset 0).

## 3. Metrics (per session, both sessions)

- Max. output gap.
- Readiness.
- Time without local service (remote-served + interrupted).
- Per-session throughput (served calls / s during the migration window).
- Migration completion (switched before `--max_run_s`).
- Link utilization: the coordinator's allocation log plus `node_*/network.csv`.
- GPU memory peak: node `--mem_log`.
- C2 / C3 vs C1 differences reported in absolute terms.

## 4. Predictions [H] (not used by any rule)

- **OTTER:** gap unchanged at about 1.6 s. Its gap is the Sink-snapshot stall, which Fig. 12a shows does not depend
  on the link. Readiness between its 1 Gbps (23 s) and 0.5 Gbps (41 s) values, depending on how long the two
  transfers overlap.
- **Full:** gap up to about 2x (54 -> about 100 s) while both transfers overlap.
- **R-full:** about unchanged (0.08 GB).

## 5. Pilot size and stop rules

- Size: F0 (1 attempt), C1 (1), C2 OTTER (1 two-session run), C3 x 3 methods (3 two-session runs). About 1 h of GPU
  time after the coordinator exists.
- Stop rules:
  - The pilot stops at the first harness failure, which is fixed and kept as a record.
  - If C3's coordinator cannot hold the shared cap (NIC > 1.15 x cap at the destination), C3 is not run formally.
  - If the pilot fails, the formal concurrency experiment is not pursued, and the paper states that two-session
    contention is simulated only (E9).

## 6. Open decisions (user)

| # | decision | recommendation |
|---|---|---|
| P1 | implement the rate coordinator for C3 | yes (smallest change that creates real sharing) |
| P2 | which link the two migrations share | the destination side (B and D ingress, one cap), matching a shared site uplink in E9 |
| P3 | pilot workloads | dog / dog |
| P4 | any GPUs beyond GPU 0 of the four hosts (needed for M3 under concurrency) | ask the testbed owners; otherwise M3 concurrency = E9 only |
