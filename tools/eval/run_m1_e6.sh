#!/usr/bin/env bash
# E6 (osdi/m1_continuity/e6_plan.md): M1 log-only replay + replay-aware Sink synchronization on more workloads, and one
# real GPU fallback run. One orchestrator invocation per workload (the nodes start with that workload's video).
#   elves-01:  bash tools/eval/run_m1_e6.sh orch
#   elves-02:  bash tools/eval/run_m1_e6.sh metrics      (the destination host; frames under /home/ckim151/m1e6_frames)
set -u
cd "$(dirname "$0")/../.."
FR=/home/ckim151/m1e6_frames
# name | unit (thresholds) | metrics input | video | prompt | seed | extra
RUNS=(
  "train_s0|train_s0|train|examples/train.mp4|examples/train_prompt.txt|0|"
  "bfly_s1|butterfly-feeding-slow-motion_s1|butterfly-feeding-slow-motion|data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4|data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt|1|"
  "audi_s1|audi-snow-trail_s1|audi-snow-trail|data/loveu_tgve_2023/audi-snow-trail.mp4|data/loveu_tgve_2023/audi-snow-trail__multiple.txt|1|"
  "dog_s1_fallback|dog_s1|dog|examples/original.mp4|examples/prompt.txt|1|--replay_sink_sync_test_perturb_dst"
)
PY=${PY:-python}
case "${1:-}" in
  orch)
    for r in "${RUNS[@]}"; do
      IFS='|' read -r name unit inp video prompt seed extra <<< "$r"
      echo "[E6] === $name"
      $PY tools/eval/mobility_orchestrate.py --experiment "expM1E6_$name" --launch --policies precopy_replay --hops 1 --tm 1e9 --bw 1000 --reps 1 \
        --migration_chunk 30 --post_chunks 400 --max_run_s 2400 --xb_horizon 100 --xb_policy_settings "precopy_replay@thr=16:rl=1" \
        --replay_window 12 --replay_lag 1 --replay_verify --replay_sink_sync $extra --dump_frames "$FR/$name" \
        --node_extra="--video_path $video --prompt_file_path $prompt --seed $seed" || echo "[E6] $name: orchestrator exit $?"
    done ;;
  metrics)
    for r in "${RUNS[@]}"; do
      IFS='|' read -r name unit inp video prompt seed extra <<< "$r"
      [ -d "$FR/$name" ] || { echo "[E6] $name: no frames"; continue; }
      .venv/bin/python tools/eval/m1_live_metrics.py --dump_root "$FR/$name" --runs "$(ls "$FR/$name" | paste -sd,)" --unit "$unit" --input "$inp" \
        --out "results/evaluation/osdi/m1_continuity/e6_metrics_$name.json" || echo "[E6] $name: metrics exit $?"
    done ;;
  *) echo "usage: $0 orch|metrics"; exit 2 ;;
esac
