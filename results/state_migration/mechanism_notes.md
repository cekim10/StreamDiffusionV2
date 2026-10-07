# Mechanism run reading (results/state_migration/mechanism, harness 1682bb9, bit-exact)

## Serialization is exact
`xfer_all` (whole live state serialized at M, restored into a freshly allocated destination) = 99 dB. The earlier `sinkxfer` numbers were a harness bug (sink copied into a ring buffer whose bookkeeping did not match); the transfer operation itself is now validated.

## What the destination actually needs (fresh destination, component transfer)
| transferred | bytes | PSNR M+0 | M+0..7 | M+16.. | SSIM M+16.. |
|---|---|---|---|---|---|
| meta only | 2 MB | 10.4 | 16.4 | 19.1 | 0.747 |
| meta + vae + inflight (no sink) | 2.9 GB | 21.1 | 17.4 | 18.7 | 0.747 |
| sink + meta | 1.6 GB | 10.2 | 22.5 | 35.2 | 0.970 |
| sink + meta + vae | 4.5 GB | 9.2 | 22.9 | 35.8 | 0.972 |
| sink + meta + vae + inflight | 4.5 GB | 25.7 | 27.1 | 47.7 | 0.997 |
| everything | 9.5 GB | 99 | 99 | 99 | 1.000 |

- Without the sink the destination is on a different stream for good (19 dB), whatever else it gets.
- With sink + metadata only, the ring refills naturally and continuity reaches 35 dB / 0.97.
- The 0.2 MB in-flight row is worth +12 dB long-term (35.8 -> 47.7) and +16 dB at M+0 (9 -> 26): losing it destroys chunk M-1 and the damage propagates (likely through the sink-refresh decision at call 48). It is the one piece of immediate state and it is tiny.
- The 2.9 GB of VAE caches buy nothing measurable (22.5 -> 22.9 early, 35.2 -> 35.8 late).
- Not yet run: `xfer_sink+meta+inflight` (sink + 2 MB fast path, no VAE). Prediction from the rows above: ~26 dB early, ~47 dB late. This is the configuration the design would use.

## Replay is dropped as a mechanism
`replay_3_sinkhist_pos` (5 s of replay, 42 MB of frames): 27.6 dB over M+0..7 and 29.3 long-term. It beats natural refill without the in-flight row early (+5 dB) but loses to "transfer sink + inflight + metadata" everywhere (27.1 / 47.7) at zero replay cost. Compute-based reconstruction is not worth it on this GPU.

## Placeholder then swap (refresh off, true sink arrives at M+D)
| D | zero: gap PSNR / rejoin / long-term | local placeholder: gap PSNR / rejoin / long-term |
|---|---|---|
| 1 | 28.0 / 2 / 43.9 | 28.9 / 2 / 44.0 |
| 4 | 23.0 / 4 / 43.8 | 24.1 / 3 / 44.1 |
| 8 | 20.1 / 5 / 43.0 | 22.8 / 3 / 43.4 |
| 16 | 18.5 / 4 / 42.4 | 21.8 / 4 / 42.8 |
| never (refresh on) | gap 22.6, long-term 20.3 | gap 22.8, long-term 20.7 |

- Late binding holds in the exact harness: the true sink swapped in 16 chunks (4 s) late rebinds the stream to 42-44 dB / SSIM 0.99 within 2-5 calls.
- A destination-local placeholder (recent slots copied into the sink slots) keeps the gap closer to the original trajectory by 1-3 dB and rejoins as fast or faster; long-term is unchanged. Letting adaptive refresh promote a new sink instead gives the same gap quality but never rejoins.
- Caveat: by absolute input fidelity (SSIM-vs-input) the local placeholder is slightly below zero during the gap (0.385 vs 0.399; baseline 0.406). The placeholder improves continuity with the original stream during the wait, not generic quality. A better placeholder (e.g. the source's sink of a few chunks ago, or a low-rank sketch of the true sink) is the obvious next candidate.

## Design that survives
Fast path: in-flight row + session/ring metadata (~2 MB) at migration. Background path: sink KV (1.6 GB) within ~16 chunks, bound atomically on arrival. Nothing else is transferred or recomputed; recent KV and VAE caches refill on their own. Principle: migrate state by its temporal semantics (immediate / durable / ephemeral), not by its size.

## Open before prototype
1. `xfer_sink+meta+inflight` to confirm the fast path without VAE.
2. Replicate the sink late-binding and placeholder results on a second video, k=1 and k=4, and a second seed.
3. A continuity metric that is not PSNR-to-baseline (identity/style similarity across the boundary) for the paper's primary evaluation.
