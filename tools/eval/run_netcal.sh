#!/bin/bash
# Phase 0 (agent-based; inter-host ssh does not work on the elves data path).
# 1) on EVERY host, once, inside tmux, from the repo root:   tools/eval/start_agent.sh
# 2) from elves-01:                                           tools/eval/run_netcal.sh
#    control run with kernel-default MSS (expected to stall): MSS=0 PATTERNS="2" REPS=1 TIMEOUT=120 tools/eval/run_netcal.sh
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"
exec "$PY" tools/eval/netcal_orchestrate.py --patterns "${PATTERNS:-1 2 3 4 5}" --reps "${REPS:-5}" --bytes "${BYTES:-$((1024*1024*1024))}" \
  --mss "${MSS:-1400}" --timeout "${TIMEOUT:-600}" --py "${REMOTE_PY:-auto}" ${HOSTS:+--hosts "$HOSTS"} ${IFACE:+--iface "$IFACE"}
