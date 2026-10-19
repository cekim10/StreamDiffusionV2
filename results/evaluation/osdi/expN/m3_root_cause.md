# Why the frozen M3 rule re-plans without a network change and oscillates (analysis of the Experiment N traces, 2026-10-19)

Data only: the `replan` records of the N runs (`expN_cell*/policy=reuse_dyn*/summary.json` -> `d0.replans`, with
`measured_rate_mbps`, `cap_est_mbps`, `eta_cur_s`, `eta_new_s`, `margin_s`) and the frozen rule
`tools/eval/restore_planner.dyn_decide` (E-pilot v2; `dyn_window` 2 s, `dyn_period` 0.5 s, `dyn_warmup` 2 s, `dyn_eps` 2 s,
`dyn_rel` 0.10, `dyn_ctrl` 0.3 s). **No code is changed**; the frozen results stand (`../wrn_report.md`).

## The rule, as implemented

Every 0.5 s (after a 2 s warm-up following each plan) the rule takes, for each active provider p, its verified
throughput to the destination over the last 2 s, `rate[p]`, and
1. `eta_cur` = max_p (bytes left at p / rate[p]) - the time the current assignment needs if every provider keeps its
   measured rate;
2. `cap_est[p]` = the last measured rate of p (or the configured egress cap if p was never measured); the fragments of
   the slowest provider q (except the one in flight) are reassigned greedily to the provider with the smallest
   (load + fragment) / cap_est, and `eta_new` = max_p load[p] / cap_est[p], floored by inbound / ingress cap;
3. it switches if eta_cur - eta_new > c_switch + max(eps, rel x eta_cur).

## Cause 1 - measured shares of a shared ingress are read as persistent, independent capacities

In every incorrect-placement cell two providers (the misplaced holder B and the source A) feed the destination C over
C's single 1 Gbps ingress, so each measures ~486 Mbps (`measured_rate_mbps` A = B = 486.5 at the first check, 2.07 s
after the move). The rule then predicts that moving fragments from B to A shortens the restoration (cell 7:
eta_cur 18.3 s -> eta_new 12.1 s, dT 6.1 s > c_switch 0.37 + margin 2.0) because it models A and B as two independent
486 Mbps links. On a shared ingress the sum is fixed: whatever the split, the ~352 fragments left at that moment take
~11.8 s at 1 Gbps. Measured: Sink verified 14.22 s after the move with the re-plan vs 14.26 s without (at moves). The
re-plan therefore changes nothing but the source's bytes (+0.22 Sink: the 89 fragments moved to A, while B's copies are
abandoned). This is ExpD G5 (`../expD/g5_shakedown_observation.md`), reproduced in all 3 reps of cell 7 and as the
first re-plan (at 12.3 s) of every ED run in cells 8, 9 and 10.

The same mis-model makes the later moves partial: `cap_est` of the alternative provider is its measured share (~half
the ingress), so the alternative looks slower than it is and the rule moves only part of the load, then moves again
when the next window shows the new shares (cell 8: 3 re-plans, of which the first moved 93 fragments to A just before
A's egress was degraded, and the next two moved 27 + 55 of them back; net +3.5 s vs at moves; cell 9: 3 re-plans to
move 0.73 Sink off the 62.5 Mbps holder, correct in direction, 3 > the frozen bound of 2).

## Cause 2 - fragment-quantized rate measurement at low rates

A 2 s window at a 62.5 Mbps shared ingress carries ~3.7 fragments of 4 MiB in total, i.e. 1-3 per provider: the
measured rates are 16.8 / 33.6 / 50.3 Mbps steps (cell 10 trace: A 16.8 vs B 33.6, then B 16.8 vs A 33.6, ...). With
Cause 1 the rule reads each step as a persistent capacity difference and predicts large gains (dT 24-102 s against
margins of 10-21 s), so the hysteresis (rel 0.10, eps 2 s) never holds it back; it reassigns toward whichever provider
completed one more fragment in the last window, every 2.5-3.6 s, 28-32 times per run (cell 10), re-sending 0.23 Sink
from A for a 3.9 s gain. Cell 9 does not oscillate only because the degraded link is the holder's own egress (a real
per-provider cap), so moving to A is right whatever the measurement noise.

## Cause 3 (latent) - a units mismatch in the ingress floor and in unmeasured providers' capacity

`rate` and `cap_est` of measured providers are in bytes/s; `known_caps` are in bit/s (`bw_mbps x 1e6`). The floor
`inbound / known_caps[("in", own)]` and `cap_est` of a provider that was never measured (`known_caps[("out", n)]`) are
therefore 8x too optimistic (the trace prints them as 8000 "Mbps"). In the N cells both providers were measured before
the first check and the floor never bound (e.g. cell 7: 1.1 s computed, 8.9 s correct, both below eta_new 12.1 s), so
this did not decide any re-plan here; it is recorded as a defect of the frozen rule to be fixed in any successor.

## What this means

- The frozen M3 solves "which fragments does each provider send" (bottleneck-aware assignment at moves) but decides
  *when to change providers* from a model in which providers never share a bottleneck and measurements are exact.
  Where that model holds (a degraded holder egress, cell 9; ExpD G7) the gain is large (7.5x); where it does not
  (shared destination ingress: cells 7, 8, 10; ExpD G5) it re-plans without benefit, partially, or periodically.
- Any successor (an M3-v2, a separate design with its own preregistration) would have to (i) model the destination's
  ingress as a shared constraint when predicting the gain of a reassignment (the gain of moving load between providers
  that share the bottleneck is zero), (ii) measure rates over windows that hold enough fragments for the hysteresis to
  be meaningful (or hysteresis in fragments, not in relative time), and (iii) compare the predicted gain with the
  switching cost including the bytes re-sent from the source, not only the control delay. None of this is implemented
  or evaluated here.
