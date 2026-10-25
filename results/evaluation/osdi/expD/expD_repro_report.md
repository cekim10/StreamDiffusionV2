# ExpD C / D reproduction under the corrected EXEC_START code (2026-10-24)

Frozen runs: `expD_C`, `expD_D` (commit 656dde6, source idle during the placement window). Reproduction: `expDR_C`, `expDR_D` (same configurations: `--pp_configs split:none,split:top1,reuse_dyn:top1,reuse_dyn:oracle`, lookahead 10 s, budget 1, 1 Gbps, trigger 30, 3 reps). Validity: the frozen expD rules, unchanged. Nothing in the frozen directories is modified.

## Scenario C

Reproduction commits: ['a0fbae6']; runs 12 (valid 12), source chunks before the move: original [0], reproduction [16]; move call: original [30], reproduction [47]; event order ok in reproduction: 12 / 12; boundary wait at the handoff: original median 0.002 s, reproduction 0.269 s

| configuration | reps valid orig / repro | bind-ready s | TTFO s | x (dest / top) | B_source | B_post | B_fwd | rejoin calls |
|---|---|---|---|---|---|---|---|---|
| Full OTTER | 3 / 3 | 4.942 -> 5.183 | 0.707 -> 0.969 | 0.716 -> 0.716 | 1.000 -> 1.000 | 0.280 -> 0.280 | 0.000 -> 0.000 | 7 -> 7 |
| M1 + M2 (no placement) | 3 / 3 | 15.419 -> 15.674 | 0.697 -> 0.973 | 0.000 -> 0.000 | 1.000 -> 1.000 | 1.000 -> 1.000 | 0.000 -> 0.000 | 6 -> 6 |
| M1 + M2 + top-1 | 3 / 3 | 4.900 -> 5.199 | 0.703 -> 0.984 | 0.714 -> 0.716 | 1.000 -> 1.000 | 0.283 -> 0.280 | 0.000 -> 0.000 | 7 -> 7 |
| oracle | 3 / 3 | 4.921 -> 5.271 | 0.699 -> 1.059 | 0.716 -> 0.716 | 1.000 -> 1.000 | 0.280 -> 0.280 | 0.000 -> 0.000 | 7 -> 7 |

## Scenario D

Reproduction commits: ['a0fbae6']; runs 12 (valid 12), source chunks before the move: original [0], reproduction [15, 16]; move call: original [30], reproduction [46, 47]; event order ok in reproduction: 12 / 12; boundary wait at the handoff: original median 0.002 s, reproduction 0.284 s

| configuration | reps valid orig / repro | bind-ready s | TTFO s | x (dest / top) | B_source | B_post | B_fwd | rejoin calls |
|---|---|---|---|---|---|---|---|---|
| Full OTTER | 3 / 3 | 15.463 -> 15.788 | 0.722 -> 1.025 | 0.716 -> 0.716 | 1.226 -> 1.226 | 0.506 -> 0.506 | 0.501 -> 0.501 | 6 -> 6 |
| M1 + M2 (no placement) | 3 / 3 | 15.531 -> 15.782 | 0.720 -> 1.003 | 0.000 -> 0.000 | 1.000 -> 1.000 | 1.000 -> 1.000 | 0.000 -> 0.000 | 6 -> 6 |
| M1 + M2 + top-1 | 3 / 3 | 15.525 -> 15.771 | 0.724 -> 1.045 | 0.716 -> 0.716 | 1.012 -> 1.010 | 0.293 -> 0.290 | 0.715 -> 0.717 | 6 -> 6 |
| oracle | 3 / 3 | 4.901 -> 5.253 | 0.722 -> 1.014 | 0.718 -> 0.716 | 1.000 -> 1.000 | 0.278 -> 0.280 | 0.000 -> 0.000 | 7 -> 7 |

## Verdicts (frozen rules, applied to each set by aggregate_expD.py)

- **G4**: frozen SUPPORTED (Full OTTER bind-ready 4.942 s (n=3) <= no placement 15.419 s (n=3) - 0.5 x 0.716 x 14.05 = 10.389); reproduction SUPPORTED (Full OTTER bind-ready 5.183 s (n=3) <= no placement 15.674 s (n=3) - 0.5 x 0.716 x 14.05 = 10.644)
- **G5**: frozen NOT SUPPORTED ((a) bind-ready 15.463 vs no placement 15.531 s, within 1.5 s (n=3) [pass]; (b) B_source,total 1.226 <= 1.02 [fail]; (c) B_post 0.506 <= (1 - x) + 0.02 with x 0.716 [fail]; (d) B_fwd 0.501 >= 0.9 x 0.716 [fail]); reproduction NOT SUPPORTED ((a) bind-ready 15.788 vs no placement 15.782 s, within 1.5 s (n=3) [pass]; (b) B_source,total 1.226 <= 1.02 [fail]; (c) B_post 0.506 <= (1 - x) + 0.02 with x 0.716 [fail]; (d) B_fwd 0.501 >= 0.9 x 0.716 [fail])

Changed conclusions, if any, are listed above; the frozen verdicts stay as recorded, and the choice of which set the paper cites is made after this report is reviewed.
