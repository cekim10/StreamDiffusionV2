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
# Stage 2 (rate coordinator tools/eval/rate_coord.py on elves-01, per-host shared 1 Gbps egress / ingress, max-min over
# both sessions' flows; started and stopped by this script, log results/evaluation/osdi/concurrency/coord_<cond>_*.jsonl):
#   C3b  as C3a, with --coord on both sessions (shared link)
#   C4   S1 = Fig. 11 Chain A -> B -> C -> D (GPU 0 of elves-01..04, moves at 45 / 90 s), OTTER with M3 or w/o M3;
#        S2 = one OTTER migration elves-03:1 -> elves-04:1 starting 45 s after S1 (--barrier_offset_s), with the
#        forward to D; four cells: {M3, noM3} x {alone, +S2}; every cell with --coord (one code path)
#   elves-01:  bash tools/eval/run_conc.sh stage2        # C3b x 3 methods, C4 x 4 cells (7 runs)
#   local:     bash tools/eval/run_conc.sh dry_coord     # two dry sessions on shared sites through the coordinator
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
CHAIN="--launch --hops 3 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 800 --max_run_s 2400 --xb_horizon 100 --horizon_calls 130 --dyn_probe 4 --move_times 45,90"
M3="--m3 --m3_owner --m3_staging S2 --m3_order fwd --m3_replan_s 2"   # Fig. 11 (M3-S3)
S1_CHAIN="--nodes A=$H1:29811:29812,B=$H2:29811:29812,C=$H3:29811:29812,D=$H4:29811:29812 --agent_hosts A=$H1,B=$H2,C=$H3,D=$H4 --gpus A=0,B=0,C=0,D=0"
S2_C4="--nodes A=$H3:29841:29842,B=$H4:29841:29842 --agent_hosts A=$H3,B=$H4 --gpus A=1,B=1"
CPORT=29960
guard() { $PY tools/eval/d0_remote.py gpu_idle --hosts "$1" || { echo "[CONC] GPUs busy or hosts on different commits ($1)"; exit 1; }; }
note_gpu1() {   # record only (never stops the run): who holds GPU 1 on elves-01 / 03 / 04 while C1 / C2 run on GPU 0
  local f="results/evaluation/osdi/concurrency/gpu1_state_$1_$(date +%Y%m%d-%H%M%S).txt"
  mkdir -p "$(dirname "$f")"; { date -Is; $PY tools/eval/d0_remote.py gpu_idle --hosts A:1,C:1,D:1; } > "$f" 2>&1
  echo "[CONC] GPU 1 state ($1): $(tail -n 1 "$f") -> $f"
}
sess() {   # experiment, method, node placement, barrier ("" = none), [run flags (default the single-migration COMMON)], [extra flags]
  local B=""; [ -n "$4" ] && B="--barrier $4:2"
  $PY tools/eval/mobility_orchestrate.py --experiment "$1" ${5:-$COMMON} $3 --xb_policy_settings "$SETV" $OTTER ${6:-} --policies "$2" \
    --rep_start 1 --reps 1 $B --node_extra="$DOG" || echo "[CONC] $1: exit $?"
}
pair() {   # condition, method, S2 placement, [extra flags of both sessions]: both sessions at once, aligned
  local bar="results/evaluation/_barrier/$1_$2_$(date +%Y%m%d-%H%M%S)"
  echo "[CONC] === $1 $2 (two sessions, barrier $bar)"
  sess "expCONC_$1_$2_s1" "$2" "$S1" "$bar" "$COMMON" "${4:-}" > "/tmp/conc_$1_$2_s1.log" 2>&1 & local p1=$!
  sess "expCONC_$1_$2_s2" "$2" "$3" "$bar" "$COMMON" "${4:-}" > "/tmp/conc_$1_$2_s2.log" 2>&1 & local p2=$!
  wait $p1 $p2; tail -n 2 "/tmp/conc_$1_$2_s1.log"; tail -n 2 "/tmp/conc_$1_$2_s2.log"
}
coord_up() {   # condition tag: start the coordinator (127.0.0.1:CPORT, cap 1 Gbps) with its own log
  local log="results/evaluation/osdi/concurrency/coord_$1_$(date +%Y%m%d-%H%M%S).jsonl"
  $PY tools/eval/rate_coord.py serve --port $CPORT --cap_mbps 1000 --log "$log" > "/tmp/conc_coord_$1.log" 2>&1 & CPID=$!
  sleep 1; echo "[CONC] coordinator pid $CPID, log $log"
}
coord_down() { kill $CPID 2>/dev/null; wait $CPID 2>/dev/null; return 0; }   # wait returns 143 for the killed coordinator: not a failure
c4cell() {   # arm (m3 | nom3), with S2 (0 | 1)
  local X=""; [ "$1" = m3 ] && X="$M3"
  local tag="C4_$1_$([ "$2" = 1 ] && echo conc || echo alone)"
  coord_up "$tag"
  if [ "$2" = 1 ]; then
    local bar="results/evaluation/_barrier/${tag}_$(date +%Y%m%d-%H%M%S)"
    echo "[CONC] === $tag (S1 Chain + S2 at +45 s, barrier $bar)"
    sess "expCONC_${tag}_precopy_replay_s1" precopy_replay "$S1_CHAIN" "$bar" "$CHAIN" "$X --coord 127.0.0.1:$CPORT" > "/tmp/conc_${tag}_s1.log" 2>&1 & local p1=$!
    sess "expCONC_${tag}_precopy_replay_s2" precopy_replay "$S2_C4" "$bar" "$COMMON" "--coord 127.0.0.1:$CPORT --barrier_offset_s 45" > "/tmp/conc_${tag}_s2.log" 2>&1 & local p2=$!
    wait $p1 $p2; tail -n 2 "/tmp/conc_${tag}_s1.log"; tail -n 2 "/tmp/conc_${tag}_s2.log"
  else
    echo "[CONC] === $tag (S1 Chain alone)"
    sess "expCONC_${tag}_precopy_replay_s1" precopy_replay "$S1_CHAIN" "" "$CHAIN" "$X --coord 127.0.0.1:$CPORT"
  fi
  coord_down
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
  c1)  guard A:0,C:0; note_gpu1 C1; for m in ${2:-$METHODS}; do sess "expCONC_C1_${m}_s1" "$m" "$S1" ""; done ;;
  c2)  guard A:0,B:0,C:0,D:0; note_gpu1 C2; pair C2 "${2:-precopy_replay}" "$S2_C2" ;;
  c3a) guard A:0,A:1,C:0,C:1; for m in ${2:-$METHODS}; do pair C3a "$m" "$S2_C3A"; done ;;
  stage2)
    guard A:0,A:1,B:0,C:0,C:1,D:0,D:1
    for m in $METHODS; do coord_up "C3b_$m"; pair C3b "$m" "$S2_C3A" "--coord 127.0.0.1:$CPORT"; coord_down; done
    for arm in m3 nom3; do for conc in 0 1; do c4cell $arm $conc; done; done ;;
  c3b) guard A:0,A:1,C:0,C:1; for m in ${2:-$METHODS}; do coord_up "C3b_$m"; pair C3b "$m" "$S2_C3A" "--coord 127.0.0.1:$CPORT"; coord_down; done ;;
  c4)  guard A:0,B:0,C:0,C:1,D:0,D:1; c4cell "${2:?m3|nom3}" "${3:?0|1}" ;;
  wc_live)   # formal design F1, verification on real transfers (harness check, not an experiment cell): C3b placement,
             # OTTER / OTTER, dog, one shared 1 Gbps link, --coord_tail_mbps 100; S2 starts 8 s after S1, so S1's bulk ends
             # while S2 sends (S2 expected 500 -> 900 -> 1,000 Mbps); check_wc.py + conc_report NIC checks. About 20 min.
    guard A:0,A:1,C:0,C:1
    coord_up WC_live
    bar="results/evaluation/_barrier/WC_live_$(date +%Y%m%d-%H%M%S)"
    CW="--coord 127.0.0.1:$CPORT --coord_tail_mbps ${2:-100}"
    sess expCONC_WC_live_precopy_replay_s1 precopy_replay "$S1" "$bar" "$COMMON" "$CW" > /tmp/conc_wc_s1.log 2>&1 & p1=$!
    sess expCONC_WC_live_precopy_replay_s2 precopy_replay "$S2_C3A" "$bar" "$COMMON" "$CW --barrier_offset_s 8" > /tmp/conc_wc_s2.log 2>&1 & p2=$!
    wait $p1 $p2; tail -n 2 /tmp/conc_wc_s1.log; tail -n 2 /tmp/conc_wc_s2.log
    coord_down
    $PY tools/eval/check_wc.py --coord_log "$(ls -t results/evaluation/osdi/concurrency/coord_WC_live_*.jsonl | head -1)" \
      results/evaluation/expCONC_WC_live_precopy_replay_s1 results/evaluation/expCONC_WC_live_precopy_replay_s2 \
      --nic_cap_mbps 1000 | tee results/evaluation/osdi/concurrency/wc_live_check.txt ;;
  dry_coord)   # two dry sessions whose nodes sit on the same two sites (--coord_sites), through the coordinator
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    rm -rf results/evaluation/_dryrun_expCONC_drycoord_* results/evaluation/_barrier/drycoord_*
    for p in 29911 29921 29931 29941; do
      lb=$( [ $p = 29911 ] || [ $p = 29931 ] && echo A || echo B )
      $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $p --data_port $((p + 1)) --mss 0 --dry_run --dry_sink_mb 256 \
        --dry_service_s 0.05 --migration_chunk 30 --post_chunks 300 > "/tmp/conc_dryc_node_$p.log" 2>&1 &
    done
    log="results/evaluation/_dryrun_coord_$(date +%s).jsonl"
    $PY tools/eval/rate_coord.py serve --port 29961 --cap_mbps 1000 --log "$log" > /tmp/conc_dryc_coord.log 2>&1 &
    sleep 3
    bar="results/evaluation/_barrier/drycoord_$(date +%s)"; pids=""
    for i in 1 2; do
      n1=$((29891 + 20 * i)); n2=$((n1 + 10))
      $PY tools/eval/mobility_orchestrate.py --experiment "expCONC_drycoord_precopy_replay_s$i" --dry_run --mss 0 --dyn_probe 1 \
        --nodes A=127.0.0.1:$n1:$((n1 + 1)),B=127.0.0.1:$n2:$((n2 + 1)) --hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 300 \
        --max_run_s 600 --xb_horizon 20 --horizon_calls 40 --xb_policy_settings "$SETV" $OTTER --policies precopy_replay --rep_start 1 --reps 1 \
        --barrier "$bar:2" --coord 127.0.0.1:29961 --coord_sites A=siteA,B=siteB > "/tmp/conc_dryc_orch_$i.log" 2>&1 &
      pids="$pids $!"
    done
    wait $pids; sleep 1
    grep -h "barrier round\|done:" /tmp/conc_dryc_orch_1.log /tmp/conc_dryc_orch_2.log
    $PY tools/eval/conc_report.py --prefix _dryrun_ --dry --coord_log "$log" ;;
  dry_wc)   # formal design F1, tail-aware rate allocation (--coord_tail_mbps): two dry sessions on shared sites, 200 Mbps
            # (the Mac dry sender is not pacer-bound near 1 Gbps; on the testbed use wc_live); S2 starts
            # 1 s after S1 (S1 64 MB, S2 1,536 MB), so S1's bulk ends and S1 then closes while S2 still sends: 100 -> 180 -> 200 Mbps; check_wc.py compares each pacer's achieved rate with its allocation
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    TAIL=${2:-20}   # 10 % of the 200 Mbps dry cap (testbed: 100 of 1,000 Mbps)
    rm -rf results/evaluation/_dryrun_expCONC_drywc_* results/evaluation/_barrier/drywc_*
    for p in 29911 29921 29931 29941; do
      lb=$( [ $p = 29911 ] || [ $p = 29931 ] && echo A || echo B )
      mb=$( [ $p -lt 29930 ] && echo 64 || echo 1536 )   # S1 small, S2 large: S1's bulk ends, then S1 closes, while S2 still sends
      $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $p --data_port $((p + 1)) --mss 0 --dry_run --dry_sink_mb $mb \
        --dry_service_s 0.05 --migration_chunk 30 --post_chunks 3000 > "/tmp/conc_drywc_node_$p.log" 2>&1 &
    done
    log="results/evaluation/_dryrun_coordwc_$(date +%s).jsonl"
    $PY tools/eval/rate_coord.py serve --port 29963 --cap_mbps 200 --log "$log" > /tmp/conc_drywc_coord.log 2>&1 &
    sleep 3
    bar="results/evaluation/_barrier/drywc_$(date +%s)"; pids=""
    for i in 1 2; do
      n1=$((29891 + 20 * i)); n2=$((n1 + 10)); off=$([ $i = 2 ] && echo 1 || echo 0)
      $PY tools/eval/mobility_orchestrate.py --experiment "expCONC_drywc_precopy_replay_s$i" --dry_run --mss 0 --dyn_probe 1 \
        --nodes A=127.0.0.1:$n1:$((n1 + 1)),B=127.0.0.1:$n2:$((n2 + 1)) --hops 1 --tm 1e9 --bw 200 --migration_chunk 30 --post_chunks 3000 \
        --max_run_s 600 --xb_horizon 20 --horizon_calls 40 --xb_policy_settings "$SETV" $OTTER --policies precopy_replay --rep_start 1 --reps 1 \
        --barrier "$bar:2" --barrier_offset_s $off --coord 127.0.0.1:29963 --coord_sites A=siteA,B=siteB --coord_tail_mbps $TAIL \
        > "/tmp/conc_drywc_orch_$i.log" 2>&1 &
      pids="$pids $!"
    done
    wait $pids; sleep 1
    grep -h "done:" /tmp/conc_drywc_orch_1.log /tmp/conc_drywc_orch_2.log
    $PY tools/eval/check_wc.py --coord_log "$log" results/evaluation/_dryrun_expCONC_drywc_precopy_replay_s1 results/evaluation/_dryrun_expCONC_drywc_precopy_replay_s2 ;;
  dry_coord1)   # [tail_mbps] verification 2, live: one session (Fig. 11 Chain dry, M3 and every method) through the coordinator
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    log="results/evaluation/_dryrun_coord1_$(date +%s).jsonl"
    $PY tools/eval/rate_coord.py serve --port 29962 --cap_mbps 1000 --log "$log" > /tmp/conc_dryc1_coord.log 2>&1 & CP=$!
    sleep 1
    for x in ext m3; do
      for i in 0 1 2 3; do
        lb=$(echo ABCD | cut -c$((i + 1)))
        $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $((29911 + 10 * i)) --data_port $((29912 + 10 * i)) --mss 0 \
          --dry_run --dry_sink_mb 64 --dry_service_s 0.2 --migration_chunk 30 --post_chunks 800 > "/tmp/conc_dryc1_node_$lb.log" 2>&1 & NP="${NP:-} $!"
      done
      sleep 3
      if [ $x = ext ]; then P="full,recompute_full,precopy_replay"; XF=""; else P=precopy_replay; XF="$M3"; fi
      $PY tools/eval/mobility_orchestrate.py --experiment "expCONC_drychain_$x" --dry_run --mss 0 --dyn_probe 1 \
        --nodes A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942 \
        --coord_sites A=sA,B=sB,C=sC,D=sD --coord 127.0.0.1:29962 ${2:+--coord_tail_mbps $2} \
        --hops 3 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 800 --max_run_s 900 --xb_horizon 20 --horizon_calls 60 --move_times 12,24 \
        --xb_policy_settings "$SETV" $OTTER $XF --policies "$P" --rep_start 1 --reps 1 || echo "[CONC] dry chain $x: exit $?"
      kill $NP 2>/dev/null; wait $NP 2>/dev/null; NP=""
    done
    kill $CP 2>/dev/null
    grep -h "done:" results/evaluation/_dryrun_expCONC_drychain_*/ 2>/dev/null; ls -d results/evaluation/_dryrun_expCONC_drychain_*/policy=* | sed 's#.*/##'
    for d in results/evaluation/_dryrun_expCONC_drychain_*/policy=*; do $PY -c "import json,sys; s=json.load(open(sys.argv[1]+'/summary.json')); v=s.get('validation') or {}; print(sys.argv[1].split('/')[-1][:60], 'stop', s.get('stop_reason'), 'switchovers', s.get('n_switchovers'), 'verified', v.get('switchovers_verified', s.get('switchovers_verified')))" "$d"; done
    $PY tools/eval/test_rate_coord.py --live "$log" ;;
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
  *) echo "usage: $0 preflight|stage1|c1 [methods]|c2 [method]|c3a [methods]|stage2|c3b [methods]|c4 m3|nom3 0|1|dry|dry_coord|dry_coord1|dry_wc [tail_mbps]|wc_live [tail_mbps]"; exit 2 ;;
esac
