# VD-4 addendum 2 - record (2026-10-26)

Document: `addendum2.md` (row-wise RoPE deltas for A1; approved by the user on 2026-10-26). The frozen VD-4
preregistration, schedules and VD-3 thresholds are unchanged (SHA-256 equal to `../expVD4_freeze.md`); the VD-3
freeze record's files are unchanged except the code files that carry the VD-4 additions (as since addendum 1); the
addendum 1 / 1b documents are unchanged. The stage-0 (a319a8cc), 0s (97d460a6) and 0r (8a671bf9) results are not
re-run or edited. Changed code: `mobility_node.py` (`rotate_temp` per (layer, row, slot), `a1_reference`,
`slot_equal_rows`, `within_ulp`, fakes), `vc_emulate.py` (row-wise deltas, the independent-reference checks, per-row
records), `run_vc.py` (stage `0a`, gate requirement), `aggregate_vd4.py` (`a1_rows`, gate `stage0_a1_rows_valid`),
`test_vc.py` (sections 10, 11).

**Approved to run:** stage `0a` only (`run_vc.py vd4 --stage 0a`). Stage 1 waits for the review of the results.

Verification before the run:
- `tools/eval/test_vc.py` (dry environment, no torch): ALL PASS, 107 checks (section 10: 6 new; section 11 skipped
  there).
- `tools/eval/test_vc.py` section 11 (CPU torch environment, the model's `_shift_temporal_rope` source): 8 / 8 -
  batch indexing, row isolation, per-row deltas, V unchanged, zero-delta rows unchanged, the independent reference's
  deltas and expected K (bitwise equal to the rotated K on CPU), a one-element deviation caught.
- `tools/eval/test_xb.py` ALL PASS, 87 checks.
- `aggregate_vd4.py` on the committed stage-0 / 0s / 0r data reproduces their sections of `vd4_results.md` byte for
  byte (only the new corrected-A1 section and gate key are added).

**SHA-256:**

| file | SHA-256 |
|---|---|
| `results/evaluation/osdi/expVD4/addendum2.md` | `750787482d98719093e98f0b082b8c4f230b9792249fd57add1f574c7574aab0` |
| `results/evaluation/osdi/expVD4/addendum1b.md` | `bfc1bb99f33df88f16724d01ef3c5ac759984e57298fd730de11f2c2541c8099` |
| `results/evaluation/osdi/expVD4/addendum1.md` | `a71519440b2714e4ed2bfdebc5d151a498450396d055475c140f8fa10f69c42e` |
| `results/evaluation/osdi/expVD4/preregistration.md` | `b81a193910c045799372f633ee785e1f0caf217431b6f35e3e9497ab90fe0f21` |
| `results/evaluation/osdi/expVD4/vd4_schedules.json` | `9f14d780fc077737b033ffb4ddab1845502faaf8fd4dda0d3771b0c1c864ea67` |
| `results/evaluation/osdi/expVD3/vd3_thresholds.json` | `792a6ac77ffbca24b4dfd4d2971967b17ddf69ef2a95438f4b1581388d439b57` |
| `results/evaluation/osdi/expVC/vc_schedules.json` | `e1bfffb21ceea085f8abb5c94c681bdf1f68ab3e733805660e579572a74a987b` |
| `tools/eval/aggregate_vd4.py` | `b3d894de9b62a1c0d284a7f61ac68e60ead246cf81d6dce120ee799f7767295f` |
| `tools/eval/vc_emulate.py` | `16c1dcef432b07efdd56abac69b374b236aed2aa813c88b6922adbab9976293b` |
| `tools/eval/run_vc.py` | `1f232e9ba586bf640720256c0938731a21757a55a8937ca080a47fe41dbb5f18` |
| `tools/eval/mobility_node.py` | `6006485fd764d619fdf3b2211af5b3b2f2490fe31442c0ed4bb1711baeb2918c` |
| `tools/eval/test_vc.py` | `08998e6df0c826f043d885c110db73b0a19f29d4e9f099671f083156acd2d4fe` |
