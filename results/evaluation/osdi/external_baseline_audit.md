# External baseline audit (2026-10-16)

Scope: external systems that could migrate a running StreamDiffusionV2 process (PyTorch 2.6.0+cu124, CUDA 12.4,
Python 3.10, NVIDIA L40S on elves-01..04, Ethernet only, no RDMA) between two physical servers. Every claim was read
from the cited source on 2026-10-16; "unverified" marks what could not be confirmed. StreamDiffusionV2 itself is not
counted as an external baseline. Nothing was installed or run.

**Testbed facts that matter here** (from `single_handoff/*/host_info.json`): PyTorch 2.6.0+cu124, CUDA 12.4, L40S on
both ends. **NVIDIA driver 575.51.03** (reported by the user on 2026-10-16 from one host with two L40S; the other three
hosts still to be confirmed). Per the cuda-checkpoint README (re-read 2026-10-16): basic checkpoint/restore needs
>= 550; 570 adds CRIU 4.0 process-tree integration, NVML support and the lock timeout; **"GPU migration" (restoring
onto different physical GPUs) is a 580 feature not present in 570**, and the README lists only container partial
passthrough as "also present in some 575 drivers". So on 575.51.03 cuda-checkpoint + CRIU can checkpoint and restore
on the same GPU, but restoring on a different node's GPU has no supported path; whether a same-model GPU on another
node restores without the migration API is **unverified** (issue #54 reports failure restoring to a different GPU
index without a device map on 595). Options: (a) test it empirically on two hosts before committing; (b) ask the
administrators for a driver >= 580 on all four hosts (shared machines: other users' jobs, a reboot, and a change of
the measured environment - all prior GPU results were taken on 575); (c) report the baseline as same-node C/R plus
measured transfer time of its image, labelled as such.

## Per-candidate findings

### 1. NVIDIA cuda-checkpoint + CRIU (CUDA plugin)
1. Sources: https://github.com/NVIDIA/cuda-checkpoint (binary utility, NVIDIA SDK EULA; active, last push 2026-07);
   CUDA driver API "CUDA Checkpointing" https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__CHECKPOINT.html;
   CRIU CUDA plugin (CRIU 4.0, 2024-09) https://github.com/checkpoint-restore/criu (plugins/cuda); related paper
   CRIUgpu, arXiv 2502.16631 (2025, no peer-reviewed venue found).
2. Public: yes (binary + CRIU source).
3. Cross-node: not documented by NVIDIA as cross-node; "GPU migration" (driver >= 575/580, `--device-map` /
   CRIU `cuda_plugin.device-map`) restores onto different physical GPUs of the **same chip type** with enough memory.
   Cross-node = move the CRIU image yourself + restore with a device map; a user report of a working cross-node
   restore (B200, driver 580) with a stale-PCI-bus-ID caveat: https://github.com/NVIDIA/cuda-checkpoint/issues/48.
4. L40S / CUDA 12.x: driver-level, model-agnostic; Ada (L4) reported working on driver 580 (issue #35); L40S
   specifically **unverified**; CUDA 12.x user-space works under an r580 driver (issue #48 used CUDA 12.8 + PyTorch).
5. PyTorch: transparent (no rebuild); unsupported: UVM/managed memory, CUDA IPC export, MIG/MPS, NCCL multi-process;
   CUDA graphs / pinned host buffers **unverified** (no documentation either way).
6. Changes: no driver/kernel change, no LD_PRELOAD; ptrace on the target; CRIU needs root/CAP_CHECKPOINT_RESTORE.
7. Destination: no pre-started process (CRIU recreates it); same binary, libraries and paths; same-chip GPU; driver in
   persistence mode or able to `cuInit`.
8. Checkpoint = lock driver APIs, drain submitted work, stage all device memory into host allocations inside the
   process, release the GPU; CRIU dumps the whole process (staged GPU memory + host heap + weights in host memory if
   any). Transfer = external (rsync, NFS, `criu-image-streamer`, page server). Restore = CRIU restores the process,
   cuda-checkpoint copies device memory back to the original addresses.
9. Continuity: full state by construction (bit-exact continuation); cost = the whole image every time (no incremental
   GPU checkpoint; CRIU pre-dump disabled for CUDA).
10. Effort: moderate. Blockers: driver version on elves (unknown); client/inter-node TCP sockets in the generation
    process (CRIU `--tcp-established` or close before dump); the lock drains in-flight generation; avoid NVML calls
    (stale PCI IDs); root on all four hosts.

### 2. GCR (FAST '26)
1. "GPU Checkpoint/Restore Made Fast and Lightweight", Zeng, Ren, Shu, Lu (Tsinghua), FAST '26, pp. 239-254,
   https://www.usenix.org/conference/fast26/presentation/zeng; code https://github.com/thustorage/GCR.
2. Public, **no license file**, 2 commits (last 2026-03), README is essentially `bash run.sh`.
3. Cross-node: **not supported or evaluated** (single node, checkpoints cached in CPU memory; serverless / switching /
   fault-tolerance use cases). The paper says GCR leverages CRIU for CPU state; the artifact contains no CRIU call.
4. Environment: tested CUDA 12.6, PyTorch 2.7.1, A100 (sm_80 hard-coded in `build.sh`); driver not stated (relies on
   `cuda-checkpoint --toggle`, so >= 550 implied); Ada/L40S **unverified**.
5. PyTorch: yes through the driver C/R path (Transformers, vLLM, DeepSpeed evaluated); incremental mode needs
   per-kernel templates and, for vLLM, small source annotations; UVM future work.
6. Changes: no driver change; LD_PRELOAD shim + replacement `libcuda.so` via `dlopen` interposition, hugetlbfs control
   plane (90 GB of 2 MB hugepages), sudo.
7. Destination: undefined (same-process restore on the same node).
8. Checkpoint = data buffers copied to CPU memory by the shim (~20.5 GB/s) + small control state via the driver C/R;
   no transfer component.
9. Continuity: full state; incremental mode reduces checkpoint size (86.6 % on average in the paper).
10. Effort: high - port to sm_89, add CRIU for the CPU image and our own transport, debug the libcuda interposition
    with PyTorch 2.6's own dlopen of CUDA libraries, no license (permission for use in a comparison should be
    confirmed with the authors).

### 3. PhoenixOS / PhOS (SOSP '25)
1. "PhoenixOS: Concurrent OS-level GPU Checkpoint and Restore with Validated Speculation", Wei et al., SOSP '25,
   DOI 10.1145/3731569.3764813, arXiv 2405.12079; code https://github.com/SJTU-IPADS/PhoenixOS (Apache-2.0).
2. Public; last push 2025-09; open questions about CUDA 12 support and project status unanswered (issues #30, #37).
3. Cross-node: in the paper yes (pre-copy over GPUDirect RDMA, 100 Gbps, A800); **the README states cross-node live
   migration and the device-to-device library are not released**.
4. Environment: public code CUDA 11.3 / cuDNN 8 (Docker image); CUDA 12.x / Ada **not supported as released**.
5. PyTorch: through full driver-API interception; GCR's authors report the runnable commit does not support complex
   frameworks (vLLM, DeepSpeed) (FAST '26 paper, section 6).
6. Changes: LD_PRELOAD frontend + a daemon that owns all GPUs, privileged root container; RDMA NICs for the paper's
   migration path.
7. Destination: `phosd` daemon with a warm context pool.
8-9. All GPU buffers; concurrent soft copy-on-write; on-demand restore.
10. Blockers: CUDA 11.3-only public code vs our CUDA 12.4 / PyTorch 2.6; cross-node path unreleased; no RDMA on the
    testbed.

### 4. Others considered
| system | status | reason |
|---|---|---|
| CRIUgpu (arXiv 2502.16631) | same mechanism as 1 | the CRIU CUDA plugin is the practical wrapper around cuda-checkpoint; not a separate baseline |
| Cricket (RWTH-ACS, MIT) | infeasible | CUDA API remoting; PyTorch support requires a patched PyTorch 1.13.1 build; C/R experimental |
| Singularity (Microsoft) | infeasible | no public code |
| Cedana | requires adaptation / unverified | commercial; open status of its GPU interposition not verifiable |
| gVisor GPU checkpoint | rejected | wraps cuda-checkpoint inside a sandbox; open breakage on L4 / driver 580 |
| CheckFreq, Gemini, TGS, Nebula, DeepFreeze, FlexFlow | not applicable | application-level model checkpointing, GPU sharing, or frameworks; no CUDA process state capture |

## Comparison

| | cuda-checkpoint + CRIU | GCR | PhoenixOS |
|---|---|---|---|
| public code | yes (binary + CRIU) | yes, no license | yes, Apache-2.0 |
| cross-node restore | via image transfer + device map (same chip type); user-reported | no | paper only (unreleased) |
| our stack (CUDA 12.4, PyTorch 2.6, L40S) | likely; depends on the unrecorded driver version | needs porting (sm_80, CUDA 12.6 tested) | no (CUDA 11.3) |
| shim / privileges | none / root + ptrace | LD_PRELOAD + replacement libcuda, hugepages, sudo | LD_PRELOAD + GPU-owning daemon, privileged |
| incremental | no | yes (templates) | soft CoW |
| classification | **feasible** | **requires adaptation** | **infeasible (public code)** |

## Recommendation

1. **Primary external baseline: cuda-checkpoint + CRIU** (CUDA plugin), driver >= 580 if available, image moved over
   the same shaped links (rsync or `criu-image-streamer`), restored on the destination L40S with a device map. It is
   the only candidate that is maintained, transparent to an unmodified PyTorch 2.x / CUDA 12.x process and has a
   defined cross-GPU restore path whose constraint (same chip type) the testbed satisfies. It is the full-state,
   stop-the-world reference that a systems reviewer will expect.
2. **Second baseline: GCR, as an adapted "fast GPU C/R + CRIU + transfer" variant**, clearly labelled as adapted (the
   authors evaluated single-node only). It represents the state-of-the-art GPU C/R data path. If the sm_89 port or
   the libcuda interposition fails with PyTorch 2.6 within a bounded effort (proposed: 3 working days), report it as
   attempted and fall back to an *in-repo* reference instead: the existing "Full migration" policy (application-level
   full-state transfer, already measured) - which is not an external system and must not be presented as one.
3. **PhoenixOS**: cite as related work (its RDMA live-migration numbers), not run: its public code cannot run our
   CUDA 12.4 / PyTorch 2.6 workload and its cross-node path is unreleased.

Fairness notes for whichever baselines run: same trigger chunk, same shaped links, destination host with the driver
initialized; C/R images contain the model weights (OTTER's destination preloads them), so results are reported both
"as designed" and, where the system allows, with weights excluded or preloaded (see the preregistration, section 5).

## Highest-risk integration problems

1. Driver 575.51.03 (one host confirmed): checkpoint/restore is supported, the cross-GPU migration API (580) is not;
   cross-node restore must be tested empirically, or the driver upgraded on all hosts (environment change), or the
   baseline reported as same-node C/R + measured image transfer.
2. CRIU must handle the generation process's open TCP control/data sockets (or they must be closed before dump).
3. Root/CAP_CHECKPOINT_RESTORE on shared machines.
4. GCR's replacement-libcuda interposition with PyTorch 2.6 and the sm_80 -> sm_89 port.
5. Image size (~6 GiB GPU + host heap + weights) over 1 Gbps: expected to dominate; this is the comparison's point, but
   the transfer tool and shaping must match OTTER's for fairness.
