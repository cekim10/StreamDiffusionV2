#!/bin/bash
# D0 GPU correctness shakedown (NOT Experiment D): one representative configuration per test on elves-01..04, GPU 0,
# 1 Gbps, dog workload seed 0 k = 2. All four hosts must be on the same commit and GPU 0 idle. ~30-40 min.
# Results: results/evaluation/d0_shakedown/. Review before any sweep.
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
EXP=d0_shakedown; LOG="results/evaluation/$EXP/_launch_logs"; mkdir -p "$LOG"; STAMP="$(date +%Y%m%d-%H%M%S)"
TS="${TS:-14.05}"   # measured T_s at 1 Gbps (Phase 1)
O="$PY tools/eval/mobility_orchestrate.py --launch --experiment $EXP --bw 1000 --post_chunks 300"
# Each line launches the four node processes (model load + baseline) and shuts them down at the end.
# 1. single migration (Sink verification and binding)
$O --policies reuse_dyn --hops 1 --tm 1e9 2>&1 | tee -a "$LOG/orch_$STAMP.log"
# 2-4. repeated migration with progress preservation (M1 only, M1+M2, OTTER at moves, OTTER event-driven)
$O --policies restart,split,reuse_aware_in,reuse_dyn --hops 3 --ts "$TS" --rhos 2 2>&1 | tee -a "$LOG/orch_$STAMP.log"
# 5. event-driven re-planning after network degradation (C egress -> 62.5 Mbps when D holds 50 %)
$O --policies reuse_aware_in,reuse_dyn --hops 3 --ts "$TS" --rhos 2 --cap_events "D>=0.5:C:out=62.5" 2>&1 | tee -a "$LOG/orch_$STAMP.log"
# 6. correct and incorrect proactive placement (p = 0.6/0.3/0.1 for B/C/D; L = 10 s; b = 1 Sink)
$O --policies reuse_dyn --path A,B --tm 1e9 --prepos top1 --lookahead 10 --budget 1 2>&1 | tee -a "$LOG/orch_$STAMP.log"
$O --policies reuse_dyn --path A,C --tm 1e9 --prepos top1 --lookahead 10 --budget 1 2>&1 | tee -a "$LOG/orch_$STAMP.log"
