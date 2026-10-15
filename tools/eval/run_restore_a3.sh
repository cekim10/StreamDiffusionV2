#!/bin/bash
# Experiment A3: pre-positioning under shared-source contention (H5d interference, H5e value of wrongly placed
# fragments). 30 runs, ~40 min, on elves-01. Arrangement and model predictions: TOPOLOGY_PLAN.md G.1 (A3).
set -euo pipefail
cd "$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
R=tools/eval/run_restore_prepos.sh; export EXP="${EXP:-restore_prepos_a3}" REPS="${REPS:-3}" DRAWS=1 BUDGET=0.5 LOOKAHEAD=10
# H5d: others restoring from t0 while s0 pre-positions (top-1 -> B, correct), vs none
SESSIONS=4 OTHERS_START=0  DESTS=B PREPOS=none,top1 POLICY=reuse_aware_in $R
# H5e: others start at s0's move; wrongly placed 0.5 Sink at B, destination C
SESSIONS=4 OTHERS_START=10 DESTS=C PREPOS=none,top1 POLICY=reuse_aware_in $R
SESSIONS=1 OTHERS_START=0  DESTS=C PREPOS=none,top1 POLICY=reuse_aware_in $R
SESSIONS=4 OTHERS_START=10 DESTS=C PREPOS=none,top1 POLICY=reuse_fixed,reuse_aware_in HOLDER=125 $R
