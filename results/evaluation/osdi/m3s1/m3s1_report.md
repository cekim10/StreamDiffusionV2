# M3-S1 report — network-level validation of lineage-aware progress forwarding (2026-10-29)

Runs: Original `results/evaluation/expM3S1` (54 runs, 8bafb7ec) and `expM3S1_shk` (4); Corrected `expM3S1c` (54 runs,
d8619c35 harness, ad6a6222) and `expM3S1c_shk` (3). Rules: `preregistration.md` section 5, applied by
`tools/eval/m3s1_report.py`. Labels: **[M]** measured on the testbed network, **[C]** measured constant fed to the
harness, **[S]** simulated (pre-run prediction `s0_predictions.json`).

## 0. Summary

| result | harness | validity | valid runs | verdict |
|---|---|---|---|---|
| **Original** | 9ba73566 / 0a361739 | frozen | 6 / 54 (S0, S1c/fwd) | **NO DATA** |
| **Amended** | same runs | Amendments 1 + 2 (post hoc) | 54 / 54 | GO (not used as the basis of a decision) |
| **Corrected** | d8619c35 (version-aware duplicates, in-flight accounting) | **frozen** | **54 / 54** | **GO** |

The Corrected run is a follow-up validation made after the Original results were seen (section 7); it uses the
unchanged rules, thresholds, constants and predictions and the frozen validity checks. It reproduces the Amended
numbers within 0.08 s of remote serving and 0.6 % of total bytes in every cell.

## 1. Verdicts

| validity | valid cells | verdict |
|---|---|---|
| **frozen** (section 4 checks as written) | S0, S1c/fwd only | **NO DATA** |
| Amendment 1 (stale re-sends of the M2 delta accepted) | + S1o | **NO DATA** (no valid S3 cell) |
| **Amendments 1 + 2** (+ cancellation race of one in-flight fragment) | all 54 / 54 | **GO** (R1–R5 hold) |

Every run with staging fails the frozen `no_duplicates` check; every other check passes in every run (all fragments
verified, final migration completed, four hosts on one commit, NIC and paced egress within caps, not cut by the
deadline). The check is version-blind: the M2 delta protocol re-sends, by design, the held entries whose version is
stale (dog 2, butterfly 12 per run), and one in-flight fragment of a cancelled base flow lands after the staging plan
that assigns the same entry (one per run with two candidates or S1c/rev, 9.6 MB). Both amendments are post hoc and
declared in `preregistration.md`; the classification of every duplicate receipt is in `dupcheck_expM3S1.json`
(`tools/eval/m3s1_dupcheck.py`: 0 *other* duplicates in 58 runs). The defect was present in the pre-freeze loopback
run and was missed. The GO below is **conditional on accepting the amendments**; the rules, thresholds, constants and
predictions are the frozen ones. Duplicate bytes are counted in total bytes.

## 2. Results under Amendments 1 + 2 (`s1_results_amended.md`; medians of 3 valid reps; every rep within 0.2 s of its median) [M]

| cell | remote s | ratio to S0 | final valid / 180 | final base MB | ready s | total MB | ratio | staged MB | wasted MB |
|---|---|---|---|---|---|---|---|---|---|
| dog ρ1 S0 | 52.2 | 1.00 | 0 | 1,728 | 22.0 | 4,474 | 1.00 | 0 | 0 |
| dog ρ1 S1o | 38.4 | 0.74 | 137 | 415 | 8.2 | 4,481 | 1.00 | 1,332 | 19 |
| dog ρ1 S1c/fwd | 52.2 | 1.00 | 0 | 1,728 | 21.9 | 4,485 | 1.00 | 0 | 0 |
| dog ρ1 S1c/rev | 38.4 | 0.73 | 138 | 405 | 8.1 | 4,787 | 1.07 | 1,639 | 316 |
| dog ρ1 S2 (fwd / rev) | 38.4 / 38.4 | 0.74 | 137 | 415 | 8.2 | 4,797 / 4,816 | 1.07 / 1.08 | 1,639 / 1,629 | 326 / 316 |
| dog ρ1 S3 (fwd / rev) | 38.4 / 38.4 | 0.74 | 137 | 415 | 8.1 | 4,806 / 4,806 | 1.07 | 1,658 / 1,649 | 335 / 326 |
| bfly ρ1 S0 | 58.9 | 1.00 | 0 | 1,728 | 25.5 | 5,467 | 1.00 | 0 | 0 |
| bfly ρ1 S1o | 46.0 | 0.78 | 108 | 692 | 12.7 | 5,298 | 0.97 | 1,150 | 115 |
| bfly ρ1 S1c/fwd | 58.9 | 1.00 | 0 | 1,728 | 25.6 | 5,472 | 1.00 | 0 | 0 |
| bfly ρ1 S1c/rev | 45.9 | 0.78 | 108 | 692 | 12.6 | 5,757 | 1.05 | 1,591 | 556 |
| bfly ρ1 S2 (fwd / rev) | 46.0 / 46.0 | 0.78 | 108 | 692 | 12.7 | 5,766 / 5,775 | 1.05 / 1.06 | 1,610 | 575 |
| bfly ρ1 S3 (fwd / rev) | 46.0 / 46.0 | 0.78 | 108 | 692 | 12.6 | 5,776 / 5,768 | 1.06 / 1.06 | 1,620 / 1,610 | 585 / 575 |
| dog ρ2 S0 | 38.4 | 1.00 | 0 | 1,728 | 21.6 | 2,929 | 1.00 | 0 | 0 |
| dog ρ2 S3/fwd | 32.3 | 0.84 | 61 | 1,143 | 15.5 | 3,262 | 1.11 | 920 | 335 |

Rules (amended validity):
- R1 **holds**: S3 remote 0.74 (dog) / 0.78 (butterfly) × S0, total 1.07 / 1.06 × S0 (margins ≤ 0.80, ≤ 1.30), both orders.
- R2: S1c in its worse order (fwd) = S0 (1.00) in both workloads, so one causal candidate does **not** suffice;
  S1o = S2 = S3 in remote serving. Two causal candidates cost, relative to S1o, +310 MB (dog) / +460 MB (butterfly) of
  staging, of which 240–270 MB is staging started after the final ownership change and cut by the run end (section 4).
- R3: S3 and S2 fwd vs rev differ by < 0.1 % of S0; S1c differs by 22–26 % of S0 (the predicted order fragility).
- R4 **holds**: every prediction within 15 %: remote serving −2.0 … +0.3 %, total bytes −4.0 … +1.7 % (S0, S1o, S1c,
  S2, S3, both workloads). ρ2 dog: predicted 37.9 / 31.7 s, measured 38.4 / 32.3 s; predicted 63 valid entries,
  measured 61.
- R5: under Amendments 1 + 2 all 54 runs valid; no re-run was needed.

## 3. Predictions P1–P5 against the measurements

- P1 (R1 holds): consistent (0.74 / 0.78; 1.07 / 1.06).
- P2 (S1c order-fragile, S2 / S3 robust): confirmed exactly as described — with fwd order the single candidate after
  the move to C is B, the abandoned holder itself; nothing is staged to D.
- P3 (S2 ≈ S3): holds; source prioritisation changed remote serving by < 0.1 s and total bytes by ≤ 10 MB. The
  contention I expected (B→D staging sharing D's ingress with the A→D base during the lag) did not occur: B→D staging
  had finished (25.5 s) before the second move (28.1 s).
- **P4 is wrong.** The forwarded state is B's abandoned base (1,332 MB B→D during the user's stay at C), not C's.
  C's abandoned base (1,294–1,304 MB) is discarded in every policy, because staging to D stops when the migration to D
  starts and D already held 139 (dog) / 120 (butterfly) entries from B. Discarded bytes are therefore unchanged by
  staging (2,695 MB dog, 3,107 MB butterfly, every policy); the saving is on the final base from the source
  (1,728 → 415 / 692 MB) and in remote serving (−13.8 / −12.9 s). The prediction file had this right (final valid 143 /
  110 from a tag-30 holder); the narrative in section 6 did not.
- P5 (model error ≤ 15 %): holds with margin (≤ 2 % remote, ≤ 4 % bytes).

## 4. Observations the rules do not capture

- **Horizon artefact in total / wasted bytes.** After the final ownership change (D becomes source), the holders A, B, C
  start staging toward the candidates of a next move that never comes; the run ends 2 s later. These flows moved
  240–270 MB per run (S1c/rev, S2, S3; none for S1o, whose candidate set is empty at D) and account for most of the
  reported "wasted" bytes (dog S3: 326–335 MB wasted, of which ≈ 250 MB post-completion). Excluding them, S2 / S3 total
  bytes are 1.01–1.02 × S0 and wasted staging is 60–90 MB (dog) / ≈ 300 MB (butterfly: B→C staging at the second move
  plus 12 stale entries). The frozen R1 counts them; R1 passes either way.
- **Where the amplification goes.** Staging traffic is holder egress (B→D 1.27–1.33 GB), not source egress; the
  source's final base shrinks by 1.31 GB (dog) / 1.04 GB (butterfly). Total bytes rise 6–7 % only because of the
  second-candidate staging and the horizon artefact.
- **Butterfly validity.** 108 of 120 held entries valid after 51 calls (tag 30 → c0 81), consistent with the recorded
  lineage (12 refreshed); the final base is 692 MB, readiness 12.6 s, still within T_m = 14.05 s.
- ρ2 (descriptive): S3 cuts remote serving 38.4 → 32.3 s with 61 valid entries; readiness 15.5 s > T_m = 7.0 s, so the
  final migration completes only because it is the last; staging does not make ρ2 feasible (as M3-S0 said).

## 5. What this does and does not establish

Established on the network [M]: forwarding an abandoned destination's lineage-valid partial base to the causal
candidates turns the final migration into a delta migration (415 / 692 MB instead of 1,728 MB), ready in 8.1 / 12.6 s
instead of 22.0 / 25.5 s, cutting remote serving by 26 % / 22 % at 6–7 % more total bytes; one causal candidate is
order-fragile and two are needed without prediction; source prioritisation is unnecessary at these loads; the M3-S0
model predicts the new conditions within 2 % (time) and 4 % (bytes).
Not established: GPU-level exactness of a base assembled from forwarded tag-30 entries plus a tag-81 delta under an
ownership change (M3-S2); behaviour with cross traffic or per-link caps; lineage after an ownership change (the
uninterrupted trajectory's table was used); any claim about ρ = 2 (descriptive only, infeasible as M3-S0 said).
The harness defects (version-blind duplicate check; planner unaware of a cancelled flow's in-flight fragment) are
to be fixed before any further network run, not retroactively.

## 6. Recommendation [R]

GO to M3-S2 (GPU validation of lineage-aware forwarding under ownership change), to be preregistered, **if the two
amendments are accepted**; otherwise re-run the 39 affected runs with a version-aware duplicate check and a planner
that counts a cancelled flow's in-flight fragment as claimed (≈ 55 min of testbed time, no GPU).

## 7. Corrected M3-S1 (follow-up validation, `expM3S1c`)

Decided by the user after sections 1–6: the amendments are not accepted as the basis of a verdict; the harness is fixed
and all 54 cells re-run on one harness version (`preregistration.md`, "Corrected M3-S1", written before the run).

**Validity [M].** All 54 runs (and 3 shakedown runs) pass every frozen check of section 4, including `no_duplicates`.
The per-node fragment logs confirm it independently (`dupcheck_expM3S1c.json`: 0 duplicate receipts of the Sink in
57 runs). The two defects behave as intended:
- **Stale re-sends are now version replacements**, not duplicates: `n_replaced` = 2 (dog) / 12 (butterfly) in every
  run with a tag-30 holder at D, 0 in S0, S1c/fwd and dog ρ2 (exactly the counts held − valid of the Original run).
- **The cancellation race is gone**: in every two-candidate run the planner deferred one cancelled-but-draining entry per
  cancelled base flow to a candidate (`staging_defer`: 2 per S2 / S3 run, 1 per S1c run), and re-planned at its
  FLOW_DONE (`drain_done`); the fragment then landed and was held, so nothing was re-sent. Restoration never waited
  for it.
- **Delta at base start**: in dog S2 / S3 the final delta is 42 entries instead of 43 (138 valid instead of 137): B's
  draining fragment to D lands between the migration start and the base start and is no longer re-sent.

**Rules (frozen validity) [M].**

| rule | dog | butterfly | result |
|---|---|---|---|
| R1 S3 remote / total vs S0 (fwd, rev) | 0.734 / 1.069, 0.734 / 1.067 | 0.781 / 1.056, 0.781 / 1.052 | **holds** |
| R2 S1c worse order vs S3 | S1c/fwd 0.999 × S0 | S1c/fwd 1.000 × S0 | one candidate does **not** suffice |
| R3 \|fwd − rev\| / S0 (S3, S2) | 0.00 %, 0.00 % (S1c 26.4 %) | 0.01 %, 0.06 % (S1c 21.9 %) | **holds** |
| R4 max model error (remote, total) | 2.0 %, 3.4 % | 0.6 %, 1.9 % | **holds** |
| R5 validity | 27 / 27 (+ 6 ρ2) | 24 / 24 | **holds** |

**Verdict (Corrected M3-S1): GO** — proceed to an M3-S2 GPU validation, to be preregistered.

**Reproduction against the Amended reading [M].** Largest change in any cell: remote serving 0.08 s (dog S2/rev,
S3/rev, 38.43 → 38.35), total bytes −0.6 % (dog S2/rev); every S0 cell within 0.02 s. The headline numbers do not
depend on how the duplicates were handled.

**What stands after the Corrected run.** Forwarding an abandoned destination's verified, lineage-valid partial base
to two causal candidates turns the final migration into a delta migration (405 / 692 MB instead of 1,728 MB), ready in
8.1 / 12.6 s instead of 22.0 / 25.6 s, and cuts remote serving by 26.6 % (dog) / 21.9 % (butterfly) for 5–7 % more
total bytes, of which ≈ 250 MB per run is post-ownership staging cut by the run end (section 4). The saving comes from
B's abandoned base; C's is discarded in every policy. Source prioritisation is unnecessary at these loads. The model
predicted every cell within 2 % (time) and 3.4 % (bytes). Still not established: GPU-level exactness of a Sink
assembled from blocks of different versions under ownership change; lineage after an ownership change; cross
traffic. ρ = 2 remains descriptive (S3 cuts 38.5 → 32.3 s but readiness 15.5 s > T_m).

## 8. M3-S2 design sketch (not frozen; for the next preregistration)

Question (user's framing): *can OTTER assemble an exact Sink from partially restored, differently versioned blocks
held across GPUs, while preserving live-generation continuity?*

Minimal mechanism, layered on the frozen M1 / M2 (47acbe44) without changing their verification or cutover:
1. **Per-entry versions at a holder.** An abandoned destination keeps the verified entries of its cancelled base with
   the base's snapshot call (today the XB path discards them on cancel); the old source keeps its Sink tagged at the
   switch call (M2 already retains it).
2. **Holder → candidate forwarding** of entries, entry-aligned (the GPU path's 4 MiB fragments are not block-aligned:
   412 fragments vs 180 entries; forwarding must be per entry or per block to keep versions per unit).
3. **Mixed-version delta at the destination.** At RDELTA the destination advertises (entry, version) pairs; the source's
   owner tracker answers per entry: valid (no refresh in (v, c0]; the K block needs the ordered shifts since v
   applied), or re-send. This generalises M2's single retained version to one version per entry.
4. **Exactness check** unchanged in spirit: the assembled Sink's 360 block checksums equal the source's at c0 before
   SINKOK; any mismatch → full-base fallback (as M2's DELTANO).

Experiments: dog and butterfly, A → B → C → D at ρ = 1, S2 order fwd (the Corrected network policy); conditions
fresh base / M2 / M3 forwarding, 1 run each; faults: wrong-version entry advertised, corrupted forwarded block, holder
lost mid-forward. Measurements: block checksums at c0 (bitwise), frames after the final switch bitwise equal to the
fresh-base run (as E10), readiness and bytes vs the Corrected network numbers. Open decisions for the user: whether
to implement entry-aligned fragments in the GPU path (2) or forward whole fragments and verify per block; whether
the per-entry version tracker may be added beside the frozen M2 tracker or must replace it for M3 runs only.
