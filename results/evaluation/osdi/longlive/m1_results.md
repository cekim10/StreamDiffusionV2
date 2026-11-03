# LongLive M1 (Continuity Replay) cross-model check: results

Rules: `m1_prereg.md` section 5. Measured on the testbed; PSNR vs the source's shadow continuation.

**otter_w96 (8 runs, 0 catch-up timeouts = migration failures, excluded below):** R1a generation state (sink + window fingerprint) HOLDS; R1b latents 100 / 100 HOLDS; R1c frames complete HOLDS; R2 catch-up HOLDS; R3 max output gap < Full HOLDS (4 / 4); R4 readiness < Full FAILS (0 / 4); R5 bytes < Full HOLDS. Frame fidelity (first call, W1-W3, frames bit-exact) is reported in the table, not part of R1.

| stream | max gap otter_w96 / Full (s) | difference (s) | readiness otter_w96 / Full (s) | difference (s) | bytes otter_w96 / Full (GiB) |
|---|---|---|---|---|---|
| p0_s0 | 3.23 / 49.84 | -46.60 | 59.43 / 47.55 | 11.88 | 0.87 / 5.06 |
| p0_s1 | 3.24 / 49.60 | -46.37 | 58.42 / 47.33 | 11.09 | 0.87 / 5.06 |
| p1_s0 | 3.24 / 49.72 | -46.48 | 59.23 / 47.47 | 11.75 | 0.87 / 5.06 |
| p1_s1 | 3.24 / 49.53 | -46.28 | 59.22 / 47.28 | 11.94 | 0.87 / 5.06 |

**Reading (section 5, as written):** M1 works on LongLive (exact, continuous, fewer bytes) but is not faster to be ready than Full: functional generality of M1 shown, performance generality not.

Readiness of otter_w96, medians over its runs (s; measured, destination clock):

| sink transfer | import | context-only replay | VAE rebuild | decode-replay | other | readiness | Full: transfer / import / readiness |
|---|---|---|---|---|---|---|---|
| 7.22 | 0.26 | 31.56 (113 calls, 0.280 s each) | 8.77 | 10.28 (10 calls) | 0.75 | 58.69 | 46.89 / 0.54 / 47.45 |

| arm | stream | runs | readiness (s) | max output gap (s) | delivery gap (s) | src interval before / during migration (s) | log copy (ms) | bytes to switch (GiB) | W1 / W2 / W3 PSNR (dB) | first call | frames bit-exact | latents equal | frames complete | timeouts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| otter_w96 | p0 s0 | 2 | 59.43 | 3.23 | 3.23 | 2.11 / 2.12 | 0.1 | 0.87 | 99.0 / 99.0 / 99.0 | 99.0 | 100-100 | 100 / 100 | True | 0 |
| otter_w96 | p0 s1 | 2 | 58.42 | 3.24 | 3.24 | 2.11 / 2.12 | 0.1 | 0.87 | 99.0 / 99.0 / 99.0 | 99.0 | 100-100 | 100 / 100 | True | 0 |
| otter_w96 | p1 s0 | 2 | 59.23 | 3.24 | 3.24 | 2.11 / 2.11 | 0.1 | 0.87 | 99.0 / 99.0 / 99.0 | 99.0 | 100-100 | 100 / 100 | True | 0 |
| otter_w96 | p1 s1 | 2 | 59.22 | 3.24 | 3.24 | 2.11 / 2.11 | 0.1 | 0.87 | 99.0 / 99.0 / 99.0 | 99.0 | 100-100 | 100 / 100 | True | 0 |
| otter_w12 | p0 s0 | 2 | 31.93 | 3.23 | 3.23 | 2.11 / 2.12 | 0.1 | 0.82 | 47.5 / 41.5 / 27.9 | 51.7 | 0-0 | 0 / 100 | True | 0 |
| otter_w12 | p0 s1 | 2 | 31.93 | 3.22 | 3.22 | 2.11 / 2.12 | 0.2 | 0.82 | 44.2 / 32.4 / 23.8 | 51.7 | 0-0 | 0 / 100 | True | 0 |
| otter_w12 | p1 s0 | 2 | 31.93 | 3.22 | 3.22 | 2.11 / 2.12 | 0.1 | 0.82 | 45.6 / 39.1 / 29.4 | 50.8 | 0-0 | 0 / 100 | True | 0 |
| otter_w12 | p1 s1 | 2 | 31.95 | 3.23 | 3.23 | 2.12 / 2.12 | 0.2 | 0.82 | 44.5 / 37.7 / 30.3 | 52.3 | 0-0 | 0 / 100 | True | 0 |
| recache | p0 s0 | 2 | 10.57 | 4.07 | 4.07 | 2.11 / 2.11 | 0.0 | 0.81 | 30.0 / 24.7 / 24.6 | 30.0 | 0-0 | 0 / 100 | True | 0 |
| recache | p0 s1 | 2 | 10.55 | 4.05 | 4.05 | 2.12 / 2.11 | 0.0 | 0.81 | 21.2 / 18.9 / 20.2 | 26.1 | 0-0 | 0 / 100 | True | 0 |
| recache | p1 s0 | 2 | 10.57 | 4.04 | 4.04 | 2.11 / 2.12 | 0.0 | 0.81 | 33.3 / 31.8 / 29.2 | 34.0 | 0-0 | 0 / 100 | True | 0 |
| recache | p1 s1 | 2 | 10.57 | 4.06 | 4.06 | 2.12 / 2.12 | 0.0 | 0.81 | 34.6 / 34.9 / 30.8 | 34.3 | 0-0 | 0 / 100 | True | 0 |
| full | p0 s0 | 2 | 47.55 | 49.84 | 49.84 | 2.11 / - | - | 5.06 | 99.0 / 99.0 / 99.0 | 99.0 | 100-100 | 100 / 100 | True | 0 |
| full | p0 s1 | 2 | 47.33 | 49.60 | 49.60 | 2.11 / - | - | 5.06 | 99.0 / 99.0 / 99.0 | 99.0 | 100-100 | 100 / 100 | True | 0 |
| full | p1 s0 | 2 | 47.47 | 49.72 | 49.72 | 2.12 / - | - | 5.06 | 99.0 / 99.0 / 99.0 | 99.0 | 100-100 | 100 / 100 | True | 0 |
| full | p1 s1 | 2 | 47.28 | 49.53 | 49.53 | 2.11 / - | - | 5.06 | 99.0 / 99.0 / 99.0 | 99.0 | 100-100 | 100 / 100 | True | 0 |
