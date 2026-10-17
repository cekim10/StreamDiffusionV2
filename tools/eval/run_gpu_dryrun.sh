#!/bin/bash
# Protocol test of the GPU harness (no torch): mobility_node.py processes in --dry_run mode (fake Sink, sleep-based
# generation) on 127.0.0.1 at 100 Mbps. D0 scenarios + the Experiment D capabilities (full migration, cold restart,
# revisit, hybrid scenario E, OTTER cold destination). Results go to results/evaluation/_dryrun_d0_gpu/. Never reported.
#   PY=/path/to/python tools/eval/run_gpu_dryrun.sh [scenario ...]
set -uo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-python3}"; LOGD="${LOGD:-/tmp/d0_gpu_dryrun}"; mkdir -p "$LOGD"
NODES="A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942"
NET="A=127.0.0.1:29951:29952,B=127.0.0.1:29961:29962,C=127.0.0.1:29971:29972,D=127.0.0.1:29981:29982"
TS=${TS:-5.4}   # T_s of the fake Sink at 100 Mbps (64 MiB: 5.4 s; 256 MiB: 21.5 s)
DRY="--dry_sink_mb ${DRY_MB:-64} --dry_service_s 0.2"
stop_all() { pkill -f "tools/eval/mobility_node.py" 2>/dev/null; pkill -f "tools/eval/restore_node.py" 2>/dev/null; sleep 1; }
start_nodes() { stop_all; i=0
  for L in A B C D; do
    if [[ " ${SKIP:-} " != *" $L "* ]]; then
      "$PY" tools/eval/mobility_node.py --label $L --bind 127.0.0.1 --ctl_port $((29911+10*i)) --data_port $((29912+10*i)) --mss 0 --dry_run $DRY --post_chunks ${POST:-400} > "$LOGD/node_$L.log" 2>&1 &
    fi; i=$((i+1)); done
  if [ -n "${HYB:-}" ]; then i=0; for L in A B C D; do
    "$PY" tools/eval/restore_node.py --label $L --bind 127.0.0.1 --ctl_port $((29951+10*i)) --data_port $((29952+10*i)) --mss 0 > "$LOGD/net_$L.log" 2>&1 & i=$((i+1)); done; fi
  sleep 2; }
orch() { start_nodes; "$PY" tools/eval/mobility_orchestrate.py --dry_run --nodes "$NODES" --net_nodes "$NET" --mss 0 --bw 100 --experiment d0_gpu --tail_calls 4 --max_run_s ${MAXRUN:-120} \
           --post_chunks ${POST:-400} --dry_node_args "$DRY" "$@" 2>&1 | grep -E "after final move|Traceback|rror:|done:|restored [0-9]"; stop_all; }
S="${*:-single repeated degrade prepos_ok prepos_wrong full_single full_repeated cold_repeated revisit hybrid cold_dest placement native}"
for sc in $S; do echo "== $sc"; case $sc in
  single)        orch --policies reuse_dyn --hops 1 --tm 1e9 ;;
  repeated)      orch --policies restart,split,reuse_aware_in,reuse_dyn --hops 3 --ts $TS --rhos 2 ;;
  degrade)       orch --policies split,reuse_aware_in,reuse_dyn --hops 3 --ts $TS --rhos 2 --cap_events "D>=0.5:C:out=12.5" ;;
  prepos_ok)     orch --policies reuse_dyn --path A,B --tm 1e9 --prepos top1 --lookahead 4 --budget 1 ;;
  prepos_wrong)  orch --policies reuse_dyn --path A,C --tm 1e9 --prepos top1 --lookahead 4 --budget 1 ;;
  full_single)   orch --policies full --hops 1 --tm 1e9 ;;
  full_repeated) orch --policies full --hops 3 --ts $TS --rhos 2 ;;
  cold_repeated) orch --policies cold --hops 3 --ts $TS --rhos 2 --cold_tail_calls 20 ;;
  revisit)       orch --policies restart,split,reuse_aware_in,reuse_dyn --path A,B,C,D,B --ts $TS --rhos 2 ;;
  hybrid)        HYB=1 MAXRUN=200 orch --policies restart,split,reuse_dyn --hops 3 --ts $TS --rhos 2 --hybrid_net 3 --net_grace_s 60 ;;
  cold_dest)     SKIP="B C D" orch --policies reuse_dyn --hops 1 --tm 1e9 --cold_dest ;;
  placement)     orch --policies split --path A,C --tm 1e9 --prepos none --lookahead 4 --budget 1
                 orch --policies split --path A,C --tm 1e9 --prepos top1 --lookahead 4 --budget 1
                 orch --policies reuse_dyn --path A,B --tm 1e9 --prepos oracle --lookahead 4 --budget 1 ;;
  native)        orch --policies full,reuse_dyn --hops 1 --tm 1e9 --bw 0 ;;
esac; done
