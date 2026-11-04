# Fig. 14 results

Rules: `preregistration.md`. 14a native: medians over reps of each run's median per-chunk time (upstream profile, processed 40-159).

F14-H1 NOT SUPPORTED (track / native <= 1.01): {'dog': False, 'bfly': False}

| workload | native (s) | wrap (s) | track (s) | track / native | track / wrap | wrap / native | tracking (ms / call) |
|---|---|---|---|---|---|---|---|
| dog | - (n 0) | - | 0.5312 | - | - | - | 0.40 |
| bfly | - (n 0) | - | - | - | - | - | - |

**Three configurations, each against its own host's native (same session; tracking-only does not stand for OTTER's whole cost):**

| workload | tracking-only A / native A | OTTER integrated B / native B | harness without OTTER A / native A | integrated B per call (s): generation + tracking (ms) | valid integrated runs |
|---|---|---|---|---|---|
| dog | - | - | - | - = - + - | 0 / 0 |
| bfly | - | - | - | - = - + - | 0 / 0 |

14a phases (existing runs, descriptive): source during transfer / its reference 1.019 (n 10); owner during staging / outside 1.013 (n 6).

## 14b memory (measured, node --mem_log)

| run | node | RSS first / peak (MB) | GPU alloc / reserved peak (MB) | retained peak (MB) | staged peak (MB) |
|---|---|---|---|---|---|
| single|dog rep 1 | A | 27293.8 / 32439.6 | 26637.0 / 29824.0 | 1645.3 | 0.0 |
| single|dog rep 1 | B | 27324.9 / 29049.1 | 29698.1 / 31422.0 | 0.0 | 0.0 |
| single|dog rep 1 | cluster | Sink 1645.3 MB; log 30.5 MB; switch 3.1 MB | | held end 1645.3 | held peak 1645.3 |
