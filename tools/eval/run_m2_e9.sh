#!/usr/bin/env bash
# E9 (osdi/m1_continuity/e9_plan.md): first real A -> B -> A with M2 (versioned Sink reuse) against the M1 fresh-base
# baseline. dog s1, 1 Gbps, switches at calls 64 and 164 (second trigger at 120), Replay-12, Sink synchronization.
#   elves-01:  bash tools/eval/run_m2_e9.sh orch      # both runs (baseline, then M2)
#   elves-01:  bash tools/eval/run_m2_e9.sh sync      # copy A's frame dumps to elves-02 (metrics there)
#   elves-02:  bash tools/eval/run_m2_e9.sh metrics   # continuity of both migrations of both runs
set -u
cd "$(dirname "$0")/../.."
FR=/home/ckim151/m2e9_frames
COMMON="--launch --policies precopy_replay --path A,B,A --hops 1 --allow_return --tm 1e9 --bw 1000 --reps 1 --migration_chunk 20 --post_chunks 400 --max_run_s 2400 --xb_horizon 100 --xb_policy_settings precopy_replay@thr=16:rl=1 --replay_window 12 --replay_lag 1 --replay_sink_sync --replay_switch_calls 64,164 --move_calls 120"
NODE="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 1"
PY=${PY:-python}
case "${1:-}" in
  orch)
    for name in baseline m2; do
      extra=""; [ "$name" = m2 ] && extra="--replay_retain --replay_reuse"
      echo "[E9] === $name"
      $PY tools/eval/mobility_orchestrate.py --experiment "expM2E9_$name" $COMMON $extra --dump_frames "$FR/$name" --node_extra="$NODE" || echo "[E9] $name: orchestrator exit $?"
    done ;;
  sync)
    rsync -a "$FR/" "elves-02.be.ucsc.edu:$FR/" && echo "[E9] A's frame dumps copied to elves-02" ;;
  metrics)
    for name in baseline m2; do
      for run in $(ls "$FR/$name"); do
        .venv/bin/python tools/eval/m1_live_metrics.py --dump_root "$FR/$name" --runs "$run" --unit dog_s1 --input dog --out_store OUT_B --ref_store REF_B \
          --out "results/evaluation/osdi/m1_continuity/e9_metrics_${name}_mig1.json" || echo "[E9] $name mig1: metrics exit $?"
        .venv/bin/python tools/eval/m1_live_metrics.py --dump_root "$FR/$name" --runs "$run" --unit dog_s1 --input dog --out_store OUT_A --ref_store REF_A --prefix_store OUT_B \
          --out "results/evaluation/osdi/m1_continuity/e9_metrics_${name}_mig2.json" || echo "[E9] $name mig2: metrics exit $?"
      done
    done ;;
  *) echo "usage: $0 orch|sync|metrics"; exit 2 ;;
esac
