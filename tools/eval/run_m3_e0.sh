#!/usr/bin/env bash
# M3-E0 (osdi/m3e0/preregistration.md): repeated-mobility baseline of the frozen M1 / M2 (precopy_replay), no M3.
# XB3 / XB4 mobility (A -> B -> C -> D, trigger at call 30, T_m = T_s / rho with T_s = 14.05 s, 1 Gbps caps, elves-01..04
# GPU 0) x {dog, butterfly-feeding-slow-motion} seed 0 x rho {1, 2}; one run per configuration.
#   elves-01:  bash tools/eval/run_m3_e0.sh preflight     # agents, one commit, GPU 0 idle on A-D, workload files on B-D
#   elves-01:  bash tools/eval/run_m3_e0.sh orch          # 4 runs (needs GPU 0 idle on all four hosts)
#   elves-01:  bash tools/eval/run_m3_e0.sh crossversion  # offline cross-version classification (GPU 0, after orch)
#   Mac:       relay D's frame dumps (elves-04 -> Mac -> elves-02)
#   elves-02:  bash tools/eval/run_m3_e0.sh metrics       # continuity of the final migration (VD-3 frozen rules)
set -u
cd "$(dirname "$0")/../.."
FR=/home/ckim151/m3e0_frames
OUTD=results/evaluation/osdi/m3e0
COMMON="--launch --policies precopy_replay --hops 3 --bw 1000 --ts 14.05 --reps 1 --migration_chunk 30 --post_chunks 1500 --max_run_s 2400 --xb_horizon 100 --horizon_calls 180 --dyn_probe 4 --xb_policy_settings precopy_replay@thr=16:rl=1 --replay_window 12 --replay_lag 1 --replay_sink_sync --replay_retain --replay_reuse --dump_calls 260"
DOG_V=examples/original.mp4; DOG_P=examples/prompt.txt
BF_V=data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4; BF_P=data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt
# name | rho | video | prompt | metrics unit | metrics input | workload key
RUNS=(
  "dog_rho1|1|$DOG_V|$DOG_P|dog_s0|dog|dog"
  "dog_rho2|2|$DOG_V|$DOG_P|dog_s0|dog|dog"
  "bfly_rho1|1|$BF_V|$BF_P|butterfly-feeding-slow-motion_s0|butterfly-feeding-slow-motion|bfly"
  "bfly_rho2|2|$BF_V|$BF_P|butterfly-feeding-slow-motion_s0|butterfly-feeding-slow-motion|bfly"
)
PY=${PY:-python}
case "${1:-}" in
  preflight)
    $PY tools/eval/d0_remote.py status
    $PY tools/eval/d0_remote.py probe m3e0_data "ls -l $BF_V $BF_P $DOG_V $DOG_P; git rev-parse HEAD"
    cat results/evaluation/osdi/d0/m3e0_data/*.txt
    ls -l $BF_V $BF_P $DOG_V $DOG_P
    $PY tools/eval/d0_remote.py gpu_idle && echo "[M3E0] preflight: GPU 0 idle on A-D, one commit" ;;
  orch)
    for r in "${RUNS[@]}"; do
      IFS='|' read -r name rho v p unit inp wl <<< "$r"
      echo "[M3E0] === $name"
      $PY tools/eval/mobility_orchestrate.py --experiment "expM3E0_$name" $COMMON --rhos "$rho" --dump_frames "$FR/$name" \
        --node_extra="--video_path $v --prompt_file_path $p --seed 0" || echo "[M3E0] $name: orchestrator exit $?"
    done ;;
  crossversion)
    mkdir -p "$OUTD"
    for wl in dog bfly; do
      runs=""; v=""; p=""
      for r in "${RUNS[@]}"; do
        IFS='|' read -r name rho v_ p_ unit inp wk <<< "$r"
        [ "$wk" = "$wl" ] || continue
        d=$(ls -d results/evaluation/expM3E0_$name/policy=* 2>/dev/null | tail -1)
        [ -n "$d" ] && runs="$runs${runs:+,}$d"; v=$v_; p=$p_
      done
      $PY tools/eval/m3e0_crossversion.py --runs "$runs" --video_path "$v" --prompt_file_path "$p" --seed 0 --out "$OUTD/e0x_$wl.json" || echo "[M3E0] crossversion $wl: exit $?"
    done ;;
  metrics)
    mkdir -p "$OUTD"
    for r in "${RUNS[@]}"; do
      IFS='|' read -r name rho v p unit inp wl <<< "$r"
      for run in $(ls "$FR/$name" 2>/dev/null); do
        .venv/bin/python tools/eval/m1_live_metrics.py --dump_root "$FR/$name" --runs "$run" --unit "$unit" --input "$inp" --out_store OUT_D --ref_store REF_D \
          --out "$OUTD/e0_metrics_${name}.json" || echo "[M3E0] $name: metrics exit $?"
      done
    done ;;
  *) echo "usage: $0 preflight|orch|crossversion|metrics"; exit 2 ;;
esac
