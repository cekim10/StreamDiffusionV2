#!/usr/bin/env bash
# Fig. 8b (osdi/fig8/preregistration.md): native StreamDiffusionV2 (upstream inference.py --profile) on hosts A and B,
# and OTTER with M2 + M3 tracking (Fig. 7 OTTER flags + the M3-S3 flags) after one migration A -> B. Fig. 8a needs no run.
#   elves-01:  bash tools/eval/run_fig8.sh preflight   # agents, one commit, GPU 0 idle on A-D, config + checkpoint on B-D
#   elves-01:  bash tools/eval/run_fig8.sh native      # 10 native runs on A (here) while B runs its 10 through its agent
#   elves-01:  python tools/eval/fig8_native.py remote status   # B's progress;  ... remote fetch   # copy B's results here
#   elves-01:  bash tools/eval/run_fig8.sh otter       # 10 OTTER runs (2 workloads x 5 reps); only after B's native runs end
#   elves-01:  python tools/eval/fig8_report.py        # 8a (Fig. 7 runs) + 8b
#   local:     bash tools/eval/run_fig8.sh dry         # the OTTER configuration against dry-run nodes (no GPU)
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
COMMON="--hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 1500 --max_run_s 2400 --xb_horizon 100 --horizon_calls 130 --dyn_probe 4"
SETV="precopy_replay@thr=16:rl=1"
OTTER="--replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse --m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2"
DOG="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0"
BF="--video_path data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4 --prompt_file_path data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt --seed 0"
guard() { $PY tools/eval/d0_remote.py gpu_idle || { echo "[F8] hosts not on one commit or GPU 0 busy; run d0_remote.py pull first"; exit 1; }; }
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    $PY tools/eval/d0_remote.py probe fig8_pre "ls -l configs/wan_causal_dmd_v2v.yaml; ls ckpts/wan_causal_dmd_v2v | head -3; git rev-parse HEAD"
    cat results/evaluation/osdi/d0/fig8_pre/*.txt
    guard && echo "[F8] preflight: one commit, GPU 0 idle on A-D" ;;
  native_local)   # on one host: 5 reps x 2 workloads, workloads interleaved per rep
    lb=${2:?label}
    for rep in 1 2 3 4 5; do
      for w in dog bfly; do
        CUDA_VISIBLE_DEVICES=0 $PY tools/eval/fig8_native.py run --label "$lb" --workload $w --rep $rep --gpu 0 || echo "[F8] native $lb $w rep $rep: exit $?"
      done
    done
    echo "[F8] native_local $lb done" ;;
  native)
    guard
    $PY tools/eval/fig8_native.py remote start --label B
    bash "$0" native_local A
    $PY tools/eval/fig8_native.py remote status --label B ;;
  otter)
    guard
    for rep in 1 2 3 4 5; do
      for w in dog bfly; do
        if [ $w = dog ]; then X="$DOG"; else X="$BF"; fi
        echo "[F8] === expF8_$w rep $rep"
        $PY tools/eval/mobility_orchestrate.py --experiment "expF8_$w" --launch $COMMON --xb_policy_settings "$SETV" $OTTER --policies precopy_replay \
          --rep_start $rep --reps 1 --node_extra="$X" || echo "[F8] expF8_$w rep $rep: exit $?"
      done
    done ;;
  dry)
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    for w in dog bfly; do
      for i in 0 1 2 3; do
        lb=$(echo ABCD | cut -c$((i + 1)))
        $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $((29911 + 10 * i)) --data_port $((29912 + 10 * i)) --mss 0 \
          --dry_run --dry_sink_mb 64 --dry_service_s 0.2 --migration_chunk 30 --post_chunks 400 > "/tmp/f8_dry_node_$lb.log" 2>&1 &
      done
      sleep 3
      $PY tools/eval/mobility_orchestrate.py --experiment "expF8_$w" --dry_run --mss 0 --dyn_probe 1 \
        --nodes A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942 \
        --hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 400 --max_run_s 600 --xb_horizon 20 --horizon_calls 40 --xb_policy_settings "$SETV" $OTTER \
        --policies precopy_replay --rep_start 1 --reps 1 || echo "[F8] dry $w: exit $?"
      kill $(jobs -p) 2>/dev/null; wait
    done
    $PY tools/eval/fig8_report.py --prefix _dryrun_ --dry ;;
  *) echo "usage: $0 preflight|native|native_local <label>|otter|dry"; exit 2 ;;
esac
