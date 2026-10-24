# Experiment VD-2 - continuity-critical state reconstruction at the destination: preregistration REVISED DRAFT 2 (2026-10-24)

Status: **FROZEN 2026-10-24** (freeze record `../expVD2_freeze.md`; approved by the user after revised draft 2). Implementation `tools/eval` commit 5c638cf (emulator only, dry-tested); nothing run at the freeze. Earlier status: **REVISED DRAFT 2.** Revision per the
2026-10-24 review: H3 keeps the >= 50 % criterion and gains a descriptive restoration criterion (section 5); H5 covers
post-bind-20 content and color; H6 keeps its limits and adds a preferred 0.3 s target, with combination costs
evaluated on their own; DR-1 and DR-2 both run with per-layer cache fidelity, DR-4 predefined as an exploratory
diagnostic outside the verdicts; relevance-aware binding is excluded; host D after the isolation checks.

**Primary research question:** can a compact, source-derived temporal anchor preserve pre-migration visual identity
throughout the Sink-less window without sacrificing fast local resumption? A diagnosis experiment on the VC / VD emulator
(one GPU, no network). It tests candidate M1 variants as emulator conditions; M1, M2 and M3-v2 stay frozen, and no
frozen result changes. If a condition succeeds here, it is implemented as a separate M1 variant and evaluated end to
end on the testbed under its own preregistration (section 8).

**Goal (fixed by the 2026-10-24 review):** preserve the visual identity and temporal consistency established before
the migration, without requiring pixel-exact reference-trajectory recovery. "Abandoning the reference for a different
natural video" is not a goal.

## 1. What VC and VD established (disclosed inputs to this design)

- The **reset jump** (V1 5-9x the local median on dog, 2-3x on butterfly) is caused by the VAE decoder cache being
  empty and the recent KV being empty; keeping both brings it below REF's own P99 on every input and schedule (VD-H2,
  VD-H3, VD-H5). The decoder cache holds only the last 2 time steps of each layer's input (`vae.py` CACHE_T = 2).
- The **Sink-less content change** (DINO -0.14 to -0.43 against REF bands 0.02-0.22 wide, color drift 0.7-2.5 dE,
  warp-error ratio 1.2-2.3, on all four inputs) is not reduced by the decoder cache, the recent KV or masking
  (VD-H1 not supported, VD-H4 supported). It lasts the whole Sink transfer. A cold restart, which carries no state,
  ends with content similarity -0.01 to REF after its restart: a Sink built from the current input anchors content.
- After the exact Sink binds, every input returns to REF's content, color and motion consistency (VC report), so the
  bind itself is not the problem; the window before it is.

## 2. Candidate mechanisms (all destination-side; transfer sizes stated)

| id | mechanism | what it needs from the source | cost at the destination | targets |
|---|---|---|---|---|
| **DR-k** decoder reconstruction | before the first call, decode the source's last k latent frames through the VAE decoder with an empty cache and discard the output. CACHE_T = 2 says each layer keeps its last 2 input time steps; it does **not** guarantee that 2 latent frames reproduce the cache, because deeper layers' inputs depend on earlier frames through the cache. The fidelity is measured per layer | k latent frames (k = 1, 2 in the verdicts; about 200 KB each) added to the fast path | one streaming decode of k frames | reset jump |
| DR-4 (exploratory, predefined) | as DR-k with k = 4; run only if DR-2's per-layer fidelity is poor (section 4); **excluded from every verdict** | 4 latent frames (~800 KB) | one decode of 4 frames | diagnostic |
| **RP-1** one-chunk replay | replay the source's last input chunk (4 frames) from a session seeded like a cold restart, keeping its recent KV and VAE caches; then continue | the chunk's input frames (~5 MB FFV1) or nothing if the destination already has the input | one generation call (~0.6 s) | reset jump, first calls |
| **TS-in** temporary Sink, input-based | run the model's `prepare` on [last input frame, current chunk] (the cold-restart path) and keep only the Sink slots it writes; generate with refresh frozen; swap in the exact Sink when it arrives | nothing beyond the fast path | one `prepare` (~0.5 s) | Sink-less content change |
| **TS-out** temporary Sink, output-based | as TS-in, but `prepare` is fed the source's **last output frames** (its last 1-2 latent frames decoded here), so the temporary Sink carries the pre-move appearance | 1-2 latent frames (~200-400 KB) | one decode + one `prepare` | Sink-less content change **and** identity |
| DR-2 + TS-out, RP-1 + TS-out | combinations | as above | as above | both problems |
| (relevance-aware binding) | **excluded from VD-2** (review decision D3): not a candidate mechanism, and VD-2's question is whether compact reconstruction is feasible at all | - | - | - |

Frozen M1 (zero Sink, empty caches) is the control; it is VC-1's OT-1 / OT-L run and is not re-run.

## 3. Conditions and runs

Inputs dog and butterfly-feeding-slow-motion first (train and audi-snow-trail added only if an effect appears);
schedules OT-1 (1 Gbps, 24-call window) and OT-L (320 Mbps, 74-call window); seed 0.

Conditions per input and schedule: DR-1, DR-2, RP-1, TS-in, TS-out, DR-2+TS-out, RP-1+TS-out (7), plus the control.
**28 emulations**, about 3 min each, about 1.5-2 h on one GPU; frames stored as in VC. DR-4 adds at most 4
exploratory emulations, run only under the section-4 trigger.

## 4. Metrics (VC's definitions, unchanged) plus cost

- V1 at the reset and at the bind (the swap of a temporary Sink is a second potential jump; it is measured as the
  bind-call V1);
- Sink-less window: DINO content similarity to the pre-move calls and to REF, CLIP prompt alignment, dE, E_O / E_R;
- post-bind-20 and last-10 windows as in VC; PSNR trajectory (crossing, sustained, terminal) as context;
- **restoration (descriptive, per window):** whether the Sink-less window's DINO similarity to the pre-move calls
  lies inside REF's own P5-P95 band of 10-call windows (the VC band). A 50 % gap reduction (H3) is an improvement
  criterion only; it is never equated with continuity preservation. Preservation is reported only when the window
  statistic is inside REF's band.
- **cost:** the destination's serial GPU time for the reconstruction before its first call, measured per mechanism
  and, for a combination, measured for the combination itself (not summed from its parts); bytes the mechanism would
  add to the fast path (latent frames, input chunk). The emulator cannot measure overlap with the first denoising
  call, so the serial time is reported as an upper bound on the TTFO increase.
- **decoder-cache fidelity for DR-k, per layer:** for every cached tensor, max |diff| and the relative Frobenius
  error between the reconstructed cache and the source's cache at the same call, listed by layer and summarized
  (median and worst layer). **DR-4 trigger (fixed now):** DR-4 runs if DR-2's worst-layer relative error exceeds 0.10
  or its reset V1 misses H1; it is reported as exploratory and enters no verdict.

## 5. Hypotheses (directional; thresholds proposed, fixed at the freeze; every input and schedule must agree)

| id | statement | success rule (proposed) |
|---|---|---|
| VD2-H1 | DR-2 removes most of the reset jump | V1(reset) <= 0.5 x frozen M1's, and <= REF's P99 + 1.0 |
| VD2-H2 | RP-1 removes the reset jump and the first-4-call inconsistency | V1(reset) <= 0.5 x frozen M1's; first-4 E_O / E_R lower than frozen M1's |
| VD2-H3 | TS-out keeps the pre-move content during the Sink-less window | **primary improvement criterion:** window DINO similarity to the pre-move calls at least halfway from frozen M1's value to REF's (>= 50 % of the gap closed), and dE to REF lower than frozen M1's. **Reported next to it, not part of the rule:** whether the window statistic returns inside REF's normal-variation band (section 4); only that counts as preservation |
| VD2-H4 | TS-out preserves identity better than TS-in | window DINO similarity (to the pre-move calls) higher for TS-out than TS-in on every input and schedule |
| VD2-H5 | a temporary Sink does not break the exact bind or the post-bind stream | on dog, the first call >= 35 dB within 5 calls of frozen M1's; on butterfly, terminal PSNR within 1 dB of frozen M1's; bind-call V1 <= 2 x frozen M1's bind V1; **and** post-bind-20 DINO similarity to REF not lower than frozen M1's by more than REF's band width, and post-bind-20 dE to REF not higher than frozen M1's by more than 0.5 |
| VD2-H6 | the cost stays small | serial reconstruction time <= 1.0 s for DR-k and TS variants, <= 1.5 s for RP-1 and for each combination measured as a whole; added bytes <= 1 MB for DR / TS, <= 6 MB for RP-1. **Preferred target, reported for every mechanism and combination:** <= 0.3 s serial time (not a pass / fail rule) |

**Mapping to the next step (fixed now):**
- H1 (or H2) and H3-H5 supported: implement "DR-2 + TS-out" (or "RP-1 + TS-out") as an M1 variant on the node, and
  preregister a testbed experiment measuring TTFO-local, delivery gap, bytes, GPU overhead, bind pause and VC's
  continuity metrics against frozen M1 (section 8).
- H3 fails for both TS variants: the Sink-less content change needs information the destination does not have; the
  next question is a compact approximate Sink from the source (quantized or partial), designed only then.
- H5 fails: a temporary Sink costs the exact bind; TS is dropped and only DR / RP proceed.
- H6 fails for a mechanism: it is reported with its cost and not carried forward.

## 6. Validity

Every stream passes G3; the control equals VC-1's run; DR-k's reconstructed cache is compared with the source's cache
(fidelity reported, no threshold); the temporary Sink is verified to occupy exactly the sink slots (positions,
refresh frozen) and to be fully overwritten at the swap (digest of the sink region after the bind equals the exact
Sink's); with every flag off, the G1 replay stays call-by-call identical.

## 7. Implementation sketch (emulator only; `vc_emulate.py` conditions, no change to node or mechanism code)

- DR-k: at the reset, keep the source's last k latent frames (from the serialized in-flight / hidden state), then
  `pm._timed_stream_decode` on them in the fresh session before the first call.
- RP-1: `Runner.replay_restart(c, 1, sink0=False)` semantics on the destination, then restore the fast-path meta.
- TS-in / TS-out: `pm.start_stream_session(prompt, images)` on a scratch session, copy its sink slots (K, V, pos) into
  the live session's sink region, keep refresh frozen; at the bind the exact Sink overwrites them as today.
- Fidelity: at the DR reset, the source's VAE decoder cache tensors are kept (emulator side, never transferred) and
  compared layer by layer with the reconstructed ones before the first call.

## 8. After VD-2 (not part of this preregistration)

A testbed experiment for the selected variant: XB1-style single move and XB4-style repeated mobility, 3 reps, dog and
butterfly, measuring TTFO-local, delivery gap, measured bytes, destination GPU overhead, bind pause and the VC
metrics, against frozen M1 + M2 + M3-v2. Frozen results stay as recorded; the variant is reported next to them.

## 9. Open decisions

- **VD2-D1 (closed, with the revisions above)** - H1-H6 thresholds; H3's 50 % rule is an improvement criterion, the
  REF-band restoration criterion is descriptive; H5 extended to post-bind-20 content and color; H6 keeps its limits and
  reports the 0.3 s preferred target, combination costs measured on their own.
- **VD2-D2 (closed)** - DR-1 and DR-2 in the verdicts, with per-layer cache fidelity; DR-4 predefined as an
  exploratory diagnostic under the section-4 trigger, outside every verdict.
- **VD2-D3 (closed)** - relevance-aware binding excluded.
- **VD2-D4 (closed)** - host D, after the GPU and storage isolation checks (`run_vc.py preflight`).
- Open: the freeze itself, after this revision is reviewed.
