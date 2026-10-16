#!/bin/bash
# Full Experiment E (frozen H8a-c): seven policies under execution mobility. Network level, no GPU. ALL FOUR HOSTS on the
# same commit. Conditions: (1) slow-B (B egress 125 Mbps), single session, two moves B->C->D; (2) shared source N = 4,
# two moves each; (3) C degradation (C egress -> 62.5 Mbps when D holds 50 %), single session, two moves;
# (4) revisit A->B->C->D->B, single session, three moves. 7 x 4 x 3 reps = 84 runs, ~2 h.
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
EXP="${EXP:-restore_fulle}"; REPS="${REPS:-3}"; LOG="results/evaluation/$EXP/_launch_logs"; mkdir -p "$LOG"; STAMP="$(date +%Y%m%d-%H%M%S)"
POL="${POLICIES:-restart,pp_star,fixed_line,fixed_tree,fixed_butterfly,reuse_aware_in,reuse_dyn}"
O="$PY tools/eval/restore_orchestrate.py --launch --experiment $EXP --policies $POL --rhos 2 --reps $REPS"
$O --sessions 1 --moves 2 --caps "B:out=125" 2>&1 | tee -a "$LOG/orch_$STAMP.log"                              # (1) slow-B
$O --sessions 4 --moves 2 2>&1 | tee -a "$LOG/orch_$STAMP.log"                                               # (2) shared source
$O --sessions 1 --moves 2 --cap_events "D>=0.5:C:out=62.5" 2>&1 | tee -a "$LOG/orch_$STAMP.log"            # (3) C degradation
$O --sessions 1 --moves 3 2>&1 | tee -a "$LOG/orch_$STAMP.log"                                               # (4) revisit
