#!/bin/bash
# A -> B -> C repeated mobility with single-destination sink policies (restart / relay / direct).
#   tools/run_mobility.sh                       # 3 policies x T_m {1,2,4,8,16} s at 1 Gbps
#   TMS="2 8" POLICIES="restart direct" BW=2000 tools/run_mobility.sh
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
SRC_GPU="${SRC_GPU:-0}"; DST_GPU="${DST_GPU:-1}"; PORT="${PORT:-29778}"
OUT_DIR="${OUT_DIR:-results/state_migration/mobility}"
POLICIES="${POLICIES:-restart relay direct}"
TMS="${TMS:-1 2 4 8 16}"
BW="${BW:-1000}"
M="${M:-30}"; POST="${POST:-90}"; EXTRA="${EXTRA:-}"
SWEEP=""
for pol in $POLICIES; do for tm in $TMS; do SWEEP="${SWEEP:+$SWEEP,}$pol:$tm"; done; done
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
