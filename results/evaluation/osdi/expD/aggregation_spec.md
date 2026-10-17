# Experiment D aggregation specification (written 2026-10-17, before any Experiment D sweep data)

How `tools/eval/aggregate_expD.py` applies the frozen G1-G9 text (`../gpu_end_to_end_preregistration.md`, v3, 81bb628)
to the run summaries. The criteria are not changed here; where the frozen text leaves a choice open, the choice is
stated below and marked **[interpretation]** so it can be reviewed before any data exists. Nothing here was chosen with
sweep data in view; the only GPU data seen so far are correctness runs (D0 shakedown, its re-run, the focused tests).

## Data and validity

- One directory per scenario: `expD_A`, `expD_B`, `expD_C`, `expD_D`, `expD_E`, `expD_F`, `expD_G`, `expD_G9`, and
  `expD_Agen_<clip>_s<seed>` for the generalization set. A configuration = (scenario, policy, bandwidth, rho, path,
  placement policy, cold destination); reps are its run directories.
- Run validity: `tools/eval/expD_validity.py` (prereg section 7 "Run validity"). Invalid runs are listed with reasons,
  excluded from every criterion and re-run (`--skip_done` re-runs a configuration + rep until a valid run exists); no
  run is deleted. A run with any Sink-version event is invalid (prereg section 2 (iv)).
- Every criterion uses the **median over valid reps** of each configuration (prereg section 7 header). A configuration
  with fewer than 3 valid reps is reported as "insufficient reps" and its criteria as not evaluable.
- Scenario A reps: 3, or 5 when the IQR of TTFO or of bind-ready over the 3 valid reps exceeds 10 % of its median
  **[interpretation: the frozen text does not name the metric; TTFO and bind-ready are the two scenario-A latencies]**.
  The aggregator writes the configurations that need reps 4-5 to `expD_extra_reps.json`; the driver runs them.

## Quantities (all from `summary.json` unless stated)

- TTFO = `latency_after_final_move_s.first_output` (trigger = the move's handoff request; single move: the move).
- Sink bind-ready = `latency_after_final_move_s.continuity_ready` (first chunk completed with the Sink bound; Full
  migration: its first chunk; revisit: the final ownership only).
- Rejoin delay = `final.rejoin_rel_s - final.first_bound_output_rel_s`; rejoin calls = `continuity.rejoin_calls_after_bind`.
- Source bytes B_source,total = `d0.source_bytes_total_sinks` (B_pre + B_post); B_post, B_pre, B_fwd, x from `d0`.
- Discarded bytes (Phase 1 definition (a)): bytes of `recv` rows in the run's `fragments.csv` classified `wasted`
  (delivered to a non-final node and never forwarded by it) whose destination never bound the Sink (no `sink_bind`
  event of that node in `events.csv`), divided by the Sink size.
- Re-plans = `d0.n_replans`; duplicates = `bytes.duplicate` (orchestrator) plus `recv` rows with ok = False in the
  node logs.
- T_s = 14.05 s (the measured 1 Gbps transfer-ready time used for every T_m) for G4 **[interpretation: G4 writes
  "x T_s" without naming the value]**.

## Criteria

- **G1** (A): OTTER event-driven TTFO <= 1.0 s at 1 Gbps and at native, and <= 0.1 x Full migration's TTFO at 1 Gbps.
- **G2** (A): OTTER event-driven rejoin delay <= 6.0 s and rejoin calls <= 8, at 1 Gbps and at native.
- **G3** (B), separately at rho 2 and rho 4, all of: (a) M1 + M2 source bytes <= 1.10 and M1 only >= 1.40; (b) M1 + M2
  discarded <= 0.10 and M1 only >= 0.40; (c) |bind-ready(M1 + M2) - bind-ready(M1 only)| <= 1.0 s
  **[interpretation: "within 1.0 s" = absolute difference]**. Retained / reused: descriptive.
- **G4** (C): bind-ready(Full OTTER) <= bind-ready(M1 + M2, no placement) - 0.5 x x x T_s, x = Full OTTER's
  `x_verified_at_move` at the destination **[interpretation: the frozen text has no explicit subject; Full OTTER is the
  system under test; M1 + M2 + top-1 and the oracle are reported against the same bound, not judged]**.
- **G5** (D), for Full OTTER **[interpretation: same subject as G4; M1 + M2 + top-1 reported against the same clauses,
  not judged]**, all of: (a) |bind-ready(Full OTTER) - bind-ready(M1 + M2, no placement)| <= 1.5 s **[interpretation:
  "within" = absolute]**; (b) B_source,total <= 1.02; (c) B_post <= (1 - x) + 0.02; (d) B_fwd >= 0.9 x, with x = verified
  at the misplaced holder (the top-1 candidate) at the trigger; (d) is "not evaluable" for a run whose orchestrator
  `fragments.csv` lacks a `recv` row for any fragment the final owner verified.
- **G6** (E): GPU session bind-ready: M1 + M2 <= M1 only - 3.5 s and OTTER event-driven <= M1 only - 3.5 s. Network
  sessions' restoration times reported separately.
- **G7** (F, B, G): (primary, F) bind-ready(OTTER event-driven) <= 0.5 x bind-ready(OTTER at moves), with re-plans <= 2
  and duplicates = 0 (medians); (no change) in B at rho 2, B at rho 4 and G: OTTER event-driven re-plans = 0 (median)
  and |bind-ready(OTTER event-driven) - bind-ready(OTTER at moves)| <= 1.0 s. Secondary (F): OTTER event-driven vs
  M1 + M2 and M1 only, reported. Re-plan counts of every rep are listed next to the medians.
- **G8** (G): for each of M1 + M2, OTTER at moves, OTTER event-driven: bind-ready at the revisited B <= 0.6 x M1 only's.
- **G9**: (steady state) |median chunk interval OTTER-enabled / unmodified - 1| <= 0.02 over 3 reps of 200 chunks
  (`tools/eval/steady_state.py`; definition of the two modes in its docstring) **[interpretation: "chunk service
  time" = interval between consecutive chunk completions; "within 2 %" = absolute relative difference]**; (memory)
  scenario A, per bandwidth: (max - min) / min of the destination's median peak `memory_allocated` over Full migration,
  Cold restart, M1 only and OTTER event-driven <= 0.01 (warm destination only).
- **External C/R**: not run (blocked); reported as such.
- **Generalization** (`expD_Agen_*`): TTFO, bind-ready, rejoin per clip and seed, descriptive.

Every criterion is reported as SUPPORTED / NOT SUPPORTED / NOT EVALUABLE with the medians it used and the valid / invalid
rep counts; no criterion is evaluated on fewer than 3 valid reps.
