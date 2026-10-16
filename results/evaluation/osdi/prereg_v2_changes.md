# Experiment D preregistration: v1 (7800261) -> v2 (DRAFT, not frozen), 2026-10-16

Only `gpu_end_to_end_preregistration.md` and two lines of `figure_manifest.md` (F8c, F8 hypothesis note) changed. No
code, plotting script, data, or earlier frozen hypothesis was modified.

## G1-G9 before / after

| | v1 | v2 | why |
|---|---|---|---|
| G1 | OTTER TTFO <= 1.0 s at 1 Gbps and native; <= 0.1 x full migration at 1 Gbps | unchanged; "OTTER" now named "OTTER event-driven" (= Full OTTER without a prediction) | naming only |
| G2 | rejoin - bind <= 6 s | rejoin delay (wall clock) <= 6.0 s **and** rejoin calls after bind <= 8; both reported per run | item 5: wall-clock and call-count recovery are different quantities (calls are bandwidth-independent, seconds depend on chunk time) |
| G3 | M1+M2 source <= 1.1, M1-only >= 1.4; bind-ready within 1 s | four separated clauses: (a) source bytes <= 1.10 vs >= 1.40; (b) discarded <= 0.10 vs >= 0.40; (c) verified progress reused >= 0.85 vs 0; (d) bind-ready within 1.0 s. Aggregate bytes reported, **not** a pass condition (Phase 1 measured them equal) | item 1: v1 mixed traffic classes and left aggregate traffic implicit; Phase 1 shows preservation cuts source and discarded bytes, not aggregate bytes or single-ingress latency, so the hypothesis now says exactly that |
| G4 | bind-ready <= no-placement - 0.5 x x_placed x T_s | unchanged | - |
| G5 | bind-ready within 1.5 s of no placement; source bytes <= 1.02 | (a) bind-ready within 1.5 s; (b) **total source = pre-move placement + post-move restoration** <= 1.02; (c) post-move source <= 1 - x_placed + 0.02; (d) forwarded by holders >= 0.9 x x_placed; pre-move, post-move and aggregate (expected 1 + x_placed) reported separately | item 2: v1's "source bytes" was ambiguous about placement traffic |
| G6 | Full OTTER and M1+M2 bind-ready <= M1-only - 3.5 s (scenario E) | same threshold; scenario and hypothesis labelled **hybrid GPU/network contention** (one GPU generation session + three network-level restoration sessions); claim limited to source-egress contention | item 4 |
| G7 | Full OTTER <= 0.5 x M1+M2 (scenario F) | **primary:** OTTER event-driven <= 0.5 x OTTER at moves, <= 2 re-plans, 0 duplicates, and 0 re-plans / within 1.0 s of at-moves in the no-change scenarios B and G; **secondary (reported):** vs M1+M2 and M1 only | item 3: the mechanism under test is event-driven re-planning, so its baseline is the same planner without it; "OTTER at moves" added as a policy (was an ablation note) |
| G8 | progress-preserving bind-ready at revisited B <= 0.6 x M1-only | unchanged; policy list now names OTTER at moves and event-driven explicitly | - |
| G9 | steady-state service time within 2 %; destination memory within 1 % | unchanged; run size fixed (3 reps x 200 chunks) and measured with t_decode logging enabled | item 6 consequence |

## Other changes

- **New section 0**: lists every earlier frozen outcome (H1 ... H8c) verbatim and states that Experiment D neither
  re-tests nor reinterprets them (item 9).
- **Section 2, state-consistency scope** (item 8): evaluation restricted to the single Sink version frozen at the
  trigger; repeated-mobility scenarios use the dog workload only; generalization clips moved to scenario A only (they
  promote after bind, which would create a second version on repeated moves); runs with version events are flagged and
  excluded from G criteria. v1 had generalization in scenarios A and B.
- **Section 3, policies**: "OTTER at moves" added; "Full OTTER" defined as event-driven + top-1 placement where a
  prediction exists (C, D) and equal to event-driven elsewhere (placement disabled for every policy without a
  prediction).
- **Section 5, external baselines** (item 7): two separate comparisons, *as designed* (vs a new **OTTER
  cold-destination** sensitivity run that also pays process start and weight load) and *warm destination* (reported as
  not applicable where the system recreates the process; image-without-weights time as a labelled lower bound). Driver
  575.51.03 caveat and the fallback labelling ("not a cross-node migration") added. v1 had a single "as designed vs
  weights preloaded" sentence.
- **Section 6, streaming latency** (item 6): three timestamps defined - chunk completion (exists), frame decode
  completion (new logging), frame delivery (requires a consumer that does not exist). Inter-frame metrics are now
  decode-level and descriptive; the deadline-miss rate is renamed a decode-deadline proxy; **no frame-level SLO
  compliance is claimed** unless delivery semantics are implemented. v1 defined "inter-frame latency" and "deadline miss
  rate" without delivery semantics.
- **Section 6, network metrics**: source bytes split into pre-move and post-move with total defined; verified progress
  reused and forwarded-by-holders added.
- **Sections 8-9**: implementation list gains items 6-7 (new metrics, cold-destination variant) and the two-host restore
  test before external C/R; run count 180 -> ~177 (generalization reduced to scenario A; OTTER at moves added to B, F,
  G; cold-destination and external comparisons added to A).

## Remaining ambiguities and risks

1. **Delivery semantics**: is a consumer process (and which transport / playout clock) in scope? Without it the
   paper can make no frame-level SLO claim; F8c stays decode-level.
2. **External C/R on driver 575.51.03**: cross-node restore unverified; the two-host test decides whether scenario A's
   external rows are cross-node migrations or labelled same-node C/R + transfer.
3. **OTTER cold-destination** is a new variant that has never run; its process-start and weight-load times are not
   measured yet (they also bound how much of a C/R baseline's cost is weight transfer).
4. **G3(c) threshold 0.85** rests on a derived Phase 1 estimate (~0.92-0.93), not a direct measurement; the new metric
   is implemented for the first time in Experiment D.
5. **G6 hybrid**: the three network-level sessions do not load the source GPU; any GPU-side contention at A is absent.
6. **G7 no-change clause** depends on the E-pilot v2 thresholds behaving the same on GPU hosts with generation load
   (CPU contention for sender threads and measurement noise).
7. **G2 call bound (<= 8)** assumes the chunk length is unchanged on the destination; t_decode logging could shift it
   (G9 checks steady state only).
8. **Bind step**: network-level predictions add ~0.3-0.4 s for bind (measured once at 1 Gbps); the bind time under
   repeated moves on GPU is unmeasured.

## GO / NO-GO for freezing

**Conditional GO.** G1-G9 are now well-defined on metrics the harness produces or will produce with the listed
implementation, and none depends on frame delivery or on an external system. Recommended: freeze G1-G9 as written
after the reviewer accepts them, with two conditions recorded at the freeze: (i) frame-delivery metrics stay out of
scope (descriptive decode-level metrics only) unless a consumer is specified before the first run; (ii) external C/R
remains descriptive, and its comparison type (cross-node vs labelled same-node C/R + transfer) is fixed by the
two-host test before any external run. If the reviewer wants delivery-level SLO claims, it is NO-GO until the consumer
and its semantics are specified.
