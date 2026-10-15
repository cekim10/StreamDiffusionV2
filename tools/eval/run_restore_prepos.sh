#!/bin/bash
# Experiment A: prediction-aware pre-positioning (network level, no GPU). Session s0 executes at source A; during the
# lookahead L the allocation policy sends Sink fragments to candidates B, C, D; at L the session moves to the true
# destination and restores with the progress-preserving policy. Other sessions (N > 1) start at OTHERS_START seconds.
#   tools/eval/run_restore_prepos.sh                                   # A-pilot: 4 policies x dests B,C,D (12 runs)
#   tools/eval/run_restore_a3.sh                                       # A3 grid (see that script)
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
EXP="${EXP:-restore_prepos_pilot}"; SESSIONS="${SESSIONS:-1}"; POLICY="${POLICY:-reuse_aware_in}"
PREPOS="${PREPOS:-none,oracle,top1,proportional}"; PROBS="${PROBS:-0.6,0.3,0.1}"; LOOKAHEAD="${LOOKAHEAD:-10}"; BUDGET="${BUDGET:-1}"
DESTS="${DESTS-B,C,D}"; DRAWS="${DRAWS:-3}"; REPS="${REPS:-1}"; OTHERS_START="${OTHERS_START:-0}"; HOLDER="${HOLDER:-0}"; EXTRA="${EXTRA:-}"
LOG="results/evaluation/$EXP/_launch_logs"; mkdir -p "$LOG"; STAMP="$(date +%Y%m%d-%H%M%S)"
# shellcheck disable=SC2086
"$PY" tools/eval/restore_orchestrate.py --launch --experiment "$EXP" --sessions "$SESSIONS" --policies "$POLICY" --moves 1 --rhos 2 --reps "$REPS" \
    --prepos "$PREPOS" --probs "$PROBS" --lookahead "$LOOKAHEAD" --budget "$BUDGET" --dests "$DESTS" --draws "$DRAWS" \
    --others_start "$OTHERS_START" --holder_mbps "$HOLDER" $EXTRA 2>&1 | tee -a "$LOG/orch_$STAMP.log"
