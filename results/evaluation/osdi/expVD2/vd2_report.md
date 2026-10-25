# Experiment VD-2 - report (2026-10-24; complete, including the DR-4 exploratory cells)

Frozen plan `preregistration.md` (FROZEN 2026-10-24, `../expVD2_freeze.md`). Aggregation `tools/eval/aggregate_vd2.py`
-> `vd2_results.md` / `.json`. 28 emulations on host D (dog, butterfly x OT-1, OT-L x 7 conditions), all valid, G3
passed on every stream; controls = VC-1's frozen-M1 runs. One implementation fix during the run (the temporary Sink
writes only the two slots prepare fills and never positions; recorded in the frozen document; no rule changed).

## 1. Verdicts (frozen rules: every input and schedule must agree)

| id | statement | verdict | where it fails |
|---|---|---|---|
| VD2-H1 | DR-2 halves the reset jump and lands within REF P99 + 1 | **NOT SUPPORTED** (3 of 4) | dog OT-1: V1 ratio 0.54 (rule <= 0.50); the other three 0.40, 0.39, 0.42 |
| VD2-H2 | RP-1 halves the reset jump and lowers first-4 warp error | **NOT SUPPORTED** (0 of 4) | V1 ratio 0.60-0.76 |
| VD2-H3 | TS-out closes >= 50 % of the Sink-less content gap and lowers color drift | **NOT SUPPORTED** (0 of 4) | the gap closes 67-93 %, but TS-out's color drift is **higher** than frozen M1's in 3 of 4 (dE 3.2-3.3 vs 1.8-2.2 on dog) |
| VD2-H4 | TS-out preserves identity better than TS-in | **NOT SUPPORTED** (0 of 4) | TS-in is equal or better on every cell (0.945 vs 0.941; 0.965 vs 0.939; 0.838 vs 0.831; 0.848 vs 0.843) |
| VD2-H5 | temporary Sinks keep the exact bind and the post-bind stream | **NOT SUPPORTED** (0 of 4) | the rule covers RP-1 + TS-out, and every RP-1 cell forfeits reference recovery (dog terminal 27-28 dB, never >= 35 dB). TS-in, TS-out and DR-2 + TS-out pass every H5 clause on their own (dog rejoin at call 63-65 vs 66; bind V1 0.74-1.11 x; post-bind DINO within 0.001 of REF) |
| VD2-H6 | costs within limits | **NOT SUPPORTED** (0 of 4) | RP-1 + TS-out: 1.83 s (limit 1.5) and 6.4 MB (limit 6). Every other cell is within its limits; none meets the preferred 0.3 s except DR-1 (0.26 s) |

By the frozen rules nothing is supported. The cells behind the rules say more (section 2), and the mapping fixed in
the preregistration (section 3) decides what happens next.

## 2. What the cells show (effect sizes; dog / butterfly, OT-1 / OT-L)

**Reset jump (V1, x frozen M1).** DR-1 0.60 / 0.47 / 0.49 / 0.42; DR-2 0.54 / 0.40 / 0.39 / 0.42; DR-2 + TS-out
**0.45 / 0.42 / 0.34 / 0.37**; RP-1 0.75 / 0.76 / 0.70 / 0.60; TS alone 0.9-1.2 (no effect). Decoder-cache
reconstruction from two latent frames (0.4 MB, 0.52 s serial) removes half to two thirds of the jump, in line with VD
(keeping the real cache: 0.27-0.45). The reconstructed cache is **not** close to the source's (per-layer relative
error median 0.49-0.74, worst 1.05-1.63 at layer 6); the jump still halves, so the first decode's effect comes from
having *a* warmed-up cache rather than the exact one. The DR-4 trigger (worst error > 0.10) fired; DR-4 runs as
exploratory.

**Sink-less content (DINO to the pre-move calls; frozen M1 0.54 / 0.59 / 0.72 / 0.72, REF 0.97 / 0.97 / 0.89 / 0.87).**
A temporary Sink restores most of it: TS-in **0.945 / 0.965 / 0.838 / 0.848** (gap closed 95 / 98 / 71 / 86 %), TS-out
0.941 / 0.939 / 0.831 / 0.843. Inside REF's own band in 5 of 16 TS cells (dog OT-L TS-in; butterfly OT-1 TS-in and
both combinations; dog OT-1 both combinations), just below it elsewhere. Prompt alignment and warp error move with it
(DR-2 + TS-out first-4 E 1.27-1.92 vs 2.1-3.2). The source's last output frames give no identity advantage over the
current input (H4), and TS-out drifts in color more than TS-in (dE 3.2-3.3 vs 1.2-1.6 on dog).

**Exact bind afterwards.** TS-in, TS-out and DR-2 + TS-out bind the exact Sink as frozen M1 does: dog rejoins at
call 63-65 (frozen 66), terminal 43.3-44.9 dB, post-bind content within 0.001 of REF; butterfly ends at 28.6-30.7 dB
as frozen M1 does. **RP-1 does not**: the replayed session carries its own positions and in-flight state, and after
the bind the stream stays near 26-28 dB on dog with content preserved (post-bind DINO within 0.006 of REF). RP-1
converts the post-bind stream from reference recovery to plausible divergence; the frozen rule counts that as failure.

**Cost (serial, upper bound on the TTFO increase).** DR-1 0.26 s; DR-2 0.52 s; TS 0.78 s (one prepare); DR-2 +
TS-out 1.30 s; RP-1 1.05 s; RP-1 + TS-out 1.83 s. Bytes: DR-2 0.4 MB, TS-in 0, TS-out 0.4 MB. Only DR-1 meets the
preferred 0.3 s. OTTER's TTFO-local would move from 0.67 s to about 1.2-2.0 s with a decoder reconstruction and a
temporary Sink, still 18-30 x faster than R-full, if nothing overlaps.

## 3. Reading under the frozen mapping

- "H3 fails for both TS variants" was the condition for moving to an approximate Sink from the source. It does not
  hold as written: TS-in closes 71-98 % of the gap and lowers color drift on 3 of 4 cells; TS-out fails H3 only on
  color drift. The content-restoring effect of a temporary Sink is real and large; the preregistered TS-out choice
  (identity from the last output frames) was the wrong variant, and the hypothesis that output frames preserve identity
  better (H4) is rejected.
- "H5 fails: TS is dropped" was written for a temporary Sink that breaks the bind. The TS cells do not break it; the
  H5 failure comes from RP-1. RP-1 is dropped (it forfeits exact recovery and costs the most).
- DR-2 misses H1 by 0.04 on one cell and passes the other three; the decoder-cache mechanism is confirmed in
  direction, with the fidelity finding (the exact cache is not needed) as a new fact.
- Nothing here changes a frozen result. Any mechanism built from this needs its own preregistration; the candidate
  this data points to is **DR-2 + TS-in** (0.4 MB, about 1.3 s serial before overlap), which no cell tested as a
  combination. A follow-up (VD-3) would test DR-2 + TS-in with H1 / H3 / H5-style rules re-stated for TS-in, the
  preferred 0.3 s target as a hard limit only if overlap with the first call is implemented, and train / audi added.
  That is a proposal, not a decision.

## 4. DR-4 (exploratory, run under the section-4 trigger; outside every verdict)

Four more latent frames do not help: reset V1 ratio 0.53 / 0.37 / 0.39 / 0.43 (DR-2: 0.54 / 0.40 / 0.39 / 0.42) at
twice the cost (1.04 s, 0.8 MB). The reconstructed cache gets closer to the source's (median relative error 0.20-0.27
vs 0.49-0.74; worst layer 0.43-0.82 vs 1.05-1.63) without changing the jump. Cache fidelity and the visual effect are
therefore decoupled over this range, which is what VD-3's DR2-stale / DR2-noise controls test directly.

## 5. Pending

The decision on the VD-3 follow-up (`../expVD3/preregistration.md`, draft).
