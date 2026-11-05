# E9 after the Fig. 10 long-age runs (2026-11-04; E9 D5, user decision G4)

## 1. What was measured (`osdi/fig10/fig10_longage_results.md`, Versioned only, 2 reps, 8 / 8 valid)

| input | age (calls) | measured delta (MB) | frozen simulator's extrapolation (MB) | measured / extrapolated |
|---|---|---|---|---|
| dog | 1,000 | 117.4 | 293.1 | 0.40 |
| dog | 3,000 | 127.0 | 932.1 | 0.14 |
| bfly | 1,000 | 558.3 | 757.5 | 0.74 |
| bfly | 3,000 | 596.6 | 1,609.4 | 0.37 |

Every second cutover SINKOK and DELTAOK, 0 / 360 blocks mismatched, 0 fallbacks, retained version held to the second
trigger in 8 / 8. The delta saturates (changed blocks 91 -> 92 dog, 161 -> 168 bfly from age 1,000 to 3,000); the
frozen extrapolation (150-240 slope) overstated OTTER's and Unstaged's delta bytes by 1.4-7.3 x at long ages.
Readiness 8.86-10.30 s (Fig. 10: 8.80-9.30 s).

## 2. Calibration change and gate

- `calibration_longage.json` = the frozen `calibration.json` + the measured base bytes at ages 1,000 / 3,000
  (medians). The frozen file is unchanged; `cluster_sim.py` reads `OTTER_CAL` (default: the frozen file).
- Frozen validation reproduced byte-identical with the default calibration.
- Gate with the long-age calibration: **76 / 76 PASS**; every one of the 76 simulated values is identical (the
  validation runs only use ages <= 240).

## 3. Re-run (`longage_sweep_{primary,load,scale,scale_g4}.json`, same grids and seeds)

- Changed runs: only the methods that use Versioned deltas (OTTER, Unstaged): 648 / 2,592 primary runs. Full,
  Llumnix, SLLM and Replicate are identical.
- **Frozen verdicts unchanged:** CL-H1 NOT SUPPORTED (same table; OTTER / best baseline stalled 0.184),
  CL-H2 SUPPORTED, CL-H3 staging helps in 0 / 36 cells.
- **Main-figure points (N 64, 10 Gbps, M 32 GB, 6 / 20 / 60 moves per hour): unchanged** to the shown precision
  (largest change 0.004 stalled s / session-h, 0.00001 local share).
- Largest changes, all at 1 Gbps: OTTER / Unstaged stalled -20.9 to +12.6 s / session-h, local share -2.8 to +7.8
  points (smaller deltas make local service come sooner).
- OTTER's median stalled seconds below all three external baselines: 134 / 144 primary cells (frozen 135). The one
  flipped cell is N 96, 1 Gbps, M 128 GB, 60 moves / h: OTTER 10.7 -> 13.8 against Llumnix 12.8 s / session-h, where
  Llumnix serves locally 6.9 % of the time and OTTER 22.8 %.
- Stalled-seconds order changed in 12 / 144 primary cells and 3 / 16 load cells, only among OTTER, Unstaged and
  Replicate except the cell above.
- Scaling grids (descriptive, preliminary label kept): L-D1 16 / 16, S-D1 G8 7 / 10, G4 10 / 10, as before. R0 as
  printed in `longage_scaling_*.md` compares with the frozen sweep and so fails by construction (48 OTTER / Unstaged
  runs); against `longage_sweep_primary.json` the shared runs are identical (load 144 / 144, scale 36 / 36).

## 4. Reading

The extrapolation was conservative for OTTER; correcting it changes no verdict and no main-figure number. The paper
uses the long-age-calibrated results (`longage_*`), states that the frozen verdicts are unchanged, and cites the
measured long-age deltas as the check of the simulator's delta model.
