# Experiment VD-3 - GO / NO-GO for a continuity-preserving M1 variant (DR-2 + TS-in): preregistration REVISED DRAFT 5 (2026-10-25)

Status: **REVISED DRAFT 5 (implementation complete, dry tests pass; `dry_test_validity.md`). Not frozen. No execution
until the thresholds and the GO / NO-GO rules are reviewed and frozen.** Changes from draft 4: the tolerance of every
paired comparison is the smaller of two REF-only measures, the seed-to-seed natural variation and the draft-4 band
width (section 3), because the band width alone does not detect the known frozen-M1 failure on audi-snow-trail (VC-1
control data; `dry_test_validity.md` section 3); motion / warp tolerances are REF-derived like the others; an assay
sensitivity check on the frozen-M1 controls with an INCONCLUSIVE outcome (section 4); execution in three gated phases
(section 11); implementation notes (section 12). Changes from draft 3: every comparison is paired with REF at the
same calls and the same pre-move anchor, with numerical tolerances derived from REF's own variation and fixed here
(section 4); R3 measures excess late-window drift against REF's own early-to-late change; PSNR rejoin is a secondary
diagnostic; C3 re-stated (failing to beat the stale / noise controls does not show that any warmed cache suffices);
TSinKC is a distinct candidate; NO-GO rejects the preregistered general claim, not all utility; blinded, randomized
visual inspection by the user with a fixed form (section 5). Emulator only, one GPU (host D after the isolation checks); M1, M2 and M3-v2 stay frozen; no
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
| **confirmation** | train, audi-snow-trail, seed 0 | OT-1, OT-L (train OT-L: copied schedule, counterfactual; **audi OT-1: copied schedule, counterfactual**, because its source run generated train seed 1, `../audi_s0_w2_provenance.md`) | VC-1 | VC-1 runs (exist) |
| **confirmation** | dog, butterfly, train, audi, **seed 1** | OT-1 (realized: `expW_W2_<input>_s1` reuse_dyn, move 34, bind 58 / 59); **OT-L** (stress: dog's seed-0 RD-X schedule copied, reset 80, bind 154; counterfactual) | new | **new** REF baseline and frozen-M1 OT-1 / OT-L runs at seed 1; the OT-1 replay is checked call by call against the real W2 seed-1 run |

Confirmation cells: 4 (seed 0) + 8 (seed 1) = **12**. If the GPU budget forces a cut, seed-1 OT-L is dropped first;
the confirmation inputs are never cut.

Conditions per cell (emulator kind `vd3`; frozen M1 is the control):

| id | mechanism | role |
|---|---|---|
| TSin | temporary Sink from the current input; decoder cache empty as in frozen M1 | component alone (negative control for DR-2's contribution) |
| DR2 | decoder cache from the source's last 2 latent frames | component alone |
| **DR2+TSin** | both | **the candidate; the GO / NO-GO is decided on it** |
| TSinKC | TS-in keeping the decoder cache its own prepare produced (zero bytes, no extra compute) | a distinct candidate (C4) with its own GO / NO-GO line; never an automatic replacement |
| DR2stale | DR-2 with the source's latent frames of calls m-18 and m-17 (DR-2's pair m-2, m-1 shifted 16 calls earlier: real but wrong history) | negative control: temporal information vs any warmed cache |
| DR2noise | DR-2 with seeded standard-normal latent frames of the same shape and dtype | negative control: noninformative initialization |

16 cells x 6 conditions = 96 emulations, plus 8 seed-1 controls and 4 seed-1 REF baselines: about 6 h on host D.

## 3. The three critical phases and their metrics (VC definitions; all REF-relative)

| phase | window | metrics | REF-relative reference |
|---|---|---|---|
| **P1 migration boundary** | the reset call (first transition into it) | V1: frame difference across the boundary / median of the 8 preceding transitions | REF's P99 of V1 over its evaluated span (natural variation) |
| **P2 Sink-less interval** | whole window (reset .. bind - 1); **early** (first 8 calls); **late** (last 8 calls before the bind: late-window drift) | DINO content similarity to the 16 pre-move calls and to REF at the same calls (DINO ViT-B/16; DINOv2 sensitivity); CLIP prompt alignment; color difference dE (CIEDE2000, window mean Lab vs REF and vs the pre-move calls); warp-error ratio E_O / E_R and motion ratio | REF's P5-P95 band of 10-call-window statistics over the same span (content, color, warp); the band is computed from REF alone |
| **P3 exact Sink binding and recovery** | the bind call (bind discontinuity V1); post-bind 20 calls; last 10 calls | V1 at the bind; DINO difference to REF; dE to REF; E_O / E_R; PSNR trajectory (first call >= 35 dB, terminal median) | REF's P99 (bind V1); REF's band (post-bind content and color); frozen M1's rejoin call (where it rejoins) |
| **cost** | the destination before its first call | serial reconstruction time per mechanism and per combination (measured as a whole); bytes added; TTFO increase bound (serial) and the overlap measurement (section 6) | - |

**Pairing (D1).** Every statistic of a candidate cell is compared with REF's statistic over **the same calls**, with
**the same pre-move anchor** (the 16 calls before the reset; REF's anchor is REF's own frames at those calls). A
scene that evolves naturally lowers the candidate's and REF's similarity to the anchor alike; only the **paired
difference** (candidate minus REF at the same calls) is a migration-induced effect. V1 uses exactly one normalization
for both streams: the first transition into the call divided by the median of that stream's own 8 preceding
transitions; the paired REF transition at the same call is reported next to every candidate V1.

**Tolerances (definition fixed now, from REF streams alone; never from candidate results; `vd3_tolerances.py`).** Per
input and schedule, over sliding 10-call windows after the anchor:
- **seed-to-seed natural variation** w_seed(m): two uninterrupted generations of the same input (REF seed 0, REF seed
  1) see the same scene evolution, so the difference of their drift statistics over the same window measures natural
  variability, not scene change: P95 of |stat_s1 - stat_s0| for content (DINO similarity to the own anchor) and color
  (dE to the own anchor); P95 of the window dE between the two REF streams (candidate-vs-REF color); P95 of
  |ratio - 1| for warp error (mean e_s1 / mean e_s0) and motion (d_s1 / d_s0);
- **band width** (the draft-4 definition): P95 - P5 of each REF's 10-call-window means over the span (relative to the
  median for warp / motion; for the candidate-vs-REF color, the P95 of REF's own window-to-anchor dE);
- **tolerance** w_m = min(w_seed, band of seed 0, band of seed 1).
The band alone includes scene evolution and is too loose where the scene changes: on audi-snow-trail it lets the
frozen-M1 control pass the content and color clauses (D_c -0.14 vs band -0.15 / -0.22) although VC-1 established a
visible Sink-less change there. The paired comparisons are:
- content: D_c = DINO_cand(window, own anchor) - DINO_REF(window, REF anchor) >= -w_DINO;
- color: C_c = dE_cand(window vs own anchor) - dE_REF(window vs REF anchor) <= +w_dE; and the window dE between the
  candidate and REF at the same calls <= w_dEx;
- warp / motion: E_O / E_R <= 1 + w_E and the motion ratio in [1 - w_motion, 1 + w_motion] (replaces draft 4's fixed
  1.10 / [0.90, 1.10]);
- V1: candidate V1 <= REF's P99 of V1 over its span, per unit (paired REF V1 at the same call reported).
The numerical values are computed in phase T (section 11) before any candidate condition exists, reported with the
assay-sensitivity check, and committed before the candidates run.

Two outcome columns are reported for every continuity metric and never merged:
- **improvement**: the fraction of the frozen-M1-to-REF paired gap closed (or the ratio to frozen M1 for V1);
- **restoration**: whether the paired comparison is within its tolerance (above).

## 4. GO / NO-GO rules (fixed at the freeze; applied to DR2+TSin on every confirmation cell; thresholds under review)

GO requires **all** of R1-R5 on **all 12 confirmation cells** (replication cells reported next to them, not judged),
**and** the visual inspection of section 5 finds no identity, appearance, color or temporal break.

| rule | phase | restoration requirement (GO) | improvement (reported, never sufficient) |
|---|---|---|---|
| R1 | P1 boundary | V1(reset) <= REF's P99 (same normalization; paired REF V1 at that call reported) | V1 ratio to frozen M1 (<= 0.5 expected) |
| R2 | P2 whole window | paired content D_c >= -w_DINO; paired color C_c <= +w_dE and candidate-vs-REF window dE <= w_dEx; E_O / E_R <= 1 + w_E and motion ratio within 1 +/- w_motion | fraction of the paired DINO gap closed (>= 0.5 expected) |
| R3 | P2 late window | **excess late drift** X = [DINO_early - DINO_late]_cand - [DINO_early - DINO_late]_REF <= +w_DINO (early = first 8 window calls, late = last 8 before the bind; both paired), and the late window's paired D_c >= -w_DINO | - |
| R4 | P3 bind and recovery | V1(bind) <= REF's P99; post-bind-20 and last-10: paired D_c >= -w_DINO, paired C_c <= +w_dE, E_O / E_R <= 1 + w_E, motion ratio within 1 +/- w_motion. **Secondary diagnostic, not a GO criterion:** PSNR trajectory (first call >= 35 dB vs frozen M1's; terminal median) | - |
| R5 | cost | serial reconstruction time <= 1.5 s and bytes <= 1 MB (DR2+TSin); the 0.3 s preferred target reported | - |

**Assay sensitivity (checked in phase T, on controls only).** Every frozen-M1 control must fail the R2 content clause
under the tolerances (VC-1 established a visible Sink-less change in every frozen-M1 stream). A confirmation cell
where it passes cannot detect the failure the experiment is about.

Verdict levels: **GO** (R1-R5 on 12 / 12 and the inspection clean); **NO-GO** otherwise; **INCONCLUSIVE** when a
confirmation cell is not discriminative (proposed; the alternative is to judge on the discriminative cells only). A NO-GO is reported with the
failing phase per cell (section 7). No partial GO. **A NO-GO rejects the preregistered general claim** ("DR-2 + TS-in
preserves continuity across the confirmation workloads and schedules"); it does not rule out utility on a subset of
conditions, which may be reported descriptively but never as a continuity-preservation claim.

Component and control hypotheses (reported with effect sizes; they shape the implementation and the explanation, not
the GO):

| id | statement | rule |
|---|---|---|
| C1 | the combination keeps each component's benefit | V1(DR2+TSin) <= 1.1 x V1(DR2); DINO(DR2+TSin) >= DINO(TSin) - 0.01, every confirmation cell |
| C2 | TS-in alone is not enough for P1 | V1(TSin) > REF's P99 on the majority of cells (otherwise DR-2 is unnecessary) |
| C3 | the correct latent history contributes beyond cache initialization | V1(DR2) < V1(DR2stale) and V1(DR2) < V1(DR2noise) on every confirmation cell. Supported: DR-2's effect is attributed in part to temporal information. Not supported: the attribution is **not established**; it does not show that an arbitrary warmed cache suffices, and no mechanism is selected on that basis |
| C4 | TSinKC as a **distinct candidate** | R1-R5 are applied to TSinKC on every confirmation cell exactly as to DR2+TSin, with its own GO / NO-GO line in the report. Neither candidate replaces the other automatically; if both pass, both are reported and the testbed proposal (section 9) names the cheaper one as the first to validate, the other as the alternative |

## 5. Visual evidence (required before the verdict)

For the repository inputs (dog, train; both seeds; OT-1 and OT-L) the emulator's stored frames are exported as
synchronized clips: REF, frozen M1, TS-in, DR-2 and DR-2+TS-in, side by side and individually, H.264, with the
migration call and the exact-bind call marked by an overlay and a one-frame colored border (`vc_export_clips.py`).
butterfly and audi-snow-trail clips are exported for internal inspection only (LOVEU frames are never redistributed
and never appear in the paper).

**Blinded inspection by the user (D3).** `vc_export_clips.py` names every clip with a random code, writes the
code-to-condition key to a sealed file (`vd3_blind_key.json`, not opened before the inspection is recorded), and
produces a randomized presentation order. REF is included among the blinded clips. The fixed form
(`vd3_inspection_form.md`, generated with the codes) asks, per clip: object identity (kept / changed / unsure),
appearance (kept / changed), color (no shift / shift), boundary (no visible jump / jump), Sink-less interval (stable /
drifts / breaks), exact bind (no visible jump / jump), free notes. The user records the form in `vd3_inspection.md`
**before** the aggregator's verdicts are read; the key is then opened and the answers are attached to conditions.
A visible discontinuity in any confirmation clip of the candidate **vetoes GO**; inspection never overrides a failed
quantitative rule, and no visual impression upgrades a NO-GO. The paper never claims continuity preservation from
DINO / CLIP alone.

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
- **No continuity-preserving M1 is claimed until a redesign passes a new GO / NO-GO.** A NO-GO rejects the general
  claim as preregistered; descriptive utility on a subset is reported as such.

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

## 10. Decisions and open items (see also section 13)

- **D1 (closed):** R1 REF P99 with one normalization and the paired REF V1 reported; R2 / R3 / R4 paired at the same
  calls and anchor with the tolerances of section 3 (w_m from REF alone); PSNR rejoin secondary; R5 1.5 s / 1 MB; 10 %
  contention bound for overlap.
- **D2 (closed):** all 12 confirmation cells, seed-1 OT-L included and labelled a counterfactual stress condition
  (copied schedule), never an observed migration trace.
- **D3 (closed):** the user inspects, blinded and randomized, with the fixed form, before the verdicts are revealed.
- **Open:** the freeze itself, after this draft, the implementation and the dry-test validity report are reviewed.

## 11. Execution order (phases and gates; `run_vc.py vd3`)

1. **Phase T (`--phase base`)**: preflight and the isolation checks on host D; the seed-0 REF frames of the four VC-1
   units verified present; per input, the seed-1 unit (REF baseline + frozen-M1 OT-1 / OT-L controls), G1 (OT-1 vs
   the real W2 seed-1 run, call by call, |dPSNR| <= 0.001 dB) and G3, metrics; then `vd3_tolerances.py` (numerical
   tolerances and the assay-sensitivity check) and `vd3_overlap.py` (section 6). **Stop.**
2. **Review gate**: the tolerances and the sensitivity table are reviewed and committed (`vd3_tolerances.json`). No
   candidate condition exists yet.
3. **Phase C (`--phase cand`)**: refuses to run unless the tolerances are committed; the six conditions on the eight
   units, G3, merged metrics; then the blinded clips and the form (`vc_export_clips.py`).
4. **Inspection gate**: the user fills `vd3_inspection.md` (STATUS: RECORDED) and commits it; `--phase key` refuses
   to copy the sealed key before that; `aggregate_vd3.py` writes only the validity section until the inspection is
   recorded and keyed (the key's SHA-256 must equal the one printed in the form).
5. **Aggregation**: `aggregate_vd3.py` (R1-R5 per cell, GO / NO-GO / INCONCLUSIVE per candidate, C1-C4).

## 12. Implementation notes (emulator only; no frozen path changed)

- `vc_emulate.py` kind `vd3`: order at the reset = [TS-in prepare -> save its 2 filled Sink slots (and, TSinKC, its
  decoder state)] -> frozen fast path (meta + in-flight; KV and VAE caches zero) -> [write the 2 slots' K / V, never
  positions] -> [TSinKC: write the saved decoder state] -> [DR-2 decode of the latent source]. TSinKC's copy is an
  emulation artifact (a node would not zero the cache): recorded, not counted in its cost. Validity per stream: 2 slots
  written, none left after the bind, TSinKC digest equal, 2 stale latents captured.
- VD-2 / VD-3 conditions run only on request; the frozen VC / VD / VD-2 paths are unchanged (test_vc section 6).
- `vc_metrics.py`: early / late Sink-less windows (first / last 8 calls) added; seed-1 units read from the schedule's
  `units`.
- `d0_remote.py pull`: a pull blocked by local copies of result files clears only the copies byte-identical to the
  incoming commit and retries; differing files are left untouched and reported.

## 13. Open items for the freeze

- **D1b**: the tolerance definition of section 3 (min of seed-to-seed and band), including warp / motion (replacing
  the fixed 1.10 / [0.90, 1.10]); the values are reviewed after phase T, before any candidate runs.
- **D1c**: a non-discriminative confirmation cell makes the verdict INCONCLUSIVE (proposed) or is excluded from the
  judgment.
- **D2b**: the audi seed-0 OT-1 cell stays in the confirmation set with its schedule labelled a counterfactual copied
  schedule (proposed), or is replaced by the genuine audi seed-0 run's schedule (move 34, bind 58; that run is invalid
  under the W / R / N NIC rule).
- **Freeze**: after this draft and `dry_test_validity.md` are reviewed.

