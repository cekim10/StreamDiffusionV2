# Follow-up experiments W, R, N - common rules (FINAL; frozen together with the W / R / N preregistrations, record `followup_prereg_freeze.md`)

W (`expW/preregistration.md`), R (`expR/preregistration.md`) and N (`expN/preregistration.md`) are
**mechanism-motivated follow-up evaluations** of OTTER: each tests, over a declared range, a claim that Experiment D
supported or failed at a single workload or operating point. They add no mechanism and do not re-test Experiment D.
Nothing here changes Experiment D (frozen v3, 81bb628; results `expD/expD_report.md`), Experiment T (frozen v3.1,
2a781f8d; on hold), the M1 / M2 / M3 implementations, or any earlier frozen outcome. History: drafts W v1-v3, R v1-v2,
N v1-v2 (commits c765876, 773afe0, 4ae375b; files `exp*/preregistration_draft.md`, renamed at the freeze) are superseded
by the frozen texts.

## 1. Scientific-integrity rules

1. **Experiment D is prior evidence, not new data.** Its numbers appear only as recorded predictions and as the reason a
   condition exists. No ExpD run is re-analysed, pooled with, or counted as a W / R / N observation.
2. **Thresholds are not tuned.** Each threshold carries its origin: a bound frozen before ExpD ran, an analytic model
   stated in the text, or a labelled judgment value. No W / R / N GPU result existed when any threshold was set.
3. **Negative findings are preserved.** Every hypothesis ends SUPPORTED / NOT SUPPORTED / NOT EVALUABLE (with the
   reason); ExpD G5 and G9 stay NOT SUPPORTED whatever W / R / N show.
4. **No universal M3 claim** (N reports per cell and per class).
5. **Confirmatory vs descriptive** are separated in each document; descriptive results never become pass / fail after
   the data are seen. Exploratory items listed in the drafts are **not part of the frozen run plan**, except W-AR; any
   other exploratory run needs a separate, dated decision.
6. **Workload choice without outcome inspection** (LOVEU subset fixed 2026-10-18 from input properties only).

## 2. Testbed, workload defaults, definitions

- Hosts elves-01..04, GPU 0 only (NVIDIA L40S; drivers 575.51.03 on elves-01/02 and 575.57.08 on elves-03/04, as audited
  for ExpD); A = elves-01 (source), B, C, D = elves-02..04; per-node egress and ingress shaped to 1 Gbps (max-min fair
  token buckets), TCP_MAXSEG 1400; warm destinations (process, weights, CUDA, 250-call warm-up before the trigger).
- StreamDiffusionV2 1.3B (`configs/wan_causal_dmd_v2v.yaml`), k = 2, 480x832, 4 MiB fragments; **one Sink =
  1,725,236,640 B (412 fragments)**; every quantity in "Sinks" is bytes / 1,725,236,640. Immediate state 2.67 MiB.
- **T_ref = 14.05 s** (Phase 1 measured Sink transfer-ready time at 1 Gbps; the value every ExpD T_m used), fixed.
- Timing: TTFO = trigger (the move's handoff request) -> first chunk completed at the new owner; Sink bind-ready =
  trigger (or final move) -> first chunk completed with the Sink bound; Sink verified = last fragment checksummed at the
  final owner. Bytes: B_pre, B_post, B_source,total = B_pre + B_post, B_fwd, aggregate network bytes, discarded bytes
  (Phase 1 definition (a): delivered to an owner that neither bound nor forwarded them), in Sinks, computed as in
  `tools/eval/aggregate_expD.py`. Re-plans = `d0.n_replans`; duplicates = orchestrator duplicate bytes + node `recv`
  rows with ok = False.

## 3. Validity, re-runs, timeouts and missing data (apply to W, R, N)

- **Run validity** = `tools/eval/expD_validity.py` (all fragments verified, digest match, NIC peaks <= 1.15 x the cap in
  force, paced egress <= 1.05 x the cap in force over 10 s, four distinct hosts on one commit, GPU 0 idle, reference
  available). An owner-side Sink-version event before the final bind makes a run **inapplicable** to M2 / M3 claims
  (ExpD scope conditions 5-6): it is kept, listed with its events per policy, and handled as each document states.
  Reference-side Sink changes (W's RVC) are a diagnostic, never invalidity.
- **Re-runs:** an invalid run is kept and its configuration + rep re-run, at most 2 further attempts. A cause that is
  deterministic for the configuration (a version event, a reproducible harness failure) is not re-run; the configuration
  is reported NOT EVALUABLE with the cause. No run is deleted.
- **Timeouts / censoring:** a run ends at its call window (`post_chunks`) or `max_run_s`. A time whose event did not
  occur by then (bind-ready, Sink verified, rejoin) is **right-censored** at the elapsed time (or call) reached. The run
  stays in the dataset with: timeout status and which limit ended it, last observed restoration progress (verified
  fragments at the final owner / 412), elapsed time, source and network bytes, re-plan count. Completed-run-only
  averages are never a primary result.
- **Aggregation over reps:** the median of the valid reps of a configuration, as the middle order statistic with
  censored values ranked above every observed value; it is *established* if that order statistic is uncensored,
  otherwise it is "> its censoring time". A configuration with fewer valid reps than planned (after re-runs) is NOT
  EVALUABLE.
- **Deciding a criterion under censoring:** a criterion is decided whenever the bounds determine it (e.g. X <= 0.5 Y is
  SUPPORTED if X is established and X <= 0.5 x Y's censoring time while Y is censored; an upper-bound criterion X <= b
  whose X is censored at a time >= b is NOT SUPPORTED: not finishing before a deadline is a failure); otherwise it is NOT
  EVALUABLE with the reason "censoring". "Within X" = absolute difference.

## 4. Order of execution

1. Implementation of section 5; CPU-only tests; loopback (network-level, dry-node) tests.
2. GPU shakedown: one W unit (W1 + W2), one R configuration, one N configuration; execution correctness only, judged by
   the pre-written conditions in `followup_shakedown_conditions.md`; never used to set or change anything frozen.
3. W1 (its dog result is needed for R's rho <= 1 cells), then W2, R, N, then W-AR.
A correctness bug found after the freeze is fixed with a dated amendment appended to the affected document; the frozen
text is never edited, and affected cells are re-run.

## 5. Implementation required (no item changes M1 / M2 / M3)

| exp | item |
|---|---|
| W | per-call Sink fingerprint on the **value** cache of each sink slot per layer, in the node runtime (run and baseline = reference) and in the W1 runner |
| W | W1 uninterrupted runner (330 calls, one GPU; reuses `build_runtime` / `Runner`) |
| W | fixed observation horizon in the orchestrator: the final owner generates through trigger call + 99 whatever the rejoin |
| W | call-class labels (cut / boundary-adjacent / first-pass / repeated-input) from the `tools/eval/expw_loop_audit.py` arithmetic, applied offline |
| W | W-AR center-band variant script (lossless re-encode, outside version control) |
| R | per-run contention-exposure record (background flows from A: start, end, bytes; overlap with the GPU session's final restoration) |
| R | rho <= 1 path (a bound owner forwards as a holder; M1 only drops) and hybrid sessions at rho other than 2, loopback-tested |
| N | progress-aligned cap-event trigger (`expN/preregistration.md` section 3), `in`-direction caps, degradation record |
| all | timeout / censoring fields in the run summary; sweep driver and aggregator for W / R / N |

## 6. Planned runs and time (GPU 0 of four hosts; ~0.556 s per call)

| exp | runs | estimate |
|---|---|---|
| W1 | 40 (20 workloads x 2 seeds) | ~1 h on four GPUs in parallel |
| W2 | 80 (40 units x 2 policies), 40 orchestrator invocations | ~6 h |
| R | 90 (5 rho x 2 contention x 3 policies x 3 reps) | ~4.5 h |
| N | 90 (10 cells x 3 policies x 3 reps), 10 invocations | ~6 h |
| W-AR (exploratory) | 12 (4 videos: W1 + 2 W2 policies) | ~1 h |
| **total** | **312 runs** | **~19 h**, plus the shakedown (~1 h) |

## 7. Reproducibility metadata recorded per run

Commit of every node and of the orchestrator; host names, GPU model, driver, CUDA / torch / torchvision / PyAV versions
(`pyproject.toml` pins: torch 2.6.0, torchvision 0.21.0, av 13.1.0); command line; seed; input-video SHA-256; reference
cache path; caps and cap events; all event, flow, fragment and metric logs. Dataset identity: the LOVEU archive SHA-256
and the SHA-256 of `expW/loveu_population.csv`, `expW/loveu_selection.csv`, `expW/loop_audit.json` (frozen in
`followup_prereg_freeze.md`).

## Amendment 1 (2026-10-19, after the GPU shakedown, before any W / R / N measurement run; the frozen text above is unchanged)

**Section 3, NIC check on a degraded link.** The frozen text applies "NIC peaks <= 1.15 x the cap in force" to the 1 s
kernel NIC samples. On a link degraded to 62.5 Mbps one 4 MiB fragment is 33 Mbps within a 1 s sample, i.e. more than
the tolerance (9.4 Mbps), so a correctly shaped link fails the check whenever two fragments complete inside one sample
(GPU shakedown N cell 9, OTTER event-driven: samples 77 / 60 / 77 / 60 / 60 Mbps after the change while the fragment
records show 62.5 Mbps). **Correction:** for a link under a changed cap, the NIC check uses the mean of the 1 s samples
over 10 s windows (>= 9 samples) after the change, <= 1.15 x the degraded cap (one fragment is then 5 % of the window);
the 1 s-sample check is unchanged against the nominal cap, and the fragment-record paced-egress check (10 s) is
unchanged. Implemented in `tools/eval/wrn_validity.py`. No hypothesis, threshold or matrix entry changes.
