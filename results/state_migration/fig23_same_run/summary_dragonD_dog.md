# Fig. 2b / 3 same-run case dragonD_dog

Criteria and rule: tools/select_fig23_run.py (fixed before the runs).

| run | D | E | gap M+16.. (dB) | no in-flight rows: mean M+16.. / last 16 | no recent KV: mean M+16.. / last 16 | no VAE caches: mean M+16.. / last 16 | no recent KV + VAE: mean M+16.. / last 16 | no Sink KV: mean M+16.. / last 16 | no-eph first >= 35 |
|---|---|---|---|---|---|---|---|---|---|
| dragonD_dog_s0_k2 | True | True | 26.3 | 35.9 / 35.5 | 47.4 / 48.3 | 46.7 / 47.4 | 45.8 / 46.5 | 19.5 / 19.8 | M+9 |
| dragonD_dog_s1_k2 | True | True | 26.2 | 36.2 / 35.3 | 47.3 / 48.2 | 46.2 / 47.0 | 45.6 / 46.3 | 19.4 / 19.7 | M+9 |
| dragonD_dog_s2_k2 | True | True | 26.2 | 35.9 / 35.3 | 47.3 / 48.2 | 46.4 / 47.3 | 45.5 / 46.2 | 19.2 / 19.5 | M+9 |

D in 3 / 3, E in 3 / 3; gap median 26.2 dB, range 26.2-26.3
Selected (rule): dragonD_dog_s0_k2 (gap 26.3 dB)
