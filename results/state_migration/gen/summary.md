# Generalization of temporal-semantics claims across video x seed x k

PSNR in dB vs each run's own baseline (bit-exact = 99). Columns: proposed policy = sink + meta + in-flight; no-inflight = sink + meta; no-sink = meta + in-flight.

| run | floor | k | policy M+0..7 | policy M+16.. | no-inflight M+16.. | no-sink M+16.. | drop_kv_recent M+16.. | drop_vae_all M+16.. | drop_inflight M+0 | ph_zero_8 gap / rejoin / late | ph_local_8 gap / rejoin / late | ph_localrefresh late | IMMEDIATE | DURABLE | EPHEMERAL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bird_s0_k1 | 99.0 | 1 | 27.6 | 46.5 | 46.5 | 22.2 | 48.0 | 46.4 | - | 23.0 / 4 / 47.2 | 25.1 / 3 / 47.3 | 22.3 | n/a (k=1) | PASS | PASS |
| bird_s0_k2 | 99.0 | 2 | 22.0 | 30.4 | 27.3 | 18.1 | 43.7 | 38.7 | 14.6 | 19.6 / 9 / 33.8 | 20.8 / 8 / 33.9 | 18.3 | FAIL | PASS | PASS |
| bird_s0_k4 | 99.0 | 4 | 18.0 | 23.8 | 22.8 | 15.4 | 32.2 | 29.9 | 13.2 | 19.3 / 14 / 31.7 | 20.1 / 13 / 32.5 | 15.5 | FAIL | FAIL | FAIL |
| boxing_s0_k1 | 99.0 | 1 | 32.8 | 43.2 | 43.2 | 25.5 | 53.5 | 43.1 | - | 24.9 / 1 / 52.9 | 27.2 / 0 / 52.9 | 26.7 | n/a (k=1) | FAIL | PASS |
| boxing_s0_k2 | 99.0 | 2 | 26.3 | 35.6 | 32.5 | 22.2 | 37.9 | 35.6 | 10.4 | 22.7 / 2 / 35.2 | 25.0 / 2 / 35.2 | 22.7 | FAIL | PASS | PASS |
| boxing_s0_k4 | 99.0 | 4 | 23.1 | 42.5 | 32.7 | 19.7 | 46.0 | 44.5 | 9.7 | 24.0 / 9 / 38.3 | 25.7 / 5 / 39.1 | 20.3 | PASS | PASS | PASS |
| original_s0_k1 | 99.0 | 1 | 28.0 | 49.0 | 49.0 | 21.3 | 50.2 | 49.0 | - | 21.7 / 3 / 46.6 | 25.3 / 1 / 46.7 | 23.6 | n/a (k=1) | PASS | PASS |
| original_s0_k2 | 99.0 | 2 | 24.4 | 45.8 | 35.2 | 18.8 | 47.7 | 46.5 | 10.4 | 20.1 / 5 / 43.0 | 22.8 / 3 / 43.4 | 20.3 | PASS | PASS | PASS |
| original_s0_k4 | 99.0 | 4 | 22.1 | 45.1 | 30.9 | 16.8 | 46.7 | 45.5 | 9.9 | 21.8 / 10 / 33.6 | 23.3 / 6 / 34.4 | 17.9 | PASS | PASS | PASS |
| original_s1_k2 | 99.0 | 2 | 25.1 | 45.3 | 34.1 | 18.8 | 47.8 | 46.4 | 10.4 | 20.4 / 6 / 43.4 | 23.0 / 3 / 43.5 | 20.5 | PASS | PASS | PASS |

Tally (pass/fail): IMMEDIATE 4/7, DURABLE 8/10, EPHEMERAL 9/10

Thresholds: IMMEDIATE >= 6 dB gain from the in-flight row; DURABLE no-sink < 25 dB and rejoin <= 8 calls after an 8-chunk-late sink; EPHEMERAL >= 35 dB after dropping recent KV and after dropping VAE caches. Runs whose floor is not 99 are not bit-exact and should be inspected.
