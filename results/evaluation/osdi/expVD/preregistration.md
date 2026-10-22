# Experiment VD - what state governs the visual discontinuity of an M1 reset: preregistration DRAFT (2026-10-22)

Status: **DRAFT for review. Not frozen; nothing implemented or run.** A diagnosis experiment on the RD / VC emulator,
one GPU, no network. It does not change M1, M2 or M3-v2: every condition is an emulator-side variant of what survives
a reset, plus one model flag that defaults to the frozen behavior. It runs in the same emulation unit as VC-1 (same
inputs, REF baselines and schedules), with its own hypotheses, result document and verdicts; VC-1's frozen-M1 results
are reported first and are never affected by VD's conditions.

Decisions taken 2026-10-22 (recorded): run VD with VC-1 in one unit; inputs dog and butterfly-feeding-slow-motion first
(train and audi-snow-trail only if an effect appears); schedules OT-1 and OT-L; the dilution precheck runs before the
factorial; nothing starts before VC-0 passes.

## 1. Question

VC measures whether OTTER's resumed video is discontinuous. VD asks **which lost state causes which discontinuity**, so
that any later M1 variant targets a measured cause rather than a guess. Candidate causes, each tied to a state the M1
fast path does not carry:

| candidate | state | mechanism (hypothesis, not established) | discontinuity it would explain |
|---|---|---|---|
| attention dilution | zero-filled Sink slots inside the attention range | a zero key has logit 0, so the slots take softmax mass; their zero values return nothing, so the effective tokens' attention is scaled down | global color / contrast drift during the Sink-less window |
| temporal decoding state | VAE decoder feature cache (1,801 MB) | the causal VAE decoder's temporal features restart from empty | the reset frame jump; the state study measured 19.6 dB at M+0 recovering by M+3 when only this cache is dropped |
| temporal encoding state | VAE encoder feature cache (1,069 MB) | same for the encoder | a smaller first-call effect (34.1 dB at M+0 in the state study) |
| short-term context | recent KV ring (1,645 MB) | the three most recent latent frames are gone from attention | the reset jump and the first Sink-less calls (state study: about -10 dB) |
| long-term context | the Sink itself | not testable without the Sink; VD measures everything else so that the residual is attributable to it | post-bind divergence that nothing else explains |

What is already known (disclosed): the state study measured these components' effect on PSNR to the reference at
M+0 .. M+3; it measured no boundary, flow or color metric and no Sink-less window. Task A measured recent-KV handoff on
trajectory recovery only (NO-GO). RD measured the reset spike (median 5.5x) but attributed it to nothing.

## 2. Precheck: attention dilution measured directly (before the factorial; ~10 min GPU)

On a Sink-less session (dog, after the OT-1 reset), for 4 calls, run the SDPA fallback attention with the softmax
weights exposed and record per layer and denoising row the **fraction of softmax mass on the zero Sink slots**,
averaged over queries. Report the distribution (median, max over layers). If the median fraction is below 0.01 in every
layer, masking cannot matter and VD-H1 is expected to fail; the factorial still runs, because the precheck is a
mechanism check, not a visual one. The precheck also validates the masked kernel: the masked `flash_attn_with_kvcache`
call (section 3) must equal the SDPA fallback with an explicit boolean mask on the same calls (max |diff| reported;
expected at bf16 rounding).

## 3. Conditions (per input, per schedule OT-1 and OT-L; emulator only)

Factorial of what survives the M1 reset, 2 x 2 x 2 = 8 conditions:

| factor | levels | implementation |
|---|---|---|
| S: zero Sink slots | **zero** (frozen M1: slots zero-filled and attended) / **masked** | a flag on the attention module (`causal_model.py`), default off. Masked: while the Sink is unbound, the KV-cache attention is called on `k_cache[:, sink_tokens:]`, `v_cache[:, sink_tokens:]` with `cache_seqlens - sink_tokens` (the Sink tokens occupy the first `sink_size x frame_seqlen` cache positions, and the kernel reads a contiguous prefix with no mask argument). RoPE, positions, refresh freeze and the bind are unchanged; the flag is cleared at the bind |
| D: VAE decoder cache | **reset** (frozen M1) / **kept** | after the reset's provision, `restore_state` with "vae", then the encoder map re-zeroed (kept = decoder only) |
| R: recent KV | **reset** (frozen M1) / **kept** | `restore_state` with "recent" (the Task A path writes the recent slots; here all three) |

The (zero, reset, reset) cell is frozen M1 and is the VC-1 OT condition itself (not re-run). The encoder cache is a
secondary factor: one extra condition (zero, decoder+encoder kept, reset) tests whether the encoder adds anything over
the decoder alone. Total new conditions per input and schedule: 7 + 1 = 8; two inputs x two schedules = **32
emulations**, about 3 min each, about 1.5-2 h of one GPU after the VC-1 unit. Bind and the post-bind horizon are
identical to VC-1's (the realized bind call).

Nothing is transferred: "kept" means the destination is given the state it would have had to receive. VD measures
whether keeping it helps; the cost of carrying it (1.8 GB decoder cache, 1.6 GB recent KV) is a separate question.
The state study already noted that the decoder cache is reconstructable from the last decoded latent (200 KB) plus one
decoder pass; that is the obvious cheap form if D matters.

## 4. Metrics (VC's definitions, `vc_metrics.py`, unchanged)

V1 reset spike (and the bind spike), V2 warp-error ratio and V3 motion ratio in the Sink-less window and post-bind,
V4 global color drift (to REF and to the pre-move calls), V5a content similarity and V5b prompt alignment post-bind,
PSNR trajectory (crossing, sustained, terminal). Paired OTTER - REF differences, REF bands and the VC block bootstrap.

## 5. Hypotheses (directional; effect sizes first; thresholds proposed, fixed at the freeze)

Main effects are the mean over the other factors' levels (a 2 x 2 x 2 design; interactions reported).

| id | factor | prediction | success rule (proposed) |
|---|---|---|---|
| VD-H1 | S masked | reduces Sink-less color drift and warp error | window V4 to REF and E_O / E_R both lower than with zero slots, in both inputs and schedules (main effect); size reported |
| VD-H2 | D kept | reduces the reset spike | V1(reset) lower by at least a factor 2 (main effect), both inputs and schedules |
| VD-H3 | R kept | reduces the reset spike and the first-4-call warp error | V1(reset) lower; E_O / E_R over calls move .. move + 3 lower; both inputs and schedules |
| VD-H4 | residual | with S masked, D kept and R kept, the post-bind trajectory still does not rejoin on butterfly | terminal PSNR within 2 dB of frozen M1's on butterfly (descriptive: isolates the Sink's own contribution) |
| VD-H5 | interaction | D and R effects on the reset spike are not additive (the decoder cache alone removes most of it) | descriptive |

**Mapping to the next step (fixed now):**
- H2 or H3 supported and H1 not: the reset jump is a short-term-state problem; the next M1 variant question is the
  cheapest reconstruction of that state at the destination (e.g. decoder cache from the last latent), not Sink transfer.
- H1 supported: masking becomes a candidate M1 variant on its own (zero transfer cost), to be validated end to end on
  the testbed under a new preregistration.
- H4 holds (nothing but the Sink explains the post-bind divergence): the "minimum temporal state" question
  (approximate Sink) is the right next design question; it is not designed before this result.
- No VD result changes any VC-1 verdict or frozen result, and VD runs no testbed migration.

## 6. Validity

Every VD emulation passes the G3 stream check; the (zero, reset, reset) control is VC-1's own run; the masked kernel
equals the explicit-mask SDPA on the precheck calls; with the flag off, the G1 replay (dog RD-X) stays call-by-call
identical (checked once after the flag is added, before VC-1).

## 7. Open decisions

- **VD-D1** thresholds of H1-H3 (proposed above).
- **VD-D2** whether to add train and audi-snow-trail (decided after the first two inputs).
- **VD-D3** ordering inside the unit: VC-1 conditions first, then VD (so VC-1's results exist even if VD is cut).
