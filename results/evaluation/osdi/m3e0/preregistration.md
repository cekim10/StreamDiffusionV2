# M3-E0: repeated-mobility baseline of the frozen M1 / M2 (preregistration, 2026-10-29)

Fixed before any M3-E0 run. Problem characterization, **not** an M3 evaluation: M3 is disabled.

Frozen mechanisms used unchanged:
- M1 / M2 at 47acbe44: `precopy_replay` with Replay-12, Sink synchronization, retention and versioned reuse;
- M3-v2 planner e39609a (not exercised).

Background: `../m3_audit.md` (69df6b33).

## 1. Questions

- Q1. Does repeated mobility cancel migrations and waste state transfer under M1 / M2, and how much remote serving
  accumulates?
- Q2. How much transferred Sink state is held, verified, at abandoned destinations, and how does it relate to the base
  later migrations need?
- Q3. Is same-version reuse sufficient?
- Q4. What bottleneck dominates, and how much of it could a restoration graph (multi-provider base delivery) address
  on this path?

## 2. Configuration (XB3 / XB4 semantics verified from their records, not assumed)

Verified from `expXB_XB3_dog/*/config.json`, `tools/eval/run_wrn.py` `XB_SCEN`, and `mobility_orchestrate.execute_xb`:

| item | value (as XB3 / XB4) |
|---|---|
| path | A → B → C → D (`--hops 3`), hosts elves-01..04, GPU 0 each |
| trigger | call 30 (`--migration_chunk 30`); the source A starts serving at t0; the user is at B from t0 |
| ρ and T_m | T_m = T_s / ρ with T_s = 14.05 s (`--ts 14.05`); moves at t0 + T_m (to C) and t0 + 2 T_m (to D): ρ = 1 → 14.05 s / 28.10 s, ρ = 2 → 7.025 s / 14.05 s |
| network | per-node egress and ingress caps of 1 Gbps (application pacing, max-min), one LAN |
| run length | final owner + 100 calls (`--xb_horizon 100`), `--horizon_calls 180`, `--post_chunks 1500`, `--max_run_s 2400` |
| workloads | dog (`examples/original.mp4`, `examples/prompt.txt`) and butterfly-feeding-slow-motion (`data/loveu_tgve_2023/…`, background prompt), **seed 0** as in XB |

Execution (frozen M1 / M2 as in E9 / E10):
- `--policies precopy_replay --xb_policy_settings precopy_replay@thr=16:rl=1`;
- `--replay_window 12 --replay_lag 1 --replay_sink_sync`;
- `--replay_retain --replay_reuse`: M2 is enabled. On A → B → C → D no destination holds a retained version, so M2
  reuse is expected not to apply; this is recorded, not assumed.

What M1 / M2 do on a move (code, read):
- A move during a migration cancels it (`_xb_cancel` → `PRECOPY_CANCEL`).
- A new task starts from the current source to the user's new edge, with a new base snapshot at its own boundary c0.
- The abandoned destination keeps its received fragments in memory but nothing reads them again. The new target
  starts from an empty store.

Matrix: dog ρ1, dog ρ2, butterfly ρ1, butterfly ρ2. One run each (characterization).
Scripts: `tools/eval/run_m3_e0.sh` (preflight / orch / crossversion / metrics), `tools/eval/m3e0_report.py`,
`tools/eval/m3e0_crossversion.py`.

## 3. Instrumentation (behavior-preserving; record only)

Existing logs give the timeline, partial base bytes at cancellation (`xb_precopy_round.dirty_bytes`), serving and
correctness. They do not give three things, which `mobility_node.py` now adds as extra fields of existing events
(no new message, no change to what is sent, verified or decided):
- `replay_base_sent` (source): the base's per-fragment SHA-256 prefixes (16 hex; the hashes the source already
  computes), the number of Sink fragments in the base, and the number sent.
- `replay_base` (destination, when round 1 ends, complete or cut short): the number of fragments held hash-verified per
  component, and the held Sink fragments' ids and hash prefixes.
- `xb_precopy_cancelled` (source): c0, log calls / bytes, patches / patch bytes and base bytes sent to the abandoned
  destination, and the source's call.

Checks before freezing:
- Dry test (fake runtime, A → B → C → D, T_m 2.5 s): every cancelled destination holds exactly the fragments sent,
  each equal to the source's base hash. The final migration is SINKOK.
- Regressions `test_m2_live.py` and `test_m1_live.py`: ALL PASS.

## 4. Measurements and definitions

**A. Migration progress.** Per task:
- start, cancellation / completion times, boundary c0;
- base bytes sent, Sink fragments sent / total;
- fragments verified at the destination;
- log and patch bytes sent.

Derived values:
- **discarded** = base + log bytes of cancelled tasks;
- **reused (measured)** = delta-base bytes;
- final completion, with readiness = task start → `replay_ready`.

**B. Serving.** XB delivery accounting (`xb_delivery.delivery_metrics`, unchanged):
- TTFO-local per edge, delivery gap;
- remote serving: chunks and wall seconds served by a host other than the user's edge;
- interruption (`summary.cutover`);
- per-call service time (`chunk_s`).

**C. Reuse opportunities.**
- Base version of each task = its c0 and live fragment hashes.
- Held bytes at abandoned destinations = verified fragments × fragment size.
- Each held fragment is classified against the **final** base by `m3e0_crossversion.py`. This is a deterministic
  offline reproduction; it is valid only if its fragment hashes equal the live ones for every version, 412 / 412,
  otherwise the run's classification is not used. Classes:
  - **identical** (hash-equal; usable as is after an SHA-256 check against the new manifest);
  - **shift_only** (needs ordered-shift reconstruction, i.e. cross-version);
  - **refresh** / **other** (must come from the source).
- **Strict same-version** = held fragments of a version equal to the final base's (same c0).
- The union over abandoned holders counts each final-base fragment once, in its best class.

**D. Correctness.**
- Every switchover verified (`switchovers_verified`);
- final cutover SINKOK with 0 / 360 mismatched blocks and positions equal;
- base verified;
- output equivalence after the final resume (per-call digest = reference);
- continuity of the final migration by VD-3 frozen rules (`m1_live_metrics.py`, OUT_D / REF_D, units `dog_s0` and
  `butterfly-feeding-slow-motion_s0`);
- run validity by the frozen XB rule (`xb_validity.run_validity_xb`). An invalid run is kept and re-run once.

**E. Remote-serving decomposition (Q4).**
- remote serving ≈ **chase** (trigger → final task start) + the final migration (snapshot + base send + replay
  catch-up + switch).
- **Graph upper bound (UB)**: the destination must receive the whole base through its own ingress, whoever sends it.
  So any multi-provider delivery, including the partial bases held at B and C, can shorten the final base by at most
  the destination-ingress capacity left unused during the final base transfer:
  UB = base send time × (1 − mean D NIC rx / cap), from D's 1 s kernel samples over that interval.
- The chase cannot be shortened by a restoration graph on this path: the user is not at D before the last move.

## 5. Rules (applied as written by `m3e0_report.py`)

- **Q1 supported** if, in ≥ 3 of 4 configurations, all three hold:
  - ≥ 1 cancelled migration;
  - discarded ≥ 0.5 Sink (863.8 MB of base + log);
  - remote-serving wall time ≥ 1.5 × 22.17 s = 33.3 s (E9's single-migration readiness).
- **Q3 same-version sufficient** if, in ≥ 3 of 4 configurations, the strict same-version plus identical union over
  abandoned holders is ≥ 0.25 Sink of the final base.
- **Q4 meaningful headroom** in a configuration if UB ≥ 2.0 s **and** UB ≥ 10 % of its remote-serving wall time.

**Recommendation mapping:**

| condition | recommendation |
|---|---|
| Q1 not supported | NO-GO / REASSESS |
| Q1 supported, Q4 meaningful in < 3 configurations | NO-GO / REASSESS for the restoration graph on this path; the report names the dominant measured bottleneck |
| Q4 meaningful in ≥ 3, Q3 sufficient | GO (same-version integration) |
| Q4 meaningful in ≥ 3, Q3 insufficient, identical + shift_only union ≥ 0.25 Sink in ≥ 3 | EXPAND (versioned holders) |
| otherwise | NO-GO / REASSESS |

## 6. Predictions (written before the runs; from E9 / E10 and XB3 / XB4, not evidence)

Inputs to the predictions:
- E9 / E10 full-base rounds: send 16.7-18.0 s for 1,727.6 MB (bound 13.82 s); readiness 21.6-24.0 s.
- In those rounds D's mean rx was 830-881 Mbps, i.e. 2.0-3.0 s of unused ingress.
- XB3 / XB4 P-sink: two cancelled rounds of ~1.3 GB at ρ1; remote serving 44.8 s (ρ1) and 30.2 s (ρ2).

| configuration | predicted |
|---|---|
| ρ1 | Both intermediate migrations are cancelled before their base completes: ~75-80 % of the base, ~1.3-1.4 GB each, plus log. Final A → D starts at ~28.1 s and serves ~50-53 s after the trigger. Discarded ~1.6-2.2 Sink. Chase share ~55 % |
| ρ2 | Cancellations at ~35-40 % of the base. Final starts at 14.05 s; remote serving ~36-39 s. Discarded ~0.8-1.1 Sink. Chase share ~37 % |
| UB | ~2-3 s per configuration, ~4-8 % of remote serving: **not** meaningful by the rule |
| strict same-version | 0 by construction: every task snapshots its own c0 |
| identical fraction | Bases ~20-45 calls apart cross the realignment at calls 48 / 49, so ~50-60 % of the base is hash-identical (dog, E4: 42 % dirty over calls 31 → 64); fewer for butterfly (more refreshes) |
| correctness | final SINKOK 0 / 360, all outputs equal to the reference |

Predicted recommendation: **NO-GO / REASSESS for the restoration graph on this path**. Q1 is supported, but the
dominant term is the chase plus the single-migration readiness, not provider capacity. This prediction does not bind
the result. The rules above decide.

## 7. Discipline

- No change to the M1 / M2 protocol, the M3-v2 planner or the run settings after this commit.
- No commit or pull on the testbed while runs are in progress.
- Failed or incomplete runs are kept and reported.
- Nothing is substituted from oldM1 / oldM2 experiments.
- Cross-version classes are offline reproductions and are used only when the hashes match the live run.
