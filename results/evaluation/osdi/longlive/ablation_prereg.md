# LongLive state-component ablation: preregistration (FROZEN 2026-11-02; DRAFT 1 3762464a + user review; nothing run)

## 1. Question

Gate 1 (`gates.md`, measured): at call 30, sink + teacher-forced replay of the last 12 calls gives PSNR 51.2 dB on the
first call after the cutover, then 29.4 dB median and 24.1 dB minimum over the next 30 calls; window K / V exact on
5 / 30 layers, VAE decoder cache not exact. Replay from call 0 is bit-exact. Three explanations are open: (1) the
window K / V is not restored exactly, (2) the VAE decoder history is not restored exactly, (3) small state differences
are amplified by repeated generation. This study asks, before any LongLive migration protocol is designed:

**Which component's absence or approximation causes the sink + W12 loss, and can that component be reconstructed?**

Its purpose is to find out whether OTTER's selective state reconstruction can hold on another streaming diffusion
model, not to show that OTTER works on LongLive. The answer picks between a bounded reconstruction for LongLive, a
hybrid (ship some components exactly, rebuild the rest), and stating the conditions under which OTTER applies.

## 2. Facts this rests on

- State at a call (measured, gate0): sink K / V 0.86 GB (written by call 0 only), window K / V 2.59 GB (9 latent
  frames, rolls 3 per call), VAE decoder cache 1.89 GB (causal conv feature cache, 2 frames per conv), cross-attention
  K / V 0.09 GB (prompt-derived), latent buffer 2.4 MB. Total 5.44 GB.
- Cross-attention K / V is recomputed from the prompt in every condition except full (never shipped); the run checks it
  equals R's after the first call. [V tiny model]
- A cold VAE decoder restarts its temporal upsampling: the first call after the cutover decodes to 9 frames, not 12.
  [V tiny model] Frame completeness is a separate correctness metric (section 4).
- T2V: no input frames; every call conditions only on the prompt and on the model's own past. SDV2 is V2V. [H] why
  bounded reconstruction recovers on SDV2 and may not here; not claimed without the SDV2 contrast (D5).

## 3. Runs

`bash tools/longlive/run_gates.sh ablate P S PH`: reference R = calls 0-219 (seed S, prompt P), full export before call
M = 120, each condition builds a fresh session at M and runs calls 120-219 (k = 1-100), scored against R. Streams (D1):
prompts 0 (boy on a lawn) and 1 (hacker at screens) of `third_party/longlive/example/interactive_example.jsonl`, seeds
0 and 1; one stream per host (elves-01 0 0, elves-02 1 0, elves-03 0 1, elves-04 1 1), all four in parallel.

**Phase 1, state dependency diagnosis (about 40 min).** **Phase 2, reconstruction feasibility and sensitivity (about
45 min), run only if Phase 1's sanity rule S passes in all four streams**; if S fails, the harness / runtime is fixed
and Phase 1 rerun first (both records kept). Phase 2's analysis may concentrate on the component Phase 1 implicates,
but its conditions and rules are the ones written here.

| phase | condition | shipped exact | rebuilt / perturbed | role |
|---|---|---|---|---|
| 1 | full | all | - | sanity: bit-exact |
| 1 | sink_win_vae | sink, window, VAE | cross-attention recomputed, no latent buffer | sanity: bit-exact = these are the whole state |
| 1 | sink | sink | window empty, VAE cold | lower bound (P-sink, no recache) |
| 1 | sink_win | sink, window | VAE cold | is the VAE cache needed? |
| 1 | sink_vae | sink, VAE | window empty | is the window needed? |
| 1 | w12 | sink | window + VAE by replay of 12 calls | current OTTER (= gate1 replay_w12) |
| 1 | w12_vaeX | sink, VAE | window by replay of 12 calls | window approximation alone |
| 1 | winX_vaeR12 | sink, window | VAE by decoding the last 12 logged blocks | VAE approximation alone |
| 2 | winX_vae1 | sink, window | VAE by decoding the last block | cheapest VAE rebuild |
| 2 | eps_win | all | window x (1 + 2^-8 random sign), bf16 | sensitivity to a small window error |
| 2 | eps_vae | all | VAE cache, same | sensitivity of the decoder cache |
| 2 | eps_sink | all | sink, same | sensitivity to sink error |
| 2 | recache | sink, latent buffer | LongLive KV recache, VAE warmed on the last block | LongLive-native baseline |
| 2 | w24 / w48 / w96 | sink | window + VAE by replay of W calls | does a longer bounded replay converge? |

## 4. Metrics (per stream and condition; k = call - M + 1)

- **Fidelity:** PSNR vs R per call; windows first, W1 = k 1-8, W2 = 9-24, W3 = 25-100 (medians, as Fig. 13), minimum;
  reference-relative temporal PSNR (frame differences; boundary = first frame after the cutover vs R's last frame
  before it); latent relative error per call (divergence growth).
- **Frame completeness (correctness, separate):** frames delivered / expected. Missing frames are scored, not dropped:
  in PSNR and tPSNR they count as the last displayed frame held (R's last frame before the cutover). The PSNR of the
  delivered frames aligned to the reference's last frames is kept only as a diagnostic.
- **State at M:** sink / window (per layer: exact, relative error) / VAE exact and relative error; cross-attention
  recomputed exact; for eps_*: elements actually changed, changed fraction, realized relative error (2^-8 is not one
  ulp for every value).
- **Cost:** build time on the destination GPU (measured); bytes shipped (measured state sizes + replay log blocks);
  estimated readiness at 1 Gbps = bytes x 8 / 1e9 + build time (**estimated**: no serialization, copies, protocol or
  import; not a migration measurement).

## 5. Rules (written before the runs; 40 dB is the Fig. 13 operational threshold, not a perceptual one)

A result "holds" when it holds in >= 3 of the 4 streams.

- **S (sanity, Phase 1).** full and sink_win_vae equal R on 100 / 100 calls (latent digests), frames complete, and the
  recomputed cross-attention equals R's. Otherwise a runtime defect: fix, rerun, keep both records; nothing else is read
  and Phase 2 is not run.
- **Q2 necessity (Phase 1).** sink_win W3 < 40 = the VAE cache is needed; sink_vae W3 < 40 = the window is needed.
- **Q4 attribution of the W12 loss (Phase 1).** Reported: W3 of w12, w12_vaeX (window error only), winX_vaeR12 (VAE
  error only); the component whose approximation alone keeps W3 < 40 is named as a cause (both may be).
- **Q3 reconstruction (Phase 2).** VAE: winX_vaeR12 or winX_vae1 W3 >= 40 and frames complete = rebuildable from the
  latent log. Window: W* = smallest W in {12, 24, 48, 96} with w_W W3 >= 40 (none = no bounded window replay up to 96
  calls); also window layers exact vs W.
- **Q1 sensitivity (Phase 2; evidence, not proof).** eps_X W3 < 40 dB = the output is sensitive to a small relative
  error in X (reported with the realized error). This is sensitivity evidence only: a perturbation of this kind may be
  harsher or milder than a real reconstruction error, so it never establishes that an approximate reconstruction of X
  is impossible; that is decided by the reconstruction conditions themselves (Q3).

**Feasibility is judged on three separate axes for every reconstruction condition (one that ships neither window nor
VAE exactly, or only one of them):**
- **Fidelity feasible:** W3 >= 40 dB and frames complete.
- **Performance screen:** estimated readiness at 1 Gbps < 44 s (the measured 5.44 GB state at 1 Gbps, the lower bound
  of a Full migration). Passing the screen is not a claim of being faster than Full: that needs the measured
  end-to-end readiness of both in a migration harness (E10).
- **Applicable (candidate):** both of the above.

**Direction (applied to the result as written):**
- **Bounded reconstruction** if a condition that ships neither window nor VAE is applicable (candidate).
- **Hybrid** if not, but one with one of window / VAE shipped exactly and the other rebuilt is applicable (candidate);
  reported with the bytes it saves vs the whole state.
- **Applicability conditions** otherwise: the paper analyses LongLive's state dependency and limits OTTER's claims to
  the conditions shown (with Q1 as supporting sensitivity evidence; V2V vs T2V only after the SDV2 contrast, D5).

Never claimed from this study: OTTER works on LongLive; equivalent correctness of any reconstruction with the full
state; a speed advantage over Full. Descriptive: seam continuity of diverged outputs (boundary tPSNR), latent error
growth.

## 6. Decisions (user, 2026-11-02)

| # | decision |
|---|---|
| D1 | approved: prompts 0, 1 x seeds 0, 1 (4 hosts, parallel) |
| D2 | approved: M = 120, 100 scored calls |
| D3 | conditional: relative 2^-8, with elements changed and realized relative error recorded; Q1 is sensitivity evidence, not an impossibility proof |
| D4 | revised: 40 dB kept; 44 s only as an estimated performance screen; fidelity, performance, applicability judged separately; a speed claim vs Full needs measured end-to-end readiness |
| D5 | approved: SDV2 eps contrast after the LongLive analysis |
| D6 | approved: ablation (Phase 1, then Phase 2) before the D8 re-measurement |
| added | two phases; frame completeness as a separate correctness metric, missing frames scored as held frames |

CPU tests: `tools/longlive/test_ll_ablate.py` (tiny model: each condition builds the intended state, exact conditions
reproduce R with complete frames, the snapshot is never modified, missing frames scored as held, perturbation recorded,
the two phases cover the 16 conditions once, W > M skipped) and `test_ll_runtime.py`, ALL PASS.
