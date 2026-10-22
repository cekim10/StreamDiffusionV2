# Experiment VC - visual continuity of OTTER's resumed output: preregistration DRAFT (2026-10-22)

Status: **DRAFT for review. Not frozen; nothing implemented or run.** Proposed in response to the review concern that
reference-trajectory recovery failed in every refresh-heavy WX run. No frozen experiment, result or mechanism (M1 / M2 /
M3-v2) is changed. Thresholds marked "proposed" are fixed only at the freeze, by the user.

## 1. Question

Does leaving the reference trajectory mean that the video the user sees is visibly discontinuous? Two cases must be told
apart:

- **Case A, breakage:** a visible jump at the migration, a color or appearance shift, objects lost, motion that no longer
  follows the input.
- **Case B, plausible divergence:** the output is temporally consistent and follows the input and the prompt, but it is
  not pixel-equal to the uninterrupted stream (low PSNR to the reference).

PSNR to the reference cannot separate A from B. VC measures the periods separately: the reset (move), the Sink-less
window, the bind, and the steady state after the bind.

## 2. What is already known (seen before this draft; disclosed so that no threshold is tuned to it)

- RD (frozen f850072): in the last 10 calls of the horizon, the input-motion-conditioned warp-error ratio E_O / E_R is
  0.97-1.02 and the motion ratio 0.97-1.01 in every condition, including streams that end at 28 dB. This supports Case B
  for the steady state.
- RD: during the Sink-less window, E_O / E_R is 1.23-1.60 (refresh-heavy inputs) and 1.77-3.12 (dog). A reset produces a
  frame-difference spike of median 5.5x the local median (max 16.6x; reference 1.0x); a bind produces 1.6x. These are
  Case A signals at the boundary and inside the window.
- State-study figure (dragonD, same run): the No-Sink-KV condition shows a color drift that persists; the full-state
  condition shows a transient artifact that recovers. This is one input, qualitative.
- RD's own conclusion: "None of these metrics establishes perceptual continuity."

VC's confirmatory hypotheses use new schedules, new comparison conditions and new metrics. The RD values are cited as
prior observations only.

## 3. How the outputs are obtained

Real migration runs do not store output frames. The RD emulator (`tools/eval/rd_emulate.py`) reproduces real runs call
by call on one GPU: 11 of 11 real runs matched, with per-call |dPSNR| 0.00 dB. VC adds a frame-saving option to the
emulator and regenerates the outputs of realized schedules. Frames are stored losslessly (FFV1) on the testbed from 16
calls before the first reset to 100 calls after the final bind.

**Conditions per input (same seed, same input, same calls):**

| id | condition | how it is produced | what the viewer sees |
|---|---|---|---|
| REF | uninterrupted stream (= Full migration, P-full, R-full outputs, which are exact) | baseline | continuous |
| OT-1 | OTTER, single move at 1 Gbps | reset at the move, bind at the realized bind call | Sink-less window, then bound |
| OT-L | OTTER, single move, slow link (RD-X schedule: reset 80, bind 154) | as realized | long Sink-less window |
| OT-R | OTTER, repeated mobility (WX X3 rho 2, M1 + M2, realized schedule) | resets at every move, final bind | several resets |
| WFS | Wait-for-Sink | reset and bind at the same call (RD d = 0) | playback frozen for the measured wait, then exact Sink with rebuilt recent / VAE state |
| COLD | cold restart | fresh session from the prompt and the current input at the move (`Runner.restart_at`; small emulator addition) | no state at all |

**Inputs (proposed):** dog and train (repository clips, usable in figures and in a human study), butterfly-feeding-slow-
motion and audi-snow-trail (LOVEU: automatic metrics only; no LOVEU frames in figures or rater stimuli).

## 4. Automatic metrics (per window: boundary +-2 calls, Sink-less window, first 20 calls after the bind, last 10 calls)

| id | measures | definition |
|---|---|---|
| V1 | boundary jump | frame-difference spike at the reset and at the bind, relative to the local median (RD definition) and to the reference at the same call |
| V2 | temporal consistency | input-motion-conditioned warp-error ratio E_O / E_R (RD definition, Farneback flow of the input) |
| V3 | motion following | motion magnitude ratio output / reference (RD definition) |
| V4 | color / appearance drift | CIEDE2000 between the window's mean Lab color and the mean of the 16 pre-migration calls, minus the same quantity for the reference |
| V5 | content and prompt consistency | image-embedding similarity to the pre-migration frames (identity) and image-text similarity to the prompt, relative to the reference (embedding model: decision D3) |
| V6 | per-frame quality, no reference | a no-reference video quality model (decision D3) |
| - | trajectory (context only) | PSNR / SSIM to the reference, as in every earlier experiment |

## 5. Human evaluation (decision D4)

Two-alternative forced choice and absolute continuity ratings on clips of about 6 s around the move, for OT-1, OT-R, WFS
and COLD against REF, on repository inputs only. This is a human-subjects study; a UCSC IRB determination is needed
before any participant is recruited. Nothing is designed beyond this paragraph until D4 is decided.

## 6. Hypotheses (proposed; thresholds fixed at the freeze)

| id | statement | proposed success rule |
|---|---|---|
| VC-H1 | after the bind, OTTER's output is as temporally consistent as the reference | last-10-call E_O / E_R <= 1.10 and motion ratio in [0.90, 1.10] for every input and OT schedule |
| VC-H2 | OTTER's reset is no larger a visual jump than a cold restart's | OT reset spike <= COLD spike at the same call, every input |
| VC-H3 | the Sink-less window is temporally less consistent than the reference (expected; reported, not hidden) | descriptive: window E_O / E_R per input and schedule |
| VC-H4 | OTTER does not leave a persistent appearance shift | last-10-call V4 <= a just-noticeable threshold (value and source fixed at the freeze; the often cited 2.3 is a CIE76 value, not CIEDE2000) |
| VC-H5 | OTTER keeps the content and the prompt | last-10-call V5 within a fixed margin of the reference (margin fixed at the freeze) |
| VC-H6 (if D4) | viewers do not judge OTTER less continuous than WFS (which stalls) or COLD | 2AFC preference and ratings with a pre-registered test |

**How results map to paper claims (fixed now):**
- If H1, H2, H4 and H5 hold, the paper may say that under the evaluated conditions OTTER trades exact trajectory
  preservation for low-latency resumption while the resumed video stays temporally consistent after the bind. It must
  also report H3: the Sink-less window is less consistent.
- If H4 or H5 fails, the trajectory loss is reported as a visible quality cost (Case A), not as plausible divergence.
  A continuity-first resume mode (for example Wait-for-Sink) would then be a separate design question; it is not added
  before this result exists.
- No VC result is read as evidence about latency, bytes or restoration correctness.

## 7. Cost

Emulation only, on one GPU: about 4 inputs x 6 conditions = 24 emulations of about 250 calls each, about 1.5-2 h of GPU
0 on one host. Frame storage is about 0.4 GB per condition (FFV1), about 10 GB on the testbed; frames are not committed.
Metrics run on CPU or a GPU after generation.

## 8. Open decisions

- **D1** inputs (proposal: dog, train, butterfly, audi-snow-trail; seed 0).
- **D2** schedules (proposal: OT-1, OT-L, OT-R as realized in frozen runs).
- **D3** embedding and no-reference quality models for V5 / V6, with their licenses and weights checked before use.
- **D4** human study (yes or no; IRB first).
- **D5** final thresholds of H1, H4, H5.
- **D6** ordering. VC runs on one GPU. The XB gate and calibration use GPU 0 of A and B only, so VC could run on C or D
  at the same time, provided both code changes are committed before either starts.
