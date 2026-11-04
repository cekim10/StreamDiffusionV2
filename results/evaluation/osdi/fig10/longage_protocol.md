# Fig. 10 long ages: exploratory calibration for E9 D5 (protocol, 2026-11-03; user-approved scope; nothing run)

Not a preregistration: no hypothesis is tested and nothing here changes Fig. 10's frozen verdicts (399f22ff). Purpose
(E9 D5): the simulator extrapolates Versioned delta bytes past the measured 240 calls with the 150-240 slope, capped
at the Sink (`cluster_sim.Cal.delta_bytes`, [A5]); these runs measure ages 1,000 and 3,000.

## 0. Scope change (user, 2026-11-04, before any long-age run)

The cluster simulation (E9) goes into the main evaluation, so these runs are needed to check its delta extrapolation.
To keep them short, **only the Versioned arm runs: 2 workloads x 2 ages x 2 reps = 8 runs** (`LONG_ARMS=ver`), about
3 h with both pairs at once. Consequences, stated before the runs:
- Full's base is the whole Sink by construction (1,728 MB), so the calibration does not need the Full arm.
- The per-rep equivalence of B's outputs between the arms (section 2) is not available. Exactness rests on the second
  cutover's SINKOK and DELTAOK (block digests of the rebuilt Sink equal the source's) and the mismatched-block count.
- No Versioned-vs-Full readiness comparison is made at long ages.
The original 16-run scope stays in the tools (`LONG_ARMS` default) and is not run.

## 1. Runs

The Fig. 10 protocol unchanged except the age and the run length: path A -> B -> A, 1 Gbps, seed 0, first trigger at
call 30, first switch at S1 = 74, second trigger at S1 + age, second switch at S1 + age + 44; Full (`--replay_retain`)
vs Versioned (`+ --replay_reuse`); Fig. 10's OTTER flags.

| item | value |
|---|---|
| ages | 1,000 / 3,000 calls |
| workloads | dog on P1 (elves-01 / 02), butterfly on P2 (elves-03 / 04), at once |
| arms | Full, Versioned |
| reps | 2 (user) -> 16 runs |
| run length | `--post_chunks` = S2 + 100 (1,218 / 3,218), `--max_run_s` = post_chunks + 1,200 |
| record only | node `--mem_log` (process RSS, GPU allocated / reserved, retained and staged bytes at 2 Hz) |
| experiments | `expF10L_<w>_a<age>` |
| tools | `run_fig10.sh long_first / long1 / long2`, `fig10_report.py --long [--sanity]` (dry test `run_fig10.sh dry_long` passed) |

Wall time (corrected): every warm node regenerates the uninterrupted reference of calls 0 .. M + N - 1 before each
run and keeps its frames in host memory (`mobility_node.baseline`), so a run costs about twice its length: about 24 min
at age 1,000 and about 61 min at age 3,000, **about 5.7 h per pair**, the two pairs at once (the earlier 3.5 h estimate
left out the reference). The reference frames of a 3,218-call run raise each node's host memory and write one
reference cache per (host, workload, length) under `results/evaluation/_reference_cache/`; check free host memory and
disk on the four hosts before `long_first`.

## 2. Recorded per run (`fig10_report.py --long`)

- Validity as Fig. 10 (XB rule; both switches at the planned calls; both cutovers SINKOK; no readiness timeout; base
  sent; Versioned: delta verdict recorded), and the per-rep equivalence of B's outputs between the arms.
- **Retained version kept:** from `node_A/memory.csv`, whether A holds a nonzero retained version from its first
  sample after the first cutover to the second trigger, and its size. No eviction exists in the node (no limit on the
  retained version); a reset or loss shows as a zero sample.
- **Delta vs fallback:** the base mode of the second migration (delta or full); a fallback is counted and kept out of
  the delta medians' reading.
- **Exactness:** second cutover SINKOK, DELTAOK (the rebuilt Sink's block digests equal the source's) and the number
  of mismatched blocks.
- Base bytes, total bytes of the second migration, readiness, base-ready time, interruption, refreshed / shifted
  entries, changed-vs-retained blocks; memory peaks (RSS, GPU reserved) on A and B.
- Next to each Versioned cell: the simulator's current extrapolation for that age. At the Fig. 5 refresh intensities
  it is dog 293 / 932 MB and butterfly 758 / 1,609 MB at ages 1,000 / 3,000 (the Sink is 1,728 MB).

## 3. Use in E9

1. Report how the measured delta bytes grow at long ages (and the fallbacks), separately from (2).
2. If the measurements change the simulator's delta model or its calibration ([A5], `calibration.json`), re-run the
   validation gate; the 76 / 76 PASS is not carried over. Then re-run the E9 sweep and report whether the methods'
   order changes. If the model is unchanged, the E9 results stand and the long-age values are cited as a check.

## 4. Reading rules (fixed before the runs)

- A run whose retained version is not held to the second trigger, or whose second base is a fallback, is reported as
  such; its bytes are not read as delta bytes.
- No sentence of the form "Versioned stays below Full at any age" is made from 2 reps; the numbers are calibration.
- Fig. 10's figure is not extended with these points unless the user decides so after the runs.
