#!/bin/bash
# Experiment B: one Sink from source A to destinations B, C, D under fixed plans (star, pipelined line, tree,
# disjoint-fragment multipath) and the backlog/ingress-aware assignment. Network level, no GPU. Run on elves-01;
# ALL FOUR HOSTS must be on the same commit (restore_node.py changed for FLOW_ADD; the run records each node's commit).
#   tools/eval/run_restore_dissem.sh                       # B-pilot: 5 plans, uniform 1 Gbps, 1 rep
#   SOURCE=250 REPS=3 EXP=restore_dissem tools/eval/run_restore_dissem.sh
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
EXP="${EXP:-restore_dissem_pilot}"; PLANS="${PLANS:-star,line,tree,multipath,aware}"; REPS="${REPS:-1}"
SOURCE="${SOURCE:-0}"; FWD="${FWD:-0}"; IN="${IN:-0}"; EXTRA="${EXTRA:-}"
LOG="results/evaluation/$EXP/_launch_logs"; mkdir -p "$LOG"; STAMP="$(date +%Y%m%d-%H%M%S)"
# shellcheck disable=SC2086
"$PY" tools/eval/restore_orchestrate.py --launch --experiment "$EXP" --dissem "$PLANS" --reps "$REPS" \
    --source_mbps "$SOURCE" --holder_mbps "$FWD" --in_mbps "$IN" $EXTRA 2>&1 | tee -a "$LOG/orch_$STAMP.log"
