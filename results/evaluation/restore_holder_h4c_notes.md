# Step 1: ingress-aware correction of provider selection (`reuse_aware_in`), 2026-10-15

45 runs: the 15 Step 2 configurations (N in {1, 2, 4} x holder egress B_h in {62.5, 125, 250, 500, 1000} Mbps, one move,
rho = 2) with the corrected policy only, 3 reps; restart / reuse_fixed / reuse_adaptive / reuse_aware are taken from
Step 2 (`restore_holder/`, same harness, same caps) for the criteria. Pass conditions and the model table were written
before the run (TOPOLOGY_PLAN.md E.5, G step 1). Raw runs `restore_holder_h4c/policy=reuse_aware_in_*`; tables and
verdicts `restore_holder_h4c/{summary.csv, summary_by_config.csv, criteria.md}`; figures `figures/figE8_*`, `figE9_*`
(all five policies; `aggregate_holder.py --experiment restore_holder_h4c --ref restore_holder --aware_policy reuse_aware_in`).

## The correction

`reuse_aware` (Step 2) moved a held fragment from its holder to the source whenever the holder's egress backlog over
its cap exceeded the source's. At N = 1 the binding resource is the owner's ingress, so that rule resent fragments
without shortening anything (H4c failed at (1, 500 Mbps): 1.17 Sinks, same makespan as fixed). `reuse_aware_in` moves a
fragment only when its best holder would finish after **both** the source and the ingress bound (bytes headed to the
owner / the owner's ingress cap). Nothing else changed; `reuse_aware` is kept as a policy so the Step 2 data keep their
meaning.

## Run quality

45/45 valid: all fragments verified; paced egress within cap (source worst 997.7 Mbps over 10 s; edges <= 1.02 x B_h);
kernel NIC receive peaks <= 1075 Mbps; four distinct hosts; no early rate/cancel events. Rep spread <= 0.1 s in
makespan; source bytes identical across reps except (1, 125): 1.36-1.38.

## Result (medians of 3; makespan s / source Sinks per session) against the pre-registered model table

| N | B_h | model | measured | Step 2 `reuse_aware` |
|---|---|---|---|---|
| 1 | 62.5 | 20.9 / 1.45 | 21.1 / 1.44 | 21.1 / 1.44 |
| 1 | 125 | 20.9 / 1.39 | 21.1 / 1.38 | 21.0 / 1.39 |
| 1 | 250 | 20.9 / 1.26 | 21.0 / 1.25 | 21.0 / 1.30 |
| 1 | 500 | 20.9 / 1.01 | 21.1 / **1.00** | 21.1 / 1.17 |
| 1 | 1000 | 20.9 / 1.00 | 21.1 / 1.00 | 21.1 / 1.00 |
| 2 | 62.5 | 33.7 / 1.21 | 34.2 / 1.20 | 34.2 / 1.21 |
| 2 | 125 | 31.3 / 1.11 | 31.6 / 1.10 | 31.7 / 1.12 |
| 2 | 250 | 28.9 / 1.01 | 29.0 / 1.01 | 29.0 / 1.01 |
| 2 | 500-1000 | 28.9 / 1.00 | 29.0 / 1.00 | 29.0 / 1.00 |
| 4 | 62.5 | 57.2 / 1.03 | 57.3 / 1.03 | 57.3 / 1.03 |
| 4 | 125-1000 | 55.4 / 1.00 | 55.5 / 1.00 | 55.5 / 1.00 |

Largest deviation from the model: 0.5 s in makespan, 0.013 Sink in source bytes.

## Verdict (pass conditions as written before the run)

- Every median within 1 s / 0.05 Sink of the model table: **pass** (0.5 s / 0.013).
- (1, 500) sends <= 1.02 Sinks: **pass** (1.00).
- No condition slower than Step 2's `reuse_aware` by > 1 s: **pass** (max +0.1 s).
- P0, H4a, H4b, H4c re-judged with `reuse_aware_in` in place of `reuse_aware`: **all hold** (`criteria.md`); H4c, which
  failed at (1, 500) in Step 2, now holds at every condition.

## Reading

The correction removes exactly the retransmission it was designed to remove: 0.17 Sink at (1, 500) and 0.05 Sink at
(1, 250), with no change in restoration time anywhere (the ingress bound was binding, so the bytes bought nothing).
Where the source is shared (N >= 2) or the holder is slow enough that the ingress is not binding, the two rules make
the same decisions, as the model predicted. The provider-selection rule going forward is therefore: a held fragment
leaves its holder for the source only if the holder's whole-node backlog over its egress cap exceeds both the source's
and the owner's ingress bound. Limitation unchanged from Step 2: no re-plan while a session's flows run, so a holder
that goes idle early is not reused.
