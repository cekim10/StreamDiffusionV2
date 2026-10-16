#!/bin/bash
# Experiment E pilot (E.4): event-driven re-planning vs aware-at-moves. Network level, no GPU; ALL FOUR HOSTS on the same
# commit. Scenario A: single session A->B->C->D (rho 2, two moves); when D holds 50 % of the Sink, C's egress drops from
# 1 Gbps to 62.5 Mbps. Scenario B: N = 4, holder egress 250 Mbps, 0.5 Sink pre-positioned at B, destination C, others
# start at s0's move (source share grows as they finish). 3 reps. ~25 runs, ~40 min.
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
EXP="${EXP:-restore_epilot}"; REPS="${REPS:-3}"; LOG="results/evaluation/$EXP/_launch_logs"; mkdir -p "$LOG"; STAMP="$(date +%Y%m%d-%H%M%S)"
# A: forwarder collapse
"$PY" tools/eval/restore_orchestrate.py --launch --experiment "$EXP" --sessions 1 --policies restart,reuse_fixed,reuse_aware_in,reuse_dyn --moves 2 --rhos 2 --reps "$REPS" \
    --cap_events "D>=0.5:C:out=62.5" 2>&1 | tee -a "$LOG/orch_$STAMP.log"
# B: source share change at the crossover (pre-positioning arrangement of A3 / the holder diagnostic)
R=tools/eval/run_restore_prepos.sh
EXP="$EXP" REPS="$REPS" DRAWS=1 BUDGET=0.5 LOOKAHEAD=10 SESSIONS=4 OTHERS_START=10 DESTS=C PREPOS=top1 POLICY=reuse_fixed,reuse_aware_in,reuse_dyn HOLDER=250 $R
