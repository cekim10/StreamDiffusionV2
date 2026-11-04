# Fig. 14 results

Rules: `preregistration.md`. 14a native: medians over reps of each run's median per-chunk time (upstream profile, processed 40-159).

F14-H1 SUPPORTED (track / native <= 1.01): {'dog': True, 'bfly': True}

| workload | native (s) | wrap (s) | track (s) | track / native | track / wrap | wrap / native | tracking (ms / call) |
|---|---|---|---|---|---|---|---|
| dog | 0.5320 (n 5) | 0.5319 | 0.5325 | 1.0009 | 1.0011 | 0.9998 | 0.39 |
| bfly | 0.5329 (n 5) | 0.5326 | 0.5332 | 1.0006 | 1.0011 | 0.9994 | 0.40 |

**Three configurations, each against its own host's native (same session; tracking-only does not stand for OTTER's whole cost):**

| workload | tracking-only A / native A | OTTER integrated B / native B | harness without OTTER A / native A | integrated B per call (s): generation + tracking (ms) | valid integrated runs |
|---|---|---|---|---|---|
| dog | 1.0009 | 1.0555 | 1.0457 | 0.5567 = 0.5561 + 0.57 | 5 / 5 |
| bfly | 1.0006 | 1.0528 | 1.0472 | 0.5558 = 0.5552 + 0.58 | 5 / 5 |

14a phases (existing runs, descriptive): source during transfer / its reference 1.019 (n 10); owner during staging / outside 1.013 (n 6).

## 14b memory (measured, node --mem_log)

| run | node | RSS first / peak (MB) | GPU alloc / reserved peak (MB) | retained peak (MB) | staged peak (MB) |
|---|---|---|---|---|---|
| single|dog rep 1 | A | 27293.8 / 32439.6 | 26637.0 / 29824.0 | 1645.3 | 0.0 |
| single|dog rep 1 | B | 27324.9 / 29049.1 | 29698.1 / 31422.0 | 0.0 | 0.0 |
| single|dog rep 1 | cluster | Sink 1645.3 MB; log 30.5 MB; switch 3.1 MB | | held end 1645.3 | held peak 1645.3 |
| single|dog rep 2 | A | 25656.0 / 30824.7 | 26710.4 / 29884.0 | 1645.3 | 0.0 |
| single|dog rep 2 | B | 27270.3 / 28994.5 | 29234.8 / 31422.0 | 0.0 | 0.0 |
| single|dog rep 2 | cluster | Sink 1645.3 MB; log 30.9 MB; switch 3.1 MB | | held end 1645.3 | held peak 1645.3 |
| single|dog rep 3 | A | 27221.8 / 32333.4 | 26557.2 / 29884.0 | 1645.3 | 0.0 |
| single|dog rep 3 | B | 27270.4 / 28965.2 | 28647.7 / 31422.0 | 0.0 | 0.0 |
| single|dog rep 3 | cluster | Sink 1645.3 MB; log 30.5 MB; switch 3.1 MB | | held end 1645.3 | held peak 1645.3 |
| single|bfly rep 1 | A | 27232.9 / 32478.5 | 26781.6 / 29884.0 | 1645.3 | 0.0 |
| single|bfly rep 1 | B | 25604.7 / 27507.4 | 28720.1 / 31422.0 | 0.0 | 0.0 |
| single|bfly rep 1 | cluster | Sink 1645.3 MB; log 497.8 MB; switch 3.1 MB | | held end 1645.3 | held peak 1645.3 |
| single|bfly rep 2 | A | 25726.0 / 30935.5 | 27959.1 / 29884.0 | 1645.3 | 0.0 |
| single|bfly rep 2 | B | 27279.6 / 29295.7 | 28796.1 / 31582.0 | 0.0 | 0.0 |
| single|bfly rep 2 | cluster | Sink 1645.3 MB; log 544.2 MB; switch 3.1 MB | | held end 1645.3 | held peak 1645.3 |
| single|bfly rep 3 | A | 27253.1 / 32562.7 | 26557.2 / 29884.0 | 1645.3 | 0.0 |
| single|bfly rep 3 | B | 27279.7 / 29153.9 | 28173.4 / 31422.0 | 0.0 | 0.0 |
| single|bfly rep 3 | cluster | Sink 1645.3 MB; log 488.3 MB; switch 3.1 MB | | held end 1645.3 | held peak 1645.3 |
| chain|dog rep 1 | A | 15051.8 / 20555.0 | 27972.8 / 29684.0 | 1645.3 | 1645.3 |
| chain|dog rep 1 | B | 15077.9 / 20307.6 | 36608.2 / 37726.0 | 1645.3 | 1645.3 |
| chain|dog rep 1 | C | 15020.3 / 20159.9 | 34598.3 / 37584.0 | 1645.3 | 1645.3 |
| chain|dog rep 1 | D | 15079.8 / 16884.7 | 29381.8 / 31382.0 | 0.0 | 1645.3 |
| chain|dog rep 1 | cluster | Sink 1645.3 MB; log 57.9 MB; switch 9.2 MB | | held end 11517.1 | held peak 11517.1 |
| chain|dog rep 2 | A | 15024.7 / 20640.4 | 27097.0 / 29684.0 | 1645.3 | 1645.3 |
| chain|dog rep 2 | B | 15101.4 / 20319.0 | 34479.9 / 37606.0 | 1645.3 | 1645.3 |
| chain|dog rep 2 | C | 15010.6 / 20158.1 | 34455.8 / 37604.0 | 1645.3 | 1645.3 |
| chain|dog rep 2 | D | 14157.5 / 16005.7 | 28138.3 / 31382.0 | 0.0 | 1645.3 |
| chain|dog rep 2 | cluster | Sink 1645.3 MB; log 59.0 MB; switch 9.2 MB | | held end 11517.1 | held peak 11517.1 |
| chain|bfly rep 1 | A | 14466.7 / 19930.9 | 27243.2 / 29684.0 | 1645.3 | 1645.3 |
| chain|bfly rep 1 | B | 15087.1 / 20760.1 | 34747.1 / 37826.0 | 1645.3 | 1645.3 |
| chain|bfly rep 1 | C | 15022.5 / 20568.0 | 34547.5 / 37384.0 | 1645.3 | 1645.3 |
| chain|bfly rep 1 | D | 15020.7 / 17150.2 | 28172.4 / 31522.0 | 0.0 | 1645.3 |
| chain|bfly rep 1 | cluster | Sink 1645.3 MB; log 1188.3 MB; switch 9.2 MB | | held end 11517.1 | held peak 11517.1 |
| chain|bfly rep 2 | A | 15033.9 / 20782.2 | 26950.7 / 29684.0 | 1645.3 | 1645.3 |
| chain|bfly rep 2 | B | 14177.9 / 19966.5 | 34474.6 / 37706.0 | 1645.3 | 1645.3 |
| chain|bfly rep 2 | C | 15050.2 / 20533.6 | 34474.0 / 37764.0 | 1645.3 | 1645.3 |
| chain|bfly rep 2 | D | 14134.6 / 16217.9 | 28646.9 / 31522.0 | 0.0 | 1645.3 |
| chain|bfly rep 2 | cluster | Sink 1645.3 MB; log 1178.8 MB; switch 9.2 MB | | held end 11517.1 | held peak 11517.1 |
