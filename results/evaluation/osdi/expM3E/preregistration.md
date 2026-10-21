# Experiment M3E - final OTTER (M3-v2) end-to-end validation: preregistration DRAFT (2026-10-20)

Status: **DRAFT, not frozen. Nothing implemented or run.** No frozen result (ExpD, W / R / N, V, A, B, VACW, RD) is
modified. Open decisions are in section 10 and must be closed before the freeze.

## 1. Purpose and evidence classes

The paper's M3 is the frozen M3-v2 planner (`reuse_dyn2`, freeze e39609a). Its GPU evidence so far is single-move only
(V holdout, dog). The end-to-end numbers of Experiment D that motivate M3 (G6 contention, G7 re-planning) were produced
with M3-v1 (`reuse_dyn`). M3E re-measures those configurations, and adds negative cases, with the final implementation.

| class | source | role here |
|---|---|---|
| **historical M3-v1** | ExpD (81bb628): B, E (G6), F (G7), G; N cells 1-10 | prior evidence and predictions; never pooled with M3E data; any comparison with them is descriptive and labelled cross-commit |
| **M3-v2 development / holdout** | N cells 7-10 regressions (`m3dev*`, development data), V holdout (`expV*`, 96 runs) | prior evidence for v2's single-move behaviour; not re-counted |
| **new end-to-end** | M3E runs (this document) | the only data the M3E verdicts use |

Scope (unchanged from ExpD section 2 and frozen M2): **one Sink snapshot per restoration** (frozen `split`; no VACW);
repeated mobility at rho = 2 (T_m = 7.025 s < T_s = 14.05 s), so no intermediate owner binds before it is left. A run
with an owner-side Sink promotion before the final bind, any fragment-version rejection or a digest mismatch is
flagged and is NOT EVALUABLE for every hypothesis (W / R / N rule).

## 2. Policies (identical transport, fragment table, move schedule)

| name | code | role |
|---|---|---|
| M1 only | `restart` | baseline: the source re-sends the whole Sink to each owner |
| M1 + frozen M2 | `split` | progress preserved, fixed provider order (newest holder, then source) |
| **OTTER (M3-v2)** | `reuse_dyn2` (frozen parameters, `--dyn_probe 4`) | system under test |
| OTTER at moves | `reuse_aware_in` | **only in S2**, to reproduce G7's primary comparison (event-driven vs at moves); see D2 |

M3-v1 (`reuse_dyn`) is not re-run (D1). No placement in any scenario (as ExpD B / E / F / G).

## 3. Common configuration

elves-01..04 GPU 0 (A = elves-01 initial owner and Sink source), dog clip, prompt "A dog walks on the grass, realistic",
seed 0, k = 2, 4 MiB fragments (412 per Sink), trigger at chunk 30, path A -> B -> C -> D, rho = 2 (T_m = 7.025 s), all
per-node caps 1 Gbps unless a cap event says otherwise, warm destinations, `--post_chunks 400`, `--max_run_s 600`
(restorations through a 62.5 Mbps link take ~110 s). 3 repetitions per (scenario, policy).

## 4. Scenarios

| id | reproduces | condition | class | policies |
|---|---|---|---|---|
| **S1** | ExpD E / G6 | hybrid contention: the GPU session plus 3 network-level restoration sessions from the same source A (`--hybrid_net 3`) | source-egress contention | M1 only, M1 + M2, M3-v2 |
| **S2** | ExpD F / G7 | C's egress drops to 62.5 Mbps when D holds 50 % of the Sink (`D>=0.5:C:out=62.5`) | **holder bottleneck, alternative available** (the source holds every fragment) | M1 only, M1 + M2, M3-v2, OTTER at moves |
| **S3** | new (N cell 10 class, repeated mobility) | D's **ingress** drops to 62.5 Mbps when D holds 50 % (`D>=0.5:D:in=62.5`) | **shared-ingress bottleneck: reassignment cannot help** (negative case) | M1 only, M1 + M2, M3-v2 |
| **S4** | ExpD B rho 2 / G7 no-change clause | no network change | **no change** (false-positive regression check) | M1 only, M1 + M2, M3-v2 |
| **S5** | new (N cell 8 class, repeated mobility) | A's egress drops to 62.5 Mbps when D holds 50 % (`D>=0.5:A:out=62.5`) | **source bottleneck: fragments only A holds cannot move** (negative case) | M1 only, M1 + M2, M3-v2 |

S1 note (as ExpD): only one session generates; the three network sessions are network-level (`restore_node.py`),
their planner is the network-level mapping of the GPU policy (`hybrid_net.NET_POLICY`: `restart` -> restart, `split`
-> reuse_fixed, `reuse_dyn2` -> **reuse_dyn (v1)**, because v2 is not implemented in the network-level harness; see D3).

## 5. Metrics (per run; all exist in the harness unless marked new)

- TTFO after the final move; Sink verified; **Sink bind-ready** (= continuity-ready: first chunk with the Sink bound,
  the frozen ExpD / N / V definition) after the final move.
- Source egress bytes (B_source, Sinks) and **total network bytes** (all fragment bytes on all links, Sinks); discarded /
  duplicate bytes.
- Re-plans and probes (count, time after the move, fragments moved, estimator state), duplicates.
- Completion and validity: stop reason, every fragment verified, final digest, version events, NIC checks, commit,
  GPU 0 idle before the run.
- **GPU service interference (new aggregation, existing data):** median chunk service time (`chunk_s`) at the final
  owner over the calls between the final move and the bind, and over the 20 calls after the bind.
- S1 only: completion time of each network session (reported separately; never merged with the GPU session).

## 6. Hypotheses (medians over 3 valid reps per policy; thresholds fixed at the freeze)

| id | scenario | success (all clauses) | failure | prediction (source) |
|---|---|---|---|---|
| **H1** contention | S1 | M3-v2 bind-ready <= M1 only - 3.5 s (G6 threshold) **and** <= M1 + M2 + 1.0 s; M3-v2 B_source <= M1 + M2 + 0.05 | any clause | v2 ~43 s vs M1 only ~57 s (ExpD G6: 42.8 / 43.1 / 57.1 s, v1); 0 re-plans |
| **H2** holder bottleneck | S2 | M3-v2 bind-ready <= 0.5 x OTTER at moves **and** <= 0.5 x M1 + M2; <= 2 re-plans and <= 1 probe (<= 4 fragments) per run; 0 duplicates; B_source <= 1.35 (removes >= 2/3 of M1 only's ~1.0 redundant Sink) | any clause | v2 16-21 s (G7 v1: 15.8 s; V2 / V4 / V5: v2 +0-4 s vs v1); B_source ~1.2-1.3 (v1 1.19; v2 in V2 1.31); at moves ~52 s; M1 + M2 ~78 s |
| **H3** no harm, ingress | S3 | M3-v2: 0 re-plans and <= 1 probe per run; bind-ready <= M1 + M2 + 1.0 s; B_source <= M1 + M2 + 0.02 | any clause | 0 re-plans (V6, V8); all policies ~120 s |
| **H4** no change | S4 | M3-v2: 0 re-plans and 0 probes in every rep; bind-ready within 1.0 s of M1 + M2; B_source <= M1 + M2 + 0.01 | any clause | 0 re-plans (V1); ~15.1-15.5 s |
| **H5** no harm, source | S5 | as H3 against M1 + M2 in S5 | any clause | 0 re-plans (V7); v1's N cell-8 harm (+3.5 s) absent |
| **H6** resumption | S1-S5 | M3-v2 TTFO <= M1 + M2 TTFO + 0.2 s in every scenario | any scenario | ~0.9-1.0 s after the final move in all (ExpD B / E / F) |
| **H7** GPU interference | S1-S5 | M3-v2's median chunk service time (final move -> bind) within 2 % of M1 + M2's in every scenario | any scenario | < 1 % (ExpD G9: +0.10 % steady state) |

Reported next to the verdicts, never as pass conditions: M3-v2 vs M1 only in S2 (M1 only avoids the degraded holder by
construction and may bind sooner, at ~2.0 Sinks of source traffic: ExpD F 15.4 s, 2.02 Sinks); total network bytes
(expected equal across progress-preserving policies, ExpD G3); S1 network-session completion times; historical v1
numbers for the same scenario (labelled cross-commit).

**NOT EVALUABLE** for a hypothesis: fewer than 3 valid reps of a compared policy after <= 2 re-runs
(`followup_common.md` section 3); an applicability flag (section 1) in any compared run; for H2 / H3 / H5, the cap
event not fired in a run (the progress trigger must fire once). Censoring: a restoration not finished by `max_run_s` is
right-censored at its elapsed time (censored order-statistic median, `followup_common.md`).

**Overall reading (fixed now):** M3-v2 is reported as the paper's end-to-end M3 if H1, H2, H4 are supported and H3 and
H5 are not failed (supported or NOT EVALUABLE with the reason stated). Any failed hypothesis is a stated limitation of
the final system in that scenario class; a failure of H3, H4 or H5 is a **regression against frozen M2** and must be
reported as such, not explained away. H6 / H7 failures are reported as overheads.

## 7. Negative cases and regression risks (recorded before any run)

- **S3, S5** are designed so that no provider reassignment can shorten restoration; any re-plan there is a false
  positive (v1 made 28-32 in N cell 10 and lost 3.5 s in N cell 8).
- **S4** checks false positives without any change (v1 re-planned once under incorrect placement, N cell 7; v2 had 0 in V1).
- **S1** is a new risk for v2: shared source egress among four restorations makes the GPU session's measured rates
  fall without a link change; v2's bottleneck estimator was developed on single-session data (N, V) and has not seen
  this contention. A probe or re-plan in S1 is reported with its estimator state.
- **S2 vs M1 only**: M3-v2 is expected to be slower than M1 only (which never uses the degraded holder); this is
  reported, not hidden.
- **Repeated mobility for v2** (state reset at every ownership change, estimator warm-up per move) is first exercised
  here; V was single-move.

## 8. Run counts, runtime, testbed occupancy

| scenario | policies | runs (3 reps) | per run (estimate) |
|---|---|---|---|
| S1 | 3 | 9 | ~2-2.5 min (restoration 43-57 s) |
| S2 | 4 | 12 | ~1.5-2.5 min (16-80 s) |
| S3 | 3 | 9 | ~3 min (~120 s) |
| S4 | 3 | 9 | ~1.5 min (~15 s) |
| S5 | 3 | 9 | ~3 min (~120 s) |
| **total** | | **48** | |

Plus one orchestrator invocation per scenario (node start with the 330-call baseline, ~4 min each). Estimated
**~2.5-3 h of exclusive use of GPU 0 on all four hosts** (S1 also runs the network-level restore nodes on all four
hosts), plus a shakedown before the sweep (one run per policy per scenario, 16 runs, ~45 min; inspected, not evidence).
No commit or pull on the testbed while it runs.

## 9. Implementation required before the freeze is executed (not started)

1. Driver subcommand (`run_wrn.py m3e` or a new driver) with the five scenario configurations; M3-v2 with `--dyn_probe 4`.
2. Aggregator: hypotheses H1-H7, censoring, NOT EVALUABLE rules, the chunk-service-time aggregation (H7), historical v1
   columns labelled cross-commit.
3. Loopback dry run of every scenario (including M3-v2 with hybrid sessions and progress-triggered cap events on
   repeated mobility, which no previous v2 run exercised) before any GPU run.
No change to M1, M2, M3-v2 or their parameters.

## 10. Open decisions (close before the freeze)

- **D1** - re-run M3-v1 (`reuse_dyn`) as a same-commit reference in S1-S5 (+15 runs, ~45 min)? Without it, v1-vs-v2
  statements rest on cross-commit comparisons with ExpD / N. Recommended: no (the paper's M3 is v2; v1 stays historical).
- **D2** - keep OTTER at moves in S2 only (G7's primary comparator)? Recommended: yes.
- **D3** - S1 network sessions use the v1 network-level planner under the v2 GPU policy (current mapping), or implement
  v2 in `restore_orchestrate.py` (code change, new regression test)? Recommended: keep the mapping and state it; the
  hypothesis concerns the GPU session.
- **D4** - a second workload for S2 (holder bottleneck), e.g. butterfly-feeding-slow-motion (+12 runs)? Its Sink
  promotes frequently but no intermediate owner binds at rho 2, so the stable-snapshot scope holds. Recommended: only if
  the time budget allows; dog keeps comparability with ExpD.
- **D5** - include ExpD G (revisit A -> B -> C -> D -> B) as a sixth scenario (+9 runs)? Recommended: no; v1's revisit
  result stays historical, v2 has no revisit-specific logic.
