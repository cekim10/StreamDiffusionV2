#!/bin/bash
# Start the per-host experiment agent in a detached tmux session (idempotent). Run from the repo root on each host.
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
PORT="${PORT:-29900}"; PY="${PY:-$ROOT_DIR/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
mkdir -p results/evaluation/_agent
if tmux has-session -t evalagent 2>/dev/null; then
  if [ "${RESTART:-0}" = "1" ]; then tmux kill-session -t evalagent; sleep 1; else echo "[agent] already running (tmux session evalagent); RESTART=1 to restart"; exit 0; fi
fi
tmux new-session -d -s evalagent "cd $ROOT_DIR && $PY tools/eval/agent.py --port $PORT 2>&1 | tee -a results/evaluation/_agent/agent_$(hostname).log"
sleep 1; tmux capture-pane -pt evalagent | tail -2
