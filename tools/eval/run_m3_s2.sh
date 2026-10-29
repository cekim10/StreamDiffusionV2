#!/usr/bin/env bash
# M3-S2 (osdi/m3s2/preregistration.md): GPU validation of lineage-aware forwarding and mixed-version Sink reconstruction.
# Phases in order; each later phase runs only if the earlier ones pass (m3s2_report.py).
#   elves-01:  bash tools/eval/run_m3_s2.sh preflight   # agents, one commit, GPU 0 idle on A-D, workload files
#   elves-01:  bash tools/eval/run_m3_s2.sh a0          # Phase A0: offline mixed-version exactness, GPU 0 of elves-01 only (~10 min)
#   elves-01:  bash tools/eval/run_m3_s2.sh ac          # Phases A + C: dog, butterfly end-to-end (2 runs, frame dumps for diagnostics)
#   elves-01:  bash tools/eval/run_m3_s2.sh faults      # Phase B: dog, three injected faults (3 runs)
#   elves-01:  bash tools/eval/run_m3_s2.sh perf        # Phase D: 2 workloads x {base, ctl, s2} x 3 reps (18 runs, no dumps)
set -u
cd "$(dirname "$0")/../.."
FR=/home/ckim151/m3s2_frames
COMMON="--launch --policies precopy_replay --hops 3 --bw 1000 --ts 14.05 --rhos 1 --migration_chunk 30 --post_chunks 1500 --max_run_s 2400 --xb_horizon 100 --horizon_calls 180 --dyn_probe 4 --xb_policy_settings precopy_replay@thr=16:rl=1 --replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse"
DOG_V=examples/original.mp4; DOG_P=examples/prompt.txt
BF_V=data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4; BF_P=data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt
node_args() { if [ "$1" = dog ]; then echo "--video_path $DOG_V --prompt_file_path $DOG_P --seed 0"; else echo "--video_path $BF_V --prompt_file_path $BF_P --seed 0"; fi; }
PY=${PY:-python}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    $PY tools/eval/d0_remote.py probe m3s2_data "ls -l $BF_V $BF_P $DOG_V $DOG_P; git rev-parse HEAD; free -g | head -2"
    cat results/evaluation/osdi/d0/m3s2_data/*.txt
    $PY tools/eval/d0_remote.py gpu_idle && echo "[M3S2] preflight: GPU 0 idle on A-D, one commit" ;;
  a0)
    mkdir -p results/evaluation/osdi/m3s2
    CUDA_VISIBLE_DEVICES=0 $PY tools/eval/m3s2_assemble.py --video_path $DOG_V --prompt_file_path $DOG_P --seed 0 --out results/evaluation/osdi/m3s2/a0_dog.json || echo "[M3S2] a0 dog: exit $?"
    CUDA_VISIBLE_DEVICES=0 $PY tools/eval/m3s2_assemble.py --video_path $BF_V --prompt_file_path $BF_P --seed 0 --out results/evaluation/osdi/m3s2/a0_bfly.json || echo "[M3S2] a0 bfly: exit $?" ;;
  ac)
    for wl in dog bfly; do
      echo "[M3S2] === A/C $wl"
      $PY tools/eval/mobility_orchestrate.py --experiment "expM3S2A_$wl" $COMMON --reps 1 --m3 --m3_staging S2 --m3_order fwd --dump_frames "$FR/A_$wl" --dump_calls 260 \
        --node_extra="$(node_args $wl)" || echo "[M3S2] A/C $wl: exit $?"
    done ;;
  faults)
    for f in advertise_wrong corrupt_held holder_fail; do
      echo "[M3S2] === B $f"
      $PY tools/eval/mobility_orchestrate.py --experiment "expM3S2B_$f" $COMMON --reps 1 --m3 --m3_staging S2 --m3_order fwd --m3_test_fault $f \
        --node_extra="$(node_args dog)" || echo "[M3S2] B $f: exit $?"
    done ;;
  perf)
    for wl in dog bfly; do
      for cond in base ctl s2; do
        case $cond in base) X="" ;; ctl) X="--m3 --m3_staging none" ;; s2) X="--m3 --m3_staging S2 --m3_order fwd" ;; esac
        echo "[M3S2] === D $wl $cond"
        $PY tools/eval/mobility_orchestrate.py --experiment "expM3S2D_${wl}_$cond" $COMMON --reps 3 $X --node_extra="$(node_args $wl)" || echo "[M3S2] D $wl $cond: exit $?"
      done
    done ;;
  *) echo "usage: $0 preflight|a0|ac|faults|perf"; exit 2 ;;
esac
