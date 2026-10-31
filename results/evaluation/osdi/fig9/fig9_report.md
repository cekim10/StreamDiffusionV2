# Fig. 9 report: M1 design breakdown

Preregistration FROZEN d79f4606 (decisions D1-D6). Runs: 30 new (2d41a96e, run commit d79f4606 on A and B):
Wait-for-Sink, P-sink (`thr=256:rl=10`), OTTER w/o Sink sync, 5 reps x 2 workloads; OTTER and P-full = the Fig. 7 runs
(00f2dd92). Numbers: `fig9_results.{json,md}` (`tools/eval/fig9_report.py`); figures: `figures/` (`tools/eval/plot_fig9.py`);
descriptive early-PSNR analysis: `early_psnr.json` (`tools/eval/fig9_early_psnr.py`, not preregistered).

Figures used in the paper (user, 2026-10-31): **(a) dog only** (`fig9a_dog`) and **(b)** (`fig9b_gap`); `fig9a_bfly` and
`fig9c_psnr` are kept for the appendix / record. All panels on Fig. 6a's canvas (5.83 x 4.78 in, axes box left 0.18,
right 0.97, bottom 0.22, top 0.97, no tight bbox). Panel (a) is drawn in MB (power-of-ten labels) instead of GB so the
tick labels fit that canvas; the data are the same.

## 1. Verdicts (frozen rules)

| hypothesis | Low-refresh (dog) | High-refresh (butterfly) | verdict |
|---|---|---|---|
| F9-H1: P-sink stops by the threshold in >= 4 / 5 runs | 5 / 5 | 5 / 5 | **SUPPORTED** |
| F9-H2: median gap OTTER < each other step | 1.63 < 2.23, 8.83, 15.02 | 1.59 < 2.52, 10.40, 15.02 | **SUPPORTED** |
| F9-H3: median PSNR of B's first 24 calls, OTTER >= P-sink and >= Wait-for-Sink | 41.0 vs 40.6 (yes), 42.6 (**no**) | 41.6 vs 41.5 (yes), 34.5 (yes) | **NOT SUPPORTED** |

Validity: 30 / 30 new runs valid with every C1 check passing (Wait-for-Sink: Sink digest equal at bind, no generation
before the bind; P-sink: switchover and Sink verified; OTTER w/o Sink sync: base, replay order, resent Sink verified);
Fig. 7 OTTER and P-full 10 / 10 each (unchanged).

## 2. Panel (a): dirty state per pre-copy round [V] measured

| | dog rounds (GB) -> stop-and-copy | butterfly rounds (GB) -> stop-and-copy | stop reason |
|---|---|---|---|
| P-full (5 / 5 identical except bfly rep 4) | 6.46 -> 5.48 -> 5.46 -> **5.45** | 6.46 -> 5.73 -> 5.69 -> **5.67** (rep 4: 6.46 -> 5.73 -> 4.57 -> 4.55 -> 4.53) | no_shrink |
| P-sink (5 / 5 identical) | 1.73 -> 0.72 -> 0.025 -> **0.003** | 1.73 -> 0.90 -> 0.28 -> 0.088 -> **0.028** (0.024 in rep 3) | threshold |

- Whole-state pre-copy stops shrinking after round 2 at 85-88 % of the state (70 % in one butterfly run) and ends with a
  4.5-5.7 GB stop-and-copy (gap 50.9 / 52.6 s).
- Sink-only pre-copy converges: 3 rounds (dog) / 4 rounds (butterfly, the high-refresh workload needs one more) to a
  3 / 28 MB stop-and-copy.
- Converging Sink pre-copy does not complete a migration: P-sink sends no recent state (B starts it from zero), which (c)
  and section 4 show at the switch.

## 3. Panel (b): maximum output gap [V] measured

| step | dog gap (s) | bfly gap (s) | dog TTFO-local (s) | bfly TTFO-local (s) | dog bytes (GB) | bfly bytes (GB) | total stall dog / bfly (s) |
|---|---|---|---|---|---|---|---|
| Wait-for-Sink | 15.02 [15.01-15.03] | 15.02 [15.01-15.03] | **15.0** | **15.0** | 1.73 | 1.73 | 14.43 / 14.42 |
| P-sink | 2.23 [2.22-2.30] | 2.52 [2.44-2.54] | 28.7 | 35.3 | 2.48 | 3.02 | 4.77 / 6.05 |
| OTTER w/o Sink sync | 8.83 [8.72-8.87] | 10.40 [10.38-10.40] | 30.3 | 32.1 | 2.47 | 2.68 | 9.22 / 10.76 |
| **OTTER** | **1.63** [1.60-1.66] | **1.59** [1.57-1.73] | 23.3 | 24.6 | 1.76 | 2.24 | **1.99 / 1.87** |

- **Sink synchronization** is the largest single difference among the OTTER steps: without it the switch resends the
  dirty Sink (730 MB dog / 936 MB bfly; stop -> sent 7.35 / 8.93 s) and the gap is 8.83 / 10.40 s; with it the switch
  sends 3.2 MB (stop -> sent 1.37 / 1.24 s) and the gap is 1.63 / 1.59 s.
- **Overlap with generation**: Wait-for-Sink stalls for the whole Sink transfer (15.0 s, all at the switch); P-sink
  overlaps it with A's service (gap 2.23 / 2.52 s) at the cost of later local service (28.7 / 35.3 s) and more bytes.
- **TTFO-local**: Wait-for-Sink reaches local service first (15.0 s vs OTTER 23.3 / 24.6 s), as predicted; it does so
  by stopping the stream for 15 s.
- P-sink's gap is all at the switch (cutover 2.23 s with a 3 MB stop-and-copy in dog); the split of that time (B's
  restore, first call from a zero recent state) is not decomposed here.

## 4. Panel (c): PSNR of B's first 24 calls; why F9-H3 fails (descriptive, not preregistered)

| step | first B call dog / bfly | dog: calls 1-8 / 9-24 (median dB) | bfly: calls 1-8 / 9-24 (median dB) | first call dog / bfly (dB) |
|---|---|---|---|---|
| Wait-for-Sink | 30 / 30 | 22.9 / 45.5 | 23.5 / 35.3 | 19.3 / 14.1 |
| P-sink | 68 / 76-77 | 22.8 / 46.2 | 23.4 / 41.8 | 19.2 / 14.8 |
| OTTER w/o Sink sync | 62-64 / 63-64 | 30.2 / 44.2 | 31.4 / 44.4 | 29.3 / 32.8 |
| OTTER | 63-64 / 65-67 | 30.5 / 44.2 | 30.6 / 41.3 | 29.3 / 35.9 |

- **Where replay helps**: in B's first 8 calls the steps with replayed recent state are 7-8 dB higher than the steps
  that start it from zero (first call 29-36 dB vs 14-19 dB); by call ~8 the zero-start steps catch up.
- **Why the frozen metric does not show it**: the median over 24 calls is dominated by calls 9-24, where the
  zero-start steps are equal or higher (dog 45.5 / 46.2 vs 44.2 dB).
- **Confound**: B starts at different calls (Wait-for-Sink at 30, OTTER at 63-67, P-sink at 68-77), so "B's first 24
  calls" are different segments of the video, and PSNR against the reference depends on the segment. The calls-9-24
  differences cannot be attributed to the method from these runs.
- Butterfly OTTER's low quartile (35.9) is the two Fig. 7 runs whose Sink schedule diverged after the cutover
  (`osdi/fig7/bfly_fidelity_analysis.md`).
- F9-H3 stays NOT SUPPORTED. For Fig. 13: compare at a fixed switch call or per call relative to the switch and at the
  same absolute calls, and report the early window (calls 1-8) separately from the rest.

## 5. OTTER cost breakdown (D6: table in the text; medians) [V] measured

| | OTTER dog | OTTER bfly | w/o Sink sync dog | w/o Sink sync bfly |
|---|---|---|---|---|
| calls replayed / time per call / total | 32 / 0.120 s / 3.89 s | 34 / 0.121 s / 4.33 s | 32 / 0.121 s / 3.89 s | 32 / 0.120 s / 3.88 s |
| Sink base (MB) | 1,728 | 1,728 | 1,728 | 1,728 |
| input log incl. patches (MB) / patches | 32.0 / 2 (19.2 MB) | 512.0 / 52 (498.4 MB) | 12.8 / 0 | 12.8 / 0 |
| sent at the switch (MB) | 3.2 | 3.2 | 730.2 | 935.7 |
| wait for replay to catch up (s) | 4.08 | 4.65 | 4.07 | 4.06 |
| stop -> switch sent (s) | 1.37 | 1.24 | 7.35 | 8.93 |
| Sink digest source / destination (s) | 0.064 / 0.064 | 0.064 / 0.064 | - | - |
| verdict wait (s) / fallback | 0.13 / none | 0.08 / none | - | - |
| B restore / DR-2 (s) | 0.68 / 0.52 | 0.63 / 0.52 | 0.65 / 0.52 | 0.66 / 0.52 |

Replay runs at ~0.12 s per call, 4.6x faster than generation (0.556 s), so it catches up while A keeps serving. On the
high-refresh workload the Sink changes during the shadow window are carried as 52 patches (498 MB) inside the log
instead of a 936 MB resend at the switch.

## 6. Claim wording

Can claim (one migration, 1 Gbps, two workloads, 5 reps):
- "Whole-state pre-copy does not converge: after the first round 85-88 % of the state is dirty again every round, and
  the final stop-and-copy moves 4.5-5.7 GB. Pre-copying only the Sink converges in 3-4 rounds to 3-28 MB."
- "Sink synchronization cuts the switch from 730-936 MB to 3.2 MB and the maximum gap from 8.8-10.4 s to 1.6 s."
- "OTTER has the shortest maximum gap of all design points (1.6 s vs 2.2-2.5 s for Sink pre-copy without replay and
  15 s for waiting for the Sink)."
- "Replaying the recent state raises the first outputs after the switch by 7-8 dB (calls 1-8) over starting it from
  zero." (descriptive, not a preregistered test; different video segments)

Must not claim:
- That replay gives higher fidelity over the post-switch window (F9-H3 NOT SUPPORTED).
- That OTTER reaches local service first (Wait-for-Sink: 15.0 s vs 23.3-24.6 s).
- A strict one-component ablation; that P-sink / Wait-for-Sink are external systems; that the recent state is exact.
- E3 / E5 / E6 numbers as Fig. 9 results.
