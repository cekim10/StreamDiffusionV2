# VD-4 addendum 1b - record (2026-10-26)

Document: `addendum1b.md` (batch-row positions; approved by the user as "Option 1" on 2026-10-26). The frozen VD-4
preregistration, schedules and VD-3 thresholds are unchanged (SHA-256 equal to `../expVD4_freeze.md`); addendum 1's
document is unchanged (SHA-256 equal to `addendum1_record.md`). The stage-0 (a319a8cc) and stage-0s (97d460a6) results
are not re-run or edited. The A1 implementation is unchanged: the four changed code files carry per-row logging, the
per-row checks, stage `0r` and its gates only.

**Approved to run:** stage `0r` only (`run_vc.py vd4 --stage 0r`). Stage 1 waits for the review of the results and
the decision gate of addendum 1b section 5.

Verification before the run:
- `tools/eval/test_vc.py` ALL PASS, 101 checks (section 9: 7 new checks; section 7's driver check now expects the
  refusal of stage 1 until addendum 1b's gates hold).
- `tools/eval/test_xb.py` ALL PASS, 87 checks.
- `aggregate_vd4.py` on the committed stage-0 and stage-0s data reproduces their sections of `vd4_results.md`
  unchanged (diff: only the new batch-row section and the two new gate keys).

**SHA-256:**

| file | SHA-256 |
|---|---|
| `results/evaluation/osdi/expVD4/addendum1b.md` | `bfc1bb99f33df88f16724d01ef3c5ac759984e57298fd730de11f2c2541c8099` |
| `results/evaluation/osdi/expVD4/addendum1.md` | `a71519440b2714e4ed2bfdebc5d151a498450396d055475c140f8fa10f69c42e` |
| `results/evaluation/osdi/expVD4/preregistration.md` | `b81a193910c045799372f633ee785e1f0caf217431b6f35e3e9497ab90fe0f21` |
| `results/evaluation/osdi/expVD4/vd4_schedules.json` | `9f14d780fc077737b033ffb4ddab1845502faaf8fd4dda0d3771b0c1c864ea67` |
| `results/evaluation/osdi/expVD3/vd3_thresholds.json` | `792a6ac77ffbca24b4dfd4d2971967b17ddf69ef2a95438f4b1581388d439b57` |
| `results/evaluation/osdi/expVC/vc_schedules.json` | `e1bfffb21ceea085f8abb5c94c681bdf1f68ab3e733805660e579572a74a987b` |
| `tools/eval/aggregate_vd4.py` | `31088f404e9e0befbeeb1b7f9c3091cdd9da9a25b299e1176a5e1f14a9ad1006` |
| `tools/eval/vc_emulate.py` | `b775e57add5eb086e4e4946d94f34b7cfbe8a276897b1c262d5f47333dc68afc` |
| `tools/eval/run_vc.py` | `40051108c3dd2f018a8c9b52865c403b80d926b00713be8383362f9a5bc0214a` |
| `tools/eval/mobility_node.py` | `d786afe937d6dfb0f701e18301159e4cfd63a0a04ad3d8a9d8234a6560442746` |
| `tools/eval/test_vc.py` | `c6d2df21057838d4ca46f6f19a10630c07b054bba3938fcaeb98f018e1a0f17c` |
