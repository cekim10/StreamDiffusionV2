# M3-v2 and Experiment V (holdout) freeze record

- **Freeze commit:** `e39609a8ee80d3c81a68a50c35b4b109469c7537` (2026-10-19T23:00Z, pushed to `phase0a-quality-elastic`)
- **Frozen:** the M3-v2 algorithm and parameters (`expN/m3v2_design.md` section 7; code `tools/eval/restore_planner.py`
  `dyn_decide_v2` / `update_bottlenecks` / `fluid_eta`, `tools/eval/mobility_orchestrate.py` `Run.dyn_check_v2`, policy
  `reuse_dyn2`, `--dyn_probe` 4) and the Experiment V preregistration (`expN/m3v2_holdout_plan.md`: cells V1-V8, policies
  at moves / M1 + M2 / M3-v1 / M3-v2, 3 reps = 96 runs; V-H1..V-H4 with the frozen N thresholds; censoring, re-runs and
  aggregation per `followup_common.md` section 3; verdicts by `tools/eval/aggregate_wrn.py` section V).
- **Development data (never evidence for v2):** Experiment N cells 1-10, ExpD G5 / G7, loopback runs, GPU regression
  rounds 1 and 2 (`m3dev_cell*`, `m3dev_r2_cell*`). No holdout condition (magnitudes 250 / 125 / 31.25 Mbps, onsets 0.25 /
  0.75, proportional placement) has been run for any policy.
- **Recorded before the holdout:** V-H4 is expected NOT SUPPORTED in holder-degraded cells (development cell 9: v2 bound
  5.4 s after v1 because v1's false-positive re-plan had moved fragments to the source before the degradation); the
  hypothesis is kept as written.
- **Unchanged:** M3-v1 (`reuse_dyn`, `dyn_decide`), M1 / M2, the migration protocol and state formats, Experiment D, W / R / N
  and their reports.

| file | SHA-256 at the freeze |
|---|---|
| tools/eval/restore_planner.py | b10cbf5216bf494a3587f492194a5e62d83f04ed647655c4f07553b84de23fde |
| tools/eval/mobility_orchestrate.py | 144b7913dfb2706665a66ffa36939a4ae9556508ec433fbbbeff52c5bb3e3ae1 |
| tools/eval/run_wrn.py | 76e3dccf5840f66f1615e2362c4a7ba4cd8fb93f80e363cd51e5e4c00b6382fb |
| tools/eval/aggregate_wrn.py | 7d63bf1f61e208e5ac36388c96c197d2f32012ab762bad6baf43261d0a6e70e4 |
| expN/m3v2_design.md | 0823ab062c872824f212ddb08bf8f13e74fa0065e84e57eceff6bd023e2045b0 |
| expN/m3v2_holdout_plan.md | 8a09a7e865aea42eb19e31e9917fc4b74536a9712637d570694723353a32aae0 |

## Amendment 1 (2026-10-20; `expN/m3v2_holdout_plan.md` Amendment 1)

Harness fix (placement-window guard in `plan_aware`; not in the M3-v2 algorithm) and V8's run window (`post_chunks`
800 / `max_run_s` 1200). V1-V3 and V8 are re-run as `expV_a1_cell*`; the first-run directories are kept and flagged
superseded; V4-V7 stand. `tools/eval/mobility_orchestrate.py` after the fix differs from the frozen hash only by the
guard (commit recorded in git).
