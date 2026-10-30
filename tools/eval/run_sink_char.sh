#!/usr/bin/env bash
# Sink-evolution characterization for Background Fig. 5 (results/state_migration/figures/background/m123/CAPTIONS.md):
# the per-call Sink lineage table (refresh writes, ordered RoPE shifts, 360 per-block checksums, lineage-rule check) of
# every available video input, recorded with the M3-S0 dump tool (data extraction only; nothing in the migration path
# runs). Same settings as osdi/m3s0/events_{dog,bfly}.json: seed 0, calls 25-140; fragment hashes skipped (not used).
# The workload list is fixed here before any run: every input in examples/ and data/loveu_tgve_2023/ with its one
# prompt file (20 inputs); dog and butterfly are already recorded (osdi/m3s0) and are not re-run.
# Analysis fixed before the runs (tools/eval/plot_background_m123.py): snapshot = call 30 (the migration trigger of every
# experiment), entry state at version age 50 calls for Fig. 5a, ages 0-110 for Fig. 5b.
#   elves-0K:  bash tools/eval/run_sink_char.sh <shard 0-3> 4      # one shard per host, GPU 0 idle
#   then push results/evaluation/osdi/sinkchar/events_*.json
set -u
cd "$(dirname "$0")/../.."
OUTD=results/evaluation/osdi/sinkchar
L=data/loveu_tgve_2023
# key | video | prompt
RUNS=(
  "bird|examples/bird.mp4|examples/bird_prompt.txt"
  "boxing|examples/boxing.mp4|examples/boxing_prompt.txt"
  "train|examples/train.mp4|examples/train_prompt.txt"
  "aircraft|$L/aircraft-landing.mp4|$L/aircraft-landing__style.txt"
  "audi|$L/audi-snow-trail.mp4|$L/audi-snow-trail__multiple.txt"
  "basketball|$L/basketball-shot.mp4|$L/basketball-shot__object.txt"
  "circus|$L/circus-ball-act.mp4|$L/circus-ball-act__background.txt"
  "cows|$L/cows-grazing.mp4|$L/cows-grazing__object.txt"
  "cricket|$L/cricket-bat-practice.mp4|$L/cricket-bat-practice__style.txt"
  "earth|$L/earth-full-view.mp4|$L/earth-full-view__multiple.txt"
  "eiffel|$L/eiffel-flyover.mp4|$L/eiffel-flyover__multiple.txt"
  "hurdles|$L/hurdles-race.mp4|$L/hurdles-race__multiple.txt"
  "hockey|$L/ice-hockey.mp4|$L/ice-hockey__background.txt"
  "juggling|$L/juggling-selfie.mp4|$L/juggling-selfie__object.txt"
  "mbike|$L/mbike-trick.mp4|$L/mbike-trick__style.txt"
  "seagull|$L/seagull-flying.mp4|$L/seagull-flying__background.txt"
  "street|$L/street-artist-painting.mp4|$L/street-artist-painting__object.txt"
  "swimmer|$L/swimmer.mp4|$L/swimmer__style.txt"
)
SHARD=${1:?shard index}; NSH=${2:?number of shards}
PY=${PY:-python}
mkdir -p "$OUTD"
for i in "${!RUNS[@]}"; do
  [ $((i % NSH)) -eq "$SHARD" ] || continue
  IFS='|' read -r key v p <<< "${RUNS[$i]}"
  out="$OUTD/events_$key.json"
  if [ -s "$out" ]; then echo "[SINKCHAR] $key: exists, skipped"; continue; fi
  echo "[SINKCHAR] === $key ($v)"
  $PY tools/eval/m3s0_dump_events.py --video_path "$v" --prompt_file_path "$p" --seed 0 --c_lo 25 --c_hi 140 --no_hashes \
    --gpu_id 0 --out "$out" || echo "[SINKCHAR] $key: exit $?"
done
