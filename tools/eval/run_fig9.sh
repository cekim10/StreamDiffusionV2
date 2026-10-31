#!/usr/bin/env bash
# Fig. 9 (osdi/fig9/preregistration.md): M1 design breakdown, one migration A -> B at call 30, 1 Gbps (Fig. 7 setting).
# New runs: Wait-for-Sink (split_wait), P-sink (precopy_sink@thr=256:rl=10), OTTER w/o Sink sync (precopy_replay without
# --replay_sink_sync); 5 reps x 2 workloads each. OTTER and P-full come from the Fig. 7 runs (no run here).
#   elves-01:  bash tools/eval/run_fig9.sh preflight     # agents, one commit, GPU 0 idle on A-D
#   elves-01:  bash tools/eval/run_fig9.sh first         # dog P-sink rep 1 (counted if it meets the preregistered conditions)
#   elves-01:  python tools/eval/fig9_report.py --sanity # C1 / metrics / rounds of that run
#   elves-01:  bash tools/eval/run_fig9.sh rest          # the other 29 runs (reps interleaved across steps and workloads)
#   local:     bash tools/eval/run_fig9.sh dry           # the three new conditions against local dry-run nodes (no GPU)
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
COMMON="--hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 1500 --max_run_s 2400 --xb_horizon 100 --horizon_calls 130 --dyn_probe 4"
SETV="precopy_sink@thr=256:rl=10;precopy_replay@thr=16:rl=1"   # D1: P-sink = the Fig. 7 P-full rule, Sink scope; replay as Fig. 7
NOSYNC="--replay_window 12 --replay_lag 1"                       # OTTER w/o Sink sync (M1 E3): no patches, dirty Sink resent at the switch
DOG="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0"
BF="--video_path data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4 --prompt_file_path data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt --seed 0"
guard() { $PY tools/eval/d0_remote.py gpu_idle || { echo "[F9] hosts not on one commit or GPU 0 busy; run d0_remote.py pull first"; exit 1; }; }
orch() {   # experiment, policies, rep, node args, [extra orchestrator args]
  echo "[F9] === $1 $2 rep $3"
  $PY tools/eval/mobility_orchestrate.py --experiment "$1" --launch $COMMON --xb_policy_settings "$SETV" $NOSYNC ${5:-} --policies "$2" \
    --rep_start "$3" --reps 1 --node_extra="$4" || echo "[F9] $1 $2 rep $3: exit $?"
}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    guard && echo "[F9] preflight: one commit, GPU 0 idle on A-D" ;;
  first)
    guard; orch expF9_dog precopy_sink 1 "$DOG" ;;
  rest)
    guard
    for rep in 1 2 3 4 5; do
      for w in dog bfly; do
        if [ $w = dog ]; then X="$DOG"; else X="$BF"; fi
        if [ $w = dog ] && [ $rep = 1 ]; then P=split_wait,precopy_replay; else P=split_wait,precopy_sink,precopy_replay; fi   # dog P-sink rep 1 = the first run
        orch "expF9_$w" "$P" $rep "$X"
      done
    done ;;
  dry)
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    for w in dog bfly; do
      for i in 0 1 2 3; do
        lb=$(echo ABCD | cut -c$((i + 1)))
        $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $((29911 + 10 * i)) --data_port $((29912 + 10 * i)) --mss 0 \
          --dry_run --dry_sink_mb 64 --dry_service_s 0.2 --migration_chunk 30 --post_chunks 400 > "/tmp/f9_dry_node_$lb.log" 2>&1 &
      done
      sleep 3
      $PY tools/eval/mobility_orchestrate.py --experiment "expF9_$w" --dry_run --mss 0 --dyn_probe 1 \
        --nodes A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942 \
        --hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 400 --max_run_s 600 --xb_horizon 20 --horizon_calls 40 --xb_policy_settings "$SETV" $NOSYNC \
        --policies split_wait,precopy_sink,precopy_replay --rep_start 1 --reps 1 || echo "[F9] dry $w: exit $?"
      kill $(jobs -p) 2>/dev/null; wait
    done
    $PY tools/eval/fig9_report.py --prefix _dryrun_ --dry ;;
  *) echo "usage: $0 preflight|first|rest|dry"; exit 2 ;;
esac
