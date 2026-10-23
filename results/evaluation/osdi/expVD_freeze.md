# Experiment VD - freeze record (2026-10-23)

Frozen document: `expVD/preregistration.md` (FROZEN 2026-10-23), including the implementation in its section 8. The
freeze commit is the commit that adds this file. VD is a diagnosis on the emulator: it changes no frozen experiment,
result or mechanism. The model flag `mask_sink_slots` defaults off, and the VC-1 dog unit re-runs G1 with it in the
code.

**Frozen:** the precheck (section 2), the 2 x 2 x 2 factorial plus the encoder condition at OT-1 and OT-L on dog and
butterfly (32 emulations), the outcomes, hypotheses VD-H1..H5 with the thresholds accepted as proposed (VD-D1), and
the mapping to the next step (section 5).

**Run:** inside the VC-1 unit (`run_vc.py vc1`): the precheck first, then VD's conditions after VC's for dog and
butterfly; `aggregate_vd.py` on elves-01. VD-D2 (train, audi-snow-trail) is decided after these results.
