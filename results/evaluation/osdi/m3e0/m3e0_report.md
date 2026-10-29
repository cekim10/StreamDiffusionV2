# M3-E0 report: repeated-mobility baseline of the frozen M1 / M2 (2026-10-29)

**Outcome by the preregistered rules: NO-GO / REASSESS** for a restoration graph on this path.
- Q1 is supported in 4 / 4 configurations.
- The graph upper bound is 1.9-3.2 s, which is 3.8-6.7 % of remote serving. It is not meaningful in any
  configuration.

Labels:
- **Measured**: from the run logs.
- **Offline**: deterministic reproduction, verified against the live hashes.
- **Estimate**: arithmetic on measured values, with the formula given.

## 1. Configuration

Frozen in `preregistration.md` (6a37b94a, before any run). Runs at 6a37b94a.

| item | value |
|---|---|
| execution | frozen M1 / M2: `precopy_replay`, Replay-12, lag 1, Sink sync, retain + reuse. M3 off |
| path and hosts | A → B → C → D on elves-01..04, GPU 0 |
| trigger and moves | trigger at call 30; moves at t0 + T_m and t0 + 2 T_m, with T_m = 14.05 s / ρ |
| network | 1 Gbps per-node egress and ingress caps |
| inputs | dog and butterfly-feeding-slow-motion, seed 0; ρ 1 and 2; one run each |
| measured move times | ρ1: 14.07-14.08 s / 28.14-28.15 s. ρ2: 7.04 s / 14.08-14.10 s |

## 2. Raw results

| configuration | run directory |
|---|---|
| dog ρ1 | `results/evaluation/expM3E0_dog_rho1/policy=precopy_replay_bw=1000_rho=1_tm=14.05_rep=1_sinksync_retain_reuse_20261029-012634` |
| dog ρ2 | `…/expM3E0_dog_rho2/…_20261029-014520` |
| butterfly ρ1 | `…/expM3E0_bfly_rho1/…_20261029-020352` |
| butterfly ρ2 | `…/expM3E0_bfly_rho2/…_20261029-022233` |

Derived files:
- `e0x_{dog,bfly}.json`: offline classification (elves-01, 6a37b94a).
- `e0_metrics_*.json`: continuity (elves-02).
- `e0_report.json`: `tools/eval/m3e0_report.py`.

Commits: runs and classification 134f3136; metrics 904147fa.

## 3. Summary (measured)

| | dog ρ1 | dog ρ2 | butterfly ρ1 | butterfly ρ2 |
|---|---|---|---|---|
| valid (frozen XB rule) | yes | yes | yes | yes |
| cancelled migrations | 2 | 2 | 2 | 2 |
| Sink fragments sent before cancel (of 412): B / C | 330 / 328 | 126 / 118 | 324 / 251 | 117 / 80 |
| discarded (base + log) | 2,795.0 MB (1.62 Sink) | 1,039.8 MB (0.60) | 2,953.3 MB (1.71) | 1,033.5 MB (0.60) |
| of which log + patches | 35.1 MB | 16.4 MB | 541.5 MB | 207.3 MB |
| all bytes sent (all tasks) | 4,555.0 MB | 2,809.4 MB | 5,125.8 MB | 3,265.2 MB |
| reused bytes (M2 delta) | 0 (no destination held a version) | 0 | 0 | 0 |
| final migration completes | yes (A → D, switch at call 106) | yes (83) | yes (111) | yes (88) |
| remote serving: wall s / chunks | **50.0 / 76** | **35.4 / 53** | **53.8 / 81** | **38.7 / 58** |
| TTFO-local at B / C / D (s) | none / none / 23.7 | none / none / 23.8 | none / none / 28.4 | none / none / 27.1 |
| interruption at the final cutover | 1.65 s | 1.70 s | 1.97 s | 1.81 s |
| per-call service time: median / p95 / max | 0.560 / 0.583 / 1.54 s | 0.558 / 0.613 / 1.56 | 0.559 / 0.589 / 2.04 | 0.558 / 0.598 / 1.57 |

## 4. Timeline (measured; s after the trigger)

| configuration | task 1, A → B (c0 31) | task 2, A → C | task 3, A → D (completes) |
|---|---|---|---|
| dog ρ1 | 0.0 → 14.59 cancelled | c0 52, 14.59 → 28.53 cancelled | c0 73, 28.53 start → base ready +17.77 → replay ready +21.62 → first output +23.32 (51.8) |
| dog ρ2 | 0.0 → 7.59 cancelled | c0 41, 7.59 → 14.71 cancelled | c0 50, 14.71 → +17.13 → +20.96 → +23.12 (37.8) |
| butterfly ρ1 | 0.0 → 16.94 cancelled | c0 56, 16.94 → 31.06 cancelled | c0 77, 31.06 → +19.09 → +23.21 → +25.53 (56.6) |
| butterfly ρ2 | 0.0 → 8.87 cancelled | c0 43, 8.87 → 14.76 cancelled | c0 50, 14.76 → +19.68 → +24.19 → +26.41 (41.2) |

A cancellation takes effect after the move: 0.5-2.9 s later, at the next chunk boundary or fragment. That lag is why
butterfly's chase is longer.

## 5. Wasted transfer and remote serving

**Q1: is repeated mobility a real problem? Yes (measured).**
- Each configuration cancelled both intermediate migrations.
- Discarded transfer: 0.60-1.71 Sink.
- Total bytes sent: 1.6-3.0× one base.
- The user was served remotely for 35.4-53.8 s, which is 1.6-2.4× E9's single-migration readiness (22.17 s).
- B and C never served the user.
- Fragile margins at ρ2: discarded 0.60 Sink against the 0.5 threshold; remote 35.4 s against 33.3 s (dog).

Remote-serving decomposition (measured):

| | dog ρ1 | dog ρ2 | butterfly ρ1 | butterfly ρ2 |
|---|---|---|---|---|
| chase (trigger → final task start) | 28.5 s (57 %) | 14.7 s (42 %) | 31.1 s (58 %) | 14.8 s (38 %) |
| final snapshot + base send | 0.4 + 17.0 s | 0.05 + 16.7 | 0.6 + 18.1 | 0.1 + 19.2 |
| base ingress bound (1,727.6 MB at 1 Gbps) | 13.8 s | 13.8 | 13.8 | 13.8 |
| mean D rx / A tx during the base | 888 / 889 Mbps | 885 / 886 | 823 / 871 | 864 / 916 |
| **graph UB** (unused D ingress × send time) | **1.90 s (3.8 %)** | **1.91 s (5.4 %)** | **3.20 s (6.0 %)** | **2.61 s (6.7 %)** |
| replay catch-up (base ready → replay ready) | 3.85 s | 3.83 | 4.12 | 4.51 |
| replay ready → first output (switch) | 1.69 s | 2.16 | 2.32 | 2.22 |
| final-task log + patches | 32.3 MB | 41.9 | 444.9 | 504.0 |

**Q4: the dominant term is the chase, 38-58 % of remote serving. The next is the single migration itself, which is
ingress-bound.**
- The final base ran at 82-89 % of D's 1 Gbps ingress.
- The remaining 1.9-3.2 s is the ceiling for any multi-provider delivery. That includes using the partial bases held
  at B and C, because D must still receive the whole base through its own ingress.
- Part of this ceiling may be the single paced sender's efficiency, a harness property, so the ceiling is generous.

**Estimate: even a perfect graph would not change the cancellations.** Final readiness minus UB is 19.1-21.6 s in
every configuration, still above T_m = 14.05 s (ρ1) and 7.03 s (ρ2).

**Structural point (estimate).**
- The ingress-bound base alone takes 13.8 s, and replay catch-up adds 3.8-4.5 s. So under ρ ≥ 1, an M1 migration of a
  full base cannot finish before the next move, whatever the provider graph: T_s = 14.05 s is itself the base
  transfer time.
- The measured factors are therefore, in order:
  1. repeated cancellation and restart (the chase);
  2. single-migration readiness, at its ingress bound.
- Replay readiness is 3.8-4.5 s.
- The ordered log / patch stream is 445-504 MB for butterfly, about 4 s of D's ingress. For dog it is negligible.
- Network degradation was not present.

## 6. Same-version reuse feasibility

**Q2: what is held at abandoned destinations? (measured)**
- Verified at abandoned destinations: 2,759.9 MB (dog ρ1), 1,023.4 (dog ρ2), 2,411.7 (butterfly ρ1) and 826.3
  (butterfly ρ2).
- Every held fragment was hash-verified at receipt and equals the source's base hash for its version.

**Classification against the final base (offline).**
- The reproduction matched the live fragment hashes 412 / 412 for every version of every run, and 0 fragments are
  unexplained.
- Union over B and C, each fragment counted once:

| | dog ρ1 | dog ρ2 | butterfly ρ1 | butterfly ρ2 |
|---|---|---|---|---|
| strict same-version (same c0) | **0** | **0** | **0** | **0** |
| identical (hash-equal, usable as is) | 1,354.8 MB (0.78 Sink) | 276.8 (0.16) | 956.3 (0.55) | 205.5 (0.12) |
| shift-only (cross-version reconstruction) | 8.4 MB | 251.7 | 88.1 | 226.5 |
| refresh (must come from the source) | 21.0 MB | 0 | 314.6 | 58.7 |

Bytes already transferred vs verified vs reusable, per tier (measured / offline):
- **transferred:** dog ρ1 4.55 GB in total, 2.80 GB of it discarded;
- **verified:** 2.76 GB held at B and C;
- **same-version reusable:** 0;
- **content-identical:** 1.35 GB;
- **needs cross-version reconstruction:** 8 MB.

The other configurations follow the table above.

**Q3: is same-version reuse sufficient? No, by the rule.**
- Strict same-version reuse is 0 everywhere, by construction: each new migration snapshots its own base at its own
  boundary c0 (31 / 41-56 / 50-77), so the required base version always changes.
- Identical content reaches 0.25 Sink in 2 of 4 configurations (dog ρ1 0.78, butterfly ρ1 0.55), not 3.
- Why the version change matters:
  - Between c0 = 31 and a base at c0 ≥ 50, the Sink's RoPE realignment at calls 48 / 49 re-rotates the K of 72-74
    blocks (dog) and 61-93 blocks (butterfly). Those fragments are not hash-equal; they become valid only after the
    ordered shifts.
  - Refreshes change values that only the source has: dog 2-4 blocks, butterfly up to 70.
  - With cross-version reconstruction the union is 0.25-0.79 Sink (≥ 0.25 in 4 / 4; butterfly ρ2 at 0.2501).
- **Descriptive:** a base held at C (c0 52) is 322 / 328 fragments identical to the final base at c0 73, because no
  realignment falls between them. Partial bases age slowly between realignments and change wholesale at a
  realignment.

## 7. Correctness (measured)

**All four runs:**
- valid by the frozen XB rule: nodes on one commit, GPU 0 idle, every switchover verified, source served until the
  switch, final edge served, NIC within cap;
- final base verified;
- final cutover SINKOK: 0 / 360 mismatched blocks, positions equal;
- no fallback, no readiness timeout, no refused switch.

**Output vs reference: 0 / 101 calls bit-equal in every run.** This is a property of the frozen M1, not an E0 failure:
- log-only replay reconstructs the recent KV approximately (E2);
- E9 and E10 also have 0 / 100 at every destination (`expM2E9_baseline`, `expM2E10_bfly_baseline`);
- M1's exactness is Sink exactness (block-level) plus determinism across runs, not equality with the uninterrupted
  stream.

The preregistration's prediction "all outputs equal to the reference" was wrong and is recorded as such. No rule used
it.

Other measured values:
- **Trajectory:** D crosses 35 dB within 6 calls and holds it in every run; terminal median 45.2-49.0 dB.
- **Continuity (VD-3 frozen rules, final migration):** P1 / P2a / P2b pass in 3 / 4. Dog ρ1 fails P2b (V1 2.64 vs REF
  1.54 at the same call), the same class as the dog first-migration P2b failures of E3 / E5 / E9 / E10.

## 8. Limitations

- One run per configuration. Margins at ρ2 are small (section 5).
- One path, A → B → C → D, with no revisit. Uniform 1 Gbps caps with equal ingress and egress, so multi-provider
  aggregation cannot exceed the destination's ingress by construction.
- The UB counts all unused ingress as recoverable, including single-sender pacing inefficiency.
- Two inputs, seed 0, one model. No network degradation and no concurrent sessions.
- The cross-version classes are offline reproductions (verified bit-exact against the live hashes). Reconstruction was
  not executed.

## 9. Recommendation

**NO-GO / REASSESS (rule).**

Repeated mobility is a real, measured problem under M1 / M2:
- 0.60-1.71 Sink discarded;
- 35-54 s of remote serving;
- every intermediate migration cancelled.

But a restoration graph cannot address it on this path. The final migration is within 1.9-3.2 s of its ingress bound;
the largest share of remote serving is the chase; and no provider graph brings readiness below T_m at ρ ≥ 1.

Same-version reuse is zero by construction. Content-identical and shift-reconstructable state is substantial, but on
this path it sits on nodes the user never returns to.

What the data point to instead (hypotheses, not tested; each would need its own preregistration):
- **(a) Not chasing.** Do not start or keep a migration that cannot finish before the next move. This would remove the
  0.60-1.71 Sink of waste without changing remote serving. It is a policy question, not a graph.
- **(b) Revisits.** A partial base aged less than a realignment interval is ~98 % identical (C → final at dog ρ1).
  Revisiting a node that holds one is a same-node versioned reuse, i.e. an M2 extension.
- **(c) Destination ingress larger than one provider path,** or source egress contention. Only there can multi-provider
  delivery exceed the single-path rate. This is the regime where the old M3 had its gains, and the testbed's uniform
  caps exclude it.
