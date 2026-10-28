# M1 input-log replay: E0 / E1 record (2026-10-27)

Run on host D (L40S) at 69b6e4f7, clean tree, recorded in e50dfdd0 (merged on the Mac). Reading rules from
`e0e1_plan.md` (committed before the run). Raw files: `e0e1/<unit>.json`, aggregate `e0e1/e0e1_results.md`. Scope was
E0 and E1 only: no protocol, no E2, no frames.

## 1. Validity

- Determinism: in all 6 units the generator inputs of the two source streams are equal on every common call (35 calls).
- Forced decisions took effect: every replayed call's metadata (positions, end indices, current_step, eviction queues)
  equals the source's, in E0 and in every E1 window, on 12 / 12 cells.
- E1 sanity: layer 0 of the recent slots is bitwise equal to the source's for w = 6 and 12 on 12 / 12 cells (layer 0
  has no attention context). At w = 3 it is not on 4 cells, because a refresh in the last 3 calls wrote into a Sink
  slot and left one recent slot unwritten (zero). This was expected and found in the CPU test.

## 2. E0: exact replay is bitwise correct

**E0 passes on 12 / 12 cells.** From the exact ring at M - 12, replaying 12 logged calls reproduced:
- every written slot, bitwise (12 / 12 calls in every cell);
- the whole ring at M (K and V, every layer, row and slot), bitwise, with equal metadata;
- the source's call-M generator output, bitwise.

The replay windows contained 1-14 adaptive-refresh decisions per cell, so forced decisions are exercised. Log size:
399,408-399,426 bytes per call (generator inputs of both rows, timesteps, row starts / ends, refresh decisions).

## 3. E1: log-only replay converges geometrically but not to zero within 12 calls

Ranges over the 12 cells (recent slots zeroed at M - w; Sink and metadata exact):

| w | recent K rel. error at M | recent V rel. error at M | call-M output error ratio r(w) |
|---|---|---|---|
| 0 | 1 | 1 | 1 (S3 analogue) |
| 3 | 0.22-0.34 | 0.41-0.61 | 0.21-0.45 |
| 6 | 0.07-0.12 | 0.13-0.23 | 0.064-0.21 |
| 12 | 0.011-0.025 | 0.020-0.054 | 0.031-0.065 |

- **Convergence trajectory (w = 12):** the K error of the slot each replayed call writes falls from 0.28-0.47 at the
  first call to 0.009-0.018 at the twelfth (V from 0.51-0.78 to 0.018-0.037). It roughly halves every 1.5-2 calls over
  the first 8 calls, then flattens to about 1-2 % for K. The decline is still slow at M - 1 on cells without refreshes
  (dog s1 OT-1: 0.014, 0.011, 0.009).
- **Sink contamination:** in log-only mode, a refresh inside the window writes a replayed, approximate frame into a
  Sink slot. Sink K error at M reached 0.03 at w = 12 on four cells (audi s0 / s1 OT-1, train s0 OT-1, butterfly s1
  OT-L ~0.02). The exact-base mode has no such error (E0).
- **Reading (frozen rule):**
  - "Short window plausible" requires some w <= 6 with r(w) <= 0.10 on 12 / 12 cells. At w = 6 that holds on 5 / 12
    cells (butterfly OT-1 / OT-L, dog OT-1 / OT-L, and none of audi or train; audi s0 OT-L is 0.105).
  - "Not plausible" requires r(12) > 0.50 on >= 6 cells. r(12) <= 0.065 on 12 / 12.
  - The reading is therefore **unclear**. Replaying 12 calls closes 93.5-96.9 % of the first-output gap between exact
    Sink with zero recent (S3) and the source (RS3). Whether the remaining 3-6.5 % is visible at the boundary is a P1
    question that only E2 answers.

## 4. Replay cost

| quantity | value (median per call) |
|---|---|
| replay, generator only (outside the slowdown bursts below) | 0.118-0.125 s |
| source generator, same calls | 0.133-0.137 s |
| source call interval (encode + generator + decode) | 0.547-0.557 s |

- **Frozen rule:** the replay is below the source call interval on **10 / 12 cells**, so "keeps up on 12 / 12" is
  **not met as written**.
- The two failing cells (audi s1 OT-L, dog s1 OT-L) and a third anomaly (dog s1 OT-1, source pre-window call median
  2.2 s) come from contiguous bursts in which every generator call took 1.09-1.15 s. A burst starts and stops in the
  middle of a sequence, and hits the source's own calls too: in audi s1 OT-L the source generator median is 1.29 s.
  Outside the bursts, every replay call in the same cells took 0.12 s (the E1 w = 12 replays of both cells: 0.120-0.128
  s). The bursts look like external slowdown of host D's GPU (contention or throttling); GPU utilization by other
  processes was not recorded, so this is not proven.
- Outside the bursts the replay costs about 22 % of a source call interval (4.5x headroom), so a shadow can follow
  the source. A w-call warm-up costs w x 0.12 s of destination GPU: 0.73 s for w = 6, 1.45 s for w = 12, off the
  critical path for a predicted move. On the critical path, for an unpredicted move, the same time compares with
  shipping 1.73 GB (13.8 s at 1 Gbps; about 2.7 s native in follow-up A).

## 5. Is the mechanism still promising for practical M1?

- **The exact assumption holds.** Recent KV (and the whole ring) is a deterministic function of the logged inputs and
  decisions. Starting from an exact base, shadow replay reproduces the source bit for bit at 0.4 MB and 0.12 s per
  call, below the call interval. This makes the exact-base variant a validated mechanism: copy the ring once in the
  background, then follow the source by log. The state at the cutover is exactly RS3's, with no Recent KV on the
  critical path.
- **The log-only assumption holds only approximately.** Without the base, the error decays steadily but is still 1-2.5
  % (K) at 12 calls. It also leaks into the Sink through refreshes inside the window. Under the frozen reading this is
  "unclear", not a demonstrated short window.
- **Choice between the variants:** the exact base costs one background ring copy (1.73 GB of recent slots in addition
  to the Sink). Log-only avoids it but leaves a residual whose visual effect is unknown. Deciding needs E2, which is not
  approved, or a decision to adopt the exact-base variant.
