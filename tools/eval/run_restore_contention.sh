#!/bin/bash
# Experiment 3 Scenario B: N sessions restore their Sinks through one shared source A (network level, no GPU).
# Run on elves-01; the agents on all four hosts launch restore nodes (ports 29831/29832). GPUs are not used.
#   tools/eval/run_restore_contention.sh                 # full grid: N 1,2,4,8 x 3 policies x moves {1, continuous} x 3 reps
#   SESSIONS=4 MOVES=1 REPS=1 tools/eval/run_restore_contention.sh      # one quick configuration
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
SESSIONS="${SESSIONS:-1,2,4,8}"; POLICIES="${POLICIES:-restart,reuse_fixed,reuse_adaptive}"; MOVES="${MOVES:-1,0}"
RHOS="${RHOS:-2}"; REPS="${REPS:-3}"; CAPS="${CAPS:-}"; EXTRA="${EXTRA:-}"
LOG="results/evaluation/restore_contention/_launch_logs"; mkdir -p "$LOG"; STAMP="$(date +%Y%m%d-%H%M%S)"
# shellcheck disable=SC2086
"$PY" tools/eval/restore_orchestrate.py --launch --sessions "$SESSIONS" --policies "$POLICIES" --moves "$MOVES" --rhos "$RHOS" --reps "$REPS" --caps "$CAPS" $EXTRA 2>&1 | tee "$LOG/orch_$STAMP.log"
