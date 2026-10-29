#!/usr/bin/env bash
# M3-S1 (osdi/m3s1/preregistration.md): network-level validation of lineage-aware progress forwarding. Restore nodes
# (no GPU) on elves-01..04, launched through the per-host agents; run on elves-01.
#   bash tools/eval/run_m3_s1.sh preflight   # agents, one commit, data present
#   bash tools/eval/run_m3_s1.sh main        # 48 runs at rho 1 (dog, bfly x 8 policies x 3 reps) + 6 descriptive dog rho-2 runs (~1.3 min each)
#   bash tools/eval/run_m3_s1.sh shakedown   # one rep of S0 and S3/rev per workload (4 runs), results under expM3S1_shk
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
COMMON="--launch --ts 14.05 --cap_mbps 1000 --max_run_s 240"
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    ls -l results/evaluation/osdi/m3s0/events_dog.json results/evaluation/osdi/m3s0/events_bfly.json results/evaluation/osdi/m3s0/calibration.json results/evaluation/osdi/m3e0/e0_report.json ;;
  shakedown)
    for wl in dog bfly; do
      $PY tools/eval/m3s1_orchestrate.py $COMMON --experiment expM3S1_shk --workload $wl --staging none,S3 --orders rev --rhos 1 --reps 1 || echo "[M3S1] shakedown $wl: exit $?"
    done ;;
  main)
    for wl in dog bfly; do
      $PY tools/eval/m3s1_orchestrate.py $COMMON --experiment expM3S1 --workload $wl --staging none,S1o,S1c,S2,S3 --orders fwd,rev --rhos 1 --reps 3 || echo "[M3S1] $wl: exit $?"
    done
    $PY tools/eval/m3s1_orchestrate.py $COMMON --experiment expM3S1 --workload dog --staging none,S3 --orders fwd --rhos 2 --reps 3 || echo "[M3S1] dog rho2: exit $?" ;;
  *) echo "usage: $0 preflight|shakedown|main"; exit 2 ;;
esac
