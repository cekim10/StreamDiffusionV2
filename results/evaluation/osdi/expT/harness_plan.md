# Experiment T - 3. Harness extension plan (DRAFT, 2026-10-17; nothing implemented)

Constraint: the frozen planner (`tools/eval/restore_planner.py`) and every policy parameter (E-pilot v2 thresholds:
dT > C_switch + max(2 s, 0.1 ETA), 2 s window, 0.5 s period, 2 s warm-up, 0.3 s control cost) stay unchanged; the
decision-equivalence test (`tools/eval/test_restore_planner.py`) must still pass after the changes.

## Which harness

- **Primary: the network-level harness** (`restore_orchestrate.py` + `restore_node.py` on the four hosts). Same planner
  code as the GPU harness (decision-equivalent, D0), real TCP and token buckets, no generation; a run takes ~1-2 min,
  so many trace segments x policies x reps fit.
- **Confirmation: the GPU harness** (`mobility_orchestrate.py`) on a small fixed subset of segments, to show that the
  network-level behaviour carries over to real generation (bind-ready, rejoin).

## Minimum changes

1. **Time-varying caps through the existing `tick()`.** Both harnesses already apply cap events of the form
   `t=<s>:<node>:<in|out>=<Mbps>` in `tick()` (`restore_planner.parse_cap_events`), the planners are not told, and every
   change re-runs the max-min allocation. A trace becomes a list of such events at 1 s steps. The only addition is an
   input path: `--cap_trace FILE` (CSV `t_rel_s,node,dir,mbps`), expanded into the same event list (a command line
   cannot carry hundreds of events). No new mechanism, no planner change.
2. **Trace-driven move schedule.** `--move_trace FILE` (CSV `t_rel_s,dest`) replaces the fixed T_m schedule: the
   network harness's per-session schedule list and the GPU harness's move loop read explicit move times and
   destinations. Revisits are allowed (both harnesses support them).
3. **Validity with time-varying caps.** Paced egress per node <= 1.05 x the time-averaged cap in every 10 s window (the
   current check uses the larger of the initial and final cap); NIC peaks <= 1.15 x the window's maximum cap; an
   alignment check that every scheduled cap change was applied within 1 s of its trace time (logged `cap_change`).
4. **Logging for event-level analysis.** Already logged: restoration time per move and after the final move, source /
   total bytes, flows (provider, destination, fragments, start/end), every re-plan (time, bottleneck provider, moved
   fragments per new provider, measured rates, ETA before/after, C_switch, margin). Add at each plan and re-plan: the
   full assignment (fragment ids per provider) before and after, the holders' verified sets, and in-flight fragments,
   so the decision state can be reconstructed offline.
5. **Offline event-level counterfactual (analysis code only).** A state-injection entry point for the fluid model
   (`tools/eval/restore_model.py`, which already accepts the same cap-event syntax): start from the logged state at a
   re-plan decision and simulate, under the recorded remaining cap trace, (i) the pre-re-plan assignment continued and
   (ii) the re-plan applied; the difference is the model-estimated effect of that single decision on completion time
   and bytes.

## Policy-level versus event-level benefit

- **Policy level:** paired runs of each policy on the identical trace segment (same mobility segment, same
  cross-traffic segment, same alignment); differences in completion time / bytes between OTTER event-driven and OTTER at
  moves are the policy-level effect of event-driven re-planning on that segment.
- **Event level:** a single re-plan is classified only from the counterfactual of item 5, never from policy-level
  completion times (a run can finish faster for reasons unrelated to a given re-plan). Each classification states the
  model's error bound: the model is first validated on the executed branch (predicted vs measured completion of the
  same run); a re-plan is "beneficial" / "harmful" only if the counterfactual difference exceeds that bound, otherwise
  "indistinguishable". Model fidelity itself is reported.

## Policies

M1 only (`restart`), M1 + M2 (`reuse_fixed` / GPU `split`), OTTER at moves (`reuse_aware_in`), OTTER event-driven
(`reuse_dyn`). Placement needs a destination prediction that the mobility traces do not provide, so it is disabled
and "Full OTTER" equals OTTER event-driven (prereg v3 section 3 definition); "Full OTTER at moves" equals OTTER at moves.

## Reproducibility

- Trace preprocessing is a deterministic script from the raw files (recorded with their SHA-256) to the CSV inputs;
  segment ids, offsets and the cell-to-site clustering k are written into every run's config.
- Segment choice is fixed before any run by a seeded, stratified rule computed from trace statistics only
  (`preregistration.md`); the list is committed with the preregistration.
- Alignment: trace time 0 = the run's start (t0); cap changes and moves at their trace times (1 s resolution).
- Paired comparisons: every policy runs every segment; policy order within a rep is randomized with a recorded seed;
  reps of a segment run back to back on the same hosts and commit.
- The existing validity rules (`tools/eval/expD_validity.py`) apply, plus item 3.

## Not planned

No change to M3's rules or thresholds; no placement; no Star/Line/Tree/Butterfly selection; no new transport.
