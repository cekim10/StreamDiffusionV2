#!/bin/bash
# Loopback regression of the shared planner refactor: replays, on 127.0.0.1 with four restore nodes, every configuration
# of the pre-refactor loopback runs kept under results/evaluation/_dryrun_{reg,prepos,a3,dissem,e2,fe}, writing to
# results/evaluation/_regress_planner/<group>/. Compare with tools/eval/compare_planner_regression.py.
#   PY=/path/to/python tools/eval/run_planner_regression.sh [group ...]     (groups: reg prepos a3 dissem e2 fe)
set -uo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-python3}"; OUT="${OUT:-_regress_planner}"; LOGD="${LOGD:-/tmp/planner_regression_nodes}"; mkdir -p "$LOGD"
NODES="A=127.0.0.1:29851:29852,B=127.0.0.1:29861:29862,C=127.0.0.1:29871:29872,D=127.0.0.1:29881:29882"
start_nodes() { pkill -f "tools/eval/restore_node.py" 2>/dev/null; sleep 0.5; i=0
  for L in A B C D; do "$PY" tools/eval/restore_node.py --label $L --bind 127.0.0.1 --ctl_port $((29851+10*i)) --data_port $((29852+10*i)) --mss 0 > "$LOGD/node_$L.log" 2>&1 & i=$((i+1)); done; sleep 2; }
orch() { start_nodes; "$PY" tools/eval/restore_orchestrate.py --nodes "$NODES" --mss 0 --no_resume --cap_mbps 100 "$@" 2>&1 | grep -E "^\[orch\] (prepos|restart|reuse|pp_star|fixed|star|line|tree|multipath|aware|done)|Traceback|rror:"; pkill -f "tools/eval/restore_node.py"; sleep 1; }
G="${*:-reg prepos a3 dissem e2 fe}"
for g in $G; do echo "== $g"; case $g in
  reg)    orch --experiment $OUT/reg --sink_bytes $((64<<20)) --ts 5.4 --sessions 1 --policies reuse_fixed,reuse_aware_in,restart --moves 1 --reps 1 --holder_mbps 25
          orch --experiment $OUT/reg --sink_bytes $((64<<20)) --ts 5.4 --sessions 1 --policies reuse_aware_in --moves 1 --reps 1 --prepos top1 --lookahead 3.8 --budget 1 --dests C --draws 1
          orch --experiment $OUT/reg --sink_bytes $((64<<20)) --ts 5.4 --sessions 4 --policies reuse_aware_in --moves 1 --reps 1 --prepos top1 --lookahead 3.8 --budget 0.5 --dests C --draws 1 --others_start 3.8 ;;
  prepos) orch --experiment $OUT/prepos --sink_bytes $((64<<20)) --ts 5.4 --sessions 1 --policies reuse_aware_in --moves 1 --reps 1 --prepos none,oracle,top1,proportional --lookahead 3.8 --budget 1 --dests B,C,D --draws 3 ;;
  a3)     orch --experiment $OUT/a3 --sink_bytes $((64<<20)) --ts 5.4 --sessions 4 --policies reuse_aware_in --moves 1 --reps 1 --prepos none,top1 --lookahead 3.8 --budget 0.5 --dests C --draws 1 --others_start 3.8 ;;
  dissem) orch --experiment $OUT/dissem --sink_bytes $((64<<20)) --ts 5.4 --dissem star,line,tree,multipath,aware --reps 1 ;;
  e2)     for EV in "D>=0.5:C:out=12.5" "" "D>=0.5:C:out=12.5;t=36:C:out=100"; do
            orch --experiment $OUT/e2 --sink_bytes $((256<<20)) --ts 21.5 --sessions 1 --policies reuse_dyn,reuse_aware_in --moves 2 --rhos 2 --reps 1 --cap_events "$EV"; done ;;
  fe)     orch --experiment $OUT/fe --sink_bytes $((128<<20)) --ts 10.7 --sessions 1 --policies restart,pp_star,fixed_line,fixed_tree,fixed_butterfly,reuse_aware_in,reuse_dyn --moves 3 --rhos 2 --reps 1
          orch --experiment $OUT/fe --sink_bytes $((128<<20)) --ts 10.7 --sessions 1 --policies pp_star,fixed_line,fixed_tree,fixed_butterfly,reuse_aware_in,reuse_dyn --moves 2 --rhos 2 --reps 1 --caps "B:out=12.5" ;;
esac; done
