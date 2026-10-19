# M3-v2: bottleneck-constrained, uncertainty-aware restoration re-planning (design and development record)

Status: implemented as policy `reuse_dyn2` (`tools/eval/restore_planner.dyn_decide_v2`, `update_bottlenecks`,
`fluid_eta`; orchestrator `Run.dyn_check_v2`). M3-v1 (`reuse_dyn`, `dyn_decide`) is unchanged and selectable. M1 / M2,
the migration protocol, the fragment table, the state formats, the measurement (verified bytes per provider over
`dyn_window`) and the v1 thresholds (`dyn_period` 0.5 s, `dyn_window` 2 s, `dyn_warmup` 2 s, `dyn_eps` 2 s,
`dyn_rel` 0.10, `dyn_ctrl` 0.3 s) are unchanged. **Development data:** the frozen Experiment N cells 7-10
(`m3_root_cause.md`); nothing below is evidence for v2 (holdout plan: `m3v2_holdout_plan.md`, after the freeze).

## 1. What changes (and why: the three causes of `m3_root_cause.md`)

| v1 (frozen) | v2 | cause addressed |
|---|---|---|
| `known_caps` in bit/s mixed with rates in bytes/s (ingress floor and unmeasured providers 8x optimistic) | every capacity converted once to bytes/s at the harness boundary (`bps_to_Bps`); unit tests | 3 |
| each provider's measured rate = its persistent independent capacity; ETA = max_p (left_p / rate_p) | a **bottleneck model**: per-provider capacities `c_est[p]` and the destination's ingress `I_est`, estimated separately from the same measurements; ETA of *any* assignment = max-min fluid simulation under {c_est, I_est} (`fluid_eta`, re-solved whenever a provider finishes) | 1 |
| reassign the slowest provider's fragments greedily by (load + f) / rate | **joint** candidate: fragments move from the provider that finishes last to the provider that would finish earliest, only while that shortens the longest finish; in-flight heads stay; the current assignment is the starting point (no churn when nobody is behind) | 1, 3 |
| switch if dT > ctrl + drain + max(eps, rel x eta_cur) | same hysteresis, applied to the **pessimistic gain** (current providers +1 fragment/span faster, new ones -1 slower); switching cost = ctrl + drain of every losing provider's in-flight fragment | 2 |
| rates over one 2 s window, no notion of resolution | attribution uses rates averaged over a **span holding >= 8 fragments in aggregate** at the current ingress estimate (2 s at 1 Gbps, ~6 s at 62.5 Mbps); differences below **two fragments per span** are not evidence; downward revisions need a span without a transition (all window rates within two raw-window fragments) | 2 |
| - | **anti-oscillation**: a re-plan that reverses the previous one is refused unless a bottleneck estimate changed by more than the resolution | 2 |
| - | **single-provider probe**: when the only evidence for a provider bottleneck is one provider delivering below the ingress estimate (indistinguishable from an ingress drop), at most 4 fragments move; the next windows, with two providers, either confirm (aggregate rises: the rest moves) or withdraw the attribution (both share the aggregate: `I_est` drops, nothing else moves). Bounded cost: 4 fragments (0.01 Sink) | 1, 2 |

## 2. Bottleneck estimator (`update_bottlenecks`), per check

Inputs: window rates `rate[p]` (bytes/s) of the active providers, nominal caps (bytes/s), resolution `res` = one
fragment per window. State: `I_est` (init nominal ingress), `c_est[p]` (init nominal egress), rate history over the
span, single-provider attributions, confirmations.
1. span = max(window, 8 x fragment / I_est); `sm[p]` = mean of the window rates in the span; `res_eff` = fragment / span;
   margin = 2 x `res_eff`; `steady[p]` = the span's window rates differ by <= 2 x `res` (no transition inside).
2. Providers with zero delivery are excluded from the aggregate R and the fair share; if they stay at zero over a
   steady span while others deliver, they are stalled (`c_est` = res_eff / 2: their fragments can move).
3. n >= 2 delivering providers: p is **provider-limited** if steady, `sm[p]` < share - margin and another provider is
   above share + margin -> `c_est[p]` = `sm[p]` (confirmed). If none is limited, all are steady and R < `I_est` - margin,
   the **ingress** dropped -> `I_est` = R, single-provider attributions withdrawn.
4. n = 1: if steady and `sm[p]` < `I_est` - margin -> `c_est[p]` = `sm[p]`, marked *single-provider* (unconfirmed).
5. Upward revisions (`sm[p]` > `c_est[p]` + margin; R > `I_est` + margin) are immediate.

## 3. Decision (`dyn_decide_v2`), per check after the warm-up

eta_cur = fluid(current); candidate by joint reassignment (section 1); if nothing moves -> None. If every losing
provider is only single-provider-attributed and more than 4 fragments would move -> probe (4 fragments). Gain
dT = fluid(current, c + res_eff) - fluid(candidate, c - res_eff); switch iff dT > ctrl + drain + max(eps, rel x eta_cur)
and the move does not reverse the previous re-plan without a changed estimate. The harness cancels the losing
providers' flows (their in-flight head drains at the node, as v1), re-starts a flow for what stays, and adds the moved
fragments to the gaining providers' flows.

## 4. Development tests (CPU; `tools/eval/test_m3v2.py`; development data, not evidence)

- Units: bit/s -> bytes/s; one 4 MiB fragment per 2 s window = 16.78 Mbps.
- Fluid ETA: split-independent under a shared ingress (352 fragments: 11.81 s for any split); provider-limited holder
  (62.5 Mbps) 161 s -> 10 s when moved; re-solve when a provider finishes.
- Estimator: balanced shares keep the nominal estimates; one provider dropping while the other rises is attributed
  after a transition-free span, not in the first window; both dropping together (16.8 vs 33.6 Mbps quantized, flipping)
  lowers `I_est` and attributes nothing.
- Synthetic decisions: cell-7 situation -> no re-plan; cell-9 situation (two providers, B degraded) -> one joint move
  of B's movable fragments to A balanced by capacity (eta 146 -> 12 s), then no further move; cell-10 situation
  (quantized flips) -> no re-plan over 6 windows; cell-8 situation -> nothing movable (A's fragments are held only by A).
- Replay of the frozen **at-moves** streams (the measurement v2 would see while it has not re-planned): cell 7 whole run
  no re-plan (v1: re-plan at +2.3 s); cell 8 whole run no re-plan; cell 9 first decision after the change = a 4-fragment
  probe to A; cell 10 at most one probe.
- Loopback (fake nodes, emulated caps; section 5) and GPU regression on cells 7-10 before the freeze.

## 5. Loopback regression on cells 7-10 (fake nodes; 100 Mbps nominal, degradation 6.25 Mbps, 16 fragments of 4 MiB)

Plumbing only: the scaled emulation does not reproduce v1's false positive (v1 also makes 0 re-plans in cells 7-8
here: with 16 fragments the first check sees too few deliveries), one fragment is 6 % of the Sink (so byte bounds are
meaningless) and one fragment on the degraded link takes 5.4 s. What it verifies: the v2 policy runs end to end through
the orchestrator (flow cancel / keep / add), its re-plan records carry I_est, c_est and the probe flag, the trigger fires
at ceil(|S| / 2) = 8 of 16, and runs are valid.

| cell | at moves bind / B_src | v1 bind / B_src / re-plans | v2 bind / B_src / re-plans (record) |
|---|---|---|---|
| 7 | 5.6 s / 1.06 | 5.6 / 1.00 / 0 | 5.6 / 1.06 / 0 |
| 8 | 5.6 / 1.00 | 5.6 / 1.00 / 0 | 5.6 / 1.00 / 0 |
| 9 | 45.9 / 1.00 | 17.2 / 1.31 / 1 | 22.8 / 1.25 / 1 (11.8 s: B -> A 4 fragments, eta 28 -> 4 s, I_est 100, c_B 8.4) |
| 10 | 45.3 / 1.00 | 42.8 / 1.31 / 1 | 43.0 / 1.25 / 1 (12.9 s: B -> A 4 fragments; c_B attributed from one 2 s window holding 0-1 fragments: the quantization regime of the scaled emulation) |

v2's extra 5.4 s in cell 9 vs v1 is one fragment left at B after the balanced move (head + one in flight at the cancel)
on a 6.25 Mbps link; at 412 fragments and 62.5 Mbps the same effect is ~0.5 s. The GPU regression (section 6) is the
behavioural test.

## 6. GPU regression on cells 7-10 (`run_wrn.py m3dev`: at-moves, v1, v2, 1 rep each; development data)

Pass conditions, written before the run (a failure is a defect to fix before the freeze; passing is not evidence):

| cell | condition on v2 (vs at-moves of the same run set) |
|---|---|
| 7 incorrect x 0 | 0 re-plans; B_source <= at-moves + 0.02; bind within 1.0 s |
| 8 incorrect x src | 0 re-plans (A's fragments are held only by A: nothing can move); bind within 1.0 s; B_source <= + 0.02 |
| 9 incorrect x hold | <= 2 re-plans (probe + move), bind <= 0.5 x at-moves, 0 duplicates; B_source reported |
| 10 incorrect x in | <= 1 re-plan (a probe), B_source <= at-moves + 0.05, bind within 1.0 s |
| all | the trigger fired once at ceil(|S| / 2); valid by `wrn_validity`; every v2 re-plan record carries I_est, c_est, probe |

Results: [GPU RESULTS]

## 7. Freeze - [FREEZE RECORD]
