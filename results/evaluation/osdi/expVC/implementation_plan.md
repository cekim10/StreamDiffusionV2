# Experiment VC - VC-1 implementation plan (2026-10-22; for review; nothing implemented)

Companion to `preregistration.md` (revised draft 3). Nothing here changes M1 / M2 / M3-v2, `rd_emulate.py`, or any
frozen result. Order: this plan and draft 3 are checked -> VC-0 (code, dry and CPU tests, two GPU equivalence checks)
-> review -> freeze -> VC-1.

## 1. Files (all new except where marked)

| file | purpose |
|---|---|
| `tools/eval/vc_schedules.py` | derive every condition from frozen runs: reset / bind calls, delivered-chunk times (orchestrator `metrics.csv`), bind time after the move (WFS hold), cold-restart time (COLD hold). Writes `results/evaluation/osdi/expVC/vc_schedules.json` (committed; reviewed before the freeze) |
| `tools/eval/vc_emulate.py` | the VC emulator: imports the RD emulator's helpers (`payload_of`, `sha`, the reset / bind sequence of `rd_emulate.run_condition`) and adds frame saving and the COLD operation. `rd_emulate.py` is not edited |
| `tools/eval/vc_playback.py` | the last-frame-hold playback model (P1-P3) from a delivery timeline |
| `tools/eval/vc_metrics.py` | V1-V5 (and V6 if enabled) from the saved frames, on the VC host |
| `tools/eval/run_vc.py` | driver on elves-01: preflight, launch on the VC host through its agent, copy back the small results |
| `tools/eval/aggregate_vc.py` | tables, paired differences, bootstrap CIs, REF bands, effect sizes, VC-H1 / VC-H2 verdicts |
| `tools/eval/test_vc.py` | dry and CPU tests (section 5) |
| `tools/eval/d0_remote.py`, `tools/eval/run_wrn.py` (edited) | host-scoped GPU-idle check (section 6) |

## 2. Emulation (`vc_emulate.py`)

One process per input on the VC host: the REF baseline (`GpuRuntime.baseline`, frames kept), then each condition from
call 0, as in RD.

| condition | per-call operations |
|---|---|
| OT-1, OT-L, OT-R | RD semantics: an M1 reset before each reset call (serialize, pack in-flight + meta, release, provision, unpack, `restore_fast`; the Sink packed once at the episode's first reset), a bind before the bind call |
| WFS-1, WFS-L | reset and bind before the same call (RD d = 0): the withheld Sink is bound before the first generated call |
| COLD-1, COLD-L | at the move call c: `GpuRuntime.cold_restart(c)`, then the node's rule for the frozen `cold` policy: no model call at c (skip), and at c + k - 1 the cold restart's frames are emitted (override). Nothing else is carried |

**Saved per condition:** every output frame from 16 calls before the first reset to 100 calls after the final bind, as
FFV1 (bit-exact; `xb_codec.encode(..., "ffv1")`), one file per 25 calls. Also `calls.csv` (call, phase, event, PSNR,
SSIM, frame digest) and `summary.json` (the schedule, the realized operations, validity as in RD: prefix identical to
REF, operations at the scheduled calls, no missing calls).

**Frame location:** `--frames_dir` on the VC host's local disk, outside the repository. `calls.csv` and `summary.json` go
to `results/evaluation/expVC_<input>/<condition>/` and are copied back to elves-01. Frames stay on the host.

## 3. Schedules and timelines (`vc_schedules.py`)

| condition | source run(s) (all frozen, present locally) | extracted |
|---|---|---|
| OT-1 | `expW_W2_<input>_s0/policy=reuse_dyn_*` (audi: the earlier valid one) | move call, destination bind call (`rd_schedule.replay_from_run`, the RD-X extractor), delivered-chunk times relative to the move |
| OT-L | `expRDX_<input>/policy=split_*` rep 1 (butterfly, audi, dog); **train: dog's schedule and times, labelled "counterfactual replay, copied schedule"** | as OT-1 |
| OT-R | `expWX_<w>_X3/policy=split_*_rep=1_*` (butterfly, audi, train), `expM3E_S4/policy=split_*_rep=1_*` (dog) | every move call, final bind call, delivered-chunk times |
| WFS-1, WFS-L | the OT-1 / OT-L source run | hold duration = the destination's `sink_bind` time minus the move request time |
| COLD-1, COLD-L | `expW_W2_<input>_s0/policy=cold_*` | hold duration = the first output after the move minus the move request time |

`test_vc.py` checks every extracted value against the source run's summary (moves, binds), as `test_rd.py` does for
RD Phase 0.

## 4. Metrics (`vc_metrics.py`, `vc_playback.py`)

- **V1-V3:** `rd_metrics` functions as they are (`small_gray`, Farneback flow of the input, `warp_error`, the
  motion-ratio and spike definitions), on the windows of draft 3 section 4.1.
- **V4:** mean CIELAB per frame (skimage `rgb2lab`), window means, CIEDE2000 (skimage `deltaE_ciede2000`), against
  REF and against the 16 pre-move calls.
- **V5a:** DINO ViT-B/16 (`torch.hub`, `facebookresearch/dino:main`, `dino_vitb16`); DINOv2 ViT-B/14
  (`facebookresearch/dinov2`, `dinov2_vitb14`) as sensitivity. Standard ImageNet preprocessing at 224 px (resize,
  center crop), L2-normalized CLS features.
- **V5b:** CLIP ViT-L/14 with the OpenAI weights (`open_clip`, `ViT-L-14`, `pretrained='openai'`; MIT); image-text
  cosine with the prompt file's text.
- **V6:** DOVER at a pinned commit with `DOVER.pth`, **only if D8 enables it**; otherwise not installed and not computed.
- **Playback:** the last-frame-hold model of draft 3 section 4.2, applied to each condition's timeline; P3 uses V1
  between the held frame and the next shown frame.
- **Model provenance:** the preflight downloads each model once into a cache on the VC host's local disk and records
  the source, version or commit and the SHA-256 of every weight file in `results/evaluation/osdi/expVC/model_provenance.json`.
- **Aggregation (`aggregate_vc.py`):** per input x condition x window, paired OTTER - REF differences with a bootstrap 95 %
  CI over calls (10,000 resamples, fixed seed), REF's P5-P95 bands of 10-call windows, effect sizes, VC-H1 and VC-H2
  verdicts reported after their effect sizes, and the playback table.

## 5. VC-0 tests (before any VC-1 run; not evidence)

**Local (dry runtime and CPU):**
1. Schedule extraction matches the source runs' recorded moves and binds, for every condition and input.
2. Dry emulation of all seven conditions: operation order (WFS bind at the reset call; COLD skip and emit at c and c +
   k - 1; OT-R one reset per move and the Sink packed once per episode), frames written and read back bit-exact (FFV1).
3. Playback model on synthetic timelines with known stalls (count, total, longest, resume jump).
4. Metric sanity on a repository clip: identical streams give V1 ratio 1, V4 0 and V5 difference 0; an injected cut
   gives a large V1; an injected global color shift gives a V4 equal to the shift's CIEDE2000; a frame swap changes V5a.
   DINO and CLIP run on CPU for a few frames.

**GPU, on the VC host, about 20 min (equivalence checks, not evidence):**
- **G1** replay the dog RD-X rep 1 schedule with `vc_emulate.py`. Every call's PSNR must equal the real run's, as RD-X
  showed for `rd_emulate.py` (|dPSNR| 0.00), and the prefix must be digest-identical to REF.
- **G2** replay dog's frozen W2 `cold` run as COLD-1. Every call's PSNR must equal the real run's.
- WFS has no real counterpart yet. XB1's Wait-for-Sink runs, once they exist, will allow the same check. Until then WFS
  is labelled "emulated (RD d = 0)".

A failing G1 or G2 stops VC; the mismatch is reported.

## 6. Execution isolation (draft 3 section 8)

- **Host-scoped idle check (needed):** today `run_wrn.py` waits until GPU 0 is idle on **all four** hosts before every
  invocation (`d0_remote.py gpu_idle`), so a VC unit on D would block the XB gate and calibration on A and B. Change:
  `gpu_idle --hosts A,B` checks GPU 0 only on the listed hosts. It still requires all four repositories on one commit.
  `run_wrn.py` passes the invocation's hosts (A and B for one hop), and `run_vc.py` checks only the VC host. Every
  other experiment keeps the four-host check.
- **Order of operations:**
  1. all four hosts on one commit;
  2. VC preflight on the VC host (local filesystem check of the frames directory with `findmnt -T` and `df`, at least
     20 GB free; package and model downloads into the local cache);
  3. start the XB gate, then calibration, on A and B; start VC-1 on the VC host;
  4. no pull or commit on any host until both finish.
- Model downloads happen in step 2, before XB starts, so no internet traffic overlaps XB runs.
- **Interference records:**
  - each VC unit records its host's NIC byte counters (`/proc/net/dev`) before and after (expected near zero);
  - each XB run keeps its existing per-node NIC validity check on A and B;
  - VC writes frames only to the VC host's local disk and results only under `expVC*`;
  - logs go to `results/evaluation/vc_logs/`.

## 7. Size and time

| item | estimate |
|---|---|
| sequences | 4 inputs x (REF + 7 conditions) = 32 |
| GPU time | per input: one ~300-call baseline plus 7 conditions of ~150-300 calls, about 15-20 min; about 1-1.5 h in total on one GPU 0 |
| metrics | DINO, DINOv2 and CLIP on about 30,000 frames at 224 px: well under 1 h on the same GPU after generation |
| frames | about 0.4 MB per frame with FFV1, about 10 GB on the VC host's local disk; deleted only on the user's instruction |

## 8. Dependencies to install on the VC host only (by the user, as with OpenCV)

- `open_clip_torch`;
- `scikit-image` (CIELAB, CIEDE2000): already a dependency (`state_ablation.py` imports it), so nothing to install;
- `torch.hub` access to GitHub and to the weight URLs (DINO, DINOv2, OpenAI CLIP);
- DOVER only if D8 enables it.

The exact commands are given with the VC-0 code.

## 9. VC-0 status (2026-10-22) and deviations from this plan

**Decisions applied (2026-10-22):**
- VC runs on host D, with C as the spare (`run_vc.py --host`).
- GPU-idle checks are scoped to the job's hosts. `d0_remote.py gpu_idle --hosts`; XB invocations in `run_wrn.py` check
  only their path's hosts. Every other experiment keeps the four-host check, and no run-validity rule changed.
- DOVER is excluded: no V6 code path, no weight download.
- G1, G2 and G3 are implemented in `vc_check.py`.
- WFS records its skipped input calls, its stall, and the input-to-output alignment after the resume.
- V5 uses within-window aggregation (frames -> call -> window) with a preregistered moving block bootstrap
  (`aggregate_vc.py`: block 5 calls, sensitivity 3 and 10, 10,000 resamples, seed 0).

**Implemented:**
- `vc_schedules.py` and `vc_schedules.json`: 28 conditions, every one checked against its source run.
- `vc_emulate.py`, `vc_frames.py`, `vc_playback.py`, `vc_metrics.py`, `vc_check.py`, `aggregate_vc.py`, `run_vc.py`.
- `test_vc.py`, run locally on the fake runtime and CPU: ALL PASS. It covers the schedules, dry emulation of seven
  conditions on two inputs, G3, four G3 negative cases, the G1 / G2 comparison logic against the real runs' own logs,
  the playback model, the metric self-test and the aggregation.
- The real-model self-test (DINO, DINOv2, CLIP) and G1 / G2 / G3 on the GPU have **not run yet**; they run on host D
  through `run_vc.py vc0`.

**Deviations (for review before VC-1):**

| id | plan / draft text | implemented | why |
|---|---|---|---|
| D-VC-1 | playback at 16 fps (draft 3 section 4.2) | both 16 fps and a rate matched to the measured delivery cadence (4 frames per post-bind chunk interval); the rate-matched table is primary in the report, and 16 fps stays in the json | the realized runs deliver one 4-frame chunk every ~0.60 s (about 6.7 fps). At 16 fps even REF stalls continuously (dry check: 224 stalls, 79 s), so the 16 fps model cannot separate conditions. **Decision needed:** adopt the rate-matched model in the draft |
| D-VC-2 | V1 local median "over the 16 preceding calls (RD definition)" | the RD definition as coded: median of the **8 preceding frame transitions** (`rd_metrics.no_reference`) | the draft text misstates RD's definition; the code follows RD. **Decision needed:** correct the draft text |
| D-VC-3 | V1 at a cold restart | COLD's event transition spans the skipped call (last frame of c - 1 to the first emitted frame at c + 1), flagged `across_gap` | RD's code drops transitions across a missing call, which would leave COLD without a V1 |
| D-VC-4 | stall definition not specified beyond "frame not delivered" | a stall counts when the picture freezes for at least one display-frame interval; shorter lateness from cadence jitter is reported separately as total lateness | cadence differences of about 1 % between runs otherwise produce many microsecond "stalls" (dry check: 105 for COLD) |
| D-VC-5 | timelines | COLD-L has no realized run: the W2 cold run's timeline is shifted to call 80, labelled "copied". WFS has no realized run: its timeline is derived (hold = the paired run's move-to-bind time, then the paired run's first-output latency and cadence), labelled "derived". Both are emulated conditions, not reproductions of real runs | no real COLD at call 80 or real Wait-for-Sink run exists; XB1's Wait-for-Sink runs, once made, allow a check |
| D-VC-6 | VC-0 GPU set "G1 and G2, about 20 min" | dog OT-L (G1), COLD-1 (G2) and WFS-1 (G3 on a WFS stream), REF frames, and the real-model metric self-test; about 30-40 min | G3 needs a WFS stream to check its alignment rule; the self-test checks the model code before VC-1 |
| D-VC-7 | WFS skipped input calls | the harness skips none: it generates every input call in order after the hold (a delay). The input chunks a real-time player that drops the backlog would skip (move call .. + ceil(hold / 0.25 s) - 1) are recorded. Outputs are paired with REF only on the same input chunk | as decided: never compare mismatched input calls |
| D-VC-8 | audi-snow-trail OT-1 "the earlier valid one" | the later W2 run (20261019-135751); the earlier one is invalid under the W / R / N rules (NIC peak > 1.15 x cap) | consistent with the rule; noted because the bind call is 59, not 58 |
| D-VC-9 | V5 preprocessing | DINO / DINOv2: the ImageNet evaluation transform (shorter side 256, center crop 224). CLIP: OpenAI's transform (shorter side 224, center crop 224) with the OpenAI normalization constants | stated for reproducibility |
