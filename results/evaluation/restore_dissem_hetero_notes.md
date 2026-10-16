# Experiment B, heterogeneous subset: five dissemination plans x three conditions, 45 runs (2026-10-15)

One Sink at A to B, C, D; plans star / pipelined line / tree (A->B->{C,D}) / disjoint-fragment multipath
(butterfly-like) / aware fragment assignment; conditions B_f = 500 Mbps, B_f = 125 Mbps (forwarder egress), B_s = 250 Mbps
(source egress), all other caps 1 Gbps; 3 reps. The uniform 1 Gbps condition is the B-pilot (`restore_dissem_pilot`,
1 rep). Design, scope and the 15 model predictions were recorded before the run (TOPOLOGY_PLAN.md G.1). Raw runs
`restore_dissem_hetero/plan=*`; tables and verdicts `summary.csv`, `summary_by_config.csv`, `criteria.md`; figure
`figures/figE10_makespan_by_condition` (`tools/eval/aggregate_dissem.py --experiment restore_dissem_hetero --ref restore_dissem_pilot`).

## Run validity

45/45 valid (50/50 with the pilot): every fragment verified at all three destinations, no duplicates or missing
fragments, paced egress within cap over every 10 s window (source 996.6 Mbps worst; forwarders 500 / 126 / 169-250 Mbps
at the 500 / 125 / 1000 caps), kernel NIC receive peaks <= 1041 Mbps, four distinct hosts, all nodes on commit ccd57d6,
every forwarder pipelined. Rep spread <= 0.1 s in every configuration.

## Results (makespan s, medians; source Sinks in brackets; model in italics)

| condition | star | pipelined line | tree | multipath | **aware** | best fixed | aware / best |
|---|---|---|---|---|---|---|---|
| uniform (pilot) | 41.7 *41.8* [3.00] | 14.1 *14.2* [1.00] | 27.9 *28.0* [1.00] | 14.0 *14.2* [1.00] | 14.0 *14.3* [1.00] | multipath 14.0 | 1.00 |
| B_f = 500 | 41.7 [3.00] | 28.0 *28.0* [1.00] | 55.6 *55.6* [1.00] | 18.6 *18.9* [1.00] | **16.9** *17.1* [1.20] | multipath 18.6 | **0.91** |
| B_f = 125 | **41.7** [3.00] | 111.0 *111.2* [1.00] | 221.1 *221.5* [1.00] | 73.8 *74.5* [1.00] | 42.1 *42.3* [2.18] | star 41.7 | 1.01 |
| B_s = 250 | 166.0 *166.2* [3.00] | 55.6 *55.6* [1.00] | 55.6 *55.6* [1.00] | 55.4 *55.7* [1.00] | 55.4 *55.6* [1.00] | multipath 55.4 | 1.00 |

Per-destination completion follows the plans' structure: line and tree finish B at 14.0 s and the downstream nodes
late (line 110.8 / 111.1, tree 221.1 / 221.1 at B_f = 125); multipath and aware finish all three within 0.1-0.8 s of
each other.

## Verdicts over the tested conditions (frozen F; full grid not tested)

| clause | measured | verdict |
|---|---|---|
| H6a best fixed plan differs across conditions | multipath (uniform, B_f = 500, B_s = 250), star (B_f = 125) | supported |
| H6b at B_s = 250 every forwarding plan <= 0.5 x star | 55.4-55.6 vs 166.0 | supported |
| H6c at B_f = 125 line and tree >= 2 x star | 111.0 / 221.1 vs 41.7 | supported |
| H6d at B_f = 500 multipath <= 0.75 x line and <= 0.5 x tree | 18.6 vs 28.0 / 55.6 | supported |
| H6e uniform multipath within 1 s of line | 14.0 vs 14.1 | supported |
| H6f-subset aware within 10 % of the best fixed plan in every tested condition | 1.00 / 0.91 / 1.01 / 1.00 | **supported on the subset**; full-grid H6f open |

Model error: max 0.70 s in makespan (median 0.17 s; the 0.7 s is multipath at B_f = 125, 73.8 vs 74.5), <= 0.006 Sink in
source bytes. The analytical regions of D.2 are met: forwarding plans pay (2/3) T(B_f) (multipath) or T(B_f) (line)
when forwarders are slow, star pays 3 T(B_s), and at B_f = 125 star wins because 125 < 222 Mbps.

## Reading

1. **The best fixed plan changes with the bottleneck** (H6a-d): multipath where forwarders are fast enough (uniform,
   500 Mbps, slow source), star where they are not (125 Mbps). No fixed family is right everywhere, as predicted.
2. **The aware assignment reaches the best fixed plan in every tested condition and beats it where the fixed families
   are all sub-optimal.** At B_f = 500 it finishes in 16.9 s against multipath's 18.6 s (9 % faster) by sending 1.20
   Sinks from the source instead of 1.00 and 0.60 Sink from each forwarder instead of 0.67: it balances the source's
   egress time against the forwarders' (A 1.2 S at 1 Gbps = 16.9 s; each edge 0.6 S at 500 Mbps = 16.9 s) instead of
   fixing the split at thirds. At B_f = 125 it sends 2.18 Sinks from the source and lets each edge forward only 0.27
   Sink, landing within 0.4 s of star; at B_s = 250 and uniform it reproduces the multipath split exactly (A 1.0,
   edges 0.67). Its decisions came from caps, its own queue and fragment availability only, computed once at t0.
3. **Mechanism, stated precisely.** The aware plan is not a selection among star / line / tree / multipath. It is a
   per-(fragment, destination) provider assignment that also decides how much the source retransmits; the four fixed
   families are points in that space (A 3.0 / 1.0 / 1.0 / 1.0 Sinks), and the balanced assignment (1.20 at B_f = 500,
   2.18 at B_f = 125) lies between them. Its cost is source traffic: 0.20 and 1.18 Sinks above the forwarding plans
   where it beats or matches them; total traffic is 3.00 Sinks for every plan (three copies must exist).
4. **Does any result justify a separate topology-selection mechanism?** Not on this subset. Choosing the best fixed
   family would need the same information the assignment uses (caps and holdings) and would still lose 9 % at
   B_f = 500. What the subset does not test is reconfiguration *during* a dissemination or a restoration (capacities
   or destinations changing after the plan), which is Experiment E's question, and the full B grid (H6f stays open).

## Most informative Experiment E configuration for dynamic reconfiguration

Two conditions, both already pointed at by measured weaknesses of plan-once assignment:
- **Forwarder degradation mid-restoration** (D.3 / C2): under A -> B -> C -> D mobility with C forwarding to D at
  1 Gbps, drop C's egress to 125 or 62.5 Mbps when D holds ~50 %; aware-at-moves keeps C (remaining 0.5 Sink at
  62.5 Mbps = 112 s), event-driven re-planning moves the rest to A/B (~7 s + 0.3 s + one 4 MiB fragment drain). The
  predicted gap (~100 s) is large enough that even a coarse trigger (rate estimate from FRAG_RECV timestamps every few
  seconds) will show it, and the switching cost is measured directly.
- **Share change at the crossover** (the holder diagnostic's 1.6 s): N = 4 at B_h = 250 Mbps, where the source's share
  rises as other sessions finish; re-planning when the measured source rate changes by > 25 % should recover the 1.6 s
  and shows the small end of the benefit range.
Both use the dissemination/pre-positioning harness plus E.4 (time-varying caps, re-plan trigger with hysteresis,
switching-cost accounting). The first configuration decides whether M3 has a large regime; the second bounds its
gain where conditions change slowly. Policies: aware-at-moves (M2) vs aware + event-driven re-plan (M3 candidate),
with restart and fixed line as references.
