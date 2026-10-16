#!/bin/bash
# D0: copy back the per-fragment node logs (node_X/fragments.csv) that restore nodes wrote on elves-02..04 for the
# completed network-level experiments. Read-only on the remote hosts; never overwrites an existing local file
# (rsync --ignore-existing); copies nothing else. Run on elves-01, then verify with
# tools/eval/verify_node_logs.py and commit.
#   REMOTE_USER=ckim151 REMOTE_REPO=StreamDiffusionV2 tools/eval/recover_node_logs.sh
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
U="${REMOTE_USER:-ckim151}"; R="${REMOTE_REPO:-StreamDiffusionV2}"
for pair in B:elves-02 C:elves-03 D:elves-04; do
  L=${pair%%:*}; H=${pair#*:}
  echo "== node $L from $H"
  rsync -a --ignore-existing --prune-empty-dirs \
    --include='restore_*/' --include='restore_*/policy=*/' --include='restore_*/plan=*/' \
    --include="restore_*/*/node_$L/" --include="restore_*/*/node_$L/fragments.csv" --exclude='*' \
    "$U@$H.be.ucsc.edu:$R/results/evaluation/" results/evaluation/
  echo "   local node_$L logs now: $(ls results/evaluation/restore_*/*/node_$L/fragments.csv 2>/dev/null | wc -l)"
done
du -ch results/evaluation/restore_*/*/node_[BCD]/fragments.csv 2>/dev/null | tail -1
