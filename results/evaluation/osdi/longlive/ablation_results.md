# LongLive state-component ablation: results

Rules: `ablation_prereg.md` (FROZEN fba111ae). Measured on the testbed; 4 streams (prompt p x seed s).

## Phase 1, state dependency diagnosis (4 / 4 streams)

Runs: p0 s0 elves-01, p1 s0 elves-02, p0 s1 elves-03 (commit ca0f13c3); p1 s1 on elves-01 (commit 4fff1b24, the stream assigned to elves-04, whose setup was still running; no code difference under tools/longlive or third_party between the two commits; gate1 showed cross-host determinism). Deviation: host only.

| condition | W3 PSNR (dB), p0s0 / p1s0 / p0s1 / p1s1 | first call | W1 | latents bit-exact | frames | build (s) |
|---|---|---|---|---|---|---|
| full | 99.0 / 99.0 / 99.0 / 99.0 | 99.0-99.0 | 99.0-99.0 | 100-100 / 100 | 1200 / 1200 | 1.6-1.6 |
| sink_win_vae | 99.0 / 99.0 / 99.0 / 99.0 | 99.0-99.0 | 99.0-99.0 | 100-100 / 100 | 1200 / 1200 | 1.2-1.6 |
| sink | 24.8 / 26.8 / 19.5 / 26.8 | 13.3-19.1 | 14.8-21.4 | 0-0 / 100 | 1197 / 1200 | 0.3-0.3 |
| sink_win | 99.0 / 99.0 / 99.0 / 99.0 | 23.0-28.3 | 51.0-52.1 | 100-100 / 100 | 1197 / 1200 | 1.0-1.1 |
| sink_vae | 24.8 / 26.8 / 19.5 / 26.8 | 12.7-18.5 | 14.8-21.4 | 0-0 / 100 | 1200 / 1200 | 0.4-0.9 |
| w12 | 23.1 / 30.6 / 21.7 / 31.3 | 44.8-51.1 | 41.3-45.7 | 0-0 / 100 | 1200 / 1200 | 12.3-12.4 |
| w12_vaeX | 23.1 / 30.6 / 21.7 / 31.3 | 44.8-51.1 | 41.3-45.7 | 0-0 / 100 | 1200 / 1200 | 12.9-13.0 |
| winX_vaeR12 | 99.0 / 99.0 / 99.0 / 99.0 | 79.7-80.5 | 99.0-99.0 | 100-100 / 100 | 1200 / 1200 | 9.4-11.5 |

**S (sanity): PASSES** in 4 / 4 streams: full and sink_win_vae equal R on 100 / 100 calls, frames 1200 / 1200, cross-attention recomputed exact (every condition).

**Q2 necessity.** VAE needed (sink_win W3 < 40): 0 / 4 streams -> **not needed** for W3 (sink_win W3 = 99 dB in 4 / 4; latents bit-exact 100 / 100), but a cold decoder drops 3 frames on the first call (1197 / 1200) and the first calls are low (first 23.0-28.3 dB, W1 51-52 dB; 99 dB from k = 14). Window needed (sink_vae W3 < 40): 4 / 4 -> **needed**.

**Q4 attribution of the W12 loss.** Window approximation alone (w12_vaeX) keeps W3 < 40 in 4 / 4 streams -> **a cause**; VAE approximation alone (winX_vaeR12) in 0 / 4 -> **not a cause** (W3 99 dB, latents 100 / 100; first call 79.7-80.5 dB, bit-exact from k = 2). w12 and w12_vaeX have identical output latents on all 100 calls in 4 / 4 streams; their frames differ only on the first call, by < 0.001 dB (w12's VAE cache after the replay differs from R's by 3.6e-4 relative), and are identical from k = 2.

Descriptive: after w12 the window's relative error is 0 in layers 0-1 and 5e-3 to 2e-2 in deeper layers; the output latents' relative error grows from 7e-3-1.6e-2 at k = 1 to 0.08-0.25 at k = 24-100. Consistent with amplification of a small window error by repeated generation; the mechanism itself is not shown here. The VAE decoder cache feeds nothing back into generation (latents bit-exact with any VAE cache when the window is exact).


## Phase 2, reconstruction feasibility and sensitivity (4 / 4 streams)

Runs: p0 s0 and p1 s1 on elves-01, p1 s0 elves-02, p0 s1 elves-03, all at commit 83c606b8 (no code difference under tools/longlive or third_party from Phase 1's commits). Run order w24, w48, w96, eps_*, winX_vae1, recache (execution order only).

| condition | W3 PSNR (dB), p0s0 / p1s0 / p0s1 / p1s1 | window layers exact | first call | W1 | latents bit-exact | frames | build (s) | est. ready @1 Gbps (s) |
|---|---|---|---|---|---|---|---|---|
| w24 | 31.1 / 29.9 / 21.2 / 30.7 | 11 / 30 | 48.7-52.0 | 42.1-46.8 | 0 / 100 | 1200 / 1200 | 24.6-24.8 | 31.6-31.8 |
| w48 | 24.1 / 30.5 / 21.1 / 31.1 | 23 / 30 | 47.9-52.0 | 41.3-47.6 | 0 / 100 | 1200 / 1200 | 49.2-49.6 | 56.3-56.7 |
| w96 | 99.0 / 99.0 / 99.0 / 99.0 | 30 / 30 | 99.0 | 99.0 | 100 / 100 | 1200 / 1200 | 98.5-99.4 | 105.8-106.8 |
| eps_win | 24.0 / 30.8 / 22.2 / 30.7 | 0 / 30 | 47.0-51.2 | 42.4-48.6 | 0 / 100 | 1200 / 1200 | 2.0-4.7 | 45.5-48.2 |
| eps_vae | 99.0 / 99.0 / 99.0 / 99.0 | 30 / 30 | 57.8-58.8 | 59.1-59.7 | 100 / 100 | 1200 / 1200 | 1.3-4.6 | 44.8-48.1 |
| eps_sink | 24.0 / 31.3 / 21.9 / 29.9 | 30 / 30 | 48.2-51.7 | 40.5-47.7 | 0 / 100 | 1200 / 1200 | 1.7-3.0 | 45.2-46.5 |
| winX_vae1 | 99.0 / 99.0 / 99.0 / 99.0 | 30 / 30 | 38.0-41.9 | 54.9-56.4 | 100 / 100 | 1200 / 1200 | 1.3-1.9 | 28.9-29.5 |
| recache | 26.0 / 29.2 / 22.4 / 29.9 | 1 / 30 | 29.0-32.5 | 24.4-32.9 | 0 / 100 | 1200 / 1200 | 1.9-2.4 | 8.8-9.4 |

Perturbations (relative 2^-8, random sign, bf16): elements changed and realized relative error: eps_win 0.996-0.996 / 5.75e-03-5.75e-03; eps_vae 0.994-0.994 / 5.77e-03-5.79e-03; eps_sink 0.996-0.996 / 5.74e-03-5.75e-03.

**Q3 reconstruction.** VAE rebuildable from the latent log (W3 >= 40 and frames complete): from 12 blocks 4 / 4, from 1 block 4 / 4 streams -> **rebuildable** (1 block: first call 38.0-41.9 dB, W1 54.9-56.4 dB, 99 dB in W2-W3). Window: W3 >= 40 for W = 12 / 24 / 48 / 96 in 0 / 0 / 0 / 4 streams -> **W* = 96** (bit-exact window and latents at W = 96 in 4 / 4); window layers exact 5 / 11 / 23 / 30 at W = 12 / 24 / 48 / 96 (identical in all streams), about one layer per two replayed calls. A window with 23 / 30 layers exact (W = 48) is still at 21-31 dB: fidelity is close to all-or-nothing in the window's exactness.

**Q1 sensitivity (evidence, not proof).** W3 < 40 after a 5.7e-3 relative perturbation: window 4 / 4, sink 4 / 4, VAE 0 / 4 streams -> the output is **sensitive to small window and sink errors** (W3 21-31 dB, the level of the approximate reconstructions) and **not to VAE-cache errors** (first call 58 dB, W1 59 dB, 99 dB from W2: the decoder cache feeds nothing back).

**Feasibility axes (section 5; estimated readiness = bytes at 1 Gbps + build, not a migration measurement):**

| condition | ships | fidelity feasible (W3 >= 40, frames complete) | performance screen (est. < 44 s) | applicable (candidate) |
|---|---|---|---|---|
| w12 | sink + replay log | 0 / 4 | 4 / 4 | no |
| w24 | sink + replay log | 0 / 4 | 4 / 4 | no |
| w48 | sink + replay log | 0 / 4 | 0 / 4 | no |
| w96 | sink + replay log | 4 / 4 | 0 / 4 | no |
| recache | sink + latent buffer | 0 / 4 | 4 / 4 | no |
| sink | sink | 0 / 4 | 4 / 4 | no |
| winX_vaeR12 | sink + window + 12 log blocks | 4 / 4 | 4 / 4 | yes |
| winX_vae1 | sink + window + 1 log block | 4 / 4 | 4 / 4 | yes |
| sink_win | sink + window | 0 / 4 | 4 / 4 | no |
| w12_vaeX | sink + VAE + replay log | 0 / 4 | 4 / 4 | no |
| sink_vae | sink + VAE | 0 / 4 | 4 / 4 | no |

**Direction (as written): hybrid.** No condition that ships neither window nor VAE is applicable: the only fidelity-feasible one, w96, needs a 98.5-99.4 s replay (est. 106 s at 1 Gbps; fails the screen). Two that ship the window exactly and rebuild the VAE from the latent log are applicable candidates: winX_vae1 (3.21 GiB + 1 block, est. 29-30 s) and winX_vaeR12 (3.22 GiB, est. 37-39 s), i.e. 1.85 GiB (36 %) less than the 5.06 GiB state. These are static estimates; whether the hybrid works live (snapshot while the source serves, exact catch-up replay, switch) is the frozen feasibility study `snapshot_prereg.md`.

Observation outside the preregistered rules (no claim): w96 rebuilds the window exactly from the sink alone (0.86 GiB + log); run live, its 99 s replay could overlap with the source's serving. Not part of any preregistration; would need its own.
