# E9 load scaling and cluster-size scaling: protocol (DRAFT 1, 2026-11-04; not frozen; SIMULATED when run)

Extends the frozen E9 (`preregistration.md`, 37aca4b7; results cf6b1658) without changing it. CL-H1 / CL-H2 / CL-H3,
the model, the calibration and the validation gate (76 / 76) stay as they are. This draft replaces S-A of
`scalability_draft.md` (DRAFT 1, e83a267a); S-B (staging fanout) and S-A' (core oversubscription) stay in that draft.
Nothing is frozen or run before the user reviews it.

Tools (implemented 2026-11-04, harness only):
- `tools/sim/cluster_sim.py`: new grids `load`, `scale`, `scale_g4`; `sweep()` accepts (E, G, N) `points`. The model is
  untouched.
- `tools/sim/scaling_report.py`: tables plus gates R0 / R1.

## 0. What was seen before this draft (disclosure)

While checking determinism and the simulator's wall time (2026-11-04), these single runs were made. All were seed 0,
C 10 Gbps, M 32 GB, dwell 180 s:
- E 16, N 64 / 120 and C 1 / 10, OTTER and Full: identical to the frozen sweep (R0 holds on 4 / 4).
- E 2, N 8, OTTER and Unstaged: identical (R1). Stalled 26.8 s / session-h, local share 0.954.
- E 32, N 240: Unstaged stalled 16.5, local 0.54; OTTER stalled 16.3, local 0.53; wall 1.9 / 5.0 s.
- E 32, N 128: OTTER local 0.919. E 8, N 60: OTTER local 0.627. E 64 x G 4, N 240: OTTER local 0.463.
- Off-grid check (not in this design): E 36, N 240, OTTER local 0.715.

Already known from the frozen sweep: OTTER's local share falls from 0.910 (N 64) to 0.442 (N 120) at E 16, C 10.

A plumbing dry test was also run, on a 1,500 s horizon (`_dry_*`, not committed, not results).

## 1. Facts that shape the design [V, code]

- Sessions per GPU = N / (E x G). Each GPU serves one session.
- A move or drain to a full site cannot become local. The session is served **remotely** (not a stall) until a slot
  frees.
- Consequence: at high load, stalled seconds can fall while local share falls. Remote service replaces migration
  stalls.
  - **Stalled seconds and local share are always reported together.**
  - A lower stalled-seconds value at a higher load is not read as better service.
- Site links are per site (egress / ingress C). The **core is non-blocking**, so cluster size creates no contention
  in the model. Only geometry changes with E:
  - fewer neighbours at the edge;
  - incomplete grids (E 8 = 3 x 3 minus 1, E 32 = 6 x 6 minus 4);
  - with 2 sites, no staging candidate (OTTER = Unstaged by construction).
- N 128 at 128 GPUs (1.0 per GPU) is outside the model's scope. A drain needs a free slot. So the highest load stays
  0.94 per GPU, as in E9.
- The simulator is deterministic per seed. A configuration shared with the frozen sweep reproduces it field by field
  (section 0).

## 2. L: load scaling (128 GPUs, sessions increase)

**Question.** At a fixed 128-GPU cluster, how do stalls, locality and migration completion change for each method as
sessions per GPU rise? Does OTTER's stall advantage over the external baselines hold at every load?

| dimension | values |
|---|---|
| cluster | E 16 sites x G 8 GPUs = 128 GPUs (E9 primary) |
| N | 16, 32, 48, 64, 80, 96, 112, 120 (0.125-0.94 per GPU) |
| link C | 10 Gbps (primary point), 1 Gbps (link-bound) |
| M, dwell, life, drains, k | 32 GB, 180 s, 1,200 s, as E9, 4 |
| seeds | 0-4 |
| methods | Full, Llumnix, SLLM, Unstaged, OTTER, Replicate |

- Size: 8 x 2 x 5 x 6 = 480 runs, about 15 min.
- Shared with the frozen sweep: N 32 / 64 / 96 / 120 at C 1 / 10, seeds 0-2 (144 runs). R0 requires them identical.
- New: N 16 / 48 / 80 / 112, and seeds 3-4 everywhere.

## 3. S: cluster-size scaling (16 -> 128 GPUs)

**Question.** With load per GPU fixed, do the per-session results and the methods' order change as the cluster grows
from 16 to 128 GPUs? (Also: does the simulator remain usable at that size?)

| grid | sites x GPUs | 16 | 32 | 64 | 128 | 256 (wall time only) |
|---|---|---|---|---|---|---|
| `scale` (G 8, E9's site size) | E x 8 | 2 x 8 | 4 x 8 | 8 x 8 | 16 x 8 (= E9) | 32 x 8 |
| `scale_g4` (G 4) | E x 4 | 4 x 4 | 8 x 4 | 16 x 4 | 32 x 4 | 64 x 4 |

- Load: 0.5 per GPU (N 8 / 16 / 32 / 64 / 128) and 0.94 (N 15 / 30 / 60 / 120 / 240).
- Fixed: C 10 Gbps, M 32 GB, dwell 180 s, seeds 0-4, six methods.
- Size: 300 runs per grid, about 10-15 min each.
- R0: the `scale` 128-GPU points at seeds 0-2 equal the frozen sweep.
- R1: the 2-site points have OTTER = Unstaged.

Choice of grid (decision G2):
- `scale` keeps E9's 8 GPUs per site, so 128 GPUs is the frozen primary point. But 16 GPUs is then 2 sites, where
  staging cannot act (R1): a geometry artefact, not a scaling result.
- `scale_g4` starts at 4 sites, so every size has staging candidates. But its 128-GPU point (32 x 4) is not E9's
  configuration.
- Proposal: `scale` primary, with the 2-site point marked "no staging candidate"; `scale_g4` as a robustness row.

## 4. Metrics (both experiments; medians over seeds, min-max for the first two)

- Stalled s / session-h; stalls > 1 / 2 / 5 / 10 s per session-h.
- Local share and remote share.
- Moves reaching local service (completion); time without local service per move.
- Staging GB / session-h; all bytes / session-h.
- Site memory mean / peak; link utilisation p50 / p99.
- Blocked starts.
- Simulator wall time per run.

## 5. Proposed criteria (for review; fixed at freeze)

Descriptive by default, as `scalability_draft.md`. Two optional confirmatory checks extend CL-H1's stall part
(decision G3):
- **L-H1.** At every N and both C, OTTER's median stalled s / session-h < each of Full, Llumnix and SLLM.
- **S-H1.** At every size and both loads, the same.

CL-H1's local-share part failed in the frozen sweep (a tie with Full). It is reported here, not tested again.

Predictions [H] (not rules):
- L: stalled seconds rise with load until sites fill, then fall as remote service takes over, for every method. Local
  share falls steeply above about 0.75 per GPU. The OTTER-to-baseline stall ratio holds roughly constant up to the
  point where remote service dominates. At 1 Gbps, staging hurts more as load rises (CL-H3 found 0 / 36 helping cells
  at N 64).
- S: per-session results flatten from about 8 sites on. The non-blocking core gives no contention with size.
  - Differences at 16-32 GPUs come from geometry. The paper says so and does not read a flat curve as "OTTER scales".
  - Wall time grows about linearly in sessions (5 s at 256 GPUs, 0.94 per GPU).

## 6. Labels and dependencies

- Labelled **simulated**. Calibrated from Figs. 5, 7, 8, 10; validated on Fig. 11 (76 / 76).
- **D5:** delta bytes beyond 240 calls are extrapolated until the Fig. 10 long-age runs. If those change the
  calibration, the gate is re-run, then L and S are re-run (minutes).
- **[A11]:** the store is the idealized one. The A11 sensitivity (protocol DRAFT 1, 9e926750) applies to these grids
  too, if it is run.
- Two-session sharing: the model assumes equal max-min on site links. The formal concurrency experiment (X1 / X2)
  tests that on two sessions only, and the model is not changed before this freeze.
- Gates first: R0 and R1 must PASS before any table is read. A FAIL stops the experiment for a review.

## 7. Decisions needed

| # | question | proposal |
|---|---|---|
| G1 | L grid: N 16-120 in steps of 16, C 10 and 1 Gbps, 5 seeds | approve |
| G2 | S grid | `scale` (G 8) primary with the 2-site point marked; `scale_g4` as robustness |
| G3 | L-H1 / S-H1 confirmatory, or descriptive only | confirmatory (stall part only); everything else descriptive |
| G4 | when to run | now as preliminary (labelled "delta extrapolated"), re-run after the Fig. 10 long-age calibration; or wait |
| G5 | 256 GPUs | wall time only, not in a figure |
| G6 | figure | one panel each: L = stalled s and local share vs sessions per GPU; S = the same vs GPUs; or text numbers (no appendix) |
| G7 | S-A' core oversubscription | keep optional (model extension, unvalidated) |
