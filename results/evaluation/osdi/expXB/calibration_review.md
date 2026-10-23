# XB calibration review (2026-10-22; before the freeze)

Source: `calibration_grid.md`, `calibration_selection.json` (35 runs on GPU 0 of A and B, commit 89d2041; all valid, all
pass their class check, all selected-setting jitter <= 2.2 %, so rule 5 does not trigger). Calibration runs are not
evidence for XH1-XH5. Nothing in this note changes a selection rule; it lists what the reviewer must decide before the
freeze.

## 1. What the grid shows (descriptive)

| method | selected (rules as written) | TTFO-local | delivery gap | behavior across the grid |
|---|---|---|---|---|
| P-full | thr=256:rl=10 | 213.5-214.1 s | 50.8-50.9 s | **identical in all 9 settings**: 3 rounds, dirty [6164, 5224, 5208] MiB, then the no-shrink rule or round limit 3; final stop-and-copy ~5.1 GiB. TTFO-local 213.5-216.7 s across settings (noise) |
| P-sink | thr=16:rl=3 | 28.5-29.5 s | 2.2 s | dirty [1645, 689, 24] MiB in every setting (round 2 is ~0.4 Sink: refresh and realignment during round 1); rl 3 switches after round 3, rl >= 6 adds a round 4 with 0 MiB. TTFO-local 28.5-31.3 s |
| R-full | lag=1:rl=3 | 69.2-70.8 s | 17.2-17.8 s | replay runs at generation speed, so the lag never closes; **every run ends by the round limit**, and TTFO-local grows with it (rl 3: ~70 s, 6: ~120 s, 10: ~176 s). The lag threshold has no effect |
| R-win | W=6 (rule 3: only W=6 is within 1.0 dB of the best terminal PSNR) | 4.8 s | 4.1 s | W=1 / 3 / 6: TTFO-local 2.65 / 3.15 / 4.81 s, terminal PSNR 21.1 / 21.9 / 23.3 dB; no W reaches 35 dB |

Exactness: P-full and R-full outputs are bit-identical to the reference after the switchover in every run (101 / 101
calls), and the gate (4 runs) verified all five state components. P-sink is never output-equivalent (0 / 101) but
reaches 35 dB after 8-9 calls (terminal 48.5-49.1 dB). Measured LAN RTT 0.17-0.33 ms.

## 2. Decisions needed before the freeze

**D-cal-1 (grid edge; recommended: extend).** For R-full and P-sink the best TTFO-local lies at the grid's lower edge
(round limit 3), and the trend says a smaller limit would be faster still: R-full with one round would replay to the
current call (~17 s) and then catch up after stopping the source; P-sink with one or two rounds would skip the later
rounds at the cost of a larger final copy (round 2 is 689 MiB, about 6 s at 1 Gbps). The plan's purpose is a
baseline-favorable setting, and XH1a compares OTTER with R-full; a reviewer can object that R-full's best setting was
outside the grid. Proposal: add round limit {1, 2} for R-full (lag is irrelevant; 2 runs) and P-sink (threshold is
irrelevant at rl 1, and at rl 2 with thr 16; 2 runs), apply the unchanged selection rules to the extended grid, and
repeat a newly selected setting twice (rule 5). At most 8 runs, about 1 h with two node starts. Disclosed in the frozen
document as a pre-freeze grid extension made because the optimum was at the edge.

**D-cal-2 (tie-break tolerance; recommended: keep the rules as written).** The selections for P-full (thr=256:rl=10)
and P-sink (thr=16:rl=3) came from secondary tie-breaks decided by noise (delivery gaps differing by 0.01-0.03 s). The
tolerance proposal of draft 5 was not adopted before the calibration, so adopting it now would change a rule after
seeing the results. Recommendation: keep the written rules. For P-full this choice has no consequence, because all nine
settings behave identically (same rounds, bytes and switch point).

**D-cal-3 (rule-4 alternative runs).** Rule 4 adds XB1 runs where the minimum-gap setting differs from the selected one:
- P-sink: thr=256:rl=6 behaves identically to the selected setting apart from one empty round, so these runs would
  measure noise.
- R-full: lag=2:rl=10 is a real alternative (gap 15.7 s vs 17.3 s, TTFO-local 175 s vs 69 s).
- R-win: W=1 is a real alternative (gap 2.0 s, TTFO-local 2.65 s, terminal 21.1 dB).
- Recommendation: keep the R-full and R-win alternatives (12 runs). Drop the P-sink alternative (6 runs) as
  behaviorally identical, and disclose that. Re-evaluate after D-cal-1, which may change the selections.

**D-cal-4 (exactness classification).** The gate and every calibration run satisfy section 3.1 and 3.3 for P-full and
R-full. Recommendation: classify both as exact in the frozen document.

## 3. Observations to carry into the report (not hypotheses)

- Full-state pre-copy does not converge at 1 Gbps: about 85 % of the state (recent KV, VAE caches) is rewritten
  between rounds. This is XH2's prediction, now seen in calibration only.
- Recompute gains nothing from rounds when replay runs at generation speed. R-full's TTFO-local is set by when the
  source is stopped.
- P-sink resumes in ~29 s with a ~2 s gap and rejoins the reference after ~9 calls, consistent with RD's d = 0 (an
  immediate Sink bind after an M1 reset).
