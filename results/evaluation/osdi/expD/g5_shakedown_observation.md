# Known G5 observation from the D0 GPU shakedown (recorded 2026-10-16, before any Experiment D sweep data)

**Status: an observation from one correctness-shakedown run, not an Experiment D result and not a G5 outcome.** G5 is
judged only on the formal Experiment D runs (scenario D, 3 reps, medians), against the frozen text. Nothing below
changes G5, the M3 algorithm, or the shakedown verdict (9/9 PASS on its correctness conditions). Decision (2026-10-16):
preserve the current M3 algorithm (event-driven re-planning, ETA estimation, hysteresis thresholds, provider assignment,
placement rules) unchanged; the formal evaluation decides whether the behaviour is reproducible.

## The run

`results/evaluation/d0_shakedown/policy=reuse_dyn_bw=1000_rho=none_tm=inf_path=AC_pp=top1_L=10_b=1_rep=1_20261016-162052/`
(commit a363411; raw `events.csv`, `flows.csv`, `fragments.csv`, `node_*/fragments.csv`, `summary.json` unchanged).
Full OTTER (OTTER event-driven + top-1 placement), p = 0.6 / 0.3 / 0.1 for B / C / D, L = 10 s, b = 1 Sink, true
destination C (incorrect placement), 1 Gbps.

| quantity | value | source |
|---|---|---|
| placed at B before the move | 299 fragments sent, 294 checksum-verified at the trigger: x = 0.7136 | `summary.json` d0.x_verified_at_move |
| plan at the move (10.04 s) | B -> C 294 fragments (B's), A -> C 118 | `events.csv` flow_start f2_AC, f3_BC |
| measured rates 2.3 s later | A 487 Mbps, B 487 Mbps (C's 1 Gbps ingress shared) | `events.csv` replan |
| re-plan (12.35 s, no network change) | ETA 18.2 -> 12.1 s; 88 fragments moved from B to A (B keeps 175) | `events.csv` replan, flow_cancel f3_BC |
| Sink bind-ready after the move | 14.94 s (no placement, same harness: 14.85 s) | `summary.json` |
| B_pre / B_post / B_source,total | 0.72 / 0.51 / 1.23 Sinks | d0 block |
| B_fwd (from B, verified at C) | 0.50 Sink | d0 block |
| B_network,total | 1.73 Sinks | bytes.by_link |
| duplicates, version events | 0, 0 | validation |

## Reading against the frozen G5 text (for information only)

(a) bind-ready within 1.5 s of no placement: 14.94 vs 14.85 s, inside the bound; (b) B_source,total <= 1.02: 1.23,
outside; (c) B_post <= (1 - x) + 0.02 = 0.31: 0.51, outside; (d) B_fwd >= 0.9 x = 0.64: 0.50, outside. If the formal
runs reproduce this, G5 is **not supported** for Full OTTER and is reported as such.

## Cause (mechanism, from the decision trace)

The event-driven rule estimates each provider's remaining time from its measured rate over the 2 s window and assumes
that rate persists. Both providers share the destination's ingress; when A's flow (118 fragments) ends, B's rate would
roughly double. The original plan was therefore already ingress-bound (412 fragments at 1 Gbps ~ 13.8 s), and the
re-plan changed no latency (Sink verified 14.3 s after the move) while moving 88 fragments, 0.21 Sink, from the
misplaced holder to the source. This is the frozen E-pilot v2 rule (decision-equivalent to the network harness,
`osdi/d0/planner_equivalence_seed2.txt`); the network-level A-pilot prediction (B_source,total 1.00, B_fwd 0.72) was
made without event-driven re-planning in that configuration.

## What is preserved

The run directory, its decision trace and this note are kept as written; the run stays in the shakedown report; the
GPU harness and the planner are not modified to make G5 pass; G5's thresholds are unchanged.
