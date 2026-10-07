#!/bin/bash
# Repeated mobility with per-segment sink routing (restart / relay / relay_pipe / split / direct).
#   tools/run_mobility.sh                                   # default: A->B->C->D at T_m=2 (all policies) + A->B->C at T_m 24/32 (regime boundary)
#   SWEEP="split:4:2,restart:4:2" tools/run_mobility.sh     # explicit policy:T_m:hops list
#   TMS="2 4" HOPS="3" POLICIES="split direct" BW=2000 tools/run_mobility.sh
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
SRC_GPU="${SRC_GPU:-0}"; DST_GPU="${DST_GPU:-1}"; PORT="${PORT:-29778}"
OUT_DIR="${OUT_DIR:-results/state_migration/mobility}"
POLICIES="${POLICIES:-restart relay relay_pipe split direct}"
TMS="${TMS:-2}"
HOPS="${HOPS:-3}"
BW="${BW:-1000}"
M="${M:-30}"; POST="${POST:-130}"; EXTRA="${EXTRA:-}"
if [ -z "${SWEEP:-}" ]; then
  SWEEP=""
  for pol in $POLICIES; do for tm in $TMS; do for h in $HOPS; do SWEEP="${SWEEP:+$SWEEP,}$pol:$tm:$h"; done; done; done
  # regime boundary: A->B->C with T_m beyond the sink time (rho < 1) for the three single-destination policies
  for tm in ${BOUNDARY_TMS:-24 32}; do for pol in restart relay direct; do SWEEP="$SWEEP,$pol:$tm:2"; done; done
fi
echo "[mobility] sweep: $SWEEP @ $BW Mbps"
mkdir -p "$OUT_DIR"
# shellcheck disable=SC2086
python tools/proto_mobility.py --role dest --gpu_id "$DST_GPU" --port "$PORT" --sweep "$SWEEP" --bw_mbps "$BW" \
  --migration_chunk "$M" --post_chunks "$POST" --out_dir "$OUT_DIR" $EXTRA 2>&1 | tee "$OUT_DIR/dest_log.txt" &
DEST_PID=$!
sleep 2
# shellcheck disable=SC2086
python tools/proto_mobility.py --role source --gpu_id "$SRC_GPU" --port "$PORT" --sweep "$SWEEP" --bw_mbps "$BW" \
  --migration_chunk "$M" --post_chunks "$POST" $EXTRA 2>&1 | tee "$OUT_DIR/source_log.txt"
wait $DEST_PID
python tools/mobility_aggregate.py --results "$OUT_DIR/mobility_results.json"
