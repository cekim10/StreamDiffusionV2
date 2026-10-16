# Shared-planner loopback regression

Pre-refactor loopback runs (`_dryrun_*`) vs the same configurations with the shared planner (`_regress_planner/`).

| group | configuration | T (old -> new, s) | verdict |
|---|---|---|---|
| reg | `policy=restart_N=1_moves=1_rho=2_bh=25_rep=1` | 5.48 -> 5.48 | PASS |
| reg | `policy=reuse_aware_in_N=1_moves=1_rho=2_bh=25_rep=1` | 5.42 -> 5.43 | PASS |
| reg | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=top1_L=3.8_b=1_d=C_k=0_rep=1` | 5.43 -> 5.43 | PASS |
| reg | `policy=reuse_aware_in_N=4_moves=1_rho=2_pp=top1_L=3.8_b=0.5_d=C_k=0_os=3.8_rep=1` | 11.20 -> 11.19 | PASS |
| reg | `policy=reuse_fixed_N=1_moves=1_rho=2_bh=25_rep=1` | 10.77 -> 10.78 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=none_L=3.8_b=1_d=B_k=0_rep=1` | 5.47 -> 5.46 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=none_L=3.8_b=1_d=C_k=1_rep=1` | 5.45 -> 5.46 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=none_L=3.8_b=1_d=D_k=2_rep=1` | 5.46 -> 5.46 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=oracle_L=3.8_b=1_d=B_k=0_rep=1` | 1.72 -> 1.71 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=oracle_L=3.8_b=1_d=C_k=1_rep=1` | 1.71 -> 1.71 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=oracle_L=3.8_b=1_d=D_k=2_rep=1` | 1.71 -> 1.71 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=proportional_L=3.8_b=1_d=B_k=0_rep=1` | 3.05 -> 3.05 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=proportional_L=3.8_b=1_d=C_k=1_rep=1` | 4.40 -> 4.40 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=proportional_L=3.8_b=1_d=D_k=2_rep=1` | 5.07 -> 5.08 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=top1_L=3.8_b=1_d=B_k=0_rep=1` | 1.71 -> 1.71 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=top1_L=3.8_b=1_d=C_k=1_rep=1` | 5.44 -> 5.43 | PASS |
| prepos | `policy=reuse_aware_in_N=1_moves=1_rho=2_pp=top1_L=3.8_b=1_d=D_k=2_rep=1` | 5.42 -> 5.44 | PASS |
| a3 | `policy=reuse_aware_in_N=4_moves=1_rho=2_pp=none_L=3.8_b=0.5_d=C_k=0_os=3.8_rep=1` | 21.56 -> 21.56 | PASS |
| a3 | `policy=reuse_aware_in_N=4_moves=1_rho=2_pp=top1_L=3.8_b=0.5_d=C_k=0_os=3.8_rep=1` | 11.19 -> 11.21 | PASS |
| dissem | `plan=aware_bs=100_bf=100_bin=100_rep=1` | 6.51 -> 6.54 | PASS |
| dissem | `plan=line_bs=100_bf=100_bin=100_rep=1` | 6.01 -> 6.07 | PASS |
| dissem | `plan=multipath_bs=100_bf=100_bin=100_rep=1` | 6.45 -> 6.46 | PASS |
| dissem | `plan=star_bs=100_bf=100_bin=100_rep=1` | 16.18 -> 16.24 | PASS |
| dissem | `plan=tree_bs=100_bf=100_bin=100_rep=1` | 11.04 -> 11.05 | PASS |
| e2 | `policy=reuse_aware_in_N=1_moves=2_rho=2_ev=Dge0.5Cout12.5+t36Cout100_rep=1` | 21.60 -> 21.70 | PASS |
| e2 | `policy=reuse_aware_in_N=1_moves=2_rho=2_ev=Dge0.5Cout12.5_rep=1` | 46.07 -> 46.15 | PASS |
| e2 | `policy=reuse_aware_in_N=1_moves=2_rho=2_rep=1` | 21.60 -> 21.68 | PASS |
| e2 | `policy=reuse_dyn_N=1_moves=2_rho=2_ev=Dge0.5Cout12.5+t36Cout100_rep=1` | 21.92 -> 21.67 | DIFF: link B->D 20 vs 24 fragments; link C->D 21 vs 17 fragments; re-plans 3 ['B', 'C', 'A'] vs 1 ['C'] |
| e2 | `policy=reuse_dyn_N=1_moves=2_rho=2_ev=Dge0.5Cout12.5_rep=1` | 27.26 -> 27.31 | PASS |
| e2 | `policy=reuse_dyn_N=1_moves=2_rho=2_rep=1` | 21.59 -> 22.35 | DIFF: bytes 1.00/2.00 vs 1.14/2.03; duplicates 8388608; link A->D 16 vs 25 fragments; link C->D 24 vs 17 fragments; re-plans 0 [] vs 2 ['C', 'A'] |
| fe | `policy=fixed_butterfly_N=1_moves=2_rho=2_rep=1` | 43.12 -> 43.05 | PASS |
| fe | `policy=fixed_butterfly_N=1_moves=3_rho=2_rep=1` | 5.41 -> 5.44 | PASS |
| fe | `policy=fixed_line_N=1_moves=2_rho=2_rep=1` | 10.88 -> 10.90 | PASS |
| fe | `policy=fixed_line_N=1_moves=3_rho=2_rep=1` | 5.48 -> 5.54 | PASS |
| fe | `policy=fixed_tree_N=1_moves=2_rho=2_rep=1` | 43.13 -> 43.04 | PASS |
| fe | `policy=fixed_tree_N=1_moves=3_rho=2_rep=1` | 5.50 -> 5.54 | PASS |
| fe | `policy=pp_star_N=1_moves=2_rho=2_rep=1` | 11.08 -> 11.27 | PASS |
| fe | `policy=pp_star_N=1_moves=3_rho=2_rep=1` | 5.78 -> 5.58 | PASS |
| fe | `policy=restart_N=1_moves=3_rho=2_rep=1` | 11.20 -> 11.11 | PASS |
| fe | `policy=reuse_aware_in_N=1_moves=2_rho=2_rep=1` | 10.88 -> 10.82 | PASS |
| fe | `policy=reuse_aware_in_N=1_moves=3_rho=2_rep=1` | 5.40 -> 5.43 | PASS |
| fe | `policy=reuse_dyn_N=1_moves=2_rho=2_rep=1` | 10.89 -> 10.83 | PASS |
| fe | `policy=reuse_dyn_N=1_moves=3_rho=2_rep=1` | 5.78 -> 5.43 | PASS |

43 configurations compared; 2 with differences.
