# Experiment VD-3 - GO / NO-GO for a continuity-preserving M1 variant (DR-2 + TS-in): preregistration REVISED DRAFT 3 (2026-10-24)

Status: **REVISED DRAFT 3 for review. Not frozen. No execution until the thresholds and the GO / NO-GO rules are
reviewed and frozen.** Emulator only, one GPU (host D after the isolation checks); M1, M2 and M3-v2 stay frozen; no
frozen result changes. Emulator findings never become end-to-end migration claims (section 9).

**Primary research question.** Can DR-2 + TS-in preserve pre-migration visual identity and temporal consistency
throughout the migration, including the Sink-less interval and the exact Sink binding?

VD-3 is a GO / NO-GO experiment for the mechanism, not an optimization study. GO requires **restoration** of
continuity to the uninterrupted REF's own range in every critical phase on every confirmation cell; a percentage
reduction of drift (improvement) is reported but never counts as preservation.

## 1. Candidate and what VD-2 showed

- **DR-2**: before the destination's first call, decode the source's last 2 latent frames (0.4 MB on the fast path)
  through the empty VAE decoder; VD-2: reset jump 0.39-0.54 x frozen M1.
- **TS-in**: the model's own `prepare` on [last input frame, current chunk] fills 2 of the 3 Sink slots with a
  temporary Sink built from the current input (zero bytes); VD-2: 71-98 % of the Sink-less content gap closed,
  exact bind kept, TS-out no better and worse in color, RP-1 forfeits reference recovery.
- The combination was never run. VD-2's eight cells (dog, butterfly; OT-1, OT-L; seed 0) were seen while choosing
  it, so they are **replication cells**; the GO / NO-GO is decided on cells VD-2 did not use.

## 2. Units, schedules, conditions

| set | units | schedules | schedule source | control (frozen M1) |
|---|---|---|---|---|
| replication | dog, butterfly, seed 0 | OT-1 (1 Gbps, 24-call window), OT-L (320 Mbps, 74-call window) | VC-1 | VC-1 runs (exist) |
| **confirmation** | train, audi-snow-trail, seed 0 | OT-1, OT-L (train OT-L: copied schedule, counterfactual) | VC-1 | VC-1 runs (exist) |
| **confirmation** | dog, butterfly, train, audi, **seed 1** | OT-1 (realized: `expW_W2_<input>_s1` reuse_dyn, move 34, bind 58 / 59); **OT-L** (stress: dog's seed-0 RD-X schedule copied, reset 80, bind 154; counterfactual) | new | **new** REF baseline and frozen-M1 OT-1 / OT-L runs at seed 1; the OT-1 replay is checked call by call against the real W2 seed-1 run |

Confirmation cells: 4 (seed 0) + 8 (seed 1) = **12**. If the GPU budget forces a cut, seed-1 OT-L is dropped first;
the confirmation inputs are never cut.

Conditions per cell (emulator kind `vd3`; frozen M1 is the control):

| id | mechanism | role |
|---|---|---|
| TSin | temporary Sink from the current input; decoder cache empty as in frozen M1 | component alone (negative control for DR-2's contribution) |
| DR2 | decoder cache from the source's last 2 latent frames | component alone |
| **DR2+TSin** | both | **the candidate; the GO / NO-GO is decided on it** |
| TSinKC | TS-in keeping the decoder cache its own prepare produced (zero bytes, no extra compute) | cheapest nonempty cache; decides the implementation if the noise control shows cache content does not matter |
| DR2stale | DR-2 with the source's latent frames from 16 calls before the move (real but wrong history) | negative control: temporal information vs any warmed cache |
| DR2noise | DR-2 with seeded Gaussian latent frames | negative control: noninformative initialization |

16 cells x 6 conditions = 96 emulations, plus 8 seed-1 controls and 4 seed-1 REF baselines: about 6 h on host D.

## 3. The three critical phases and their metrics (VC definitions; all REF-relative)

| phase | window | metrics | REF-relative reference |
|---|---|---|---|
| **P1 migration boundary** | the reset call (first transition into it) | V1: frame difference across the boundary / median of the 8 preceding transitions | REF's P99 of V1 over its evaluated span (natural variation) |
| **P2 Sink-less interval** | whole window (reset .. bind - 1); **early** (first 8 calls); **late** (last 8 calls before the bind: late-window drift) | DINO content similarity to the 16 pre-move calls and to REF at the same calls (DINO ViT-B/16; DINOv2 sensitivity); CLIP prompt alignment; color difference dE (CIEDE2000, window mean Lab vs REF and vs the pre-move calls); warp-error ratio E_O / E_R and motion ratio | REF's P5-P95 band of 10-call-window statistics over the same span (content, color, warp); the band is computed from REF alone |
| **P3 exact Sink binding and recovery** | the bind call (bind discontinuity V1); post-bind 20 calls; last 10 calls | V1 at the bind; DINO difference to REF; dE to REF; E_O / E_R; PSNR trajectory (first call >= 35 dB, terminal median) | REF's P99 (bind V1); REF's band (post-bind content and color); frozen M1's rejoin call (where it rejoins) |
| **cost** | the destination before its first call | serial reconstruction time per mechanism and per combination (measured as a whole); bytes added; TTFO increase bound (serial) and the overlap measurement (section 6) | - |

Two outcome columns are reported for every continuity metric and never merged:
- **improvement**: the fraction of the frozen-M1-to-REF gap closed (or the ratio to frozen M1 for V1);
- **restoration**: whether the cell's statistic lies inside REF's own range (band or P99).

## 4. GO / NO-GO rules (fixed at the freeze; applied to DR2+TSin on every confirmation cell; thresholds under review)

GO requires **all** of R1-R5 on **all 12 confirmation cells** (replication cells reported next to them, not judged),
**and** the visual inspection of section 5 finds no identity, appearance, color or temporal break.

| rule | phase | restoration requirement (GO) | improvement (reported, never sufficient) |
|---|---|---|---|
| R1 | P1 boundary | V1(reset) <= REF's P99 | V1 ratio to frozen M1 (<= 0.5 expected) |
| R2 | P2 whole window | DINO similarity to the pre-move calls inside REF's P5-P95 band; dE to REF <= REF's P95 of its own window color variation; E_O / E_R <= 1.10 | fraction of the DINO gap closed (>= 0.5 expected) |
| R3 | P2 late window | the late-window DINO similarity inside REF's band and not lower than the early window by more than REF's band width (no late-window drift) | - |
| R4 | P3 bind and recovery | V1(bind) <= REF's P99; post-bind-20 and last-10 DINO difference to REF inside REF's band width; post-bind dE inside REF's band; where frozen M1 rejoins (>= 35 dB), the candidate rejoins within 5 calls of it; where it does not (butterfly), terminal PSNR within 1 dB of frozen M1's | - |
| R5 | cost | serial reconstruction time <= 1.5 s and bytes <= 1 MB (DR2+TSin); the 0.3 s preferred target reported | - |

Verdict levels: **GO** (R1-R5 on 12 / 12 and the inspection clean); **NO-GO** otherwise. A NO-GO is reported with the
failing phase per cell (section 7). No partial GO.

Component and control hypotheses (reported with effect sizes; they shape the implementation and the explanation, not
the GO):

| id | statement | rule |
|---|---|---|
| C1 | the combination keeps each component's benefit | V1(DR2+TSin) <= 1.1 x V1(DR2); DINO(DR2+TSin) >= DINO(TSin) - 0.01, every confirmation cell |
| C2 | TS-in alone is not enough for P1 | V1(TSin) > REF's P99 on the majority of cells (otherwise DR-2 is unnecessary) |
| C3 | temporal information, not initialization, explains DR-2 | V1(DR2) < V1(DR2stale) and V1(DR2) < V1(DR2noise) on every confirmation cell. If not: a warmed cache of any content removes the jump; the implementation becomes TSinKC if it satisfies R1-R5 |
| C4 | TSinKC vs DR2+TSin | descriptive: V1, DINO, cost per cell |

## 5. Visual evidence (required before the verdict)

For the repository inputs (dog, train; both seeds; OT-1 and OT-L) the emulator's stored frames are exported as
synchronized clips: REF, frozen M1, TS-in, DR-2 and DR-2+TS-in, side by side and individually, H.264, with the
migration call and the exact-bind call marked by an overlay and a one-frame colored border (`vc_export_clips.py`).
butterfly and audi-snow-trail clips are exported for internal inspection only (LOVEU frames are never redistributed
and never appear in the paper).

Inspection (by the reviewer, recorded in `vd3_inspection.md` before the aggregator's verdict is read): per clip,
object identity kept / changed, appearance kept / changed, color shift visible / not, temporal discontinuity at the
move, inside the window, at the bind. A visible break in any confirmation clip vetoes GO even if R1-R5 pass; no
visual impression upgrades a NO-GO. The paper never claims continuity preservation from DINO / CLIP alone.

## 6. Reconstruction overhead and TTFO (D3)

Serial costs are measured per cell. On one unit (dog seed 0, OT-1, DR2+TSin; 5 repeats) the overlap of the DR-2
decode with the first generation call is measured on a second CUDA stream (`vd3_overlap.py`): (a) the first call's
output digest equals the serial order's; (b) the generation call's wall time under the concurrent decode is within
10 % of its wall time alone; (c) the time to the first output is lower than in the serial order. Overlap counts as a
latency optimization only if (a)-(c) hold; otherwise the serial cost stands. The emulator does not model the network;
the TTFO numbers here are destination-side bounds, not migration TTFO (section 9).

## 7. If VD-3 fails (fixed now)

- The report names, per failing cell, the phase that violates continuity (P1, P2 early / late, P3) and the metric.
- P1 fails (boundary): decoder-side state is insufficient; the next question is additional source-derived decoder
  state (more latent history did not help in DR-4; the stale / noise controls say whether content matters).
- P2 late-window drift fails while early passes: the temporary Sink does not hold identity over a long window; the
  next question is **source-derived temporal state** for the Sink (an approximate or partial Sink), reopened only
  then.
- P3 fails: the temporary Sink interferes with the exact bind; TS-in is dropped and only DR-2 proceeds.
- R5 fails: overlap engineering before any further claim.
- **No continuity-preserving M1 is claimed until a redesign passes a new GO / NO-GO.**

## 8. Validity

G3 on every stream; seed-1 REF baselines and frozen-M1 controls generated by the emulator, with the OT-1 control
checked call by call against the real W2 seed-1 run; with every flag off, the dog RD-X replay stays identical;
TSinKC's kept cache verified equal to its prepare's (digest); DR2stale's latent calls and DR2noise's seed recorded;
the temporary Sink verified to occupy exactly the two slots prepare fills and to be fully overwritten at the bind.

## 9. If VD-3 passes: the end-to-end validation it proposes (separate preregistration)

Implement the variant on the node (M1-R: fast path + 2 latent frames; destination prepare and decode before the first
call, overlapped only if section 6 validates it) and preregister a testbed experiment against frozen M1 + M2 + M3-v2:
actual TTFO-local, delivery gap, measured bytes, destination GPU overhead, bind pause, and the VC continuity metrics
with the same GO / NO-GO structure, on XB1-style single moves and XB4-style repeated mobility, dog and butterfly, 3
reps. Frozen results stay as recorded; the variant is reported beside them.

## 10. Open items before the freeze

- The numerical thresholds in sections 4 and 6 (R1-R5 and the 10 % contention bound), under review.
- Whether seed-1 OT-L is kept in the confirmation set (budget).
- The inspection form (section 5) and who inspects.
