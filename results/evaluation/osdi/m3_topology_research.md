# M3 research investigation: is topology-aware, version-consistent restoration a real systems problem? (2026-10-29)

Read-only investigation. No code, run, result or verdict is changed. Labels: **[V]** verified from repository files,
code or recorded traces (path given); **[H]** hypothesis or inference; **[R]** recommendation. "oldM1 / oldM2" are the
fast-path and continuity-wavefront mechanisms of the earlier experiments; "M1 / M2" are the frozen mechanisms of
47acbe44 (`m1_continuity/`), as in `m3_audit.md`.

---

## 1. Executive conclusion

**Recommendation: CONDITIONAL GO**, for one direction only, and **NO-GO for explicit topology morphing as a
mechanism.**

1. **The four topologies are not four mechanisms** [V]. In the repository they are four parameterizations of one
   per-fragment provider-assignment function, differing only in which holders may provide (section 2). The adaptive
   assignment reproduces every one of them and, in two of the four Full-E conditions, produced flows identical to the
   "butterfly" plan (section 3). The earlier conclusion — no separate topology-selection mechanism is justified —
   remains valid under the original assumptions (section 4).
2. **The restoration graph cannot help a reactive migration on this testbed** [V]. M3-E0 bounds any multi-provider
   gain of the final base to 1.9-3.2 s (3.8-6.7 % of remote serving) because the destination's ingress is the
   bottleneck and the user never returns to the holders (`m3e0/m3e0_report.md`).
3. **What the frozen M1 / M2 add is a version structure that oldM1 / oldM2 did not have** [V]: every Sink block
   carries a snapshot call; blocks age by two known transforms (RoPE shifts, exactly reconstructible in order; refreshes,
   source-only). On the M3-E0 traces 0 of 412 fragments fell outside these two classes, and the shift class is
   reconstructed bitwise offline (section 5). That makes stale, partial, third-party Sink state *convertible* rather
   than invalid.
4. **The one direction with a technical core** is to move the base transfer off the critical path by *staging*
   version-converted state at candidate destinations before the move, where holder-to-candidate forwarding (a
   dissemination graph) and version lineage interact (candidate C1, section 6). It attacks the only large term M3-E0
   measured (the chase, 38-58 % of remote serving) and converts the final migration into an M2-style delta migration
   (readiness 8.7 s measured in E9 vs 21-24 s). Its critical unverified assumption is not exactness but **timing and
   prediction**: whether staging fits inside T_m and whether a usable next-edge estimate exists. Section 9 gives the
   offline falsification experiment, on the recorded M3-E0 versions and the validated fluid model, with GO / NO-GO
   rules.
5. The four topologies' role in C1 is as **states and baselines of a staging graph**, not as the contribution. If the
   falsification test fails, the better-supported alternative is a small control-plane change (migration admission,
   C3) and the paper presents M1 / M2 with repeated mobility as a measured limitation.

---

## 2. Audit of the four topology implementations

### 2.1 Where the topologies live [V]

Two families exist, both inside `tools/eval/restore_planner.py`, both executed by the network harness only:

| family | function | experiment | destinations | planned when |
|---|---|---|---|---|
| **Dissemination** plans `star / line / tree / multipath / aware` | `dissem_assign(plan, nfr, flen, caps, edges)` → provider of every (fragment, destination) pair | Experiment B (`restore_dissem_pilot`, `restore_dissem_hetero`; `DissemRun` in `restore_orchestrate.py`) | three fixed destinations B, C, D at once | once, at t0; `DissemRun.plan` is a no-op |
| **Mobility** plans `pp_star / fixed_line / fixed_tree / fixed_butterfly` | branch `policy in FIXED_PLANS` of `assign_providers(...)` | Full Experiment E (`restore_fulle`; `Run.plan`) | the current owner only | at start, every move, every `flow_done` |

The GPU orchestrator `mobility_orchestrate.py` imports neither family: its `AWARE` set is `reuse_aware_in`,
`reuse_dyn`, `reuse_dyn2`, and `plan()` has no fixed-plan branch [V]. No topology was ever executed with a GPU
workload [V].

### 2.2 What each plan does, from code and flow records [V]

Data path in both harnesses: a provider opens one TCP connection per (provider, destination) flow (`FLOW_START`),
sends only fragments it has **verified** (SHA-256 at receipt; `restore_node._sender`: `held = fid in s["have"]`,
otherwise `FRAG_SKIP`), and forwards pipelined through `FLOW_ADD` as fragments land (`DissemRun.handle` on `FRAG_RECV`;
`Run.plan`'s `late` queue). Relaying is **physical**: bytes pass through the intermediate node, which must hold them
verified. In the network node the forwarded bytes are regenerated deterministically from (session, fragment)
(`frag_bytes`), so network-level holders keep **no** fragment memory [V]; in the GPU node they are real
(`mobility_node._sender` reads `r["sink"]["buf"]`) [V]. No per-link capacities exist: `maxmin(flows, caps)` knows only
per-node `("out", n)` and `("in", n)` caps [V].

**Dissemination plans** (one Sink of 412 × 4 MiB at A; `restore_dissem_pilot/plan=*/flows.csv`):

| plan | graph (who sends what) | replication / partition | concurrency | A egress / edge egress / edge ingress | measured makespan at uniform 1 Gbps | failure dependency [H: never tested] |
|---|---|---|---|---|---|---|
| star | A → B, A → C, A → D, each all 412 | 3 full replicas from A | 3 concurrent flows | 3 S / 0 / 1 S | 41.7 s (= 3 T) | none between edges |
| line | A → B (412); B → C (412) pipelined; C → D (412) pipelined | full replica per hop | 3 concurrent, one-fragment lag per hop | 1 S / B 1 S, C 1 S / 1 S | 13.9 / 14.1 / 14.1 s | B's failure stalls C and D |
| tree | A → B (412); B → C (412); B → D (412) | full replica; hub B | 3 concurrent | 1 S / B 2 S / 1 S | 14.0 / 27.9 / 27.9 s (B's egress halves) | B's failure stalls C and D |
| multipath ("butterfly") | A sends third i (f mod 3) to edge i; each edge forwards its third to the other two: 9 flows | **partitioned** at A, assembled at each edge | 9 concurrent | 1 S / 2/3 S each / 1 S | 14.0 s at all three | any edge's failure stalls one third at the others |
| aware | per (f, d) greedy by provider finish estimate, arrival-order forwarding | partitioned; in the pilot it produced A → {B, C, D} thirds and a cycle B → C → D → B of 275 each | 6 flows | 1 S / 2/3 S / 1 S | 14.0 s | as multipath |

The name "butterfly" denotes disjoint-stripe multipath (Bullet / SplitStream style), not a butterfly interconnect [V
from `dissem_assign`].

**Mobility plans** (owner changes A → B → C → D; `assign_providers`, `FIXED_PLANS` branch) [V]:

```
past = owners so far except the source
pp_star          allowed = []                 nobody forwards; the source sends what the owner lacks
fixed_line       allowed = [past[-1]]         only the previous owner forwards
fixed_tree       allowed = [past[0]]          only the first intermediate owner (hub) forwards
fixed_butterfly  allowed = all past holders   a fragment held by several goes to the one with the fewest assigned
missing fragments held by no allowed holder -> source
```

So in the mobility family a "topology" is an **eligibility set over holders**; the destination is always the single
current owner; fragments are partitioned among eligible providers and the source; flows are concurrent; forwarding
dependencies (a fragment still in flight to a holder) are expressed by the `late` queue. Memory: a holder keeps what it
received as a past owner (GPU: real bytes; network: none). Completion time at the final owner (Full E,
`restore_fulle_notes.md`, medians):

| condition | pp_star | line | tree | butterfly | aware (at moves) | dyn (M3-v1) |
|---|---|---|---|---|---|---|
| 1 slow B (125 Mbps egress) | 14.0 | 14.0 | **56.0** | **52.5** | 14.0 | 14.0 |
| 2 shared source N = 4 | 54.6 | 38.7 | 45.7 | 38.4 | 38.7 | 38.8 |
| 3 C degrades to 62.5 Mbps mid-restoration | 14.0 | **62.8** | 14.0 | 53.2 | 53.8 | **14.0** (2 re-plans) |
| 4 revisit B | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 |

Flow records explain every slow cell as a *provider* cell, not a structural one [V, `restore_fulle/*/flows.csv`]:
tree's 56.0 s is `B>D 207 fragments` ending at 70.0 s (the slow hub); butterfly's 52.5 s is `B>D 194` ending at
66.5 s; line's 62.8 s is `C>D 207` ending at 76.9 s (its only eligible provider collapsed); butterfly's 53.2 s in
condition 3 is `C>D 155` ending at 67.3 s.

### 2.3 Abstractions, kept apart [V]

| abstraction | present in the repository? |
|---|---|
| dissemination topology (one source, several destinations) | yes: `dissem_assign`; three destinations, planned once |
| mobility restoration topology (sequence of single owners) | yes: `FIXED_PLANS`; eligibility sets |
| logical fragment → provider assignment | yes: this *is* what both families compute; the output is a set of flows |
| physical relay / routing topology | only as a consequence: a provider relays through its own memory; no per-link model, no relay node that is not a holder, no multi-path routing below the flow level |

---

## 3. Expressiveness: adaptive provider assignment vs the four topologies

**Q1. Can the adaptive mechanism reproduce the four?** Yes, by construction [V]: `AWARE_PLANS` and `FIXED_PLANS` are
branches of the same function over the same inputs and produce the same output type (flows per provider). The
adaptive rule's candidate set is `holders + [SOURCE]` with cost weights; each fixed plan is the same rule with the
candidate set restricted and the weights removed.

| topology behavior | representable by the adaptive rule? | evidence |
|---|---|---|
| star: every fragment from the source | yes: the rule assigns the source whenever a holder's finish estimate exceeds the source's and the ingress bound (`reuse_aware_in`); with no eligible holder it is `pp_star` | `assign_providers` AWARE branch |
| butterfly: fragments spread across every holder | yes: with equal caps the rule's greedy balance is an even split; in Full E conditions 3 and 4 `reuse_aware_in` and `fixed_butterfly` produced **identical flow sets** (3: `B>D 155 / A>D 101 / C>D 156` vs `155 / 101 / 156`; 4: `D>B 78-79 / C>B 95-96`) | `restore_fulle/*/flows.csv` |
| line / tree: relay through the previous owner / a hub | yes: pipelined forwarding is the `late` queue + `FLOW_ADD`, available to every policy; restricting to one provider is a special case | `Run.plan`, `restore_node.cmd_flow_add` |
| dissemination star / line / tree / multipath | yes, per (fragment, destination): the `aware` dissemination rule reproduced multipath's split exactly (uniform, B_s = 250) and beat the best fixed plan at B_f = 500 (16.9 vs 18.6 s) by sending 1.20 S from the source | `restore_dissem_hetero_notes.md` |

**What the adaptive rule does not express** [V]:
- *Fan-out to several concurrent destinations* in the mobility harness: `Run.plan` plans for the current owner only.
  Replication to several nodes exists only as pre-positioning (`prepos_alloc`: the **source** sends disjoint fragment
  sets to candidates, star-shaped, never candidate-to-candidate) and as the once-at-t0 `aware` dissemination rule.
- *A relay that is not a holder* (a pure forwarder with no interest in the state): no policy creates one; `relay_pipe`
  (Phase 1) relays only along the fixed ownership chain.
- *Re-planning of a dissemination* (`DissemRun.plan` is a no-op).
- *Per-link or shared-core constraints*: the capacity model has none, so no plan can route around a link.

None of these gaps is a topology-*selection* problem; the first is a replication problem, the last two are modelling
gaps.

---

## 4. Reinterpretation of Experiment B and Full Experiment E

**Why fixed topologies performed differently** [V]. In every slow cell the slow plan had restricted its provider set
to a node whose egress was the bottleneck: the hub (tree, 2 S through B; 56.0 s when B is 125 Mbps), the previous
owner alone (line, 62.8 s when C collapsed), the source alone (star, 3 S of source egress; 41.7 s and 166 s at
B_s = 250), or all holders by count regardless of their caps (butterfly, 52.5 s with slow B). The structure matters
exactly through *which egress carries how many bytes*, i.e. provider assignment under per-node caps.

**Whether the differences came from structure or assignment** [V]. Where the eligibility sets coincide, the plans
coincide: butterfly = aware in Full E conditions 3 and 4 (identical flows, 53.2 vs 53.8 s and 7.0 vs 7.0 s); aware =
multipath in B at uniform and B_s = 250 (same A 1.0 / edge 0.67 split). Where they differ, the difference is the use
of cap knowledge: in slow-B aware sent `B>C 52` against butterfly's `B>C 207`. No condition shows an effect of graph
shape that is not an effect of provider egress.

**Why adaptive matched the best fixed plan** [V]. It optimizes the same quantity the fixed plans only sample:
per-provider finish time under the ingress bound. The fixed plans are four points of its feasible set (Experiment B
reading 3: source 3.0 / 1.0 / 1.0 / 1.0 S; aware 1.20 S at B_f = 500). Its 9 % gain at B_f = 500 came from a point
between star and multipath (1.20 S from the source), unreachable by selection among the four.

**Did any scenario show a capability the adaptive planner lacks?** No [V]. The two things the fixed plans "had" that
aware-at-moves lacked were not structural: dyn's re-plan in condition 3 (reacting to a mid-restoration change) and
fixed tree's accidental 14.0 s there (its hub was not the collapsing node; it pays 56.0 s in condition 1).

**Standing of the earlier conclusion.** "No separate topology-selection mechanism justified by B / E" **remains valid
under the original assumptions** [V]: per-node caps only, one immutable Sink version, known caps, no failures, one
owner at a time (E) or three fixed destinations planned once (B). It was never tested, and therefore says nothing,
about: re-planning *during* a dissemination; holder failures; per-link bottlenecks; **different Sink versions at
different holders**; or replication to future candidates under a source that is also generating. The last two are
exactly what M1 / M2 introduce.

---

## 5. Constraints introduced by the frozen M1 / M2

### 5.1 Versioned state [V]

Facts from E8 / E9 / E10 and the M3-E0 offline classification (`m3e0/e0x_{dog,bfly}.json`, reproduced 412 / 412
against the live fragment hashes):

- The Sink base is 360 blocks (K / V × 30 layers × 2 rows × 3 slots, 4,792,320 B each) plus 1,440 B of positions;
  the wire unit is 412 × 4 MiB fragments, not block-aligned (`m3_audit.md` 3.3).
- Between a snapshot at call s and a base at call t, every changed block is one of two kinds: **shifted** (K of an
  entry not refreshed in (s, t]; its ordered RoPE shifts reproduce the t value **bitwise** — classification by
  `torch.equal` after `_shift_temporal_rope` in order) or **refreshed** (new values only the source has).
  "Other" = 0 blocks in all 8 (version, target) pairs [V].
- Realignment comes in pairs of calls (48 / 49, 93 / 94, 138 / 139) and re-rotates 72-74 (dog) or 61-93 (butterfly)
  of the 180 K blocks; it touches 166-177 of 412 fragments by hash. Between two realignments a 21-call-old base is
  406 / 412 (dog) or 333 / 412 (butterfly) hash-identical to the current one.
- Refreshes are workload-dependent: dog 0-4 blocks over 9-42 calls; butterfly 6-70 blocks (13-99 fragments) over
  7-46 calls.
- A one-shot summed shift is **not** bitwise (E8: 287 / 360); shifts must be applied in order; reconstruction costs
  ~15 ms on the GPU and the shift list ~3 KB (E8).

What M2 handles today [V]: one retained version per node (`retain_sink` at SINKOK), one tracker on the **new owner**
started at its switch (`sink_track_start(version)` at `_xb_switch` when `track_after`), a delta sent only to the node
that advertises the tracked version (`_replay_send_base`: "the destination's version is not the tracked one" →
full base). It does **not** handle: a third node's version, several outstanding versions, partial bases, or blocks
staged at a node that never owned the session.

**New constraint** [V]: a holder's fragments are valid for a target base only per block and only with the shift
suffix since the block's snapshot call; validity is decided by the *source's* refresh / shift history, which no
holder has. oldM1 / oldM2 had none of this: one immutable snapshot, hash validity, no transforms.

### 5.2 Live state evolution [V] + [H]

- The optimal graph does change as state evolves [V]: in M3-E0 the base at c0 = 52 was 98 % identical to the final
  base at 73, the base at 31 only 58 % (dog); staged content loses hash validity at every realignment (every ~45
  calls) but stays *shift-valid*; it loses shift validity only at refreshes.
- Existing holders become stale in two ways [V]: convertible (shift) and non-convertible (refresh). Only the second
  needs source bytes: 21-34 MB (dog) to 315-378 MB (butterfly) in M3-E0's union.
- New refreshes invalidate earlier transfer decisions [V]: a staged block refreshed after staging must be re-sent;
  M2's tracker already drops an entry's shifts when it is refreshed (`sink_track_step`).
- Re-planning must account for conversion cost [H, small]: 15 ms per base on the GPU, 77-96 ms H2D of a retained
  copy (E8, E10); the cost that matters is bytes, not compute.
- Does M2 already handle these? Only for the owner-held retained version. Its data model (per-entry refresh set +
  ordered shift list since a version) is exactly what a multi-holder scheme needs; what is missing is tracking since
  *several* snapshot calls on the source and conversion at a destination that is not the retaining node [V].

### 5.3 Network bottlenecks [V] + [H]

- Uniform 1 Gbps per-node caps: the destination's ingress binds; multi-provider UB 1.9-3.2 s (M3-E0) [V].
- The source's egress is not idle under M1: it carries the live log + refresh patches, measured 12-16 Mbps (dog) and
  **153-167 Mbps (butterfly)** during the final task of M3-E0, concurrently with the base and generation [V]. During
  the base transfer A's NIC averaged 871-916 Mbps (butterfly) vs D's 823-864 Mbps received: the source was within
  10 % of its cap while the destination was not, i.e. source egress was the tighter side for butterfly [V].
- Deployment model (`expT/deployment_model.md`) [V]: site uplinks with egress / ingress caps, a non-blocking core, all
  of a site's flows and cross-traffic sharing its uplink. Under that model relays through non-holders can never help
  (they only add egress load), and multi-provider delivery helps only when the destination's ingress exceeds the
  source's available egress — source slower than destination, source cross-traffic, concurrent sessions, or the live
  log. Real edge uplinks are often asymmetric (upload below download) [H: no trace; `expT` paused].
- Conditions that would make graph structure matter, in order of evidence: (1) source egress shared by several
  sessions — measured in oldM2 (Full E condition 2: 38.4 vs 54.6 s; M3E S1 43.1 vs 57.2 s) [V], unmeasured under
  M1 / M2; (2) source egress < destination ingress (B at B_s = 250: 55 vs 166 s) [V network-level]; (3) replication
  to several candidates before a move, where the source would otherwise send k copies [V B: 41.7 vs 14.0 s]; (4)
  heterogeneous holder egress (crossover below ~250 Mbps, `restore_holder_notes.md`) [V network-level].

---

## 6. Candidate technical mechanisms

### C1. Lineage-staged restoration graphs (proactive, version-converted staging)

**Problem** [V]. Under M1 / M2 the base (73-97 % of migration bytes) is sent reactively after each move, so (a) every
migration restarts from an empty destination and is cancelled when T_m < readiness (M3-E0: 2 cancellations per run,
0.60-1.71 Sink discarded) and (b) remote serving is dominated by the chase (38-58 %) plus one ingress-bound base
(13.8 s). No reactive graph changes either term (UB 1.9-3.2 s).

**Observation.**
- [V] A destination that already holds a base version needs only a delta: E9 measured base-ready 2.46 s and readiness
  8.74 s (vs 18.30 / 22.17 s), with 21.6 MB (dog) / 357 MB (butterfly, E10) instead of 1,727.6 MB.
- [V] Partial bases at abandoned nodes are 58-98 % hash-identical to later bases and 100 % convertible except for
  refreshed blocks (0 "other").
- [V] Correct pre-positioning cut oldM1 bind-ready 15.42 → 4.94 s (ExpD G4, reproduced `expDR_C`); incorrect placement
  cost bytes, not latency (G5 / `expDR_D`).
- [V] Forwarding among destinations delivers k copies for one source copy (B: 14.0 s vs star 41.7 s), and the source
  under M1 is already loaded by the log (153-167 Mbps on butterfly).
- [H] A next-edge estimate (even a 2-candidate set) is available in practice. No trace evidence (`expT` paused).

**Challenges.**
1. *Version lineage across hosts*: a block staged at node X at snapshot call s must be converted to the target call t
   with the shift suffix (s, t] and declared invalid if refreshed in (s, t]; the history lives at the source, the
   bytes at X, the assembly at the destination; exactness must be verified before replay. Multiple X with different s
   must combine into one digest-equal base.
2. *Staging under uncertainty and aging*: staged bytes decay (refresh rate: dog ≈ 0.1 block / call, butterfly ≈ 1-1.5
   blocks / call) and the destination is uncertain; the graph must decide how much to stage where, from whom (source
   vs holders), and when to stop, against the source's egress shared with the live log and generation.
3. *Deciding profitability*: staging pays only if the resulting delta migration is ready before the next move
   (T_m) and the staged bytes are not larger than what they save; with ρ = 2 (T_m 7.0 s) even a delta migration
   (≈ 8.5-9 s: delta base 2.5 s + catch-up 3.8-4.5 s + switch 2 s, estimate from E9 / M3-E0) may not fit.

**Solution** (one mechanism) [R]. Per session, the source keeps a **per-entry lineage log**: for each of the 180
entries, its last refresh call and its ordered shift events (3-5 ints per event; E8: 150-197 events / 100 calls). Every
node keeps for each Sink block it holds a **(snapshot call, hash)** tag. A **staging graph** is planned at each move
over candidates {next-edge candidates} with providers {source, holders with tagged blocks}: for each (block, candidate)
choose a provider whose block is lineage-valid at the current call (not refreshed since its snapshot), weighted by the
provider's egress backlog and the candidate's ingress, under a source-egress budget that reserves the live log's rate.
At the move, the destination advertises its tagged blocks; the source answers with a **delta** = the refreshed entries'
current values + the ordered shift suffixes per staged block (M2's `reuse_base`, generalized to per-block snapshot
calls); the destination rebuilds and verifies 360 block checksums + positions before `shadow_base` (M2's DELTAOK /
DELTANO with full-base fallback, unchanged); the cutover check stays. Dynamics: a refresh at the source marks staged
copies of that entry invalid (they are simply excluded from the delta's "keep" set); a realignment does not invalidate
anything, it only lengthens the shift suffix. Correctness is never decided by a staged node: validity is a function
of the source's log, verified at the destination.
*Why not reducible to the existing planner*: the planner assigns fragments of one immutable version to one owner from
holders of identical bytes; here the objects are blocks with lineages, the validity of a transfer depends on state the
provider does not have, the destinations are future candidates, and the objective includes the delta the staging
leaves for the critical path.

**Role of the four topologies.** States and baselines of the staging graph: star = the source stages everything
(G4 / `prepos_alloc` today); line / tree = chained forwarding from an earlier-staged candidate; butterfly = holders
and candidates exchanging disjoint lineage-valid partitions. They are special cases of the general per-block graph and
expose its structural limits (source egress, hub egress); none is required to be used as such.

**Novelty** [H]. The algorithmic object is a restoration graph whose edges are either transfers or version transforms,
with validity windows set by a live log; staged state is treated as *lineage + transform*, not as a replica. The
systems insight is specific to streaming diffusion: the dominant Sink churn is a known, exactly invertible rotation,
so stale replicas are cheap to convert and only refreshes cost bandwidth. This is more than M2 × M3-v2: M2 converts one
version at one node; M3-v2 assigns identical fragments reactively.

**Risks.**
- Novelty collisions [H]: proactive VM / container migration to predicted edges (follow-me cloud literature);
  delta / incremental state sync (rsync-style, KV-cache deltas); striped dissemination (Bullet, SplitStream, Orchestra).
  The combination with exact lineage conversion is what must carry the claim.
- Weak assumptions: a usable next-edge estimate; ρ ≤ ~1.5 (at ρ = 2 even a delta migration may not fit).
- Correctness complexity: per-block snapshot tags, multiple lineages per base, verification before replay; refresh
  races between staging and the move.
- Experimental feasibility: 4 hosts suffice; traces for prediction do not exist (`expT` HOLD).
- No benefit when: destinations are unpredictable and k·staging exceeds the budget; refresh-heavy inputs (butterfly's
  24 % refreshed blocks over 46 calls) shrink the convertible share; destination ingress ≫ source egress makes the
  reactive delta cheap anyway.

**Falsification test** [R]. Section 9.

### C2. Lineage-aware reactive multi-provider base delivery (the audit's I1-I4)

**Problem** [V]: the final base is sent by the source alone while abandoned holders keep 0.5-1.4 GB of convertible
state. **Observation** [V]: M3-E0 UB 1.9-3.2 s on uniform caps; source egress tighter than destination ingress for
butterfly (871-916 vs 823-864 Mbps); oldM2 contention gains 14 s (M3E S1). **Challenges**: (1) third-party conversion
(as C1's challenge 1); (2) deciding when holders help at all (ingress-aware, as M3-v2) now with version-dependent
byte counts; (3) progress preservation of partial bases in the XB path. **Solution**: holders forward lineage-valid
fragments concurrently with the source's refreshed entries, planned by `assign_providers` + `dyn_decide_v2` over
version-weighted fragment sets; verification as C1. **Topologies**: baselines only. **Novelty** [H]: low-to-moderate;
reviewers will read it as the integration of M2 and M3-v2. **Risks**: the gain regime (source-limited egress,
contention) is unmeasured under M1 / M2 and excluded by the uniform testbed; on the measured path the bound is
1.9-3.2 s. **Falsification**: a network-level run with A's egress capped at 250-500 Mbps or 3 concurrent sessions,
M1 / M2 configuration, holders forwarding vs not (fluid model first).

### C3. Mobility-aware migration admission (no-chase control)

**Problem** [V]: 0.60-1.71 Sink per run is spent on migrations that cannot finish before the next move. **Observation**
[V]: readiness 21-24 s vs T_m 14.05 / 7.0 s; cancellation lag 0.5-2.9 s. **Challenges**: (1) estimating readiness
online from base size, link rate and log rate; (2) deciding under an unknown T_m; (3) interaction with staging (C1).
**Solution**: start or continue a base transfer only when predicted readiness < predicted dwell; otherwise serve
remotely and stage nothing (or stage a small lineage-valid subset). **Topologies**: none. **Novelty** [H]: low (an
admission heuristic); **but** it removes a measured waste at near-zero cost and does not change remote serving.
**Risks**: a wrong dwell estimate delays a migration that would have finished. **Falsification**: offline on the M3-E0
timelines, trivial; GPU confirmation 4 runs.

---

## 7. Comparative OSDI assessment

| criterion | C1 lineage-staged graphs | C2 reactive lineage-aware delivery | C3 migration admission |
|---|---|---|---|
| technical novelty | new object (transfer + transform graph with validity windows); specific to invertible Sink churn [H] | integration of M2 and M3-v2 with third-party conversion [H] | heuristic |
| problem significance | attacks the chase (38-58 %) and the full-base term; could turn repeated mobility from "never completes at ρ ≥ 1" into delta migrations [V problem, H gain] | ≤ 1.9-3.2 s on the measured path [V]; larger only in unmeasured regimes | removes 0.6-1.7 Sink waste [V]; no latency gain |
| experimental support | G4 placement 3×, E9 delta 2.5× readiness, 0 "other" blocks, B forwarding 3× — all pieces measured, the composition not | M3-E0 (negative on this path), oldM2 contention (not transferable) | M3-E0 timelines |
| M1 / M2 compatibility | preserves base verification + cutover check; extends M2's tracker to several snapshot calls (protocol extension, must be re-validated as E10) | same | no protocol change |
| topology relevance | staging graph states / baselines; dissemination results (B) directly relevant | baselines only | none |
| implementation complexity | high: lineage log, block tags, staging planner, multi-lineage delta, candidate protocol | medium: partial-base retention, third-party conversion, flow plumbing in the XB path | low |
| evaluation feasibility | 4 hosts OK; needs a mobility model for candidates (synthetic; no traces) | 4 hosts; needs asymmetric caps / contention configs | trivial |
| strongest reviewer criticism | "prediction assumed; proactive migration is known; gains only at ρ ≲ 1.5" | "engineering; your own bound says ≤ 3 s" | "not a contribution" |

**Ranking**: C1 > C3 > C2. C2 is dominated: its only distinct capability (third-party conversion) is a component of
C1, and its gain regime is unmeasured and excluded by the testbed model. C3 is sound but is a control knob, not a
paper section; it should accompany whichever direction survives.

Skeptical note on C1 [H]: it is a strong contribution only if the staged-delta path makes repeated mobility *complete*
where it now never does, on a mobility model reviewers accept. Without that, it is a complex mechanism for a 2-3 s
gain, and the honest paper is M1 / M2 with repeated mobility as a measured limitation.

---

## 8. Recommended research direction

**CONDITIONAL GO on C1 (lineage-staged restoration graphs); NO-GO on explicit topology morphing** [R].

- Keep the advisor's graph framing but change its object: not "which of four topologies", but "which lineage-valid
  blocks move between which nodes before the move, and what delta remains on the critical path". Star, line, tree and
  butterfly appear as states and baselines of that graph.
- The condition: the offline test of section 9 must show that staging fits inside T_m at ρ = 1 and reduces remote
  serving and discarded bytes by a stated margin on the recorded M3-E0 versions. If it fails, adopt C3 for the paper
  and report repeated mobility as a limitation of M1 / M2.
- Independently of the outcome, the two facts worth stating in the paper are already measured [V]: a Sink version ages
  by exactly two transforms (shift: exact and cheap; refresh: source-only), and the destination's ingress, not the
  provider set, bounds a reactive base transfer.

---

## 9. One minimal falsification experiment: **M3-S0, offline staging feasibility**

**Hypothesis under test** (the most important unverified assumption of C1): *given the measured version dynamics,
staging lineage-valid state at the next candidate before the move makes the final migration a delta migration that is
ready before the next move at ρ = 1, at a staging cost below the bytes it saves.* Exactness is not the question
(0 "other" blocks; E8 / E10 verified conversion); timing and bytes are.

**Inputs (all existing)** [V]:
- the four M3-E0 runs: move times, task timelines, per-task flow rates (`expM3E0_*/…/events.csv`, `node_*/network.csv`);
- the offline per-block refresh / shift history and per-version fragment hashes
  (`tools/eval/m3e0_crossversion.py`, already reproduced 412 / 412; extend its output to a per-call validity table —
  analysis code only);
- the fluid model `tools/eval/restore_model.py` (per-node max-min caps; matched 84 Full-E runs within 0.70 s max,
  0.17 s median) for transfer times;
- measured constants: delta rebuild 0.42 s, replay catch-up 3.8-4.5 s, switch 1.7-2.3 s (E9 / M3-E0), log rate
  12-16 / 153-167 Mbps.

**Policies compared offline** (no code in the frozen path; a ~300-line analysis script):

| policy | what is staged, from whom, when |
|---|---|
| S0 none | M3-E0 as measured (reference) |
| S1 source star | at each move, A stages its current base to the candidate(s) with the egress left after the active migration and the log |
| S2 holder forward | the just-abandoned holder forwards its lineage-valid blocks to the candidate(s); A sends only blocks the holder lacks or that were refreshed |
| S3 butterfly staging | S2 with two holders (B and C) partitioning the candidate's missing set |
| candidate knowledge | (a) oracle next edge; (b) uniform over the 2 other edges (budget split) |

**Computed per policy and configuration**: blocks lineage-valid at the destination at its move (from the validity
table at the final c0), delta bytes the source must send (refreshed entries since each block's snapshot + missing),
predicted base-ready = delta / destination ingress share + 0.42 s, predicted readiness = base-ready + catch-up,
staging bytes by provider, source egress time budget used, remote serving = chase + predicted readiness + switch.

**GO / NO-GO (fixed now)**:
- **GO** if, at ρ = 1 for both workloads under S2 or S3 with the oracle candidate: predicted readiness < T_m
  (14.05 s), source bytes of the final migration ≤ 0.5 Sink, remote serving reduced ≥ 30 % vs S0; **and** under the
  uniform-2-candidate case the extra bytes (staging + wasted staging) are ≤ 1.0 Sink per migration. ρ = 2 is reported
  descriptively (expected not to fit).
- **NO-GO** if readiness ≥ T_m at ρ = 1 for either workload under every staging policy, or if the uniform case costs
  more than 1.5 Sink per migration. Then C1 is dropped and C3 is taken.
- Between the two: CONDITIONAL, and the next step is a network-level (no GPU) staging run with the restore harness,
  not GPU integration.

**What it does not need**: GPU time, changes to M1 / M2 or M3-v2, new runs. **What it cannot show**: real mobility
predictability (declared limitation), real refresh timing under staging load (fluid model), and conversion at a third
party executed end to end (E8 / E10 verified the primitives; end-to-end only after a GO).

---

## 10. Evidence and repository references

| claim | where |
|---|---|
| topology families and their code | `tools/eval/restore_planner.py`: `dissem_assign` (dissemination), `assign_providers` `FIXED_PLANS` / `AWARE_PLANS` (mobility), `maxmin` (per-node caps only), `prepos_alloc` (source-star placement) |
| execution and relay semantics | `tools/eval/restore_orchestrate.py` `Run.plan` (late queue), `DissemRun` (FLOW_ADD pipelining, `plan` no-op); `tools/eval/restore_node.py` `_sender` (held check, `frag_bytes` regeneration), `cmd_flow_add` |
| GPU path has no fixed plans | `tools/eval/mobility_orchestrate.py` `AWARE`, `plan`, `plan_aware` |
| B-pilot flows (star 3 × 412 from A; line chain; tree hub 2 S; multipath 9 flows; aware cycle) | `results/evaluation/restore_dissem_pilot/plan=*/flows.csv`; `restore_dissem_pilot_notes.md`; `restore_dissem_hetero_notes.md` |
| Full E flows and the provider explanation of slow cells; butterfly = aware in conditions 3 / 4 | `results/evaluation/restore_fulle/policy=*/flows.csv`; `restore_fulle_notes.md` |
| holder crossover (~250 Mbps) | `restore_holder_notes.md`, `restore_holder_h4c_notes.md` |
| ExpD G4 / G5 / G7; reproduction | `osdi/expD/expD_report.md`, `expD_repro_reading.md`, `expDR_{C,D}` |
| oldM2 contention gains | `osdi/expM3E/m3e_report.md` S1; Full E condition 2 |
| M1 / M2 facts: delta 21.6 / 357 MB, readiness 8.74 vs 22.17 s, ordered shifts required, 0 "other", 412 / 412 reproduction | `osdi/m1_continuity/e8_record.md`, `e9_record.md`, `e10_record.md`; `osdi/m3e0/e0x_{dog,bfly}.json`, `m3e0_report.md` |
| M2 tracker and delta protocol | `tools/eval/mobility_node.py` `sink_track_start/step/copy`, `_replay_send_base`, `reuse_base`, `_replay_base_delta` |
| source egress load of the live log | `osdi/m3e0/e0_report.json` (final task log bytes / readiness); `node_A/network.csv` tx means |
| deployment model (site uplinks, non-blocking core) | `osdi/expT/deployment_model.md` |
| audit of M3 status and the naming collision | `osdi/m3_audit.md` (69df6b33) |
| fluid model provenance | `tools/eval/restore_model.py`; validation in `restore_fulle_notes.md`, `restore_dissem_hetero_notes.md` |
