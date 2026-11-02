# LongLive state-component ablation: preregistration (DRAFT 1, not frozen, nothing run)

## 1. Question

Gate 1 (`gates.md`, measured): at call 30, sink + teacher-forced replay of the last 12 calls gives PSNR 51.2 dB on the
first call after the cutover, then 29.4 dB median and 24.1 dB minimum over the next 30 calls; window K / V exact on
5 / 30 layers, VAE decoder cache not exact. Replay from call 0 is bit-exact. This study asks one thing before any
LongLive migration protocol is designed:

**Which component's absence or approximation causes the sink + W12 loss, and can that component be reconstructed
cheaply?** The answer picks between (B) a selective reconstruction for LongLive and (C) stating the conditions under
which OTTER's bounded reconstruction applies. It does not test OTTER on LongLive.

## 2. Facts this rests on

- State at a call (measured, gate0): sink K / V 0.86 GB (written by call 0 only), window K / V 2.59 GB (9 latent
  frames, rolls 3 per call), VAE decoder cache 1.89 GB (causal conv feature cache, 2 frames per conv), cross-attention
  K / V 0.09 GB (prompt-derived), latent buffer 2.4 MB. Total 5.44 GB; 1 Gbps transfer about 44 s.
- Cross-attention K / V is recomputed from the prompt in every condition (never shipped); the run checks it equals R's
  after the first call. [V tiny model]
- A cold VAE decoder restarts its temporal upsampling: the first call after the cutover decodes to 9 frames, not 12
  (3 frames missing; recorded; PSNR on that call uses the reference's last 9 frames). [V tiny model]
- T2V: no input frames. Every call conditions only on the prompt and on the model's own past (KV, VAE cache). SDV2 is
  V2V: every call also sees a new input frame. [H] this is why bounded reconstruction recovers on SDV2 and may not here.

## 3. Runs

`bash tools/longlive/run_gates.sh ablate P S`: reference R = calls 0-219 (seed S, prompt P), full export before call
M = 120 (so replays up to W = 96 fit), each condition builds a fresh session at M and runs calls 120-219 (k = 1-100),
scored against R. Streams (D1): prompts 0 (boy on a lawn) and 1 (hacker at screens) of
`third_party/longlive/example/interactive_example.jsonl`, seeds 0 and 1 = 4 streams, one per host (elves-01 0 0,
elves-02 1 0, elves-03 0 1, elves-04 1 1), about 70 min each, all in parallel. elves-03 / 04 need `setup` first.

| condition | shipped exact | rebuilt / perturbed | role in the analysis |
|---|---|---|---|
| full | all | - | sanity: bit-exact |
| sink_win_vae | sink, window, VAE | cross-attention recomputed, no latent buffer | sanity: bit-exact = these three are the whole state |
| sink | sink | window empty, VAE cold | lower bound (P-sink, no recache) |
| sink_win | sink, window | VAE cold | is the VAE cache needed? |
| sink_vae | sink, VAE | window empty | is the window needed? |
| w12 | sink | window + VAE by replay of 12 calls | current OTTER (= gate1 replay_w12) |
| w12_vaeX | sink, VAE | window by replay of 12 calls | window approximation alone |
| winX_vaeR12 | sink, window | VAE by decoding the last 12 logged blocks | VAE approximation alone; cheap VAE rebuild? |
| winX_vae1 | sink, window | VAE by decoding the last block | cheapest VAE rebuild |
| eps_win | all | window x (1 + 2^-8 random sign), bf16 | sensitivity to a 1-ulp-scale window error |
| eps_vae | all | VAE cache perturbed the same way | sensitivity of the decoder cache |
| eps_sink | all | sink perturbed the same way | sensitivity to sink error |
| recache | sink, latent buffer | LongLive KV recache, VAE warmed on the last block | LongLive-native baseline |
| w24 / w48 / w96 | sink | window + VAE by replay of W calls | does a longer bounded replay converge? |

## 4. Metrics (per stream and condition; k = call - M + 1)

PSNR vs R per call; reference-relative temporal PSNR (frame differences; boundary = first frame after the cutover vs
R's last frame before it); windows first, W1 = k 1-8, W2 = 9-24, W3 = 25-100 (medians, as Fig. 13), minimum; latent
relative error per call (divergence growth); at M: sink / window (per layer: exact, relative error) / VAE exact and
relative error; build time; frames missing; cross-attention recomputed exact.

## 5. Rules (written before the runs; 40 dB is the Fig. 13 operational threshold, not a perceptual one)

A result "holds" when it holds in >= 3 of the 4 streams.

- **S (sanity).** full and sink_win_vae equal R on 100 / 100 calls (latent digests); cross-attention recomputed exact.
  Otherwise a runtime defect: fix, rerun, keep both records; no other rule is read.
- **Q1 sensitivity.** For each of window, VAE, sink: eps_X W3 < 40 dB = the output is not stable under a 1-ulp-scale
  error in X, so matching the reference at 40 dB needs X bit-exact and no approximate reconstruction of X can meet it.
- **Q2 necessity.** sink_win W3 < 40 = the VAE cache is needed; sink_vae W3 < 40 = the window is needed.
- **Q3 cheap reconstruction.** VAE: winX_vaeR12 (or winX_vae1) W3 >= 40 = the VAE cache is rebuildable from the latent
  log. Window: W* = smallest W in {12, 24, 48, 96} with w_W W3 >= 40 (none = no bounded window replay up to 96 calls).
- **Q4 attribution of the W12 loss.** Reported: W3 of w12, w12_vaeX (window error only), winX_vaeR12 (VAE error only).

**Direction (applied to the result as written):**
- **B (selective reconstruction feasible)** if some condition that ships neither window nor VAE (w24 / w48 / w96, or
  w12 with exact VAE replaced by a rebuild) has W3 >= 40 with build time <= 44 s (the measured full state at 1 Gbps).
- **B-partial** if B fails but the VAE is rebuildable (Q3) and only the window must be shipped: saving 1.89 of 5.44 GB;
  reported as a weak result, not as OTTER's mechanism carrying over.
- **C (scope condition)** if B and B-partial fail. If Q1 holds for the window or the sink, the paper states that
  LongLive's output is sensitive to 1-ulp-scale KV errors, so reference fidelity requires an exact state (shipped or
  replayed from call 0), and that OTTER's bounded reconstruction applies to models whose calls are anchored by new
  input (V2V) [H, to be tested on SDV2 with the same eps probe before it is claimed].

Never claimed from this study: OTTER works on LongLive; equivalent correctness of any reconstruction with the full state.
Descriptive: whether diverged outputs stay seam-continuous (boundary tPSNR), latent error growth rate.

## 6. Open decisions

| # | decision | recommendation |
|---|---|---|
| D1 | streams | prompts 0, 1 x seeds 0, 1 (4 hosts, parallel) |
| D2 | cutover M and horizon | M = 120 (W up to 96), 100 scored calls |
| D3 | perturbation | relative 2^-8 (the bf16 rounding scale; smaller rounds back to the same value) |
| D4 | thresholds | 40 dB W3, >= 3 / 4 streams, B budget 44 s |
| D5 | SDV2 contrast | same eps probe on SDV2 (window and Sink) as a follow-up, needed before the V2V condition is claimed |
| D6 | order vs D8 | ablation first (decides the paper's scope), then `run_fig11.sh rfull_chain` (needs all four GPUs) |

CPU tests: `tools/longlive/test_ll_ablate.py` (tiny model: each condition builds the intended state, exact conditions
reproduce R, the snapshot is never modified, W > M skipped) and `test_ll_runtime.py`, ALL PASS.
