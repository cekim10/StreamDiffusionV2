# Experiment VC - visual continuity of OTTER's resumed output: preregistration REVISED DRAFT 2 (2026-10-22)

Status: **REVISED DRAFT 2 for review. Not frozen; nothing implemented or run; no participant recruited.** Revision of
draft 1 (db0c42c) per the review of 2026-10-22: three continuity notions separated (section 1), VC-H1 narrowed to
post-bind motion consistency, VC-H2 against COLD and REF's own variation with effect sizes, V4 descriptive (no JND
threshold), V5 split into content similarity and prompt alignment with proposed models and margins (section 5), V6
auxiliary, Wait-for-Sink semantics, no assumed equivalence of exact migration methods to REF, OT-R = M1 + M2, human
evaluation as a separate optional phase. No frozen experiment, result or mechanism (M1 / M2 / M3-v2) is changed.

## 1. Question and the three notions kept apart

Does leaving the reference trajectory mean the user sees a visibly discontinuous video? Two cases must be told apart:
**Case A, breakage** (a visible jump, a color or appearance shift, lost content, motion that no longer follows the input)
and **Case B, plausible divergence** (consistent and faithful to input and prompt, but not pixel-equal to REF).

| notion | object measured | question | metrics |
|---|---|---|---|
| **generation continuity** | the generated frame sequence, indexed by call (no wall-clock time) | do consecutive generated frames, across the move, the Sink-less window and the bind, form a consistent video? | V1-V5 (V6 auxiliary) |
| **playback continuity** | what a viewer sees in wall-clock time: generated frames placed at their measured delivery times, the last frame held while nothing arrives | how long does the picture freeze, and how large is the jump when it resumes? | P1-P3 (section 4.2) plus V1 at the resume point |
| **reference-trajectory recovery** | per-call PSNR / SSIM to REF | does the stream return to the uninterrupted one? | crossing, sustained 10 calls, terminal median (as in RD / WX) |

No result for one notion is read as evidence for another. In particular, low PSNR to REF is never read as a continuity
failure, and a good generation-continuity score is never read as good playback continuity (Wait-for-Sink can generate
consistent frames after a long freeze).

## 2. What is already known (seen before this draft; disclosed)

- RD (frozen f850072), last 10 calls of the horizon: input-motion-conditioned warp-error ratio E_O / E_R 0.97-1.02 and
  motion ratio 0.97-1.01 in every condition, including streams ending at 28 dB.
- RD, Sink-less window: E_O / E_R 1.23-1.60 (refresh-heavy) and 1.77-3.12 (dog). Reset frame-difference spike median
  5.5x the local median (max 16.6x; REF 1.0x); bind 1.6x.
- State-study figure (dragonD, one run): the No-Sink-KV condition shows a color drift that persists.
- RD's own conclusion: none of these metrics establishes perceptual continuity.

VC-H1 is therefore partly a replication of an RD observation on new schedules, and is labelled so. All other hypotheses
use conditions (COLD, WFS, playback) or metrics (V4, V5) that RD did not measure.

## 3. Outputs and conditions

### 3.1 How the frames are obtained

Real runs do not store output frames. The RD emulator reproduces real runs call by call on one GPU (11 of 11 real runs,
per-call |dPSNR| 0.00 dB). VC adds a frame-saving option to the emulator, and a COLD restart operation
(`Runner.restart_at`, the existing official prompt-switch path). Frames are stored losslessly (FFV1) on the testbed
from 16 calls before the first reset to 100 calls after the final bind. They are not committed, and LOVEU-derived frames
are never redistributed.

### 3.2 REF and the exact migration methods

**REF is the uninterrupted single-node stream** (the node baseline: same seed, input and calls). Full migration, P-full
and R-full are **not assumed to equal REF**. Their equivalence is a claim to be verified on the real GPU (XB exactness
gate: per-call output digest after the switchover). Until that gate passes and is reviewed, VC neither substitutes
them for REF nor makes any statement about them. If it passes, the paper may say that their generated frames equal
REF's on the verified runs; their playback still differs (they stall during transfer or replay).

### 3.3 Conditions per input (inputs: dog, train, butterfly-feeding-slow-motion, audi-snow-trail; seed 0)

| id | condition | schedule source | generation | playback timeline |
|---|---|---|---|---|
| REF | uninterrupted | - | baseline | one frame every 1/16 s (section 4.2) |
| OT-1 | OTTER, single move, 1 Gbps | realized reset and bind calls of the frozen W2 seed-0 `reuse_dyn` run of the input (audi-snow-trail has two such runs: the earlier valid one). With one move from one source the schedule is one reset and one bind; VC uses the realized calls and evaluates no M3 behavior | reset at the move (M1 fast path), Sink-less until the bind, bind | the realized run's delivered-chunk times |
| OT-L | OTTER, single move, slow link | RD-X realized schedule (reset 80, bind 154; real runs for butterfly, audi, dog). Train has no RD-X run, so the same calls are emulated and labelled "schedule copied" | as OT-1 | RD-X delivered-chunk times (train: those of the dog RD-X run, labelled) |
| OT-R | **M1 + M2 under repeated mobility** (policy `split`, A -> B -> C -> D, rho 2). **Not M3-v2**: with no network change, M3-v2 does not change the realized schedule, and VC does not evaluate M3. | WX X3 `split` rep 1 (butterfly, audi, train) and the frozen dog equivalent (M3E S4 `split` rep 1) | a reset at every move, final bind | the realized run's delivered-chunk times |
| WFS-1, WFS-L | Wait-for-Sink at the OT-1 / OT-L move | same move call, and the bind time of the same realized run | see section 3.4 | the last pre-move frame held from the move until the realized bind time, then generation resumes |
| COLD-1, COLD-L | cold restart at the OT-1 / OT-L move | same move call | a fresh session from the prompt and [last frame, current chunk] (`restart_at`); no state carried | held frame for the measured cold-restart time from the frozen W2 `cold` runs (the value is read from those runs at implementation, not assumed) |

### 3.4 Wait-for-Sink semantics (WFS)

- At the move, the source stops and the destination receives the M1 fast path. **No frame is generated until the Sink
  is restored**: the exact Sink snapshot of the source at the move is bound **before** generation resumes. In the
  emulator this is the RD d = 0 condition (reset and bind before the same call).
- The recent KV and VAE caches are rebuilt by the M1 path, **not** restored. WFS's output can therefore still differ
  from REF; it is measured, not assumed equal.
- Generation resumes at the call where it stopped. The input frames that a live camera produces during the wait are not
  generated in the harness; a live system would skip or delay them. This is stated as a harness property.
- **The waiting time is part of WFS's playback.** The freeze lasts the measured time from the move to the bind in the
  same realized run (OT-1's or OT-L's), so WFS is compared with OTTER at the same network condition. A WFS result is
  never reported on generation continuity alone.

## 4. Metrics

### 4.1 Generation continuity (per window: boundary +-2 calls of each reset and bind, Sink-less window, first 20 calls after the final bind, last 10 calls)

| id | measures | definition | role |
|---|---|---|---|
| V1 | boundary discontinuity | frame-difference spike at a reset, bind or resume: the mean absolute difference between the last frame before and the first frame after, divided by the median consecutive-frame difference of the same stream over the 16 preceding calls (RD definition) | VC-H2 |
| V2 | temporal consistency | input-motion-conditioned warp-error ratio E_O / E_R (RD definition; Farneback flow of the input at 1/4 resolution) | VC-H1, VC-H3 |
| V3 | motion following | motion magnitude ratio output / REF (RD definition) | VC-H1 |
| V4 | **global color drift** | CIEDE2000 between the window's mean CIELAB color and REF's at the same calls, and between the window and the 16 pre-move calls of the same stream; REF's own drift against its pre-move calls is reported next to it for scale | **descriptive only; no threshold** |
| V5a | content similarity | section 5 | VC-H4 |
| V5b | prompt alignment | section 5 | VC-H5 |
| V6 | per-frame / per-clip quality, no reference | section 5 | **auxiliary only**: reported next to V1-V5; never used alone, and never as the deciding metric of any hypothesis |

### 4.2 Playback continuity

Playback model, fixed now: the client shows one frame every 1/16 s, starting with a playout buffer of one chunk (4
frames); frames are shown in order, never skipped; if the next frame has not been delivered at its display time, the
previous frame stays on screen (a stall) until it arrives. Delivery times come from the realized runs (section 3.3).

| id | measures |
|---|---|
| P1 | stall count and total stall time from the move to 100 calls after the final bind |
| P2 | longest single freeze |
| P3 | the V1 jump at every resume after a stall, measured between the frozen frame and the next shown frame |

### 4.3 Reference-trajectory recovery (context)

PSNR / SSIM to REF per call; first call >= 35 dB, sustained 10 calls, terminal median (calls b + 90 .. b + 99), exactly as
in RD / WX.

## 5. Proposed models for V5 and V6 (for review; licenses checked 2026-10-22 from the primary sources listed)

| metric | proposed model | why | license (as stated by the source) |
|---|---|---|---|
| **V5a content similarity** | **DINO ViT-B/16** (`facebookresearch/dino`, `dino_vitb16`), L2-normalized image features, cosine similarity | self-supervised image features that track object identity and appearance rather than text; the same model and the same comparison (to the first frame and to the previous frame) as VBench's "subject consistency" dimension, so the definition is an established one and the numbers are comparable with that benchmark | Apache-2.0 (repository LICENSE) |
| | DINOv2 ViT-B/14 (sensitivity only) | newer features; checks that conclusions do not depend on the DINO version | Apache-2.0 for code and weights (repository README) |
| **V5b prompt alignment** | **OpenAI CLIP ViT-L/14**, image-text cosine similarity per frame (CLIPScore-style) | the standard image-text alignment measure; VBench uses this CLIP backbone for its aesthetic dimension | MIT (repository LICENSE) |
| **V6 auxiliary quality** | **DOVER** (clip-level technical and aesthetic quality) | a no-reference video quality model that separates technical from aesthetic quality | S-Lab License 1.0: use for non-commercial purposes permitted; commercial use needs the authors' permission. Adequate for academic evaluation; stated in the paper |
| | MUSIQ trained on SPAQ via IQA-PyTorch (alternative) | per-frame imaging quality as in VBench's "imaging quality" dimension | IQA-PyTorch code: PolyForm Noncommercial 1.0.0 (plus NTU S-Lab License for some components); its weights repository asks users to respect each original model's license, and **the original MUSIQ weights' license was not verified** - not used until it is |

ViCLIP (VBench's video-text "overall consistency") is not proposed: its weights' license was not checked.

**V5 definitions.**
- V5a(window) = mean over the window's frames of the cosine similarity between DINO features of the frame and of the
  mean feature of the 16 pre-move calls (identity kept from before the move), and, separately, the VBench-style score
  (first-frame and previous-frame similarity averaged).
- V5b(window) = mean over the window's frames of the CLIP ViT-L/14 image-text cosine with the input's prompt.
- **Prompt alignment is read only relative to REF.** The pipeline is video-to-video: the dog workload is a cat video
  with a dog prompt, so the absolute alignment of every stream, REF included, reflects the input as much as the prompt.

**Proposed preregistered margins (REF's own variation, computed from REF alone, before any OTTER frame is scored).**
For each input, slide a 10-call window over REF's evaluated span (16 calls before the move to 100 after the final bind)
and take the distribution of the window statistic. The **REF band** is its 5th-95th percentile range.
- VC-H4 (content) holds for an input if OTTER's post-bind-20 and terminal-10 V5a are **not below REF's 5th percentile**.
- VC-H5 (prompt) holds if OTTER's post-bind-20 and terminal-10 V5b are **not below REF's 5th percentile**.
- The effect size is reported in every case as (OTTER - REF median) / (REF P95 - REF P5), with the window values.
- Rationale: a margin taken from the reference stream's natural fluctuation needs no external perceptual threshold,
  which the literature does not supply for these embeddings. It is fixed before OTTER is scored. Its limitation is that
  a stream with little natural variation gets a narrow band; this is reported per input.

## 6. Hypotheses (thresholds fixed at the freeze; effect sizes always reported)

| id | notion | statement | success rule (proposed) | effect sizes reported |
|---|---|---|---|---|
| **VC-H1** | generation | **post-bind motion consistency**: after the final bind, OTTER's frames follow the input's motion as consistently as REF's (replication of an RD observation on new schedules). This is **not** a perceptual-continuity claim | last-10-call and post-bind-20 E_O / E_R <= 1.10 and motion ratio in [0.90, 1.10], every input, OT-1 / OT-L / OT-R | the ratios with bootstrap 95 % CI over calls |
| **VC-H2a** | generation | OTTER's reset discontinuity is no larger than a cold restart's at the same call | V1(OT reset) <= V1(COLD) for OT-1 and OT-L, every input | ratio V1(OT) / V1(COLD) |
| **VC-H2b** | generation | OTTER's reset discontinuity is within REF's normal frame-to-frame variation | V1(OT reset) <= REF's 99th percentile of V1 over all calls of its evaluated span | V1(OT) / REF P99 and V1(OT)'s percentile rank in REF's distribution; also for each OT-R reset and each bind. RD's prior (median 5.5x the local median) predicts H2b fails; it is tested and reported either way |
| VC-H3 | generation | the Sink-less window is temporally less consistent than REF | descriptive | window E_O / E_R, V1 inside the window, V4 |
| VC-H4 | generation | OTTER keeps the content after the bind | section 5 margin (V5a) | section 5 effect size |
| VC-H5 | generation | OTTER keeps prompt alignment relative to REF after the bind | section 5 margin (V5b) | section 5 effect size |
| VC-H6 | playback | descriptive trade-off: OTTER vs WFS vs COLD at the same move | none (descriptive) | P1-P3 per condition; for WFS also its generation metrics after the resume |
| - | color | V4 global color drift | **descriptive only** | V4 per window, with REF's own drift |

V6 is reported next to every hypothesis and never decides one.

**Mapping to paper statements (fixed now).**
- H1 supported: "after the Sink is bound, the resumed stream follows the input's motion as consistently as the
  uninterrupted stream on the tested inputs." Nothing about perceptual quality follows from H1.
- H1, H2a, H4 and H5 supported: the paper may describe the post-bind divergence as plausible divergence (Case B) on
  the tested inputs and schedules. It must also report H3 (the Sink-less window is less consistent), H2b (the size of
  the reset jump relative to normal variation), V4 (color drift) and the playback trade-off (H6).
- H4 or H5 fails, or V4 shows a drift beyond REF's own range: the trajectory loss is reported as a visible cost (Case
  A). A continuity-first resume mode would be a separate design question; nothing is added before this result.
- No VC result is read as evidence about latency, bytes or restoration correctness, and VC makes no claim about M3-v2.

## 7. Phases

| phase | content | status |
|---|---|---|
| VC-0 | emulator frame saving and COLD operation, playback model, metric code (DINO, CLIP, DOVER), dry and loopback tests on the fake runtime, a CPU check of the metric code on repository clips | after review |
| VC-1 | GPU emulation: 4 inputs x 7 generated conditions (OT-1, OT-L, OT-R, WFS-1, WFS-L, COLD-1, COLD-L) plus REF = 32 sequences, one GPU 0, ~2-3 h; metrics afterwards | after the freeze |
| VC-2 (optional, separate) | human evaluation: two-alternative forced choice and continuity ratings on repository inputs only (dog, train), playback-timed clips | **only after a UCSC IRB determination; no participant is recruited and no study is designed further before that** |

## 8. Open decisions

- **D3** V5 / V6 models (proposal in section 5) and the V5 margin rule (REF band, 5th percentile).
- **D5** thresholds of VC-H1 (proposed 1.10 / [0.90, 1.10]) and VC-H2b (proposed REF P99).
- **D6** ordering: VC-1 uses one GPU; the XB gate and calibration use GPU 0 of A and B, so VC-1 could run on C or D at
  the same time if both code states are committed before either starts.
- **D7** whether VC-2 is pursued at all (IRB first).

Closed by the 2026-10-22 review: D1 inputs (dog, train, butterfly, audi), D2 schedules (OT-1, OT-L, OT-R).

Sources for section 5: github.com/facebookresearch/dino (LICENSE), github.com/facebookresearch/dinov2 (README),
github.com/openai/CLIP (LICENSE), github.com/VQAssessment/DOVER (S-Lab-LICENSE), github.com/chaofengc/IQA-PyTorch
(README), github.com/Vchitect/VBench (`vbench/utils.py`, `vbench/subject_consistency.py`).
