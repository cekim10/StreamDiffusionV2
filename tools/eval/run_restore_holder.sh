#!/bin/bash
# Experiment 3 Step 2: heterogeneous holder bandwidth (network level, no GPU). N sessions share source A (1 Gbps egress);
# every edge's egress (what previous holders forward with) is capped at B_h. One move per session, then it stays.
# Run on elves-01; the agents on all four hosts launch restore nodes (ports 29831/29832).
#   tools/eval/run_restore_holder.sh                       # full grid: N 1,2,4 x B_h 62.5..1000 Mbps x 4 policies x 3 reps (180 runs)
#   SESSIONS=2 HOLDERS=125 REPS=1 tools/eval/run_restore_holder.sh      # one quick configuration
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
SESSIONS="${SESSIONS:-1,2,4}"; POLICIES="${POLICIES:-restart,reuse_fixed,reuse_adaptive,reuse_aware}"; HOLDERS="${HOLDERS:-62.5,125,250,500,1000}"
RHOS="${RHOS:-2}"; REPS="${REPS:-3}"; EXTRA="${EXTRA:-}"; EXP="${EXP:-restore_holder}"
LOG="results/evaluation/$EXP/_launch_logs"; mkdir -p "$LOG"; STAMP="$(date +%Y%m%d-%H%M%S)"
for BH in ${HOLDERS//,/ }; do
  # shellcheck disable=SC2086
  "$PY" tools/eval/restore_orchestrate.py --launch --experiment "$EXP" --sessions "$SESSIONS" --policies "$POLICIES" --moves 1 --rhos "$RHOS" \
      --reps "$REPS" --holder_mbps "$BH" $EXTRA 2>&1 | tee -a "$LOG/orch_$STAMP.log"
done
