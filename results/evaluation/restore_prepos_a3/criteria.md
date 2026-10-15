# Experiment A pilot checks (restore_prepos_a3)

Valid runs 30/31; invalid: ['policy=reuse_fixed_N=4_moves=1_rho=2_bh=125_pp=none_L=10_b=0.5_d=C_k=0_os=10_rep=3_20261015-160506']; incomplete: none

## Per run: T_r (move -> all fragments verified at the destination) vs the fluid model at the run's caps

| prepos | dest | correct | T_r s | model s | d | verified at move (Sinks) | model verified | at chosen | at non-chosen | fwd by non-owner holders | post-move source | source total | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| none | C | False | 14.03 | 14.14 | -0.11 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| none | C | False | 14.01 | 14.14 | -0.13 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| none | C | False | 13.99 | 14.14 | -0.15 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| top1 | C | False | 13.98 | 14.14 | -0.16 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 1.50 |
| top1 | C | False | 13.99 | 14.14 | -0.15 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 1.50 |
| top1 | C | False | 13.98 | 14.14 | -0.16 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 1.50 |
| none | C | False | 55.44 | 55.60 | -0.16 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| none | C | False | 55.43 | 55.60 | -0.17 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| none | C | False | 55.46 | 55.60 | -0.14 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| top1 | C | False | 48.61 | 48.76 | -0.15 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.12 | 0.88 | 1.09 | 1.27 |
| top1 | C | False | 48.64 | 48.76 | -0.12 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.12 | 0.88 | 1.09 | 1.27 |
| top1 | C | False | 48.59 | 48.76 | -0.17 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.12 | 0.88 | 1.09 | 1.27 |
| none | B | True | 45.47 | 45.66 | -0.19 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.19 |
| none | B | True | 45.47 | 45.66 | -0.19 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.19 |
| none | B | True | 45.67 | 45.66 | +0.01 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.19 |
| none | C | False | 55.44 | 55.60 | -0.16 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| none | C | False | 55.43 | 55.60 | -0.17 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| none | C | False | 55.43 | 55.60 | -0.17 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| top1 | B | True | 32.14 | 32.38 | -0.24 | B:0.18 C:0.00 D:0.00 | B:0.18 C:0.00 D:0.00 | 0.18 | 0.00 | 0.00 | 0.82 | 1.00 | 1.14 |
| top1 | B | True | 32.13 | 32.38 | -0.25 | B:0.18 C:0.00 D:0.00 | B:0.18 C:0.00 D:0.00 | 0.18 | 0.00 | 0.00 | 0.82 | 1.00 | 1.14 |
| top1 | B | True | 32.13 | 32.38 | -0.25 | B:0.18 C:0.00 D:0.00 | B:0.18 C:0.00 D:0.00 | 0.18 | 0.00 | 0.00 | 0.82 | 1.00 | 1.14 |
| top1 | C | False | 27.76 | 27.96 | -0.20 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 1.27 |
| top1 | C | False | 27.76 | 27.96 | -0.20 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 1.27 |
| top1 | C | False | 27.75 | 27.96 | -0.21 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 1.27 |
| none | C | False | 55.43 | 55.60 | -0.17 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| none | C | False | 55.44 | 55.60 | -0.16 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| none | C | False | 55.50 | 55.60 | -0.10 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| none | C | False | 55.48 | 55.60 | -0.12 | B:0.00 C:0.00 D:0.00 | B:0.00 C:0.00 D:0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.14 |
| top1 | C | False | 79.89 | 80.04 | -0.15 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 1.27 |
| top1 | C | False | 79.88 | 80.04 | -0.16 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 1.27 |
| top1 | C | False | 79.89 | 80.04 | -0.15 | B:0.50 C:0.00 D:0.00 | B:0.50 C:0.00 D:0.00 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 1.27 |

## Model agreement (T_r and verified bytes at the move within 1 s / 0.05 Sink of the fluid model; with fast holders: non-chosen holders forward, source <= 1 Sink)

- all checks pass: GO

## A3: frozen criteria (medians; model value in brackets)

| clause | configuration | measured | model | threshold | verdict |
|---|---|---|---|---|---|
| H5d interference | N=4, others at t0: others' makespan top-1(0.5) - none | 3.3 | 3.3 | >= 3.5 s | FAIL |
| H5d idle source | N=4, others at L: others' makespan top-1(0.5) - none | -6.9 | -6.9 | < 1 s | PASS |
| H5e shared source | N=4, 1 Gbps holders, others at L: T_r none - top-1 -> C (wrong) | 27.7 | 27.6 | >= 0.5 T_s = 7.0 s | PASS |
| H5e ingress-bound | N=1: T_r none - top-1 -> C (wrong) | 0.0 | 0.0 | |d| < 1 s | PASS |
| H5e slow holder, reuse_fixed | N=4, 125 Mbps holders, others at L: T_r none - top-1 -> C (wrong) | -24.5 | -24.4 | < 1 s | PASS |
| H5e slow holder, reuse_aware_in | N=4, 125 Mbps holders, others at L: T_r none - top-1 -> C (wrong) | 6.8 | 6.8 | >= 0.5 T_s = 7.0 s | FAIL |
