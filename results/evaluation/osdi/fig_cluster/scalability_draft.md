# E9 scalability extension (DRAFT 1, 2026-11-03; not frozen; nothing run; SIMULATED when run)

Extends the frozen E9 (preregistration.md, 37aca4b7; results cf6b1658) without changing it. The primary sweep, CL-H1
(smoke-informed, reformulated (b), stalled seconds per session-hour as the primary metric), CL-H2 and CL-H3 stay as
they are. Both extensions below are **descriptive**: no confirmatory hypothesis, predictions marked [H].

## 1. Facts about the current model that shape the design [V, code]

- The primary sweep is a **load sweep**: E = 16 sites x G = 8 GPUs = 128 GPUs fixed, N = 32 / 64 / 96 / 120 sessions
  (primary point N = 64, i.e. 0.5 sessions per GPU).
- Links are per site (egress and ingress at C). The **core is non-blocking**: no flow is limited by anything other
  than its two sites' links.
- Staging candidates are the **k = 4 nearest sites** to the user, excluding the user's site and the owner
  (`candidates()`, `k_stage`); naive replication uses the same candidates.
- **k = 0 is exactly Unstaged:** the candidate list is empty, so `stage()` does nothing, and `base` and `otter` share
  `mig_otter_like`. Checked numerically on one configuration (E 16, G 4, N 48, C 10, M 16, dwell 180, seed 0): every
  summary field is identical except the method label. The check is repeated on each S-B cell before its results.
- The grid is `ceil(sqrt(E))` wide:
  - E = 2 is a 1 x 2 row. A user who is away from the owner is at the only other site, so there is no staging
    candidate, and OTTER = Unstaged by construction.
  - E = 8 is a 3 x 3 grid with one site missing.
- Retained and staged versions are host memory (budget M per site, LRU) in the model and on the testbed
  (`MemLog`: host bytes). GPU memory holds only the served session (one per GPU).

## 2. S-A cluster scale-out (separate from the N load sweep)

| GPUs | sites E x G | sessions at rho = 0.5 | sessions at rho = 0.94 |
|---|---|---|---|
| 16 | 2 x 8 | 8 | 15 |
| 32 | 4 x 8 | 16 | 30 |
| 64 | 8 x 8 | 32 | 60 |
| 128 | 16 x 8 | 64 (= E9 primary point) | 120 (= E9's highest load) |
| 256 (optional) | 32 x 8 | 128 | 240 |

Settings:
- Fixed: C 10 Gbps, M 32 GB, dwell 180 s, life 1,200 s, drains as E9, k 4, seeds 0-2, all six methods.
- Size: 4 sizes x 2 loads x 3 seeds x 6 methods = 144 runs. The primary sweep's 2,592 runs took 1.4 h, so this is
  minutes. The 256-GPU size is for the simulator's execution time only.

Metrics:
- Stalled s / session-h, stalls > 1 / 2 / 5 / 10 s, local share.
- Moves reaching local service (completion).
- Time without local service per move.
- Staging GB / session-h.
- Mean and peak site memory.
- Link utilization p50 / p99.
- Simulator wall time.

[H] With a non-blocking core and per-site links, per-session results should be nearly flat in E from about 8 sites
on. Differences at 2-4 sites come from geometry (fewer neighbours and candidates, longer load fallbacks), not from
contention. The paper must say so if it happens, rather than read a flat curve as "OTTER scales".

**S-A' core oversubscription (optional; a model extension, sensitivity only, cannot be validated on the testbed).**
All inter-site flows also cross one core link of capacity E x C / kappa, with kappa = 1 / 2 / 4.
- kappa = 1 must reproduce the current model's outputs exactly (regression).
- This is the only way cluster size can create contention in the model.
- It is labelled an unvalidated assumption wherever it is shown.

## 3. S-B staging fanout

k = 0 / 1 / 2 / 4 / 8 for OTTER and naive replication, in three cells at N = 64:

| cell | C (Gbps) | M (GB) | dwell (s) | why |
|---|---|---|---|---|
| primary | 10 | 32 | 180 | CL-H1's point |
| slow link | 1 | 32 | 180 | where E9 found staging hurts (9.5-81 %) |
| fast mobility | 10 | 32 | 60 | most moves per session-hour |

Size: 5 k x 3 cells x 3 seeds x 2 methods = 90 runs. Full / Llumnix / SLLM / Unstaged do not depend on k and are
reused from the primary sweep.

Metrics:
- Destination hit rate: migrations whose base is a staged or delta version, over all migrations (`migrations`
  counts).
- Staging GB / session-h.
- Site memory mean / peak, and LRU evictions (a record-only counter to add: the model does not count them yet).
- Delay per move.
- Stalled s / session-h.
- Link utilization.

[H] The hit rate rises with k and saturates near the user's neighbour count (4 on the interior grid). Staging bytes
grow about linearly in k. At 1 Gbps, larger k hurts more (staging competes with migrations on the same uplinks); at
10 Gbps, k beyond 4 adds bytes without delay gains.

## 4. Contention items and their evidence

| item | in the model | measured on the testbed | plan |
|---|---|---|---|
| shared-link bandwidth | yes (fluid max-min per site link) | one session's own flows (Fig. 11 gate) | two sessions via the concurrency pilot's C3 (if approved); compare the simulator on the same two-session schedule |
| destination GPU replay contention | not applicable: one session per GPU, migrations go to a free GPU | same (two sessions do not fit one L40S) | stated as a model scope, not modelled |
| staging vs migration traffic | yes (equal-weight flows on the same links) | no (needs M3 + two sessions = 6 GPUs) | sensitivity only (S-B slow-link cell); not claimed as validated |
| memory pressure -> staging failure | host-memory budget M, LRU | retained / staged bytes recorded (Fig. 14, long-age runs) | S-B reports evictions; GPU memory not involved |

Any simulator change (S-A' core link, or a fix after C3) re-runs the validation gate. The 76 / 76 PASS is not carried
over.

## 5. Order and decisions (user)

Order: run after the Fig. 10 long-age calibration (if it changes [A5], first re-gate and re-run the primary sweep),
then S-B, then S-A (and S-A' if chosen).

| # | decision | recommendation |
|---|---|---|
| E1 | loads in S-A | both rho 0.5 (the primary point) and 0.94 |
| E2 | 256 GPUs | yes, for execution time only |
| E3 | S-A' core oversubscription | yes, as labelled sensitivity |
| E4 | S-B cells | the three above |
| E5 | figure | at most one panel each, or text numbers (no appendix, 18-20 figure budget) |
