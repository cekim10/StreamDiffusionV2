# Prompt/clip sweep: does the state asymmetry reproduce?

Criteria (fixed in tools/aggregate_prompt_sweep.py before the sweep ran): D = no-Sink mean over M+16.. < 30 dB and no chunk >= 35 dB after M+4; E = no-ephemeral reaches >= 35 dB and its last-16-chunk mean >= 35 dB.

| source | run | clip | seed | k | window | no Sink mean M+16.. | no Sink max after M+4 | no eph. M+0 | no eph. first >= 35 | no eph. mean M+16.. | no eph. last 16 | gap | D | E | refreshes before M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| grid | bird_s0_k1 | bird | 0 | 1 | 40 | 22.3 | 23.8 | 17.7 | 7 | 46.5 | 46.5 | 24.1 | True | True | [] |
| grid | bird_s0_k2 | bird | 0 | 2 | 40 | 18.3 | 19.9 | 15.5 | 36 | 30.4 | 30.6 | 12.2 | True | False | [20] |
| grid | bird_s0_k4 | bird | 0 | 4 | 40 | 15.5 | 17.4 | 14.9 | None | 23.8 | 24.0 | 8.3 | True | False | [5, 21] |
| grid | boxing_s0_k1 | boxing | 0 | 1 | 40 | 26.7 | 29.0 | 18.5 | 4 | 43.2 | 43.5 | 16.5 | True | True | [] |
| grid | boxing_s0_k2 | boxing | 0 | 2 | 40 | 22.7 | 24.7 | 20.9 | 9 | 35.6 | 36.4 | 12.9 | True | True | [] |
| grid | boxing_s0_k4 | boxing | 0 | 4 | 40 | 20.3 | 22.0 | 20.8 | 12 | 42.5 | 42.7 | 22.2 | True | True | [14, 20] |
| grid | original_s0_k1 | original | 0 | 1 | 40 | 23.6 | 25.8 | 16.8 | 6 | 49.0 | 49.0 | 25.4 | True | True | [] |
| grid | original_s0_k2 | original | 0 | 2 | 40 | 20.3 | 21.5 | 19.3 | 8 | 45.8 | 45.4 | 25.4 | True | True | [] |
| grid | original_s0_k4 | original | 0 | 4 | 40 | 17.9 | 19.5 | 19.5 | 12 | 45.1 | 45.1 | 27.2 | True | True | [] |
| grid | original_s1_k2 | original | 1 | 2 | 40 | 20.5 | 21.5 | 19.2 | 8 | 45.3 | 44.9 | 24.7 | True | True | [] |

D holds in 10/10 runs, E in 8/10 runs.

Fig. 3 rule pick: none (no sweep run with frames satisfies D and E)
Manual override (FIG3_SELECTED): none
