#!/bin/bash
# Phase 1: physical single handoff elves-01 (source) -> elves-02 (destination).
# Run on BOTH hosts (or from one host with SSH=1 to launch the peer). Same repo path and venv on both.
#
#   on elves-02 (destination; connects to the source):   ROLE=dest   tools/eval/run_single_handoff.sh
#   on elves-01 (source; listens):                        ROLE=source tools/eval/run_single_handoff.sh
#   or from elves-01 with passwordless ssh:               SSH=1 tools/eval/run_single_handoff.sh
#
# Env: SRC_HOST, DST_HOST, PORT, GPU, BWS ("250 500 1000 2500 5000 native"), POLICIES, REPS, POST, MSS, IFACE, EXTRA
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"
SRC_HOST="${SRC_HOST:-elves-01.be.ucsc.edu}"; DST_HOST="${DST_HOST:-elves-02.be.ucsc.edu}"
PORT="${PORT:-29777}"; GPU="${GPU:-0}"; MSS="${MSS:-1400}"; IFACE="${IFACE:-}"
BWS="${BWS:-250 500 1000 2500 5000 native}"
POLICIES="${POLICIES:-repeat ours full cold replay}"
REPS="${REPS:-3}"; M="${M:-30}"; POST="${POST:-80}"; EXTRA="${EXTRA:-}"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"
ROLE="${ROLE:-}"; SSH="${SSH:-0}"

SWEEP=""
for bw in $BWS; do for pol in $POLICIES; do
  [ "$pol" = "repeat" ] && [ "$bw" != "$(echo $BWS | awk '{print $1}')" ] && continue   # determinism check once
  SWEEP="${SWEEP:+$SWEEP,}$pol:$bw"
done; done
IFACE_ARG=""; [ -n "$IFACE" ] && IFACE_ARG="--iface $IFACE"
COMMON="--port $PORT --gpu_id $GPU --mss $MSS --sweep $SWEEP --reps $REPS --migration_chunk $M --post_chunks $POST --experiment single_handoff $IFACE_ARG $EXTRA"
LOGDIR="results/evaluation/single_handoff/_launch_logs"; mkdir -p "$LOGDIR"; STAMP="$(date +%Y%m%d-%H%M%S)"
echo "[handoff] sweep: $SWEEP (reps=$REPS, mss=$MSS)"

if [ "$SSH" = "1" ]; then
  # shellcheck disable=SC2086
  ssh -o BatchMode=yes "$DST_HOST" "cd $ROOT_DIR && $PY tools/proto_handoff.py --role dest --host $SRC_HOST $COMMON" > "$LOGDIR/dest_$STAMP.log" 2>&1 &
  DPID=$!
  sleep 5
  # shellcheck disable=SC2086
  $PY tools/proto_handoff.py --role source $COMMON 2>&1 | tee "$LOGDIR/source_$STAMP.log"
  wait $DPID
elif [ "$ROLE" = "source" ]; then
  # shellcheck disable=SC2086
  $PY tools/proto_handoff.py --role source $COMMON 2>&1 | tee "$LOGDIR/source_$STAMP.log"
elif [ "$ROLE" = "dest" ]; then
  # shellcheck disable=SC2086
  $PY tools/proto_handoff.py --role dest --host "$SRC_HOST" $COMMON 2>&1 | tee "$LOGDIR/dest_$STAMP.log"
else
  echo "set ROLE=source|dest or SSH=1"; exit 1
fi
[ "$ROLE" = "source" ] || "$PY" tools/eval/aggregate_single_handoff.py
