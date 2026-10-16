#!/bin/bash
# D0 protocol test of the GPU harness with the shared planner: four mobility_node.py processes in --dry_run mode (no torch,
# fake 64 MiB Sink, sleep-based generation) on 127.0.0.1, then the six D0 shakedown scenarios at 100 Mbps.
# Results go to results/evaluation/_dryrun_d0_gpu/. Never used for reported results.
#   PY=/path/to/python tools/eval/run_gpu_dryrun.sh [scenario ...]   (single repeated degrade prepos_ok prepos_wrong)
set -uo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-python3}"; LOGD="${LOGD:-/tmp/d0_gpu_dryrun}"; mkdir -p "$LOGD"
NODES="A=127.0.0.1:29911:29912,B=127.0.0.1:29921:29922,C=127.0.0.1:29931:29932,D=127.0.0.1:29941:29942"
TS=${TS:-5.4}   # T_s of the fake Sink at 100 Mbps (64 MiB: 5.4 s; 256 MiB: 21.5 s)
start_nodes() { pkill -f "tools/eval/mobility_node.py" 2>/dev/null; sleep 0.5; i=0
  for L in A B C D; do "$PY" tools/eval/mobility_node.py --label $L --bind 127.0.0.1 --ctl_port $((29911+10*i)) --data_port $((29912+10*i)) --mss 0 --dry_run --dry_sink_mb ${DRY_MB:-64} --dry_service_s 0.2 --post_chunks ${POST:-400} > "$LOGD/node_$L.log" 2>&1 & i=$((i+1)); done; sleep 2; }
orch() { start_nodes; "$PY" tools/eval/mobility_orchestrate.py --dry_run --nodes "$NODES" --mss 0 --bw 100 --experiment d0_gpu --tail_calls 4 --max_run_s 120 "$@" 2>&1 \
           | grep -E "after final move|Traceback|rror:|done:"; pkill -f "tools/eval/mobility_node.py"; sleep 1; }
S="${*:-single repeated degrade prepos_ok prepos_wrong}"
for sc in $S; do echo "== $sc"; case $sc in
  single)       orch --policies reuse_dyn --hops 1 --tm 1e9 ;;
  repeated)     orch --policies restart,split,reuse_aware_in,reuse_dyn --hops 3 --ts $TS --rhos 2 ;;
  degrade)      orch --policies split,reuse_aware_in,reuse_dyn --hops 3 --ts $TS --rhos 2 --cap_events "D>=0.5:C:out=12.5" ;;
  prepos_ok)    orch --policies reuse_dyn --path A,B --tm 1e9 --prepos top1 --lookahead 4 --budget 1 ;;
  prepos_wrong) orch --policies reuse_dyn --path A,C --tm 1e9 --prepos top1 --lookahead 4 --budget 1 ;;
esac; done
