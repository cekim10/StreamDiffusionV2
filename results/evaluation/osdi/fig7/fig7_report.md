# Fig. 7 report: single-migration performance (M1)

Preregistration: `preregistration.md`, FROZEN 00f2dd92 (before any Fig. 7 run). Runs: `results/evaluation/expF7_dog`,
`expF7_bfly` (40 runs, one commit, A -> B at call 30, 1 Gbps). Numbers: `fig7_results.{json,md}` (`tools/eval/fig7_report.py`).
Figures: `figures/fig7{a_ttfo,b_gap,c_bytes}.{pdf,png}` (`tools/eval/plot_fig7_migration.py`).

## 1. Verdict (frozen rules, medians, both workloads)

**F7-H1 and F7-H2 both SUPPORTED.** 40 / 40 runs valid, 0 failed, every cell 5 / 5, C1 passed in every run.

| workload | H1: gap OTTER / best baseline (<= 0.25) | H2: TTFO-local OTTER / best baseline (< 1) |
|---|---|---|
| Low-refresh (dog) | 1.63 / 18.47 s (R-full) = **0.088** | 23.28 / 36.94 s (R-full) = **0.630** |
| High-refresh (butterfly) | 1.59 / 18.33 s (R-full) = **0.087** | 24.62 / 36.78 s (R-full) = **0.670** |

Conclusion (section 8 table): OTTER's single migration stalls far less and reaches local service sooner than every
full-state baseline. The state claims differ, so the comparison is whole-state exact (baselines) against Sink-exact
plus replay (OTTER), not equal correctness (section 11).

## 2. Results (median [IQR], 5 reps)

| workload | method | TTFO-local (s) | delivery gap (s) | bytes (GB) | remote serving (s) | C1 |
|---|---|---|---|---|---|---|
| dog | Full | 54.24 [54.18-54.25] | 54.24 [54.18-54.25] | 6.463 | 0 | whole state exact 5/5 |
| dog | Llumnix-style P-full | 213.85 [213.57-213.86] | 50.92 [50.75-50.99] | 22.854 | 162.9 | whole state exact 5/5 |
| dog | ServerlessLLM-style R-full | 36.94 [36.79-36.94] | 18.47 [18.42-18.51] | 0.084 | 18.4 | whole state exact 5/5 |
| dog | OTTER | 23.28 [23.12-23.53] | 1.63 [1.60-1.66] | 1.763 | 21.6 | Sink exact 5/5 (SINKOK, 0/360) |
| bfly | Full | 54.22 [54.05-54.23] | 54.22 [54.05-54.23] | 6.463 | 0 | whole state exact 5/5 |
| bfly | Llumnix-style P-full | 219.21 [219.16-219.35] | 52.57 [52.51-52.58] | 23.555 | 166.6 | whole state exact 5/5 |
| bfly | ServerlessLLM-style R-full | 36.78 [36.70-36.79] | 18.33 [18.30-18.36] | 0.064 | 18.4 | whole state exact 5/5 |
| bfly | OTTER | 24.62 [24.45-25.78] | 1.59 [1.57-1.73] | 2.243 [2.243-2.282] | 23.1 | Sink exact 5/5 (SINKOK, 0/360) |

**Bytes (F7-D, descriptive).** OTTER / Full 0.273 dog, 0.347 bfly; OTTER / P-full 0.077, 0.095; OTTER / R-full
**21.0, 35.3** (R-full sends only the FFV1 input history, 84 / 64 MB, and pays in recomputation time instead). OTTER's
bytes = Sink base 1.728 GB + log (dog 32 MB, patches 19 MB; bfly 512-551 MB, patches 498-537 MB) + switch 3.2 MB. NIC
receive bytes / accounted bytes after the header factor: 0.9998-1.0005 in every run with a NIC record (Full has none).

**OTTER C2 output fidelity** (PSNR at B against the uninterrupted reference; descriptive, section 6). 0 bit-exact
calls of 101 in every OTTER run; every baseline run is bit-exact on every scored call (99 dB).

| workload | first call (dB) | min over 24 (dB) | median over 24 (dB) | terminal median (dB) |
|---|---|---|---|---|
| dog | 29.3 [29.3-29.3] | 27.5 [26.9-27.5] | 41.0 [41.0-41.0] | 48.8 [48.6-48.8] |
| bfly | 35.9 [33.8-35.9] | 25.5 [25.5-26.3] | 41.6 [35.9-41.6] | 44.4 [32.4-44.4] |

## 3. Observations the frozen text did not anticipate

1. **OTTER's largest gap is not always the cutover.** In all 10 OTTER runs the source's first call after the trigger
   (call 30 -> 31) takes 1.56-1.65 s instead of ~0.61 s. It holds the round-1 Sink snapshot (`snapshot_s` 0.67-0.69 s)
   plus ~0.3 s more. The maximum gap is this source stall in 6 runs (dog reps 2-5, bfly reps 2, 4, 5 at t = 0.65 s) and the
   cutover in 4 runs (dog rep 1, bfly reps 1, 3); the two are within 0.1-0.2 s of each other. Cutover interruption
   medians: 1.57 s dog, 1.51 s bfly. The metric is as defined (largest interval after the trigger, section 4), so the
   medians stand; reducing the stall would need both the snapshot stall and the cutover to shrink. P-full has the same
   kind of start stall (1.6-1.7 s) and later snapshot stalls (2.3-2.5 s), all well below its stop-and-copy gap.
2. **The switch call varies by one or two calls, and fidelity follows it.** Logged calls at the switch: dog 32 (3
   reps) or 33 (2 reps); bfly 34 (3) or 36 (2). Runs with the same switch call have identical bytes and identical
   PSNR series. In bfly the 36-call switch (reps 1, 3) gives terminal median 32.4 dB against 44.4 dB for the 34-call
   switch. 32.4 dB is lower than the M1 E6 butterfly record (42.0 dB). The prereg defines no threshold for "severely
   degraded"; this report does not judge it, and Fig. 13 (quality) must cover the switch-call dependence.
3. **P-full never converges** (no-shrink in all 10 runs: 3 rounds + final copy, bfly rep 4: 4 rounds). Per section 5
   this is a completed migration with a long stop-and-copy, not a failure.

## 4. Figure

- 7a TTFO-local: medians span 9.4x (< one decade) -> **linear** axis by the frozen rule (no broken axis).
- 7b maximum output gap ("Max. output gap (s)" = the delivery gap metric): span 34x -> **log**. Both versions kept:
  `fig7b_gap_log`, `fig7b_gap_linear`.
- 7c transferred data ("Transferred data (GB)" = measured harness bytes): span 370x -> **log**.
- Tick labels abbreviate Llumnix-style and ServerlessLLM-style as "Llumnix" and "SLLM" (named in the caption).
- Style (user, 2026-10-30): the EC-LLM evaluation figures (`fig_e3_tiered_layout_a_concentration.pdf`): 7.70 x 4.80 in
  canvas, axes box [0.19, 0.20, 0.78, 0.73], 28 pt Times axis text, 19 pt italic values, 25 pt legend; OTTER in the
  accent blue, baselines in grays. Presentation only; data, rules and scale choices unchanged.

**Claim wording.** OTTER reduces the longest output interruption by 11.3-11.5x compared with the strongest migration
baseline (R-full: 18.47 / 1.63 s dog, 18.33 / 1.59 s butterfly) and starts local service 1.5-1.6x sooner (36.9 / 23.3 s,
36.8 / 24.6 s). Not "seamless" or "imperceptible": 1.6 s is a visible interruption. OTTER does not minimize traffic
(21-35x R-full's bytes); it combines Sink transfer with replay to shorten the interruption. P-full's 22.9-23.6 GB is
iterative pre-copy that never converges (no-shrink: after the first 6.46 GB round, every round finds 4.5-5.7 GB
of the state dirty again, since recent KV and VAE caches are rewritten every call; measured dirty rounds in section 2). The source keeps serving for 21.6 / 23.1 s (median remote serving) before B serves; WAN latency during
that period is not charged here.

**Caption.**
```latex
\caption{
\textbf{Single-migration performance at 1~Gbps.}
(a) Time to first locally generated output,
(b) maximum output delivery gap, and
(c) transferred data.
Bars show medians over five runs, with IQR whiskers and individual measurements.
Llumnix and SLLM denote Llumnix-style pre-copy and ServerlessLLM-style recomputation baselines.
All baselines restore the complete state exactly, whereas \sys verifies the Sink and reconstructs recent state by replay.
For low-/high-refresh inputs, \sys achieves 29.3/35.9~dB PSNR on the first output and 48.8/44.4~dB terminal PSNR against uninterrupted generation.
}
```
The text must give the butterfly terminal-PSNR distribution (2 / 5 runs at 32.4 dB, switch two calls later) next to
the 44.4 dB median (section 3, item 2).
