# VD-3 implementation and dry-test validity report (2026-10-25; revised the same day for draft 6; for review before the freeze)

Nothing here is evidence about the mechanism: the dry runs use the fake runtime (synthetic frames, pixel embedder)
and check the protocol, the bookkeeping and the gates. Sections 3 and 4 use existing frozen data (frozen-M1 controls,
REF and real source runs), never a VD-3 candidate result.

## 1. Implementation (emulator only; no frozen path changed)

| file | change |
|---|---|
| `vc_schedules.py` | VD-3 conditions (6 per schedule, kind `vd3`) on all inputs; seed-1 units (OT-1 from `expW_W2_<input>_s1`, OT-L copied from dog's RD-X run, counterfactual); `unit_sched()`; `PROVENANCE` (section 4). The VC / VD / VD-2 entries of `vc_schedules.json` are identical to the pre-VD-3 file (checked per input) |
| `vc_emulate.py` | `vd3_reset` (order of section 12 of the preregistration), stale-latent capture (calls m-18, m-17), seeded noise latents, TSinKC decoder-state copy with a digest check, temporary-Sink checks after the bind; VD-2 / VD-3 only on request; seed-1 units |
| `mobility_node.py` | emulator-only helpers (`vae_dec_state_copy / write`, `dec_digest`, `noise_latents`, `temp_slots_left`) and fake doubles |
| `vc_metrics.py`, `vc_check.py` | early / late Sink-less windows; seed-1 unit lookup; G1 condition selectable (`--g1_cond OT-1`) |
| `vd3_tolerances.py` | REF-only tolerances (min of seed-to-seed and band) and the assay-sensitivity check |
| `vc_export_clips.py` | blinded clips (random codes, randomized grid positions and order, identical M / B markers), sealed key with its SHA-256 in the generated form |
| `aggregate_vd3.py` | per phase effect sizes, R1-R5 per cell, GO / NO-GO / INCONCLUSIVE per candidate, C1-C4; refuses without tolerances; withholds verdicts until the inspection is recorded and keyed; refuses a key whose SHA-256 differs from the form |
| `vd3_overlap.py` | serial vs overlapped DR-2 decode (second CUDA stream, event-ordered decode), checks (a)-(c) |
| `run_vc.py vd3` | phases base / cand / key with the gates of section 11 (cand refuses unless the tolerances are committed; key refuses unless the inspection is committed) |
| `d0_remote.py pull` | clears only result copies byte-identical to the incoming commit when a pull is blocked |

## 2. Tests

- `tools/eval/test_vc.py`: **ALL PASS (55 checks)**, including the new section 6 (24 checks): seed-1 schedules and
  labels; frozen VD-2 conditions unchanged; defaults exclude VD-2 / VD-3; 12 VD-3 conditions valid per seed; G3 on 15
  streams of the seed-1 unit; stale calls [16, 17] at m = 34; noise seed recorded; TSinKC digest equal and its copy not
  counted; DR2+TSin costs and no temporary-Sink slot after the bind; early / late windows [80, 87] / [146, 153] at OT-L;
  tolerances equal min(seed-to-seed, bands) and > 0; 4 cells x 6 blinded clips + 4 grids with no condition names in the
  form or file names and the key's SHA-256 in the form; verdicts withheld without an inspection; "no shift" / "no
  visible jump" not vetoes; a "jump" on a confirmation clip of DR2+TSin vetoes its GO; a replaced key refused; overlap
  checks present; `run_vc vd3` refuses before the freeze; the pull resolution clears an identical copy and leaves a
  differing file untouched. The earlier VC / VD / VD-2 checks still pass (the one failure seen before the fix came from
  VD-3 conditions entering the default run; fixed).
- `tools/eval/test_xb.py`: **ALL PASS (75 checks)** (`mobility_node.py` and `d0_remote.py` changed).

## 3. Why the tolerance is not the draft-4 band alone (frozen-M1 controls, VC-1 data)

Frozen M1's Sink-less paired content D_c and color C_c against the draft-4 band tolerance (P95 - P5 of REF's 10-call
window means over the span); VC-1 established a visible Sink-less change in every one of these streams.

| cell | D_c | band (DINO) | content clause | C_c | band (dE) | color clause |
|---|---|---|---|---|---|---|
| dog OT-1 | -0.425 | 0.036 | fails | +1.51 | 0.88 | fails |
| dog OT-L | -0.378 | 0.027 | fails | +1.14 | 0.91 | fails |
| train OT-1 | -0.273 | 0.054 | fails | +0.40 | 1.05 | passes |
| train OT-L | -0.238 | 0.025 | fails | +1.50 | 1.25 | fails |
| butterfly OT-1 | -0.173 | 0.061 | fails | +0.08 | 0.83 | passes |
| butterfly OT-L | -0.150 | 0.039 | fails | +0.19 | 0.80 | passes |
| **audi OT-1** | -0.142 | 0.148 | **passes** | +0.77 | 4.63 | passes |
| **audi OT-L** | -0.166 | 0.221 | **passes** | +0.69 | 8.64 | passes |

On audi-snow-trail (a confirmation input) the band includes the scene's own evolution (DINO band 0.15-0.22, dE band
4.6-8.6) and cannot detect the known failure. The seed-to-seed term removes scene evolution (both REF streams see the
same input); its values exist only after phase T (the seed-1 REF streams are new), which is why the numbers are
reviewed at the gate before any candidate runs. The relative band widths for warp / motion are 0.22-0.84 on these
units, far looser than draft 4's fixed 1.10, so the same min rule is applied to them (D1b).

## 4. Replay of the real source runs (G1 readiness) and a provenance defect

`vc_check.replay_equivalence` on the existing VC-1 seed-0 OT-1 emulations against their source runs: dog, train,
butterfly **identical** (101 calls, max |dPSNR| 0.000 dB); audi-snow-trail **differs** (up to 8.7 dB from the move).
The audi source run (`expW_W2_audi-snow-trail_s0/..._20261019-135751`) generated train seed 1 (an orphaned node of a
failed train seed-1 invocation): `../audi_s0_w2_provenance.md`. The emulation matches the genuine audi seed-0 run
exactly. Consequences for VD-3: the audi seed-0 OT-1 cell keeps its schedule but is labelled a counterfactual copied
schedule; the four seed-1 sources used by G1 are genuine (each shares its generation with `expA_<input>_s1`).

## 5. Not exercised by the dry tests (GPU-only paths, checked in phase T / C by the validity rules)

- the real temporary-Sink slot check after the bind (`torch.equal` per slot), the decoder-state copy / write (attribute
  names `_conv_idx`, `first_decode`), noise latents, the stale-latent capture (one decode per call);
- the CUDA-stream overlap: if PyTorch serializes the two streams, check (c) fails and the serial cost stands (the
  correctness check (a) guards the event ordering);
- G1 at seed 1 (expected to apply: section 4); a G1 failure stops phase T for that input.

## 6. Budget

Phase T: 4 seed-1 units (REF + 2 controls), metrics, tolerances, overlap: about 1.5 h. Phase C: 96 conditions (about
2-3 min each, as VD-2) plus metrics and clips: about 5 h. Inspection: 16 cells x 6 clips of 15-28 s.

## 7. Revision for draft 6 (decisions of 2026-10-25)

- `vd3_tolerances.py` is replaced by **`vd3_phaseT.py`**: per cell (16) it reports distributions only - natural REF
  variation (window statistics with percentiles and P95 - P5 widths, lag-10 window changes, REF V1, REF early-to-late
  change), measurement noise (embedder recomputation on the same REF frames; emulation determinism from G1 and prefix
  digests), cross-seed differences as sensitivity, frozen-M1 paired deviations as context. It chooses no threshold.
  Section 3's band evidence stays as information: it is not used to tighten any threshold.
- `aggregate_vd3.py` reads the frozen thresholds (`vd3_thresholds.json`, written after the Phase T review) and refuses
  without them; per confirmation cell and candidate it classifies FAIL / DISCRIMINATIVE PASS / NON-DISCRIMINATIVE PASS
  (frozen M1's R1-R4 in the same cell) and applies the overall rule (any FAIL or veto -> NO-GO; every confirmation
  input with a discriminative pass -> GO; otherwise INCONCLUSIVE); non-discriminative passes are listed.
- `run_vc.py vd3 --phase base` (Phase T) requires `expVD3_phaseT_approval.md`; `--phase cand` / `key` require the
  freeze, and `cand` the committed thresholds.
- Node identity verification and orphan cleanup (`mobility_node.py`, `mobility_orchestrate.py`), the audi seed-0
  reproduction (`run_wrn.py w2_repro`) and its comparison (`compare_wrn_audi_repro.py`): `../audi_s0_w2_provenance.md`
  section 6. The comparison's verification refuses a non-audi run (checked on `expW_W2_train_s1`: no identity, digests
  equal train seed 1), and the frozen W recomputation reproduces the recorded W-H1 / W-H2 / W-H3 verdicts.
- Tests after the revision: `test_vc.py` ALL PASS (59 checks; new: Phase T outputs, D1c classes and overall rule,
  refusal without thresholds, Phase T refusal without its approval record); `test_xb.py`: see the commit message.
