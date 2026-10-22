# Experiment VC - visual continuity of OTTER's resumed output: preregistration REVISED DRAFT 3 (2026-10-22)

Status: **REVISED DRAFT 3. Draft 2 was approved for implementation preparation with final changes (2026-10-22), which
are applied here. Not frozen; nothing implemented or run; no participant recruited.** VC is frozen and launched only
after this draft and the implementation plan (`implementation_plan.md`) are checked. No frozen experiment, result or
mechanism (M1 / M2 / M3-v2) is changed.

Changes from draft 2: models fixed (section 5; MUSIQ-SPAQ excluded; DOVER gated on its license terms); V5 descriptive
(no binary threshold); VC-H1 limited to post-bind motion consistency; VC-H2 compares OTTER with COLD, with REF's
P99 and percentile ranks as descriptive context; the last-frame-hold playback model labelled; train OT-L labelled a
counterfactual replay; VC-2 deferred until VC-1 is reviewed; execution isolation (section 8).

## 1. Question and the three notions kept apart

Does leaving the reference trajectory mean that the user sees a visibly discontinuous video? Two cases must be told
apart:
- **Case A, breakage:** a visible jump, a color or appearance shift, lost content, or motion that no longer follows the
  input.
- **Case B, plausible divergence:** the output is consistent and faithful to the input and the prompt, but not
  pixel-equal to REF.

| notion | object measured | question | metrics |
|---|---|---|---|
| **generation continuity** | the generated frame sequence, indexed by call (no wall-clock time) | do consecutive generated frames, across the move, the Sink-less window and the bind, form a consistent video? | V1-V5 (V6 auxiliary) |
| **playback continuity** | what a viewer would see in wall-clock time under the **last-frame-hold playback model** (section 4.2) | how long does the picture freeze, and how large is the jump when it resumes? | P1-P3 |
| **reference-trajectory recovery** | per-call PSNR / SSIM to REF | does the stream return to the uninterrupted one? | crossing, sustained 10 calls, terminal median (as in RD / WX) |

No result for one notion is read as evidence for another. Low PSNR to REF is never read as a continuity failure. A
good generation-continuity score is never read as good playback continuity: Wait-for-Sink can generate consistent
frames after a long freeze.

## 2. What is already known (seen before this draft; disclosed)

- RD (frozen f850072), last 10 calls of the horizon: input-motion-conditioned warp-error ratio E_O / E_R 0.97-1.02 and
  motion ratio 0.97-1.01 in every condition, including streams ending at 28 dB.
- RD, Sink-less window: E_O / E_R 1.23-1.60 (refresh-heavy inputs) and 1.77-3.12 (dog). A reset gives a
  frame-difference spike of median 5.5x the local median (max 16.6x; REF 1.0x); a bind gives 1.6x.
- State-study figure (dragonD, one run): the No-Sink-KV condition shows a color drift that persists.
- RD's own conclusion: none of these metrics establishes perceptual continuity.

VC-H1 is therefore partly a replication of an RD observation on new schedules, and is labelled so.

## 3. Outputs and conditions

### 3.1 How the frames are obtained

Real runs do not store output frames. The RD emulator reproduced 11 of 11 real runs call by call on one GPU (per-call
|dPSNR| 0.00 dB). VC uses a separate emulator module built on the RD one, which adds frame saving and the COLD
operation; `rd_emulate.py` itself is not changed (implementation plan, section 2). Before any VC-1 run, the new module
must reproduce a frozen real run call by call (implementation plan, VC-0 GPU checks).

Frames are stored losslessly (FFV1) on the executing host's local disk, from 16 calls before the first reset to 100
calls after the final bind. They are never committed, and LOVEU-derived frames are never redistributed.

### 3.2 REF and the exact migration methods

**REF is the uninterrupted single-node stream** (the node baseline: same seed, input and calls). Full migration, P-full
and R-full are **not assumed to equal REF**. Their equivalence is verified on the real GPU by the XB exactness gate
(per-call output digest after the switchover). Until that gate passes and is reviewed, VC neither substitutes them for
REF nor states anything about them.

### 3.3 Conditions per input (dog, train, butterfly-feeding-slow-motion, audi-snow-trail; seed 0)

| id | condition | schedule source | generation | playback |
|---|---|---|---|---|
| REF | uninterrupted | - | baseline | one frame every 1/16 s |
| OT-1 | OTTER, single move, 1 Gbps | realized reset and bind calls of the frozen W2 seed-0 `reuse_dyn` run of the input (audi-snow-trail has two such runs: the earlier valid one). With one move from one source the schedule is one reset and one bind; VC evaluates no M3 behavior | reset at the move (M1 fast path), Sink-less until the bind, then bind | the realized run's delivered-chunk times |
| OT-L | OTTER, single move, slow link | RD-X realized schedule (reset 80, bind 154) of the real runs for butterfly, audi-snow-trail and dog. **Train has no RD-X run: its OT-L is a counterfactual replay under a copied schedule (dog's calls and delivery times), not a realized train run**, and is reported with that label | as OT-1 | the realized RD-X delivered-chunk times (train: copied from dog) |
| OT-R | **M1 + M2 under repeated mobility** (policy `split`, A -> B -> C -> D, rho 2). **Not M3-v2**: VC evaluates no M3 behavior | WX X3 `split` rep 1 (butterfly, audi-snow-trail, train) and M3E S4 `split` rep 1 (dog) | a reset at every move, then the final bind | the realized run's delivered-chunk times |
| WFS-1, WFS-L | Wait-for-Sink at the OT-1 / OT-L move | same move call; the bind time of the same realized run | section 3.4 | last-frame hold from the move until the realized bind time, then resume |
| COLD-1, COLD-L | cold restart at the OT-1 / OT-L move | same move call | a fresh session seeded with [last frame, current chunk], the operation of the frozen `cold` policy (`GpuRuntime.cold_restart` with the node's skip / emit rule); no state carried | last-frame hold for the cold-restart time measured in the frozen W2 `cold` run of the input (read from that run, not assumed) |

### 3.4 Wait-for-Sink semantics (WFS)

- At the move the source stops and the destination receives the M1 fast path. **No frame is generated until the Sink
  is restored**: the source's exact Sink snapshot at the move is bound **before** generation resumes. In the emulator
  this is the RD d = 0 condition (reset and bind before the same call).
- The recent KV and VAE caches are rebuilt by the M1 path, **not** restored, so WFS's output can still differ from REF.
  It is measured, not assumed equal.
- Generation resumes at the call where it stopped. The harness does not generate the input frames a live camera would
  produce during the wait; a live system would skip or delay them. This is stated as a harness property.
- **WFS playback uses the last-frame-hold model.** The last frame before the move stays on screen for the measured time
  from the move to the bind in the same realized run (OT-1's or OT-L's), then playback resumes. WFS is never reported on
  generation continuity alone.

## 4. Metrics

### 4.1 Generation continuity

Windows: boundary +-2 calls of each reset, bind and resume; the Sink-less window; the first 20 calls after the final
bind; the last 10 calls.

| id | measures | definition | role |
|---|---|---|---|
| V1 | boundary discontinuity | frame-difference spike at a reset, bind or resume: mean absolute difference between the last frame before and the first frame after, divided by the median consecutive-frame difference of the same stream over the 16 preceding calls (RD definition) | VC-H2 |
| V2 | temporal consistency | input-motion-conditioned warp-error ratio E_O / E_R (RD definition; Farneback flow of the input at 1/4 resolution) | VC-H1, VC-H3 |
| V3 | motion following | motion magnitude ratio output / REF (RD definition) | VC-H1 |
| V4 | **global color drift** | CIEDE2000 between the window's mean CIELAB color and REF's at the same calls, and between the window and the 16 pre-move calls of the same stream; REF's own drift is reported for scale | **descriptive; no threshold** |
| V5a | content similarity | section 5 | **descriptive** |
| V5b | prompt alignment | section 5 | **descriptive** |
| V6 | clip-level quality, no reference | section 5 (only if enabled) | **auxiliary**: reported next to V1-V5; never used alone and never decides a hypothesis |

### 4.2 Playback continuity: the last-frame-hold playback model

**Model (fixed now, and named in every figure and table that uses it):** the client shows one frame every 1/16 s,
starting after a playout buffer of one chunk (4 frames). Frames are shown in order and never skipped. If the next frame
has not been delivered by its display time, the previous frame stays on screen (a stall) until it arrives. Delivery
times come from the realized runs (section 3.3). This is a model of a simple player, not a measurement of a real
client.

| id | measures |
|---|---|
| P1 | stall count and total stall time, from the move to 100 calls after the final bind |
| P2 | longest single freeze |
| P3 | the V1 jump at every resume after a stall, between the frozen frame and the next frame shown |

### 4.3 Reference-trajectory recovery (context)

PSNR / SSIM to REF per call: first call >= 35 dB, sustained 10 calls, terminal median of calls b + 90 .. b + 99, exactly
as in RD / WX.

## 5. Models (V5, V6)

Licenses were checked on 2026-10-22 against the primary sources listed at the end.

| metric | model | why | license |
|---|---|---|---|
| **V5a content similarity, primary** | **DINO ViT-B/16** (`facebookresearch/dino`, `dino_vitb16`) | self-supervised image features that track object identity and appearance; the same model and comparison as VBench's "subject consistency" dimension | Apache-2.0 (repository LICENSE) |
| **V5a sensitivity** | **DINOv2 ViT-B/14** | checks that conclusions do not depend on the DINO version | Apache-2.0 for code and weights (repository README) |
| **V5b prompt alignment** | **CLIP ViT-L/14** (OpenAI weights) | the standard image-text alignment measure (CLIPScore-style cosine) | MIT (repository LICENSE) |
| **V6 auxiliary** | **DOVER** (`DOVER.pth`) - **gated** | clip-level technical and aesthetic quality | see below |
| excluded | MUSIQ-SPAQ | - | excluded for now (the original weights' license was not verified) |

**DOVER license check (result).** The GitHub repository's `LICENSE` and `S-Lab-LICENSE` files are both the **S-Lab
License 1.0**. It permits redistribution and use for non-commercial purposes; commercial use requires the authors'
permission. The README states no license for the weights. Its download links are the repository's GitHub releases and
the Hugging Face repository `teowu/DOVER`, whose license tag is MIT. The two sources disagree, so VC applies the
stricter reading: **weights and code under S-Lab License 1.0, non-commercial academic use only**. VC's use is
non-commercial research evaluation, which this reading permits. **V6 is enabled only after the user confirms this
reading.** Until then, V6 is not computed and VC's conclusions do not depend on it.

**V5 definitions.**
- V5a(window): mean over the window's frames of the cosine similarity between the DINO feature of the frame and the
  mean feature of the 16 pre-move calls (identity kept from before the move). Separately, the VBench-style score: the
  first-frame and previous-frame similarities, averaged.
- V5b(window): mean over the window's frames of the CLIP ViT-L/14 image-text cosine with the input's prompt.
- The pipeline is video-to-video. The dog workload is a cat video with a dog prompt, so the absolute alignment of every
  stream, REF included, reflects the input as much as the prompt. V5b is read **only relative to REF**.

**V5 reporting (descriptive; no binary success threshold).** For each input, condition and window:
- the paired difference OTTER - REF at the same calls (mean, with a bootstrap 95 % CI over calls);
- REF's own variation band: the 5th-95th percentile of the 10-call-window statistic over REF's evaluated span (16 calls
  before the move to 100 after the final bind), computed from REF alone;
- the effect size (OTTER - REF median) / (REF P95 - REF P5).
- **No perceptual equivalence is claimed from embedding scores alone.** A paired difference inside REF's band is
  reported as "within REF's own variation on this embedding", nothing more.

## 6. Hypotheses (effect sizes always reported; thresholds fixed at the freeze)

| id | notion | statement | success rule | effect sizes reported |
|---|---|---|---|---|
| **VC-H1** | generation | **post-bind motion consistency** (replication of an RD observation on new schedules): after the final bind, OTTER's frames follow the input's motion as consistently as REF's. The claim is limited to motion consistency after the bind: it says nothing about perceptual quality, appearance, the Sink-less window or playback | last-10-call and post-bind-20 E_O / E_R <= 1.10, and motion ratio in [0.90, 1.10], for every input and for OT-1, OT-L and OT-R | the ratios with bootstrap 95 % CI over calls |
| **VC-H2** | generation | OTTER's reset discontinuity is no larger than a cold restart's at the same call | V1(OT reset) <= V1(COLD) for OT-1 and OT-L, every input | **primary:** the ratio V1(OT) / V1(COLD) per input and schedule, with V1 values. **Context, descriptive:** REF's P99 of V1 over its evaluated span, and the percentile ranks of V1(OT) and V1(COLD) within REF's distribution (also for each OT-R reset and each bind). These are **not perceptual thresholds** |
| VC-H3 | generation | the Sink-less window is temporally less consistent than REF | descriptive | window E_O / E_R, V1 inside the window, V4 |
| - | generation | content similarity (V5a), prompt alignment (V5b), global color drift (V4) | **descriptive** (section 5, section 4.1) | paired differences, REF bands, effect sizes |
| VC-H4 | playback | trade-off between OTTER, WFS and COLD at the same move under the last-frame-hold model | descriptive | P1-P3 per condition; for WFS also its generation metrics after the resume |

VC-H1 and VC-H2 verdicts are reported with their effect sizes, and the effect sizes are reported first. V6, if
enabled, is reported next to every result and decides nothing.

**Mapping to paper statements (fixed now).**
- **VC-H1 supported:** the paper may say that after the Sink is bound, the resumed stream follows the input's motion
  as consistently as the uninterrupted stream on the tested inputs and schedules. Nothing about perceptual quality
  follows from VC-H1.
- **Case B wording** (plausible divergence) may be used only together with: the VC-H2 effect sizes and REF context; the
  Sink-less window results (VC-H3); the V4 and V5 effect sizes with REF's bands; the playback trade-off (VC-H4); and the
  statement that embedding and flow metrics do not establish perceptual equivalence.
- If V4 or V5 show differences outside REF's band after the bind, the paper reports them as a visible cost of
  trajectory loss, with the effect sizes. A continuity-first resume mode would be a separate design question; nothing is
  added before the result exists.
- No VC result is read as evidence about latency, bytes or restoration correctness, and VC makes no claim about M3-v2.

## 7. Phases

| phase | content | status |
|---|---|---|
| VC-0 | implementation, dry and CPU tests, two GPU equivalence checks on one host (`implementation_plan.md`) | after this draft and the plan are checked |
| VC-1 | 4 inputs x (REF + 7 conditions) = 32 sequences on GPU 0 of one host (C or D), then metrics | after the freeze |
| VC-2 (optional, separate) | human evaluation on repository inputs only (dog, train), with playback-timed clips | **deferred until the VC-1 results are reviewed. No recruitment before a UCSC IRB determination; no design work before then** |

## 8. Execution isolation (VC alongside XB)

- VC runs on GPU 0 of **C or D** while the XB gate and calibration run on A and B. XB with one move launches nodes on A
  and B only.
- Generated frames go to a directory on the executing host's **local disk** (checked to be a local filesystem, not
  NFS, with enough free space, before the run).
- VC writes its logs and results under its own names (`results/evaluation/expVC*`, `vc_logs/`), separate from every XB
  path.
- Interference checks, recorded per VC unit and per XB run:
  - the VC host's NIC bytes during the unit (VC moves no data between hosts, so this should be about zero);
  - XB's own per-node NIC validity check on A and B, which already exists;
  - VC's frame storage is on the VC host only, and XB writes nothing to it;
  - the GPU-idle check of each job covers only that job's hosts (the current all-hosts check would make XB wait for
    VC; implementation plan, section 6).
- All hosts are on one commit before either job starts. Nothing is pulled or committed on the testbed while either runs.

## 9. Open decisions

- **D5** VC-H1 thresholds (1.10; [0.90, 1.10]) are kept as proposed; confirmed at the freeze.
- **D6** VC host: C or D.
- **D8** V6: enable DOVER under the S-Lab License 1.0 reading (section 5), or leave V6 out.
- **D7** VC-2: decided after VC-1 is reviewed; IRB first.

Closed: D1 inputs, D2 schedules (draft 2 review); D3 models (this revision: DINO ViT-B/16, DINOv2 ViT-B/14, CLIP
ViT-L/14, DOVER gated, MUSIQ-SPAQ excluded).

Sources for section 5: github.com/facebookresearch/dino (LICENSE); github.com/facebookresearch/dinov2 (README);
github.com/openai/CLIP (LICENSE); github.com/VQAssessment/DOVER (LICENSE, S-Lab-LICENSE, README);
huggingface.co/teowu/DOVER (license tag); github.com/Vchitect/VBench (`vbench/utils.py`, `vbench/subject_consistency.py`).
