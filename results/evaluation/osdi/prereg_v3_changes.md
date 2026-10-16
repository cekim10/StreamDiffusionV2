# Experiment D preregistration: v2 (5267075) -> v3 (DRAFT, not frozen), 2026-10-16

Only `gpu_end_to_end_preregistration.md` changed (plus this file). No code, plotting script, data, or earlier frozen
hypothesis or outcome was modified. One read-only analysis of existing Phase 1 logs was run (below); nothing was executed
on GPUs or the network.

## Changes

| item | v2 | v3 |
|---|---|---|
| G3(c) | pass criterion "verified progress reused >= 0.85", threshold derived indirectly from discarded bytes | **removed as a criterion.** Split into two descriptive metrics: *verified progress retained* (fragments verified at an abandoned owner still held at the next move) and *verified progress reused* (distinct such fragments that the final owner actually received and verified from an abandoned owner). The remaining G3 criteria (a) source bytes, (b) discarded bytes, (c, was d) bind-ready within 1.0 s are unchanged. |
| G3 reference values | derived ~0.93 / ~0.92 | **directly measured** from Phase 1 per-fragment logs (read-only): reused 0.974-0.983 at rho 2 (3 sweep reps + 1 shakedown rep), 0.961-0.967 at rho 4; restart 0. Reported as reference only; not promoted to a threshold, per the review. |
| G4 | x_placed = "Sink fraction verified at the destination at the move" | x = fraction fully received **and checksum-verified** at or before the move trigger (same definition as G5) |
| G5 | x_placed loosely defined; "source bytes", "forwarded by holders" | x defined as fully received + checksum-verified at the misplaced holder at or before the trigger, in-flight excluded. Explicit B_pre, B_post, **B_source,total = B_pre + B_post**, B_fwd, **B_network,total** reported every run. (a) bind-ready within 1.5 s, (b) B_source,total <= 1.02, (c) B_post <= 1 - x + 0.02 unchanged; (d) B_fwd >= 0.9x **kept as a pass criterion** because the GPU harness logs per-fragment `recv` rows with sender and checksum result (verified in `repeated_mobility/*/fragments.csv`); a run lacking those records reports (d) as not evaluable instead of inferring it. Duplicates counted (the identities assume single delivery). |
| Metrics table | one "Source bytes" row, "Forwarded by holders" without data source | separate rows for B_pre, B_post, total source, B_fwd (with its log source), aggregate network bytes, retained, reused, x |
| External baselines | two comparisons (as designed vs OTTER cold destination; warm destination) | **two separate groups**: (1) *primary migration comparison* - OTTER, Full migration, Cold restart, all warm destination; all G1-G9 headline numbers come only from here; (2) *external system comparison* - C/R as designed, OTTER cold destination, C/R lower bound where applicable. Warm OTTER is never put on a speedup axis against as-designed C/R. (3) A separate **compatibility table** for failed cross-node restores, which are not plotted on performance axes. |
| State consistency | scope section with a "stated limitation" | adds an **explicit evaluation assumption** to be stated in the paper: repeated-mobility evaluation assumes a stable Sink version during a restoration; M2/M3 are evaluated only within one Sink version; concurrent Sink-version evolution is not supported and not claimed; promotion frequency on other workloads is an open measurement outside Experiment D. |
| Earlier frozen outcomes | listed in section 0 | unchanged |

## Recommendation on freezing G1-G9

**GO - G1-G9 can be frozen as written in v3**, with the two conditions recorded in v2 carried into the freeze commit:
(i) no frame-delivery or frame-level SLO metric is in scope unless a consumer with defined delivery semantics is
specified before the first run (decode-level metrics stay descriptive); (ii) external C/R stays descriptive and its
comparison type (cross-node vs labelled same-node C/R + transfer, or compatibility-table failure) is fixed by the
two-host restore test before any external run. Every remaining pass criterion is now defined on quantities the GPU
harness either already logs (t_chunk, per-fragment `recv` with sender and checksum, flows, events) or that are listed
as implementation items with a defined source (t_decode, version-event counters, cold-destination timing). The review
items with inferred thresholds (G3(c)) are now descriptive.

Residual risks (unchanged from v2 unless noted): OTTER cold destination has never run; G6 hybrid has no GPU-side load
at A; G7's no-change clause on loaded GPU hosts; G2's call bound under decode logging; bind time under repeated moves
unmeasured; cross-node C/R on driver 575.51.03.
