#!/usr/bin/env bash
# Fig. 10 (osdi/fig10/preregistration.md): M2 versioned Sink reuse vs version age. Path A -> B -> A, 1 Gbps, seed 0; first
# trigger at call 30, first switch at S1 = 74; second trigger at S1 + age, second switch at S1 + age + 44 (fixed switch
# calls: B's outputs are identical between the arms). Arms: Full (--replay_retain) and Versioned (+ --replay_reuse).
# Ages 10 / 60 / 150 / 240; 3 reps; experiments expF10_<w>_a<age>.
#   elves-01:  bash tools/eval/run_fig10.sh preflight
#   elves-01:  bash tools/eval/run_fig10.sh first          # dog, age 60, Versioned, rep 1 (counted if valid)
#   elves-01:  python tools/eval/fig10_report.py --sanity
#   elves-01:  bash tools/eval/run_fig10.sh rest           # the other 47 runs (reps outermost; ages, workloads, arms interleaved)
#   elves-01:  bash tools/eval/run_fig10.sh extra <w> <age> # only if fig10_report.py lists the cell under the extra-rep rule
#   local:     bash tools/eval/run_fig10.sh dry
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
S1=74; GAP=44; AGES="10 60 150 240"
COMMON="--launch --policies precopy_replay --path A,B,A --hops 1 --allow_return --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 500 --max_run_s 2400 --xb_horizon 100 --dyn_probe 4 --xb_policy_settings precopy_replay@thr=16:rl=1 --replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain"
DOG="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0"
BF="--video_path data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4 --prompt_file_path data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt --seed 0"
guard() { $PY tools/eval/d0_remote.py gpu_idle || { echo "[F10] hosts not on one commit or GPU 0 busy; run d0_remote.py pull first"; exit 1; }; }
one() {   # workload, age, arm (full|ver), rep
  local X; if [ "$1" = dog ]; then X="$DOG"; else X="$BF"; fi
  local R=""; [ "$3" = ver ] && R="--replay_reuse"
  local M=$((S1 + $2)); local S2=$((M + GAP))
  echo "[F10] === expF10_$1_a$2 $3 rep $4 (switches $S1,$S2; second trigger $M)"
  $PY tools/eval/mobility_orchestrate.py --experiment "expF10_$1_a$2" $COMMON $R --replay_switch_calls "$S1,$S2" --move_calls "$M" \
    --rep_start "$4" --reps 1 --node_extra="$X" || echo "[F10] expF10_$1_a$2 $3 rep $4: exit $?"
}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    guard && echo "[F10] preflight: one commit, GPU 0 idle on A-D" ;;
  first)
    guard; one dog 60 ver 1 ;;
  rest)
    guard
    for rep in 1 2 3; do
      for age in $AGES; do
        for w in dog bfly; do
          for arm in full ver; do
            [ $rep = 1 ] && [ $age = 60 ] && [ $w = dog ] && [ $arm = ver ] && continue   # = the first run
            one $w $age $arm $rep
          done
        done
      done
    done ;;
  extra)   # preregistered extra-rep rule (section 6): reps 4 and 5 of both arms of one (workload, age) cell
    guard
    for rep in 4 5; do for arm in full ver; do one "${2:?workload}" "${3:?age}" $arm $rep; done; done ;;
  dry)
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    for w in dog bfly; do
      for age in 10 60; do
        for arm in full ver; do
          for i in 0 1 2 3; do
            lb=$(echo ABCD | cut -c$((i + 1)))
            $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $((29911 + 10 * i)) --data_port $((29912 + 10 * i)) --mss 0 \
              --dry_run --dry_sink_mb 64 --dry_service_s 0.2 --migration_chunk 30 --post_chunks 500 > "/tmp/f10_dry_node_$lb.log" 2>&1 &
          done
          sleep 3
          R=""; [ $arm = ver ] && R="--replay_reuse"
          M=$((S1 + age)); S2=$((M + GAP))
          $PY tools/eval/mobility_orchestrate.py --experiment "expF10_${w}_a$age" --dry_run --mss 0 --dyn_probe 1 \
            --nodes A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942 \
            --policies precopy_replay --path A,B,A --hops 1 --allow_return --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 500 --max_run_s 900 --xb_horizon 20 \
            --xb_policy_settings precopy_replay@thr=16:rl=1 --replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain $R \
            --replay_switch_calls "$S1,$S2" --move_calls "$M" --rep_start 1 --reps 1 || echo "[F10] dry $w a$age $arm: exit $?"
          kill $(jobs -p) 2>/dev/null; wait
        done
      done
    done
    $PY tools/eval/fig10_report.py --prefix _dryrun_ --dry --sanity ;;
  *) echo "usage: $0 preflight|first|rest|extra <w> <age>|dry"; exit 2 ;;
esac
