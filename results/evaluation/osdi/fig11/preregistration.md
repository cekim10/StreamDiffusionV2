# Fig. 11 preregistration: repeated mobility (M3, RQ5)

**Status: DRAFT 1 (2026-10-31), not frozen. Nothing run.** Tools and a local dry run are done (section 8) so the set can
start right after Fig. 10. Plan: `osdi/eval_plan/plan.md` (Fig. 11, RQ5, P0). Open decisions: section 10. Labels: [V]
verified in code or earlier records, [H] hypothesis / expectation, [R] recommendation.

Roles: Fig. 7 = one migration vs external baselines; Fig. 9 = M1; Fig. 10 = M2; **Fig. 11 = the whole system when the
user keeps moving: OTTER vs the external baselines, and the effect of lineage staging (M3) itself, under the same
conditions** (plan: "separate the gain over external baselines from the effect of staging itself").

## 1. Questions and messages

RQ5: can lineage-based staging accelerate repeated GPU mobility?

- **11a, time without local service.** Over a run in which the user moves A -> B -> C -> D, how long is the user not
  served by the GPU at their current edge, and how much of that time is served remotely vs interrupted? Message to test:
  OTTER keeps this far below the external baselines, and M3 staging shortens it further than OTTER without staging.
- **11b, final readiness.** After the last move, how long until the final edge serves locally (TTFO-local at D)?

Out of scope: one migration (Fig. 7); the return path A -> B -> A (Fig. 10, M2's case); bandwidth and mobility frequency
sweeps (Fig. 12); quality (Fig. 13); memory of retained / staged state (Fig. 14).

## 2. Facts this protocol rests on

| fact | source | tag |
|---|---|---|
| M3-S3 (SUPPORTED eae5f1c4): A -> B switch at call 80, user to C at B's call 110 and to D at 130 (B -> C cancelled); remote serving s2 / base 0.771 dog, 0.747 bfly; readiness of B -> D 21.3 -> 8.2 s, 24.7 -> 9.7 s; total bytes +5-10 %. Flags: base = Fig. 7 OTTER flags; M3 = `--m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2`. | `osdi/m3s3/m3s3_report.md`, `run_m3_s3.sh` | [V] |
| External baselines handle overlapping moves: P-full / R-full cancel the in-flight task (progress discarded) and start toward the new edge (`_xb_cancel`, `_xb_start`); Full cancels the in-transit state and resends it whole to the new edge (`full_handoff` redirect). | `mobility_orchestrate.py` | [V] code |
| Moves: the XB loop supports wall-clock (`--tm`, equal spacing) or call-based (`--move_calls`, XB policies only) moves; Full's loop supports `--tm` only. Call-based moves depend on how fast each method generates (a method that stalls would move the user later), so they cannot compare methods. | same | [V] code |
| **Harness addition (Fig. 11):** `--move_times t1,t2` (seconds after the trigger) in both loops; without the flag the schedule is unchanged. `tm` is used only for this schedule. | `_move_due` | [V] code |
| Per edge change the delivery log gives TTFO-local (change -> first output generated at that edge, before the next change) and the remote-served stretches. | `xb_delivery.delivery_metrics` | [V] code |
| Single migration at 1 Gbps (Fig. 7): TTFO-local OTTER 23.3 / 24.6 s, R-full 36.9 / 36.8, Full 53.6 / 53.6, P-full 213.6 / 219.2; R-full recomputes from call 0, so its cost grows with the call at which a migration starts. | Fig. 7 | [V] |

**Numbers seen before this draft (disclosed).** Fig. 7 (above); M3-S3 Phase D (above); XB3 / XB4 (older OTTER
`reuse_dyn2`, rho 1 / 2, dog): Full gap 81.6 / 67.7 s, R-full remote 71.7 / 44.7 s, OTTER (old) 0.5 s remote.

## 3. Scenarios, methods, runs

Path A -> B -> C -> D, 1 Gbps, first trigger at call 30 (user to B), Fig. 7 workloads with seed 0.

| scenario | moves after the trigger (`--move_times`) | what it exercises |
|---|---|---|
| **Chain** | user to C at 45 s, to D at 90 s | repeated moves; each OTTER migration has time to finish (~22 s) before the next move |
| **Cancel** | user to C at 48 s, to D at 60 s | the M3-S3 pattern on the wall clock: B -> C is cancelled by the move to D (OTTER base needs ~22 s) |

| method | policy / flags |
|---|---|
| Full | `full` |
| Llumnix-style (P-full) | `precopy_full@thr=256:rl=10` (Fig. 7); non-convergence marked (plan) |
| ServerlessLLM-style (R-full) | `recompute_full@lag=1:rl=1` (Fig. 7) |
| OTTER w/o staging | `precopy_replay@thr=16:rl=1` + Fig. 7 OTTER flags (M1 + M2) |
| OTTER | the same + `--m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2` (M3-S3) |

All: `--hops 3 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 800 --max_run_s 2400 --xb_horizon 100
--horizon_calls 130 --dyn_probe 4`. `--post_chunks 800` lets the reference cover P-full's late final switch (~call 540)
plus the horizon. Runs: 5 methods x 2 scenarios x 2 workloads x 3 reps (D4) = **60**, methods interleaved per rep.
Estimate [H] ~13 min per run (reference ~8 min): ~13 h.

## 4. Metrics (per run)

- **Time without local service** N (figure label "Non-local time") = sum over the three edge changes (B, C, D) of the time from the change to the first
  output generated at the new edge, truncated at the next change (and at the run's last delivery for D). Split into
  **remote-served** (the user receives chunks from another edge: `remote_wall_s`) and **interrupted** (N - remote).
- **Final readiness** R_D = TTFO-local at D (the last change).
- Descriptive: max delivery gap, total stall (Fig. 8 rule), bytes (all / into D after the move to D), per-move TTFO-local,
  remote-delivery estimate, M3 staged / reused entries, fallbacks.

## 5. Hypotheses (each scenario x workload)

- **F11-H1 (vs external).** median N(OTTER) <= 0.5 x min(median N of Full, P-full, R-full). Predictions [H]: Chain OTTER
  ~35-45 s, Full ~145 s (redirected twice, ~53 s per resend), R-full >= 100 s (recomputes ~180 calls at D), P-full
  >= 200 s; Cancel similar.
- **F11-H2 (staging).** median N(OTTER) <= 0.80 x median N(OTTER w/o staging) (M3-S3's R-D1 margin). Predictions [H]:
  Chain ~0.6 (the first move is identical in both, ~22 s; later moves ~8 vs ~22 s); Cancel ~0.75.
- **F11-H3 (final readiness).** median R_D(OTTER) < median R_D(OTTER w/o staging).

Descriptive: the same comparisons for every method pair; R_D of all methods; bytes (M3 is not a traffic reduction,
M3-S3: +5-10 %).

## 6. Statistics

Per cell: median and range over 3 valid reps (3 required, else NOT EVALUABLE); every rep shown.

## 7. Validity and correctness (as each method claims it)

- XB validity for the XB policies, the W / R / N validity for Full (as in Fig. 7); one commit on A-D; GPU 0 idle.
- **Non-convergence is a result, not an exclusion:** a run whose final edge never serves locally before the run ends is
  kept, marked "not converged", with N truncated at its last delivery; it counts in the medians.
- Full: whole-state digests at every resume, final Sink digest equal to the source's.
- P-full: every completed switchover verified (component digests). R-full: inputs exact at every switchover.
- OTTER (both): every switch SINKOK or verified fallback (0 / 360 mismatching blocks at each `sink_sync_check`), replay
  order / no lost or duplicated calls, M3 provenance checks as M3-S3 (issued versions only, entry digests).

## 8. Procedure and tools

`tools/eval/run_fig11.sh preflight | first | rest | dry`, `tools/eval/fig11_report.py` (`--sanity`),
`tools/eval/plot_fig11.py`; `--move_times` in `mobility_orchestrate.py`.

1. Local dry run (dog, both scenarios, all five methods, moves scaled to the dry service time: Chain 12 / 24 s,
   Cancel 12 / 13 s): done, `run_fig11.sh dry` rc 0. 10 / 10 runs valid with every C1 check passing; moves at the given
   wall-clock times for every method (Full through its own loop); OTTER: SINKOK at every switch, M3 handover, lineage
   import and entry forwarding happen with wall-clock moves, B -> C cancelled in Cancel; report and figures produced
   (dry values are not results).
2. Regression with `--move_times` (done 2026-10-31, sequential): `test_xb` ALL PASS (87), `test_m1_live` ALL PASS (50),
   `test_m2_live` ALL PASS (45), `test_m2_track_cpu` ALL PASS, `test_m3v2` ALL PASS (28). A first pass had `test_xb`
   fail on "nodes on different commits" (I committed during the test) and two `test_m2_live` fault tests miss the planned
   switch call 164 under CPU load (full-base fallback at 100 Mbps); both passed on an undisturbed rerun. Rerun at the
   freeze commit; one commit on A-D (after Fig. 10).
3. `run_fig11.sh first` (Chain, dog, OTTER, rep 1) + `fig11_report.py --sanity`; counted if it meets section 7.
4. `run_fig11.sh rest` (59 runs), `fig11_report.py`, `plot_fig11.py`.

## 9. Plot specification

Canvas of Fig. 6a / 9 / 10 (5.83 x 4.78 in); OTTER blue, OTTER w/o staging light blue, external baselines gray.
- **11a**: stacked bars, N split into remote-served (method color) and interrupted (darkened), per method; one panel
  per scenario, workloads side by side (Low-refresh solid, High-refresh hatched) (D5); not-converged runs marked. Method
  names 28 pt, rotated 30 degrees, short (Full, Llumnix, SLLM, w/o M3, OTTER) so they fit Fig. 6a's plot box; fonts never
  reduced.
- **11b**: R_D per method (log if the medians span >= 1 decade, the Fig. 7 rule).

## 10. Open decisions (user)

| | question | options | [R] |
|---|---|---|---|
| D1 | scenarios | Chain + Cancel / Cancel only (= M3-S3 on the wall clock) / + Return (Fig. 10 covers it) | Chain + Cancel |
| D2 | move schedule | wall clock `--move_times` for every method (new flag) / call-based (XB methods only; not comparable across methods) | wall clock |
| D3 | methods | the five above / without P-full (it never finishes a move before the next; ~10 % of the run time) | the five (plan: include, mark non-convergence) |
| D4 | reps | 3 / 5 for the OTTER pair only (+8 runs) | 3 |
| D5 | layout | one panel per scenario (methods x workloads) / one panel per workload | per scenario |
| D6 | thresholds | H1 0.5, H2 0.80 / others | as above |

## 11. What Fig. 11 must not claim

- A traffic reduction from M3 (it moves more bytes; M3-S3 +5-10 %).
- Equivalent correctness across methods (Full / P-full / R-full restore the whole state; OTTER the Sink exactly and the
  recent state by replay).
- Results for other mobility frequencies, bandwidths, unpredicted paths or more edges (four hosts; Fig. 12).
- That the user's network latency during remote serving is measured (it is not: LAN; deferred to the network evaluation).
