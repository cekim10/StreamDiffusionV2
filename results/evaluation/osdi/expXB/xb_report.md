# Experiment XB - report (complete: main sweep, D5 lossy inputs, XB-N native-bandwidth sensitivity)

Frozen plan: `preregistration.md` (FROZEN 2026-10-23, `../expXB_freeze.md`). Aggregation: `tools/eval/aggregate_xb.py`
-> `xb_results.md` / `.json` (all numbers below come from it). 99 runs, **99 valid**: XB1 dog and butterfly (7 methods x 3
reps each), XB2 (3 x 3), XB3 and XB4 (5 x 3 each) and the rule-4 alternatives (3 x 3 per workload). Medians over 3 reps. Every external method is
a re-implementation "in the style of" its source system, inside OTTER's harness (same model, transport, caps, timing).

## 1. Verdicts so far (frozen rules)

| id | statement | verdict | evidence |
|---|---|---|---|
| XH1a | OTTER resumes locally much sooner than every exact method (TTFO-local <= 0.25 x), XB1 both workloads | **SUPPORTED** (6 / 6 comparisons) | OTTER 0.67 s; Full 54.05 s (ratio 0.012); P-full 214.2 / 219.5 s (0.003); R-full 36.7 / 36.8 s (0.018) |
| XH2 | full-state pre-copy does not converge at 1 Gbps | **SUPPORTED** (6 / 6 runs end by the no-shrink rule) | about 5.2 GiB of the 6.0 GiB state is rewritten between rounds |
| XH3 | recompute cost grows with session length | **SUPPORTED** | R-full destination replay time 35.0 s at trigger 30 vs 132.8 s at trigger 120 (x3.79; threshold 3) |
| XH4 | waiting methods accumulate remote serving under repeated mobility (remote-serving seconds of P-sink and R-full >= 5 x OTTER's TTFO-local, rho 1 and 2) | **SUPPORTED** (4 / 4) | rho 1: P-sink 44.8 s, R-full 71.7 s vs OTTER 0.83 s (x54, x86); rho 2: 30.2 s, 44.7 s vs 0.85 s (x36, x53) |
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

## 4. Repeated mobility (XB3 rho 1, XB4 rho 2; dog; A -> B -> C -> D)

| method | TTFO-local at D (s) rho 1 / 2 | delivery gap (s) | remote serving (chunks, wall s) | transmitted, measured (GB) | trajectory (terminal PSNR) |
|---|---|---|---|---|---|
| OTTER | 0.83 / 0.85 | 0.75 / 0.74 | 2 / 2 (in-flight chunks at moves) | 5.16 / 3.48 | 41.3 / 43.5 dB (rejoins after 32-33 calls) |
| Full | 53.4 / 53.6 | 81.6 / 67.7 | 0 | 8.19 / 6.47 | 99 |
| Wait-for-Sink | 14.9 / 14.9 | 43.1 / 29.0 | 0 | 5.18 / 3.47 | 47.2 / 47.2 dB |
| P-sink | 25.2 / 19.5 | 8.3 / 2.6 | 68 / 45, 44.8 / 30.2 s | 5.21 / 2.79 | 49.4 / 46.4 dB |
| R-full | 88.2 / 62.6 | 43.5 / 31.2 | 118 / 74, 71.7 / 44.7 s | 0.32 / 0.25 | 99 |

- Every move before the final one cancels the copy or replay in progress; the user never reaches B or C's resumption
  under any waiting method. The bytes of cancelled pre-copy rounds are counted (P-sink rho 1: two ~1.3 GB rounds to
  abandoned targets).
- Full and Wait-for-Sink stop the stream at every move, so their gaps grow with the number of moves (Full 54 s single
  move -> 68-82 s; Wait-for-Sink 15 s -> 29-43 s).
- **P-sink's gap depends on when the Sink's RoPE realignment falls (descriptive).** Its final stop-and-copy carries what
  changed during its last copy round. The streaming pipeline re-rotates the Sink's keys every ~45 calls (calls 48/49,
  93/94, ...; Task B). When that falls inside the last round (XB1: calls 30-58; XB3: 78-106) about 0.7 GB is dirty and
  the gap is ~8 s; when it does not (XB4: calls 54-82) the final copy is small (gap 2.6 s, TTFO-local 19.5 s).

## 5. D5 lossy-input sensitivity (descriptive; 8 runs, all valid; never exact recomputation)

| method | codec | inputs sent | TTFO-local | terminal PSNR (dog / butterfly) |
|---|---|---|---|---|
| R-full | FFV1 (frozen, lossless) | 60-80 MB | 36.7 s | 99 / 99 (bit-exact) |
| R-full | H.264 CRF 23 | 2.0-2.4 MB | 36.4-36.7 s | 37.5 / 27.7 |
| R-full | H.264 CRF 28 | 1.0-1.2 MB | 36.5 s | 32.8 / 27.5 |
| R-win | CRF 23 / 28 | 0.1-0.3 MB | 4.7 s | 21.7-23.1 |

Lossy inputs cut the transferred bytes by 30-60x but leave TTFO-local unchanged (input transfer is not R-full's
bottleneck at 1 Gbps) and break exactness: R-full's output then diverges from the reference (on butterfly to 27.5 dB,
below OTTER's 30.4 dB). Input PSNR 31.3-36.4 dB.

## 5b. XB-N: P-full without the emulated cap (descriptive sensitivity, 3 runs; `../expXBN/plan.md`)

| quantity | 1 Gbps (frozen XB1) | native (XB-N) |
|---|---|---|
| measured end-to-end throughput per round | 0.84-0.88 Gb/s | **3.1-3.6 Gb/s** (hashing, packing and TCP included; the NIC's line rate was not reached) |
| rounds, dirty bytes | 3: 6164, 5224, 5208 MiB | 4: 6163, 5207, 4542, 4518 MiB |
| convergence | no (no-shrink rule) | **no (no-shrink rule)**; final stop-and-copy 4,562 MiB |
| total transmitted | 22.9 GB | 26.2 GB |
| TTFO-local / delivery gap | 214 s / 51 s | 66.6 s / 12.5 s |
| output after switchover | bit-exact | bit-exact (101 / 101) |

Reading: with 3.3 Gb/s of end-to-end bandwidth the rounds shorten from ~55 s to ~12 s, but the dirty set does not
shrink below ~4.5 GiB, because every generation call rewrites the recent KV ring slot and the VAE caches. The state
mutates about 4.5 GiB per call interval (~0.56 s); converging to a small final copy would need that much copied
within one call interval, about 64 Gb/s end to end, which this harness did not have. Stated as arithmetic on the
measured dirty set, not as a general claim that pre-copy cannot converge.

## 6. Scope of the comparison

The external methods are re-implementations of the **migration mechanisms** described by Llumnix (multi-stage
pre-copy relying on an append-only KV cache, with a final short stop-and-copy) and ServerlessLLM (token-based
migration with destination recomputation in rounds while the source serves). They are not the original systems: their
scheduling, checkpoint loading and LLM-specific paths are not compared. Two of their assumptions do not hold for this
model, and the adaptations are disclosed:
- the state is not append-only, so pre-copy tracks content-hash changes per fragment;
- recomputation is sequential, so replay runs at generation speed rather than an order of magnitude faster.
All results are for 1 Gbps emulated caps, a sub-millisecond LAN, one model, seed 0, and the tested inputs (dog, and
butterfly-feeding-slow-motion in XB1).
