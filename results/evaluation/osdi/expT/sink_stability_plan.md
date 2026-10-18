# Experiment T - 4. Sink-version stability measurement plan (DRAFT, 2026-10-17; nothing run)

## Why

OTTER restores one Sink version per restoration (prereg v3 scope conditions 5-6). If the Sink changes at an owner
while a restoration is in progress, holders' fragments become stale; that path (re-fetch of a new version) is not
implemented. Experiment D used the dog workload, which shows no promotions in its measured window. How often a version
change falls inside a restoration window on other workloads is the open measurement named in prereg v3 section 2.

## Input format (verified in the code, 2026-10-17)

The pipeline is video-to-video: `configs/wan_causal_dmd_v2v.yaml`, input video (resized to 480x832) plus a text
prompt; the harness `Runner` (`tools/state_ablation.py`) feeds the input frames of each chunk at every call. A T2V
branch exists in `streamv2v/inference.py` but not in the harness path. Hence workloads need a video and a prompt;
text-only prompt suites (VBench, EvalCrafter) are not usable as they are.

## What a version change is in this pipeline

- **Adaptive sink refresh (promotion):** in `models/wan/causal_model.py`, when the cosine similarity between a new
  frame's keys/values and a sink slot falls below `adapt_sink_threshold` (0.2 in the config), that slot is queued for
  eviction and later overwritten by a new frame: the Sink's content changes (a new version).
- **t_refresh realignment:** every `t_refresh` (50) latent frames the RoPE positions are rewound and cached keys
  re-rotated; positions change, sink content does not (handled at bind by re-rotation; not a version change).

## Measurement (uninterrupted generation, no OTTER transfer)

Per workload, run the unmodified pipeline for M + N calls (as a node baseline) and record per call:
1. the sink-slot positions (existing `slot_positions`), and the eviction-queue insertions that target a sink slot,
   per layer (the refresh decision);
2. a cheap per-slot content fingerprint (e.g. the sum of layer-0 keys of each sink slot) to separate a content change
   (promotion) from a position change (realignment);
3. call index and wall time.

Derived, per workload:
- promotions per 100 calls, their call indices and spacing;
- **P(change in window)**: for every call c taken as a hypothetical trigger, whether a promotion occurs in [c, c + W],
  W = restoration length in calls: 1 Gbps T_s / service time = 14.05 s / ~0.555 s ~ 25 calls; native ~3.1 s ~ 6 calls;
  repeated mobility (bind after the final move at ~15 s after a 14 s schedule) ~ 52 calls;
- affected state volume per promotion: slots x layers x bytes per slot (the Sink is 1.61 GiB for 3 slots x 30 layers
  x k = 2 rows; one slot of all layers ~ 0.54 GiB), reported per event.

## Workloads

- W-a: repository clips (dog, bird, boxing, train with their prompt files), seeds 0 and 1, k = 2.
- W-b: LOVEU-TGVE-2023 videos with their four editing prompts (`trace_candidates.md`), a seeded random subset of 20
  videos x 4 prompts, seed 0 (all 76 if time allows). Clips have 32 or 128 frames and loop to fill a run; loop
  boundaries are marked and promotions within 2 calls after a boundary are reported separately (a loop cut is an
  artificial scene change).
- Cost (one session per GPU): ~3.5 min per workload-seed (330 calls x ~0.555 s + model load); W-a ~ 30 min, W-b subset
  (80 runs) ~ 4.7 h on one GPU, ~1.2 h on the four GPU 0s.

## Reporting rule

Version-change frequency is itself the result: every workload is reported, with or without promotions. In the
trace-driven study (`preregistration_draft.md`), a run with a Sink-version event is flagged, excluded from the criteria
as Experiment D's scope rule requires, and listed with its count and timing in the descriptive results; it is never
dropped silently.
