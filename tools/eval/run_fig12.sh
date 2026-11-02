#!/usr/bin/env bash
# Fig. 12a (osdi/fig12/preregistration.md, DRAFT): bandwidth sensitivity of one migration A -> B at call 30, the Fig. 7
# protocol (Full, Llumnix-style P-full, ServerlessLLM-style R-full, OTTER; Fig. 7 flags) at 0.25 / 0.5 / 1 / 2.5 Gbps and
# native (unshaped, --bw 0). Experiments expF12_<w>_bw<B> (B in Mbps, 0 = native). Two independent pairs (Fig. 13 style):
# P1 = elves-01 / elves-02 runs dog, P2 = elves-03 / elves-04 (labelled A, B via --nodes) runs butterfly (D2).
# Reps are interleaved over bandwidths and methods (rep r: every bandwidth, every method, then rep r + 1).
#   elves-01:  bash tools/eval/run_fig12.sh preflight
#   elves-01:  bash tools/eval/run_fig12.sh first      # OTTER at the two extremes: dog 0.25 Gbps on P1 and bfly native on P2, at once
#   elves-01:  python tools/eval/fig12_report.py --sanity
#   elves-01:  bash tools/eval/run_fig12.sh rest1      # P1 (terminal 1)
#   elves-01:  bash tools/eval/run_fig12.sh rest2      # P2 (terminal 2, at the same time)
#   local:     bash tools/eval/run_fig12.sh dry
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
REPS=${REPS:-3}                                   # D3
BWS=${BWS:-"250 500 1000 2500 0"}                 # Mbps; 0 = native (D1)
SETV="precopy_full@thr=256:rl=10;recompute_full@lag=1:rl=1;precopy_replay@thr=16:rl=1"   # Fig. 7 (XB freeze; M1 E3-E6)
COMMON="--launch --hops 1 --tm 1e9 --migration_chunk 30 --post_chunks 1500 --max_run_s 2400 --xb_horizon 100 --horizon_calls 130 --dyn_probe 4"
OTTER="--replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse"   # Fig. 7 OTTER flags
ALL=full,precopy_full,recompute_full,precopy_replay
DOG="--video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0"
BF="--video_path data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4 --prompt_file_path data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt --seed 0"
P2NODES="--nodes A=elves-03.be.ucsc.edu,B=elves-04.be.ucsc.edu --agent_hosts A=elves-03.be.ucsc.edu,B=elves-04.be.ucsc.edu"
guard() { $PY tools/eval/d0_remote.py gpu_idle --hosts "$1" || { echo "[F12] hosts not on one commit or GPU 0 busy ($1); run d0_remote.py pull first"; exit 1; }; }
pairargs() { if [ "$1" = P2 ]; then echo "$P2NODES"; fi; }
wl() { if [ "$1" = dog ]; then echo "$DOG"; else echo "$BF"; fi; }
orch() {   # pair, workload, bw, policies, rep
  echo "[F12] === $1 $2 bw $3 $4 rep $5"
  $PY tools/eval/mobility_orchestrate.py --experiment "expF12_$2_bw$3" $COMMON --bw "$3" $(pairargs "$1") --xb_policy_settings "$SETV" $OTTER \
    --policies "$4" --rep_start "$5" --reps 1 --node_extra="$(wl "$2")" || echo "[F12] $1 $2 bw $3 $4 rep $5: exit $?"
}
rest() {   # pair, workload, first-run bandwidth (its OTTER rep 1 is already done)
  local P=$1 w=$2 fb=$3
  for rep in $(seq 1 "$REPS"); do
    for bw in $BWS; do
      if [ "$rep" = 1 ] && [ "$bw" = "$fb" ]; then orch "$P" "$w" "$bw" full,precopy_full,recompute_full 1
      else orch "$P" "$w" "$bw" "$ALL" "$rep"; fi
    done
  done
}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    $PY tools/eval/d0_remote.py codecs
    guard A,B,C,D && echo "[F12] preflight: one commit, GPU 0 idle on A-D, codecs ok" ;;
  first)
    guard A,B,C,D
    orch P1 dog 250 precopy_replay 1 > /tmp/f12_first_P1.log 2>&1 &
    orch P2 bfly 0 precopy_replay 1 > /tmp/f12_first_P2.log 2>&1 &
    wait; tail -3 /tmp/f12_first_P1.log /tmp/f12_first_P2.log ;;
  rest1)
    guard A,B; rest P1 dog 250 ;;
  rest2)
    guard C,D; rest P2 bfly 0 ;;
  dry)
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    rm -rf results/evaluation/_dryrun_expF12_*
    for bw in 250 0; do
      for i in 0 1; do
        lb=$(echo AB | cut -c$((i + 1)))
        $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $((29911 + 10 * i)) --data_port $((29912 + 10 * i)) --mss 0 \
          --dry_run --dry_sink_mb 64 --dry_service_s 0.2 --migration_chunk 30 --post_chunks 400 > "/tmp/f12_dry_node_$lb.log" 2>&1 &
      done
      sleep 3
      $PY tools/eval/mobility_orchestrate.py --experiment "expF12_dog_bw$bw" --dry_run --mss 0 --dyn_probe 1 \
        --nodes A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922 --hops 1 --tm 1e9 --bw "$bw" --migration_chunk 30 --post_chunks 400 \
        --max_run_s 600 --xb_horizon 20 --horizon_calls 40 --xb_policy_settings "$SETV" $OTTER --policies "$ALL" --rep_start 1 --reps 1 || echo "[F12] dry bw $bw: exit $?"
      kill $(jobs -p) 2>/dev/null; wait
    done
    $PY tools/eval/fig12_report.py --prefix _dryrun_ --dry --sanity ;;
  *) echo "usage: $0 preflight|first|rest1|rest2|dry"; exit 2 ;;
esac
