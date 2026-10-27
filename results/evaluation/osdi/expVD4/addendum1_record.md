# VD-4 addendum 1 - record (2026-10-26)

Document: `addendum1.md` (supplemental stage-0 validation, approved by the user as "Option B" on 2026-10-26). The
frozen VD-4 preregistration, schedules and VD-3 thresholds are unchanged (SHA-256 equal to `../expVD4_freeze.md`); the
stage-0 results of a319a8cc are not re-run or edited. The four changed code files carry only logging, supplemental
checks, stage `0s` and its gate (diff: additions plus the lines that route stage `0s` to its own root).

**Approved to run:** stage `0s` only (`run_vc.py vd4 --stage 0s`). Stage 1 waits for the review of the supplemental
results.

Verification before the run:
- `tools/eval/test_vc.py` ALL PASS, 94 checks: sections 1-7 as before (the section-7 driver check now expects the refusal of stage 1
  until the supplemental gate passes) and section 8 (11 new checks; addendum 1).
- `tools/eval/test_xb.py` ALL PASS, 87 checks.
- `aggregate_vd4.py` on the committed stage-0 data reproduces the stage-0 section of `vd4_results.md` unchanged (diff:
  only the new supplemental section and the new gate key).
- One-off CPU check of the GPU-only helpers with the real `_shift_temporal_rope` source (not part of the test suite:
  the test environment has no torch): per-(layer, slot) records, K changed only in the temporal-RoPE half and never at a
  zero delta, one element unchanged at delta 1 (bf16 rounding, the reason the K change is recorded and not required),
  V untouched, per-slot equality and a one-element difference located, decoder layout / entry / attribute mismatches
  caught.

**SHA-256:**

| file | SHA-256 |
|---|---|
| `results/evaluation/osdi/expVD4/addendum1.md` | `a71519440b2714e4ed2bfdebc5d151a498450396d055475c140f8fa10f69c42e` |
| `results/evaluation/osdi/expVD4/preregistration.md` | `b81a193910c045799372f633ee785e1f0caf217431b6f35e3e9497ab90fe0f21` |
| `results/evaluation/osdi/expVD4/vd4_schedules.json` | `9f14d780fc077737b033ffb4ddab1845502faaf8fd4dda0d3771b0c1c864ea67` |
| `results/evaluation/osdi/expVD3/vd3_thresholds.json` | `792a6ac77ffbca24b4dfd4d2971967b17ddf69ef2a95438f4b1581388d439b57` |
| `results/evaluation/osdi/expVC/vc_schedules.json` | `e1bfffb21ceea085f8abb5c94c681bdf1f68ab3e733805660e579572a74a987b` |
| `tools/eval/aggregate_vd4.py` | `1c477a61019f93be90d4fefb7416f461663db30043b42febb98a0b6a45ff0420` |
| `tools/eval/vc_emulate.py` | `571579371e66a2e86c3b0a944847e0f2c4641abc019fb16cddac42f0117c4456` |
| `tools/eval/run_vc.py` | `a837d27549342f48af63fa990d89eeefb318c1b987d753a05f7bd9587dfa8b47` |
| `tools/eval/mobility_node.py` | `31aa3184f12af5a44db16c99641d40f380e99a34b05b57df1f30dac73c4bb5db` |
| `tools/eval/test_vc.py` | `3ece4ed3d8d64ca27e0f2a3871762734a4351952a79286be885f0194e0ede524` |
| `tools/eval/vc_check.py` | `bd5f4494cf2af733d81d10b077c64802318f0563e79adecdf5887709032a51fc` |
| `tools/eval/vc_metrics.py` | `7392a72580aac806dc043d6c41843e306c3fc5b181fab2e07d4d30e2e828c2b2` |
| `tools/eval/aggregate_vd3.py` | `415f390828759273f0f43addac0c555fc8b4b91d7717b1c1d0a55b0993f5603e` |
