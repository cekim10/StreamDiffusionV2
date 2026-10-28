# Experiment VD-5 - freeze record (2026-10-27)

Frozen document: `expVD5/preregistration.md` (FINAL; approved for implementation and execution 2026-10-27 on the
basis of `proposal.md`, cebcb516). Implementation at 2b8b95ac (`test_vc.py` ALL PASS including the VD-5 section;
`test_xb.py` ALL PASS). The freeze commit is the commit that adds this file.

**Frozen:** the question (oracle sufficiency of joint recent KV + exact Sink restoration; not necessity, not
practical feasibility); the 2 x 2 with VD-4's B0, R, S3 reused and RS3 new; V0 as positive control and hidden REF
duplicate; the 12 numeric cells and the six visual cells; VD-3's thresholds and rules; the joint-restoration checks;
the reuse gate (dog s1 OT-1, B0 / R / S3 digests equal to the stored runs, else stop); the two-block blinded session
(fields, flags, block A committed before block B, one key); VD-4's STRICT / NEAR rule; the rater calibration gate;
RS3 vs R and vs S3 non-inferiority; the interaction rule and its tolerances.

**Not changed:** every VD-4 document, schedule overlay, form, record, key and result. `vc_emulate.py` and
`vc_schedules.py` gained VD-5-only code (taken only for conditions with the `vd5` flag or from the VD-5 overlay); the
reuse gate checks that VD-4's conditions still produce identical outputs.

**Approved to run:** `run_vc.py vd5` (gate, RS3, V0, checks, metrics, clips, forms, aggregate), then the blinded
inspection (block A, then block B), then `--phase key`. No other condition or experiment.

**SHA-256 of the frozen files:**

| file | SHA-256 |
|---|---|
| `results/evaluation/osdi/expVD5/preregistration.md` | `d343da89f18a72c197fcb1dec1adeada56062d2aa43d03e7fcd8cc0c44a83096` |
| `results/evaluation/osdi/expVD5/vd5_schedules.json` | `bd9cb85c54a5aacf595ab6e251df2b71220d90ba5fcecb68c186e13a051cb3fe` |
| `results/evaluation/osdi/expVD4/vd4_schedules.json` | `9f14d780fc077737b033ffb4ddab1845502faaf8fd4dda0d3771b0c1c864ea67` |
| `results/evaluation/osdi/expVC/vc_schedules.json` | `e1bfffb21ceea085f8abb5c94c681bdf1f68ab3e733805660e579572a74a987b` |
| `results/evaluation/osdi/expVD3/vd3_thresholds.json` | `792a6ac77ffbca24b4dfd4d2971967b17ddf69ef2a95438f4b1581388d439b57` |
| `tools/eval/aggregate_vd5.py` | `0ad401d22fcf000ac2f0fb90718004778fe43f1fc5bb6262ddb51dd49978a786` |
| `tools/eval/aggregate_vd4.py` | `ce13cfea18ad2467e66a2f868199e4fe92f876d6eca20d933a68190444f07960` |
| `tools/eval/aggregate_vd3.py` | `415f390828759273f0f43addac0c555fc8b4b91d7717b1c1d0a55b0993f5603e` |
| `tools/eval/vc_emulate.py` | `3c1d23d4eb0773ddd987fc8197a05f288044f2edabe3c3424603de4dc8edf226` |
| `tools/eval/vc_metrics.py` | `7392a72580aac806dc043d6c41843e306c3fc5b181fab2e07d4d30e2e828c2b2` |
| `tools/eval/vc_check.py` | `bd5f4494cf2af733d81d10b077c64802318f0563e79adecdf5887709032a51fc` |
| `tools/eval/vd5_export_clips.py` | `60ed57f65cc8942deb3eda94b24924efb80e13ecae1c35efde350b51d44e52d8` |
| `tools/eval/vc_export_clips.py` | `8d001a360cdf1a35630af0b35e9c3f4d3d632fc9854a668ed9fc370ebe9b0f52` |
| `tools/eval/vc_schedules.py` | `65308222eb39d8d0e4630f84e552ff6eef2b204704f00e4d168933036748170e` |
| `tools/eval/run_vc.py` | `1e4cd30595d0d2ba27a1e41710e38430e077341285411a2864f5f45688006fa4` |
| `tools/eval/mobility_node.py` | `eca40f9657143493679a4a972df3d07a99e02132d16e26b81e5fdfe494e0a0f3` |
