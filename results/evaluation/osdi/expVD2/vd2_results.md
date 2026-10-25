# VD-2 results

Effect sizes and costs first. Control = frozen M1 (VC-1's OT-1 / OT-L). DINO = content similarity to the 16 pre-move calls; 'closed' = fraction of the gap between frozen M1 and REF closed in the Sink-less window; 'in band' = inside REF's own P5-P95 (preservation, descriptive). Costs are serial GPU seconds at the destination (upper bound on the TTFO increase) and bytes added to the fast path (RP-1 as a raw upper bound).

## dog OT-1 (REF V1 P99 3.96; control: V1 reset 8.12, bind 1.50, Sink-less DINO 0.544 vs REF 0.968 band [0.95, 0.986], dE 1.76, terminal 44.3 dB, first >= 35 dB 66)

| cell | valid | V1 reset (x ctrl) | V1 bind (x ctrl) | Sink-less DINO | closed | in band | Sink-less dE | first-4 E | post-bind DINO diff | post-bind dE | terminal PSNR | first >= 35 | cost s (pref <= 0.3) | bytes | DR fidelity (median / worst rel) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DR1 | True | 4.83 (0.60) | 1.50 (1.00) | 0.555 | 0.03 | False | 1.83 | 2.832 | -0.007 | 0.08 | 44.3 | 66 | 0.259 | 0.20 MB | 1.201 / 2.240 (layer 17) |
| DR2 | True | 4.36 (0.54) | 1.50 (1.00) | 0.556 | 0.03 | False | 1.82 | 2.318 | -0.007 | 0.08 | 44.3 | 66 | 0.520 | 0.40 MB | 0.712 / 1.596 (layer 6) |
| RP1 | True | 6.09 (0.75) | 1.24 (0.82) | 0.661 | 0.28 | False | 2.56 | 2.116 | -0.003 | 0.47 | 28.4 | None | 1.054 | 5.99 MB | - / - (layer None) |
| TSin | True | 8.66 (1.07) | 1.66 (1.11) | 0.945 | 0.95 | False | 1.22 | 2.771 | -0.001 | 0.11 | 43.3 | 65 | 0.778 | 0.00 MB | - / - (layer None) |
| TSout | True | 8.66 (1.07) | 1.42 (0.95) | 0.941 | 0.93 | False | 3.27 | 2.812 | -0.001 | 0.20 | 43.3 | 63 | 0.780 | 0.40 MB | - / - (layer None) |
| DR2+TSout | True | 3.67 (0.45) | 1.42 (0.95) | 0.952 | 0.96 | True | 3.22 | 1.918 | -0.001 | 0.20 | 43.3 | 63 | 1.300 | 0.80 MB | 0.712 / 1.596 (layer 6) |
| RP1+TSout | True | 5.34 (0.66) | 1.53 (1.02) | 0.952 | 0.96 | True | 2.38 | 1.334 | 0.001 | 0.63 | 28.4 | None | 1.831 | 6.39 MB | - / - (layer None) |

## dog OT-L (REF V1 P99 3.96; control: V1 reset 9.24, bind 2.28, Sink-less DINO 0.593 vs REF 0.971 band [0.956, 0.982], dE 2.15, terminal 44.9 dB, first >= 35 dB 162)

| cell | valid | V1 reset (x ctrl) | V1 bind (x ctrl) | Sink-less DINO | closed | in band | Sink-less dE | first-4 E | post-bind DINO diff | post-bind dE | terminal PSNR | first >= 35 | cost s (pref <= 0.3) | bytes | DR fidelity (median / worst rel) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DR1 | True | 4.39 (0.47) | 2.28 (1.00) | 0.597 | 0.01 | False | 2.17 | 2.316 | -0.006 | 0.08 | 44.9 | 162 | 0.258 | 0.20 MB | 1.225 / 2.287 (layer 17) |
| DR2 | True | 3.72 (0.40) | 2.28 (1.00) | 0.597 | 0.01 | False | 2.17 | 1.831 | -0.006 | 0.08 | 44.9 | 162 | 0.521 | 0.40 MB | 0.742 / 1.631 (layer 6) |
| RP1 | True | 7.03 (0.76) | 1.89 (0.83) | 0.721 | 0.34 | False | 2.12 | 1.892 | -0.006 | 0.50 | 27.3 | None | 1.056 | 5.99 MB | - / - (layer None) |
| TSin | True | 10.38 (1.12) | 1.69 (0.74) | 0.965 | 0.98 | True | 1.62 | 2.680 | 0.000 | 0.17 | 44.9 | 162 | 0.776 | 0.00 MB | - / - (layer None) |
| TSout | True | 10.80 (1.17) | 1.87 (0.82) | 0.939 | 0.91 | False | 3.22 | 2.744 | -0.001 | 0.25 | 44.9 | 162 | 0.778 | 0.40 MB | - / - (layer None) |
| DR2+TSout | True | 3.88 (0.42) | 1.87 (0.82) | 0.944 | 0.93 | False | 3.20 | 1.872 | -0.001 | 0.25 | 44.9 | 162 | 1.295 | 0.80 MB | 0.742 / 1.631 (layer 6) |
| RP1+TSout | True | 5.78 (0.63) | 1.33 (0.58) | 0.947 | 0.94 | False | 2.41 | 1.704 | 0.001 | 0.73 | 27.3 | None | 1.832 | 6.39 MB | - / - (layer None) |

## butterfly-feeding-slow-motion OT-1 (REF V1 P99 1.40; control: V1 reset 3.30, bind 0.95, Sink-less DINO 0.715 vs REF 0.888 band [0.838, 0.898], dE 0.70, terminal 31.3 dB, first >= 35 dB 66)

| cell | valid | V1 reset (x ctrl) | V1 bind (x ctrl) | Sink-less DINO | closed | in band | Sink-less dE | first-4 E | post-bind DINO diff | post-bind dE | terminal PSNR | first >= 35 | cost s (pref <= 0.3) | bytes | DR fidelity (median / worst rel) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DR1 | True | 1.61 (0.49) | 0.95 (1.00) | 0.723 | 0.05 | False | 0.81 | 1.729 | -0.012 | 0.17 | 31.3 | 66 | 0.259 | 0.20 MB | 1.031 / 1.882 (layer 17) |
| DR2 | True | 1.29 (0.39) | 0.95 (1.00) | 0.724 | 0.05 | False | 0.99 | 1.657 | -0.012 | 0.17 | 31.3 | 66 | 0.520 | 0.40 MB | 0.583 / 1.226 (layer 6) |
| RP1 | True | 2.31 (0.70) | 0.77 (0.81) | 0.727 | 0.07 | False | 0.94 | 1.689 | 0.004 | 1.07 | 26.4 | None | 1.059 | 5.99 MB | - / - (layer None) |
| TSin | True | 3.03 (0.92) | 0.72 (0.76) | 0.838 | 0.71 | True | 3.13 | 1.659 | -0.004 | 0.15 | 30.5 | 65 | 0.780 | 0.00 MB | - / - (layer None) |
| TSout | True | 3.00 (0.91) | 0.70 (0.74) | 0.831 | 0.67 | False | 2.06 | 1.674 | -0.006 | 0.18 | 30.7 | 65 | 0.776 | 0.40 MB | - / - (layer None) |
| DR2+TSout | True | 1.13 (0.34) | 0.70 (0.74) | 0.841 | 0.73 | True | 1.73 | 1.266 | -0.006 | 0.18 | 30.7 | 65 | 1.298 | 0.80 MB | 0.583 / 1.226 (layer 6) |
| RP1+TSout | True | 2.53 (0.77) | 0.66 (0.70) | 0.838 | 0.71 | True | 1.16 | 1.294 | 0.012 | 1.11 | 26.4 | None | 1.836 | 6.39 MB | - / - (layer None) |

## butterfly-feeding-slow-motion OT-L (REF V1 P99 1.40; control: V1 reset 1.97, bind 0.84, Sink-less DINO 0.719 vs REF 0.869 band [0.854, 0.893], dE 1.27, terminal 28.6 dB, first >= 35 dB None)

| cell | valid | V1 reset (x ctrl) | V1 bind (x ctrl) | Sink-less DINO | closed | in band | Sink-less dE | first-4 E | post-bind DINO diff | post-bind dE | terminal PSNR | first >= 35 | cost s (pref <= 0.3) | bytes | DR fidelity (median / worst rel) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DR1 | True | 0.83 (0.42) | 0.84 (1.00) | 0.722 | 0.01 | False | 1.27 | 1.475 | -0.041 | 0.46 | 28.6 | None | 0.259 | 0.20 MB | 1.067 / 1.609 (layer 17) |
| DR2 | True | 0.82 (0.42) | 0.84 (1.00) | 0.722 | 0.01 | False | 1.32 | 1.447 | -0.041 | 0.46 | 28.6 | None | 0.520 | 0.40 MB | 0.488 / 1.052 (layer 6) |
| RP1 | True | 1.19 (0.60) | 0.87 (1.03) | 0.727 | 0.05 | False | 1.83 | 1.471 | -0.026 | 0.20 | 23.7 | None | 1.056 | 5.99 MB | - / - (layer None) |
| TSin | True | 1.74 (0.88) | 0.63 (0.75) | 0.848 | 0.86 | False | 3.27 | 1.666 | -0.029 | 0.65 | 28.6 | None | 0.777 | 0.00 MB | - / - (layer None) |
| TSout | True | 1.70 (0.86) | 0.66 (0.78) | 0.843 | 0.83 | False | 1.50 | 1.661 | -0.028 | 0.50 | 28.7 | None | 0.775 | 0.40 MB | - / - (layer None) |
| DR2+TSout | True | 0.72 (0.37) | 0.66 (0.78) | 0.846 | 0.85 | False | 1.41 | 1.231 | -0.028 | 0.50 | 28.7 | None | 1.296 | 0.80 MB | 0.488 / 1.052 (layer 6) |
| RP1+TSout | True | 1.32 (0.67) | 1.11 (1.31) | 0.831 | 0.75 | False | 0.88 | 1.299 | -0.012 | 0.22 | 23.7 | None | 1.831 | 6.39 MB | - / - (layer None) |

## Verdicts (preregistered rules; every input and schedule must agree)

- VD2-H1 (DR-2 halves the reset jump and lands within REF P99 + 1): **NOT SUPPORTED** [False, True, True, True]
- VD2-H2 (RP-1 halves the reset jump and lowers first-4 warp error): **NOT SUPPORTED** [False, False, False, False]
- VD2-H3 (TS-out closes >= 50 % of the Sink-less content gap and lowers color drift; improvement only): **NOT SUPPORTED** [False, False, False, False]
- VD2-H4 (TS-out preserves identity better than TS-in): **NOT SUPPORTED** [False, False, False, False]
- VD2-H5 (temporary Sinks keep the exact bind and the post-bind stream): **NOT SUPPORTED** [False, False, False, False]
- VD2-H6 (costs within limits; preferred <= 0.3 s reported per cell): **NOT SUPPORTED** [False, False, False, False]
- Preservation (descriptive): see 'in band' per cell. A 50 % closure is not continuity preservation.
- DR-4: exploratory, excluded from every verdict.
