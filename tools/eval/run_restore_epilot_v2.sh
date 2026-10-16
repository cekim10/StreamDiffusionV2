#!/bin/bash
# Experiment E pilot v2: re-planner with corrected hysteresis (idle estimates kept; dT > C_switch + max(2 s, 0.1 ETA)).
# Limited validation only; the v1 pilot (restore_epilot) is kept unchanged. ALL FOUR HOSTS on the same commit.
# A1 collapse, A0 no-collapse control, A2 collapse then recovery 5 s later; B source-share change. 21 runs, ~25 min.
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
EXP="${EXP:-restore_epilot_v2}"; REPS="${REPS:-3}"; LOG="results/evaluation/$EXP/_launch_logs"; mkdir -p "$LOG"; STAMP="$(date +%Y%m%d-%H%M%S)"
O="$PY tools/eval/restore_orchestrate.py --launch --experiment $EXP --sessions 1 --moves 2 --rhos 2 --reps $REPS"
$O --policies reuse_dyn --cap_events "D>=0.5:C:out=62.5" 2>&1 | tee -a "$LOG/orch_$STAMP.log"                                   # A1 collapse
$O --policies reuse_dyn,reuse_aware_in 2>&1 | tee -a "$LOG/orch_$STAMP.log"                                                      # A0 control
$O --policies reuse_dyn,reuse_aware_in --cap_events "D>=0.5:C:out=62.5;t=26:C:out=1000" 2>&1 | tee -a "$LOG/orch_$STAMP.log"    # A2 recovery
R=tools/eval/run_restore_prepos.sh
EXP="$EXP" REPS="$REPS" DRAWS=1 BUDGET=0.5 LOOKAHEAD=10 SESSIONS=4 OTHERS_START=10 DESTS=C PREPOS=top1 POLICY=reuse_aware_in,reuse_dyn HOLDER=250 $R   # B
