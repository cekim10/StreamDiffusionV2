# Experiment XB - report (INTERIM: XB1, XB2 and the rule-4 alternatives; XB3 / XB4 pending)

Frozen plan: `preregistration.md` (FROZEN 2026-10-23, `../expXB_freeze.md`). Aggregation: `tools/eval/aggregate_xb.py`
-> `xb_results.md` / `.json` (all numbers below come from it). 69 runs, **69 valid**: XB1 dog and butterfly (7 methods x 3
reps each), XB2 (3 x 3) and the rule-4 alternatives (3 x 3 per workload). Medians over 3 reps. Every external method is
a re-implementation "in the style of" its source system, inside OTTER's harness (same model, transport, caps, timing).

## 1. Verdicts so far (frozen rules)

| id | statement | verdict | evidence |
|---|---|---|---|
| XH1a | OTTER resumes locally much sooner than every exact method (TTFO-local <= 0.25 x), XB1 both workloads | **SUPPORTED** (6 / 6 comparisons) | OTTER 0.67 s; Full 54.05 s (ratio 0.012); P-full 214.2 / 219.5 s (0.003); R-full 36.7 / 36.8 s (0.018) |
| XH2 | full-state pre-copy does not converge at 1 Gbps | **SUPPORTED** (6 / 6 runs end by the no-shrink rule) | about 5.2 GiB of the 6.0 GiB state is rewritten between rounds |
| XH3 | recompute cost grows with session length | **SUPPORTED** | R-full destination replay time 35.0 s at trigger 30 vs 132.8 s at trigger 120 (x3.79; threshold 3) |
| XH4 | waiting methods accumulate remote serving under repeated mobility | **pending** (XB3 / XB4 main sweep) | - |
| XH1b, XH5 | descriptive | below | - |

## 2. XB1: the four outcome notions, per method (dog / butterfly)

| method | class | TTFO-local (s) | delivery gap (s) | remote serving (chunks, wall s) | transmitted, measured (GB) | remote delivery, estimated, CRF 23 (MB) | restoration | trajectory (terminal PSNR; first call >= 35 dB) |
|---|---|---|---|---|---|---|---|---|
| OTTER (M1 + M2 + M3-v2) | system | 0.67 / 0.67 | 0.69 / 0.70 | 0 | 1.73 | 0 | Sink exact after bind | 44.2 dB, call +31 / **30.4 dB, never** |
| Full migration | exact | 54.05 / 54.05 | 54.05 / 54.05 | 0 | 6.46 | 0 | whole state exact | 99 (bit-exact) |
| P-full (Llumnix-style) | exact | 214.2 / 219.5 | 50.7 / 52.4 | 247-252, 163-167 s | 22.9 / 23.6 | 11.9 / 10.5 | whole state exact (101 / 101 calls) | 99 |
| R-full (ServerlessLLM-style) | exact | 36.7 / 36.8 | 18.3 / 18.3 | 30, 18 s | 0.08 / 0.06 (FFV1 inputs) | 1.4 / 1.2 | whole state exact (101 / 101) | 99 |
| P-sink (M1-based hybrid) | hybrid | 25.1 / 26.5 | 8.1 / 9.6 | 26, 17 s | 2.45 / 2.62 | 1.2 / 1.1 | Sink exact, recent / VAE rebuilt | 49.4 dB, +8 / 34.0 dB, +10 |
| Wait-for-Sink (ablation) | hybrid | 15.0 / 15.0 | 15.0 / 15.0 | 0 | 1.73 | 0 | Sink exact, recent / VAE rebuilt | 47.3 dB, +8 / 36.2 dB, +8 |
| R-win (W = 6) | approximate | 5.5 / 4.8 | 4.2 / 4.2 | 1-2 | 0.01 | 0.1 | not exact | 21.6 / 22.2 dB, never |

Rule-4 alternatives (minimum-gap settings): P-sink thr=256:rl=6 (TTFO-local 29.2 / 35.3 s, gap 2.4 / 2.5 s), R-full
lag=2:rl=10 (173.4 / 168.4 s, gap 15.1 / 14.4 s), R-win W=1 (2.6 s, gap 1.9 s, terminal 21.1 / 21.9 dB).

Measured LAN RTT between the hosts is sub-millisecond; WAN / radio latency is not emulated or measured, so remote serving
here is a best case for the methods that serve remotely.

## 3. Reading (descriptive, XH1b and XH5)

- **Fast local resumption:** only OTTER resumes at the user's edge in under 1 s. The next fastest is approximate (R-win,
  4.8-5.5 s, never rejoins the reference). The fastest exact method is R-full (36.7 s), helped by input transfer of
  only ~0.07 GB.
- **Uninterrupted delivery:** P-sink's smallest gap is 2.4 s (alternative setting), at the cost of 29-35 s of remote
  serving before local resumption. The exact methods have gaps of 18-54 s. OTTER's gap is 0.7 s.
- **Restoration correctness:** P-full, R-full and Full restore the whole state exactly. OTTER and the hybrids restore
  the Sink exactly and rebuild the recent KV and VAE caches.
- **Trajectory (XH5):** OTTER pays for its early resumption. Before the bind its output is far from the reference
  (median 16.6 dB dog, 18.4 dB butterfly). On dog it rejoins 31 calls after the move and ends at 44.2 dB. On butterfly
  it never reaches 35 dB (30.4 dB). The Sink-exact hybrids that start from an immediate bind do better on butterfly
  (Wait-for-Sink 36.2 dB, P-sink 34.0 dB). This is the cost VC / VD examine.
- **Network cost:** pre-copy moves 3.5x the state (22.9-23.6 GB vs Full's 6.46 GB) while the source keeps serving;
  remote delivery of the output, estimated at CRF 23, is small next to state transfer (at most ~12 MB).

## 4. Pending

XB3 / XB4 main sweep (30 runs; XH4), then the D5 lossy-input runs (8, descriptive), then the final report.
