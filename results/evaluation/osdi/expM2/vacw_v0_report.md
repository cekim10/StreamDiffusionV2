# VACW v0 results: Version-aware Continuity Wavefront (GPU, 2026-10-20)

Frozen design and rules: `vacw_v0_design.md` (freeze 9137bc9, Amendment 1); implementation 47243de, loopback record
`../vacw_v0_freeze.md`. Runs: 36 (`results/evaluation/expVA_{dog,butterfly-feeding-slow-motion}_rho{0.5,1}`, commit
94f1da0, 2026-10-20, A -> B -> C -> D, 1 Gbps, M = 30, 3 reps), **36 / 36 valid**, no re-runs. Verdicts by
`tools/eval/aggregate_vacw.py` (`vacw_v0_results.{md,json}`). Hypotheses, thresholds and the decision rule were not
changed after the runs.

## 1. Verdicts

| | result | verdict |
|---|---|---|
| exposure | rho 0.5: 2 fresh transitions in every `split_va` rep (B -> C, C -> D); rho 1: **0** in every rep (B is left before it binds) | rho 1 cells NOT EVALUABLE for H2 / H3, as recorded before the runs |
| **H1a** snapshot integrity | 24 binds in 12 `split_va` runs; every bind is of the snapshot active at bind time and follows an ok whole-digest verification of that version at that node (12 fresh binds of S_1 / S_2 at rho 0.5) | **SUPPORTED** (12 / 12) |
| **H1b** post-bind quality (single crossing >= 35 dB) | dog 6 / 6, butterfly **0 / 6** | **NOT SUPPORTED** (6 / 12; threshold >= 11) |
| **H2** bytes, dog rho 0.5 | source 0.429 vs `restart_fresh` 1.000 Sink (threshold 1.000 - 0.9 x 0.570 = 0.487); aggregate 3.00 vs 3.00 | **SUPPORTED** |
| **H2** bytes, butterfly rho 0.5 | source 0.523 vs 1.000 (threshold 0.572); aggregate 3.00 vs 3.00 | **SUPPORTED** |
| **H3** latency, dog rho 0.5 | bind-ready after the final move 16.14 vs 15.92 s (+0.22; threshold +1.0) | **SUPPORTED** |
| **H3** latency, butterfly rho 0.5 | 16.26 vs 16.49 s (-0.23) | **SUPPORTED** |
| H2 / H3, rho 1 (both workloads) | no fresh transition | NOT EVALUABLE (no fresh transition) |

**Decision (section 7, applied as frozen): NO-GO** - "H1b <= 10 of 12 with H1a passing". Per the rule: keep the frozen
M2, state the stable-version assumption and the rho <= 1 limitation explicitly. v0 is not adopted as the paper's M2
extension on this evidence.

## 2. What the data show beyond the verdicts (descriptive; not used to revise any verdict)

- **The H1b failure is not attributable to fresh snapshots.** Butterfly never crosses 35 dB at the final owner in any
  of its 18 runs, under every policy: frozen `split` (stale S_0) 0 / 6, `restart_fresh` 0 / 6, `split_va` 0 / 6. In the
  rho 1 cells `split_va` executes no fresh path at all (its runs are the frozen `split` path: same binds of S_0, same
  bytes, same PSNR to 0.1 dB) and still fails. Post-bind PSNR plateaus at a median of ~29.5 dB over the last 10 calls
  (maximum 32.2-33.8 dB) over 180-230 calls after the bind. The section 7 wording for this NO-GO branch ("fresh-but-
  changing Sinks do not restore continuity") therefore describes the rule's trigger, not the cause: on butterfly,
  continuity is not restored after three moves whichever Sink is bound. Context (other experiments, not evidence
  here): butterfly crossed 35 dB in W2 (one move, bind ~26 calls after the trigger) and sustained it in Experiment A
  (native, bind ~4 calls after the trigger); here the final bind happens at call 101-151, 70-120 calls after the
  trigger. This is consistent with the Experiment A observation that recovery on refresh-heavy clips depends on how
  long the session ran without its Sink; it was not tested as a hypothesis.
- **Dog (refresh-light): fresh snapshots bind and recover.** rho 0.5: maximum post-bind PSNR 43.6-44.1 dB with fresh
  Sinks vs 41.3 dB with the stale S_0 (`split`); rejoin ~1 s later than `split` because of the manifest wait. 3 reps,
  one workload: no claim beyond that.
- **Bytes.** With fresh snapshots the previous owner holds the whole predecessor snapshot, so at the final move
  realized reuse = available verified reuse = content reuse potential (dog 0.570, butterfly 0.476-0.481): every
  unchanged fragment came from a holder and the capturing owner sent only the changed ones. Aggregate network bytes
  are the same 3.00 Sinks for all policies (every owner receives one full Sink); the saving is in the capturing owner's
  egress, not in the destination's ingress.
- **Latency.** Ingress-bound restoration is 14.0 s for every policy; the fresh path adds the manifest wait (median
  1.47-1.53 s at the final move: D2H + pack 0.93-1.14 s, 412 SHA-256 0.13 s, install 0.17-0.24 s). `split_va` is within
  0.25 s of `restart_fresh` (which pays the same capture) and **1.1-1.5 s slower than the stale `split`** in the rho 0.5
  cells (16.1-16.3 vs 14.8-15.0 s). The design's estimate (~1 s wait + ~0.3 s assembly) is superseded: no assembly
  (Amendment 1), wait ~1.5 s.
- **Dirty fraction per fresh move** (S_k vs S_{k-1}, 412 x 4 MiB): dog 0.417-0.430, butterfly 0.519-0.524, after ~23
  calls of generation at the capturing owner. This is about twice the Task B prediction for 25 calls (dog ~0.21,
  butterfly ~0.34). A likely contributor not in the Task B per-call measurement: every capturing owner first bound its
  predecessor snapshot with a RoPE re-rotation (73-75 slot-rows of sink K on dog, 94-96 on butterfly, ~0.35-0.46 GB),
  so those K blocks differ from S_{k-1} before any refresh. Not attributed block by block (no block checksums in
  these runs).
- **rho 1:** as predicted, the first owner's bind-ready (14.4-14.9 s) exceeds T_m = 14.05 s, so no owner is bound when
  left and every policy binds S_0 at D only; the fresh path needs T_m > T_s.

## 3. Consequences for the paper (per the frozen rule)

- M2 stays as frozen (`split`), with its stable-version assumption stated: the restored Sink is the snapshot taken at
  the trigger; at rho <= 1 an owner that bound and generated is left with a newer Sink than the one restored downstream
  (I5 not provided by the frozen M2).
- Statements the data support without overreach: (i) fresh, hash-verified Sink snapshots can be captured at the
  handoff boundary (~1.3 s for 1.6 GB on L40S) and bound correctly at every subsequent owner (24 / 24 binds), (ii) hash
  reuse cuts the capturing owner's egress to the changed fraction (0.43 / 0.52 Sink) with no aggregate or latency cost
  against a fresh-snapshot restart, (iii) about half the Sink changes per move at these rho, and (iv) continuity on
  the refresh-heavy clip is not restored after three moves by any tested policy.
- Not supported: adopting v0 as the M2 extension; any claim that fresh snapshots improve continuity.

## 4. Limitations

Two workloads, seed 0, one path, one bandwidth, 3 reps; rho 1 cells not exercised; quality measured against the
uninterrupted run with the frozen single-crossing rule; the cause of the butterfly plateau was not isolated.
