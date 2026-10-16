#!/bin/bash
# D0: copy back the per-fragment node logs (node_X/fragments.csv) that restore nodes wrote on elves-02..04 for the
# completed network-level experiments, through the per-host agents (no ssh between the testbed hosts). Read-only on
# the remote hosts; never overwrites an existing local file; copies nothing else. Run on elves-01, then verify with
# tools/eval/verify_node_logs.py and commit.
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
"$PY" tools/eval/d0_remote.py recover
for L in B C D; do echo "local node_$L logs: $(ls results/evaluation/restore_*/*/node_$L/fragments.csv 2>/dev/null | wc -l)"; done
du -ch results/evaluation/restore_*/*/node_[BCD]/fragments.csv 2>/dev/null | tail -1
