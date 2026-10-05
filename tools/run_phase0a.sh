#!/bin/bash
# Phase 0A runner: one fresh process per k, optional nvidia-smi dmon / dcgmi sampling.
#
# Usage (on the GPU server, inside the streamdiffusionv2 conda env, from the repo root):
#   tools/run_phase0a.sh                      # k=1 2 3 4, GPU 0, 10 warm-up + 100 measured chunks
#   STEPS="1 4" GPU=1 tools/run_phase0a.sh    # subset
#   SAVE_VIDEO=1 tools/run_phase0a.sh         # also keep decoded output per k for quality eval
#   MEMSNAP=1 tools/run_phase0a.sh            # dump a torch memory snapshot after warm-up (heavy)
#   EXTRA="--video_path examples/bird.mp4" tools/run_phase0a.sh
#
# Then:  python tools/phase0a_analyze.py --results_dir results/quality_elastic
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

STEPS="${STEPS:-1 2 3 4}"
GPU="${GPU:-0}"
OUT_DIR="${OUT_DIR:-results/quality_elastic}"
WARMUP="${WARMUP:-10}"
MEASURED="${MEASURED:-100}"
SEED="${SEED:-0}"
EXTRA="${EXTRA:-}"
SAVE_VIDEO="${SAVE_VIDEO:-0}"
MEMSNAP="${MEMSNAP:-0}"

mkdir -p "$OUT_DIR"

# Keep previous raw results instead of silently mixing runs.
if [ -f "$OUT_DIR/phase0a_raw.csv" ]; then
  STAMP="$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$OUT_DIR/previous_$STAMP"
  mv "$OUT_DIR"/phase0a_raw.csv "$OUT_DIR"/phase0a_static_k*.json "$OUT_DIR"/phase0a_dmon_k*.txt "$OUT_DIR"/phase0a_dcgm_k*.txt "$OUT_DIR/previous_$STAMP/" 2>/dev/null || true
  echo "[run_phase0a] moved previous results to $OUT_DIR/previous_$STAMP"
fi

{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host: $(hostname)"
  echo "commit: $(git rev-parse HEAD)"
  echo "git status:"; git status --short
  echo "python: $(python --version 2>&1)"
  nvidia-smi --query-gpu=index,name,driver_version,memory.total,clocks.max.sm,clocks.max.mem --format=csv || true
  python -c "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda)"
  python -c "import flash_attn; print('flash_attn', flash_attn.__version__)" 2>/dev/null || echo "flash_attn: not installed"
  echo "STEPS=$STEPS GPU=$GPU WARMUP=$WARMUP MEASURED=$MEASURED SEED=$SEED EXTRA=$EXTRA"
} | tee "$OUT_DIR/phase0a_environment.txt"

for K in $STEPS; do
  echo "============================ k=$K ============================"
  DMON_PID=""
  DCGM_PID=""
  if command -v nvidia-smi >/dev/null 2>&1; then
    # -s p: power/temp, u: utilization (sm%, mem% = memory-controller busy), m: fb memory; -o T: HH:MM:SS timestamps
    nvidia-smi dmon -i "$GPU" -s pum -d 1 -o T > "$OUT_DIR/phase0a_dmon_k$K.txt" 2>&1 &
    DMON_PID=$!
  fi
  if command -v dcgmi >/dev/null 2>&1; then
    # 1002 SM_ACTIVE, 1003 SM_OCCUPANCY, 1004 TENSOR_ACTIVE, 1005 DRAM_ACTIVE (HBM bandwidth utilization proxy)
    dcgmi dmon -i "$GPU" -e 1002,1003,1004,1005 -d 1000 > "$OUT_DIR/phase0a_dcgm_k$K.txt" 2>&1 &
    DCGM_PID=$!
  fi

  ARGS=(--step "$K" --gpu_id "$GPU" --out_dir "$OUT_DIR" --warmup_chunks "$WARMUP" --measured_chunks "$MEASURED" --seed "$SEED")
  [ "$SAVE_VIDEO" = "1" ] && ARGS+=(--save_video)
  [ "$MEMSNAP" = "1" ] && ARGS+=(--memory_snapshot)

  CMD="python tools/phase0a_quality_elastic.py ${ARGS[*]} $EXTRA"
  echo "$CMD" | tee -a "$OUT_DIR/phase0a_commands.txt"
  # shellcheck disable=SC2086
  python tools/phase0a_quality_elastic.py "${ARGS[@]}" $EXTRA 2>&1 | tee "$OUT_DIR/phase0a_log_k$K.txt"

  [ -n "$DMON_PID" ] && kill "$DMON_PID" 2>/dev/null || true
  [ -n "$DCGM_PID" ] && kill "$DCGM_PID" 2>/dev/null || true
  sleep 2
done

echo "[run_phase0a] done. Now run: python tools/phase0a_analyze.py --results_dir $OUT_DIR"
