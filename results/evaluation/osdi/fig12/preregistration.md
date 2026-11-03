# Fig. 12a preregistration: bandwidth sensitivity of one migration (FROZEN 2026-11-02; DRAFT 1 + user D1-D6; nothing run)

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
- **Achieved link throughput:** the destination's highest 10 s mean NIC receive rate per run (`network.csv`), reported
  per cell. For the shaped cells it checks the cap; for **native** (no cap; NIC 9.4 Gbps) it is the only measure of
  what "native" was, so it is always given with the native results (never "native" alone).
- **Per cell:** median [IQR] over valid reps. P-full runs that end by the round limit (`switch_reason = round_limit`)
  are counted and marked as non-convergent; they are still scored.

## 5. Hypotheses [H] and predictions

| id | rule | prediction (Fig. 7-based) |
|---|---|---|
| F12-H1 | OTTER median gap <= 2.5 s at every bandwidth, both workloads | about 1.6 s everywhere (the snapshot stall does not depend on the link) |
| F12-H2 | OTTER median sink_share >= 0.5 at 0.25, 0.5 and 1 Gbps, both workloads. **Previously informed threshold:** 0.5 was set knowing Fig. 7's 1 Gbps value 0.73 [K], so H2 is not an independent prior hypothesis; it is reported as a check against a threshold chosen with that knowledge | 0.25: about 0.78, 0.5: about 0.77, 1: 0.73 [K], 2.5: about 0.6, native: about 0.4-0.6 |
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

## 10. Decisions (user, 2026-11-02)

| # | decision |
|---|---|
| D1 | 0.25 / 0.5 / 1 / 2.5 Gbps / native (no 5 Gbps); native reported with its measured throughput |
| D2 | two pairs, one workload each (P1 dog, P2 butterfly), fixed |
| D3 | 3 reps |
| D4 | 1 Gbps re-measured |
| D5 | P-full at 0.25 / 0.5 Gbps run to the round limit |
| D6 | H1 2.5 s, H2 share 0.5, shrink ratio 0.5 kept; H2's threshold is stated as previously informed (Fig. 7's 0.73 [K]) |

## Outcome (2026-11-03; 120 / 120 runs valid at 355ce187; rules above unchanged; `fig12_results.md`)

- **F12-H1 SUPPORTED:** OTTER median gap 1.59-1.79 s at every bandwidth, both workloads (prediction about 1.6 s).
- **F12-H2 NOT SUPPORTED:** dog's sink_share is 0.75-0.78 at 0.25 / 0.5 / 1 Gbps, but butterfly's is 0.45 at 0.25 Gbps
  (0.72 at 0.5, 0.74 at 1). There the catch-up is 83 s (sink 70.2 s, first output 154.9 s) and OTTER sends 4.67 GB vs
  2.25 GB at 1 Gbps. [H, derived from bytes, not separately measured] At 0.25 Gbps the high-refresh input's Sink
  refreshes made during the long transfer accumulate, and shipping them (about 2.4 GB, about 80 s at 0.25 Gbps)
  becomes the catch-up. B*: dog native, butterfly 0.25 Gbps. (H2's threshold was previously informed.)
- **F12-H3 SUPPORTED:** OTTER's gap < every baseline's at every bandwidth, both workloads. OTTER / best baseline is
  0.085-0.093 when shaped, 0.22 at native (vs Full 7.3 s); benefit-shrink region: none.
- **Native** (always with its throughput): Full peaks at 5.3 Gbps at B, OTTER at 1.4-1.6 Gbps; OTTER's 2.5 Gbps and
  native cells also peak at 1.4-1.6 Gbps, so above about 1.5 Gbps OTTER's transfer is not link-bound. Full reaches local
  service sooner at native (TTFO-local 7.3 vs 11.4 / 11.6 s).
- **Exploratory TTFO-local vs R-full (prediction held):** OTTER / R-full is 2.00 / 1.11 (dog) and 4.03 / 1.29
  (butterfly) at 0.25 / 0.5 Gbps, and 0.63-0.68 at 1 Gbps; log-interpolated crossover about 0.57 Gbps (dog) and
  0.66 Gbps (butterfly). As written: below about 0.6 Gbps OTTER keeps continuity but reaches local readiness later
  than recomputation.
- P-full reached no round limit (0 runs).
