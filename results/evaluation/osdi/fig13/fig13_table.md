# Fig. 13 per-input table (OTTER, fixed cutover; measured)

| input | refresh / 100 calls | conditions | schedule diverged (%) | first call (dB) | W3 PSNR median [min-max] (dB) | W3 >= 40 dB (%) | W3 tPSNR (dB) | both >= 40 dB (%) |
|---|---|---|---|---|---|---|---|---|
| Bird | 3.6 | 15 | 53 | 29.9 | 39.8 [34.5-44.3] | 47 | 39.2 | 47 |
| Dog | 3.6 | 15 | 40 | 28.7 | 48.0 [40.5-48.5] | 100 | 47.2 | 100 |
| Boxing | 8.2 | 15 | 40 | 35.3 | 46.9 [38.3-49.2] | 80 | 44.4 | 73 |
| Basketball | 9.1 | 15 | 87 | 30.6 | 44.2 [36.3-47.7] | 60 | 43.7 | 53 |
| Hockey | 16.4 | 15 | 47 | 31.3 | 43.9 [38.5-45.3] | 87 | 42.6 | 87 |
| Swimmer | 22.7 | 15 | 67 | 27.5 | 39.3 [38.0-39.8] | 0 | 37.9 | 0 |
| Train | 34.5 | 15 | 67 | 33.5 | 46.0 [39.8-46.7] | 93 | 46.3 | 93 |
| Audi | 53.6 | 15 | 100 | 27.1 | 33.8 [31.3-41.0] | 13 | 34.1 | 13 |
| Circus | 89.1 | 15 | 100 | 33.6 | 41.6 [31.2-48.5] | 53 | 41.6 | 53 |
| Butterfly | 128.2 | 15 | 87 | 33.2 | 43.8 [39.3-45.4] | 87 | 43.3 | 87 |
| **All** | | 150 | 69 | 30.8 | 43.2 [31.2-49.2] | 62 | 42.6 | 61 |

W3 = calls 25-100 after the cutover (median per condition); conditions = 15 cutover calls per input (seed 0: S 70-79, seed 1: S 70-78 step 2). 40 dB is an operational threshold, not a perceptual one.
