# M3-S1: network-level validation of lineage-aware progress forwarding (preregistration, 2026-10-29)

Fixed before any testbed run. Independent of M3-S0's rules (its thresholds are not revisited). No change to the frozen
M1 / M2 (47acbe44) or to the M3-v2 planner; no GPU run. Background: `../m3s0/m3s0_report.md`, `../m3_topology_research.md`.

## 1. Question

*Does forwarding abandoned, version-valid partial restoration state reduce end-to-end remote serving without excessive
network amplification?*

Secondary: (a) is one staged candidate enough, or are two needed, and at what traffic cost; (b) does the gain depend
on the candidate ordering; (c) does the M3-S0 model predict new conditions it was not calibrated on.

## 2. What is measured and what is modelled (declared)

Network level: `tools/eval/m3s1_orchestrate.py` (extends `restore_orchestrate.Run`) on `restore_node.py` processes on
elves-01..04, real TCP transfers of real sizes under the harness's per-node caps (1 Gbps egress and ingress, max-min).
**Measured on the network:** every transfer time and byte count, the base completion time, cancellation effects,
holder forwarding, contention between base, log and staging flows, the NIC and paced-egress checks.
**Modelled (from measured constants, as M3-S0):** the generation side — call period 0.559 s; Sink lineage from the
recorded tables `../m3s0/events_{dog,bfly}.json` (uninterrupted trajectory); log bytes per call (dog 0.98 MB,
butterfly 13.1 MB) fed into a real flow; base startup latency h = 2.36 s (snapshot + hashing + connect, fitted in
M3-S0); replay catch-up 0.117 / 0.121 s per logged call; readiness floor t(c0 + 12) + 0.6 s; switch 1.69 / 2.32 s;
cancellation lag 0.45 / 2.9 s (dog / butterfly, M3-E0 means). The `lg` session's bytes are real; the log's content is
not. Lineage after an ownership change is the uninterrupted trajectory's (limitation; see section 7).

**Not validated here:** GPU lineage correctness under ownership change (the frozen M1 verifies this per migration; a
GPU test is M3-S2 if S1 passes).

## 3. Execution model (as the frozen M1 / M2 schedule; `m3s1_orchestrate.M3S1Run`)

- Path A → B → C → D; the user is at B from t0, moves at T_m and 2 T_m, T_m = 14.05 / ρ.
- Migration = base flow source → user's edge (the entries not lineage-valid at the destination at c0 + the metadata
  fragment; 181 fragments of 9,584,640 B, the last 2,401,488 B) + log flow (open flow fed every call period).
- Base complete → readiness → first output → **ownership**: the destination becomes the source and serves locally; the
  old source becomes a holder with its Sink tagged at the switch call.
- A move before readiness cancels the migration after the measured lag; the abandoned destination keeps its verified
  fragments with their snapshot tags.
- Validity: fragment f (entry) with tag s is valid for a base at c0 iff f was not refreshed in (s, c0]. The metadata
  fragment is always sent.

## 4. Policies and matrix

| policy | staging |
|---|---|
| **S0** | none: every migration from the source; abandoned fragments never reused (frozen M1 / M2 behaviour) |
| **S1o** | holders forward lineage-valid entries to the **next edge (oracle)** |
| **S1c** | holders forward to **one causal candidate**: the first node ≠ user, ≠ source in the candidate order |
| **S2** | holders forward to **both** causal candidates |
| **S3** | S2 with the active migration's base and log **prioritized** (staging gets the residual capacity) |

Holders = abandoned destinations and old sources; the source never stages; a fragment held by several holders goes
to the one with the fewest assignments; staging to a node stops when a migration to it starts. Candidate order:
**fwd** (A, B, C, D) and **rev** (D, C, B, A) for S1c / S2 / S3.

Matrix: workloads dog and butterfly (seed-0 lineage) × ρ = 1 × {S0, S1o, S1c/fwd, S1c/rev, S2/fwd, S2/rev, S3/fwd,
S3/rev} × 3 reps = 48 runs (~1.3 min each), plus dog ρ = 2 × {S0, S3/fwd} × 3 = 6 descriptive runs.

Validity per run (frozen harness checks): all fragments verified, no duplicates, four distinct hosts on one commit,
NIC receive peaks ≤ 1.15 × cap, paced egress ≤ 1.05 × cap, final migration completed, run not cut by the deadline.
An invalid run is kept and re-run once.

## 5. Rules (medians over 3 valid reps; applied by `tools/eval/m3s1_report.py`)

- **R1 benefit** (primary): under **S3** at ρ = 1, for **both** workloads, remote serving ≤ 0.80 × S0 **and** total
  bytes ≤ 1.30 × S0.
- **R2 one vs two candidates**: report S1o, S1c (both orders) and S2 against S3: remote serving ratio and total /
  staged / wasted bytes. "One candidate suffices" if S1c under its *worse* order is within 10 % of S3's remote serving;
  otherwise two candidates (or prediction) are needed.
- **R3 ordering robustness**: for S3 and S2, |fwd − rev| ≤ 10 % of S0's remote serving. For S1c the ordering effect
  is reported (the model predicts a large one).
- **R4 model validity on new conditions**: the M3-S0 simulator's predictions (`s0_predictions.json`, written before
  the run, same constants) must be within 15 % of the measured medians for remote serving and total bytes in every
  configuration; otherwise the model is reported as not predictive for that quantity.
- **R5 correctness** (harness): the validity checks of section 4 in every run used.

| outcome | recommendation |
|---|---|
| R1 and R5 hold | **GO** for an M3-S2 GPU validation of lineage-aware forwarding (end-to-end exactness under ownership change); its design to be preregistered |
| R1 fails on bytes only (remote ≤ 0.80 but total > 1.30) | **CONDITIONAL**: proceed only with the single-candidate variant if R2 says one suffices, else NO-GO |
| R1 fails on remote serving for a workload | **NO-GO**: adopt migration admission (C3); report repeated mobility as an M1 / M2 limitation |

## 6. Predictions (M3-S0 simulator with holder-only staging; `s0_predictions.json`; written before the run)

| configuration | S0 remote s | S1o | S1c fwd / rev | S2 (either) | S3 (either) | final valid / base MB / ready s (S3) |
|---|---|---|---|---|---|---|
| dog ρ1 | 51.6 | 37.7 (0.73) | **51.6 (1.00)** / 37.7 (0.73) | 37.7 | 37.7 | 143 / 357 / 7.4 |
| butterfly ρ1 | 59.0 | 45.7 (0.77) | **59.0** / 45.7 | 45.7 | 45.7 | 110 / 673 / 12.4 |
| dog ρ2 | 37.9 | 31.7 (0.84) | 37.9 / 31.7 | 31.7 | 31.7 | 63 / 1,124 / 14.9 |

Total bytes: S1o 0.97-1.00 × S0; S2 / S3 1.02-1.06 × S0 (wasted staging 134 MB dog, 642 MB butterfly).

Specific predictions:
- P1. R1 holds for both workloads (remote 0.73 / 0.77 × S0; total 1.02 / 1.06 × S0).
- P2. **S1c is order-fragile**: with fwd order the single candidate after the move to C is B — the abandoned holder
  itself — so nothing is staged to D and S1c/fwd = S0; with rev order it equals S2. S2 and S3 are order-robust.
- P3. S2 ≈ S3 in remote serving: holder-sourced staging does not use the source's egress, so prioritization changes
  bytes little and time not at all. (This is the hypothesis most likely to fail on the real network: holder → candidate
  staging shares the candidate's ingress with nothing until its migration starts, but the holder B→D flow shares D's
  ingress with the A→D base for the lag between the move and the staging stop.)
- P4. The gain is dominated by the second cancelled migration's base at C (≈ 1.3 GB received by C before the move to
  D, forwarded C → D), not by B's.
- P5. Model error ≤ 15 % on remote serving for S0 (calibrated) and ≤ 15 % on the staging policies (not calibrated);
  the untested part of the model is holder → candidate contention and TCP ramp of many short flows.

## 7. Limitations (declared)

- Lineage after an ownership change is the uninterrupted trajectory's. Observed on the GPU (E9 / E10, B's tracker
  after its switch at call 64 over 59 calls): dog 2 refreshed entries vs 2 in the uninterrupted table; butterfly 73
  events / 37 distinct vs 69 / 35. Close, not identical; validity decisions in a real system come from the live source.
- No generation on the hosts; the log is real bytes of synthetic content at the measured mean rate.
- Caps are per node (1 Gbps symmetric); no per-link or cross traffic.
- The reactive multi-provider base (holders feeding the *active* migration) is excluded by design (staging to the
  destination stops at c0), to keep the frozen base-verification protocol shape.

## Amendment 1 (2026-10-29, after the testbed run, before any amended verdict; rules and thresholds unchanged)

**What happened.** All 54 main runs and the 4 shakedown runs completed with every validity check of section 4 passing
except `no_duplicates`, which fails in **every** run with staging (S1o, S1c/rev, S2, S3 at ρ = 1; S3 at ρ = 2) and
passes in every run without staging (S0, S1c/fwd). Under the frozen checks no staging cell has a valid rep, so the
frozen verdict is **NO DATA** (the report tool's verdict fall-through, which printed CONDITIONAL for empty R1 cells,
was corrected to NO DATA; a reporting bug, not a rule).

**Cause (harness, not protocol).** The restore node marks a fragment "dup" when it already holds that
(session, fragment_id) (`restore_node._receiver`), with no notion of version. The M2 delta protocol, as frozen,
re-sends to the destination every entry it holds whose version is stale (refreshed since its snapshot tag) — by
design, the stale copy is overwritten. In M3-S1 the final destination D holds forwarded entries tagged at call 30
(B's abandoned base) and the final base at c0 ≈ 81 re-sends those refreshed in (30, 81]: 2 entries (dog) and
12 entries (butterfly) per run, equal to held − valid in every ρ = 1 run (`m3s1_dupcheck.py` table). The ρ = 2 dog runs
show held − valid = 0 and still fail; the suspected cause is the in-flight fragment of a staging flow cancelled at
migration start landing after the delta was computed (to be classified from the node logs, not assumed).
The same two stale re-sends were present in the loopback run made before freezing (`_dryrun_m3s1`, S2 / S3: 2
duplicates at D) and were not noticed; the check was wrong when it was frozen.

**Amended validity (post hoc; declared).** `no_duplicates` is replaced by `amended_no_duplicates` from
`tools/eval/m3s1_dupcheck.py`, which classifies every duplicate receipt of the Sink session from the per-node fragment
logs (`node_X/fragments.csv`, copied back from the hosts with `d0_remote.py recover --pattern`): *stale_resend* (via a
base flow; the held copy's tag s has the entry refreshed in (s, c0] — the M2 delta by design), *drain_race* (via a base
flow; the held copy was lineage-valid but arrived after the migration started), *other* (a same-version double
delivery — a genuine duplicate). A run is valid under the amendment iff it has no *other* duplicate and every other
check passes. Duplicate bytes stay counted in total bytes. Both verdicts (frozen: NO DATA; amended) are reported; no
rule, threshold, policy, constant or prediction changes. The amended analysis requires the node logs of B, C, D, which
the orchestrator does not collect (only node A's log is local to elves-01).

## Amendment 2 (2026-10-29, after the node logs were classified; rules and thresholds unchanged)

With the node logs, `m3s1_dupcheck.py` found, in every run with two causal candidates or with S1c/rev (39 of 54 main
runs, 2 of 4 shakedown runs), exactly one duplicate that Amendment 1's classes did not cover: node C receives one
entry via the staging flow B → C that it already holds, where the held copy was the **in-flight fragment of the
cancelled A → C base** (cancelled at the move, 28.57 s; the fragment landed at ≈ 28.65 s) and the staging flow was
planned at the cancellation (28.574 s) before that fragment landed. A cancelled flow finishes its in-flight fragment
(`restore_orchestrate` semantics); the planner's "already held or claimed" set does not include it. Cost: one entry
(9.6 MB, ≈ 0.2 % of total bytes) per run; the staged copy carries tag 30 and the held copy tag 56 — both lineage-valid,
so no version conflict. A new class **cancel_race_stage** is added with the mechanistic condition checked from the
logs: the held copy's delivering flow was cancelled no later than the staging flow's start (+ clock tolerance 0.25 s)
and the held copy landed no earlier than that start (− tolerance). Everything outside the three classes stays
*other*. Under Amendment 1 alone the only valid staging cells are S1o (3 / 3 both workloads) and the verdict stays
NO DATA (no valid S3 cell); under Amendments 1 + 2 every run is valid. The ρ = 2 failures are this class alone
(held − valid = 0; no stale re-send).

## Corrected M3-S1 (follow-up validation; written 2026-10-29 before its run)

The user's decision after the Original (frozen: NO DATA) and Amended (Amendments 1 + 2: GO) results: do not accept the
amendments as the basis of a verdict; fix the harness and re-run **all 54 cells** on one harness version, judged by
the **unchanged** section 5 rules, thresholds, constants and predictions (`s0_predictions.json`), with the **frozen**
section 4 validity checks (no amendment). The three results are kept apart: *Original* (expM3S1), *Amended*
(expM3S1 + dupcheck), *Corrected* (expM3S1c). The Corrected run is a validation of reproducibility under a race-free
harness, made after the results were seen; it is labelled as such wherever it is cited.

Harness changes (`tools/eval/restore_node.py`, `m3s1_orchestrate.py`; loopback-tested, 0 duplicates, deferrals and
re-plans observed when the base is cancelled mid-flight):
1. **Version-aware duplicate detection, separate from in-flight accounting.** FLOW_START / FLOW_ADD carry optional
   per-fragment snapshot tags; the FRAG header carries the tag; a verified fragment whose fid is held with a *different*
   tag is a *replace* (the M2 delta's stale re-send; logged as event `replace`, counted in `n_replaced`), the same tag
   again is a *duplicate* as before. Fragments without tags behave exactly as before (the frozen restore harness of
   the earlier experiments is unaffected). `no_duplicates` now means: no same-version double delivery.
2. **In-flight accounting in the planner.** Per (node, fragment) the planner distinguishes *verified and held*
   (`held`: receipts with checksum ok), *in flight, expected* (`claims`: queued in an active flow or sent and not yet
   received), *cancelled but draining* (the first unsent fragment of a cancelled flow until it reports FLOW_DONE) and
   *not held* (everything else, including a drained fragment that did not land). Only verified-held entries count as
   state: `valid_at` is unchanged. A cancelled-but-draining fragment is neither relied upon nor assigned: staging to a
   candidate defers it (event `staging_defer`) and the cancelled flow's FLOW_DONE is a decision point (`drain_done`
   re-plan): if the fragment landed it is held, if not it is assigned then. Restoration never waits for a draining
   fragment.
3. **Delta fixed at base start from verified-held entries.** The migration's c0 is unchanged (snapshot call); the
   delta is recomputed when the base transfer starts (2.7 s after the migration start, as the M2 destination advertises
   its held versions at RDELTA), so a staging fragment that drained into the destination in between is not re-sent and
   one that did not land is. `valid_at_start` (the old definition) is also recorded.
4. Correctness unchanged: the Sink verification (per-fragment SHA-256, digest at completion), the readiness floor,
   the switch and the cancellation lag are as before; nothing is weakened for performance.
5. Summary additions (`corrected_harness`): `n_replaced`, `replaced_bytes`, `n_drain_replans`,
   `post_ownership_stage_bytes` (the horizon artefact, reported, still counted in total bytes), `duplicate_bytes`.

Expectations for the Corrected run (not rules): every run passes the frozen checks; `n_replaced` = 2 (dog) / 12
(butterfly) per staging run with a tag-30 holder, 0 for S0 and S1c/fwd; `n_drain_replans` ≥ 1 per cancellation with a
flow in flight; one deferred entry per two-candidate run instead of the 9.6 MB duplicate; remote serving within 0.5 s
and total bytes within 1 % of the Amended medians; R1–R5 as in the Amended reading. Shakedown: dog S3/rev, butterfly
S3/rev, dog ρ2 S3/fwd (1 rep, `expM3S1c_shk`), checked for `dup 0`, `replaced` as expected and `valid True` before the
54 runs.
