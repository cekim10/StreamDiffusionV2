#!/usr/bin/env bash
# E10 (osdi/m1_continuity/e10_plan.md): butterfly s1 A -> B -> A (baseline / M2) and real GPU delta-base fallback
# (dog s1, three injected faults). Same protocol and settings as E9.
#   elves-01:  bash tools/eval/run_m2_e10.sh orch
#   Mac:       relay A's frames (elves-01 -> Mac -> elves-02), see the E10 instructions
#   elves-02:  bash tools/eval/run_m2_e10.sh metrics
#   elves-02:  bash tools/eval/run_m2_e10.sh frames    # bitwise frame comparison against the baselines (E9 dog frames there)
set -u
cd "$(dirname "$0")/../.."
FR=/home/ckim151/m2e10_frames
COMMON="--launch --policies precopy_replay --path A,B,A --hops 1 --allow_return --tm 1e9 --bw 1000 --reps 1 --migration_chunk 20 --post_chunks 400 --max_run_s 2400 --xb_horizon 100 --xb_policy_settings precopy_replay@thr=16:rl=1 --replay_window 12 --replay_lag 1 --replay_sink_sync --replay_switch_calls 64,164 --move_calls 120"
BF="--video_path data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4 --prompt_file_path data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt --seed 1"
DG="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 1"
# name | node args | unit | metrics input | extra
RUNS=(
  "bfly_baseline|$BF|butterfly-feeding-slow-motion_s1|butterfly-feeding-slow-motion|--replay_retain"
  "bfly_m2|$BF|butterfly-feeding-slow-motion_s1|butterfly-feeding-slow-motion|--replay_retain --replay_reuse"
  "dog_fault_advertise|$DG|dog_s1|dog|--replay_retain --replay_reuse --replay_test_fault advertise_wrong"
  "dog_fault_held|$DG|dog_s1|dog|--replay_retain --replay_reuse --replay_test_fault held_wrong"
  "dog_fault_corrupt|$DG|dog_s1|dog|--replay_retain --replay_reuse --replay_test_fault corrupt_block"
)
PY=${PY:-python}
case "${1:-}" in
  orch)
    for r in "${RUNS[@]}"; do
      IFS='|' read -r name node unit inp extra <<< "$r"
      echo "[E10] === $name"
      $PY tools/eval/mobility_orchestrate.py --experiment "expM2E10_$name" $COMMON $extra --dump_frames "$FR/$name" --node_extra="$node" || echo "[E10] $name: orchestrator exit $?"
    done ;;
  metrics)
    for r in "${RUNS[@]}"; do
      IFS='|' read -r name node unit inp extra <<< "$r"
      for run in $(ls "$FR/$name" 2>/dev/null); do
        .venv/bin/python tools/eval/m1_live_metrics.py --dump_root "$FR/$name" --runs "$run" --unit "$unit" --input "$inp" --out_store OUT_B --ref_store REF_B \
          --out "results/evaluation/osdi/m1_continuity/e10_metrics_${name}_mig1.json" || echo "[E10] $name mig1: metrics exit $?"
        .venv/bin/python tools/eval/m1_live_metrics.py --dump_root "$FR/$name" --runs "$run" --unit "$unit" --input "$inp" --out_store OUT_A --ref_store REF_A --prefix_store OUT_B \
          --out "results/evaluation/osdi/m1_continuity/e10_metrics_${name}_mig2.json" || echo "[E10] $name mig2: metrics exit $?"
      done
    done ;;
  frames)
    .venv/bin/python tools/eval/m2_e10_frames.py ;;
  *) echo "usage: $0 orch|metrics|frames"; exit 2 ;;
esac
