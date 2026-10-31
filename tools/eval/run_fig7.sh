#!/usr/bin/env bash
# Fig. 7 (osdi/fig7/preregistration.md): one migration A -> B at call 30, 1 Gbps; Full, Llumnix-style P-full,
# ServerlessLLM-style R-full and OTTER (frozen M1 / M2 flags as M3-S3 Phase D base, --m3 off); 5 reps per cell.
# Order: the first run (dog, OTTER, rep 1) is the sanity check; the rest runs only after it is checked.
#   elves-01:  bash tools/eval/run_fig7.sh preflight     # agents, one commit, GPU 0 idle on A-D
#   elves-01:  bash tools/eval/run_fig7.sh first         # dog OTTER rep 1 (counted if it meets the preregistered conditions)
#   elves-01:  python tools/eval/fig7_report.py --sanity # C1 / metrics / bytes of that run
#   elves-01:  bash tools/eval/run_fig7.sh rest          # the other 39 runs (reps interleaved across methods)
#   local:     bash tools/eval/run_fig7.sh dry           # all four policies against local dry-run nodes (no GPU)
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
SETV="precopy_full@thr=256:rl=10;recompute_full@lag=1:rl=1;precopy_replay@thr=16:rl=1"   # XB freeze; M1 E3-E6 / M3-S3
COMMON="--hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 1500 --max_run_s 2400 --xb_horizon 100 --horizon_calls 130 --dyn_probe 4"
OTTER="--replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse"
ALL=full,precopy_full,recompute_full,precopy_replay
DOG="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0"
BF="--video_path data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4 --prompt_file_path data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt --seed 0"
guard() { $PY tools/eval/d0_remote.py gpu_idle || { echo "[F7] hosts not on one commit or GPU 0 busy; run d0_remote.py pull first"; exit 1; }; }
orch() {   # experiment, policies, rep_start, reps, node args
  echo "[F7] === $1 $2 reps $3..$(( $3 + $4 - 1 ))"
  $PY tools/eval/mobility_orchestrate.py --experiment "$1" --launch $COMMON --xb_policy_settings "$SETV" $OTTER --policies "$2" --rep_start "$3" --reps "$4" \
    --node_extra="$5" || echo "[F7] $1 $2: exit $?"
}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    $PY tools/eval/d0_remote.py codecs
    guard && echo "[F7] preflight: one commit, GPU 0 idle on A-D, codecs ok" ;;
  first)
    guard; orch expF7_dog precopy_replay 1 1 "$DOG" ;;
  rest)
    guard
    orch expF7_dog full,precopy_full,recompute_full 1 1 "$DOG"     # rep 1 of the baselines (OTTER rep 1 = the first run)
    orch expF7_dog "$ALL" 2 4 "$DOG"                                # reps 2-5, methods interleaved per rep
    orch expF7_bfly "$ALL" 1 5 "$BF" ;;
  dry)
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    for w in dog bfly; do   # fresh dry-run nodes per invocation (the orchestrator shuts its nodes down at the end)
      for i in 0 1 2 3; do
        lb=$(echo ABCD | cut -c$((i + 1)))
        $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $((29911 + 10 * i)) --data_port $((29912 + 10 * i)) --mss 0 \
          --dry_run --dry_sink_mb 64 --dry_service_s 0.2 --migration_chunk 30 --post_chunks 400 > "/tmp/f7_dry_node_$lb.log" 2>&1 &
      done
      sleep 3
      $PY tools/eval/mobility_orchestrate.py --experiment "expF7_$w" --dry_run --mss 0 --dyn_probe 1 \
        --nodes A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942 \
        --hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 400 --max_run_s 600 --xb_horizon 20 --horizon_calls 40 --xb_policy_settings "$SETV" $OTTER \
        --policies "$ALL" --rep_start 1 --reps 1 || echo "[F7] dry $w: exit $?"
      kill $(jobs -p) 2>/dev/null; wait   # nodes the orchestrator did not use (C, D) are still up
    done
    $PY tools/eval/fig7_report.py --prefix _dryrun_ --dry ;;
  *) echo "usage: $0 preflight|first|rest|dry"; exit 2 ;;
esac
