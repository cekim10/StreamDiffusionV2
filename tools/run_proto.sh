#!/bin/bash
# Two-GPU late-binding handoff prototype: launches destination (GPU 1) and source (GPU 0) processes that
# talk over a TCP socket with a sender-side bandwidth limit, sweeping policies x bandwidths.
#
#   tools/run_proto.sh                                    # default sweep below
#   BWS="500 1000 5000" POLICIES="ours full" tools/run_proto.sh
#   SRC_GPU=0 DST_GPU=1 POST=60 tools/run_proto.sh
#
# Then: python tools/proto_aggregate.py --results results/state_migration/proto/proto_results.json
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

SRC_GPU="${SRC_GPU:-0}"
DST_GPU="${DST_GPU:-1}"
PORT="${PORT:-29777}"
OUT_DIR="${OUT_DIR:-results/state_migration/proto}"
POLICIES="${POLICIES:-ours cold replay full}"
BWS="${BWS:-500 1000 2000 5000 10000}"   # Mbps
M="${M:-30}"
POST="${POST:-60}"
EXTRA="${EXTRA:-}"

SWEEP=""
for bw in $BWS; do for pol in $POLICIES; do
  # full transfer below 1 Gbps takes minutes per point; keep it but warn
  SWEEP="${SWEEP:+$SWEEP,}$pol:$bw"
done; done
echo "[proto] sweep: $SWEEP"
mkdir -p "$OUT_DIR"

# shellcheck disable=SC2086
python tools/proto_handoff.py --role dest --gpu_id "$DST_GPU" --port "$PORT" --sweep "$SWEEP" \
  --migration_chunk "$M" --post_chunks "$POST" --out_dir "$OUT_DIR" $EXTRA 2>&1 | tee "$OUT_DIR/dest_log.txt" &
DEST_PID=$!
sleep 2
# shellcheck disable=SC2086
python tools/proto_handoff.py --role source --gpu_id "$SRC_GPU" --port "$PORT" --sweep "$SWEEP" \
  --migration_chunk "$M" --post_chunks "$POST" $EXTRA 2>&1 | tee "$OUT_DIR/source_log.txt"
wait $DEST_PID
python tools/proto_aggregate.py --results "$OUT_DIR/proto_results.json"
