#!/usr/bin/env bash
# Concurrency pilot, stage 1 (osdi/concurrency/pilot_protocol.md; DRAFT, not frozen): one migration per session with
# the Fig. 7 configuration (1 Gbps, trigger at call 30, Fig. 7 flags), dog seed 0 in every session. Two sessions =
# two orchestrators on elves-01 whose migration starts are aligned by --barrier (same host clock, +2 s after the last
# arrival). Each session has its own per-node caps (no shared link before the rate coordinator: stage 2).
#   C1   S1 alone          elves-01:0 -> elves-03:0
#   C2   S1 + S2           S1 as C1; S2 elves-04:0 -> elves-02:0 (no shared host)
#   C3a  S1 + S2           S1 as C1; S2 elves-01:1 -> elves-03:1 (same source and destination hosts, own GPUs and ports)
# Methods: Full, R-full, OTTER (both sessions run the same method); node --mem_log. Experiments expCONC_<cond>_<method>_s<1|2>.
#   elves-01:  bash tools/eval/run_conc.sh preflight
#   elves-01:  bash tools/eval/run_conc.sh stage1        # C1 x 3 methods, C2 OTTER, C3a x 3 methods (7 runs)
#   elves-01:  python tools/eval/conc_report.py
#   local:     bash tools/eval/run_conc.sh dry           # two dry-run sessions on 127.0.0.1 through the barrier
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
SETV="precopy_full@thr=256:rl=10;recompute_full@lag=1:rl=1;precopy_replay@thr=16:rl=1"   # Fig. 7
COMMON="--launch --hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 1500 --max_run_s 2400 --xb_horizon 100 --horizon_calls 130 --dyn_probe 4"
OTTER="--replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse"   # Fig. 7 OTTER flags
DOG="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0 --mem_log"
H1=elves-01.be.ucsc.edu; H2=elves-02.be.ucsc.edu; H3=elves-03.be.ucsc.edu; H4=elves-04.be.ucsc.edu
S1="--nodes A=$H1:29811:29812,B=$H3:29811:29812 --agent_hosts A=$H1,B=$H3 --gpus A=0,B=0"
S2_C2="--nodes A=$H4:29811:29812,B=$H2:29811:29812 --agent_hosts A=$H4,B=$H2 --gpus A=0,B=0"
S2_C3A="--nodes A=$H1:29841:29842,B=$H3:29841:29842 --agent_hosts A=$H1,B=$H3 --gpus A=1,B=1"
METHODS="full recompute_full precopy_replay"
guard() { $PY tools/eval/d0_remote.py gpu_idle --hosts "$1" || { echo "[CONC] GPUs busy or hosts on different commits ($1)"; exit 1; }; }
sess() {   # experiment, method, node placement, barrier ("" = none)
  local B=""; [ -n "$4" ] && B="--barrier $4:2"
  $PY tools/eval/mobility_orchestrate.py --experiment "$1" $COMMON $3 --xb_policy_settings "$SETV" $OTTER --policies "$2" \
    --rep_start 1 --reps 1 $B --node_extra="$DOG" || echo "[CONC] $1: exit $?"
}
pair() {   # condition, method, S2 placement: both sessions at once, aligned
  local bar="results/evaluation/_barrier/$1_$2_$(date +%Y%m%d-%H%M%S)"
  echo "[CONC] === $1 $2 (two sessions, barrier $bar)"
  sess "expCONC_$1_$2_s1" "$2" "$S1" "$bar" > "/tmp/conc_$1_$2_s1.log" 2>&1 &
  sess "expCONC_$1_$2_s2" "$2" "$3" "$bar" > "/tmp/conc_$1_$2_s2.log" 2>&1 &
  wait; tail -n 2 "/tmp/conc_$1_$2_s1.log"; tail -n 2 "/tmp/conc_$1_$2_s2.log"
}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    guard A:0,A:1,B:0,C:0,C:1,D:0 && echo "[CONC] preflight: one commit; GPUs idle (elves-01 0/1, 02 0, 03 0/1, 04 0)" ;;
  stage1)
    guard A:0,A:1,B:0,C:0,C:1,D:0
    for m in $METHODS; do echo "[CONC] === C1 $m (S1 alone)"; sess "expCONC_C1_${m}_s1" "$m" "$S1" ""; done
    pair C2 precopy_replay "$S2_C2"
    for m in $METHODS; do pair C3a "$m" "$S2_C3A"; done ;;
  c1)  guard A:0,C:0; for m in ${2:-$METHODS}; do sess "expCONC_C1_${m}_s1" "$m" "$S1" ""; done ;;
  c2)  guard A:0,B:0,C:0,D:0; pair C2 "${2:-precopy_replay}" "$S2_C2" ;;
  c3a) guard A:0,A:1,C:0,C:1; for m in ${2:-$METHODS}; do pair C3a "$m" "$S2_C3A"; done ;;
  dry)
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    rm -rf results/evaluation/_dryrun_expCONC_* results/evaluation/_barrier/dry_*
    for p in 29911 29921 29931 29941; do
      lb=$( [ $p = 29911 ] || [ $p = 29931 ] && echo A || echo B )
      $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $p --data_port $((p + 1)) --mss 0 --dry_run --dry_sink_mb 64 \
        --dry_service_s 0.05 --migration_chunk 30 --post_chunks 300 --mem_log > "/tmp/conc_dry_node_$p.log" 2>&1 &
    done
    sleep 3
    bar="results/evaluation/_barrier/dry_$(date +%s)"; pids=""
    for i in 1 2; do
      n1=$((29891 + 20 * i)); n2=$((n1 + 10))
      $PY tools/eval/mobility_orchestrate.py --experiment "expCONC_dry_precopy_replay_s$i" --dry_run --mss 0 --dyn_probe 1 \
        --nodes A=127.0.0.1:$n1:$((n1 + 1)),B=127.0.0.1:$n2:$((n2 + 1)) --hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 300 \
        --max_run_s 600 --xb_horizon 20 --horizon_calls 40 --xb_policy_settings "$SETV" $OTTER --policies precopy_replay --rep_start 1 --reps 1 \
        --barrier "$bar:2" > "/tmp/conc_dry_orch_$i.log" 2>&1 &
      pids="$pids $!"
    done
    wait $pids; sleep 1
    grep -h "barrier round\|done:" /tmp/conc_dry_orch_1.log /tmp/conc_dry_orch_2.log
    $PY tools/eval/conc_report.py --prefix _dryrun_ --dry ;;
  *) echo "usage: $0 preflight|stage1|c1 [methods]|c2 [method]|c3a [methods]|dry"; exit 2 ;;
esac
