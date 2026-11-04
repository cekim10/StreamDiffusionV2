# Formal concurrency experiment: design (DRAFT 1, 2026-11-04; not frozen, nothing run)

Basis: pilot stages 1-2 (`pilot_protocol.md` sections 10-15) and the user's decision of 2026-11-04 (section 0).
M1 / M2 / M3, the frozen M3-v2 planner (e39609a), the frozen claims and Fig. 7-14 are unchanged. Nothing here is
frozen or run before the user reviews this draft.

## 0. User decision (2026-11-04)

| item | decision |
|---|---|
| Stage 2 feasibility | PASS |
| C4 2 x 2 | valid pilot observation |
| extra pilot cell (S2 at 90 s) | not run |
| formal concurrency design | approved to draft |
| freeze | after design review |
| M1 / M2 / M3, frozen claims | unchanged |
| required | the formal experiment measures the cost M3 moves onto another session |
| required | staging contention and migration contention are separate experiments, each with a stated causal comparison |
| required | M3 is not judged by summed readiness; readiness, continuity, locality, link use and fairness are reported apart |

## 1. Questions

- **RQ-C1 (experiment X1).** Does OTTER keep service continuity when two sessions migrate at once over one shared
  1 Gbps link? (Fig. 12 varies bandwidth; X1 varies the number of sessions on the link.)
- **RQ-C2 (experiments X2s, X2m).** What does M3 staging gain for its own session, and what does it cost another
  session, (s) when the other session migrates while S1 stages, and (m) when it migrates while S1 migrates?

## 2. Pilot facts the design rests on (measured, `pilot_protocol.md` 14-15, event logs)

| fact | value |
|---|---|
| S1 Chain moves (A -> B, B -> C, C -> D) start on a fixed clock, 0 / 45 / 90 s after the first move, in both arms | coordinator logs: x1 0.0, x2 45.0, x3 90.0 s (M3 and no M3) |
| M3's forward A -> D (1.71 GB) starts at the move to C | 45.1 s; ended 72.8 s at 500 Mbps (contended), 2 small C -> A / C -> D forwards (19 MB) |
| S1's C -> D pre-copy with M3 sends 12 MB in 1.45 s (D already holds the Sink) | `xb_precopy_round` |
| S1's C -> D pre-copy without M3 sends 1.73 GB in 16.6 s | `xb_precopy_round` |
| S2 (elves-03:1 -> elves-04:1) shares elves-03 egress and elves-04 ingress with S1's C -> D and elves-04 ingress with the A -> D forward | placement |
| without M3, S1 never shares a NIC direction with an S2 started at +45 s | `C4_nom3_conc`: 0 shared seconds |
| a coordinator flow stays registered after its last byte until the switch closes the task: 5-9 s per pre-copy; the M3-arm C -> D sent 12 MB by 1.9 s and stayed registered to 9.9 s (8 s idle) | events vs coordinator log |
| one single-migration cell (incl. reference regeneration) about 18 min; one Chain cell about 13-17 min | run directory timestamps |

**Consequence of the last-but-one row (harness, must be fixed before X2m).** The coordinator divides the cap over
registered flows, not over flows that are sending. A flow idle in its switch tail still holds its share. In X2m this
would hold S2 at 500 Mbps for about 8 s while M3's S1 sends nothing, i.e. a bias against M3 in exactly the
comparison X2m makes. A real shared link is work-conserving. Proposed fix (harness only, needs approval, section 7):
a transfer is registered only while it has bytes to send (close at the end of a pre-copy round's send, reopen if a
further round starts). The pilot is not affected in its conclusions: in `C4_m3_conc` both shared flows were sending
for the whole 27.9 s (S2's round ended at 30.0 s after its start, the forward at 72.8 s; S2's tail had no partner on
elves-04). The pilot's "below alone" seconds counted registration and are an upper bound; the formal report also
gives active-send overlap (round start = end - `send_s`), which needs no harness change.

## 3. Experiment X1: continuity under a shared link (extends C3b)

Placement: S1 elves-01:0 -> elves-03:0, S2 elves-01:1 -> elves-03:1 (C3b), one shared 1 Gbps egress at elves-01
and ingress at elves-03 through the coordinator. Fig. 7 single-migration configuration, triggers aligned
(`--barrier`, offset 0).

| factor | levels |
|---|---|
| method (both sessions the same) | Full, R-full, OTTER |
| input (both sessions the same) | dog (low refresh), butterfly (high refresh) |
| sessions on the link | 1 (S1 alone, through the coordinator), 2 (S1 + S2) |
| repetitions | 5 |

60 cells, about 18 h. **Causal comparison:** for one method and input, 2 sessions vs 1 session on the same link,
same placement, same day, interleaved. The only difference is the second session's traffic and host load.
Secondary: methods compared within the 2-session condition (same rep index).

Metrics per session: max output gap (primary), cumulative stall, TTFO-local, completion, served calls / s in the
migration window, bytes, active-send overlap, coordinator and NIC checks.

Proposed hypotheses (thresholds for review; fixed at freeze):
- **X1-H1 (primary).** OTTER, each input: median max gap with 2 sessions <= 1.25 x the median with 1 session, and no
  2-session OTTER session > 1.5 x that median. Pilot dog: 1.64-1.67 vs 1.61 s (1.04 x).
- **X1-H2.** With 2 sessions, OTTER's max gap is below Full's and R-full's in every rep, both sessions, both inputs.
- **X1-D (descriptive, no rule).** 2-session / 1-session ratios of TTFO-local, stall and throughput per method.
  Expected from the pilot: OTTER TTFO about 1.7 x, Full gap about 2 x.

## 4. Experiments X2s and X2m: M3's gain and its cost to another session

Common: S1 = Fig. 11 Chain A -> B -> C -> D (GPU 0 of elves-01..04, moves at 45 / 90 s, dog); S2 = one OTTER
migration elves-03:1 -> elves-04:1 (dog); every cell through the coordinator; S2 starts by barrier offset.

| cell | S1 arm | S2 | S2 trigger | serves |
|---|---|---|---|---|
| A-M3 | M3 | none | - | S1 alone, both experiments |
| A-noM3 | no M3 | none | - | S1 alone, both experiments |
| S2-alone | none | alone | - | S2 uncontended reference (absolute cost) |
| s-M3 | M3 | yes | +45 s = start of S1's forward A -> D | X2s |
| s-noM3 | no M3 | yes | +45 s | X2s |
| m-M3 | M3 | yes | +90 s = start of S1's C -> D move | X2m |
| m-noM3 | no M3 | yes | +90 s | X2m |

7 cells x 5 reps = 35 runs, about 9.5 h. A-M3 / A-noM3 are shared by X2s and X2m.

**X2s, staging contention. Causal comparison: s-M3 vs s-noM3.** Same S1 schedule, same S2 placement and trigger
time; the only difference is whether S1 stages. In s-noM3, S1 has no flow on S2's links in S2's window (pilot:
0 s), so the comparison is "S2 next to S1's staging traffic" vs "S2 next to S1 without staging traffic".
- Cost to S2: S2 TTFO-local(s-M3) - S2 TTFO-local(s-noM3); same for gap, stall.
- S1's gain under contention: R_D(s-noM3) - R_D(s-M3), compared with R_D(A-noM3) - R_D(A-M3).
- Contention validity: each s-M3 run shows >= 10 s of active-send overlap on elves-04 ingress (pilot 27.9 s);
  each s-noM3 run's overlap is recorded (expected 0).
- Proposed hypotheses:
  - **X2s-H1.** S1's gain persists: median gain under contention >= 0.75 x median gain alone (pilot 13.15 / 13.15).
  - **X2s-H2 (cost transfer).** Every s-M3 S2 TTFO-local exceeds every s-noM3 S2 TTFO-local (complete separation,
    5 vs 5). The median difference and ratio are reported whatever the outcome (pilot +16.3 s, +70 %).
  - **X2s-H3.** S2's max gap is not changed by S1's staging: median ratio s-M3 / s-noM3 <= 1.25 (pilot 0.98).

**X2m, migration contention. Causal comparison: m-M3 vs m-noM3.** S2 starts with S1's C -> D move in both arms
(same clock time; per-run check: |S2 first open - S1 x3 open| <= 0.5 s, else the run is invalid and rerun). Same S1
state at 90 s except that with M3, D already holds the Sink (staged at 45-73 s, alone on the link). The difference
is how many bytes S1's move puts on the shared link while S2 migrates.
- S1's move bytes in the window: C -> D pre-copy bytes, m-M3 vs m-noM3.
- Effect on S2: S2 TTFO-local(m-noM3) - S2 TTFO-local(m-M3); gap, stall.
- S1 under contention: R_D(m-noM3) - R_D(m-M3) vs alone.
- Contention validity: each m-noM3 run shows >= 10 s of active-send overlap (S1 C -> D with S2); m-M3 overlap
  recorded (expected about 1.5 s).
- Needs the work-conserving coordinator fix (section 2); without it m-M3's S2 is penalised by S1's idle tail.
- Proposed hypotheses:
  - **X2m-H1.** With M3, S1's C -> D move sends <= 10 % of the bytes it sends without M3 (pilot alone: 12 MB vs
    1.73 GB).
  - **X2m-H2.** Every m-M3 S2 TTFO-local is below every m-noM3 S2 TTFO-local.
  - **X2m-H3.** S1's gain persists (as X2s-H1).

**Staging cost included (descriptive ledger, no single verdict).** M3's staging traffic is paid in X2s's window and
its saving appears in X2m's window. The report gives, for each scenario, per session:

| view | metric |
|---|---|
| migration readiness | S1 R_D, S2 TTFO-local, each vs its alone cell |
| user-visible continuity | max gap, cumulative stall, per session |
| locality | S1 N, N_post |
| link use | active-send seconds and bytes on each shared host direction, by flow kind (S1 staging, S1 move, S2) |
| fairness | per-session readiness degradation, concurrent / alone |

No sum of readiness across sessions is reported as a system result (S1's R_D and S2's TTFO-local are different
quantities on different paths and start times). Whether staging pays off depends on when another session migrates
(during staging vs during the move); the paper reports both cases and does not claim cluster-wide efficiency from
two sessions.

## 5. Validity, order and stop rules (all experiments)

- Run validity: pilot `condition_valid`; coordinator allocation sums <= cap at every event; every transfer
  registered and closed; NIC sustained <= 1.05 x, burst <= 1.15 x after the header factor; both migrations complete;
  plus the per-experiment contention and alignment checks above.
- An invalid run is rerun once; both records are kept (harness-bug precedent). Two invalid runs in one cell stop the
  experiment for a review.
- Order inside an experiment: rep-blocks; within a block the cells run in a seeded random order (seed fixed at
  freeze), so time-of-day drift spreads over cells.
- GPU guard per cell with the 5-minute wait loop; the neighbour state of any GPU not used is recorded, not used as a
  rule.
- Labels: measured (testbed). Two sessions do not validate the E9 cluster model; they calibrate its two-session
  sharing assumption only.

## 6. What the paper may say (scope, unchanged until results)

- Allowed now (pilot): concurrent migrations on shared hosts without OOM or substantial throughput loss; in one
  pilot run, M3 kept S1's gain under contention while S2's readiness rose by 70 % and both gaps stayed short.
- After X1: continuity under a shared link, if X1-H1 holds.
- After X2: M3's gain and its cost to other sessions, by contention phase. Not: that M3 improves cluster-wide
  efficiency; that the planner is contention-aware (it is not).

## 7. Decisions needed before freeze

| # | question | proposal |
|---|---|---|
| F1 | work-conserving coordinator registration (harness only; regression `test_rate_coord`, `dry_coord`, `dry_coord1`, `test_xb`) | approve; required for X2m |
| F2 | X2 input | dog only (Fig. 11's input); butterfly doubles X2 to about 19 h |
| F3 | X1 size | as above, 60 runs (~18 h); alternative: 1-session arm 3 reps (~15.5 h) |
| F4 | hypothesis thresholds (1.25 x / 1.5 x gap, 0.75 x gain, 10 s overlap, 10 % bytes, complete separation) | review |
| F5 | order | X2 first (about 9.5 h; the new finding), then X1 |
| F6 | S2-alone reference cell | include (absolute cost of each phase) |
