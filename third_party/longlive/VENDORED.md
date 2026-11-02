# Vendored: LongLive 1.0 (NVlabs)

Second model for the OTTER evaluation (osdi/second_model_survey.md). Copied unmodified from
https://github.com/NVlabs/LongLive, directory `LongLive1.0/`, commit `242635807b4ebb89fa2609a84df7eacde6aed92f`
(2026-10-30), Apache-2.0 (`LICENSE`; copyright NVIDIA CORPORATION & AFFILIATES and the Alibaba Wan Team).

Copied: `wan/`, `utils/`, `configs/`, `example/`, `LICENSE`. Not copied: `pipeline/` (its package `__init__` imports
the training pipelines; the per-call inference loop is re-implemented in `tools/longlive/ll_runtime.py` from
`pipeline/causal_inference.py` and `pipeline/interactive_causal_inference.py`), `model/`, `trainer/`, training scripts.
No file in this directory is modified.

Weights (not in git): the Wan2.1-T2V-1.3B base under `wan_models/Wan2.1-T2V-1.3B/` (the same directory
StreamDiffusionV2 uses; the vendored code opens it by the relative path `wan_models/...`, so the runtime runs with
the repository root as its working directory) and the LongLive checkpoints `longlive_base.pt` and `lora.pt` from
Hugging Face `Efficient-Large-Model/LongLive-1.3B` under `wan_models/LongLive-1.3B/`. The LongLive weights are
licensed CC-BY-NC-SA-4.0 (research use). Extra Python dependency: `peft` (LoRA).
