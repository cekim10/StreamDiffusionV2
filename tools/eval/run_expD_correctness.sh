#!/bin/bash
# Experiment D: focused GPU correctness tests of the capabilities added after D0 (NOT the Experiment D sweep). One
# representative configuration per capability on elves-01..04, GPU 0, 1 Gbps, dog seed 0 k = 2, then the 9 D0 shakedown
# runs again (regression of the existing shakedown). Pass conditions: tools/eval/check_expD_correctness.py (written
# before the runs). Results: results/evaluation/expD_correctness/ and results/evaluation/d0_shakedown_rerun/.
# All four hosts on one commit; before every run GPU 0 must be idle on all four hosts. ~2-2.5 h.
#   tools/eval/run_expD_correctness.sh [test ...]   (full_single full_repeated cold_single cold_repeated revisit hybrid cold_dest placement native d0_rerun)
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
EXP=expD_correctness; LOG="results/evaluation/$EXP/_launch_logs"; mkdir -p "$LOG"; STAMP="$(date +%Y%m%d-%H%M%S)"
TS="${TS:-14.05}"   # measured T_s at 1 Gbps (Phase 1)
WAIT_S="${WAIT_S:-1800}"
idle() { local t0=$SECONDS; until "$PY" tools/eval/d0_remote.py gpu_idle; do
  [ $((SECONDS - t0)) -ge "$WAIT_S" ] && { echo "[expD] GPU 0 not idle after ${WAIT_S}s; stopping"; exit 3; }; sleep 60; done; }
run() { idle; "$PY" tools/eval/mobility_orchestrate.py --launch --experiment "${E:-$EXP}" --bw 1000 --post_chunks 300 "$@" 2>&1 | tee -a "$LOG/orch_$STAMP.log"; }
T="${*:-full_single full_repeated cold_single cold_repeated revisit hybrid cold_dest placement native d0_rerun}"
for t in $T; do echo "== $t"; case $t in
  # A. Full migration: single (consistency with the Phase 1 single-handoff `full`) and repeated A->B->C->D at rho 2
  full_single)   run --policies full --hops 1 --tm 1e9 ;;
  full_repeated) run --policies full --hops 3 --ts "$TS" --rhos 2 ;;
  # B. Cold restart: single and repeated (same move schedule as OTTER)
  cold_single)   run --policies cold --hops 1 --tm 1e9 ;;
  cold_repeated) run --policies cold --hops 3 --ts "$TS" --rhos 2 ;;
  # C. Revisit A->B->C->D->B at rho 2: M1 only, M1 + M2, OTTER at moves, OTTER event-driven
  revisit)       run --policies restart,split,reuse_aware_in,reuse_dyn --path A,B,C,D,B --ts "$TS" --rhos 2 ;;
  # D. Hybrid scenario E: one GPU session + three network-level sessions (restore_node.py) sharing A's egress
  hybrid)        run --policies restart,split,reuse_dyn --hops 3 --ts "$TS" --rhos 2 --hybrid_net 3 ;;
  # E. OTTER cold destination: B is started after the trigger (needs B's reference cache, written by any earlier warm
  #    run above with --post_chunks 300)
  cold_dest)     run --policies reuse_dyn --hops 1 --tm 1e9 --cold_dest ;;
  # scenarios C/D policies not covered by the D0 shakedown: M1 + M2 without placement and with top-1 (incorrect: A->C),
  # and the oracle (destination known at the trigger) with OTTER event-driven restoration (A->B)
  placement)     run --policies split --path A,C --tm 1e9 --prepos none --lookahead 10 --budget 1
                 run --policies split --path A,C --tm 1e9 --prepos top1 --lookahead 10 --budget 1
                 run --policies reuse_dyn --path A,B --tm 1e9 --prepos oracle --lookahead 10 --budget 1 ;;
  # scenario A's unshaped condition (~9.4 Gbps): Full migration and OTTER event-driven
  native)        run --policies full,reuse_dyn --hops 1 --tm 1e9 --bw 0 ;;
  # the existing D0 GPU shakedown (9 runs), re-run on this commit as a regression
  d0_rerun)      E=d0_shakedown_rerun run --policies reuse_dyn --hops 1 --tm 1e9
                 E=d0_shakedown_rerun run --policies restart,split,reuse_aware_in,reuse_dyn --hops 3 --ts "$TS" --rhos 2
                 E=d0_shakedown_rerun run --policies reuse_aware_in,reuse_dyn --hops 3 --ts "$TS" --rhos 2 --cap_events "D>=0.5:C:out=62.5"
                 E=d0_shakedown_rerun run --policies reuse_dyn --path A,B --tm 1e9 --prepos top1 --lookahead 10 --budget 1
                 E=d0_shakedown_rerun run --policies reuse_dyn --path A,C --tm 1e9 --prepos top1 --lookahead 10 --budget 1 ;;
  *) echo "unknown test $t"; exit 2 ;;
esac; done
