# Diagnostic: holder-bandwidth sensitivity of a wrongly placed Sink under shared-source contention (2026-10-15)

Not pre-registered; approved after A3 and reported separately from it. 60 runs: the A3/H5e arrangement (N = 4 sessions
sharing source A at 1 Gbps; session s0 pre-positions 0.5 Sink to the top-1 candidate B during L = 10 s with the others
idle, then moves to C while the three others start restoring from A) over holder egress B_h in {62.5, 125, 250, 500,
1000} Mbps x restoration {reuse_fixed, reuse_aware_in} x {none, top-1} x 3 reps. Model predictions were recorded in
TOPOLOGY_PLAN.md G.1 before the run. Raw runs `restore_holder_diag/`; tables `summary.csv`, `summary_by_config.csv`,
`criteria.md` (`tools/eval/aggregate_prepos.py --experiment restore_holder_diag --diag`).

## Run validity

60/60 valid: every fragment verified; paced egress within cap (source 998.5 Mbps worst over 10 s; edges at most
1.02 x B_h); kernel NIC receive peaks <= 1056 Mbps (no external traffic this time); four distinct hosts; no early
rate/cancel events. Rep spread <= 0.1 s in every configuration.

## Results (medians; T_r = s0's move -> all fragments verified at C; "gain" = T_r(none) - T_r(top-1))

| B_h (Mbps) | fixed none -> top-1 | fixed gain | aware_in none -> top-1 | aware_in gain | aware_in split of the 0.5 Sink: B forwards / A resends | source Sinks per session fixed / aware_in | others' makespan none / fixed / aware_in |
|---|---|---|---|---|---|---|---|
| 62.5 | 55.5 -> **159.6** | **-104.1** | 55.5 -> 52.1 | +3.3 | 0.06 / 0.44 | 1.00 / 1.12 | 71.2 / **120.1** / 65.1 |
| 125 | 55.5 -> 79.9 | -24.4 | 55.5 -> 48.7 | +6.8 | 0.12 / 0.38 | 1.00 / 1.09 | 65.5 / 71.2 / 63.8 |
| 250 | 55.4 -> 40.0 | +15.4 | 55.4 -> 41.6 | +13.8 | 0.25 / 0.25 | 1.00 / 1.06 | 65.5 / 58.5 / 62.0 |
| 500 | 55.4 -> 27.8 | +27.7 | 55.4 -> 27.8 | +27.7 | 0.50 / 0 | 1.00 / 1.00 | 65.5 / 58.6 / 58.6 |
| 1000 | 55.5 -> 27.8 | +27.7 | 55.5 -> 27.8 | +27.7 | 0.50 / 0 | 1.00 / 1.00 | 65.5 / 58.6 / 58.6 |

Total traffic is 1.27 Sinks per session in every top-1 configuration (the 0.5 Sink is carried twice, A -> B and then
B -> C or A -> C again) and 1.14 with none (the others' own forwarding).

## Measured crossover vs analytical

- Fixed forwarding of the wrongly placed fragments helps only from **250 Mbps** up (gain +15.4 s) and is harmful below
  (-24.4 s at 125, -104.1 s at 62.5 Mbps, where s0's restoration takes 160 s and the slow forwarding also delays the
  other three sessions to 120 s). The analytical crossover B_h = x B_s / (N (1 - x)) = 250 Mbps for x = 0.5, N = 4 is
  confirmed: at exactly 250 Mbps the holder's 0.5 Sink (28.1 s) takes as long as the source's 0.5 Sink at its
  250 Mbps share, so parallel forwarding is optimal and fixed = optimal there.
- aware_in is never worse than none (gain +3.3 / +6.8 / +13.8 / +27.7 / +27.7 s) and selects the three regimes the
  analysis predicted: slow holders (62.5, 125) -> mostly retransmit from the source (B forwards 0.06 / 0.12 Sink,
  A resends 0.44 / 0.38); the crossover (250) -> an even split (0.25 / 0.25); fast holders (>= 500) -> pure reuse
  (0.50 / 0, no retransmission, source exactly 1.00 Sink per session).

## Does aware_in pick the right provider?

Across the range, yes, with one quantified exception at the crossover: at 250 Mbps aware_in (41.6 s, 1.06 Sinks of
source) is **1.6 s slower than fixed** (40.0 s, 1.00) and costs 0.06 Sink of retransmission, exactly as the model
predicted. The rule balances backlogs at plan time with the source's queue counted at its 4-way share; the other
sessions then finish and free source capacity, so the optimal split shifts toward the holder after the plan, which a
plan-once rule cannot follow. Elsewhere its decision matches the best policy within 0.1 s. Model error over the 60
runs: <= 0.3 s in T_r, <= 0.01 Sink in bytes.

## Regressions

- Latency: the 1.6 s at 250 Mbps above (aware_in vs fixed), bounded by the retransmitted 0.06 Sink; none elsewhere.
- Traffic: aware_in's retransmission (0.44 / 0.38 / 0.25 Sink at 62.5 / 125 / 250 Mbps) is the price of the latency it
  recovers (+107 / +31 / -1.6 s vs fixed); the aggregate traffic is identical (1.27 Sinks per session) because the
  retransmitted bytes replace forwarded ones. Fixed forwarding at slow holders is the real regression: it also delays
  the other sessions (others' makespan 120.1 s at 62.5 Mbps vs 65.1 with aware_in), because their own held fragments
  are forwarded through the same slow edges.

## Implications for M2 / M3

- The value of speculative placement is set by the bottleneck at recovery time, not by prediction correctness: the
  same wrongly placed 0.5 Sink is worth +27.7 s with fast holders, 0 at the ingress bound (A3, N = 1), and -104 s under
  unconditional reuse with a slow holder.
- Bottleneck-aware provider selection is therefore a precondition for pre-positioning, not an optimization on top of
  it: it converts the slow-holder loss into a 3-7 s gain and leaves fast-holder reuse untouched. Its remaining
  weakness is quantified and small (1.6 s at the crossover, from planning once); re-planning when the source's share
  changes would remove it, and that is a concrete, measurable target for the dynamic variant in Experiment E rather than
  a reason to build a topology optimizer.
- For the paper: the Step 2 crossover (restart vs unconditional reuse) and this one (retransmit vs forward a wrongly
  placed fragment) are the same law, B_h* = x B_s / (N (1 - x)), measured from both sides.
