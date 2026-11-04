# E9 [A11] memory-policy sensitivity: protocol DRAFT 1 (2026-11-03; NOT frozen; nothing implemented or run)

Labels: [V] verified in code or records, [H] expectation, [A] modelling assumption, [D] open decision.
Status: exploratory. It does not re-judge CL-H1 / CL-H2 / CL-H3 (`preregistration.md`, FROZEN; section 13 discloses
[A11]). Results are SIMULATED.

## 1. Why (user, 2026-11-03)

The Fig. 14 memory audit (`../fig14/preregistration.md` section 11) found that E9's store differs from the testbed:

| | E9 `Store` ([A11], idealized) [V] | testbed [V] |
|---|---|---|
| copies per (site, session) | one: the retained or the staged version (a put replaces it) | former owner: two of the same version (M2 retained buffer + M3 entry-store copy); otherwise one (staged entry) |
| new owner | drops its copy | keeps its staged copy |
| budget / eviction | per-site budget M, LRU | none; everything is held until the session ends |
| Fig. 11 four-node chain | 3 x Sink | 7 x Sink (measured) |

Neither 3 x (E9) nor 7 x (the prototype) is claimed to be M3's intrinsic requirement. This protocol measures how much
E9's conclusions depend on the idealized store.

## 2. Memory policies (only the store's accounting changes; workload, topology, links, mobility, seeds unchanged)

| id | name | store | budget | what it stands for |
|---|---|---|---|---|
| I | A11-idealized | one copy per (site, session); owner drops; LRU | M = 0 / 8 / 32 / 128 GB | the frozen E9 model (re-run only to add record-only counters, section 5) |
| I-inf | idealized, unbounded | as I | none | reference for U's performance |
| U | A11-implementation, unbounded | per (site, session) two slots: `retained` (written when the session leaves the site) and `entry` (M3 handover copy of the same version at a former owner, or a staged forward); the owner keeps both; a newer version replaces a slot's older one; both freed only when the session ends | none (the testbed has no budget) | the testbed's retention behaviour |
| B | implementation accounting under a budget [A12] | U's slots as separate allocations; LRU over individual slots under M | M = 0 / 8 / 32 / 128 GB | a NEW policy (the testbed has no budget enforcement); never called the implementation |

Rules per method:
- OTTER: as in the table.
- Unstaged (OTTER without staging; M1 + M2 only): U / B keep one `retained` slot per (site, session), also at the
  owner; no entry slot (no M3 on the testbed in that configuration [V]).
- Replicate: no testbed implementation exists, so it keeps the idealized accounting in every policy. This is the
  conservative direction for OTTER and is stated with every comparison.
- Full, Llumnix, SLLM do not use the store (budget 0, no puts, no staging; `cluster_sim.py` lines 320, 497-499, 597) [V]; run once per cell for the ranking.
- A version usable at a site is the newer of its slots (U, B), as on the testbed, where the destination builds the
  base from whichever copy matches.

**Feasibility, not performance, for the implementation under a budget.** U has no budget, so its performance is that
of unbounded retention. Its memory trace is compared with each M afterwards (section 4, item 4): "would the prototype
fit in M?" B answers a different question ("if a budget with LRU were enforced on the prototype's duplicated store")
and is labelled [A12] wherever it appears.

## 3. Grid and pairing

- The frozen primary grid: E 16, G 8, N 32 / 64 / 96 / 120, C 1 / 10 / 25 Gbps, dwell 60 / 180 / 600 s, k 4,
  seeds 0 / 1 / 2, 2.5 simulated hours, 30-min warm-up. Primary point N 64, C 10 Gbps, dwell 180 s.
- M: I and B at 0 / 8 / 32 / 128 GB; analysis first at M 8 and 32 (user), all four reported.
- Runs: I 2,592 (frozen grid, all methods) + I-inf 324 + U 324 + B 1,296 (OTTER, Unstaged, Replicate) = 4,536;
  about 2-5 h on the Mac (frozen sweep 1-3 h).
- **Pairing check P0.** The simulator draws mobility, lifetimes and refreshes from one RNG stream [V]. A run records a
  hash of its user-move trace (time, session, site) and of its session arrivals. Paired runs (same cell and seed,
  different policy) must have equal hashes. If they differ (an RNG draw depends on the served state), the comparison
  is reported as "same seeds, traces not identical", with the share of differing moves; changing the RNG layout would
  change the frozen I results and needs a user decision.

## 4. Metrics (all SIMULATED; per run, medians over seeds as in E9)

1. Cumulative stalled seconds per session-hour (existing).
2. Migration completion rate: completed / started (existing counters).
3. Non-local service time: remote and stall seconds per session-hour (from the existing shares), and delay per move
   (existing; CL-H2's quantity).
4. Memory:
   - per site: time mean and peak (existing);
   - cluster-wide: sum over sites, time mean and peak (new, record-only);
   - U only, feasibility: per M in {8, 32, 128} GB, the share of site-time with held bytes > M, the number of sites
     that ever exceed M, and the cluster-wide peak / (E x M).
5. Staging admission and eviction (new, record-only): puts by kind (retain, handover, stage), puts rejected
   (budget 0 or a copy larger than M), evictions by victim kind, copies evicted before any use, staging flows started /
   landed; the reuse ratio (existing).
6. Method ranking: the order of the six methods by stalled seconds per session-hour, and of OTTER / Unstaged /
   Replicate by delay per move, per policy, at the primary point and per cell.
7. U / I-inf ratios of the cluster-wide mean and peak memory (the cluster-scale analogue of Fig. 14's 7 / 3).

## 5. Implementation plan (after review; not started)

- `cluster_sim.py`: a `mem_policy` key (`ideal` default, `impl`, `impl_budget`); `ImplStore` with the two slots;
  record-only counters and the cluster-wide memory integral in both stores; the move / arrival trace hash.
- **Regression gate R0** before any sensitivity run: with `mem_policy = ideal`, the frozen primary sweep is
  reproduced bit for bit on every existing metric (`sweep_primary.json`), and `validate` gives the same 76 / 76 values.
  Any difference stops the work.
- **Unit check R1:** the Fig. 11 four-node chain replayed in the simulator (`replay_testbed`, staging on) ends with
  7 x Sink under U and 3 x under I, matching the measured / modelled counts in section 1.
- Outputs: `a11_sweep.json`, `a11_results.md` (tables per section 4), no new figure unless asked.

## 6. Expectations [H] (written before any run; none decides anything)

- H-a: U's performance equals I-inf's on every metric except memory; at N 64 also I at M 128, because the idealized
  site peak there (91.6 GB, frozen sweep) stays below 128 GB.
- H-b: U's cluster-wide memory is 1.5-2.5 x I-inf's.
- H-c: at the primary point U exceeds 32 GB on most sites and 128 GB on some: the prototype as is would not fit the
  budgets E9 sweeps.
- H-d: B lowers OTTER's reuse ratio at M 8 / 32 versus I, but delay per move changes by less than 1 s, because at
  10 Gbps OTTER's delay per move is 12.8-13.2 s for every M including 0 (frozen sweep).
- H-e: CL-H2's two conditions still hold under B at the primary point (OTTER's delay at M 0, 13.15 s, is already below
  Replicate's 14.3 s), and the stalled-time ranking is unchanged.

## 7. Reading the outcome (user's three cases; thresholds [D])

Judged on B vs I (the only budgeted comparison), with U's feasibility reported next to it. A "flip" is a cell
(N, C, dwell) at a given M where CL-H2's two conditions hold under I and not under B, or where OTTER's stalled-time
rank changes.

| case | rule | follow-up (user) |
|---|---|---|
| 1. advantage kept | no flip at the primary point at M 8, 32, 128, and flips in at most 10 % [D] of the cells at each M | report E9 with the sensitivity next to it |
| 2. reversal only at small budget | flips at M 8 only (at the primary point, or in more than 10 % of cells), none of case 3 | state that memory regime as a limitation |
| 3. broad reversal | a flip at the primary point at M 32 or 128, or flips in more than 10 % of cells at M 32 or 128 | re-examine E9's scalability claim |

- Unfavourable results are reported as they are; the model is not adjusted after seeing them.
- CL-H2 keeps its frozen verdict; the paper states that it depends on [A11] and gives this sensitivity.
- E9's change history (smoke-informed CL-H1 reformulation, D8 re-measurement) is cited with this protocol's dates:
  drafted 2026-11-03 after the Fig. 14 audit, before any sensitivity run.
- The same [A11] applies to the scale-out / fanout DRAFT (`scalability_draft.md`); it inherits the policy chosen here.

## 8. Decisions for the user

| # | question | proposal |
|---|---|---|
| A1 | B's eviction rule | LRU over slots (the same rule as I, so only the accounting differs); admission rejection instead is a second [A12] variant, not proposed |
| A2 | Replicate's accounting | idealized in every policy (no implementation to model; conservative for OTTER) |
| A3 | flip threshold in section 7 | 10 % of cells |
| A4 | when to run | implement + R0 / R1 after the freeze; run with E9's final simulation step (user's order) |
