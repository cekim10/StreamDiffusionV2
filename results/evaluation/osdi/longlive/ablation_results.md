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

Phase 2 (reconstruction feasibility and sensitivity) runs next: sanity holds in all four streams.
