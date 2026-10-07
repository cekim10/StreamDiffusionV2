# Late-binding handoff prototype: policy x bandwidth

Destination steady-state service time S = 547 ms/chunk (4 frames). Times are seconds after the destination's READY (t_mig). stall = time to the first output chunk minus S. missed = missing output chunks plus output gaps longer than 2S after resume (hiccups, e.g. from background-transfer contention). PSNR vs the destination's own bit-exact baseline (99 = identical, ~20 = different stream).

| policy | BW (Mbps) | fg MB | bg MB | first output s | stall s | missed/hiccup chunks | sink arrived s | bound at call | PSNR M+0..7 | PSNR gap->bind | PSNR after bind+8 | PSNR M+16.. | PSNR last 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cold | 500 | 0.0 | 0 | 1.07 | 0.52 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.8 |
| full | 500 | 6163.8 | 0 | 109.69 | 109.14 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 500 | 2.7 | 1645 | 1.43 | 0.88 | 1 | 29.17 | 82 | 16.5 | 16.7 | 39.7 | 25.5 | 40.8 |
| ours_refresh | 500 | 2.7 | 1645 | 1.54 | 0.99 | 1 | 29.49 | 81 | 16.7 | 18.4 | 30.0 | 23.6 | 30.0 |
| replay | 500 | 42.3 | 0 | 6.35 | 5.81 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 30.0 |
| cold | 1000 | 0.0 | 0 | 1.06 | 0.51 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.8 |
| full | 1000 | 6163.8 | 0 | 57.18 | 56.63 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 1000 | 2.7 | 1645 | 1.56 | 1.01 | 0 | 15.32 | 57 | 16.5 | 16.7 | 43.6 | 37.0 | 43.6 |
| ours_refresh | 1000 | 2.7 | 1645 | 1.42 | 0.88 | 0 | 15.04 | 56 | 16.7 | 17.8 | 30.4 | 27.9 | 30.0 |
| replay | 1000 | 42.3 | 0 | 5.96 | 5.41 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 30.0 |
| cold | 2000 | 0.0 | 0 | 1.06 | 0.52 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.8 |
| full | 2000 | 6163.8 | 0 | 31.28 | 30.73 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 2000 | 2.7 | 1645 | 1.54 | 0.99 | 0 | 8.33 | 44 | 16.5 | 16.6 | 43.6 | 42.4 | 43.7 |
| ours_refresh | 2000 | 2.7 | 1645 | 1.45 | 0.90 | 0 | 8.36 | 44 | 16.7 | 17.3 | 43.8 | 42.7 | 43.8 |
| replay | 2000 | 42.3 | 0 | 5.90 | 5.35 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 30.0 |
| cold | 5000 | 0.0 | 0 | 1.06 | 0.51 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.8 |
| full | 5000 | 6163.8 | 0 | 15.57 | 15.02 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 5000 | 2.7 | 1645 | 1.51 | 0.96 | 0 | 4.01 | 36 | 17.4 | 16.2 | 43.9 | 44.0 | 43.7 |
| ours_refresh | 5000 | 2.7 | 1645 | 1.44 | 0.89 | 0 | 3.92 | 36 | 17.1 | 16.4 | 43.9 | 43.9 | 43.7 |
| replay | 5000 | 42.3 | 0 | 5.71 | 5.16 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 30.0 |
| cold | 10000 | 0.0 | 0 | 1.07 | 0.52 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.8 |
| full | 10000 | 6163.8 | 0 | 10.40 | 9.85 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 10000 | 2.7 | 1645 | 1.44 | 0.90 | 0 | 2.76 | 34 | 19.7 | 16.1 | 45.4 | 45.5 | 46.4 |
| ours_refresh | 10000 | 2.7 | 1645 | 1.38 | 0.83 | 0 | 2.73 | 34 | 19.6 | 16.1 | 45.4 | 45.6 | 46.4 |
| replay | 10000 | 42.3 | 0 | 5.69 | 5.14 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 30.0 |

Headline check: for `ours`, first-output time should be independent of bandwidth (fast path only), while `full` first-output time scales with 6.2 GB / BW; `ours` should rejoin the baseline (PSNR after bind+8 >= 35) once the sink binds, `cold` should stay near 20 dB.
