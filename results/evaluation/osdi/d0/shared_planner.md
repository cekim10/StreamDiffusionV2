# D0: shared restoration planner - implementation summary (2026-10-16)

## What moved

`tools/eval/restore_planner.py` holds every restoration decision as pure functions over plain data; both harnesses
collect their own state and apply the decision with their own flow machinery.

| function | decision | previously in |
|---|---|---|
| `assign_providers` | provider for every missing fragment at a plan: `reuse_fixed` (M2 wavefront), `pp_star` / `fixed_line` / `fixed_tree` / `fixed_butterfly` (baselines), `reuse_aware` / `reuse_aware_in` / `reuse_dyn` (M3 bottleneck-aware assignment), `reuse_adaptive` (H3b rule) | `restore_orchestrate.Run.plan` |
| `holder_order` | past owners newest first, then never-owner holders | `Run.plan` |
| `dyn_decide` | event-driven re-plan of the bottleneck provider's remaining fragments (E-pilot v2 thresholds: dT > C_switch + max(2 s, 0.1 ETA); idle estimates kept) | `Run.dyn_check` |
| `prepos_alloc` | placement allocation before a move | `Run.prepos_start` |
| `dissem_assign`, `maxmin`, `parse_cap_events` | Experiment B plans, network emulation, cap events | module level |

The code is moved verbatim; no algorithm, threshold or tie-break changed. `restore_orchestrate.py` now gathers the
state (holders, in-flight fragments, whole-node backlogs, bytes headed to the owner, measured throughput) and calls the
planner. `restore_model.py` (the fluid model that produced the pre-registered predictions) is untouched; it imports
`maxmin` / `parse_cap_events` / `dissem_assign` through `restore_orchestrate`, which re-exports them.

## GPU harness integration (`mobility_orchestrate.py`, `mobility_node.py`)

- New policies: `reuse_aware_in` (OTTER at moves) and `reuse_dyn` (OTTER event-driven) call `assign_providers` and
  `dyn_decide`. Triggers as in the network harness: start, moves, and the end of a flow with fragments still missing
  (per-fragment arrivals do not re-plan these policies). The Phase 1 policies (restart, relay, relay_pipe, split,
  direct) are unchanged.
- Per-node caps (`--caps`) and cap events (`--cap_events`, time- or progress-triggered); planners see only the caps
  known at the start. Rates use the shared `maxmin` under per-node caps when shaped; unshaped runs are unchanged.
- Placement window (`--prepos`, `--path A,<dest>`, `--probs`, `--lookahead`, `--budget`): the source keeps generating
  (new node command `EXEC_START`) while it sends the `prepos_alloc` allocation to the candidates; the move happens
  `L` seconds after the trigger.
- Harness-level handling (not a decision change): a holder asked to forward a fragment it does not hold yet skips it
  (`flow_skip_not_held`); for the planner policies the orchestrator now releases that claim and re-plans at the flow's
  end, as the network harness does with `FRAG_SKIP`. After an event-driven cancel, any fragment the cancelled flow did
  not send is assigned again by the same rules.
- Instrumentation: per-chunk decode completion (`t_decode`, wall clock after a device sync around the VAE decode call)
  and frames decoded per chunk in `metrics.csv`; `d0` block in `summary.json` with pre-/post-move source bytes, total
  source, holder-forwarded bytes, aggregate bytes, x verified at the move per candidate, verified progress retained and
  reused, version-event count (`fragment_rejected_version`, `sink_version_mismatch`, rejected receipts), re-plans with
  their measured rates, estimates and switching costs, cap changes, placement allocation; validation flag
  `version_events_zero`. Per-fragment send/receive logs, Sink verification and bind events existed before.
- Not implemented in D0 (needed before the full sweep, prereg section 8): full migration and cold restart as
  repeated-mobility execution policies, revisit paths, hybrid scenario E, the OTTER cold-destination variant, and the
  external C/R baselines. No frame-delivery consumer (out of scope by the freeze).

## Finding about the frozen decode-interval metric

The VAE decodes all frames of an output chunk in one call, so every frame of a chunk completes decoding at the same
instant. "Decode interval between consecutive frames" (prereg section 6, descriptive) is therefore 0 within a chunk
and equal to the chunk interval across chunks. This does not change any criterion (decode metrics are descriptive);
it is recorded here so the reported distribution is not misread. Whether to add a dated erratum to the frozen text is
the reviewer's decision.
