# M1 input-log replay: E0 / E1 plan and reading rules (fixed before the run, 2026-10-27)

Approved scope: E0 and E1 only (proposal.md section 7). No migration protocol, no E2, no frames or visual
inspection, no new conditions. Tool: `tools/eval/m1_replay.py`; CPU test `tools/eval/test_m1_replay.py` (tiny real
CausalWanModel with refreshes and a t_refresh realignment in the window; tampered input and dropped decisions must fail
E0) passes.

## 1. Setup

- Cells: the 12 VD-4 / VD-5 confirmation cells (train s0 / s1, audi s0 / s1, dog s1, butterfly s1; OT-1 at M = 34,
  OT-L at M = 80). One process per unit on host D (L40S), streams started from call 0 with the VC Runner (same calls
  and seeds as REF).
- Source log, recorded by a hook on the generator for calls M - 12 .. M: the generator inputs of both Stream-Batch rows
  as fed, timesteps, row starts / ends, ring metadata before and after the call, and the source's cache decisions
  (written slot per layer and row; a write into a Sink slot = adaptive refresh). Ring snapshots before calls M - 12,
  M - 6, M - 3, M.
- Replay: generator only (no VAE), forced decisions (refresh off, the source's refresh slot pushed to the front of the
  layer's / row's eviction queue before the call).

## 2. E0: exact replay correctness

Restore the exact ring (K, V, positions, end indices, current_step, eviction queues) at M - 12; replay calls
M - 12 .. M - 1. **Pass** per cell = all of: every replayed call's metadata equals the source's after that call; every
written slot (all layers, rows) equals the source's bitwise; the ring at M equals the source's bitwise on every layer,
row and slot (K and V) with equal metadata; a replay of call M gives the source's generator output bitwise.
**E0 passes** only on 12 / 12 cells. If any cell fails, E1 is not read: the failure is investigated and reported first.

## 3. E1: log-only convergence

For w in {0, 3, 6, 12}: restore the ring at M - w with the recent slots (3-5) zeroed and the Sink and metadata exact;
replay calls M - w .. M - 1. Measured: recent K / V relative error (Frobenius, all layers, rows, recent slots) against
the source at M, by layer and by slot age; Sink relative error and the number of refresh decisions inside the window;
the relative error of every replayed call's written slot against the source's (convergence trajectory, w = 12); the
call-M generator output error per row; replay time per call.

Reading (descriptive; E2 decides continuity):
- **Continuity proxy:** r(w) = call-M output error of the decoded row (last Stream-Batch row) at w, divided by the
  same error at w = 0 (exact Sink, zero recent: the S3 analogue; the source's own ring, RS3, gives 0).
  - "Short window plausible" if some w <= 6 has r(w) <= 0.10 on 12 / 12 cells.
  - "Not plausible" if r(12) > 0.50 on >= 6 / 12 cells.
  - "Unclear" otherwise.
- **Cost:** replay keeps up if the E0 replay time per call (median) is below the source call interval (median full
  step, calls before the recorded window) on 12 / 12 cells. Also reported: replay vs the source's generator-only time,
  and log bytes per call.

## 4. Validity and limits

- Determinism: the generator inputs of the unit's two source streams (OT-1 and OT-L runs) are equal on every common
  call (0 .. 34). Every replayed call's metadata equals the source's (the forced decisions took effect) in E0 and E1.
  The tool records the commit and whether `tools`, `models`, `streamv2v` were modified.
- The proxy is the generator output at the first destination call, not P1: no decoding (DR-2), no frames, no V1.
- E1 assumes the Sink is exact at M - w (predicted move, M2 pre-copy done). A refresh inside the window writes a
  replayed (approximate) frame into a Sink slot; counted and reported.
- Cost: about 30-40 min of GPU on D for the 6 units; host memory about 25 GB per process (four ring snapshots and the
  13 recorded calls' written slots).
