#!/usr/bin/env bash
# Fig. 11 (osdi/fig11/preregistration.md): repeated mobility A -> B -> C -> D on the wall clock (--move_times), 1 Gbps,
# trigger at call 30, seed 0. Scenarios Chain (moves at 45, 90 s) and Cancel (48, 60 s). Methods: Full, Llumnix-style
# P-full, ServerlessLLM-style R-full, OTTER w/o staging (M1 + M2), OTTER (+ M3). 3 reps; experiments expF11_<scen>_<w>.
#   elves-01:  bash tools/eval/run_fig11.sh preflight
#   elves-01:  bash tools/eval/run_fig11.sh first          # Chain, dog, OTTER, rep 1 (counted if valid)
#   elves-01:  python tools/eval/fig11_report.py --sanity
#   elves-01:  bash tools/eval/run_fig11.sh rest           # the other 59 runs (reps outermost; scenarios, workloads, methods interleaved)
#   local:     bash tools/eval/run_fig11.sh dry            # dog, both scenarios, all five methods, against dry-run nodes
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
SETV="precopy_full@thr=256:rl=10;recompute_full@lag=1:rl=1;precopy_replay@thr=16:rl=1"   # Fig. 7 settings
COMMON="--hops 3 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 800 --max_run_s 2400 --xb_horizon 100 --horizon_calls 130 --dyn_probe 4"
OTTER="--replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse"   # Fig. 7 OTTER flags (M1 + M2)
M3="--m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2"                          # M3-S3
EXT=full,precopy_full,recompute_full,precopy_replay   # precopy_replay here = OTTER w/o staging
DOG="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0"
BF="--video_path data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4 --prompt_file_path data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt --seed 0"
guard() { $PY tools/eval/d0_remote.py gpu_idle || { echo "[F11] hosts not on one commit or GPU 0 busy; run d0_remote.py pull first"; exit 1; }; }
moves() { if [ "$1" = chain ]; then echo "45,90"; else echo "48,60"; fi; }
orch() {   # scenario, workload, policies, rep, extra flags
  local X; if [ "$2" = dog ]; then X="$DOG"; else X="$BF"; fi
  echo "[F11] === expF11_$1_$2 $3 ${5:+(M3) }rep $4"
  $PY tools/eval/mobility_orchestrate.py --experiment "expF11_$1_$2" --launch $COMMON --move_times "$(moves "$1")" --xb_policy_settings "$SETV" $OTTER ${5:-} \
    --policies "$3" --rep_start "$4" --reps 1 --node_extra="$X" || echo "[F11] expF11_$1_$2 $3 rep $4: exit $?"
}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    guard && echo "[F11] preflight: one commit, GPU 0 idle on A-D" ;;
  first)
    guard; orch chain dog precopy_replay 1 "$M3" ;;
  rest)
    guard
    for rep in 1 2 3; do
      for scen in chain cancel; do
        for w in dog bfly; do
          orch $scen $w "$EXT" $rep
          [ $rep = 1 ] && [ $scen = chain ] && [ $w = dog ] && continue   # OTTER (M3) chain dog rep 1 = the first run
          orch $scen $w precopy_replay $rep "$M3"
        done
      done
    done ;;
  dry)
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    for scen in chain cancel; do
      if [ $scen = chain ]; then MV="12,24"; else MV="12,13"; fi   # scaled to the dry service time (0.2 s / call)
      for x in ext m3; do
        for i in 0 1 2 3; do
          lb=$(echo ABCD | cut -c$((i + 1)))
          $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $((29911 + 10 * i)) --data_port $((29912 + 10 * i)) --mss 0 \
            --dry_run --dry_sink_mb 64 --dry_service_s 0.2 --migration_chunk 30 --post_chunks 800 > "/tmp/f11_dry_node_$lb.log" 2>&1 &
        done
        sleep 3
        if [ $x = ext ]; then P=$EXT; XF=""; else P=precopy_replay; XF="$M3"; fi
        $PY tools/eval/mobility_orchestrate.py --experiment "expF11_${scen}_dog" --dry_run --mss 0 --dyn_probe 1 \
          --nodes A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942 \
          --hops 3 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 800 --max_run_s 900 --xb_horizon 20 --horizon_calls 60 --move_times "$MV" \
          --xb_policy_settings "$SETV" $OTTER $XF --policies "$P" --rep_start 1 --reps 1 || echo "[F11] dry $scen $x: exit $?"
        kill $(jobs -p) 2>/dev/null; wait
      done
    done
    $PY tools/eval/fig11_report.py --prefix _dryrun_ --dry --sanity ;;
  *) echo "usage: $0 preflight|first|rest|dry"; exit 2 ;;
esac
