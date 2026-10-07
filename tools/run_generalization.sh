#!/bin/bash
# Generalization grid for the temporal-semantics claims (immediate / durable / ephemeral + late binding).
# Runs the key configs only, one process per (video, seed, k), then aggregates.
#
#   tools/run_generalization.sh                       # default grid (see below), ~80 min on L40S
#   VIDEOS="original bird" SEEDS="0 1" STEPS="2" tools/run_generalization.sh
#   GPU=1 tools/run_generalization.sh
#
# Afterwards: python tools/aggregate_generalization.py --root results/state_migration/gen
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

GPU="${GPU:-0}"
OUT_ROOT="${OUT_ROOT:-results/state_migration/gen}"
VIDEOS="${VIDEOS:-original bird boxing}"
SEEDS="${SEEDS:-0}"
STEPS="${STEPS:-1 2 4}"
EXTRA_RUNS="${EXTRA_RUNS:-original:1:2}"   # video:seed:k triples run in addition to the grid
CONFIGS="${CONFIGS:-repeat,xfer_sink+meta+inflight,xfer_sink+meta,xfer_meta+inflight,drop_inflight,drop_kv_recent,drop_vae_all,ph_zero_8,ph_local_8,ph_localrefresh}"
M="${M:-30}"
POST="${POST:-40}"

prompt_for() {
  case "$1" in
    original) echo "examples/prompt.txt" ;;
    *) echo "examples/$1_prompt.txt" ;;
  esac
}

run_one() {
  local video="$1" seed="$2" k="$3"
  local out="$OUT_ROOT/${video}_s${seed}_k${k}"
  if [ -f "$out/ablation_summary.md" ]; then
    echo "[gen] skip $out (exists)"; return
  fi
  mkdir -p "$out"
  echo "============================ $video seed=$seed k=$k ============================"
  python tools/state_ablation.py --gpu_id "$GPU" --video_path "examples/$video.mp4" --prompt_file_path "$(prompt_for "$video")" \
    --seed "$seed" --step "$k" --migration_chunk "$M" --post_chunks "$POST" \
    --configs "$CONFIGS" --out_dir "$out" 2>&1 | tee "$out/run_log.txt"
}

for v in $VIDEOS; do for s in $SEEDS; do for k in $STEPS; do run_one "$v" "$s" "$k"; done; done; done
for t in $EXTRA_RUNS; do IFS=: read -r v s k <<< "$t"; run_one "$v" "$s" "$k"; done

python tools/aggregate_generalization.py --root "$OUT_ROOT"
