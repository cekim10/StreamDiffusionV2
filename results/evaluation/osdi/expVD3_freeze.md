# Experiment VD-3 - freeze record (2026-10-25)

Frozen document: `expVD3/preregistration.md` (FINAL: draft 7 with the final-review revisions of 2026-10-25, approved).
The freeze commit is the commit that adds this file; implementation and thresholds at cd03ff65 (`test_vc.py` ALL
PASS, 67 checks). Phase T (`expVD3_phaseT_approval.md`) is complete. No mechanism (M1 / M2 / M3-v2) and no frozen
result changes.

**Frozen:** the primary research question; the six conditions (TSin, DR2, DR2+TSin, TSinKC, DR2stale, DR2noise) on
the 16 cells (replication: dog, butterfly seed 0; confirmation: train, audi seed 0 and all four inputs seed 1, OT-1 and
OT-L; copied schedules labelled counterfactual, audi seed-0 OT-1 included as a counterfactual stress condition) with
frozen M1 as the control; the paired same-seed same-call REF comparison; the thresholds of `vd3_thresholds.json`
(set A primary for content and color; B and C sensitivity; fixed engineering limits for warp / motion with the
near-zero safeguard; V1 <= REF P99; R3 excess drift; P3 = absolute bind V1, non-inferiority to frozen M1 in the first
20 post-bind calls with the preregistered margins, terminal REF restoration; cost <= 1.5 s, <= 1 MB); the phase-level
classes and the continuity / identity rules of section 4; C1-C4; the blinded inspection (veto only) before the
verdicts; serial reconstruction costs (overlap not validated, no overlap benefit claimed).

**Not modified after Phase C starts:** thresholds, rules, the inspection form. Every confirmation cell is reported,
failures included.

**Run:** host D after the isolation checks:
`run_vc.py vd3 --phase cand --frames_dir <local> --clips_dir <local>` (refuses without this file and the committed
thresholds), then the blinded inspection (`vd3_inspection.md`, committed), `run_vc.py vd3 --phase key`, and
`aggregate_vd3.py` on elves-01.

**SHA-256 of the frozen files:**

| file | SHA-256 |
|---|---|
| `results/evaluation/osdi/expVD3/preregistration.md` | `2131782c7a8ec7da4970781c8e5a398da9e22b3ae38b7092aaf670a8521be2df` |
| `results/evaluation/osdi/expVD3/vd3_thresholds.json` | `792a6ac77ffbca24b4dfd4d2971967b17ddf69ef2a95438f4b1581388d439b57` |
| `results/evaluation/osdi/expVD3/vd3_phaseT.json` | `f725401a1cf87d528807e7e27c4f1d62f9fffa4336149df11adf33dd67f041a1` |
| `results/evaluation/osdi/expVC/vc_schedules.json` | `e1bfffb21ceea085f8abb5c94c681bdf1f68ab3e733805660e579572a74a987b` |
| `tools/eval/aggregate_vd3.py` | `415f390828759273f0f43addac0c555fc8b4b91d7717b1c1d0a55b0993f5603e` |
| `tools/eval/vc_emulate.py` | `544825b3b831bebec498e36d5df6a6d85222b741bf6eed2025f63a50f909b2da` |
| `tools/eval/vc_metrics.py` | `957e82181a81c19a97235f82b9ed72b25144de98d44a18c4e1af85923e77365e` |
| `tools/eval/vc_check.py` | `bd5f4494cf2af733d81d10b077c64802318f0563e79adecdf5887709032a51fc` |
| `tools/eval/vc_export_clips.py` | `8d001a360cdf1a35630af0b35e9c3f4d3d632fc9854a668ed9fc370ebe9b0f52` |
| `tools/eval/vc_schedules.py` | `ff91b5d00c7dd8fe36c81d3448653f89a57a79cc9f9f3b437132750f9af68c59` |
| `tools/eval/run_vc.py` | `4c877b0df4eb66ecfbcdd4ee0b99f869b0b0c4cda17b0fa12caa4b5d27d824a3` |
| `tools/eval/mobility_node.py` | `e1c06f5de543b6a4f0c289f1e0f1b6570e5bb08ee442ad7304e739944bb97d04` |
