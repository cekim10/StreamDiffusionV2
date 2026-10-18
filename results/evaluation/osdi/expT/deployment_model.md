# Experiment T (trace-driven M3 study) - 1. Deployment network model (DRAFT, 2026-10-17)

Planning document. Nothing here changes Experiment D (frozen 81bb628; results `../expD/expD_report.md`) or OTTER's
M1/M2/M3 logic. No measurement has been run for this study.

## Roles

| role | what it is | what it holds / does |
|---|---|---|
| user device U | the phone or camera client | uploads the input video stream and receives generated output over the **last-mile** (cellular radio) link to the edge site that currently serves it; its movement between cells causes the handovers |
| current destination (owner) O | the edge site serving U after the latest move | runs generation; receives the session's fragments; binds the Sink when it is complete |
| source A | the edge site where the session ran when the Sink version was created (the first owner) | holds the complete, verified Sink of that version; always a provider |
| intermediate holders H | past owners (and, with placement, candidates; not used in this study) | hold the fragments they verified before execution left them; may forward them (M2) |
| providers | A or any H sending fragments to O | chosen per fragment by the policy (M1 only: A; M1 + M2: newest holder, else A; OTTER: M3 assignment) |

## Two different networks

1. **Last-mile mobility (U <-> current edge).** Its role in this study is only to *time the moves*: a handover of U
   to a cell served by a different edge site triggers a move of execution. OTTER's state transfers never cross the
   last-mile link, so cellular throughput traces are **not** used as inter-edge capacities (see `trace_candidates.md`).
   The study does not model upload/download of the video streams themselves (scope limitation, as in Experiment D).
2. **Inter-edge state transfer (edge site <-> edge site).** Every Sink fragment travels between edge sites over the
   metro/backhaul network. This is where M3's assignment and re-planning act, and where realistic variability matters.

## Capacity model (what is shared)

Each edge site X connects to the metro/backhaul network through a site uplink with egress capacity C_out(X) and
ingress capacity C_in(X). The metro core is assumed non-blocking between site uplinks. All traffic of a site shares
its uplink: other tenants' traffic (cross-traffic, x_out(X, t), x_in(X, t)) and every OTTER fragment flow of every
session. Hence:

- **source egress** = A's uplink egress: shared by all of A's flows (every session's source flows) and A's cross-traffic;
- **provider egress** = a holder's uplink egress: shared by its forwarding flows and its cross-traffic;
- **destination ingress** = O's uplink ingress: shared by every provider sending to O and O's cross-traffic;
- available capacity for OTTER at time t: C_out(X) - x_out(X, t) and C_in(X) - x_in(X, t), divided max-min fairly among
  OTTER's flows.

This is exactly the harness's emulation: per-node egress / ingress caps with one max-min allocation across all flows
(`restore_planner.maxmin`), where a cap's time variation represents the cross-traffic. Planners see only the nominal
caps at plan time and measured throughput (frozen M3 behaviour); they are never told the cross-traffic.

## Assumptions

1. One edge site per cell, or per cluster of k adjacent cells (k is a sensitivity parameter, k = 1, 2, 4); a handover
   between cells of different sites is a move; handovers inside a site are not moves.
2. The move is issued at the handover instant (no prediction; placement is disabled in this study, so Full OTTER =
   OTTER event-driven, as prereg v3 section 3 defines for scenarios without a prediction).
3. Cross-traffic is open-loop: replayed as a time series of available capacity, not as competing TCP flows that react
   to OTTER's traffic.
4. Site uplink capacity is emulated at 1 Gbps per direction (the testbed shaping used in Experiments B-E and D);
   cross-traffic is applied as a utilization fraction u(t) of that capacity: available = C (1 - u(t)) (utilization is
   assumed scale-free across link capacities).
5. One Sink version per restoration (Experiment D scope conditions 5-6); runs with version events are flagged and
   reported (`sink_stability_plan.md`).

## Limitations stated up front

- Real metro cores can have shared bottlenecks between distinct site pairs; the model has none beyond site uplinks.
- Testbed RTT (sub-millisecond LAN) is lower than metro RTT (milliseconds); TCP dynamics at higher RTT are not emulated.
- Open-loop cross-traffic overstates its rigidity (real cross-traffic yields partly to OTTER's flows and vice versa).
- Real edge uplinks are typically 10-100 Gbps; the study uses 1 Gbps with utilization scaling, so absolute times
  scale with the Sink size / capacity ratio, not with deployed hardware.
- The cell-to-site mapping is synthetic (k), because public mobility traces identify cells (anonymized tower IDs), not
  the edge sites that would serve them.
