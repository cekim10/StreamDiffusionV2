#!/bin/bash
# Phase 0 orchestration (run from any elves host that can ssh to the others without a password).
#   tools/eval/run_netcal.sh                      # 5 patterns x REPS=5, 1 GiB per flow, MSS 1400
#   REPS=3 BYTES=$((512*1024*1024)) tools/eval/run_netcal.sh
#   MSS=0 PATTERNS="1" REPS=1 tools/eval/run_netcal.sh   # control: kernel-default MSS (expected to stall; use timeout)
# Hosts are logical A..D = elves-01..04. Each pattern: receivers first, then senders in parallel.
set -euo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"
A="${A:-elves-01.be.ucsc.edu}"; B="${B:-elves-02.be.ucsc.edu}"; C="${C:-elves-03.be.ucsc.edu}"; D="${D:-elves-04.be.ucsc.edu}"
REPS="${REPS:-5}"; BYTES="${BYTES:-$((1024*1024*1024))}"; MSS="${MSS:-1400}"; PORT="${PORT:-29800}"
PATTERNS="${PATTERNS:-1 2 3 4 5}"
PY="${PY:-$ROOT_DIR/.venv/bin/python}"
REMOTE_ROOT="${REMOTE_ROOT:-$ROOT_DIR}"   # repo path on the other hosts (same by default)
TIMEOUT="${TIMEOUT:-600}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="results/evaluation/network_calibration/mss=${MSS}_bytes=${BYTES}_${STAMP}"
mkdir -p "$OUT"
echo "git: $(git rev-parse HEAD)" > "$OUT/git_commit.txt"

remote() { # host, command...
  local h="$1"; shift
  ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$h" "cd $REMOTE_ROOT && $*"
}

run_pattern() { # name receiver_host nflows sender_host... (senders all target receiver_host)
  local name="$1" recv="$2" nflows="$3"; shift 3
  local pdir="$OUT/$name"; mkdir -p "$pdir"
  for rep in $(seq 1 "$REPS"); do
    local rdir="$pdir/rep$rep"; mkdir -p "$rdir"
    echo "[netcal] $name rep $rep: receiver $recv, senders: $*"
    remote "$recv" "timeout $TIMEOUT $PY tools/eval/netcal.py --role receiver --port $PORT --flows $nflows --mss $MSS --tag $name --out $REMOTE_ROOT/$rdir" > "$rdir/receiver.log" 2>&1 &
    local rpid=$!
    sleep 2
    local spids=()
    for s in "$@"; do
      remote "$s" "timeout $TIMEOUT $PY tools/eval/netcal.py --role sender --host $recv --port $PORT --bytes $BYTES --mss $MSS --tag $name --out $REMOTE_ROOT/$rdir" > "$rdir/sender_$s.log" 2>&1 &
      spids+=($!)
    done
    for p in "${spids[@]}"; do wait "$p" || echo "[netcal] sender failed (see logs)"; done
    wait "$rpid" || echo "[netcal] receiver failed (see logs)"
    sleep 1
  done
}

run_pattern_multi_receiver() { # name sender_host receiver_host... (one sender fans out to several receivers)
  local name="$1" send="$2"; shift 2
  local pdir="$OUT/$name"; mkdir -p "$pdir"
  for rep in $(seq 1 "$REPS"); do
    local rdir="$pdir/rep$rep"; mkdir -p "$rdir"
    echo "[netcal] $name rep $rep: sender $send -> receivers: $*"
    local rpids=()
    for r in "$@"; do
      remote "$r" "timeout $TIMEOUT $PY tools/eval/netcal.py --role receiver --port $PORT --flows 1 --mss $MSS --tag $name --out $REMOTE_ROOT/$rdir" > "$rdir/receiver_$r.log" 2>&1 &
      rpids+=($!)
    done
    sleep 2
    local spids=()
    for r in "$@"; do
      remote "$send" "timeout $TIMEOUT $PY tools/eval/netcal.py --role sender --host $r --port $PORT --bytes $BYTES --mss $MSS --tag $name --out $REMOTE_ROOT/$rdir" > "$rdir/sender_to_$r.log" 2>&1 &
      spids+=($!)
    done
    for p in "${spids[@]}"; do wait "$p" || echo "[netcal] sender failed"; done
    for p in "${rpids[@]}"; do wait "$p" || echo "[netcal] receiver failed"; done
    sleep 1
  done
}

for pat in $PATTERNS; do
  case "$pat" in
    1) run_pattern "p1_A_to_D" "$D" 1 "$A" ;;
    2) run_pattern "p2_A_to_B" "$B" 1 "$A" ;;
    3) run_pattern_multi_receiver "p3_A_to_B_and_C" "$A" "$B" "$C" ;;
    4) run_pattern "p4_A_B_to_D" "$D" 2 "$A" "$B" ;;
    5) run_pattern "p5_A_B_C_to_D" "$D" 3 "$A" "$B" "$C" ;;
  esac
done
# collect receiver/sender JSON from the remote hosts (same path on every host by default)
for h in "$A" "$B" "$C" "$D"; do
  rsync -a --ignore-existing "$h:$REMOTE_ROOT/$OUT/" "$OUT/" 2>/dev/null || true
done
"$PY" tools/eval/aggregate_netcal.py --root results/evaluation/network_calibration
