# Formal concurrency experiment: design (DRAFT 2, 2026-11-04; not frozen, nothing run)

Basis:
- Pilot stages 1-2 (`pilot_protocol.md` sections 10-15).
- The user's decisions on DRAFT 1 (section 0).

DRAFT 1 (1fde7a19) is superseded. M1 / M2 / M3, the frozen M3-v2 planner (e39609a), the frozen claims and Fig. 7-14
are unchanged. Nothing here is frozen or run before the user reviews this draft.

## 0. User decisions

On the pilot (2026-11-04):

| item | decision |
|---|---|
| Stage 2 feasibility | PASS |
| C4 2 x 2 | valid pilot observation |
| extra pilot cell (S2 at 90 s) | not run |
| required | the formal experiment measures the cost M3 moves onto another session |
| required | staging contention and migration contention are separate experiments, each with a stated causal comparison |
| required | M3 is not judged by summed readiness; readiness, continuity, locality, link use and fairness are reported apart |

On DRAFT 1 (2026-11-04):

| item | decision |
|---|---|
| F1 work-conserving coordinator | approved: implement and regress first. Three requirements:<br>(1) a flow whose transfer has ended leaves the allocation at once;<br>(2) a new round re-registers it and re-rates the others;<br>(3) the survivor's return to the full rate is shown on real transfers, not only in the allocation |
| F1 records | pilot results kept as they are; the new coordinator's verification recorded separately; never compared as one harness |
| F2 | dog only |
| F3 | X1 60 runs (5 reps for 1 and 2 sessions) |
| F4 | X1-H2 and X2s-H2 / X2m-H2 relaxed to medians; X2m contention overlap is evidence, not validity |
| F5 | X2 first, then X1 |
| F6 | S2-alone included; same offsets as the concurrent cells |
| added | X2m records whether D held the staged Sink when S2 started |
| added | X2s cost and X2m gain are never added or netted |
| freeze | after DRAFT 2 review |

## 1. Questions and the three results the experiment is for

- **RQ-C1 (X1).** Does OTTER keep service continuity when two sessions migrate at once over one shared 1 Gbps
  link? (Fig. 12 varies bandwidth; X1 varies the number of sessions on the link.)
- **RQ-C2 (X2s, X2m).** What does M3 staging gain for its own session, and what does it cost another session?
  - (s) when the other session migrates while S1 stages;
  - (m) when it migrates while S1 migrates.

Expected contributions, each tested by one experiment:
1. OTTER's output gap does not grow much with concurrency (X1).
2. Proactive staging can delay another session's migration readiness while both sessions keep their output
   continuity (X2s).
3. Staging done ahead of time reduces the next migration's traffic, which eases contention with another session
   (X2m).

Together, 2 and 3 describe M3 as **moving bandwidth use earlier in time, not removing it**. How it affects another
session depends on when that session migrates.

## 2. Pilot facts the design rests on (measured, `pilot_protocol.md` 14-15, event logs)

| fact | value |
|---|---|
| S1 Chain moves (A -> B, B -> C, C -> D) start on a fixed clock, 0 / 45 / 90 s after the first move, in both arms | coordinator logs: x1 0.0, x2 45.0, x3 90.0 s (M3 and no M3) |
| M3's forward A -> D (1.71 GB) starts at the move to C | 45.1 s; ended 72.8 s at 500 Mbps (contended); 2 small forwards C -> A / C -> D (19 MB) |
| S1's C -> D pre-copy with M3 sends 12 MB in 1.45 s (D already holds the Sink) | `xb_precopy_round` |
| S1's C -> D pre-copy without M3 sends 1.73 GB in 16.6 s | `xb_precopy_round` |
| S2 (elves-03:1 -> elves-04:1) shares elves-03 egress and elves-04 ingress with S1's C -> D, and elves-04 ingress with the A -> D forward | placement |
| without M3, S1 never shares a NIC direction with an S2 started at +45 s | `C4_nom3_conc`: 0 shared seconds |
| pilot coordinator: a flow stays registered after its last byte until the switch closes the task: 5-9 s per pre-copy; the M3-arm C -> D sent 12 MB by 1.9 s and stayed registered to 9.9 s (8 s idle) | events vs coordinator log |
| source egress in that tail: mean 8-30 Mbps, largest 1 s sample 84 Mbps (replay log, refresh patches) | `node_*/network.csv`, C1 and C4 runs |
| one single-migration cell (incl. reference regeneration) about 18 min; one Chain cell about 13-17 min | run directory timestamps |

## 2b. F1: work-conserving coordinator (implemented 2026-11-04; harness only)

**Mechanism.** Opt-in flag `--coord_tail_mbps T`. With 0, the default, nothing changes and the pilot behaviour is
reproduced.
- **Bulk vs tail.** A registered transfer is *bulk* while it has its payload to send. It becomes a *tail* when:
  - pre-copy: its last round's send ends (the node's own switch rule: dirty bytes <= threshold, round limit, or no
    shrink);
  - R-full input stream: no input part is in flight.
- **Requirement 1 (leave at once).** The orchestrator registers a tail as soon as the node's round event arrives,
  within one poll (0.25 s), and applies the new rates at once.
- **Allocation.** One max-min over all flows of all sessions, where a tail's demand is capped at T (water-filling).
  - The bulk flows share what is left.
  - With no tails, this is `restore_planner.maxmin` itself (the same code path, the same rates).
- **Pacing.** A tail is paced at the residual capacity of its path: cap minus the other flows' accounted rates.
  - A lone tail keeps the whole cap, exactly as today, so a single session is unchanged.
  - A tail never holds capacity it does not use.
- **Requirement 2 (re-register).** A new input part puts its stream back to bulk and re-rates everyone. A
  non-final pre-copy round never leaves bulk.
- **M3 forwards and Full transfers** close when they finish, as before.
- **Accounting.** The coordinator logs, per allocation:
  - accounted rates, whose sums are checked against the cap (`cap_ok`);
  - pacer rates.

**T = 100 Mbps** (proposal; decision D1). This is above the largest 1 s tail sample, 84 Mbps.
- Bulk + tail on one link: the bulk flow gets 900 Mbps; with the pilot coordinator it got 500.
- A tail that needed more than T would be slowed. The run's tail rate is in the NIC log, and the report flags any
  tail interval whose source NIC reached T.

**Known residual (stated, not repaired).** A bulk round that is sender-bound rather than link-bound keeps its full
share while it sends slowly. Example: the M3-arm C -> D sent 12 MB in 1.45 s. This lasts at most the round, about
1.5-1.9 s in the pilot.

**Records.**
- New runs use the condition prefix `WC`, and coordinator logs `coord_WC*`.
- `conc_report.py` (pilot) ignores `coord_WC*`. Its pilot tables are regenerated byte-identical.
- The pilot and formal results are never pooled or compared as one harness.

**Verification.**

| check | status |
|---|---|
| `rate_coord.py selftest`: tail -> other 900 Mbps; lone tail = cap; back to bulk 500 / 500; no demands = `maxmin` | ALL PASS |
| `test_rate_coord.py` (replay, flag off): Fig. 7 / 12a 48 tasks, Fig. 11 180 M3 points identical | ALL PASS |
| `run_conc.sh dry_wc` (two dry sessions on real loopback transfers, 200 Mbps cap since the Mac dry sender is not pacer-bound near 1 Gbps; T 20): tails registered 0.01-0.26 s after the send ended; S1 alone 200 -> achieved 196, shared 100 -> 98; S2 100 -> 96, raised to 180 when S1 tailed -> **174 achieved**; accounted sums <= cap | ALL PASS (`check_wc.py`) |
| return to the full rate while the survivor still sends (requirement 3): not reachable with dry nodes (dry S1 does not switch until after S2's bulk), so it is part of `wc_live` | pending |
| `dry_coord1`, one session (Fig. 11 Chain dry, every method + M3) through the coordinator, flag off | 34 / 34 allocations identical to today's rule |
| `dry_coord1` with the flag on (T 100) | 40 / 40 identical (6 more = tail entries; a lone tail is paced at the cap, and no tail shares a link with another flow of its own session) |
| `dry_coord` (two sessions, flag off) | unchanged: 4 allocations, 500 / 500, sums <= cap |
| `conc_report.py` (pilot) after the change | output byte-identical |
| `test_xb` on the Mac | **not conclusive**: this Mac's Python has no PyAV, so the codec checks fail and the test stops at recompute_full; identical failures on the unchanged HEAD (baseline run), so not caused by F1. To be run on elves-01 (`.venv`, PyAV present) before `wc_live` |
| **`run_conc.sh wc_live` on the testbed (C3b placement, OTTER / OTTER, dog, T 100, S2 at +8 s; about 20 min)**: S2 expected 500 -> 900 -> 1,000 Mbps achieved within 10 %, host NIC burst <= 1.15 x and 10 s <= 1.05 x | needs a run by the user |

## 3. Experiment X1: continuity under a shared link (extends C3b)

Placement: S1 elves-01:0 -> elves-03:0 and S2 elves-01:1 -> elves-03:1 (C3b), on one shared 1 Gbps egress at
elves-01 and ingress at elves-03 through the work-conserving coordinator. Fig. 7 single-migration configuration;
triggers aligned (`--barrier`, offset 0).

| factor | levels |
|---|---|
| method (both sessions the same) | Full, R-full, OTTER |
| input (both sessions the same) | dog (low refresh), butterfly (high refresh) |
| sessions on the link | 1 (S1 alone, through the coordinator), 2 (S1 + S2) |
| repetitions | 5 |

60 runs, about 18 h.

**Causal comparison.** For one method and input: 2 sessions vs 1 session on the same link, same placement, same
day, interleaved. The only difference is the second session's traffic and host load. Secondary: the methods
compared within the 2-session condition.

Metrics per session:
- max output gap (primary), cumulative stall, TTFO-local;
- completion, served calls / s in the migration window, bytes;
- active-send overlap;
- coordinator and NIC checks.

Hypotheses:
- **X1-H1 (primary).** OTTER, each input:
  - median max gap with 2 sessions <= 1.25 x the median with 1 session;
  - and no 2-session OTTER session > 1.5 x that median.
  - Every run's gap is shown (strip of individual runs next to the medians).
  - Pilot dog: 1.64-1.67 vs 1.61 s (1.04 x).
- **X1-H2.** With 2 sessions, OTTER's median max gap is lower than Full's and lower than R-full's, for each input.
  Every run is reported.
- **X1-D (descriptive).** 2-session / 1-session ratios of TTFO-local, stall and throughput per method.

## 4. Experiments X2s and X2m: M3's gain and its cost to another session

Common:
- S1 = Fig. 11 Chain A -> B -> C -> D (GPU 0 of elves-01..04, moves at 45 / 90 s, dog).
- S2 = one OTTER migration elves-03:1 -> elves-04:1 (dog).
- Every cell runs through the work-conserving coordinator. S2 starts by barrier offset.

| cell | S1 arm | S2 | S2 start | serves |
|---|---|---|---|---|
| A-M3 | M3 | none | - | S1 alone, both experiments |
| A-noM3 | no M3 | none | - | S1 alone, both experiments |
| S2-alone-s | none | alone | +45 s | S2 reference for X2s |
| S2-alone-m | none | alone | +90 s | S2 reference for X2m |
| s-M3 | M3 | yes | +45 s = start of S1's forward A -> D | X2s |
| s-noM3 | no M3 | yes | +45 s | X2s |
| m-M3 | M3 | yes | +90 s = start of S1's C -> D move | X2m |
| m-noM3 | no M3 | yes | +90 s | X2m |

- 8 cells x 5 reps = 40 runs, about 11 h.
- The two S2-alone cells differ only in the offset; with no S1, they should agree. Their agreement is reported
  (descriptive). Each concurrent cell is compared with the S2-alone cell of its own offset.

**Validity (all X2 runs; decided before any run, independent of the outcome).**
- S2's first transfer starts within 0.5 s of the S1 event it is aligned to:
  - X2s: S1's forward A -> D (M3 arm) or S1's x2 (no-M3 arm);
  - X2m: S1's x3.
- Both migrations complete.
- The coordinator tracks every transfer (registered, closed, in its log). Accounted sums <= cap at every allocation.
- NIC burst <= 1.15 x and 10 s <= 1.05 x of the cap.

**Contention evidence (reported for every run; never a validity rule).**
- Active-send overlap seconds on each shared host direction.
- Seconds a flow was allocated below its alone rate.
- Bytes sent while both flows were sending.
- The 10 s overlap of DRAFT 1 is kept only as a descriptive reference level. This applies to X2s too (DRAFT 1 used
  it as validity there as well): same reason, the overlap depends on the outcome.

**X2s, staging contention. Causal comparison: s-M3 vs s-noM3.**
- Same S1 schedule, same S2 placement and start time. The only difference is whether S1 stages.
- In s-noM3, S1 has no flow on S2's links in S2's window (pilot: 0 s). So the comparison is "S2 next to S1's
  staging traffic" vs "S2 next to S1 without staging traffic".

Measures:
- Cost to S2: S2 TTFO-local, gap and stall, s-M3 vs s-noM3 (and each vs S2-alone-s).
- S1's gain, always a difference of medians:
  - gain_alone = median R_D(A-noM3) - median R_D(A-M3);
  - gain_s = median R_D(s-noM3) - median R_D(s-M3).

Hypotheses:
- **X2s-H1.** gain_s >= 0.75 x gain_alone (pilot 13.15 / 13.15 s).
- **X2s-H2 (cost hypothesis: tests the expected cost of M3, not a benefit).** Median S2 TTFO-local(s-M3) >= 1.25 x
  median S2 TTFO-local(s-noM3) (pilot 1.70 x). The difference and ratio of medians are reported whatever the
  outcome.
- **X2s-H3.** Median S2 max gap(s-M3) / median S2 max gap(s-noM3) <= 1.25 (pilot 0.98).

**X2m, migration contention. Causal comparison: m-M3 vs m-noM3.**
- S2 starts with S1's C -> D move in both arms (same clock time; validity rule above).
- S1's state at 90 s is the same, except that with M3 D already holds the Sink (staged at about 45-73 s, alone on
  the link).
- The difference is how many bytes S1's move puts on the shared link while S2 migrates.

**Staging-complete record.** At S2's start, each m-M3 run records:
- whether S1's forward to D had finished (`m3_forward_done` for the A -> D flow before S2's first transfer);
- the Sink version D advertised at the move (`RETAINED_VERSION` / M3 entry).

Such a run is not invalid if staging had not finished:
- It is reported as M3's actual behaviour and marked "not pre-staged".
- The hypotheses use all valid runs.
- If any run is marked, the pre-staged-only medians are given next to them and labelled. Only these support the
  "pre-staged migration" reading.

Measures:
- S1's move bytes in the window: C -> D pre-copy bytes, m-M3 vs m-noM3.
- Effect on S2: TTFO-local, gap and stall, m-M3 vs m-noM3 (and each vs S2-alone-m).
- S1: gain_m = median R_D(m-noM3) - median R_D(m-M3).

Hypotheses:
- **X2m-H1.** Median C -> D move bytes(m-M3) <= 0.10 x median(m-noM3) (pilot alone: 12 MB vs 1.73 GB).
- **X2m-H2.** Median S2 TTFO-local(m-M3) < median S2 TTFO-local(m-noM3). The effect size (difference and ratio of
  medians) is reported, with no threshold.
- **X2m-H3.** gain_m >= 0.75 x gain_alone.

**No netting across scenarios.**
- X2s and X2m are different arrival times of S2. Their results are never added or subtracted, for example "S2's
  X2s cost minus its X2m saving".
- No cluster-wide efficiency is inferred from them.

Each scenario is reported on its own:

| view | metric |
|---|---|
| migration readiness | S1 R_D; S2 TTFO-local, each vs its alone cell |
| user-visible continuity | max gap, cumulative stall, per session |
| locality | S1 N, N_post |
| link use | active-send seconds and bytes on each shared host direction, by flow kind (S1 staging, S1 move, S2) |
| fairness | per-session readiness degradation, concurrent / alone |

## 5. Order and stop rules (all experiments)

- **Order.**
  1. F1 regression;
  2. `wc_live` on the testbed, reviewed;
  3. freeze;
  4. X2 (rep blocks; cells within a block in a seeded random order, seed fixed at freeze);
  5. X1, likewise.
- **Invalid runs.** An invalid run is rerun once, and both records are kept (harness-bug precedent). Two invalid
  runs in one cell stop the experiment for a review.
- **GPU guard.** Each cell runs behind the guard with a 5-minute wait loop. The state of any GPU not used is
  recorded, not used as a rule.
- **Labels.** Measured (testbed). Two sessions do not validate the E9 cluster model; they inform its two-session
  sharing assumption only.

## 6. What the paper may say (scope)

- **Allowed now (pilot).**
  - Concurrent migrations on shared hosts run without OOM or substantial throughput loss.
  - In one pilot run, M3 kept S1's gain under contention, while S2's readiness rose by 70 % and both gaps stayed
    short.
- **After X1:** continuity under a shared link, if X1-H1 holds.
- **After X2:**
  - M3's gain, and its cost to other sessions, by the phase in which they contend.
  - OTTER's goal is service continuity, not jointly optimal readiness for every session. X2 shows the two
    separately.
- **Not claimed:**
  - that M3 improves cluster-wide efficiency;
  - that the planner is contention-aware (it is not);
  - that OTTER is optimal everywhere.

## 7. Decisions left before freeze

| # | question | proposal |
|---|---|---|
| D1 | tail reservation T | 100 Mbps (above the largest 1 s tail sample, 84 Mbps) |
| D2 | X2s overlap as evidence, not validity (extends the user's X2m rule to X2s) | approve |
| D3 | two S2-alone cells (+5 runs, about 1.5 h) | run both; their agreement is reported |
| D4 | `wc_live` outcome | user reviews it before the freeze |
