# Experiment VD-3 - confirmation of local reconstruction (DR-2 + TS-in): preregistration DRAFT (2026-10-24)

Status: **DRAFT for review. Not frozen; nothing implemented or run.** Follow-up decided after VD-2 (2026-10-24
review): VD-2's frozen verdicts stay NOT SUPPORTED as recorded; the combination this draft tests was chosen after
seeing VD-2's cells, so VD-3 is an **independent confirmation** on data VD-2 did not use. Emulator only, one GPU; M1,
M2 and M3-v2 stay frozen; no frozen result changes. RP-1, TS-out and the approximate Sink are out of scope (review
decisions).

**Question (fixed by the review):** can reconstructing the decoder from a small latent history and generating a
temporary Sink from the current input preserve the pre-migration video's continuity without migrating the full
temporal state, and at what reconstruction latency?

**Design principle under test (hypothesis, named only if VD-3 supports it):** continuity-critical state can be
reconstructed locally rather than migrated in full.

## 1. What VD-2 showed and what VD-3 must not reuse

VD-2 (dog, butterfly; OT-1, OT-L; seed 0): DR-2 cut the reset jump to 0.39-0.54 x with a reconstructed cache far from
the source's (relative error 0.5-1.6); TS-in restored 71-98 % of the Sink-less content gap at zero bytes and kept the
exact bind; TS-out was no better and drifted in color; RP-1 forfeited reference recovery. DR-2 + TS-in was never run
as a combination. Those eight input x schedule cells are **replication cells** here (their data was seen). The
**confirmation set** is new: train and audi-snow-trail at seed 0 (OT-1, OT-L), and all four inputs at seed 1 (OT-1,
from the frozen W2 seed-1 runs: move 34, bind 58-59). Verdicts are decided on the confirmation set; replication cells
are reported next to them.

## 2. Units and conditions

| unit (input x seed) | schedules | source of the schedule | control (frozen M1) |
|---|---|---|---|
| dog, butterfly s0 | OT-1, OT-L | VC-1 (replication) | VC-1's runs (exist) |
| train, audi s0 | OT-1, OT-L (train OT-L: copied schedule, counterfactual) | VC-1 (confirmation) | VC-1's runs (exist) |
| dog, butterfly, train, audi **s1** | OT-1 | `expW_W2_<input>_s1` `reuse_dyn` (move 34, bind 58 / 59) (confirmation) | **new**: REF baseline and frozen-M1 OT-1 run at seed 1 |

Conditions per unit and schedule (emulator, `vc_emulate.py` kind `vd3`):

| id | mechanism | why it is here |
|---|---|---|
| TSin | temporary Sink from the current input (VD-2's TS-in; decoder cache zero as in frozen M1) | component alone |
| DR2 | decoder cache from the source's last 2 latent frames (0.4 MB) | component alone |
| **DR2+TSin** | both | the candidate |
| TSin-KC | TS-in, **keeping the decoder cache that its own prepare produced** (the prepare decodes the current input's latents; frozen M1's restore zeroes that cache). Zero bytes, no extra compute over TS-in | a reconstruction that shares TS-in's compute: if it matches DR-2 + TS-in, the 0.52 s decode is unnecessary |
| DR2-stale | DR-2 with the source's latent frames from 16 calls before the move (a real but wrong history) | review request: is it the correct history or any warmed cache that matters? |
| DR2-noise | DR-2 with Gaussian latent frames | the "any nonzero cache" control |

12 unit x schedule combinations x 6 conditions = 72 emulations, plus 4 seed-1 controls and 4 seed-1 REF baselines:
about 4.5 h on one GPU (D). Frames stored as in VC.

## 3. Metrics (VC / VD-2 definitions, unchanged)

Per cell: V1 at the reset and at the bind; Sink-less window DINO similarity to the pre-move calls (with REF's band
for the descriptive in-band criterion), CLIP, dE, E_O / E_R; first-4 E; post-bind-20 DINO difference to REF and dE;
PSNR trajectory (first >= 35 dB, terminal); serial reconstruction cost (per mechanism and per combination as a whole),
bytes added; DR cache fidelity per layer (DR2, DR2-stale, DR2-noise).

**Latency trade-off (review request):** the serial cost is an upper bound on the TTFO-local increase. VD-3 also
measures, on one unit, whether the two reconstructions can share or overlap work: (i) TSin-KC's cost vs TS-in's,
(ii) the DR-2 decode launched on a second CUDA stream concurrently with the first generation call (the generation's
wall time with and without it, 5 repeats). This is an engineering measurement, reported with the verdicts; the
emulator does not model the network.

## 4. Hypotheses (confirmatory on the confirmation set: train, audi at s0 and all four inputs at s1; every unit and schedule must agree; thresholds proposed, fixed at the freeze; effect sizes first)

| id | statement | success rule |
|---|---|---|
| VD3-H1 | DR-2 + TS-in halves the reset jump | V1(reset) <= 0.5 x frozen M1's |
| VD3-H2 | DR-2 + TS-in restores the Sink-less content | window DINO closes >= 50 % of the gap to REF, and dE to REF not higher than frozen M1's. Descriptive: in REF's band (preservation), reported per cell |
| VD3-H3 | the combination keeps each component's benefit | V1(DR2+TSin) <= 1.1 x V1(DR2), and DINO(DR2+TSin) >= DINO(TSin) - 0.01 |
| VD3-H4 | the exact bind and the post-bind stream are kept | where frozen M1 rejoins: first call >= 35 dB within 5 calls of frozen M1's; where it does not (butterfly): terminal PSNR within 1 dB; bind V1 <= 2 x; post-bind-20 DINO not below frozen M1's by more than REF's band width; post-bind-20 dE <= frozen M1's + 0.5 |
| VD3-H5 | the cost is bounded | serial cost of DR-2 + TS-in <= 1.5 s; bytes <= 1 MB. Reported: the 0.3 s preferred target, the overlap measurement (section 3), and TSin-KC's cost |
| VD3-H6 | the correct latent history matters (mechanism) | V1(DR2) < V1(DR2-stale) and V1(DR2) < V1(DR2-noise) on every confirmation cell. If not, the paper states that a warmed cache of any content removes the jump, and DR-2 is replaced by the cheapest such cache (TSin-KC) |
| VD3-H7 (descriptive) | TSin-KC vs DR-2 + TS-in | reported per cell: V1, DINO, cost; no rule |

Generality statement: each hypothesis is reported as "supported on k of 6 confirmation combinations (2 inputs x 2
schedules at s0, 4 inputs at s1)", with the replication cells shown next to them; claims are limited to these inputs,
two seeds, one model and the emulated schedules.

**Mapping to the next step (fixed now):**
- H1-H5 supported: implement the variant on the node (M1-R: fast path + 2 latent frames; destination prepare and
  decode before the first call, overlapped if section 3 shows it works) and preregister a testbed experiment
  measuring TTFO-local, delivery gap, bytes, GPU overhead, bind pause and the VC metrics against frozen M1 + M2 +
  M3-v2, with frozen results kept and the variant reported beside them.
- H6 not supported and TSin-KC within H1-H4: the variant is TS-in with its cache kept (zero bytes).
- H2 fails on the confirmation set: the temporary Sink does not generalize; reported, and the approximate Sink
  question reopens.
- H5 fails: overlap engineering before any testbed experiment.

## 5. Validity

G3 on every stream; the seed-1 REF baselines and controls generated by the same emulator with G1-style checks against
the W2 seed-1 runs (frozen-M1 OT-1 replay vs the real run, call by call); with every flag off the dog RD-X replay
stays identical; DR2-stale's and DR2-noise's latent sources are recorded; TSin-KC's kept cache is verified to be the
prepare's (digest).

## 6. Implementation notes (emulator; `vc_schedules.py` seed-1 units from `expW_W2_*_s1`, `vc_emulate.py` kind `vd3`)

TSin-KC: at the reset, run TS-in's prepare, save its sink slots **and** its VAE decoder cache tensors, restore the
fast path (which zeroes the caches), write both back. DR2-stale: capture the decode inputs of calls move-17 and
move-16 (the latent deque keeps the last 4 calls only, so the stale pair is captured separately when the condition is
VD3). DR2-noise: `torch.randn` with the latent shape, seeded. Overlap test: a second CUDA stream for the decode while
the first `runner.step` runs; wall times with `cuda.synchronize`.

## 7. Open decisions

- **VD3-D1** thresholds of H1-H6 as proposed.
- **VD3-D2** the confirmation set (train, audi s0; all four at s1) and whether OT-L at s1 is added (no RD-X run exists
  at s1; it would be a copied schedule).
- **VD3-D3** the overlap measurement in scope (section 3) or deferred to the testbed variant.
- **VD3-D4** host D; about 4.5 h.
