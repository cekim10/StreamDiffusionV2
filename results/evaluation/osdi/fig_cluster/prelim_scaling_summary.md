# E9 sensitivity to cluster size and load: PRELIMINARY summary (2026-11-04)

**Preliminary simulation - Sink delta beyond 240 calls extrapolated.** Idealized store [A11]. Descriptive only (G3).
Not final paper numbers. The model's core never congests, so this is **not an end-to-end scalability proof**.

Protocol: `scaling_protocol.md`, with decisions G1-G7 committed (1b98cd49) before the run. Tables:
`prelim_scaling_{load,scale,scale_g4}.md`. Figures: `prelim_figures/` (figs_load_*, figs_size_*; legend figc_legend).
Medians over 5 seeds.

## Gates

| gate | load | scale (G8) | scale_g4 |
|---|---|---|---|
| R0: points shared with the frozen sweep identical | 144 / 144 runs | 36 / 36 | none shared |
| R1: 2 sites, OTTER == Unstaged | none in grid | 10 / 10 pairs | none in grid |

Wall time: 787 s (load, 480 runs), 366 s (scale), 315 s (scale_g4). At 256 GPUs and 0.94 per GPU, one run takes
4-7 s.

## L: load, 128 GPUs

| sessions / GPU | 0.125 | 0.25 | 0.5 | 0.625 | 0.75 | 0.875 | 0.94 |
|---|---|---|---|---|---|---|---|
| **10 Gbps** OTTER stalled s / session-h | 28.7 | 28.2 | 27.8 | 26.4 | 23.2 | 19.9 | 16.7 |
| OTTER local share | 93.4 % | 93.8 % | 91.6 % | 88.0 % | 79.4 % | 65.6 % | 51.4 % |
| OTTER moves reaching local service | 0.94 | 0.95 | 0.93 | 0.90 | 0.84 | 0.72 | 0.56 |
| OTTER time without local service per move | 10.5 s | 9.8 s | 12.7 s | 17.3 s | 27.7 s | 47.0 s | 71.4 s |
| **1 Gbps** OTTER stalled | 27.1 | 25.5 | 19.2 | 15.2 | 11.0 | 8.9 | 15.2 |
| OTTER local share | 89.9 % | 88.1 % | 70.4 % | 58.3 % | 43.6 % | 28.8 % | 21.6 % |
| Unstaged local share | 87.6 % | 87.1 % | 81.0 % | 76.5 % | 65.3 % | 49.1 % | 32.9 % |

- **Saturation trades locality for fewer stalls.** As load rises, stalled seconds fall while local share, completion
  and time to local service all degrade: sessions stay remote instead of stalling. This is why both are always shown.
- **10 Gbps.** OTTER, Unstaged and Replicate are within 0.7 s / session-h and 1.6 points of local share at every load:
  staging neither helps nor hurts.
- **1 Gbps.** Staging costs locality, and more so as load rises:
  - OTTER's local share is 10-22 points below Unstaged from 0.5 per GPU on.
  - Replicate is lower still.
  - OTTER's lower stalled seconds there come with less local service, not better service.
  - This extends the frozen CL-H3 finding (staging helped in 0 / 36 cells) to load.
- **L-D1 (descriptive).** OTTER's median stalled seconds are below Full, Llumnix and SLLM in 16 / 16 cells.

## S: cluster size (sessions per GPU fixed)

| GPUs (G8 grid) | 16 (2 sites) | 32 | 64 | 128 | 256 (wall time only) |
|---|---|---|---|---|---|
| 0.5 / GPU: OTTER stalled, local | 26.7, 95.4 % | 28.0, 93.6 % | 27.6, 92.9 % | 27.8, 91.6 % | 27.7, 91.7 % |
| 0.94 / GPU: OTTER stalled, local | 20.8, 82.6 % | 19.6, 70.0 % | 17.8, 61.2 % | 16.7, 51.4 % | 16.2, 52.7 % |

- **0.5 per GPU.** Per-session results are flat from 32 GPUs on (stalled 27.6-28.0, local 91.6-93.6 %). The 2-site
  point has no staging candidate, so it is not a scaling result.
- **0.94 per GPU.** Local share falls with cluster size, 82.6 % -> 51.4 % from 16 to 128 GPUs.
  - Full and Unstaged fall in the same way, so it is a property of the model (moving into full sites with more
    sites), not of a method.
  - It levels off between 128 and 256 GPUs.
- **G4 grid (robustness).** The same shape at a lower level: 0.5 per GPU 87-92 %; 0.94 per GPU falling
  60 % -> 42 % (45 % at 256).
- **S-D1 (descriptive).** G8: 7 / 10 cells. The three exceptions are SLLM at 0.94 per GPU with 16-64 GPUs (SLLM 7.9-15.1
  vs OTTER 17.8-20.8 s / session-h). There SLLM has 12-50 % local service, against 61-83 % for OTTER. G4: 10 / 10.

## Follow-ups (G4)

After the Fig. 10 long-age runs:
1. Check the delta extrapolation against them.
2. Change the calibration if needed.
3. If it changed, re-run the 76 / 76 gate.
4. Re-run these three sweeps.
