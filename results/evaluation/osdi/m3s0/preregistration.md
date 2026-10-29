# M3-S0: offline feasibility of lineage-staged restoration under repeated mobility (preregistration, 2026-10-29)

Fixed before any analysis run. Offline study: no GPU experiment, no change to the frozen M1 / M2 (47acbe44) or to the
M3-v2 planner. The one GPU step is a data extraction (section 3.1). Background: `../m3_topology_research.md`
(797e1d89), `../m3e0/m3e0_report.md`.

## 1. Hypothesis under test

*Given the measured version dynamics of the Sink, staging lineage-valid entries at candidate destinations before a
move, with the bandwidth actually left by the live log and the active migration, turns later migrations into delta
migrations that are ready before the next move at ρ = 1 and reduces remote serving and wasted transfer, under
realistic (two-candidate) uncertainty and not only with an oracle.*

Exactness is not under test (E8 / E10 verified ordered-shift reconstruction; M3-E0 classified 0 of 412 fragments
outside the shift / refresh classes). Timing, bytes and the ownership-aware timeline are.

Two stages, judged separately:
- **Feasibility**: can enough lineage-valid state be at the destination at its base boundary that the migration is a
  delta migration ready before the next move?
- **End-to-end benefit**: on the recomputed timeline, with ownership transitions, do remote serving and wasted bytes
  fall by the preregistered margins?

## 2. Corrections to the first design (`../m3_topology_research.md` section 9)

1. **Causal staging.** Staging starts at the earliest causally possible time: at t0 (the user has arrived at B; the
   migration A → B has started) the candidates for the *next* move are staged; after each move the candidate set is
   recomputed. Two knowledge levels are run and reported separately:
   - *oracle*: the next edge is known (upper bound);
   - *causal*: every node that is neither the user's edge nor the source is a candidate, staged uniformly (with four
     nodes: two candidates).
2. **Shared bandwidth.** All flows share the per-node caps of the harness model (1 Gbps egress and ingress, max-min
   fair, one link-efficiency factor η): the live log (demand-limited at the measured bytes per call), the active
   migration's base and every staging flow. Primary sharing is *fair* (what the harness would do). A *residual*
   variant (staging only from capacity left after base + log) is a sensitivity.
3. **Event-driven ownership.** When a migration's first output happens, the destination becomes the source of every
   later migration and the live log; the user is served locally while at that node; the old source becomes a holder
   whose entries carry the switch call as snapshot. If the user moves before readiness, the migration is cancelled
   after the measured cancellation lag and a new one starts from the current source.

## 3. Model and inputs

### 3.1 Lineage table (GPU data extraction, `tools/eval/m3s0_dump_events.py`)

One deterministic re-generation per workload (dog, butterfly; seed 0; the same procedure reproduced the M3-E0 source's
live fragment hashes 412 / 412), calls 25..140: per call the refreshed entries and the shift events; after each call
the 360 per-block checksums and the 412 fragment hash prefixes. The dump checks the lineage rule against the checksums
over every (s, t) pair: V block unchanged iff its entry not refreshed in (s, t]; K block unchanged iff additionally not
shifted. **Validity gate G0**: consistent fraction ≥ 0.999; otherwise the table is not used.

### 3.2 Simulator (`tools/eval/m3s0_sim.py`)

Fluid model at 20 ms steps. Units: entries (K + V of one slot-row, 9,584,640 B; 180 per Sink; the unit a
lineage-aware protocol would verify), metadata 2.40 MB per base.

| element | model | source of the constant |
|---|---|---|
| calls | call 30 at t0; period 0.615 s (source A) | M3-E0 metrics |
| moves | t0 + k·T_m, T_m = 14.05 / ρ | XB3 / XB4 |
| migration start | at the move (or after a cancellation); snapshot delay then c0 = source call | M3-E0 `round_snapshot_s` |
| validity at c0 | entry held with snapshot s is valid iff not refreshed in (s, c0] | lineage table |
| base | (invalid or missing entries) × 9.58 MB + metadata; one flow source → destination | E9 / E10 delta protocol |
| base ready | flow end + 0.40 s | M3-E0 |
| readiness | max(base ready + logged calls × catch-up per call, t(c0 + W) + 0.6 s), W = 12 | M3-E0 catch-up 0.116-0.121 s / call; E9 M2 8.74 s, E10 bfly M2 8.97 s |
| first output | readiness + switch | M3-E0 1.69-2.32 s |
| cancellation | at a move, after the measured lag (dog 0.4-0.6 s, butterfly 0.7-2.9 s) | M3-E0 |
| log | demand-limited flow source → destination at bytes/call ÷ period (dog 0.98-1.27 MB, butterfly 13.1-13.3 MB per call) | M3-E0 |
| caps | 1 Gbps × η per node direction, η = 0.88, water-filling | gate G1 |
| staging snapshot | a source-sent entry carries the call at which its transfer starts; a forwarded entry inherits the holder's snapshot | protocol definition (C1) |
| refresh during staging | primary *once*: the staged copy simply becomes invalid; variant *fresh*: the source re-sends the refreshed entry to active candidates | knob |

**Validity gate G1 (model vs measured, S0 = no staging, every configuration)**: cancellations equal; final base send
within 15 %; remote serving within 10 %; discarded bytes within 15 %. If G1 fails for a configuration, that
configuration gets no verdict.

### 3.3 Staging graphs (the four topologies as staging structures, plus the adaptive assignment)

Decision points: t0, every move, every cancellation, every ownership change, every finished staging flow. Each candidate's
missing entries (not held, not queued) are assigned:

| graph | who sends what to a candidate |
|---|---|
| **star** | the source sends every missing entry directly |
| **line** | the source sends to the first candidate; the first candidate forwards each entry to the second as it lands (pipelined) |
| **tree** | the holder with the most entries (hub) sends what it holds; the source sends the rest |
| **butterfly** | every holder with a lineage-valid copy and the source partition the missing set (fewest-assigned first; source for entries no holder has) |
| **adaptive** | per entry, the least-loaded valid provider by egress finish estimate, with the destination-ingress rule of `reuse_aware_in` |
| none | S0: no staging (reference); `none+retain` keeps cancelled partial bases for later same-node use |
| floor | every migration is metadata-only (oracle zero-base): the achievable timeline |

Matrix: 4 configurations (dog / butterfly × ρ 1 / 2) × 5 graphs × 2 knowledge × 2 sharing × 2 refresh handling,
plus none / none+retain / floor. **Primary policy for the verdict: causal / fair / once.** Oracle and the variants are
reported.

## 4. Measurements

Per run: timeline (moves, migration start / cancel / base ready / ready / first output, ownership changes, staging
flows); per migration: valid entries at c0, delta entries and bytes, readiness relative to T_m, outcome; remote and
local serving seconds; discarded bytes (cancelled migrations' base + log); staged bytes, wasted staged bytes (staged
at a node and never valid at a migration to it); total bytes; bytes by (kind, link).

## 5. Rules (applied by `m3s0_sim.py rules()`)

Achievable reduction of a configuration = S0 remote serving − floor remote serving (both simulated).

- **Feasibility (per configuration)**: some migration after the first has ≥ 90 valid entries (50 %) at c0, completes,
  and its readiness − start < T_m. Required under the primary policy for **both workloads at ρ = 1**.
- **End-to-end (per configuration, primary policy, some graph)**: captured fraction of the achievable remote-serving
  reduction ≥ 0.5; discarded bytes ≤ 0.5 × S0; total bytes ≤ 1.25 × S0; the final migration completes. Required for
  **both workloads at ρ = 1**.
- **ρ = 2 is descriptive** (expected infeasible: the Replay-W readiness floor ≈ 8.7-9.0 s exceeds T_m = 7.0 s).
- **Topology question (descriptive, preregistered reading)**: if the adaptive assignment is within 10 % of the best
  fixed staging graph in every configuration, staging-graph *selection* is not needed (as Experiment B found for
  dissemination); if a fixed graph beats the adaptive assignment by > 10 % anywhere, structure matters and the reason
  is reported from the flows.

| outcome | recommendation |
|---|---|
| G0 or G1 fails | no verdict; fix the model or report the discrepancy |
| feasibility and end-to-end hold (ρ = 1, both workloads, causal primary) | **GO**: proceed to a network-level staging run with the restore harness (no GPU integration yet) |
| feasibility holds but end-to-end fails under causal (or only under oracle) | **CONDITIONAL**: the mechanism depends on prediction quality; decide whether a mobility model is defensible before any implementation |
| feasibility fails for a workload under every graph, even with oracle | **NO-GO**: adopt migration admission (C3) and report repeated mobility as an M1 / M2 limitation |

## 6. Predictions (written before the analysis; not evidence)

- The Replay-W floor bounds every completed migration at ≈ 8.7-9.0 s readiness + 1.7-2.3 s switch ≈ 10.5-11.3 s of
  remote serving per move, so the achievable reduction at ρ = 1 is about 50.0 → ~35 s (dog) and 53.8 → ~37 s
  (butterfly), i.e. ~30 %; the first migration (A → B) cannot be staged and is cancelled as measured.
- Dog: refreshes are rare (0-4 blocks per 20-40 calls), so a causally staged candidate should hold ≥ 170 valid entries at
  its c0; feasibility expected for every graph; end-to-end captured fraction ≥ 0.5 expected under causal for star and
  butterfly; line / tree depend on whether a holder exists before the second move.
- Butterfly: 25-35 entries refreshed per 40 calls, so a `once` staged copy keeps ~80 % validity; delta ≈ 300-400 MB
  (3-4 s at the destination's ingress), still inside T_m; feasibility expected; end-to-end borderline because the
  live log (153-167 Mbps) and two-candidate staging share the source's egress.
- Two-candidate staging doubles staged bytes; wasted staging ≈ one base per move; total bytes likely > 1.25 × S0 for
  star / causal, closer to the bound for butterfly (holders carry part of the load).
- ρ = 2: infeasible for every policy (floor > T_m).
- Topology: adaptive within 10 % of the best fixed graph everywhere (as B); if anything separates them it will be
  tree's hub egress when the hub is also the active migration's provider.

## 7. Discipline

- No run until this file is committed; the rules and thresholds do not change after the first `--all` run.
- The lineage table is the uninterrupted trajectory's; after an ownership transition the model assumes the same
  refresh / shift sequence (a stated assumption; M3-E0 verified it for the uninterrupted source only).
- Every number in the report is labelled simulated, measured (constants) or recorded (lineage).
