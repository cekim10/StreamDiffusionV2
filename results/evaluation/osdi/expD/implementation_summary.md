# Experiment D: missing GPU evaluation capabilities - implementation summary (2026-10-16)

Scope: only capabilities the frozen preregistration (`../gpu_end_to_end_preregistration.md`, v3, 81bb628) already
specifies (section 8 items 3, 5, 7 and the revisit part of item 2). The M3 algorithm (event-driven re-planning, ETA
estimation, hysteresis thresholds, provider assignment, placement rules), the shared planner
(`tools/eval/restore_planner.py`) and the network harness (`restore_orchestrate.py`, `restore_node.py`,
`restore_model.py`) are unchanged (`git diff` empty). No G1-G9 criterion changed. No sweep was run.

Files: `tools/eval/mobility_node.py`, `tools/eval/mobility_orchestrate.py` (GPU harness), new
`tools/eval/hybrid_net.py`; tests `tools/eval/run_gpu_dryrun.sh` (protocol, loopback), `tools/eval/run_expD_correctness.sh`
+ `tools/eval/check_expD_correctness.py` (testbed); `run_planner_regression.sh` / `compare_planner_regression.py`
gained an output-folder option only.

## A. Repeated Full migration (`--policies full`)

- At a move the generating owner stops at the chunk boundary, serializes its live state and packs every component of
  Phase 1's `full` (inflight, meta, recent, sink, vae; same `pack_component`, same order), then sends them over one TCP
  connection paced by a token bucket at min(egress cap of the sender, ingress cap of the destination) (0 = unshaped).
  The destination unpacks each component into its provisioned buffers and, at GO, restores every component
  (`restore_state(..., STATE_COMPONENTS)`, as Phase 1) and resumes; the Sink is bound at resume (part of the state).
- **Repeated mobility (implementation choice; the preregistration does not define it):** the transfer runs in the
  background. If the next move comes before it completed, the node that still holds the complete packed state (the
  last owner that generated) cancels the transfer and sends the whole state to the new destination; the partial copy
  at the abandoned destination is discarded (it never resumes). This is stop-and-copy with no progress reuse,
  consistent with M1 only's discard semantics. At rho = 2 and 1 Gbps (T_m 7 s, ~52 s per transfer) the expected
  behaviour is two cancelled transfers from A and one complete A -> D transfer. Alternative semantics (e.g. requiring
  each hop to complete) would change only descriptive Scenario B numbers (no G criterion uses Full migration in B).
- Checks: per-component digests (Phase 1 definition) computed at the sender and receiver, compared after resume (off
  the critical path, as in Phase 1); the Sink component's digest is also compared with the source manifest's Sink
  digest; bit-exactness after resume (PSNR 99 = identical).
- Accounting: bytes each transfer put on the wire (counted at the token bucket; a cancelled transfer overcounts by at
  most the 1 MiB chunk in flight), completed vs cancelled, partial state discarded at receivers, per-link totals
  (`summary.json` `execution_state`, `per_move[*].state_transfer`), included in
  `d0.aggregate_network_incl_state_sinks`.

## B. Repeated Cold restart (`--policies cold`)

- At a move the owner stops; only the call number is sent (no state; no serialization). The new owner restarts with
  Phase 1's `restart_at` (new session from [last image of a fresh destination session, chunk c]); as in Phase 1 the
  restart call produces no output and its frames are emitted at the next call. Every new owner restarts again. No Sink
  is transferred and nothing is reused. Same move schedule as OTTER.
- Output quality vs the bit-exact reference is measured per chunk (expected to diverge, Phase 1: 19-22 dB). A cold
  restart never rejoins, so its run ends `--cold_tail_calls` (60) chunks after the final owner's first output.

## C. Revisit (`--path A,B,C,D,B`)

- Paths may revisit B, C, D (never A; the owner changes at every move). Each ownership starts afresh at the node
  (bind / rejoin / first output reset; a revisited owner re-binds the Sink when it is complete).
- M1 only (`restart`) now discards an abandoned owner's fragments **at the node too** (`SINK_DROP`): previously only the
  orchestrator's view was cleared, which did not matter without revisits. Fragments of the cancelled flow still on the
  wire are drained and discarded; a drop epoch on every receipt report makes the orchestrator's view exact. Without
  revisits this changes no transfer (restart never reuses abandoned progress); `physically_held_at_end` now shows
  the drop.
- Final-owner metrics (bind, rejoin, first output, continuity) use only the final ownership. New `revisit` block:
  fraction verified at the final owner before it left, held on return, still-held fraction, fragments received again
  after return, and every drop. `verified_progress_retained` is now taken at the next move (prereg definition) from
  holder snapshots, not at the end of the run (identical for non-revisit paths).

## D. Hybrid scenario E (`--hybrid_net 3`)

- Three network-level sessions run on `restore_node.py` processes (no torch, no GPU; separate ports 29831/29832 on the
  same four hosts), driven by `restore_orchestrate.Run` **unchanged** (subclass in `hybrid_net.py` that overrides only
  the rate allocation and the schedule). Every flow of every session (GPU and network) is allocated in one max-min
  computation over the same per-node caps, so A's egress is really shared. Each network session starts at B at the GPU
  session's first move and moves with it (B -> C -> D) at the same instants; its policy is the GPU session's (M1 only =
  restart, M1 + M2 = reuse_fixed, OTTER event-driven = reuse_dyn).
- GPU metrics refer to the GPU session only; the network sessions' results (`<run>/net/<id>/sessions.csv`,
  `summary.json`) are reported separately (`summary.json` `hybrid`). The run waits up to `--net_grace_s` (120 s) after
  the GPU session's end condition for the network sessions to restore.

## E. OTTER cold destination (`--cold_dest`, scenario A sensitivity, external group)

- Destination B is not running at the trigger. At the trigger the source keeps generating (as during a placement
  window) while the orchestrator starts B's process through the agent; B loads the weights, initializes CUDA, listens;
  the orchestrator connects (polling every 20 ms), B provisions its buffers (timed), then OTTER's M1 handoff and Sink
  restoration run. `cold_destination` in `summary.json` gives process launch / start / runtime ready / listening /
  connected / provisioned / handoff / TTFO / Sink verified / bind / rejoin, all from the trigger. A fresh process per
  run; it is shut down after the run.
- No baseline run at a cold node: the PSNR reference is the cache a warm node of the same host and configuration
  wrote at its baseline (`results/evaluation/_reference_cache/`, bit-exact on the same GPU), loaded in a background
  thread; the run refuses to start if the cache is missing. Kept separate from the warm-destination comparison.
- Implementation choice: the source keeps generating until the handoff (OTTER's design); TTFO is timed from the
  trigger regardless.

## Other changes found necessary by the audit

- **M1 + M2 (`split`) holder order** extended to pre-positioned holders (after past owners, as the network-level
  reuse_fixed holder order), and its first move may target any edge. Needed for scenarios C/D ("M1 + M2 (no
  placement)" on A -> C, "M1 + M2 + top-1"); previously the first move was hard-wired to B. Without placement only past
  owners hold fragments, so the Phase 1 rule is unchanged.
- **Instrumentation for run validity / G9:** GPU 0 state on every host just before each run (utilization, memory used
  by processes other than our node); peak `memory_allocated` / `memory_reserved` per node per run; paced payload egress
  per node over 10 s windows; node commit in every HELLO (`nodes_same_commit`).
- Per-move timing (`per_move`): resume, first output, bind, rejoin and state transfer for every move, from that move's
  trigger.
