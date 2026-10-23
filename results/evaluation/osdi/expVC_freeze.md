# Experiment VC - freeze record (2026-10-23)

Frozen document: `expVC/preregistration.md` (FROZEN 2026-10-23) with `expVC/implementation_plan.md` (sections 1-9).
The freeze commit is the commit that adds this file. VC changes no frozen experiment, result or mechanism.

**Frozen:**
- the three notions (generation continuity, playback continuity, reference-trajectory recovery);
- conditions REF, OT-1, OT-L, OT-R, WFS-1 / -L and COLD-1 / -L on dog, train, butterfly-feeding-slow-motion and
  audi-snow-trail, seed 0, with schedules from `vc_schedules.json`;
- metrics V1-V5 with V6 inactive (DOVER excluded), the rate-matched last-frame-hold playback model (D-VC-1), V1 as
  RD's 8-transition definition (D-VC-2), and the stall rule (D-VC-4);
- hypotheses VC-H1 (post-bind motion consistency; E_O / E_R <= 1.10, motion ratio in [0.90, 1.10]) and VC-H2
  (OTTER vs COLD reset jump; REF P99 and percentile ranks are context only); VC-H3 and VC-H4, V4 and V5 descriptive;
- the block bootstrap (block 5 calls, sensitivity 3 and 10, 10,000 resamples, seed 0);
- the mapping to paper statements.

**Evidence before the freeze (not results):** VC-0 on host A: G1 (|dPSNR| 0.0 over 174 calls), G2 (0.0 over 100), G3
(REF, OT-L, COLD-1, WFS-1), and the DINO / DINOv2 / CLIP self-test. No VC-1 frame has been generated.

**Run:** `run_vc.py vc1 --host <C|D|A> --frames_dir <local>` (one GPU 0, about 2-3 h with VD), then
`aggregate_vc.py` on elves-01. VC-2 (human evaluation) stays deferred: IRB first, decided after VC-1.
