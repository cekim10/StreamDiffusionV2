# Fig. 11 preregistration: repeated mobility (M3, RQ5)

**Status: FROZEN (2026-10-31), before any Fig. 11 run.** DRAFT 1 was ddf88a5e; the user's review is applied: N is a
local-service delay (locality recovery), not a continuity measure, and is always reported with the max output gap and
the cumulative stall; non-converged runs are right-censored at a common observation horizon and never pooled as
completed values; H2 measures staging on the moves after the first. Runs start after Fig. 10 ends (A / B busy). Plan:
`osdi/eval_plan/plan.md` (Fig. 11, RQ5, P0). Decisions: section 10. Labels: [V]
verified in code or earlier records, [H] hypothesis / expectation, [R] recommendation.

Roles: Fig. 7 = one migration vs external baselines; Fig. 9 = M1; Fig. 10 = M2; **Fig. 11 = the whole system when the
user keeps moving: OTTER vs the external baselines, and the effect of lineage staging (M3) itself, under the same
conditions** (plan: "separate the gain over external baselines from the effect of staging itself").

## 1. Questions and messages

RQ5: can lineage-based staging accelerate repeated GPU mobility?

- **11a, local-service delay.** Over a run in which the user moves A -> B -> C -> D, how long until the user is served
  by the GPU at their current edge, summed over the moves, and how much of that time is served remotely vs interrupted?
  This is a locality-recovery cost, **not** a continuity measure (20 s of remote serving is not worse for the viewer than
  10 s of interruption), so the two parts stay separate and the continuity measures (max output gap, cumulative stall)
  are reported with it. Message to test: OTTER keeps this far below the external baselines, and staging shortens it on the
  moves after the first.
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
| No staging (OTTER w/o staging) | `precopy_replay@thr=16:rl=1` + Fig. 7 OTTER flags (M1 + M2) |
| OTTER | the same + `--m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2` (M3-S3) |

All: `--hops 3 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 800 --max_run_s 2400 --xb_horizon 100
--horizon_calls 130 --dyn_probe 4`. `--post_chunks 800` lets the reference cover P-full's late final switch (~call 540)
plus the horizon. Runs: 5 methods x 2 scenarios x 2 workloads x 3 reps (D4) = **60**, methods interleaved per rep.
Estimate [H] ~13 min per run (reference ~8 min): ~13 h.

## 4. Metrics (per run)

- **Local-service delay** N (figure label "Local-service delay") = sum over the three edge changes (B, C, D) of the time
  from the change to the first output generated at the new edge, truncated at the next change; the final edge D is
  observed for **T_obs = 300 s** after its change. Split into **remote-served** (the user receives chunks from another
  edge: `remote_wall_s`) and **interrupted** (N - remote), always shown separately.
- **N_post** = the same over the 2nd and 3rd changes (C and D): the moves on which staging can act.
- **Final-edge readiness** R_D = TTFO-local at D (the last change).
- **Continuity, reported with N in every table and in the text** (Figs. 7-8): max output gap, total stall (Fig. 8 rule).
- Descriptive: bytes (all / into D after the move to D), per-move TTFO-local, remote-delivery estimate, staged / reused
  entries, fallbacks.
- **Right-censoring (non-convergence).** Every method has the same observation horizon: T_obs after the final move. A run
  whose final edge has not served locally by then is "not converged": R_D > T_obs, and its N, N_post are lower bounds.
  Censored values are never pooled as completed values: a median whose rank falls on a censored run is reported as a
  lower bound (">="). A run that ends before T_obs without local service at D is invalid (harness), not censored.

## 5. Hypotheses (each scenario x workload)

- **F11-H1 (vs external).** median N(OTTER) <= 0.5 x min(median N of Full, P-full, R-full). Predictions [H]: Chain OTTER
  ~35-45 s, Full ~145 s (redirected twice, ~53 s per resend), R-full >= 100 s (recomputes ~180 calls at D), P-full
  >= 200 s; Cancel similar.
- **F11-H2 (staging, moves after the first; user).** median N_post(OTTER) <= 0.80 x median N_post(No staging). The first
  move cannot benefit from staging and is excluded; the total N is reported separately. Predictions [H], with caution:
  Cancel ~0.4-0.6 (M3-S3's 21.3 -> 8.2 s was measured on this pattern); **Chain is a test, not an expected win**: if the
  destination holds few valid entries or staging is late, the gain may be small.
- **F11-H3 (final readiness).** median R_D(OTTER) < median R_D(No staging).
- **Censoring in the rules.** OTTER's median must be uncensored for H1-H3 to hold; a censored baseline median enters as
  its lower bound (conservative: the comparison can only understate OTTER's advantage).

Descriptive: the same comparisons for every method pair; R_D of all methods; bytes (M3 is not a traffic reduction,
M3-S3: +5-10 %).

## 6. Statistics

Per cell: median and range over 3 valid reps (3 required, else NOT EVALUABLE); every rep shown.

## 7. Validity and correctness (as each method claims it)

- XB validity for the XB policies, the W / R / N validity for Full (as in Fig. 7); one commit on A-D; GPU 0 idle.
- **Non-convergence is a result, not an exclusion, and is right-censored:** a run without local service at D within
  T_obs after the final move is kept as "not converged" with R_D > T_obs (section 4); a run that ends earlier without
  local service at D is invalid. `--post_chunks 800` lets every method be observed past T_obs.
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

Canvas of Fig. 6a / 9 / 10 (5.83 x 4.78 in); OTTER blue, No staging light blue, external baselines gray.
Two subfigures (user): **11(a) local-service delay**, **11(b) final-edge readiness**; Chain and Cancel as separate
graphs of each (D5).
- **11a**: stacked bars, N split into remote-served (method color) and interrupted (darkened), per method; workloads side
  by side (Low-refresh solid, High-refresh hatched); censored medians labelled ">=" and "n.c.". Max gap and total stall
  in the text / table.
- **11b**: R_D per method, OTTER vs No staging emphasized (log if the medians span >= 1 decade, the Fig. 7 rule).
- No internal mechanism names in figures ("No staging", not "w/o M3"). Fonts never reduced; names at 28 pt in Fig. 6a's
  plot box (layout of the method names to be settled with the user).

## 10. Decisions (user, 2026-10-31)

| | decision |
|---|---|
| D1 | Chain + Cancel (regular repeated moves and a cancelled migration) |
| D2 | wall-clock moves (`--move_times`) for every method |
| D3 | the five methods |
| D4 | 3 reps |
| D5 | one graph per scenario for each subfigure |
| D6 | H1 kept (0.5); H2 on N_post (moves after the first, 0.80); H3 kept |

## 11. What Fig. 11 must not claim

- A traffic reduction from M3 (it moves more bytes; M3-S3 +5-10 %).
- Equivalent correctness across methods (Full / P-full / R-full restore the whole state; OTTER the Sink exactly and the
  recent state by replay).
- Results for other mobility frequencies, bandwidths, unpredicted paths or more edges (four hosts; Fig. 12).
- That the user's network latency during remote serving is measured (it is not: LAN; deferred to the network evaluation).
- That N measures streaming continuity (it measures locality recovery; continuity = max gap, cumulative stall).
- A censored value as a completed one, or a readiness for a method that did not converge within T_obs.
