# OTTER M3 research plan: pre-positioning, transfer topologies, dynamic re-planning (v3, criteria frozen 2026-10-15)

Status: audit + experimental design, revised after two reviews (v1 e3dd1f8, v2 7d1e916). **The hypotheses and
criteria in section F are frozen at this commit** and are not edited after results exist; later sections may add
model tables before a run, never change a threshold. Nothing in sections A-J has been run except the Step 1 loopback
check noted in E.5. v3 changes: H5b compares allocations under identical constraints (greedy is the optimum; the
"spreading beats top-1" claim is withdrawn), Experiment E separates restart / progress-preserving star / forwarding
and adds the revisit path A->B->C->D->B, H8c is a Pareto-frontier criterion. Every number is tagged **measured** (committed artifact), **analytical** (closed-form from
link capacities, not a run), **model** (fluid simulation `tools/eval/restore_model.py`, to be extended), or
**proposed** (mechanism not implemented). Progress-Aware Topology Morphing (M3) stays **provisional**: it is neither
removed nor confirmed until Experiments B and E decide whether reconfiguration adds value beyond provider selection.

Changes from v1: (1) pre-positioning predictions recomputed with one latency definition (the v1 top-1 figure 10.4 s was
an arithmetic error; correct 8.4 s); H5b split into mean and tail with the predicted mean penalty of tail coverage
stated; (2) H5e reworded and given an explicit cost model with holder egress and ingress sharing; (3) the Butterfly /
Tree comparison restricted to the stated implementations and assumptions, with the assumptions listed and H6d left to
measurement; (4) M3 kept provisional; (5) Experiment E (topology under repeated execution mobility) added; (6) execution
order changed to pilots before any sweep.

## A. Current verified evidence (measured; artifacts named)

| experiment | artifact | result |
|---|---|---|
| State characterization (31 runs) | `state_migration/prompt_sweep/`, Figs. 2-3 | immediate 2.67 MiB, durable Sink 1.61 GiB, ephemeral 4.41 GiB; Sink loss diverges 31/31; ephemeral-only loss heals 21/21 without adaptive refresh |
| Single handoff, 6 bandwidths x 3 reps | `single_handoff/`, Fig. 6, Fig. 7 | first output 0.69-0.74 s at every bandwidth; Sink bound 57.4 s @250 Mbps, 14.8 s @1 Gbps, 3.1 s native; rejoin (>= 35 dB) 6 calls after bind |
| Phase 1 repeated mobility A->B->C->D, 5 policies x rho {0.5..8} x 3 (GPU, physical) | `repeated_mobility_notes.md`, `repeated_mobility/figures/` | after the final move every non-oracle policy restores in 14.8-15.4 s (= S / 1 Gbps ingress); reuse removes waste (0.03-0.07 vs restart 0.26-2.00 Sinks) and keeps the source at ~1 Sink; oracle 0.7-11.4 s; control-plane cost per route change 0.28-0.32 s median, 0.68 s max |
| Scenario B v2, source shared by N sessions, 72 runs (network level) | `restore_contention_v2_notes.md`, `restore_contention_v2/criteria.md` | one move: reuse_fixed beats restart by 7.6/9.7/10.2 s at N = 2/4/8, 0 at N = 1; continuous mobility: restart restored 0 sessions in every run, reuse_fixed all; adaptive (probe-rate) worse than fixed at N >= 2 (H3b rejected) |
| Step 2, holder egress 62.5-1000 Mbps, 180 runs (network level) | `restore_holder_notes.md`, `restore_holder/criteria.md` | crossover exists (restart beats unconditional reuse by 14-97 s when holders are slow); backlog-aware provider selection <= 0.85 x fixed in every crossover condition, equal to fixed elsewhere, 12-13 % below the better baseline at N = 2/4; H4c failed at (N = 1, 500 Mbps): 0.17 Sink resent with no latency gain (ingress-bound) |
| Fluid model vs measurements | `restore_model.py`, Step 2 notes | every Scenario B / Step 2 median within 0.99 s (median 0.14 s), source bytes within 0.1 Sink |

Two facts organize everything below:
1. **Ingress bound.** A destination with ingress B_in cannot be restored sooner than (bytes it still lacks) / B_in after
   it becomes the owner; 14.05 s for a whole Sink at 1 Gbps, regardless of where the bytes come from (Phase 1 measured
   exactly this for every non-oracle policy).
2. **Source-sharing bound.** When one source serves N sessions it must send at least what no holder has; fixed reuse
   makes that exactly one Sink per session (measured 1.00). Routing gains exist only when the binding resource is a
   shared sender (source or slow holder), not the receiver's ingress.

## B. Implementation status (inspected 2026-10-15)

| capability | GPU harness (`mobility_node.py`, `mobility_orchestrate.py`) | network harness (`restore_node.py`, `restore_orchestrate.py`) |
|---|---|---|
| policies | restart, relay, relay_pipe, split (= reuse_fixed), direct (perfect oracle, unlimited budget, from t = 0) | restart, reuse_fixed, reuse_adaptive, reuse_aware |
| fragment-level multi-provider delivery to ONE destination | yes (split) | yes (fixed / adaptive / aware) |
| one session required at SEVERAL destinations at once (dissemination) | no: one owner per session | no |
| forwarding between non-owners / pipelined forwarding as fragments arrive | relay_pipe only along the fixed chain (FLOW_ADD exists) | no FLOW_ADD; a flow's fragment list is fixed at start |
| topology change without discarding verified fragments | yes, at MOVES only (cancel obsolete flows, keep held fragments, re-plan providers = attach + reparent + prune at a move) | same |
| re-plan on other events (bandwidth, deadline, candidate-set change) | no | no (plan runs at start, move, flow_done) |
| pre-positioning to non-owners before a move | only the oracle (`direct`): final owner known, whole Sink, no budget | no; `holders` come from the ownership history, so fragments at a never-owner would not be forwarded |
| per-node egress/ingress caps, max-min fair, token buckets, on-the-wire verification | yes | yes (+ paced-egress check per 10 s window) |
| per-LINK capacity matrix, time-varying caps | no | no (per node, constant) |
| deadlines, deadline-miss accounting | no | no |
| time to 35 dB PSNR, bind, first output | yes | n/a |
| full-state migration / cold restart / replay under repeated mobility | single-handoff harness only | n/a |
| ingress-aware correction of `reuse_aware` (H4c) | not implemented | **not implemented** (sketched in `restore_holder_notes.md`) |

Multi-destination dissemination: **not supported**. Fragment-level multipath: **into one destination only**.
Reconfiguration without discarding verified fragments: **supported, triggered by moves only**. Pre-positioning:
**perfect oracle only**.

## C. Experiment matrix

| id | question | level | depends on | order |
|---|---|---|---|---|
| H4c fix | does the ingress-aware correction remove the (N = 1, 500 Mbps) retransmission without changing any other Step 2 result? | network, 4 hosts | nothing | 1 |
| A | can bytes sent to likely destinations before a move cut post-move restoration latency, at what traffic cost, and when does spreading beat top-1? | model + 4 hosts; 2-3 GPU points later | E.1 | pilot 2, sweep 4 |
| B | which transfer graph (star / pipelined line / tree / disjoint multipath) is optimal under which capacities when three destinations need one Sink, and does the backlog-aware rule reproduce the best one? | model (any size) + 4 hosts (1 source, 3 destinations) | E.2, E.3 | pilot 3, sweep 5 |
| E | under execution mobility A->B->C->D with incomplete restoration at intermediate owners, do fixed topologies (star, line, tree, butterfly-like) differ, and does progress-aware dynamic reconfiguration beat the best fixed one and "aware at moves only"? | network, 4 hosts; GPU subset in D | E.2, E.3, E.4 | 5b (after B) |
| C | does re-planning on bandwidth / deadline changes (not only moves) reduce deadline misses over "aware at moves only" by more than its switching cost? | network, 4 hosts | B, E, E.4 | 6, only if B/E and the model identify a condition with >= 15 % gain |
| D | end-to-end on GPUs: TTFO, bind, 35 dB rejoin, coverage for full / cold / reuse / aware / pre-positioned / (dynamic if kept) | GPU, 4 hosts | A, B, E | 7 |

Physical runs have at most three candidate destinations / three dissemination targets (four hosts, one is the
source). Anything with 4-8 destinations is **model only** and labelled so.

## D. Analytical predictions

Common definitions. S = 1.61 GiB; T(x) = S / x; T_s = T(1 Gbps) = 14.05 s. **Post-move restoration latency T_r** =
time from the move event to the last fragment verified at the new owner (network level; the GPU equivalent is Sink
bound, which adds the bind step), including the measured ~0.3 s control plane. Every prediction below is T_r in this
sense unless it says "makespan" (= last T_r among sessions/destinations). All are **analytical** unless tagged.

### D.1 Pre-positioning (Experiment A), single session, source egress B_s, candidate ingress B_in = 1 Gbps

Candidates i = 1..k with probabilities p_1 >= p_2 >= ..., lookahead L s, budget b Sinks; x_i = fraction of the Sink at
candidate i when the move happens. Constraints: sum x_i <= min(b, L B_s / S) (budget and source egress); x_i <= L B_in / S
(each candidate's ingress). If the true destination is d: T_r = (1 - x_d) T_s + 0.3 (ingress-bound; the source is
idle after the move in the single-session case).
- Expected T_r = T_s (1 - sum p_i x_i) + 0.3 is linear in x: the optimum is a corner, **fill the top-1 candidate
  first**. Spreading can lower the mean only when the top candidate's ingress constraint binds before the source budget
  does (B_s > B_in, e.g. a native 9.4 Gbps source with 1 Gbps edges): then every candidate can be filled in parallel.
  With B_s = B_in = 1 Gbps, top-1 is optimal for the mean at every budget.
- Reference condition p = (0.6, 0.3, 0.1), L = 10 s, b = 1, 1 Gbps everywhere: pre-sendable 0.71 Sink.

  Tail metric: the miss probability P(T_r > tau) over destination draws with tau = 7.5 s (about half of T_s); it is
  robust to the percentile convention at 30 draws, which p90 is not.

| policy | x | T_r if d = B / C / D | mean T_r | P(T_r > 7.5 s) |
|---|---|---|---|---|
| none | 0 / 0 / 0 | 14.35 each | 14.35 | 1.0 |
| oracle | 0.71 at the true d | 4.4 | 4.4 | 0 |
| top-1 | 0.71 / 0 / 0 | 4.4 / 14.35 / 14.35 | 8.4 | 0.4 |
| proportional | 0.43 / 0.21 / 0.07 | 8.3 / 11.4 / 13.4 | 9.8 | 1.0 |
| tail coverage (tau = 7.5 s needs x >= 0.49 per candidate) | 0.5 / 0.21 / 0 | 7.3 / 11.4 / 14.35 | 9.2 | 0.4 (only B covered) |

  Top-1 beats proportional by 1.4 s in the mean; at L = 10 s nothing can cover two candidates, so no policy improves
  the tail over top-1.
  Allocation policies, all under the same constraints (budget, source egress over L, per-candidate ingress over L):
  **top-1-only** (everything to the most likely candidate, up to its cap; leftover budget unused), **probability-ordered
  greedy** (fill candidates in probability order until the budget is spent: the LP optimum for the mean),
  **probability-proportional** (x_i = min(b p_i, cap)), **tail coverage** (give every candidate 1 - tau / T_s in
  probability order, then greedy with the rest), plus none and oracle. At L = 10 s, 1 Gbps, greedy = top-1-only (the
  0.71 Sink the source can send fits one candidate).
- Condition L = 20 s, b = 2, 1 Gbps (pre-sendable 1.42 Sinks, per-candidate cap 1.0): top-1-only (1, 0, 0): T_r 0.3 /
  14.35 / 14.35, mean 5.9, miss 0.4; greedy (1, 0.42, 0): 0.3 / 8.45 / 14.35, mean 4.2, miss 0.4; proportional (0.85,
  0.43, 0.14): 2.4 / 8.3 / 12.4, mean 5.2, miss 0.4; coverage (0.5, 0.5, 0.42): 7.3 / 7.3 / 8.45, mean 7.4, miss 0.1.
  **Predicted trade-off: coverage cuts the miss probability from 0.4 to 0.1 and raises the mean by 3.2 s over greedy.**
- Fast source (native 9.4 Gbps, 1 Gbps edges), L = 10 s, b = 2: the source could send 6.7 Sinks in L, so the budget
  (2) and each candidate's ingress cap (0.71) bind. top-1-only (0.71, 0, 0): mean 8.4, miss 0.4; greedy (0.71, 0.71,
  0.58): T_r 4.4 / 4.4 / 6.2, mean 4.6, miss 0; proportional (0.71, 0.6, 0.2): 4.4 / 5.9 / 11.5, mean 5.6, miss 0.1;
  coverage: after 0.5 each the remainder goes greedily -> (0.71, 0.71, 0.58), identical to greedy. So under a fast
  source the optimal allocation does spread, but it is the probability-ordered greedy, not proportional or coverage;
  the v1/v2 claim that "spreading beats top-1" compared different conditions and is withdrawn. Predictions: greedy
  beats top-1-only by 3.8 s when B_s > B_in and by 0 when B_s = B_in (ingress-limit effect); proportional and coverage
  never beat greedy in the mean in any condition here.
- H5d: pre-positioning x Sinks for one session while N - 1 others restore through the same source delays their
  makespan by x S / B_s (7.0 s for x = 0.5 at 1 Gbps) in the source-bound regime and by ~0 when the source is idle.

### D.1b Value of fragments pre-positioned at a non-chosen candidate (H5e, explicit cost model)

After the move to d, the session's Sink is split: fraction x verified at holder h (the wrong candidate), 1 - x only at
the source A. A serves N sessions (rate B_s / N per session when busy), h forwards at egress B_h, d receives at B_in;
the two flows into d share B_in max-min. Under fixed reuse (h forwards all of x, A sends 1 - x):

    T_r = max( (1 - x) S / r_A,  x S / r_h ) + 0.3,   r_A = min(B_s / N, B_in), r_h = min(B_h, B_in - r_A)
    (r_A, r_h = the two flows' max-min shares of d's ingress)

and under the aware rule a fraction y of x is moved back to A so that the two finish together. Compared with the same
x at the correct destination (T_r = (1 - x) S / min(B_s / N, B_in) + 0.3):

| regime (x = 0.5) | correct-destination bytes | wrong-destination bytes, fixed | wrong-destination bytes, aware | none |
|---|---|---|---|---|
| N = 1, B_h = 1 Gbps (ingress-bound) | 7.3 s | 14.35 s (both flows share d's ingress: S / B_in) | 14.35 s | 14.35 s |
| N = 4, B_h = 1 Gbps (source-bound) | 28.4 s | 28.4 s (A 28.1 s in parallel with h 9.4 s at 750 Mbps) | 28.4 s | 56.5 s |
| N = 4, B_h = 125 Mbps (slow holder) | 28.4 s | 56.5 s (h needs 56.2 s) | 37.8 s (y = 0.167: A sends 0.667 S at 250 Mbps) | 56.5 s |
| N = 4, B_h = 62.5 Mbps | 28.4 s | 112.7 s (worse than none) | 45.3 s (y = 0.3) | 56.5 s |

So a wrongly placed fragment is worth as much as a correctly placed one only when the source is shared **and** the
holder's egress is at least x B_s / (N (1 - x)) (250 Mbps here); it is worth nothing when the ingress binds (N = 1),
and under fixed forwarding it can be harmful when the holder is slow. The aware rule recovers part of the value by
moving fragments back to the source. H5e (revised wording): *speculatively transferred fragments can retain
restoration value after incorrect destination predictions, but their benefit depends on holder forwarding capacity
and shared network bottlenecks*; the table is the pre-registered prediction of that dependence.

### D.2 Static topologies (Experiment B): one source A, three destinations B, C, D each needing the whole Sink

Assumptions of the closed forms (they define the scope of every statement in this subsection): per-node full-duplex
caps (egress B_s at A, B_f at B/C/D, ingress B_in at B/C/D), no per-link limits, max-min sharing, perfect pipelining
(a forwarder re-sends a fragment as soon as it is verified), fragment granularity and control-plane time ignored
(+0.3 s per plan, +0.03 s per hop at 1 Gbps), the source splits fragments into disjoint thirds for the multipath plan,
no duplicates. The four plans are specific implementations, not families: a different tree (e.g. A->{B}, B->C, C->D is
the line; A->{B,C}, B->D is another tree) or a different multipath partition gives different numbers.

| plan | per-destination completion |
|---|---|
| Star A->{B,C,D} | all at T(B_s / 3) = 3 T(B_s): 42.2 s at 1 Gbps; 168.6 s at B_s = 250 Mbps; 6.2 s native source |
| Pipelined line A->B->C->D | B: T(min(B_s, B_in)); C, D: T(min(B_s, B_f, B_in)) + one fragment lag per hop: 14.1 / 14.4 / 14.7 s uniform; 112.4 s for C and D at B_f = 125 |
| Tree A->B->{C,D} | B: T(B_s); C, D: T(min(B_f / 2, B_s, B_in)): 28.1 s uniform; 56.2 s at B_f = 250; 224.8 s at B_f = 125; 28.1 s with a native source |
| Disjoint multipath (A sends third i to node i; each node forwards its third to both peers) | max( T(B_s), (2/3) T(B_f), T(B_in) ) + lag: 14.1 s uniform; 18.7 s at B_f = 500; 37.5 s at B_f = 250; 74.9 s at B_f = 125; with a native source and B_f = 1 Gbps: (2/3) T_s = 9.4 s |

Predicted optimal regions **under these assumptions** (B_in = 1 Gbps unless stated):
- uniform 1 Gbps: line = multipath (ingress-bound, 14.1 s); tree 28.1; star 42.2;
- B_s = 250 Mbps: every forwarding plan ~56.5 s vs star 168.6 s (forwarding offloads the source, H6b);
- 222 < B_f < 1000 Mbps: multipath ((2/3) T(B_f)) < line (T(B_f)) < tree (2 T(B_f)); star 42.2 fixed;
- B_f < ~222 Mbps: star beats all forwarding plans (the Step 2 crossover in another guise);
- native source, B_f = 1 Gbps: star 6.2 s < multipath 9.4 s < line 14.1 s < tree 28.1 s;
- B_f >= B_in with one provider saturating the ingress: multipath adds nothing over line (H6e, predicted 0).
Where this comparison does NOT hold: with per-link caps (e.g. B->C slow while B->D fast) a tree that avoids the slow
link can beat a multipath plan that uses it; with per-destination deadlines a tree can prioritize one child; multipath
runs 3 x as many flows (more control-plane scheduling, 3 providers sharing each ingress) and its disjoint placement must
be decided by the source in advance; if holders already hold overlapping sets, multipath must avoid duplicates. These
are the reasons the Butterfly-vs-Tree ordering is a hypothesis (H6d) to measure, not a result.
**Rule prediction (H6f):** a per-(fragment, destination) assignment to the provider with the smallest backlog / egress
cap should produce star-like plans at small B_f, multipath-like plans when peers hold disjoint fragments and B_f is
moderate, and the ingress bound when everything is uniform, i.e. match the best fixed plan within ~10 % in every
condition of the grid. Where it falls short tells us what a reconfiguration mechanism must add.

### D.3 Experiment E: topologies under execution mobility A -> B -> C -> D (incomplete restoration at B and C)

Setting: single session (and N = 4 sessions as a second condition), rho = 2 (T_m = 7.02 s; each intermediate owner
receives about half a Sink before being left at 1 Gbps), per-node caps as in B. Policies (all keep verified fragments
except restart; they differ in who may forward to the current owner):

| policy | providers for the current owner |
|---|---|
| restart | source only; progress at abandoned owners is discarded (Phase 1 policy) |
| progress-preserving star | source only; every node keeps the verified fragments it holds, and an owner receives from the source only what it lacks. **On A->B->C->D without revisits this has the same completion times as restart** (each owner is new and holds nothing); it differs only when an owner is revisited, so E includes the revisit path A->B->C->D->B (rho = 2, four moves), where B already holds ~0.5 Sink from its first ownership. Its byte accounting also differs from restart's (nothing is discarded, so B's fragments count as reusable, not unused) |
| fixed line | progress-aware forwarding restricted to the immediately previous owner, which forwards what it holds (pipelined); the source sends the rest |
| fixed tree | the first intermediate owner B is the forwarding hub for every later owner (A->B; B->C; B->D); the source sends what B lacks |
| fixed butterfly-like | every past holder forwards, disjoint fragment sets split evenly by count among the holders of each fragment; the source sends the rest |
| OTTER dynamic | backlog-aware provider selection over all holders and the source, re-planned at every move AND on capacity changes / periodically with hysteresis (proposed, E.4) |
| aware at moves only | the same rule re-planned at moves only (Step 2 policy generalized; the baseline dynamic morphing must beat) |

Three groups, to be kept apart in every figure: (1) no preservation: restart; (2) preservation without forwarding:
progress-preserving star; (3) progress-aware forwarding: line, tree, butterfly-like, aware-at-moves, dynamic.
Analytical predictions for the final owner D at 1 Gbps uniform, single session: every policy is ingress-bound at D
(T_r = 14.35 s, Phase 1 measured 14.8-15.4 s for all non-oracle policies) -> E is uninformative in the uniform case and
is run only in conditions where it is not (plus the revisit path, where star and restart separate: at the fourth move
B holds ~0.5 Sink, so star's T_r at B is ~7.3 s against restart's 14.35 s at 1 Gbps):
- B slow (B_f(B) = 125 Mbps), C and D at 1 Gbps, single session: at the move to C, B holds ~0.5 S. Line: B forwards
  0.5 S at 125 Mbps -> 56.5 s; star: 14.35 s; tree: same as line (B is the hub); butterfly: B is the only holder -> as
  line; aware/dynamic: moves fragments to the source -> ~14.35 s. At the move to D: C holds whatever it received (~0.5 S
  for star/aware), B ~0.57 S (it kept receiving): line (C forwards) 7.3 s + source 7.0 s in parallel -> 14.35 s;
  tree (B forwards at 125 Mbps) ~56.5 s; butterfly (B and C split their common fragments) worse than line because half
  of C's fragments go through B; aware: 14.35 s. Predicted order at D: aware = line = star < butterfly < tree.
- Source shared by N = 4 sessions, all forwarders 1 Gbps: star = restart-like source load; line/butterfly/aware offload
  the source (Scenario B measured 7.6-10.2 s gains); tree concentrates forwarding at B (B's egress shared by 3 later
  owners x 4 sessions) -> predicted worst among reuse policies.
- Mid-run drop of C's egress to 62.5 Mbps while D is being restored from C (dynamic trigger): aware-at-moves keeps
  the plan (C's remaining 0.3 S at 62.5 Mbps -> 67 s); dynamic re-plans to A/B (~7 s + 0.3 s + one 4 MiB fragment
  drain at 62.5 Mbps = 0.5 s). This is the one condition in E where dynamic morphing is predicted to beat the
  moves-only rule by a large margin; the gain is bounded by (remaining bytes at the degraded holder) / (new rate).
These are the conditions E will use; the full numbers come from the extended model before the run.

### D.4 Dynamic re-planning (Experiment C)

Switching cost measured in Phase 1: 0.28-0.32 s control plane + one in-flight fragment per cancelled flow (4 MiB:
0.03 s at 1 Gbps, 0.5 s at 62.5 Mbps). Re-planning pays when the remaining transfer under the old plan exceeds that by
a margin; the only scenarios where that margin is large are mid-restoration slow-downs of a forwarder (C2, and the
E condition above). A deadline change at C in A->B->C cannot be helped by adding A->C unless A's egress has slack.
C is built only if B/E and the model identify a condition with >= 15 % gain over "aware at moves only".

## E. Required implementation changes (minimum per hypothesis; none started)

Network harness (`restore_*`):
1. **Pre-positioning phase** (A): per session, a window of L s before the move during which an allocation policy sends
   fragments to candidates (none / oracle / top-1 / proportional / tail-coverage / all-affordable); the true
   destination is drawn from a seeded distribution (calibrated, or a different one for miscalibration); `holders` =
   every node holding verified fragments, not only past owners. ~80 lines orchestrator.
2. **FLOW_ADD** in `restore_node.py` (append fragments to a running flow, as the GPU harness has) so forwarders can
   pipeline. ~30 lines.
3. **Dissemination mode + fixed plans** (B, E): a session with a destination set (each needing the whole Sink,
   optional deadlines); plans star / line / tree / disjoint multipath; the aware rule generalized to (fragment,
   destination) pairs with any holder as provider; the E policy set (fixed hub tree, even-split butterfly). ~200 lines.
4. **Time-varying caps, deadlines, event-driven re-plan with hysteresis, switching-cost accounting** (E dynamic, C):
   a schedule of cap changes applied through `realloc`; re-plan triggers; deadline-miss and re-plan counters. ~120 lines.
5. **Ingress-aware correction** (H4c): implemented as a new policy `reuse_aware_in` (the Step 2 policy `reuse_aware`
   is kept unchanged so the Step 2 data keep their meaning): a held fragment moves to the source only if its best
   holder's estimate exceeds both the source's estimate and the owner's ingress bound (bytes headed to the owner /
   its ingress cap). Implemented in `restore_orchestrate.py` and `restore_model.py`; loopback-checked (N = 1, holder at
   half the link: source bytes 1.12 -> 1.00 at equal makespan). Validation on the testbed: the 15 Step 2 configurations
   with `reuse_aware_in` (experiment `restore_holder_h4c`, 45 runs, ~45 min), judged against this **model** table
   (written before the run):

```
 N   B_h |      reuse_fixed      reuse_aware   reuse_aware_in   (makespan s / source Sinks per session)
 1    62 |      119.3 /1.00       20.9 /1.45       20.9 /1.45
 1   125 |       63.2 /1.00       20.9 /1.40       20.9 /1.39
 1   250 |       35.1 /1.00       20.9 /1.31       20.9 /1.26
 1   500 |       21.1 /1.00       20.9 /1.18       20.9 /1.01
 1  1000 |       20.9 /1.00       20.9 /1.01       20.9 /1.00
 2    62 |       92.7 /1.00       33.8 /1.21       33.7 /1.21
 2   125 |       50.8 /1.00       31.6 /1.12       31.3 /1.11
 2   250 |       29.9 /1.00       28.9 /1.01       28.9 /1.01
 2   500 |       28.9 /1.00       28.9 /1.00       28.9 /1.00
 2  1000 |       28.9 /1.00       28.9 /1.00       28.9 /1.00
 4    62 |       83.8 /1.00       57.2 /1.03       57.2 /1.03
 4   125 |       55.4 /1.00       55.4 /1.00       55.4 /1.00
 4   250 |       55.4 /1.00       55.4 /1.00       55.4 /1.00
 4   500 |       55.4 /1.00       55.4 /1.00       55.4 /1.00
 4  1000 |       55.4 /1.00       55.4 /1.00       55.4 /1.00
```

   Step 1 passes if every `reuse_aware_in` median is within 1 s and 0.05 Sink of the table, (1, 500) sends <= 1.02
   Sinks per session, and no condition's makespan is worse than Step 2's `reuse_aware` by > 1 s; the H4a/H4b verdicts
   are re-evaluated with `reuse_aware_in` in place of `reuse_aware` and must still hold.
Fluid model: extend with 1, 3, 4 (the same planning code) to tabulate predictions before each run.
GPU harness (D): port `reuse_aware`, the pre-positioning policy and (if kept) the dynamic rule to
`mobility_orchestrate.plan`; add full-state migration and cold restart as execution policies. ~250 lines.
Per-link capacity matrix: only if B/E results show a per-link effect matters; skipped by default.

## F. Proposed pre-registered criteria (frozen on approval; medians unless stated; T_r as defined in D)

Experiment A (network level, 1 Gbps caps unless stated; 10 seeded destination draws x 3 reps per condition):
- H5a supported if, at p = (0.6, 0.3, 0.1), L = 10 s, b = 1, top-1's mean T_r <= 0.75 x none's (analytical 8.4 vs
  14.35 s) and the oracle's <= 0.35 x (4.4 s).
- H5b-mean supported at a condition if proportional or tail-coverage beats probability-ordered greedy's mean T_r by
  >= 1 s under identical constraints. Predicted: rejected everywhere (greedy is the LP optimum; analytical margins
  greedy over proportional 1.4 s at 1 Gbps / L = 10, 1.0 s at L = 20, 1.0 s native source).
- H5b-ingress supported if greedy beats top-1-only's mean T_r by >= 1 s with a native-speed source at L = 10 s, b = 2
  (analytical 4.6 vs 8.4 s) and by < 1 s at 1 Gbps (identical allocations): the per-candidate ingress limit, not
  prediction uncertainty, is what makes spreading pay.
- H5b-tail supported if, at L = 20 s, b = 2, 1 Gbps, tail-coverage's miss probability P(T_r > 7.5 s) over the 30 draws
  is lower than greedy's by >= 0.2 (analytical 0.1 vs 0.4); its mean penalty is reported (analytical +3.2 s) and is
  part of the result, not a pass condition.
- H5c (accounting identity): bytes at non-chosen candidates + bytes at the chosen one <= budget in every run; a
  violation is a harness bug, not a result.
- H5d supported if, with N = 4 sessions sharing the source, pre-positioning 0.5 Sink for one session raises the
  others' makespan by >= 3.5 s (analytical 7.0 s), and by < 1 s when the source is otherwise idle.
- H5e supported if the D.1b table is reproduced in rank order: at N = 4 with B_h = 1 Gbps a wrongly placed 0.5 Sink
  reduces T_r by >= 0.5 T_s relative to none (analytical 28 s); at N = 1 by < 1 s; at N = 4 with B_h = 125 Mbps fixed
  forwarding reduces it by < 1 s while aware reduces it by >= 0.5 T_s (analytical 18.7 s).
Experiment B (network level, three destinations; 3 reps; model table committed before the run):
- H6a supported if the best fixed plan differs across {uniform; B_s = 250; B_f = 125; B_f = 500; native source}
  (predicted line/multipath; any forwarding; star; multipath; star).
- H6b supported if at B_s = 250 every forwarding plan's makespan <= 0.5 x star's (analytical 56.5 vs 168.6).
- H6c supported if at B_f = 125 line's and tree's last-destination completion >= 2 x star's (112 / 225 vs 42).
- H6d supported if at B_f = 500 the disjoint-multipath plan's makespan <= 0.75 x line's (analytical 18.7 vs 28.1) and
  <= 0.5 x the hub tree's (56.2); rejected at a condition if multipath is worse than tree by > 1 s there (the
  overheads listed in D.2 would then be real).
- H6e supported if at uniform 1 Gbps multipath is within 1 s of line.
- H6f supported if the generalized aware rule's makespan is within 10 % of the best fixed plan in every condition;
  rejected if > 25 % worse in any (that condition becomes the target for reconfiguration).
Experiment E (network level; single session and N = 4; 3 reps; conditions of D.3):
- H8a supported if, in the slow-B condition, aware-at-moves' T_r at D is <= 0.75 x the best fixed forwarding plan's
  (line/tree/butterfly) and within 1 s of star's; rejected if any fixed plan beats aware by > 1 s.
- H8b (dynamic value) supported if, in the mid-run C-degradation condition, the dynamic rule's T_r at D is <= 0.5 x
  aware-at-moves' with <= 2 re-plans and no run worse than aware-at-moves by > 1 s in any other E condition; if H8b
  fails, dynamic morphing is dropped and M3 is reported as provider selection at moves.
- H8c (traffic efficiency) is judged on the latency-traffic Pareto frontier, not on a fixed cap: for every E condition
  the per-policy (T_r at D, source bytes per session, aggregate bytes, redundant bytes) tuples are reported and the
  Pareto-efficient set identified. Supported if, in the shared-source and revisit conditions, every progress-aware
  policy sends fewer source bytes per session than restart by >= 0.25 Sink (analytical: restart ~2.0 Sinks at rho = 2
  as in Phase 1, forwarding policies ~1.0-1.3) AND no progress-aware policy is Pareto-dominated by restart. Source
  retransmission by a progress-aware policy is not a failure when the policy's T_r is lower than that of every policy
  with fewer source bytes (it is then on the frontier, as the Step 2 aware policy was).
Experiment C: only if H8b holds or the model finds another >= 15 % condition; criteria written then.
Validity for every network run: all fragments verified; paced egress within 1.05 x cap over 10 s; NIC peaks within
1.15 x cap; four distinct hosts; invalid runs listed and re-run, never dropped.

## G. Pilots (each inspected before its sweep; go/no-go stated)

| step | pilot | runs | go if |
|---|---|---|---|
| 1 | H4c fix (`reuse_aware_in`) on the 15 Step 2 configurations | 45 (~45 min) | every median within 1 s / 0.05 Sink of the E.5 model table; (1, 500) <= 1.02 Sinks; H4a/H4b still hold with `reuse_aware_in` |
| 2 | A-pilot: k = 3, p = (0.6, 0.3, 0.1), L = 10, b = 1, none / oracle / top-1 / proportional, 3 draws, N = 1 | 12 (~8 min) | per-candidate bytes and T_r within 1 s of D.1; pre-positioned fragments at non-chosen candidates are forwarded (H5e path exercised) |
| 3 | B-pilot: uniform 1 Gbps, star / line / tree / multipath / rule, 1 rep | 5 (~6 min) | line and multipath within 1 s of 14.1 s, tree within 1 s of 28.1, star within 1 s of 42.2 |
| 6 | E/C-pilot: slow-B and C-degradation conditions, aware-at-moves vs dynamic, 1 rep | 4 | model and run within 1 s; dynamic's re-plan count <= 2 |

## G.1 Pre-run model tables (added before each run; thresholds in F and G unchanged)

A-pilot (Step 2 of H): session s0 executes at A; candidates B, C, D with p = (0.6, 0.3, 0.1); L = 10 s, b = 1 Sink,
1 Gbps caps; restoration policy `reuse_aware_in`; true destinations fixed to B, C, D (one draw each, so the
incorrect-prediction forwarding path is exercised for top-1 and proportional). Allocation definitions as implemented
(`restore_orchestrate.prepos_start`): deliverable per candidate = L x ingress / S; affordable = min(b, L x source
egress / S); top-1-only fills the most likely candidate; greedy fills candidates in probability order; proportional
gives each candidate p_i x affordable; coverage gives each candidate 1 - (tau - 0.3) / T_s in probability order then
greedy; fragment sets are disjoint across candidates. **Model** T_r per true destination (+0.3 s control plane):

```
pre-positioning, L=10 s, b=1 Sinks, probs [0.6, 0.3, 0.1], restore policy reuse_aware_in, +0.3 s control plane
      policy | T_r d=B T_r d=C T_r d=D |  mean  miss(>tau)  alloc
-- N=1, holder egress 1000 Mbps
        none |    14.14    14.14    14.14 | 14.14  1.00  B:0.00 C:0.00 D:0.00
      oracle |     4.14     4.14     4.14 |  4.14  0.00  B:0.00 C:0.00 D:0.72
        top1 |     4.14    14.14    14.14 |  8.14  0.40  B:0.72 C:0.00 D:0.00
      greedy |     4.14    14.14    14.14 |  8.14  0.40  B:0.72 C:0.00 D:0.00
proportional |     8.18    11.12    13.12 |  9.56  1.00  B:0.43 C:0.22 D:0.07
    coverage |     7.54    10.74    14.14 |  9.16  1.00  B:0.48 C:0.25 D:0.00
```

Expected pilot outcomes: none 14.1 s everywhere; oracle 4.1 s; top-1 4.1 s at B and 14.1 s at C and D **with the whole
0.72 Sink at B forwarded to the destination by B as a never-owner holder** (T_r unchanged because the ingress binds;
this is the forwarding-path check, not a latency claim); proportional 8.2 / 11.1 / 13.1 s with 0.29 / 0.50 / 0.65 Sink
forwarded by the non-chosen candidates. Source bytes exactly 1.00 Sink in every run (pre-positioned fragments are
never resent). Loopback check at 1/27 scale (64 MiB Sink, 100 Mbps) reproduced every one of these within 0.1 s
scaled, see `restore_prepos_pilot_notes.md` once the testbed run exists.

A3 (approved after the pilot; arrangement fixed here before the run, thresholds in F unchanged). The frozen H5d and
H5e clauses assume two different timings, both consistent with their text and with D.1b: **H5d** (interference) needs
the other sessions to be restoring while s0 pre-positions, so they start at t0 (`--others_start 0`); **H5e** (value of
wrongly placed fragments) needs the 0.5 Sink to have landed before contention starts, so the others start at s0's move
(`--others_start 10`, = L). Under contention a pre-positioning flow gets only the 4-way share (250 Mbps), so with
others active only ~0.18 Sink lands in L = 10 s; the model accounts for this. Grid (3 reps each, L = 10 s, b = 0.5,
p = 0.6/0.3/0.1, restoration `reuse_aware_in` unless stated; experiment `restore_prepos_a3`, 30 runs, ~40 min):
H5d: N = 4, others at t0, {none, top-1 -> B}; H5e: N = 4, others at L, 1 Gbps holders, {none -> C, top-1 -> C};
N = 1, {none -> C, top-1 -> C}; N = 4, others at L, 125 Mbps holders, {reuse_fixed, reuse_aware_in} x {none -> C,
top-1 -> C}. The "source otherwise idle" clause of H5d is read from the others-at-L runs (the pre-positioning has ended
before they start). **Model** predictions (+0.3 s control plane):

```
A3 model table (L = 10 s, p = 0.6/0.3/0.1, restoration reuse_aware_in unless stated, +0.3 s control plane)
H5d arrangement: others start at t0 (active during pre-positioning); N = 4, holders 1 Gbps
  b=0     none->B: T_r   45.7  others_makespan   52.3  held@move 1.00 (B 1.00 C 0.00)  source 4.01 S
  b=0.5   top1->B: T_r   32.4  others_makespan   55.7  held@move 1.00 (B 1.00 C 0.00)  source 4.01 S
  b=0.5   top1->C: T_r   45.7  others_makespan   55.7  held@move 1.18 (B 0.18 C 1.00)  source 4.01 S
  b=1     top1->B: T_r   34.2  others_makespan   55.7  held@move 1.00 (B 1.00 C 0.00)  source 4.01 S
H5e arrangement: others start at s0's move (L); N = 4, holders 1 Gbps
  b=0     none->C: T_r   55.6  others_makespan   65.7  held@move 1.00 (B 0.00 C 1.00)  source 4.01 S
  b=0.5   top1->C: T_r   28.0  others_makespan   58.8  held@move 1.50 (B 0.50 C 1.00)  source 4.01 S
  b=0.5   top1->B: T_r   28.0  others_makespan   58.8  held@move 1.00 (B 1.00 C 0.00)  source 4.01 S
  b=0.5  oracle->C: T_r   28.0  others_makespan   58.8  held@move 1.00 (B 0.00 C 1.00)  source 4.01 S
H5e, N = 1 (no others)
  b=0     none->C: T_r   14.1  others_makespan   None  held@move 1.00 (B 0.00 C 1.00)  source 1.00 S
  b=0.5   top1->C: T_r   14.1  others_makespan   None  held@move 1.50 (B 0.50 C 1.00)  source 1.00 S
  b=0.5   top1->B: T_r    7.2  others_makespan   None  held@move 1.00 (B 1.00 C 0.00)  source 1.00 S
H5e, N = 4, holders 125 Mbps, others start at L
     reuse_fixed b=0     none->C: T_r   55.6  others_makespan   65.7  held@move 1.00 (B 0.00 C 1.00)  source 4.01 S
     reuse_fixed b=0.5   top1->C: T_r   80.0  others_makespan   71.5  held@move 1.50 (B 0.50 C 1.00)  source 4.01 S
  reuse_aware_in b=0     none->C: T_r   55.6  others_makespan   65.7  held@move 1.00 (B 0.00 C 1.00)  source 4.01 S
  reuse_aware_in b=0.5   top1->C: T_r   48.8  others_makespan   64.0  held@move 1.50 (B 0.50 C 1.00)  source 4.39 S
```

Model-implied verdicts, written before the run: H5d main clause +3.4 s against a 3.5 s threshold (**borderline FAIL
predicted**: the frozen analytic 7.0 s counted the whole 0.5 Sink as extra source work, but only 0.18 Sink leaves the
source during L under the 4-way share and s0's post-move work shrinks by the same amount, so the net delay to the others
is the share they lose during [0, L]); H5d idle clause: others finish 6.9 s *earlier* (pass); H5e N = 4, 1 Gbps:
55.6 -> 28.0 s, gain 27.6 s (pass; D.1b predicted 28 s); H5e N = 1: 14.1 vs 14.1 (pass); H5e slow holder: fixed
55.6 -> 80.0 s, worse (pass of the "< 1 s reduction" clause); aware_in 55.6 -> 48.8 s, 6.8 s against a 7.0 s threshold
(**borderline FAIL predicted**; D.1b's 18.7 s ignored the other sessions' own moves and the shrinking source share).
Whatever the run shows is judged against the frozen thresholds; the borderline cases are reported as such.

## H. Execution order and I. costs (network runs 0.5-2 min; GPU runs 2-3 min)

| step | work | runs | wall |
|---|---|---|---|
| 0 | model correction (this document) + model extension for A/B/E; prediction tables committed | 0 | - |
| 1 | H4c correction + re-validation | 45 | ~45 min |
| 2 | A-pilot | 12 | ~8 min |
| 3 | B-pilot (needs E.2, E.3) | 5 | ~6 min |
| 4 | A sweep: A1 b in {0, 0.5, 1, 2} x L in {2, 5, 10, 20} x 5 policies x 10 draws (~25 s each); A2 top-1 probability {0.4, 0.6, 0.8, 1.0} x calibrated / miscalibrated x 3 policies x 10 draws; A3 N = 4, b in {0, 0.5, 1} x 3 draws x 3 reps (H5d, H5e) | 800 + 240 + 27 | ~8.5 h; A1 can be cut to the 8 (b, L) cells the pilot shows to be non-degenerate |
| 5 | B sweep: 4 plans + rule x {uniform, B_s 250, B_s 500, B_f 125, B_f 500, native B_in, native B_s} x 3 reps | 105 | ~2 h |
| 5b | E sweep: 7 policies x {slow B, N = 4 shared source, C degradation} x 3 reps (+ single/N = 4) | 63-126 | ~2-3 h |
| 6 | C, only if H8b or the model justifies it | ~18 | ~0.3 h |
| 7 | D (GPU): 6-7 policies x {slow, fast, repeated} x 3 reps | 54-63 | ~3-4 h with all four GPUs free |
Model sweeps (8 destinations, finer grids) are free and precede every step.

## J. Risks and likely negative results

- A: H5b-mean is predicted rejected at 1 Gbps (linear objective); the tail gain (miss probability 0.4 -> 0.1) costs
  3.2 s of mean. Calibration is synthetic (destinations drawn from a stated distribution): the paper must not claim a
  predictor.
- B: at uniform capacities all forwarding plans collapse onto the ingress bound; the content is the crossover map,
  which the testbed confirms at 7 points. Multipath's overheads (3 x flows, shared ingress, placement) may erase its
  predicted 18.7 vs 28.1 s advantage at B_f = 500; that would reject H6d and favour the simpler plans.
- E: in the uniform condition every policy ties at D (Phase 1); E's content lives entirely in the heterogeneous and
  shared-source conditions. If aware-at-moves matches the dynamic rule everywhere except the artificial C-degradation
  case, M3 reduces to provider selection at moves.
- C: built only on evidence from B/E; likely dropped.
- D: PSNR rejoin adds a constant ~4 s after bind that no topology changes; TTFO is ~0.7 s for every OTTER variant;
  end-to-end differences will be in bind time and coverage only.
- Measurement: every new harness feature gets a loopback test at the real 412-fragment ratio before the testbed
  (Scenario B v1 was invalidated by exactly such defects).

## Critical assessment (revised)

1. **What is validated:** progress preservation (Phase 1, Scenario B) and backlog-aware provider selection into one
   destination (Step 2). **What is not:** multi-destination dissemination, forwarding among non-owners, and
   reconfiguration triggered by anything other than a move. M3 therefore stays provisional; Experiments B and E are
   designed to decide it, with "aware at moves only" as the baseline any reconfiguration mechanism must beat (H8b).
2. **Butterfly vs tree:** under the D.2 assumptions the disjoint-multipath plan is never slower than the hub tree,
   but that statement covers two specific implementations with full-duplex per-node caps, perfect pipelining and
   disjoint placement; with per-link limits, deadlines, overlapping holdings or control overheads the order can
   change. H6d is a hypothesis to measure, and its rejection (multipath worse than tree at B_f = 500) is a possible
   and reportable outcome.
3. **Dynamic adaptation:** the switching cost is small (0.3 s + one fragment), so the question is whether conditions
   change within a restoration (14-56 s). The predicted large gains are confined to mid-restoration forwarder
   degradation; E includes that condition explicitly so that the answer is measured rather than assumed.
4. **Pre-positioning vs routing:** routing adaptation is worth 12-13 % in narrow regimes and 0 at the ingress bound;
   pre-positioning is the only lever on the ingress bound itself (Phase 1 oracle 14.8 -> 0.7-11.4 s) and H5e ties it to
   reuse under source sharing, with the explicit caveat that wrongly placed bytes are valuable only when the holder
   can forward fast enough. It remains the more promising latency contribution, with a synthetic predictor.
5. **Simplest defensible contribution today:** M1 (execution ahead of the Sink, measured) + progress-preserving,
   bottleneck-aware restoration (measured). Whether M3 is "topology morphing" or "provider selection at moves plus
   budgeted pre-positioning" is decided by H8b and H6f, not by this document.
