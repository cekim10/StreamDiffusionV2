# Prompt/clip sweep: does the state asymmetry reproduce?

Criteria (fixed in tools/aggregate_prompt_sweep.py before the sweep ran): D = no-Sink mean over M+16.. < 30 dB and no chunk >= 35 dB after M+4; E = no-ephemeral reaches >= 35 dB and its last-16-chunk mean >= 35 dB.

| source | run | case | input clip | seed | k | window | no Sink mean M+16.. | no Sink max after M+4 | no eph. M+0 | no eph. first >= 35 | no eph. mean M+16.. | no eph. last 16 | gap | D | E | refreshes before M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sweep | bird_s0_k2 | bird | bird | 0 | 2 | 80 | 18.4 | 19.9 | 15.5 | 36 | 29.6 | 28.9 | 11.2 | True | False | [20] |
| sweep | bird_s1_k2 | bird | bird | 1 | 2 | 80 | 18.5 | 19.7 | 15.9 | None | 30.5 | 29.4 | 12.0 | True | False | [20] |
| sweep | bird_s2_k2 | bird | bird | 2 | 2 | 80 | 18.5 | 19.8 | 15.8 | 57 | 33.1 | 36.6 | 14.6 | True | True | [20] |
| sweep | boxing_s0_k2 | boxing | boxing | 0 | 2 | 80 | 22.6 | 24.7 | 20.9 | 9 | 36.6 | 37.1 | 14.0 | True | True | [] |
| sweep | boxing_s1_k2 | boxing | boxing | 1 | 2 | 80 | 22.8 | 24.8 | 20.9 | 7 | 45.1 | 45.7 | 22.3 | True | True | [] |
| sweep | boxing_s2_k2 | boxing | boxing | 2 | 2 | 80 | 22.8 | 24.5 | 20.7 | 10 | 36.9 | 38.4 | 14.1 | True | True | [] |
| sweep | dragonA_bird_s0_k2 | dragonA_bird | bird | 0 | 2 | 80 | 19.2 | 21.5 | 16.0 | 30 | 35.8 | 37.0 | 16.6 | True | True | [20] |
| sweep | dragonA_bird_s1_k2 | dragonA_bird | bird | 1 | 2 | 80 | 19.2 | 20.7 | 16.2 | 23 | 35.7 | 36.1 | 16.4 | True | True | [] |
| sweep | dragonA_bird_s2_k2 | dragonA_bird | bird | 2 | 2 | 80 | 18.7 | 20.4 | 15.4 | 23 | 35.7 | 36.4 | 17.0 | True | True | [] |
| sweep | dragonA_dog_s0_k2 | dragonA_dog | original | 0 | 2 | 80 | 19.2 | 20.9 | 17.2 | 14 | 37.3 | 39.1 | 18.2 | True | True | [] |
| sweep | dragonA_dog_s1_k2 | dragonA_dog | original | 1 | 2 | 80 | 18.7 | 20.1 | 17.5 | 16 | 35.1 | 35.9 | 16.4 | True | True | [] |
| sweep | dragonA_dog_s2_k2 | dragonA_dog | original | 2 | 2 | 80 | 19.2 | 21.0 | 17.2 | 13 | 38.2 | 40.7 | 19.0 | True | True | [] |
| sweep | dragonB_dog_s0_k2 | dragonB_dog | original | 0 | 2 | 80 | 18.6 | 19.9 | 17.7 | 11 | 42.5 | 43.2 | 23.9 | True | True | [] |
| sweep | dragonB_dog_s1_k2 | dragonB_dog | original | 1 | 2 | 80 | 18.9 | 20.2 | 18.1 | 10 | 45.5 | 46.6 | 26.6 | True | True | [] |
| sweep | dragonB_dog_s2_k2 | dragonB_dog | original | 2 | 2 | 80 | 18.7 | 20.5 | 18.3 | 10 | 39.3 | 40.7 | 20.5 | True | True | [] |
| sweep | original_s0_k2 | original | original | 0 | 2 | 80 | 20.3 | 21.5 | 19.3 | 8 | 46.1 | 47.0 | 25.8 | True | True | [] |
| sweep | original_s1_k2 | original | original | 1 | 2 | 80 | 20.5 | 21.8 | 19.2 | 8 | 45.8 | 46.9 | 25.3 | True | True | [] |
| sweep | original_s2_k2 | original | original | 2 | 2 | 80 | 20.7 | 22.1 | 19.6 | 8 | 42.2 | 43.2 | 21.5 | True | True | [] |
| sweep | train_s0_k2 | train | train | 0 | 2 | 80 | 17.5 | 18.6 | 16.0 | 10 | 37.2 | 35.2 | 19.7 | True | True | [20, 22] |
| sweep | train_s1_k2 | train | train | 1 | 2 | 80 | 17.1 | 18.1 | 16.6 | 23 | 34.4 | 35.1 | 17.4 | True | True | [20, 22] |
| sweep | train_s2_k2 | train | train | 2 | 2 | 80 | 18.0 | 19.4 | 16.0 | 12 | 34.0 | 33.9 | 16.0 | True | False | [20, 22] |
| grid | bird_s0_k1 | bird | bird | 0 | 1 | 40 | 22.3 | 23.8 | 17.7 | 7 | 46.5 | 46.5 | 24.1 | True | True | [] |
| grid | bird_s0_k2 | bird | bird | 0 | 2 | 40 | 18.3 | 19.9 | 15.5 | 36 | 30.4 | 30.6 | 12.2 | True | False | [20] |
| grid | bird_s0_k4 | bird | bird | 0 | 4 | 40 | 15.5 | 17.4 | 14.9 | None | 23.8 | 24.0 | 8.3 | True | False | [5, 21] |
| grid | boxing_s0_k1 | boxing | boxing | 0 | 1 | 40 | 26.7 | 29.0 | 18.5 | 4 | 43.2 | 43.5 | 16.5 | True | True | [] |
| grid | boxing_s0_k2 | boxing | boxing | 0 | 2 | 40 | 22.7 | 24.7 | 20.9 | 9 | 35.6 | 36.4 | 12.9 | True | True | [] |
| grid | boxing_s0_k4 | boxing | boxing | 0 | 4 | 40 | 20.3 | 22.0 | 20.8 | 12 | 42.5 | 42.7 | 22.2 | True | True | [14, 20] |
| grid | original_s0_k1 | original | original | 0 | 1 | 40 | 23.6 | 25.8 | 16.8 | 6 | 49.0 | 49.0 | 25.4 | True | True | [] |
| grid | original_s0_k2 | original | original | 0 | 2 | 40 | 20.3 | 21.5 | 19.3 | 8 | 45.8 | 45.4 | 25.4 | True | True | [] |
| grid | original_s0_k4 | original | original | 0 | 4 | 40 | 17.9 | 19.5 | 19.5 | 12 | 45.1 | 45.1 | 27.2 | True | True | [] |
| grid | original_s1_k2 | original | original | 1 | 2 | 40 | 20.5 | 21.5 | 19.2 | 8 | 45.3 | 44.9 | 24.7 | True | True | [] |

D holds in 31/31 runs, E in 26/31 runs.

Fig. 3 rule pick: dragonB_dog_s1_k2 (gap 26.6 dB)
Manual override (FIG3_SELECTED): results/state_migration/prompt_sweep/dragonA_bird_s2_k2
