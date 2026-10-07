# Late-binding handoff prototype: policy x bandwidth

Destination steady-state service time S = 547 ms/chunk (4 frames). Times are seconds after the destination's READY (t_mig). stall = time to the first output chunk minus S. missed = missing output chunks plus output gaps longer than 2S after resume (hiccups, e.g. from background-transfer contention). PSNR vs the destination's own bit-exact baseline (99 = identical, ~20 = different stream).

| policy | BW (Mbps) | fg MB | bg MB | first output s | stall s | missed/hiccup chunks | sink arrived s | bound at call | PSNR M+0..7 | PSNR gap->bind | PSNR after bind+8 | PSNR M+16.. | PSNR last 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cold | 500 | 0.0 | 0 | 18.15 | 17.60 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.2 |
| full | 500 | 6163.8 | 0 | 138.85 | 138.30 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 500 | 2.7 | 1645 | 17.92 | 17.37 | 1 | 51.85 | None | 16.5 | nan | nan | 16.8 | 16.9 |
| replay | 500 | 42.3 | 0 | 23.48 | 22.93 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 32.8 |
| cold | 1000 | 0.0 | 0 | 18.16 | 17.62 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.2 |
| full | 1000 | 6163.8 | 0 | 86.68 | 86.13 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 1000 | 2.7 | 1645 | 17.97 | 17.42 | 1 | 37.37 | 66 | 16.5 | 16.7 | 30.1 | 23.5 | 30.8 |
| replay | 1000 | 42.3 | 0 | 23.14 | 22.59 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 32.8 |
| cold | 2000 | 0.0 | 0 | 18.25 | 17.70 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.2 |
| full | 2000 | 6163.8 | 0 | 59.73 | 59.18 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 2000 | 2.7 | 1645 | 18.12 | 17.58 | 1 | 29.61 | 51 | 16.5 | 16.6 | 30.4 | 28.3 | 30.8 |
| replay | 2000 | 42.3 | 0 | 23.03 | 22.48 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 32.8 |
| cold | 5000 | 0.0 | 0 | 18.25 | 17.70 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.2 |
| full | 5000 | 6163.8 | 0 | 44.56 | 44.01 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 5000 | 2.7 | 1645 | 18.01 | 17.46 | 1 | 24.57 | 42 | 16.5 | 16.5 | 43.8 | 42.8 | 45.7 |
| replay | 5000 | 42.3 | 0 | 22.87 | 22.32 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 32.8 |
| cold | 10000 | 0.0 | 0 | 18.24 | 17.69 | 1 | nan | None | 19.2 | nan | nan | 21.9 | 21.2 |
| full | 10000 | 6163.8 | 0 | 38.97 | 38.42 | 0 | nan | None | 99.0 | nan | nan | 99.0 | 99.0 |
| ours | 10000 | 2.7 | 1645 | 18.02 | 17.47 | 1 | 22.94 | 39 | 16.5 | 16.5 | 43.8 | 43.7 | 45.6 |
| replay | 10000 | 42.3 | 0 | 22.86 | 22.31 | 0 | nan | None | 27.6 | nan | nan | 30.1 | 32.8 |

Headline check: for `ours`, first-output time should be independent of bandwidth (fast path only), while `full` first-output time scales with 9.5 GB / BW; `ours` should rejoin the baseline (PSNR after bind+8 >= 35) once the sink binds, `cold` should stay near 20 dB.
