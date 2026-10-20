# Challenge 3 (paper Background) - number check against frozen Experiment N (2026-10-20)

Exploratory, post-hoc analysis of the frozen N runs (`expN_cell{1,7,8,9,10}/`, 3 reps per policy); nothing re-run,
no verdict changed. Script: `tools/eval/check_challenge3.py`. "Fixed" = OTTER at moves (`reuse_aware_in`); "re-planning"
= frozen M3-v1 (`reuse_dyn`).

## 1. Latency basis (the draft mixed two)

| quantity | Sink received (last fragment) | continuity-ready (frozen N report "bind") |
|---|---|---|
| cell 7 fixed (incorrect placement, no change) | 14.17 s | 15.01 s |
| cell 9 fixed (holder B egress 1 Gbps -> 62.5 Mbps at half restoration) | 112.18 s (7.9 x) | 113.40 s (7.6 x) |
| cell 10 fixed vs re-planning (destination ingress -> 62.5 Mbps) | 116.62 vs 112.91 s: 3.7 s | 117.75 vs 113.89 s: 3.9 s |
| cell 8 re-planning vs fixed (source egress -> 62.5 Mbps) | 17.24 vs 14.17 s: +3.1 s | 18.56 vs 15.01 s: +3.5 s |

The draft's 14.2 / 112.2 / 7.9x / 3.7 s are "Sink received"; its 3.5 s is continuity-ready. One basis per paragraph.

## 2. Cell 10 re-planning (median run = rep 1)

- re-plans per run 29 / 28 / 32; predicted saving per re-plan 4-102 s in rep 1 (4-116 s across runs); predicted savings
  sum to 776-817 s per run; realized gain 3.7 s (received) / 3.9 s (continuity-ready); source bytes 1.224-1.233 Sinks.
- exactly one re-plan per run before the degradation, at +2.28-2.30 s after the move (degradation at +7.24-7.26 s);
  cells 8 and 9 show the same +2.28-2.29 s re-plan; cell 7 (no change) its only re-plan.

## 3. The "throughput dip" hypothesis (post-change re-plans, 86 in 3 runs)

- Per-provider 2 s samples only take the values 16.8 / 33.6 Mbps (one / two 4 MiB fragments); total verified ingress in
  the 2 s before a re-plan is 33.6-67.1 Mbps (median 50-67) around the 62.5 Mbps cap: the destination link does not dip;
  one provider's fragment-quantized share does.
- In 52 / 86 re-plans (60 %) the provider being drained had a 2 s rate >= 1.5x below its own 10 s mean. There the
  current plan's estimated completion time was a median 1.98x the time actually remaining; in the other 34, 1.26x.
- The estimates are biased, not merely noisy: current-plan ETA median 1.91-1.95x the actual remaining time (range
  1.15-3.52x); alternative-plan ETA 1.30-1.37x (range 0.96-2.52x).
