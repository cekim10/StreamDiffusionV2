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

## Dragon prompts (2026-10-09, 9 more runs)

Prompts A (flying, castle courtyard) and B (walking, village, tower) from `examples/dragon_{a,b}_prompt.txt`, on the dog
clip (A and B) and the bird clip (A), seeds 0/1/2, same conditions and criteria as above.

| case | input clip | D | E | gap from M+16 (dB) | no Sink, mean from M+16 | no eph., mean from M+16 |
|---|---|---|---|---|---|---|
| dragonB_dog | dog | 3/3 | 3/3 | 20.5 / 26.6 / 23.9 | 18.6-18.9 | 39.3-45.5 |
| dragonA_dog | dog | 3/3 | 3/3 | 16.4-19.0 | 18.7-19.2 | 35.1-38.2 |
| dragonA_bird | bird | 3/3 | 3/3 | 16.4-17.0 | 18.7-19.2 | 35.7-35.8 |

Totals now: D 31/31, E 26/31; E holds in 21/21 runs without an adaptive Sink refresh before migration and 5/10 with one.
The bird clip under the dragon prompt refreshed before M in only one seed (s0) and healed in all three, unlike the bird
clip under its own prompt; refresh depends on the generated content, not only on the clip.

Visual reading. Video-to-video keeps the input clip's subject and motion: on the dog clip both dragon prompts produce a
red cat-like animal on grass (no wings, village or tower); on the bird clip prompt A produces a red feathered,
dragon-like creature on a branch. Without the Sink KV the bird-clip creature changes visibly (green, scaled face, open
mouth at M+8..M+32), the clearest appearance divergence of all candidates, but its ephemeral recovery is slower (31 dB at
M+16, 39 dB at M+32 in s1).

Rule pick changed: the pre-registered rule now picks `dragonB_dog_s1_k2` (gap 26.6 dB vs the dog's 25.8). Fig. 3 in the
repo has NOT been re-rendered yet; it switches to the rule pick on the next run of make_background_figures.py unless
FIG3_SELECTED overrides it. Decision: the user chose the bird-clip dragon; FIG3_SELECTED = dragonA_bird_s2_k2 (seed by the same rule). Its ephemeral recovery is not monotone: >= 35 dB first at M+23, dips to 33-35 dB at M+54..66, sustained from M+67.
