# M1 continuity mechanism: design proposal, draft 1 (2026-10-27; not implemented, nothing run)

Question: how can a migrated session keep boundary continuity (P1) without moving the full Recent KV cache?
Inputs: VD-4 / VD-5 (oracle sufficiency), M1 / M2 follow-up A and B, the state-ablation results, and the code
(`models/wan/causal_stream_inference.py`, `models/wan/causal_model.py`).

## 1. Why the Recent KV is expensive, and what it actually contains

Facts from the code (1.3B, 480 x 832, `num_kv_cache` 6 = 3 Sink + 3 recent, 2 denoising steps):
- The stream batch has one row per denoising step, and **each row has its own KV ring**. Every call feeds each row
  one latent frame (16 x 60 x 104 bf16 = 0.2 MB) and writes one new recent slot in that row.
- One recent slot is 30 layers x (K, V) x 1,560 tokens x 12 heads x 128 x 2 B = 287.5 MB per row, 575 MB for both rows.
  The Recent KV is 3 slots = 1.73 GB.

Three properties make it expensive:

| property | Recent KV | Sink KV |
|---|---|---|
| size | 1.73 GB | 1.73 GB |
| rewrite rate | one 575 MB slot every call, about 7.7 Gbps at 0.6 s per call | refresh / realign only, 120-236 Mbps (M2 B) |
| deadline | needed at the first destination call (2 calls late is worthless) | can bind late (M1) or be pre-copied (M2) |

- The Sink can be pre-copied because it changes slowly. The Recent KV cannot: it is rewritten faster than any link
  can follow, so it can only be shipped at the cutover, on the critical path (follow-up A: +0.9 s per slot native,
  4.6 s per slot at 1 Gbps).
- **Its information content is small.** A recent slot is a deterministic function of (i) the row's input latent at
  that call (0.2 MB), (ii) the KV context it attended to (Sink plus the two previous recent slots), and (iii) metadata
  (timestep, positions, cache events). The 287.5 MB per row is a 1,440x expansion of the 0.2 MB input through 30
  layers. What P1 needs is the stream's recent history, and that history is already carried by the inputs.

## 2. Candidate approaches

| | A. Compress the Recent KV | B. Rebuild locally from the client's input | C. Replay a shipped input log |
|---|---|---|---|
| idea | 8- or 4-bit quantization, or a slot / token subset, still shipped at the cutover | destination re-encodes the last input frames, adds noise, runs the model to fill the recent slots; no source bytes | source ships each call's generator inputs (0.4 MB); destination re-executes those calls against its Sink and rebuilds the recent slots |
| expected P1 | near R at 8-bit; 4-bit unknown | weak: row 1's input is the source's own denoised prediction, which the destination does not have; this is the B0 / TS family that left the jump | approaches R; exact when the replay starts from an exact ring (section 4) |
| critical-path bytes | 430-865 MB | 0 | 0.4 MB (one log entry) |
| critical-path latency | 3.5-6.9 s at 1 Gbps; 0.7-1.4 s native (follow-up A scale) | about 3 forwards plus VAE encodes | at most one transformer forward; zero if replay runs ahead (section 3) |
| feasibility | high | medium | medium: capture inputs and cache events, add a replay path |
| research insight | weak: generic, scaling unchanged | weak: discards the source trajectory | strong: ship the cause, not the effect |

A shrinks the bytes but keeps them on the critical path. B removes the bytes but also the information P1 needs.
**C is the strongest**: it removes the bytes and keeps the information.

## 3. Proposed mechanism: replay the Recent KV from a shipped input log

**Principle.** Session state splits by temporal semantics (state-ablation results): **durable** state (the Sink) is
transferred; **ephemeral** state (the Recent KV) is re-derived by re-executing the last calls from their inputs;
**immediate** state (the in-flight rows and metadata) goes in the fast path, as today. The log is about 1,400x
smaller than the KV churn it reproduces (5.3 Mbps vs 7.7 Gbps).

**Log entry per source call** (about 0.4 MB): the generator inputs of both rows exactly as fed (noisy latents,
already including the noise the scheduler added), timesteps, `current_start` / `current_end` per row, and the cache
events of that call (slot placement, eviction, Sink refresh, realign). Prompt conditioning is constant and already in
the fast-path metadata.

**Workflow** (for a predicted move; M3 provides the trigger):
1. **Sink pre-copy:** M2 pre-copies the Sink, version-aware, unchanged.
2. **Log shipping:** once the destination holds the Sink, the source ships log entries as it serves, at 5.3 Mbps.
3. **Shadow replay:** the destination re-executes each logged call, transformer only, discarding outputs. Recent slots
   come from replay; Sink content comes only from M2's transfer. The replay is teacher-forced: every input is the
   source's, so the replay's own outputs never feed back and there is no autoregressive drift.
4. **Cutover at M:**
   - The fast path ships the in-flight rows and metadata (as today) plus the last log entry.
   - The destination's recent slots are complete up to call M-1. There is no Sink-less window, no temporary Sink and no
     late bind, because the Sink is already in place.
   - DR-2 stays as the decoder path, and nothing else in M1 changes.

**Unpredicted move:** without lead time, the source ships the last w log entries in the fast path (w x 0.4 MB). The
destination replays them on the critical path against whatever Sink it has: the temporary Sink, then late bind as in
today's M1. The cost is w forwards instead of 1.73 GB.

**Warm-up source** (the single parameter of the mechanism):
- **Log-only (default):** replay starts with empty recent slots. Errors from the missing older context must fade within
  the w replayed calls. No Recent KV bytes ever cross the network.
- **Exact base:** the background pre-copy also carries the recent slots once, at the call where replay starts. From
  then on replay is deterministic re-execution, so the ring at M equals the source's bit for bit, and so does the
  Sink, because refreshes replay exactly. This costs 1.73 GB more in the background, none on the critical path. It is
  the fallback for inputs where log-only warm-up does not converge.

## 4. Why it should work

- **Determinism:** in-place emulation is exact (Experiment RD: 0.00 dB), and cross-host replay was bit-exact in Phase
  1. Re-executing a call with the same inputs, context, shapes and kernels reproduces its KV writes. With an exact base,
  the replay is exact.
- **Fading memory:** in the state ablation, dropping the Recent KV healed to 46-48 dB within a few calls. That healing
  is what the log-only warm-up relies on, except that it now happens off screen, before the cutover, and
  teacher-forced.
- **Sufficiency:** VD-5 showed that source Recent KV gives P1 12/12, and that its effect adds to exact Sink with no
  pairing requirement. If the replayed slots approach the source's, the RS3 behaviour follows. RS3 is the upper bound.
- **Precedent in M1:** DR-2 rebuilds the VAE decoder cache from the last two latents and halves the jump despite an
  inexact cache. This mechanism applies the same principle to the transformer's ephemeral state.

## 5. Expected overhead (estimates, to be measured)

| item | log replay | ship Recent KV (follow-up A, n = 3) |
|---|---|---|
| bytes on the critical path | 0.4 MB | 1.73 GB |
| added time to first output | 0 to one transformer forward (under 0.6 s) | about 2.7 s native; 13.8 s at 1 Gbps |
| background traffic | 5.3 Mbps during the shadow window | none |
| destination GPU | one transformer forward per source call during the shadow window | none before the cutover |
| source | one async 0.4 MB device-to-host copy per call | the 1.73 GB send |

The exact-base option adds 1.73 GB of background transfer once per move.

## 6. Main technical challenges

1. **Log-only fidelity.** Whether the recent slots converge within a small w, especially on refresh-heavy inputs
   (butterfly; bird failed to heal after ephemeral loss), is unmeasured. The exact base is the fallback.
2. **Replay semantics.** The replay must apply the source's cache decisions from the log and must not decide them
   again. The refresh decision uses cosine similarity on the KV, so a slightly different shadow could decide
   differently. This covers per-row placement, eviction indices, realign rotations and refresh promotions.
3. **Lead time and contention.** The shadow needs the Sink plus w calls before the move. On a multi-tenant
   destination it competes for the GPU. Unpredicted moves fall back to replay on the critical path.
4. **Out of scope.** The VD-5 residual (two P2 cells) lies outside the KV ring: decoder, encoder cache, frozen refresh
   and bind. This mechanism does not address it, and RS3 bounds what it can reach.

## 7. Minimal validation experiment (to preregister after review)

This is a mechanism test in the emulator, not a new oracle diagnosis. The Sink is exact at M, which is the
predicted-move case.
- **E0, replay semantics (minutes, 1 cell):** start from the exact ring at M-k, replay k logged calls, and compare the
  recent slots and positions at M with the source's. Required: bitwise equality. This validates log completeness and
  determinism.
- **E1, fidelity versus warm-up (no frames):** log-only replay with w = 3, 6, 12 on the 12 confirmation cells. Report
  the per-layer relative error of the rebuilt recent K and V against the source's at M.
- **E2, continuity:** conditions L3, L6, L12 (exact Sink plus log-only replay of w calls) on the 12 cells.
  - Reuse RS3 as the upper bound and S3 as the lower bound.
  - Use VD-5's rules: V1 non-inferior to RS3 (within 0.10 x P99 on 12/12 cells) and P2 non-inferior to S3.
  - About 36 runs, about 2 GPU h on D.
- **Cost, measured in the same runs:** log bytes per call, transformer-only forward time per call, and replay
  throughput against the call period.
- **Visual inspection only if E2 passes numerically:** a small blinded session comparing L_w with RS3, decided at
  preregistration.

**Go:** E0 bitwise, and some w in {3, 6, 12} non-inferior on P1 and P2 with replay faster than the call period.
**Otherwise:** the exact-base variant becomes the mechanism, and E0 has already validated it.
