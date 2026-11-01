# Fig. 11 report: repeated mobility A -> B -> C -> D

Preregistration FROZEN 76f40e9b (+ Note 1 21e73704, cosmetic). Runs: 60 (1c9fe64f; run commit 8800fee8 on A-D):
Chain (moves at 45 / 90 s after the trigger) and Cancel (48 / 60 s), Full, Llumnix-style P-full, ServerlessLLM-style
R-full, No staging (OTTER M1 + M2), OTTER (+ M3), 3 reps, both workloads, 1 Gbps. Numbers: `fig11_results.{json,md}`
(`tools/eval/fig11_report.py`); figures: `figures/` (`tools/eval/plot_fig11.py`).

## 1. Verdicts (frozen rules)

| hypothesis | Chain dog | Chain bfly | Cancel dog | Cancel bfly | verdict |
|---|---|---|---|---|---|
| F11-H1: N(OTTER) <= 0.5 x best external N (Full in every cell) | 57.6 / 143.4 = 0.40 | 66.1 / 143.5 = 0.46 | 46.5 / 115.9 = 0.40 | 54.8 / 113.4 = 0.48 | **SUPPORTED** |
| F11-H2: N_post(OTTER) <= 0.80 x N_post(No staging) | 33.4 / 46.0 = 0.73 | 37.0 / 49.9 = 0.74 | 22.0 / 35.7 = 0.62 | 25.1 / 38.0 = 0.66 | **SUPPORTED** |
| F11-H3: R_D(OTTER) < R_D(No staging) | 10.2 < 23.1 | 10.2 < 24.6 | 10.0 < 23.7 | 13.1 < 26.0 | **SUPPORTED** |

(s, medians of 3.) Validity: 60 / 60 kept; 0 not converged, 0 right-censored (every final edge served locally within
T_obs = 300 s; the slowest, P-full, at 213-220 s); OTTER's C1 checks (SINKOK or verified fallback, 0 / 360 Sink blocks
mismatching, replay order, no lost / duplicated calls) pass in every run. No median is a lower bound.

## 2. Panel 11a: local-service delay N, with continuity [V] measured

| scenario | method | N (s) | remote-served (s) | interrupted (s) | N_post (s) | max gap (s) | total stall (s) | bytes (GB) |
|---|---|---|---|---|---|---|---|---|
| Chain dog | Full | 143.4 | 0.0 | 143.4 | 98.4 | 143.45 | 142.85 | 13.37 |
| | Llumnix-style | 303.6 | 251.6 | 51.9 | 258.6 | 51.19 | 69.26 | 31.74 |
| | ServerlessLLM-style | 226.0 | 119.6 | 106.2 | 188.7 | 85.82 | 144.36 | 0.53 |
| | No staging | 69.1 | 64.3 | 4.8 | 46.0 | 1.73 | 6.02 | 5.26 |
| | **OTTER** | **57.6** | 53.4 | 4.3 | **33.4** | **1.44** | **2.45** | 5.28 |
| Chain bfly | Full / Llumnix / SLLM | 143.5 / 310.5 / 225.3 | | | | 143.54 / 52.95 / 85.46 | | 13.37 / 32.22 / 0.40 |
| | No staging | 76.2 | 70.9 | 5.3 | 49.9 | 1.83 | 6.41 | 6.53 |
| | **OTTER** | **66.1** | 61.6 | 4.5 | **37.0** | **1.59** | **2.71** | 7.22 |
| Cancel dog | Full / Llumnix / SLLM | 115.9 / 275.3 / 161.6 | | | | 115.94 / 51.69 / 55.58 | | 9.92 / 28.78 / 0.46 |
| | No staging | 59.2 | 55.6 | 3.6 | 35.7 | 1.66 | 5.00 | 4.67 |
| | **OTTER** | **46.5** | 43.4 | 3.1 | **22.0** | **1.45** | **1.63** | 5.25 |
| Cancel bfly | Full / Llumnix / SLLM | 113.4 / 279.3 / 161.3 | | | | 113.40 / 52.35 / 55.50 | | 9.92 / 29.30 / 0.35 |
| | No staging | 64.0 | 60.2 | 3.8 | 38.0 | 1.81 | 5.43 | 5.69 |
| | **OTTER** | **54.8** | 51.5 | 3.3 | **25.1** | **1.48** | **1.67** | 6.28 |

(Full rows of every cell, all columns: `fig11_results.md`.)

- **N is not a continuity measure** (preregistration section 4). OTTER's N is almost all remote-served (the user keeps
  receiving output from the previous edge); its interruption is 3.1-4.5 s over three moves and its max gap 1.44-1.59 s.
  Full's N is all interruption (max gap 113-144 s: it stops and resends 6.46 GB at every move, redirected twice).
  P-full serves remotely for 223-257 s and still has a 51-53 s stop-and-copy gap; R-full has 55-86 s gaps (it
  recomputes from call 0, so its cost grows with each later move).
- **Bytes.** OTTER sends +0.4 % (Chain dog) to +12 % (Cancel dog) more than No staging: the staging forwards
  (1.7-2.3 GB) replace, rather than add to, most of the last migration's base (12 MB delta into D in Chain dog). M3 is
  not a traffic reduction (M3-S3: +5-10 %). R-full sends only inputs (0.35-0.53 GB) and pays in recomputation.

## 3. Where staging acts: per-move breakdown [V] measured (median time without local service per edge change, s)

| scenario, workload | method | B (1st move) | C | D (final) |
|---|---|---|---|---|
| Chain dog | No staging / OTTER | 23.1 / 24.5 | 23.0 / 23.2 | 23.1 / **10.2** |
| Chain bfly | No staging / OTTER | 26.4 / 28.7 | 25.3 / 26.7 | 24.6 / **10.2** |
| Cancel dog | No staging / OTTER | 23.3 / 24.5 | 12.0 / 12.0 (truncated by the move to D) | 23.7 / **10.0** |
| Cancel bfly | No staging / OTTER | 26.0 / 29.3 | 12.0 / 12.0 (truncated) | 26.0 / **13.1** |

- **The whole gain is at the final edge D** (13-14 s per run). C is not shortened: in Chain, C takes 23-27 s with or
  without staging.
- **Why C is not staged (event trace, Chain dog rep 1).** The first M3 plan runs at the move to C (45.0 s, `why: move`,
  the first ownership handover A -> B is taken then). It sees A holding all 180 entries of the retained version and
  forwards 178 of them to D (A -> D, 1.71 GB, 45.0 -> 59.9 s), while C receives its base from B as in No staging. When
  the user moves to D (90 s), D holds the Sink and gets a 12 MB delta base; D serves locally 9.7 s after the move, close
  to the replay-bound readiness of Fig. 10 (8.8-9.3 s). Before the move to C no plan had run, so nothing was staged for
  C. This matches the preregistered caution ("Chain is a test, not an expected win").
- **The first move costs more with M3**: +1.4 s (dog) and +2.3-3.3 s (bfly) at B, and +1.4 s at C in Chain bfly. The
  cause (M3 tracking / advertising on the source, in-flight forwards sharing the link) is not decomposed here. N_post
  excludes the first move by the frozen rule; the total N, which includes it, is also lower for OTTER in every cell.
- **Stall.** OTTER's total stall (1.6-2.7 s) is below No staging's (5.0-6.4 s) with similar max gaps; the stall
  difference is not decomposed here.

## 4. Predictions [H] vs measured

| prediction (preregistration section 5) | measured |
|---|---|
| Chain OTTER N ~35-45 s | 57.6 / 66.1 s: **higher**. Only D is shortened; B and C each still take 23-29 s |
| Full ~145 s | 143.4 / 143.5 s |
| R-full >= 100 s | 225-226 s (Chain), 161-162 s (Cancel) |
| P-full >= 200 s | 275-311 s |
| H2 Cancel ratio ~0.4-0.6 | 0.62 / 0.66: **slightly above** (still <= 0.80) |
| H2 Chain: a test, not an expected win | 0.73 / 0.74: holds, all from D |

## 5. Corrections and figure notes

- **Byte count (report tool, fixed before this report).** `transmitted_bytes()` counts migration tasks only; OTTER's
  M3 staging forwards (`m3_forward_done`, entries sent x 9,584,640 B, partial sends of cancelled flows included) were
  missing. The sanity output and the first report run showed OTTER 3.54 GB (Chain dog) instead of 5.28 GB.
  `fig11_report.py` now adds them (`m3_forward_bytes` recorded per run). Bytes are descriptive; no verdict changes.
- **Figure labels (cosmetic, after the runs; Note 2 in the preregistration).** At 28 pt the y labels "Local-service
  delay (s)" and "Final-edge readiness (s)" are taller than the Fig. 6a axes box and were clipped; they are shortened to
  "Locality delay (s)" and "Final readiness (s)" (never a smaller font). 11b uses power-of-ten tick labels ($10^k$) so
  the label clears the ticks. Text and tables keep the preregistered names. Canvas, axes box and font sizes unchanged.

## 6. Limits

Four hosts, one path A -> B -> C -> D known to the planner, two move schedules, 1 Gbps, one seed per workload, 3 reps.
Mobility frequency, bandwidth, unpredicted paths and larger topologies: Fig. 12 / Exp T. The per-move costs of M3 on
the first move and the stall difference are measured, not explained.
