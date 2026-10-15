#!/bin/bash
# Diagnostic (separate from the pre-registered A3): holder-bandwidth sensitivity of a wrongly placed 0.5 Sink under
# shared-source contention. N = 4, others start at s0's move (L = 10 s), top-1 -> B pre-positioning, true destination C,
# holder egress 62.5..1000 Mbps, restoration reuse_fixed and reuse_aware_in, with a none baseline per condition.
# 60 runs, ~75 min, on elves-01.
set -euo pipefail
cd "$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
R=tools/eval/run_restore_prepos.sh; export EXP="${EXP:-restore_holder_diag}" REPS="${REPS:-3}" DRAWS=1 BUDGET=0.5 LOOKAHEAD=10
for BH in ${HOLDERS:-62.5 125 250 500 1000}; do
  SESSIONS=4 OTHERS_START=10 DESTS=C PREPOS=none,top1 POLICY=reuse_fixed,reuse_aware_in HOLDER=$BH $R
done
