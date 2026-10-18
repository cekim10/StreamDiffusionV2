# Experiment D results (GPU end-to-end, 2026-10-17)

Frozen preregistration v3 (81bb628) judged by the frozen aggregation procedure (`aggregation_spec.md`, written before any
sweep data; corrected once before launch, G9 metric). Full table: `expD_results.md` / `expD_results.json`
(`tools/eval/aggregate_expD.py`). 147 configured runs + G9 on elves-01..04 GPU 0. Medians over 3 valid reps; ranges are
min-max over the valid reps. Nothing in the planner, thresholds, workload or criteria changed during the sweep.

## Outcomes

| criterion | verdict | medians (range) |
|---|---|---|
| G1 interruption | **SUPPORTED** | OTTER event-driven TTFO 0.675 s at 1 Gbps (0.67-0.68), 0.680 s native (0.68); Full migration 54.25 s at 1 Gbps (54.12-54.50): ratio 0.012 <= 0.1 |
| G2 continuity recovery | **SUPPORTED** | rejoin 3.58 s / 6 calls at 1 Gbps, 3.58 s / 6 calls native (<= 6.0 s, <= 8) |
| G3 progress preservation, rho 2 | **SUPPORTED** | source M1 + M2 1.03 (1.03-1.06) vs M1 only 2.01; discarded 0.049 vs 1.014; bind-ready 15.11 vs 15.52 s |
| G3, rho 4 | **SUPPORTED** | source 1.02 vs 1.52; discarded 0.036 vs 0.515; bind-ready 15.66 vs 15.17 s |
| G4 correct placement | **SUPPORTED** | Full OTTER bind-ready 4.94 s (4.94-4.96) <= 15.42 - 0.5 x 0.716 x 14.05 = 10.39 s |
| G5 incorrect placement | **NOT SUPPORTED** | (a) 15.46 vs 15.53 s: pass; (b) B_source,total 1.23 > 1.02: fail; (c) B_post 0.51 > 0.30: fail; (d) B_fwd 0.50 < 0.64: fail. M1 + M2 + top-1 (reported, not judged): 1.01 / 0.29 / 0.72, every clause met |
| G6 hybrid source contention | **SUPPORTED** | GPU session bind-ready M1 + M2 43.09 s (42.89-43.13), OTTER event-driven 42.82 s (42.65-43.32) vs M1 only 57.07 s (56.77-57.19) |
| G7 re-planning | **SUPPORTED** | F: event-driven 15.80 s (15.74-16.55) vs at moves 51.58 s (46.89-51.73); re-plans 2, 2, 2; duplicates 0. No change: 0 re-plans in every rep of B rho 2, B rho 4, G; bind-ready within 0.21 / 0.04 / 0.29 s of at moves |
| G8 revisit | **SUPPORTED** | bind-ready at the revisited B: M1 + M2 8.72, OTTER at moves 8.67, OTTER event-driven 8.38 s vs M1 only 15.41 s (bound 9.25 s) |
| G9 overhead | **NOT SUPPORTED** | steady state: chunk service time +0.10 % (555.9-556.3 vs 556.3-556.7 ms per rep; identical frames): met. Memory: destination peak `memory_allocated` Full migration 28.66, Cold restart 28.02, M1 only 27.93, OTTER event-driven 27.93 GiB: spread 2.6 % > 1 % at both bandwidths: not met |
| External C/R | **not run** | blocked on the testbed: no CRIU / CUDA plugin / cuda-checkpoint, no privileges (`../d0/cr_readiness/`) |

Scenario A extra reps: none needed (no configuration's TTFO or bind-ready IQR exceeded 10 % of its median).

## Repetitions and validity

Every configuration has 3 valid reps. Invalid or incomplete runs (kept, excluded, re-run): 3, all in scenario A:
`reuse_dyn 1 Gbps rep 1` (NIC receive peak at B 1168.7 Mbps in one 1 s sample > 1.15 x 1 Gbps; re-run),
`cold destination 1 Gbps rep 2` and `native rep 2` (incomplete: harness bug, below; re-run, and the missing rep 3s run).
Commits: 145 run directories on 656dde6 (147 configured runs + 3 invalid/incomplete - 5 re-run later); the 5 scenario-A
re-runs on aac6c8a (the bug fix only; no measurement code changed);
every run's nodes on one commit (validated per run).

## Observations reported next to the criteria (descriptive)

- **G5 mechanism** (`g5_shakedown_observation.md`): in every rep the event-driven rule re-plans 2.28-2.30 s after the
  move with no network change (measured rates on a shared ingress taken as persistent) and moves 89 fragments (0.22
  Sink) from the misplaced holder to the source; latency is unchanged (ingress-bound). M1 + M2 + top-1 forwards the placed 0.72
  Sink and meets every G5 clause, so the cost of incorrect placement here comes from M3's re-planning, not from M2.
- **G9 memory**: Full migration's destination peak is 0.73 GiB above OTTER's (restoring every component at once);
  Cold restart's 0.09 GiB. The criterion compares the policies with each other, as frozen.
- **Scenario F, secondary**: M1 only restores in 15.3 s (15.22-15.44; it never uses the degraded holder C), M1 + M2 in
  71.8-78.5 s (forwarding from C at 62.5 Mbps), OTTER at moves 46.9-51.7 s, OTTER event-driven 15.7-16.6 s at 1.19 Sinks
  of source traffic vs M1 only's 2.01.
- **Scenario B**: bind-ready is ingress-bound for every progress-preserving and non-preserving policy (15.0-15.8 s);
  Full migration 53.4-53.5 s after the final move; Cold restart first output 1.34-1.55 s and never rejoins.
- **Scenario C**: M1 + M2 + top-1 (4.89-4.95 s) and the oracle (4.90-4.93 s) match Full OTTER; in D the oracle places
  at the true destination (4.90 s).
- **Scenario E**: the three network sessions restored after their last move in ~36-40 s (M1 + M2, OTTER) vs ~53-55 s
  (M1 only), reported separately from the GPU session.
- **OTTER cold destination** (external group, not compared with warm-destination numbers): TTFO 70.7-73.0 s at 1 Gbps
  and 71.2-75.7 s native from the trigger, dominated by process start + weight load + CUDA initialization
  (runtime ready 67.8-72.7 s); bind-ready 85.1-87.3 s (1 Gbps), 73.7-78.1 s (native). Warm Full migration: 54.3 s.
- **Generalization** (scenario A, 1 Gbps, OTTER event-driven): TTFO 0.67-0.72 s for bird and boxing, seeds 0-1; rejoin
  7.7-9.6 s for bird (above G2's 6.0 s, which applies to the dog workload only), 3.6-4.8 s for boxing; PSNR after rejoin
  36.4-40.6 dB. Full migration 54.1-54.3 s, bit-exact.

## Execution anomalies and limitations

1. Cold-destination harness bug during the sweep (the closed connection of the previous run's node was reported as a
   loss and aborted the next run before its trigger); fixed in aac6c8a, affected reps re-run. The loopback dry sweep
   ran one rep per configuration and did not exercise consecutive cold-destination runs.
2. One run invalid for a 1 s NIC receive sample above 1.15 x cap at B while the sender was within cap; the cause
   (other traffic into B's NIC or sampling) is not determined.
3. Interpretations fixed before the data (`aggregation_spec.md`): G4/G5 judged on Full OTTER; "within" = absolute
   difference; T_s = 14.05 s; the scenario A IQR rule on TTFO and bind-ready; G9 = chunk service time (corrected from
   the completion interval before launch).
4. External C/R not run; frame-delivery metrics not measured (no consumer, scope condition 1); decode intervals are per
   chunk (one VAE call per chunk; erratum).
5. Scope: one Sink version per restoration, dog workload for repeated mobility (scope conditions 5-6); earlier frozen
   network-level outcomes (prereg section 0) stand unchanged.
