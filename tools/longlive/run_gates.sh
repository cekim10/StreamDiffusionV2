#!/usr/bin/env bash
# LongLive second-model gates (osdi/longlive/gates.md). One GPU per host; run only when no experiment uses the GPU.
#   each host:  bash tools/longlive/run_gates.sh setup     # peft into the venv + LongLive checkpoints (once per host)
#   elves-01:   bash tools/longlive/run_gates.sh gate0     # feasibility: FPS, memory, state inventory, recache cost
#   elves-01:   bash tools/longlive/run_gates.sh gate1     # determinism, full import, reconstruction variants
#   elves-02:   bash tools/longlive/run_gates.sh gate1     # same, second host: compare the printed "R chain" lines
#   elves-0N:   bash tools/longlive/run_gates.sh ablate P S PH   # state-component ablation, prompt P, seed S, phase PH
#               (osdi/longlive/ablation_prereg.md: elves-01 0 0, elves-02 1 0, elves-03 0 1, elves-04 1 1;
#                phase 1 ~40 min, phase 2 only after phase 1's sanity rule passes on all four, ~45 min)
#   local:      bash tools/longlive/run_gates.sh test      # tiny CPU models (no weights, no GPU)
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-python}
OUT=results/evaluation/osdi/longlive
H=$(hostname -s)
mkdir -p $OUT
idle() { [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader -i 0 2>/dev/null)" ] || { echo "[LL] GPU 0 busy on $H: not running"; exit 1; }; }
case "${1:-}" in
  setup)
    # the testbed venv is uv-managed (no pip module)
    $PY -c "import peft, omegaconf, easydict" 2>/dev/null || uv pip install --python "$(command -v $PY)" "peft>=0.13,<1" omegaconf easydict
    if [ ! -f wan_models/LongLive-1.3B/models/lora.pt ] && [ ! -f wan_models/LongLive-1.3B/lora.pt ]; then
      $PY -c "from huggingface_hub import snapshot_download as d; d('Efficient-Large-Model/LongLive-1.3B', local_dir='wan_models/LongLive-1.3B', allow_patterns=['*.pt'])"
    fi
    ls -l wan_models/LongLive-1.3B/models wan_models/Wan2.1-T2V-1.3B | head -20
    $PY -c "import peft, omegaconf, easydict, torch; print('peft', peft.__version__, 'torch', torch.__version__)" ;;
  gate0)
    idle; CUDA_VISIBLE_DEVICES=0 $PY tools/longlive/ll_gate.py gate0 --calls 60 --warmup 10 --out $OUT/gate0_$H.json 2>&1 | tee $OUT/gate0_$H.log ;;
  gate1)
    idle; CUDA_VISIBLE_DEVICES=0 $PY tools/longlive/ll_gate.py gate1 --calls 60 --at 30 --replay_windows 3,6,12 --out $OUT/gate1_$H.json 2>&1 | tee $OUT/gate1_$H.log ;;
  ablate)
    P=${2:?prompt index}; S=${3:?seed}; PH=${4:?phase 1 or 2}; idle
    CUDA_VISIBLE_DEVICES=0 $PY tools/longlive/ll_gate.py ablate --calls 220 --at 120 --prompt_idx $P --seed $S --phase $PH \
      --out $OUT/ablate_p${P}_s${S}_ph${PH}.json 2>&1 | grep -v "peft_config\|LoRA target\|trainable params" | tee $OUT/ablate_p${P}_s${S}_ph${PH}.log ;;
  test)
    $PY tools/longlive/test_ll_runtime.py && $PY tools/longlive/test_ll_ablate.py ;;
  *) echo "usage: $0 setup|gate0|gate1|ablate P S PH|test"; exit 2 ;;
esac
