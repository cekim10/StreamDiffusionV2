# Experiment A pilot checks (restore_prepos_pilot)

Valid runs 12/12; invalid: none; incomplete: none

## Per run: T_r (move -> all fragments verified at the destination) vs the fluid model at the run's caps

| prepos | dest | correct | T_r s | model s | d | verified at move (Sinks) | model verified | at chosen | at non-chosen | fwd by non-owner holders | post-move source | source total | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| none | B | True | 14.03 | 14.14 | -0.11 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| none | C | False | 14.00 | 14.14 | -0.14 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| none | D | False | 14.01 | 14.14 | -0.13 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| oracle | B | True | 3.99 | 4.14 | -0.15 | B:0.71 C:0.00 D:0.00 | B:0.72 C:0.00 D:0.00 | 0.71 | 0.00 | 0.00 | 0.29 | 1.00 | 1.00 |
| oracle | C | False | 4.00 | 4.14 | -0.14 | B:0.00 C:0.71 D:0.00 | B:0.00 C:0.72 D:0.00 | 0.71 | 0.00 | 0.00 | 0.29 | 1.00 | 1.00 |
| oracle | D | False | 4.00 | 4.14 | -0.14 | B:0.00 C:0.00 D:0.71 | B:0.00 C:0.00 D:0.72 | 0.71 | 0.00 | 0.00 | 0.29 | 1.00 | 1.00 |
| proportional | B | True | 8.00 | 8.18 | -0.18 | B:0.42 C:0.22 D:0.07 | B:0.43 C:0.22 D:0.07 | 0.43 | 0.29 | 0.29 | 0.28 | 1.00 | 1.29 |
| proportional | C | False | 10.95 | 11.12 | -0.17 | B:0.42 C:0.22 D:0.07 | B:0.43 C:0.22 D:0.07 | 0.22 | 0.50 | 0.50 | 0.29 | 1.00 | 1.50 |
| proportional | D | False | 12.98 | 13.12 | -0.14 | B:0.42 C:0.22 D:0.07 | B:0.43 C:0.22 D:0.07 | 0.07 | 0.64 | 0.65 | 0.28 | 1.00 | 1.65 |
| top1 | B | True | 3.99 | 4.14 | -0.15 | B:0.71 C:0.00 D:0.00 | B:0.72 C:0.00 D:0.00 | 0.71 | 0.00 | 0.00 | 0.29 | 1.00 | 1.00 |
| top1 | C | False | 14.01 | 14.14 | -0.13 | B:0.71 C:0.00 D:0.00 | B:0.72 C:0.00 D:0.00 | 0.00 | 0.71 | 0.72 | 0.29 | 1.00 | 1.72 |
| top1 | D | False | 14.02 | 14.14 | -0.12 | B:0.71 C:0.00 D:0.00 | B:0.72 C:0.00 D:0.00 | 0.00 | 0.71 | 0.72 | 0.29 | 1.00 | 1.72 |

## Model agreement (T_r and verified bytes at the move within 1 s / 0.05 Sink of the fluid model; with fast holders: non-chosen holders forward, source <= 1 Sink)

- all checks pass: GO
