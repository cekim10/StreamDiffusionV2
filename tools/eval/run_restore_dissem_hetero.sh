#!/bin/bash
# Experiment B heterogeneous subset: five dissemination plans x {B_f = 500, B_f = 125, B_s = 250 Mbps} x 3 reps (45 runs,
# ~1 h). ALL FOUR HOSTS must be on the same commit. Run on elves-01.
set -euo pipefail
cd "$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
R=tools/eval/run_restore_dissem.sh; export EXP="${EXP:-restore_dissem_hetero}" REPS="${REPS:-3}"
FWD=500 $R
FWD=125 $R
SOURCE=250 $R
