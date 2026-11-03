# E9 cluster simulation: results (SIMULATED)

Rules: `preregistration.md` (FROZEN). Sweep `primary`, 2592 runs; medians over seeds. Calibrated from testbed measurements, validated against Fig. 11 (gate 76 / 76).

**CL-H1 NOT SUPPORTED** (stalled seconds < each baseline: True; local share >= each: False; OTTER / best baseline stalled seconds 0.184).

| method | stalled s / session-h | local share | stalls > 1 / 2 / 5 / 10 s per session-h | seeds |
|---|---|---|---|---|
| Full | 167.4 | 0.913 | 19.06 / 18.93 / 18.52 / 3.79 | 3 |
| Llumnix | 149.2 | 0.747 | 14.62 / 14.61 / 14.58 / 7.48 | 3 |
| SLLM | 443.3 | 0.153 | 1.41 / 1.41 / 1.41 / 1.41 | 3 |
| Unstaged | 27.5 | 0.913 | 18.30 / 0.00 / 0.00 / 0.00 | 3 |
| OTTER | 27.5 | 0.913 | 18.30 / 0.00 / 0.00 / 0.00 | 3 |
| Replicate | 27.2 | 0.907 | 18.09 / 0.00 / 0.00 / 0.00 | 3 |

**CL-H2 SUPPORTED** (N 64, C 10 Gbps, dwell 180 s):

| M (GB) | delay per move OTTER / Replicate (s) | staging GB per session-h OTTER / Replicate | holds |
|---|---|---|---|
| 8.0 | 12.9 / 14.0 | 50.74 / 159.48 | True |
| 32.0 | 12.9 / 14.0 | 76.61 / 159.33 | True |
| 128.0 | 12.8 / 14.0 | 52.35 / 159.33 | True |

**CL-H3 (descriptive):** staging helps (OTTER delay per move < 0.9 x Unstaged) in 0 / 36 (C, dwell, M) cells at N 64.

| C (Gbps) | dwell (s) | M (GB) | delay OTTER / Unstaged (s) | gain |
|---|---|---|---|---|
| 1 | 60 | 0 | 47.0 / 47.0 | 0.0 % |
| 1 | 60 | 8 | 51.8 / 42.5 | -21.9 % |
| 1 | 60 | 32 | 46.1 / 37.7 | -22.5 % |
| 1 | 60 | 128 | 43.5 / 37.1 | -17.3 % |
| 1 | 180 | 0 | 45.1 / 45.1 | 0.0 % |
| 1 | 180 | 8 | 68.9 / 38.1 | -81.0 % |
| 1 | 180 | 32 | 50.2 / 32.6 | -54.1 % |
| 1 | 180 | 128 | 39.4 / 32.5 | -21.0 % |
| 1 | 600 | 0 | 36.3 / 36.3 | 0.0 % |
| 1 | 600 | 8 | 38.6 / 32.4 | -19.3 % |
| 1 | 600 | 32 | 34.4 / 31.1 | -10.6 % |
| 1 | 600 | 128 | 34.0 / 31.1 | -9.5 % |
| 10 | 60 | 0 | 10.8 / 10.8 | 0.0 % |
| 10 | 60 | 8 | 11.0 / 10.7 | -2.4 % |
| 10 | 60 | 32 | 10.9 / 10.7 | -1.7 % |
| 10 | 60 | 128 | 10.7 / 10.7 | 0.0 % |
| 10 | 180 | 0 | 12.9 / 12.9 | 0.0 % |
| 10 | 180 | 8 | 12.9 / 12.9 | -0.4 % |
| 10 | 180 | 32 | 12.9 / 12.8 | -0.2 % |
| 10 | 180 | 128 | 12.8 / 12.8 | 0.0 % |
| 10 | 600 | 0 | 15.4 / 15.4 | 0.0 % |
| 10 | 600 | 8 | 15.4 / 15.4 | -0.1 % |
| 10 | 600 | 32 | 15.4 / 15.4 | -0.0 % |
| 10 | 600 | 128 | 15.4 / 15.4 | -0.0 % |
| 25 | 60 | 0 | 10.7 / 10.7 | 0.0 % |
| 25 | 60 | 8 | 10.7 / 10.7 | 0.0 % |
| 25 | 60 | 32 | 10.7 / 10.7 | 0.0 % |
| 25 | 60 | 128 | 10.7 / 10.7 | 0.0 % |
| 25 | 180 | 0 | 12.8 / 12.8 | 0.0 % |
| 25 | 180 | 8 | 12.8 / 12.8 | 0.0 % |
| 25 | 180 | 32 | 12.8 / 12.8 | -0.0 % |
| 25 | 180 | 128 | 12.8 / 12.8 | 0.0 % |
| 25 | 600 | 0 | 15.3 / 15.3 | 0.0 % |
| 25 | 600 | 8 | 15.3 / 15.3 | 0.0 % |
| 25 | 600 | 32 | 15.3 / 15.3 | 0.0 % |
| 25 | 600 | 128 | 15.3 / 15.3 | 0.0 % |

## Reading (SIMULATED; sweep at commit 37aca4b7, the frozen simulator and calibration; no refit)

- **CL-H1 NOT SUPPORTED by the frozen rule**, on the local-share condition only: OTTER 0.91329 vs Full 0.91332
  (a 3e-5 deficit; per-seed spread about 0.01). Its stalled-time condition holds: 27.5 s per session-hour vs Llumnix
  149.2, Full 167.4, SLLM 443.3 (0.18 x the best). The time Full spends stalled, OTTER spends served remotely (remote
  share 0.079 vs 0.040). Stalls > 1 s per session-hour: OTTER 18.3, Full 19.1 (OTTER's ~1.5 s cutover counts); > 2 s:
  OTTER 0, Full 18.9. Not claimed: fewer interruptions over 1 s, or more local service than Full.
- **CL-H2 SUPPORTED** at M 8 / 32 / 128 GB: delay per move OTTER 12.8-12.9 vs Replicate 14.0 s, staging 51-77 vs 159
  GB per session-hour.
- **CL-H3 (descriptive): staging helps in 0 / 36 cells at N 64.** At 10 and 25 Gbps OTTER = Unstaged within 2.4 %
  (readiness is bound by the replay floor); at 1 Gbps staging hurts by 9.5-81 % (staging flows compete with
  migrations), and OTTER's local share falls to 0.712 vs Unstaged 0.806 at the primary M and dwell.
- **Where the baselines win (link capacity, N 64, M 32 GB, dwell 180 s):** at 25 Gbps Full has a shorter delay per
  move (8.7 vs 12.8 s) and a higher local share (0.936 vs 0.913), at 3.3 x OTTER's stalled time (92.0 vs 27.5 s per
  session-hour). At 1 Gbps OTTER (and Unstaged) keep local share 0.71-0.81 vs Full 0.43 and stalled time 19-23 vs
  1,587 s per session-hour.
- Beyond 240 calls the simulator extrapolates delta bytes (D5); the Fig. 10 long-age measurement is pending.
