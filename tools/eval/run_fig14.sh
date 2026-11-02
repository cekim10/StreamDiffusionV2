#!/usr/bin/env bash
# Fig. 14 (osdi/fig14/preregistration.md, DRAFT): OTTER's overheads.
#   14a throughput: native StreamDiffusionV2 (upstream, unmodified) vs the same native loop with OTTER's steady-state
#       tracking (M2 + M3) inserted per call (tools/eval/fig14_native_track.py; variants native / wrap / track, 5 reps x
#       dog, butterfly, variant order rotated per rep) on one host (D1: A). During migration / staging: existing Fig. 7 /
#       Fig. 11 OTTER runs (no new runs).
#   14b memory: OTTER single migration (Fig. 7 configuration) and Chain repeated mobility (Fig. 11 OTTER with staging),
#       node flag --mem_log (record only): process RSS, GPU allocated / reserved, retained and staged Sink bytes at 2 Hz.
#       Experiments expF14_mem_single_<w> (A -> B, 3 reps) and expF14_mem_chain_<w> (A -> B -> C -> D, 2 reps).
#   elves-01:  bash tools/eval/run_fig14.sh preflight
#   elves-01:  bash tools/eval/run_fig14.sh first      # one native-track run (dog, rep 1) + one memory run (single, dog, rep 1)
#   elves-01:  python tools/eval/fig14_report.py --sanity
#   elves-01:  bash tools/eval/run_fig14.sh native     # the other 29 throughput runs on A
#   elves-02:  LB=B bash tools/eval/run_fig14.sh native_only   # native on B, 10 runs (the integrated runs' baseline), at the same time
#   elves-01:  bash tools/eval/run_fig14.sh integrated # OTTER integrated: Fig. 8b's configuration, A -> B, 5 reps x 2 (after both)
#   elves-01:  bash tools/eval/run_fig14.sh memory     # the other 9 memory runs on A-D (after `native`; A's GPU is shared)
#   local:     bash tools/eval/run_fig14.sh dry
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
LB=${LB:-A}                                       # D1: host of the throughput runs
SETV="precopy_full@thr=256:rl=10;recompute_full@lag=1:rl=1;precopy_replay@thr=16:rl=1"
OTTER="--replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse"   # Fig. 7 OTTER flags (M1 + M2)
M3="--m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2"                          # Fig. 11 (M3-S3)
SINGLE="--launch --hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 1500 --max_run_s 2400 --xb_horizon 100 --horizon_calls 130 --dyn_probe 4"
CHAIN="--launch --hops 3 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 800 --max_run_s 2400 --xb_horizon 100 --horizon_calls 130 --dyn_probe 4 --move_times 45,90"
DOG="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0"
BF="--video_path data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4 --prompt_file_path data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt --seed 0"
guard() { $PY tools/eval/d0_remote.py gpu_idle --hosts "$1" || { echo "[F14] hosts not on one commit or GPU 0 busy ($1); run d0_remote.py pull first"; exit 1; }; }
wl() { if [ "$1" = dog ]; then echo "$DOG"; else echo "$BF"; fi; }
nat() {   # workload, rep, variant
  CUDA_VISIBLE_DEVICES=0 $PY tools/eval/fig14_native_track.py run --label "$LB" --workload "$1" --rep "$2" --variant "$3" --gpu 0 || echo "[F14] native $1 rep $2 $3: exit $?"
}
mem() {   # scenario (single | chain), workload, rep
  local C P X; if [ "$1" = single ]; then C="$SINGLE"; X=""; else C="$CHAIN"; X="$M3"; fi
  echo "[F14] === expF14_mem_$1_$2 rep $3"
  $PY tools/eval/mobility_orchestrate.py --experiment "expF14_mem_$1_$2" $C --xb_policy_settings "$SETV" $OTTER $X --policies precopy_replay \
    --rep_start "$3" --reps 1 --node_extra="$(wl "$2") --mem_log" || echo "[F14] mem $1 $2 rep $3: exit $?"
}
rot() {   # rep -> the three variants rotated by rep (order effects spread evenly)
  case $(( ($1 - 1) % 3 )) in 0) echo "native wrap track" ;; 1) echo "wrap track native" ;; *) echo "track native wrap" ;; esac
}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    $PY tools/eval/d0_remote.py codecs
    guard A,B,C,D && echo "[F14] preflight: one commit, GPU 0 idle on A-D" ;;
  first)
    guard A,B,C,D
    nat dog 1 track
    mem single dog 1 ;;
  native)
    guard "$LB"
    for rep in 1 2 3 4 5; do
      for w in dog bfly; do
        for v in $(rot $rep); do
          [ $rep = 1 ] && [ $w = dog ] && [ $v = track ] && continue   # = the first run
          nat $w $rep $v
        done
      done
    done ;;
  native_only)   # native on this host (LB), 5 reps x 2 workloads: the baseline of the integrated configuration
    guard "$LB"
    for rep in 1 2 3 4 5; do for w in dog bfly; do nat $w $rep native; done; done ;;
  integrated)   # the whole OTTER harness (M1 + M2 + M3, Fig. 8b's command), one migration A -> B; B's steady state after the cutover
    guard A,B
    for rep in 1 2 3 4 5; do
      for w in dog bfly; do
        echo "[F14] === expF14_int_$w rep $rep"
        $PY tools/eval/mobility_orchestrate.py --experiment "expF14_int_$w" $SINGLE --xb_policy_settings "precopy_replay@thr=16:rl=1" \
          $OTTER $M3 --policies precopy_replay --rep_start $rep --reps 1 --node_extra="$(wl $w)" || echo "[F14] int $w rep $rep: exit $?"
      done
    done ;;
  memory)
    guard A,B,C,D
    for rep in 1 2 3; do
      for w in dog bfly; do
        [ $rep = 1 ] && [ $w = dog ] || mem single $w $rep
        [ $rep -le 2 ] && mem chain $w $rep
      done
    done ;;
  dry)
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    rm -rf results/evaluation/_dryrun_expF14_*
    for scen in single chain; do
      for i in 0 1 2 3; do
        lb=$(echo ABCD | cut -c$((i + 1)))
        $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $((29911 + 10 * i)) --data_port $((29912 + 10 * i)) --mss 0 \
          --dry_run --dry_sink_mb 64 --dry_service_s 0.2 --migration_chunk 30 --post_chunks 400 --mem_log > "/tmp/f14_dry_node_$lb.log" 2>&1 &
      done
      sleep 3
      if [ $scen = single ]; then XF="--hops 1"; else XF="--hops 3 --move_times 12,24 $M3"; fi
      $PY tools/eval/mobility_orchestrate.py --experiment "expF14_mem_${scen}_dog" --dry_run --mss 0 --dyn_probe 1 \
        --nodes A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942 \
        --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 400 --max_run_s 900 --xb_horizon 20 --horizon_calls 60 $XF \
        --xb_policy_settings "$SETV" $OTTER --policies precopy_replay --rep_start 1 --reps 1 || echo "[F14] dry $scen: exit $?"
      kill $(jobs -p) 2>/dev/null; wait
    done
    $PY tools/eval/fig14_report.py --prefix _dryrun_ --dry --sanity ;;
  *) echo "usage: $0 preflight|first|native|native_only|integrated|memory|dry"; exit 2 ;;
esac
