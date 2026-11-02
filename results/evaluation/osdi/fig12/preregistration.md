# Fig. 12a preregistration: bandwidth sensitivity of one migration (DRAFT 1, not frozen, nothing run)

Plan: `osdi/eval_plan/plan.md` (Fig. 12, RQ6, P1; constraint "report the region where the benefit shrinks"). User ask
(2026-11-01): find where the Sink transfer becomes the bottleneck. Fig. 12b (time between moves) is not part of this
draft (optional, decided after 12a). Labels: [V] verified in code or earlier records, [H] hypothesis / expectation,
[R] recommendation, [K] seen while drafting (values computed from existing runs before this draft; disclosed so no
threshold can be read as blind).

## 1. Question

How do continuity (max. output gap), readiness (TTFO-local) and bytes of one migration change with link bandwidth, for
Full, Llumnix-style P-full, ServerlessLLM-style R-full and OTTER? Below which bandwidth is OTTER's readiness dominated
by the Sink transfer, and where (if anywhere) does OTTER's continuity advantage over the baselines shrink?

## 2. Facts this protocol rests on

| fact | source | label |
|---|---|---|
| Link bandwidth is an application-level cap per edge (`--bw` Mbps; 0 = unshaped "native"), applied to every flow of every method; the NIC itself is 9.4 Gbps (Phase 0 measured, `--physical_cap_mbps`) | `mobility_orchestrate.py` Run.caps, argparse | [V] |
| Validity checks the NIC receive rate against 1.15 x the cap (10 s means) for shaped runs; native runs are not capped | `xb_validity.nic_ok`, `run_validity_xb` | [V] |
| Fig. 7 at 1 Gbps (A -> B, call 30, 5 reps): gap OTTER 1.63 / 1.59 s, R-full 18.5 / 18.3, Full 54.2 / 54.2, P-full 50.9 / 52.6; TTFO-local OTTER 23.3 / 24.6, R-full 36.9 / 36.8, Full 54.2, P-full 214 / 219 (dog / butterfly) | `osdi/fig7/fig7_results.md` | [V] |
| OTTER's gap at 1 Gbps is the round-1 snapshot source stall, not the cutover | Fig. 7 report | [V] |
| Fig. 7 dog rep 1 OTTER: Sink base on B at 17.5 s, replay caught up 22.4 s, first B output 23.8 s after migration_start: sink_share 0.73 | `fig12_report.otter_breakdown` on the Fig. 7 run | [K] |
| The dry run applies the cap (Full 0.27 GB: 9.4 s at 0.25 Gbps vs 0.49 s native) | `run_fig12.sh dry` | [V] |

## 3. Conditions and runs

- One migration A -> B at call 30, the Fig. 7 protocol and flags unchanged (`run_fig7.sh`: SETV, OTTER flags,
  `--post_chunks 1500 --xb_horizon 100 --horizon_calls 130 --max_run_s 2400`); only `--bw` varies.
- Bandwidths (D1): 0.25, 0.5, 1, 2.5 Gbps and native.
- Methods: Full, P-full, R-full, OTTER. No staging methods: one move has nothing to stage. "OTTER w/o staging" in
  the plan equals OTTER here.
- Workloads: dog (low refresh), butterfly (high refresh), seed 0.
- Reps: 3 (D3).
- Pairs (D2): P1 = elves-01 / 02 runs dog, P2 = elves-03 / 04 runs butterfly, at the same time.
- Runs: 2 workloads x 5 bandwidths x 4 methods x 3 reps = **120**. The 1 Gbps cell is re-measured (D4).
- Order: reps outermost; within a rep, bandwidths 0.25 -> native, methods interleaved per bandwidth.
- First step: OTTER at the two extremes, dog 0.25 Gbps on P1 and butterfly native on P2, at once; `--sanity` checked
  before the rest.
- Wall time [H]: per pair about 72 min per rep (P-full at 0.25 Gbps about 14 min alone), about 3.6 h for 3 reps, the
  two pairs at once.

## 4. Metrics (all measured)

- **Per run:** the Fig. 7 record (`fig7_report.run_record`): validity, C1, TTFO-local, max. output gap, transmitted
  bytes, cutover interruption, C2.
- **OTTER readiness decomposition:** seconds after `migration_start` to
  - `A:replay_base_sent` (Sink base on the destination; `sink`),
  - `B:replay_caught_up` (`caught`),
  - `B:first_output` (`first`).
  - `sink_share = sink / first`.
- **Per cell:** median [IQR] over valid reps. P-full runs that end by the round limit (`switch_reason = round_limit`)
  are counted and marked as non-convergent; they are still scored.

## 5. Hypotheses [H] and predictions

| id | rule | prediction (Fig. 7-based) |
|---|---|---|
| F12-H1 | OTTER median gap <= 2.5 s at every bandwidth, both workloads | about 1.6 s everywhere (the snapshot stall does not depend on the link) |
| F12-H2 | OTTER median sink_share >= 0.5 at 0.25, 0.5 and 1 Gbps, both workloads | 0.25: about 0.78, 0.5: about 0.77, 1: 0.73 [K], 2.5: about 0.6, native: about 0.4-0.6 |
| F12-H3 | OTTER median gap < each baseline's median gap at every bandwidth, both workloads | Full gap about 6.5 GB / bw + 2.5 s (native about 8 s); R-full about 18 s flat; P-full scales with 1 / bw |

Reported but not tested:
- **B\***: the lowest bandwidth whose median sink_share < 0.5 (prediction: native or none).
- **Benefit-shrink region**: bandwidths where OTTER gap / best baseline gap > 0.5 (prediction: none; smallest margin
  at native vs Full, about 0.2).
- **Exploratory TTFO-local crossover with R-full.** Prediction: OTTER's TTFO-local is larger than R-full's at 0.25
  Gbps (about 90 vs 37 s) and at 0.5 Gbps (about 45 vs 37 s), and smaller from 1 Gbps on. The crossover is near
  0.6 Gbps.
  - If this holds, the paper states it: below about 0.6 Gbps, OTTER keeps continuity but reaches local readiness later
    than recomputation.

## 6. Validity

- Each run must pass the Fig. 7 validity: XB rule for P-full, R-full and OTTER; W/R/N rule for Full; C1 as each method
  claims it; NIC <= 1.15 x cap for shaped runs.
- A cell with fewer than 2 valid reps is "not evaluable" and is listed. A hypothesis that needs that cell is then NOT
  SUPPORTED, not skipped.
- Harness defect: fix, rerun, keep both records.

## 7. Procedure

1. Tooling: `run_fig12.sh`, `fig12_report.py`, `plot_fig12.py`. Dry run done: dog at 0.25 Gbps and native, all four
   methods valid.
2. Review D1-D6, then freeze.
3. On the testbed: `d0_remote.py pull`, `run_fig12.sh preflight`, `first`, `fig12_report.py --sanity`, then `rest1` and
   `rest2` in two terminals.
4. Report and figures.

## 8. Analysis

`fig12_report.py` applies section 5 as written. The `--with_fig7` flag (D4 alternative) counts the Fig. 7 runs as the
1 Gbps cell.

## 9. Plot specification (Fig. 6a canvas and axes box, style font sizes, OTTER blue, no mechanism names)

- **fig12a_gap_<w>:** max. output gap vs bandwidth.
  - Log-log axes; the four methods with median and IQR whiskers.
  - "Native" is drawn at 9.4 Gbps and labelled.
- **fig12a_ttfo_<w>:** TTFO-local vs bandwidth, same layout as the gap panel.
- **fig12a_ready_<w>:** OTTER's time to the first destination output, as stacked medians per bandwidth: Sink
  transfer, catch-up, switch.
- The dry figures render within the canvas at 28 / 25 pt with unrotated tick labels. "Native" is close to the right
  edge of the gap and TTFO panels.

## 10. Decisions (open)

| # | decision | recommendation |
|---|---|---|
| D1 | Bandwidths: 0.25 / 0.5 / 1 / 2.5 Gbps / native (plan). Add 5 Gbps? | [R] as planned; native already covers > 2.5 |
| D2 | Two pairs, one workload each (P1 dog, P2 butterfly) vs both workloads on P1 only (about 7 h) | [R] two pairs. Timing metrics are compared within a workload, so within one pair. Fig. 13's pair equivalence shows output equality, not timing equality: the cross-workload comparison carries a pair difference, stated in the caption |
| D3 | Reps: 3 (vs 5 in Fig. 7) | [R] 3. Fig. 7's IQRs are under 2 % of the median for every method |
| D4 | 1 Gbps: re-measure (120 runs) or count Fig. 7's runs (96 runs; `--with_fig7`) | [R] re-measure. The commit differs (record-only changes since), butterfly would move pairs, and Fig. 7 stays as a consistency check |
| D5 | P-full at 0.25 / 0.5 Gbps: run to the round limit (about 14 / 7 min per run) or skip and mark "not run" | [R] run. Non-convergence at low bandwidth is part of the answer |
| D6 | Thresholds: H1 2.5 s, H2 share 0.5, shrink ratio 0.5 | [R] as written. The share threshold was set knowing the Fig. 7 value 0.73 [K] |
