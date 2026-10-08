#!/bin/bash
# Phase 3: physical repeated mobility A(elves-01) -> B(elves-02) -> C(elves-03) -> D(elves-04).
# Run from elves-01 (the only host that commits). Node processes are started on every host through the
# per-host agents (tools/eval/start_agent.sh must be running on all four hosts, each from a venv with torch).
#
#   tools/eval/run_mobility_phys.sh ts                      # Step 1: measure T_s (A->B, no moves) at BWS
#   TS=14.2 tools/eval/run_mobility_phys.sh shakedown       # Step 6: rho=2 (RHOS), every policy once
#   TS=14.2 REPS=3 tools/eval/run_mobility_phys.sh sweep    # Fig. 8 sweep (after shakedown approval)
#
# Env: BW (Mbps, 0 = native; default 1000), BWS ("1000 2500 5000 native" for ts), RHOS, POLICIES (comma list or all),
#      REPS, GPUS ("A=0,B=0,C=0,D=0"), FRAG_MB (4), POST (baseline window, chunks), TAIL (calls after rejoin), EXTRA
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
MODE="${1:-}"; [ -n "$MODE" ] || { echo "usage: $0 ts|shakedown|sweep"; exit 1; }
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
BW="${BW:-1000}"; BWS="${BWS:-1000 2500 5000 native}"; RHOS="${RHOS:-2}"; POLICIES="${POLICIES:-all}"; REPS="${REPS:-1}"
GPUS="${GPUS:-A=0,B=0,C=0,D=0}"; FRAG_MB="${FRAG_MB:-4}"; POST="${POST:-220}"; TAIL="${TAIL:-12}"; EXTRA="${EXTRA:-}"; MSS="${MSS:-1400}"
LOGDIR="results/evaluation/repeated_mobility/_launch_logs"; mkdir -p "$LOGDIR"; STAMP="$(date +%Y%m%d-%H%M%S)"
COMMON="--launch --gpus $GPUS --frag_bytes $((FRAG_MB << 20)) --post_chunks $POST --tail_calls $TAIL --mss $MSS $EXTRA"
case "$MODE" in
  ts)
    # shellcheck disable=SC2086
    $PY tools/eval/mobility_orchestrate.py --measure_ts --bws "$BWS" --reps "$REPS" --hops 1 $COMMON 2>&1 | tee "$LOGDIR/orch_ts_$STAMP.log" ;;
  shakedown)
    [ -n "${TS:-}" ] || { echo "set TS=<measured T_s seconds at BW=$BW> (from: $0 ts)"; exit 1; }
    # shellcheck disable=SC2086
    $PY tools/eval/mobility_orchestrate.py --bw "$BW" --ts "$TS" --rhos "$RHOS" --policies "$POLICIES" --reps 1 $COMMON 2>&1 | tee "$LOGDIR/orch_shakedown_$STAMP.log"
    $PY tools/eval/aggregate_mobility.py ;;
  sweep)
    [ -n "${TS:-}" ] || { echo "set TS=<measured T_s seconds at BW=$BW>"; exit 1; }
    RHOS="${RHOS_SWEEP:-0.5,1,2,4,8}"
    # shellcheck disable=SC2086
    $PY tools/eval/mobility_orchestrate.py --bw "$BW" --ts "$TS" --rhos "$RHOS" --policies "$POLICIES" --reps "$REPS" $COMMON 2>&1 | tee "$LOGDIR/orch_sweep_$STAMP.log"
    $PY tools/eval/aggregate_mobility.py ;;
  *) echo "unknown mode $MODE"; exit 1 ;;
esac
