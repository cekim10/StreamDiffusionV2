#!/usr/bin/env bash
# Fig. 13 (osdi/fig13/preregistration.md): output fidelity after a verified cutover, as a quality-isolation experiment.
# One migration A -> B, trigger at call 30, 1 Gbps; every OTTER run switches at a fixed absolute call S
# (--replay_switch_calls S). 10 inputs x seeds 0, 1; seed 0 S = 70..79, seed 1 S = 70, 72, ..., 78; Full exact control
# per (input, seed); one OTTER repeat (seed 0, S = 74) per input on the OTHER pair (determinism + pair equivalence);
# D10: P-sink at S = 74 (--sink_switch_calls), seed 0. Record-only node flags --block_ck --fidelity_log.
# Two independent pairs: P1 = elves-01 / elves-02 (labels A, B), P2 = elves-03 / elves-04 (labelled A, B via --nodes).
# Experiments expF13_<input>_s<seed>_S<S> (OTTER, P-sink) and expF13_<input>_s<seed>_full.
#   elves-01:  bash tools/eval/run_fig13.sh preflight
#   elves-01:  bash tools/eval/run_fig13.sh first      # dog seed 0 S = 74 OTTER on P1 (rep 1) and P2 (rep 2) at once
#   elves-01:  python tools/eval/fig13_report.py --sanity
#   elves-01:  bash tools/eval/run_fig13.sh rest1      # P1's list (terminal 1)
#   elves-01:  bash tools/eval/run_fig13.sh rest2      # P2's list (terminal 2, at the same time)
#   local:     bash tools/eval/run_fig13.sh dry
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
L=data/loveu_tgve_2023
inp() {   # input key -> "video prompt" (the Fig. 5 pairs, tools/eval/run_sink_char.sh)
  case $1 in
    dog) echo "examples/original.mp4 examples/prompt.txt" ;;
    bird) echo "examples/bird.mp4 examples/bird_prompt.txt" ;;
    boxing) echo "examples/boxing.mp4 examples/boxing_prompt.txt" ;;
    train) echo "examples/train.mp4 examples/train_prompt.txt" ;;
    basketball) echo "$L/basketball-shot.mp4 $L/basketball-shot__object.txt" ;;
    hockey) echo "$L/ice-hockey.mp4 $L/ice-hockey__background.txt" ;;
    swimmer) echo "$L/swimmer.mp4 $L/swimmer__style.txt" ;;
    audi) echo "$L/audi-snow-trail.mp4 $L/audi-snow-trail__multiple.txt" ;;
    circus) echo "$L/circus-ball-act.mp4 $L/circus-ball-act__background.txt" ;;
    bfly) echo "$L/butterfly-feeding-slow-motion.mp4 $L/butterfly-feeding-slow-motion__background.txt" ;;
    *) echo "unknown input $1" >&2; exit 2 ;;
  esac
}
IN_P1="dog boxing hockey train circus"        # refresh 3.6 / 8.2 / 16.4 / 34.5 / 89.1 per 100 calls (Fig. 5)
IN_P2="bird basketball swimmer audi bfly"     # 3.6 / 9.1 / 22.7 / 53.6 / 128.2
S0="70 71 72 73 74 75 76 77 78 79"; S1="70 72 74 76 78"
SETV="precopy_sink@thr=256:rl=10;precopy_replay@thr=16:rl=1"
COMMON="--launch --hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 --post_chunks 160 --max_run_s 2400 --xb_horizon 101 --horizon_calls 130 --dyn_probe 4 --xb_policy_settings $SETV"
OTTER="--replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse"   # Fig. 7 OTTER flags
P2NODES="--nodes A=elves-03.be.ucsc.edu,B=elves-04.be.ucsc.edu --agent_hosts A=elves-03.be.ucsc.edu,B=elves-04.be.ucsc.edu"
guard() { $PY tools/eval/d0_remote.py gpu_idle --hosts "$1" || { echo "[F13] hosts not on one commit or GPU 0 busy ($1); run d0_remote.py pull first"; exit 1; }; }
pairargs() { if [ "$1" = P2 ]; then echo "$P2NODES"; fi; }
nodex() { set -- $(inp "$1") "$2"; echo "--video_path $1 --prompt_file_path $2 --seed $3 --block_ck --fidelity_log"; }
otter() {   # pair, input, seed, S, rep
  echo "[F13] === $1 OTTER $2 seed $3 S $4 rep $5"
  $PY tools/eval/mobility_orchestrate.py --experiment "expF13_$2_s$3_S$4" $COMMON $(pairargs "$1") $OTTER --policies precopy_replay \
    --replay_switch_calls "$4" --rep_start "$5" --reps 1 --node_extra="$(nodex "$2" "$3")" || echo "[F13] $1 OTTER $2 s$3 S$4 rep $5: exit $?"
}
full() {    # pair, input, seed
  echo "[F13] === $1 Full $2 seed $3"
  $PY tools/eval/mobility_orchestrate.py --experiment "expF13_$2_s$3_full" $COMMON $(pairargs "$1") $OTTER --policies full \
    --rep_start 1 --reps 1 --node_extra="$(nodex "$2" "$3")" || echo "[F13] $1 Full $2 s$3: exit $?"
}
psink() {   # pair, input (seed 0, S = 74)
  echo "[F13] === $1 P-sink $2 seed 0 S 74"
  $PY tools/eval/mobility_orchestrate.py --experiment "expF13_$2_s0_S74" $COMMON $(pairargs "$1") --policies precopy_sink \
    --sink_switch_calls 74 --rep_start 1 --reps 1 --node_extra="$(nodex "$2" 0)" || echo "[F13] $1 P-sink $2: exit $?"
}
rest() {    # pair, own inputs, the other pair's inputs (repeated here)
  local P=$1 own=$2 other=$3
  for s in $S0; do for x in $own; do
    [ "$x" = dog ] && [ "$s" = 74 ] && continue   # = the first run
    otter $P $x 0 $s 1
  done; done
  for s in $S1; do for x in $own; do otter $P $x 1 $s 1; done; done
  for x in $own; do full $P $x 0; full $P $x 1; psink $P $x; done
  for x in $other; do [ "$x" = dog ] || otter $P $x 0 74 2; done   # repeats of the other pair's inputs (dog's repeat = first on P2)
}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    guard A,B,C,D && echo "[F13] preflight: one commit, GPU 0 idle on A-D" ;;
  first)
    guard A,B,C,D
    otter P1 dog 0 74 1 > /tmp/f13_first_P1.log 2>&1 &
    otter P2 dog 0 74 2 > /tmp/f13_first_P2.log 2>&1 &
    wait; tail -n 3 /tmp/f13_first_P1.log /tmp/f13_first_P2.log ;;
  rest1)
    guard A,B; rest P1 "$IN_P1" "$IN_P2" ;;
  rest2)
    guard C,D; rest P2 "$IN_P2" "$IN_P1" ;;
  dry)
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    rm -rf results/evaluation/_dryrun_expF13_*
    for cond in otter70 otter79 full psink; do
      for i in 0 1; do
        lb=$(echo AB | cut -c$((i + 1)))
        $PY tools/eval/mobility_node.py --label $lb --bind 127.0.0.1 --ctl_port $((29911 + 10 * i)) --data_port $((29912 + 10 * i)) --mss 0 \
          --dry_run --dry_sink_mb 64 --dry_service_s 0.2 --migration_chunk 30 --post_chunks 160 --fidelity_log > "/tmp/f13_dry_node_$lb.log" 2>&1 &
      done
      sleep 3
      D="--dry_run --mss 0 --dyn_probe 1 --nodes A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922 --hops 1 --tm 1e9 --bw 1000 --migration_chunk 30 \
         --post_chunks 160 --max_run_s 900 --xb_horizon 101 --horizon_calls 130 --xb_policy_settings $SETV"
      case $cond in
        otter70) $PY tools/eval/mobility_orchestrate.py --experiment expF13_dog_s0_S70 $D $OTTER --policies precopy_replay --replay_switch_calls 70 --rep_start 1 --reps 1 ;;
        otter79) $PY tools/eval/mobility_orchestrate.py --experiment expF13_dog_s0_S79 $D $OTTER --policies precopy_replay --replay_switch_calls 79 --rep_start 1 --reps 1 ;;
        full)    $PY tools/eval/mobility_orchestrate.py --experiment expF13_dog_s0_full $D $OTTER --policies full --rep_start 1 --reps 1 ;;
        psink)   $PY tools/eval/mobility_orchestrate.py --experiment expF13_dog_s0_S74 $D --policies precopy_sink --sink_switch_calls 74 --rep_start 1 --reps 1 ;;
      esac || echo "[F13] dry $cond: exit $?"
      kill $(jobs -p) 2>/dev/null; wait
    done
    $PY tools/eval/fig13_report.py --prefix _dryrun_ --dry --sanity ;;
  *) echo "usage: $0 preflight|first|rest1|rest2|dry"; exit 2 ;;
esac
