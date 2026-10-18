# Experiment R - Repeated mobility: preregistration DRAFT v2 (2026-10-18; not frozen; nothing implemented or run)

**v2 changes (2026-10-18, review before freeze; no R data exist):** a manipulation check for realized source contention
and its use in R-H3(b) (section 3, 6); the coupling of the background sessions' policy to the GPU session's stated
(section 3); run parameters and the trigger fixed (section 3). Proposed, pending approval (decisions R-D1, R-D2).

Common rules, testbed, definitions, implementation items and cost: `../followup_common.md`. Experiment D is prior
evidence only (common rule 1).

## 1. Question

Over which ratio of restoration time to dwell time (rho) does progress preservation (M2) remove re-sent source traffic
and discarded work, and under which condition does it also shorten restoration latency? Experiment D measured two rho
values (2, 4) and one contention level per scenario; R maps the operating region with a fixed schedule definition and
source contention as a second factor. R does **not** estimate how often rho > 1 occurs in deployments; that remains a
stated deployment assumption.

## 2. Prior evidence (predictions only)

| source | observation |
|---|---|
| ExpD G3 (rho 2 / 4, no contention) | source bytes M1 + M2 1.03 / 1.02 vs M1 only 2.01 / 1.52 Sinks; discarded 0.049 / 0.036 vs 1.014 / 0.515; bind-ready 15.11 vs 15.52 s and 15.66 vs 15.17 s (both ingress-bound) |
| ExpD G6 (rho 2, three network sessions on A's egress) | GPU-session bind-ready M1 + M2 43.09 s, OTTER event-driven 42.82 s vs M1 only 57.07 s |
| network-level mobility notes (2026-10-06/07) | rho < 1 (T_m 24 / 32 s): the edge being left binds before it is left; the next edge still needs one link time unless the Sink was pre-positioned |
| GPU node code (read 2026-10-18) | a node keeps the received Sink buffer after bind (so a bound owner can forward as a holder); M1 only drops it at the move (`SINK_DROP`) |

## 3. Design

- Path A -> B -> C -> D (three moves; the first at source chunk M = 30), warm destinations, 1 Gbps, dog workload, k = 2.
- **Factor 1, rho** in {0.5, 1, 2, 4, 8}, with **T_m = T_ref / rho** and the fixed reference T_ref = 14.05 s (common
  section 2): T_m = 28.10, 14.05, 7.03, 3.51, 1.76 s. rho is a schedule parameter, not a measured ratio; the measured
  effective ratio (owner restoration time / T_m) is reported per run.
- **Factor 2, source contention** c in {0, 3}: c = 3 adds three network-level restoration sessions from A (no
  generation; real-size Sinks; `tools/eval/hybrid_net.py`, Scenario B v2 layout, network sessions using the policy
  mapped from the GPU session's), as in ExpD scenario E. Only one session generates; every GPU metric refers to it.
  - **Policy coupling (R-D2, stated before data):** the three background sessions run the policy mapped from the GPU
    session's (`hybrid_net.NET_POLICY`: restart -> restart, split -> reuse_fixed, reuse_dyn -> reuse_dyn), so under M1 + M2
    the background sessions also preserve progress and load the source less. R-H3(b) therefore compares two *systems*
    (every session on M1 only vs every session on M1 + M2), as ExpD G6 did; it is not a per-session isolation.
  - **Realized contention (manipulation check, R-D1):** the background sessions start at the GPU session's first move and
    move on its T_m schedule, so at long T_m they may finish before the GPU session's final restoration. Per run, the
    time-averaged number of active background source flows from A during the GPU session's final restoration
    ([final move, Sink verified]) is reported. A c = 3 cell whose median over reps is < 1.0 for either compared policy is
    reported "contention not realized"; R-H3(b) is NOT EVALUABLE there (R-H1 and R-H2 are still judged). The check
    concerns the manipulated condition, never the outcome.
- Run parameters: trigger M = 30 (dog's trigger call is not a loop cut, `../expW/loop_audit.md`); `--post_chunks 300`,
  `--max_run_s 600` (the longest cell, rho 0.5 with contention, needs ~200 calls after the trigger).
- **Policies:** M1 only (`restart`), M1 + M2 (`split`), OTTER event-driven (`reuse_dyn`, frozen thresholds; no
  placement). M1 only vs M1 + M2 is the M2 comparison; OTTER event-driven is reported for the full system.
- 3 reps per configuration: 5 x 2 x 3 x 3 = **90 runs**.

## 4. Metrics

Primary (M2's claimed effect): **source traffic** B_source,total of the GPU session (Sinks); **discarded bytes**
(Phase 1 definition (a): delivered to an owner that neither bound nor forwarded them). Note fixed in advance: under
definition (a), at rho <= 1 an abandoned owner that already **bound** the Sink is not counted as discarded, so at
rho <= 1 M2's effect appears in source traffic only.

Reported separately (never combined with the primary metrics into one score): **Sink bind-ready after the final move**.

Also reported: B_fwd, aggregate network bytes, re-sent bytes (B_source,total - 1), verified progress retained / reused,
re-plan count (OTTER), source egress utilization and, for c = 3, the network sessions' source bytes and restoration
times and the aggregate source bytes over all four sessions.

## 5. Analytic model (basis for the manipulation checks; stated before data)

Without contention each abandoned owner (B, C) receives min(1, 1 / rho) of a Sink before it is left. M1 only re-sends
from the source to every new owner: B_source(M1 only) = 1 + 2 min(1, 1/rho) (rho 0.5: 3.0; 1: ~3.0; 2: 2.0; 4: 1.5;
8: 1.25); discarded(M1 only) = 2 / rho for rho > 1 (2: 1.0; 4: 0.5; 8: 0.25), ~0 at rho < 1 (bound). M1 + M2 forwards
held fragments: B_source ~ 1.0, discarded ~ 0. Under contention the abandoned owners receive less (shared source
egress), so the model is an upper bound on what M2 can save there; the hypotheses below therefore use each cell's own
M1-only measurement, not the model.

## 6. Confirmatory hypotheses (medians over 3 valid reps; decision rules fixed at the freeze)

- **R-H1 (source traffic), every rho x c cell:** B_source(M1 + M2) <= 1.10 **and**
  B_source(M1 only) - B_source(M1 + M2) >= 0.75 x (B_source(M1 only) - 1), i.e. M2 removes at least 75 % of the bytes
  M1 only re-sends. A cell where M1 only re-sends < 0.10 Sink has nothing to save: R-H1 is NOT EVALUABLE there (reported).
  Origins: 1.10 is G3(a)'s bound (frozen before ExpD); 75 % is a judgment value leaving room for fragments in flight at
  each move. Recorded prediction: supported at c = 0 for every rho (model); at c = 3 unknown.
- **R-H2 (discarded work), every cell:** discarded(M1 + M2) <= 0.10 Sink. Manipulation check (on the baseline, labelled
  as such, not an OTTER claim): at c = 0 and rho in {2, 4, 8}, discarded(M1 only) >= 0.75 x 2 / rho.
  Origins: 0.10 is G3(b)'s bound (frozen before ExpD); the check uses the analytic model with the same 75 % margin.
- **R-H3 (latency, reported separately):** (a) c = 0, every rho: |bind-ready(M1 + M2) - bind-ready(M1 only)| <= 1.0 s
  (both ingress-bound; no latency claim without contention). (b) c = 3, rho in {0.5, 1, 2}: bind-ready(M1 + M2) <=
  bind-ready(M1 only) - 1.0 s (holder forwarding bypasses the contended source egress). rho 4 and 8 at c = 3 are
  descriptive (the holders hold little; the gain is expected to shrink). Cells failing the realized-contention check
  (section 3) are NOT EVALUABLE for (b).
  Origins: the 1.0 s band is G3(c)'s (frozen before ExpD); the direction of (b) follows the mechanism. Recorded
  predictions: (a) supported; (b) supported at rho 2 (G6 prior), unknown at 0.5 and 1.

OTTER event-driven is not part of R-H1-R-H3; its source traffic, discarded bytes, bind-ready and re-plans are reported
next to M1 + M2 in every cell (whether it re-plans under contention is N's subject, not R's).

## 7. Version events at rho <= 1 (fixed now)

At rho <= 1 an intermediate owner binds the Sink before it is left and keeps generating with adaptive refresh on; a
promotion there makes the forwarded Sink stale, the case ExpD's scope excludes. Rule: W1 runs first. Runs are judged by
ExpD's validity rule (a version event before the final bind makes the run invalid); because the workload and seed are
fixed the event is deterministic, so a cell whose three reps all show it is reported NOT EVALUABLE (version event) with
the counts, and the dog W1 result (P_w at the corresponding bound-owner interval) is reported next to it. Nothing in the
node's refresh behaviour is changed to avoid it.

## 8. Descriptive analyses

- Operating-region figure: re-sent bytes and discarded bytes vs rho (log scale), per policy and contention level, with
  the analytic model overlaid; bind-ready vs rho in a separate panel.
- Verified progress retained / reused vs rho; effective rho per run; source egress utilization over time for c = 3.
- Exploratory (after the primary matrix): c = 1; rho = 0.25 (T_m 56.2 s); native bandwidth at rho 2; Full migration and
  Cold restart at rho 0.5 and 8 as references.

## 9. What the outcomes mean for the paper

- R-H1 / R-H2 supported: M2's traffic and work savings hold over the whole tested rho range and under source contention
  (the claim covers rho in [0.5, 8], one workload, three moves).
- R-H3(a) is a "no latency claim" check: if it fails, M2 changes latency without contention and the paper reports it.
- R-H3(b) decides whether the paper may say that M2 shortens restoration under source contention, and at which rho.
- No statement about the frequency of rho > 1 in deployments is derived from R.
