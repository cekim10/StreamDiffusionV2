# Prompt/clip sweep: reading (2026-10-09)

12 new runs (clips original/dog, train, boxing, bird x seeds 0, 1, 2; k = 2; migration at chunk 30; 80 chunks after
migration; frames saved) plus the 10 earlier grid runs (40 chunks, no frames). Two conditions per run against the run's
own uninterrupted baseline, PSNR on uncompressed frames:
- no Sink KV (`ph_localrefresh`)
- no recent KV + VAE caches (`xfer_sink+meta+inflight`; Sink, metadata and in-flight rows kept)

Criteria and the Fig. 3 selection rule were fixed in `tools/aggregate_prompt_sweep.py` and committed (9ddc74e) before
the sweep ran. Full table: `summary.md` / `summary.csv`. Per-clip curves: `figures/background/appendix/fig_state_loss_<clip>`.
Candidate strips for every run: `figures/background/candidates/fig3_<run>`.

## Results

| claim | holds in |
|---|---|
| D: without the Sink KV the stream stays on a different trajectory (mean PSNR from M+16 < 30 dB, never >= 35 dB after M+4) | 22 / 22 runs |
| E: without recent KV + VAE caches the stream returns to the reference (reaches 35 dB, last-16-chunk mean >= 35 dB) | 17 / 22 runs |

Healing of the ephemeral state depends on the Sink's refresh history:

| runs | E holds |
|---|---|
| no adaptive Sink refresh before migration (dog all, boxing k1/k2, bird k1) | 13 / 13 |
| a refresh before migration (bird k2/k4 all seeds, train all seeds, boxing k4) | 4 / 9 |

All five failures (bird s0/s1 k2 in the sweep, bird k2 and k4 in the grid, train s2) are refreshed runs. In the
failing bird runs, dropping recent KV alone or the VAE caches alone still heals (44 / 40 dB on bird k2); dropping both
together does not within 80 chunks. Train s2 misses by 1 dB (last-16 mean 33.9 dB).

Paper wording that the data supports: losing the Sink KV changes the trajectory in every run; losing ephemeral state
is transient when the Sink holds only its original anchors, and heals slowly or incompletely once adaptive refresh has
promoted recent frames into the Sink before migration (the durable anchor then depends on ephemeral history). Do not
claim that ephemeral loss always heals.

## Fig. 3 choice

The rule (largest mean PSNR gap between the two conditions from M+16, among sweep runs satisfying D and E) picked
`original_s0_k2` (dog, seed 0), gap 25.8 dB; next are dog s1 (25.3), boxing s1 (22.3), dog s2 (21.5), train s0 (19.7).
Fig. 3 uses it (FIG3_RULE_PICK); no manual override.

Visual reading of the candidates: this pipeline is video-to-video, so the input clip fixes motion and pose. Without the
Sink KV the boxer still throws the same punches at the same moments (21-24 dB) and the train rider keeps the same pose;
what diverges is appearance (identity, texture, color). The dog shows it most clearly (face and fur differ from the
reference while the scene stays plausible). A new clip (car, robot arm) would also follow its input motion, so
"different position / different motion" cannot appear in this mode; it would need text-to-video, which the harness
does not support and which has no VAE encoder caches (a different ephemeral state).
