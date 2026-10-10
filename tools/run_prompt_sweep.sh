#!/bin/bash
# Prompt/clip sweep for Fig. 3 and its appendix: does the state asymmetry reproduce across content, and which
# reproducing case shows it most clearly? Selection rule is fixed in tools/aggregate_prompt_sweep.py BEFORE results exist.
#
# Each run: one (clip, seed, k) with the clip's own prompt (examples/<clip>_prompt.txt; dog = examples/prompt.txt),
# uninterrupted baseline + two conditions, uncompressed per-frame PSNR in ablation_raw.csv, frames saved as MP4 for figures:
#   ph_localrefresh          = no Sink KV (durable state lost)
#   xfer_sink+meta+inflight  = no recent KV + VAE caches (ephemeral state lost; Sink, metadata, in-flight rows kept)
#
#   tools/run_prompt_sweep.sh                                  # default: 4 clips x seeds 0,1,2 x k=2, 80 post-migration chunks
#   CLIPS="train original" SEEDS="0" tools/run_prompt_sweep.sh
#   GPU=1 tools/run_prompt_sweep.sh
# New clips: put examples/<name>.mp4 and examples/<name>_prompt.txt in place and add <name> to CLIPS.
# Afterwards (any host): python tools/aggregate_prompt_sweep.py
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
GPU="${GPU:-0}"
OUT_ROOT="${OUT_ROOT:-results/state_migration/prompt_sweep}"
CLIPS="${CLIPS:-original train boxing bird}"
SEEDS="${SEEDS:-0 1 2}"
K="${K:-2}"
M="${M:-30}"
POST="${POST:-80}"
CONFIGS="${CONFIGS:-ph_localrefresh,xfer_sink+meta+inflight}"

prompt_for() { if [ "$1" = "original" ]; then echo "examples/prompt.txt"; else echo "examples/$1_prompt.txt"; fi; }

for clip in $CLIPS; do
  [ -f "examples/$clip.mp4" ] || { echo "[sweep] missing examples/$clip.mp4"; exit 1; }
  [ -f "$(prompt_for "$clip")" ] || { echo "[sweep] missing $(prompt_for "$clip")"; exit 1; }
  for seed in $SEEDS; do
    out="$OUT_ROOT/${clip}_s${seed}_k${K}"
    if [ -f "$out/ablation_summary.md" ]; then echo "[sweep] skip $out (exists)"; continue; fi
    mkdir -p "$out"
    echo "==================== $clip seed=$seed k=$K post=$POST ===================="
    "$PY" tools/state_ablation.py --gpu_id "$GPU" --video_path "examples/$clip.mp4" --prompt_file_path "$(prompt_for "$clip")" \
      --seed "$seed" --step "$K" --migration_chunk "$M" --post_chunks "$POST" --configs "$CONFIGS" --save_video --out_dir "$out" \
      2>&1 | tee "$out/stdout.log"
  done
done
echo "[sweep] done -> $OUT_ROOT"
