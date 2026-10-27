# VD-4 addendum 2a - record (2026-10-27; approved; stage 0a2 not yet run)

Document: `addendum2a.md` (approved by the user on 2026-10-27; the approval adds to the gate that the stage-0a2 output digests equal the stage-0a first run call by call). Stage 0a (52a1c461) failed its gate on all four cells on one check only
(`a1_k_within_1ulp_of_independent_reference`); the cause is the reference's RoPE angle (theta over the head dim 128
instead of the temporal RoPE dim 44), not the A1 correction. The stage-0a results are preserved
(`results/evaluation/expVD4a`, `osdi/expVC/vd4a_checks_*`) and still reported in `vd4_results.md`; they no longer
decide the gate. The frozen VD-4 documents, VD-3 artifacts, addenda 1 / 1b / 2 documents and the stage-0 / 0s / 0r
results are unchanged.

Changed: `mobility_node.a1_reference` (theta over d_t = d - 4 * (d // 6)), `aggregate_vd4.py` (second root
`expVD4a2`; the first run reported as such; gate from the rerun), `run_vc.py` (stage `0a2`; stage `0a` refuses to
overwrite the first run), `test_vc.py` (section 11 builds the table the model's way with the `rope_params` source and
adds the wrong-angle regression check; section 10 covers the two roots and that a failed first run does not decide the
gate). The A1 implementation (`rotate_temp`, row-wise deltas) is untouched.

Verification (before any run):
- Offline reproduction with the model's real table construction (d = 128, keys of the observed scale, deltas 22, 23,
  -29, 1): theta over the head dim -> max abs differences 11-60, 67 % of elements equal (the spatial channels);
  theta over the temporal dim -> bitwise equality for every delta.
- `test_vc.py` section 11 (CPU torch): 9 / 9 - reference bitwise equal to the rotated K against the model's own
  table; the wrong-angle reference differs by far more than rounding.
- `test_vc.py` (dry environment): ALL PASS, 109 checks (incl.: a rerun whose digests differ from the first run closes the gate). `test_xb.py` ALL PASS, 87 checks.
- `aggregate_vd4.py` on the committed data: every section before the corrected-A1 section byte-identical; the
  stage-0a first run reported with its four FAILs; the rerun section "not run"; gate false.

**Approved to run:** stage `0a2` only (`run_vc.py vd4 --stage 0a2`). Stage 1 waits for the review of its results.

**SHA-256:**

| file | SHA-256 |
|---|---|
| `results/evaluation/osdi/expVD4/addendum2a.md` | `32604676e705928b764963b5d4e321e1bfed5fe452692e388646a7ec010e1c0d` |
| `results/evaluation/osdi/expVD4/addendum2.md` | `750787482d98719093e98f0b082b8c4f230b9792249fd57add1f574c7574aab0` |
| `results/evaluation/osdi/expVD4/addendum1b.md` | `bfc1bb99f33df88f16724d01ef3c5ac759984e57298fd730de11f2c2541c8099` |
| `results/evaluation/osdi/expVD4/addendum1.md` | `a71519440b2714e4ed2bfdebc5d151a498450396d055475c140f8fa10f69c42e` |
| `results/evaluation/osdi/expVD4/preregistration.md` | `b81a193910c045799372f633ee785e1f0caf217431b6f35e3e9497ab90fe0f21` |
| `results/evaluation/osdi/expVD4/vd4_schedules.json` | `9f14d780fc077737b033ffb4ddab1845502faaf8fd4dda0d3771b0c1c864ea67` |
| `results/evaluation/osdi/expVD3/vd3_thresholds.json` | `792a6ac77ffbca24b4dfd4d2971967b17ddf69ef2a95438f4b1581388d439b57` |
| `results/evaluation/osdi/expVC/vc_schedules.json` | `e1bfffb21ceea085f8abb5c94c681bdf1f68ab3e733805660e579572a74a987b` |
| `tools/eval/aggregate_vd4.py` | `a9e97df93410d7183b4e0c8e1c295b8750332ace5007594c3ec56ddabfb93cb1` |
| `tools/eval/vc_emulate.py` | `16c1dcef432b07efdd56abac69b374b236aed2aa813c88b6922adbab9976293b` |
| `tools/eval/run_vc.py` | `03c080d5eccc8cd3a94e3c4c27e54c5cf125c38e43e4a4b83cf956e70f2de697` |
| `tools/eval/mobility_node.py` | `eca40f9657143493679a4a972df3d07a99e02132d16e26b81e5fdfe494e0a0f3` |
| `tools/eval/test_vc.py` | `2516302e8a8ea50c353b43124c697b233b2593d1736357b678b499f62ddcae5f` |
