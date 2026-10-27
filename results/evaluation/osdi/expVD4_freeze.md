# Experiment VD-4 - freeze record (2026-10-26)

Frozen document: `expVD4/preregistration.md` (FINAL, approved 2026-10-26 with the stage-0 and stage-1-session
revisions). The freeze commit is the commit that adds this file; implementation at 28e14235 (`test_vc.py` ALL PASS,
83 checks; `test_xb.py` 87 / 87). VD-3's frozen artifacts verified unchanged. No mechanism and no frozen result changes.

**Frozen:** the question (oracle sufficiency; not necessity, not practical feasibility); the one-snapshot capture and
the per-component checks; V0 / B0 stage-0 gates on the four stage-0 cells; conditions B0, A1, D, R, DR, S1, S2, S3
(fixed slot order), exploratory A1S1, A1S2, Q8, Q4; VD-3's thresholds and rules; STRICT / NEAR resolution with raw
counts and per-cell session baselines; attribution rules; correspondence analysis; the stage plan and gates (D and R
mandatory; the non-monotonicity subset); the two stage-1 sessions; the inspection fields.

**Approved to run:** stage 0 only (`run_vc.py vd4 --stage 0`). Stage 1 waits for the review of the stage-0 validity
results.

**SHA-256 of the frozen files:**

| file | SHA-256 |
|---|---|
| `results/evaluation/osdi/expVD4/preregistration.md` | `b81a193910c045799372f633ee785e1f0caf217431b6f35e3e9497ab90fe0f21` |
| `results/evaluation/osdi/expVD4/vd4_schedules.json` | `9f14d780fc077737b033ffb4ddab1845502faaf8fd4dda0d3771b0c1c864ea67` |
| `results/evaluation/osdi/expVD3/vd3_thresholds.json` | `792a6ac77ffbca24b4dfd4d2971967b17ddf69ef2a95438f4b1581388d439b57` |
| `results/evaluation/osdi/expVC/vc_schedules.json` | `e1bfffb21ceea085f8abb5c94c681bdf1f68ab3e733805660e579572a74a987b` |
| `tools/eval/aggregate_vd4.py` | `37267dcca368166883dcb017dabb0a3c239cf2d879d634f10de2fa3d23ce43c7` |
| `tools/eval/aggregate_vd3.py` | `415f390828759273f0f43addac0c555fc8b4b91d7717b1c1d0a55b0993f5603e` |
| `tools/eval/vc_emulate.py` | `c97a1c49211624aa2ae3468170cc8078ea3141e039b4a7b73e90740b48f5572a` |
| `tools/eval/vc_metrics.py` | `7392a72580aac806dc043d6c41843e306c3fc5b181fab2e07d4d30e2e828c2b2` |
| `tools/eval/vc_check.py` | `bd5f4494cf2af733d81d10b077c64802318f0563e79adecdf5887709032a51fc` |
| `tools/eval/vd4_export_clips.py` | `5f2e5cadcdb6e41724e2c3f4225aaa7013a2bba813f3ec1fac91784a098153cf` |
| `tools/eval/vc_export_clips.py` | `8d001a360cdf1a35630af0b35e9c3f4d3d632fc9854a668ed9fc370ebe9b0f52` |
| `tools/eval/vc_schedules.py` | `84958ae1ea29fcd24d5fbf98fbb5608ca9d62893135fa02502e344f017a42e4c` |
| `tools/eval/run_vc.py` | `2ecc6bb0d8cbaec6b54627100b7fe08308c9581e887c7d876a9262225e3810bc` |
| `tools/eval/mobility_node.py` | `39c6c24746327b437a4d5c31f0ff49e0a7b4b84306e4aa29e1654c66bc64a8a7` |
