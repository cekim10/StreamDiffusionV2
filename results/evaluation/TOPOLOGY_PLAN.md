# OTTER M3 research plan: pre-positioning, transfer topologies, dynamic re-planning (DRAFT for review, 2026-10-15)

Status: audit + experimental design. Nothing in this document has been run. Criteria in sections F are proposals;
they become pre-registered at the commit that follows the user's approval, and are not edited after that.
Every number is tagged: **measured** (committed artifact), **analytical** (closed-form from link capacities, not a
run), **proposed** (mechanism not implemented), or **model** (fluid simulation `tools/eval/restore_model.py`).

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
   it becomes the owner. At 1 Gbps that is 14.05 s for a whole Sink, regardless of where the bytes come from.
   Phase 1 measured exactly this for every non-oracle policy.
2. **Source-sharing bound.** When one source serves N sessions, the source must send at least what no holder has;
   fixed reuse makes that exactly one Sink per session (measured 1.00). Latency gains from routing exist only when the
   binding resource is a shared sender (source or slow holder), never when it is the receiver's ingress.

## B. Implementation status (inspected 2026-10-15)

| capability | GPU harness (`mobility_node.py`, `mobility_orchestrate.py`) | network harness (`restore_node.py`, `restore_orchestrate.py`) |
|---|---|---|
| policies | restart, relay, relay_pipe, split (= reuse_fixed), direct (perfect oracle, unlimited budget, from t = 0) | restart, reuse_fixed, reuse_adaptive, reuse_aware |
| fragment-level multi-provider delivery to ONE destination (several holders + source send disjoint fragment sets to the owner) | yes (split) | yes (fixed / adaptive / aware) |
| one session required at SEVERAL destinations at once (dissemination) | no: one owner per session; non-owners only receive as intermediate owners | no |
| forwarding between non-owners / pipelined forwarding of fragments as they arrive | relay_pipe only along the fixed chain (FLOW_ADD exists) | no FLOW_ADD; a flow's fragment list is fixed at start |
| topology change without discarding verified fragments | yes, at MOVES only: every reuse policy cancels obsolete flows, keeps held fragments, re-plans providers (= attach + reparent + prune at a move) | same |
| re-plan on other events (bandwidth change, deadline change, candidate-set change) | no | no (the plan runs only at start, move, flow_done) |
| pre-positioning to non-owners before a move | only the oracle (`direct`): final owner known, whole Sink, no budget | no; `holders` are derived from the ownership history, so fragments delivered to a never-owner would not be forwarded |
| per-node egress/ingress caps, max-min fair, token buckets, cap verification on the wire | yes | yes (+ paced-egress check per 10 s window) |
| per-LINK capacity matrix (A->D 250 while B->D 1000), time-varying caps | no | no (caps are per node and constant) |
| deadlines, deadline-miss accounting | no | no |
| time to 35 dB PSNR, bind, first output | yes | n/a (network level) |
| full-state migration / cold restart / replay as repeated-mobility baselines | single-handoff harness only | n/a |
| ingress-aware correction of `reuse_aware` (H4c fix) | not implemented | **not implemented** (sketched in `restore_holder_notes.md` only) |

Answers to the First Task questions 4-7: multi-destination dissemination: **not supported**; fragment-level multipath
forwarding: **supported into one destination** (several providers), **not** provider-to-provider or to several
destinations; reconfiguration without discarding verified fragments: **supported, triggered by moves only**;
pre-positioning: **only the perfect oracle**, no probabilities, budget, or lookahead.

## C. Remaining scientific questions and experiment matrix

| id | question | level | depends on | priority |
|---|---|---|---|---|
| A | Can bytes sent to likely destinations before a move cut post-move restoration latency, at what traffic cost, and when does spreading beat top-1? | network (model + 4 hosts), then 2-3 GPU points | nothing | 1 |
| B | Which transfer graph (star / pipelined line / tree / disjoint multipath) is optimal under which capacities when 3 destinations need one Sink, and does the backlog-aware rule reproduce the best one? | model (free, any size) + 4 hosts (1 source, 3 destinations) | dissemination mode | 2 |
| C | Does re-planning on bandwidth / deadline / candidate changes (not only moves) reduce deadline misses over "aware at moves only" by more than its switching cost? | network, 4 hosts | B, time-varying caps | 3, conditional on a model-predicted gain |
| D | End-to-end on GPUs: TTFO, bind, 35 dB rejoin, coverage for full / cold / reuse / aware / pre-positioned under slow, fast, repeated mobility | GPU, 4 hosts | A (and B/C if kept) | 4 |

The testbed has four hosts: one source + three others. Physical runs therefore have at most 3 candidate
destinations / 3 dissemination targets. Anything with 4-8 destinations is **model only** and is labelled so.

## D. Analytical predictions (closed-form; S = 1.61 GiB, T_s = 14.05 s at 1 Gbps; +0.3 s control plane per plan)

### D.1 Pre-positioning (Experiment A), single session, source egress B_s, candidate ingress B_in = 1 Gbps

Let the mover leave in L seconds; candidates i = 1..k with probabilities p_1 >= p_2 >= ...; x_i = fraction of the Sink
delivered to i before the move. Constraints: sum x_i <= min(b, L B_s / S) (budget, source egress); x_i <= L B_in / S
(each candidate's ingress). Post-move latency if the true destination is d: (1 - x_d) T_s (ingress-bound).
- Expected latency = T_s (1 - sum p_i x_i) is linear in x, so the optimum is a corner: **fill the top-1 candidate first**.
  Spreading can only lower the mean when the top candidate's ingress constraint binds before the source budget does,
  i.e. when B_s > B_in (fast source, e.g. native 9.4 Gbps vs 1 Gbps edges): then every candidate can be filled in
  parallel and "send to all affordable candidates" dominates. With B_s = B_in = 1 Gbps, top-1 is optimal for the mean
  at every budget (prediction: H5b REJECTED for the mean objective at 1 Gbps).
- Tail objective P(latency > tau): a candidate is "covered" if x_i >= 1 - tau / T_s; cover candidates in probability
  order with just that much each. With tau = 7 s (half of T_s) coverage costs 0.5 Sink per candidate, so at budget 1
  two candidates can be covered: P(miss) = p_3 (0.1) for coverage vs p_2 + p_3 (0.4) for top-1. (prediction: H5b
  SUPPORTED for the tail objective when b >= 2 (1 - tau/T_s) and L B_s / S allows it; at L = 10 s and 1 Gbps only
  0.71 Sink can leave the source, so tail coverage needs L >= 14 s or a faster source.)
- Numbers at (p = 0.6/0.3/0.1, L = 10 s, b = 1, 1 Gbps everywhere; pre-sendable 0.71 Sink): none 14.4 s; oracle
  4.4 s; top-1 mean 0.6 x 4.4 + 0.4 x 14.4 = 10.4 s, p90 14.4 s; proportional (x = 0.43 / 0.21 / 0.07) mean
  T_s (1 - 0.71 (0.36 + 0.09 + 0.01)) + 0.3 = 9.8 s, p90 ~13.4 s (proportional spreads the same 0.71 Sink, so its mean
  is close to top-1's; neither beats the other by the 1 s margin at 1 Gbps). At L = 20 s (1.42 Sinks sendable, b = 2):
  top-1 x_1 = 1 then x_2 = 0.42: mean 0.6 x 0.3 + 0.3 x 8.5 + 0.1 x 14.4 = 4.2 s; coverage with tau = 7 covers all three
  at 0.5 each (1.5 > 1.42: covers two fully, third partially): p90 ~ 7.3 s vs top-1 p90 8.5 s.
- **Wrong-destination bytes are not waste under source sharing.** With N sessions sharing the source, a session whose
  pre-positioned fraction x landed at a non-chosen candidate still restores in (1 - x) S / (B_s / N) + x S / B_h' where
  the candidate forwards at B_h': at N = 4, 1 Gbps, x = 0.5: 28 + 7 = 35 s (parallel: max(28, 7) = 28 s) vs 56 s
  with nothing pre-positioned. Under a single session (ingress-bound) the same bytes are worth 0 s. (prediction H5e,
  new: the value of a speculative byte is independent of where it lands when the source is the bottleneck and zero
  unless it lands at the destination when the ingress is the bottleneck.)
- H5d: pre-positioning x Sinks for one session delays the active restorations of the other N - 1 sessions by
  x T_s (source-bound regime) and by 0 s when the source is idle.

### D.2 Static topologies (Experiment B), one source A, three destinations B, C, D all needing the whole Sink

Per-node full-duplex caps: source egress B_s, forwarder egress B_f (B, C, D), destination ingress B_in. T(x) = S / x.
| topology | per-destination completion (analytical) |
|---|---|
| Star A->{B,C,D} | all at T(B_s / 3) = 3 T(B_s): 42.2 s at 1 Gbps; 168.6 s at 250 Mbps; 6.2 s native source |
| Pipelined line A->B->C->D | B: T(min(B_s, B_in)); C, D: + one fragment lag each (~0.05 s) if B_f >= the arrival rate, else T(B_f) + lag: 14.1 / 14.4 / 14.7 s uniform; 112.4 s for C, D at B_f = 125 |
| Tree A->B->{C,D} | B: T(B_s); C, D: T(min(B_f / 2, B_s)): 28.1 s uniform; 56.2 s at B_f = 250; 224.8 s at B_f = 125 |
| Disjoint multipath (A sends third i to node i; each node forwards its third to both peers) | each destination receives its own third from A at B_s / 3 and the other two thirds from the two peers at B_f / 2 each: completion = max(T(B_s), (2/3) S / B_f, S / B_in) = max(T_s, (2/3) T(B_f), T(B_in)): uniform 14.1 s + lag; B_f = 500: 18.7 s; B_f = 250: 37.5 s; B_f = 125: 74.9 s |

Predicted optimal regions (uniform 1 Gbps ingress, 1 Gbps source): line = multipath (ingress-bound) for B_f = 1 Gbps;
multipath < line for 222 < B_f < 1000 Mbps (parallel ingress from two peers beats a single forwarder); star < all
others for B_f < ~222 Mbps (forwarders too slow, the idle source wins, the Step 2 crossover in another guise);
with a 250 Mbps source every forwarding topology (line, tree, multipath) is ~56.5 s vs star 168.6 s (H6b).
Native source + 1 Gbps forwarders: star 6.2 s beats every forwarding topology (14 s): a fast source makes forwarding
pointless. **Prediction for the rule**: a per-(fragment, destination) assignment to the provider with the smallest
backlog / egress cap (the Step 2 rule extended to several destinations) produces star-like plans when B_f is small,
multipath plans when peers hold disjoint fragments and B_f is moderate, and reaches the ingress bound when
everything is uniform; i.e. it should match the best fixed topology within ~10 % in every condition (H6f).
H6e: when destination ingress is saturated by one provider (B_f >= B_in), multipath adds nothing (predicted exactly 0).

### D.3 Dynamic re-planning (Experiment C)

Switching cost measured in Phase 1: 0.28-0.32 s control plane + the in-flight fragment of each cancelled flow
(4 MiB: 0.03 s at 1 Gbps, 0.5 s at 62.5 Mbps). Re-planning pays when the remaining transfer on the old plan exceeds
that by a margin: with a forwarder dropping from 1 Gbps to 125 Mbps with 50 % of the Sink left, staying costs 56 s,
re-planning to the idle source costs 7 s + 0.3 s. With the source shared by 4, the same drop is worth 28 - 7 = 21 s.
A deadline change at C in A->B->C (line, uniform) cannot be helped by adding A->C unless A's egress has slack
(it has none at B_s = B_in: A->B uses it all); it helps when B_s > B_in or when A->B is already done.
Predicted: C2 (bandwidth drop) is the only scenario with a large, robust gain; C1 gains exist only with source slack;
C3 is pre-positioning's attach/prune and belongs to Experiment A; C4 is B + C2 combined.

## E. Required implementation changes (minimum per hypothesis)

Network harness (`restore_*`), in order of need:
1. **Pre-positioning phase** (A): per session, a pre-move window of L s during which an allocation policy sends
   fragments to candidates (none / oracle / top-1 / proportional / tail-coverage / all-affordable); the true
   destination is drawn from a seeded distribution (calibrated) or from a different one (miscalibrated); `holders` =
   every node that holds verified fragments (not only past owners). ~80 lines in the orchestrator, none in the node.
2. **FLOW_ADD** in `restore_node.py` (append fragments to a running flow, as the GPU harness has) so forwarders can
   pipeline fragments as they arrive (B, C). ~30 lines.
3. **Dissemination mode** (B): a session with a destination set, each needing the whole Sink, with optional
   deadlines; fixed topologies star / line / tree / disjoint-multipath as plans; the aware rule generalized to
   (fragment, destination) pairs with any holder as a provider. ~150 lines orchestrator.
4. **Time-varying caps and deadlines** (C): a schedule of cap changes applied through `realloc` (rates are pushed
   to senders already); re-plan trigger on cap change / deadline change / periodic with hysteresis; deadline-miss
   accounting; switching-cost accounting (cancels, drained bytes, control-plane latency). ~100 lines.
5. **Ingress-aware correction of `reuse_aware`** (H4c): move a fragment off a holder only if the holder's estimate
   exceeds both the source's and the ingress bound. ~10 lines; to be validated on the Step 2 grid (re-run of the
   15 aware configurations, 45 runs, ~45 min) before it is used anywhere else.
6. Per-link capacity matrix: only if a hypothesis needs it (none of A-C does with per-node caps); skip.
Fluid model: extend with 1, 3, 4 (same code paths) to produce the prediction tables before each run.
GPU harness (D): port `reuse_aware` and the pre-positioning policy to `mobility_orchestrate.plan` (same logic);
add full-state migration and cold restart as execution policies (plan E5); ~200 lines.

## F. Proposed pre-registered criteria (frozen on approval)

Experiment A (network level, 1 Gbps caps unless stated; medians over 10 seeded destination draws x 3 reps):
- H5a supported if, at k = 3, p = (0.6, 0.3, 0.1), L = 10 s, b = 1, top-1's mean post-move completion is <= 0.75 x
  no-pre-positioning's (analytical 10.4 vs 14.4 s) and the oracle's is <= 0.35 x.
- H5b (mean) supported at a condition if proportional or tail-coverage beats top-1's mean by >= 1 s; predicted NOT
  supported at B_s = 1 Gbps, supported with a native-speed source. H5b (tail) supported if tail-coverage's p90 is
  lower than top-1's by >= 2 s at L = 20 s, b = 2 (analytical 7.3 vs 8.5 s) without raising the mean by > 1 s.
- H5c supported if bytes sent to non-chosen candidates never exceed the budget minus bytes at the chosen one, in every
  run (an accounting identity the harness must satisfy; failure = harness bug).
- H5d supported if, with N = 4 sessions sharing the source, pre-positioning 0.5 Sink for one session raises the
  others' makespan by >= 0.5 x 0.5 T_s = 3.5 s (analytical 7 s), and by < 1 s when the source is otherwise idle.
- H5e (new) supported if, with N = 4, a session whose 0.5 Sink landed at a non-chosen candidate restores >= 0.5 T_s
  sooner than with nothing pre-positioned (analytical 28 s sooner), while with N = 1 the difference is < 1 s.
Experiment B (network level, 3 destinations; 3 reps; model predictions tabulated before the run):
- H6a supported if the best fixed topology differs across the conditions {uniform; B_s = 250; B_f = 125; B_f = 500;
  native source} (predicted: line/multipath; any forwarding; star; multipath; star).
- H6b supported if at B_s = 250 every forwarding topology's makespan is <= 0.5 x star's (analytical 56.5 vs 168.6).
- H6c supported if at B_f = 125 line's and tree's last-destination completion exceed star's by >= 2 x (112 / 225 vs 42).
- H6d supported if at B_f = 500 multipath's makespan is <= 0.75 x line's (analytical 18.7 vs 28.1); H6e supported if
  at uniform 1 Gbps multipath is within 1 s of line (both ingress-bound).
- H6f (the rule) supported if the generalized aware rule's makespan is within 10 % of the best fixed topology in every
  condition; rejected if it is > 25 % worse in any.
Experiment C (only if the model predicts >= 15 % makespan or deadline-miss reduction for the chosen scenario):
- H7 supported if dynamic re-planning reduces deadline misses or makespan by >= 15 % relative to "aware at moves only"
  in scenario C2 with no more than 2 re-plans per session and no run worse than the baseline by > 1 s.
Validity for every network run: all fragments verified; paced egress within 1.05 x cap over 10 s; NIC peaks within
1.15 x cap; four distinct hosts; invalid runs listed and re-run, never dropped.

## G. Pilots (each run and inspected before its sweep)

- A-pilot: k = 3, p = (0.6, 0.3, 0.1), L = 10, b = 1, policies none / oracle / top-1 / proportional, 3 draws, N = 1:
  12 runs, ~8 min. Go if the accounting (bytes per candidate, holders forwarding pre-positioned fragments) matches
  the model within 1 s; no-go = harness fix first.
- B-pilot: uniform 1 Gbps, star / line / multipath / rule, 1 rep: 4 runs, ~5 min. Go if line and multipath are within
  1 s of 14.1 s and star within 1 s of 42.2 s.
- C-pilot: C2 only (B's egress 1 Gbps -> 125 Mbps at 50 % progress), fixed vs re-plan, 1 rep: 2 runs.

## H. Full sweeps and I. costs (network runs ~0.5-2 min each including setup; GPU runs ~2-3 min)

| sweep | grid | runs | wall |
|---|---|---|---|
| A1 budget x lookahead | k = 3, p fixed, b in {0, 0.5, 1, 2} x L in {2, 5, 10, 20} x 5 policies x 10 draws | 800 (single-session runs ~25 s) | ~6 h; cut to 3 draws if 10 are not needed (variance is in the draw, so 10 are) |
| A2 calibration | top-1 probability in {0.4, 0.6, 0.8, 1.0} x calibrated / miscalibrated x top-1 / proportional / coverage, L = 10, b = 1, 10 draws | 240 | ~2 h |
| A3 contention | N = 4, b in {0, 0.5, 1}, top-1, calibrated 0.6, 3 draws x 3 reps | 27 (N = 4 runs ~60 s) | ~0.5 h |
| B | 4 fixed + rule x {uniform, B_s 250, B_s 500, B_f 125, B_f 500, native B_in, native B_s} x 3 reps | 105 | ~2 h |
| C2 | 2 policies x 3 drop levels x 3 reps | 18 | ~0.3 h |
| D (GPU) | 6 policies x {slow, fast, repeated} x 3 reps | 54 | ~3 h + GPUs free on 4 hosts |
Model sweeps (8 destinations, finer grids) are free and run first.

## J. Risks and likely negative results

- A: H5b (mean) will probably be rejected at 1 Gbps (linear objective); report it and keep the tail result only if it
  clears the 2 s margin. Prediction calibration is synthetic (we draw destinations from a stated distribution); the
  paper must say so and not claim a predictor.
- B: at uniform capacities all forwarding topologies collapse onto the ingress bound; the interesting content is the
  crossover map, which the model gives exactly and the testbed confirms at 7 points. Butterfly-like multipath is
  predicted to beat line only for 222 < B_f < 1000 Mbps and to lose to star below that.
- C: the gain exists only for mid-restoration bandwidth drops at a forwarder; if the model shows < 15 % the experiment
  is dropped and M3 stays "re-plan at moves".
- D: PSNR rejoin adds a constant ~4 s (6 calls) after bind that no topology changes; TTFO is ~0.7 s for every OTTER
  variant. End-to-end differences will be in bind time and coverage only.
- Measurement: loopback-validated harness features only; every new feature gets a loopback test at the real
  412-fragment ratio before touching the testbed (Scenario B v1 was invalidated by exactly such defects).

## Critical assessment

1. **Full topology morphing is not scientifically justified by the evidence.** Phase 1, Scenario B and Step 2 show
   one mechanism doing the work: keep verified fragments where they land and, at each event, assign each missing
   fragment to the provider with the smallest whole-node backlog over capacity. Star, line, tree and multipath are
   shapes that rule produces under different capacities (D.2), not mechanisms. Naming four operations (attach,
   reparent, branch, prune) describes what one re-plan does; it should be presented as such, with "topology" as the
   evaluation axis (which shape is optimal when) rather than as the contribution.
2. **Butterfly vs tree:** analytically butterfly-like multipath never loses to tree (a tree shares a forwarder's egress
   among children; multipath spreads disjoint fragments so every node forwards), and beats line only in the band
   222 < B_f < 1000 Mbps (its time is (2/3) T(B_f) against line's T(B_f)); it is identical to fragment-level
  multi-provider delivery that the harness already does
   into one destination. There is no distinct mechanism to claim, only a distinct regime to map.
3. **Dynamic adaptation vs overhead:** the switching cost is small (0.3 s + one fragment), so the question is not
   overhead but whether conditions change within a restoration (14-56 s). Only mid-restoration forwarder slow-downs
   (C2) are predicted to matter; everything else is already covered by re-planning at moves. Build C only if the
   model shows >= 15 % for C2.
4. **Pre-positioning vs routing adaptation:** routing adaptation is worth 12-13 % in narrow regimes (Step 2) and 0 at
   the ingress bound; pre-positioning is the only lever that moves the ingress bound itself (Phase 1 oracle: 14.8 s ->
   0.7-11.4 s). It is the more promising latency contribution, and H5e connects it to reuse: under source sharing,
   speculative bytes are useful wherever they land. Its weakness is that the predictor is synthetic.
5. **Simplest strongest contribution:** (M1) temporal state decomposition with execution moving ahead of the Sink
   (measured: 0.7 s first output at every bandwidth); (M2) persistent, progress-preserving restoration whose provider
   choice is backlog-aware (measured: completes where restart never does under repeated mobility; 1.00 Sink of source
   traffic; crossover handled); (M3, conditional) budgeted pre-positioning to predicted destinations, evaluated against
   the oracle and shown to be worth the traffic only under stated conditions. Drop "topology morphing" as a named
   mechanism; keep the topology study as the evaluation that explains when each shape is optimal and shows the rule
   reaching the best shape within 10 %.

Recommended order: approve F -> implement E.1, E.2, E.5 (+ model) -> A-pilot -> A1/A2/A3 -> E.3 -> B-pilot -> B ->
model check for C -> (C2 if justified) -> E (GPU) -> D.
