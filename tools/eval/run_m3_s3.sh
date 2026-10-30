#!/usr/bin/env bash
# M3-S3 (osdi/m3s3/preregistration.md): lineage-aware staging across an ownership change.
# Mobility: A -> B completes at the planned switch call 80; the user moves to C when B reaches call 110 (B -> C starts)
# and to D when B reaches call 130 (B -> C is cancelled, B -> D completes). Phases in order; a failing phase stops the rest.
#   elves-01:  bash tools/eval/run_m3_s3.sh preflight   # agents, one commit, GPU 0 idle on A-D, workload files
#   elves-01:  bash tools/eval/run_m3_s3.sh p0          # Phase P0: offline checks on GPU 0 of elves-01 only (~6 min)
#   elves-01:  bash tools/eval/run_m3_s3.sh ac          # Phases A + C: dog, butterfly end to end (2 runs)
#   elves-01:  bash tools/eval/run_m3_s3.sh faults      # Phase B: dog, three ownership-change faults (3 runs)
#   elves-01:  bash tools/eval/run_m3_s3.sh perf        # Phase D: 2 workloads x {base, ctl, s2} x 3 reps (18 runs)
set -u
cd "$(dirname "$0")/../.."
COMMON="--launch --policies precopy_replay --hops 3 --bw 1000 --tm 1e9 --migration_chunk 30 --post_chunks 1500 --max_run_s 2400 --xb_horizon 100 --horizon_calls 180 --dyn_probe 4 --xb_policy_settings precopy_replay@thr=16:rl=1 --replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse --replay_switch_calls 80 --move_calls 110,130"
S3="--m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2"
CTL="--m3 --m3_owner --m3_staging none"
DOG_V=examples/original.mp4; DOG_P=examples/prompt.txt
BF_V=data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4; BF_P=data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt
node_args() { if [ "$1" = dog ]; then echo "--video_path $DOG_V --prompt_file_path $DOG_P --seed 0"; else echo "--video_path $BF_V --prompt_file_path $BF_P --seed 0"; fi; }
PY=${PY:-python}
EXPSET=${SET-expM3S3c}   # Corrected runs (prereg Note 1); SET=expM3S3 reproduces the Original set names
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    $PY tools/eval/d0_remote.py probe m3s3_data "ls -l $BF_V $BF_P $DOG_V $DOG_P; git rev-parse HEAD; free -g | head -2"
    cat results/evaluation/osdi/d0/m3s3_data/*.txt
    $PY tools/eval/d0_remote.py gpu_idle && echo "[M3S3] preflight: GPU 0 idle on A-D, one commit" ;;
  p0)
    mkdir -p results/evaluation/osdi/m3s3
    CUDA_VISIBLE_DEVICES=0 $PY tools/eval/m3s3_p0.py --video_path $DOG_V --prompt_file_path $DOG_P --seed 0 --out results/evaluation/osdi/m3s3/p0_dog.json || echo "[M3S3] p0 dog: exit $?"
    CUDA_VISIBLE_DEVICES=0 $PY tools/eval/m3s3_p0.py --video_path $BF_V --prompt_file_path $BF_P --seed 0 --out results/evaluation/osdi/m3s3/p0_bfly.json || echo "[M3S3] p0 bfly: exit $?" ;;
  ac)
    for wl in dog bfly; do
      echo "[M3S3] === A/C $wl"
      $PY tools/eval/mobility_orchestrate.py --experiment "${EXPSET}A_$wl" $COMMON --reps 1 $S3 --node_extra="$(node_args $wl)" || echo "[M3S3] A/C $wl: exit $?"
    done ;;
  faults)
    for f in version_mismatch corrupt_retained old_owner_fail; do
      echo "[M3S3] === B $f"
      $PY tools/eval/mobility_orchestrate.py --experiment "${EXPSET}B_$f" $COMMON --reps 1 $S3 --m3_test_fault $f --m3_fail_after 40 --node_extra="$(node_args dog)" || echo "[M3S3] B $f: exit $?"
    done ;;
  perf)
    for wl in dog bfly; do
      for cond in base ctl s2; do
        case $cond in base) X="" ;; ctl) X="$CTL" ;; s2) X="$S3" ;; esac
        echo "[M3S3] === D $wl $cond"
        $PY tools/eval/mobility_orchestrate.py --experiment "${EXPSET}D_${wl}_$cond" $COMMON --reps 3 $X --node_extra="$(node_args $wl)" || echo "[M3S3] D $wl $cond: exit $?"
      done
    done ;;
  *) echo "usage: $0 preflight|p0|ac|faults|perf"; exit 2 ;;
esac
