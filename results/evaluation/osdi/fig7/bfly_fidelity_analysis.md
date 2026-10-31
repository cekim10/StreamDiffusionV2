# Fig. 7 butterfly fidelity: why the 36-call cutover ends at 32.4 dB

Existing Fig. 7 logs only; no new runs. Script: `tools/eval/fig7_fidelity_check.py` -> `fidelity_check.json`.
Question (user, 2026-10-30): does the degradation come from the replay-reconstructed recent state, a refresh boundary,
or the timing of the verified cutover?

## Data

The Sink slot positions (`sink_slot_pos`, layer 0 row 0, per call in metrics.csv) of every OTTER run, compared with
Full rep 1 of the same workload. Full rep 1 is bit-exact to the uninterrupted reference on every call (99 dB), so its
slot positions are the reference schedule. A slot whose position jumps to the current frame is a refresh; a shift of all
slots together is a RoPE realignment (calls 48, 93, 138).

| run | log calls | B's first call | slot positions differ from reference | PSNR first | terminal |
|---|---|---|---|---|---|
| dog reps 1-5 | 32-33 | 63-64 | 0 calls | 29.3 | 48.6-48.8 |
| bfly reps 2, 4, 5 | 34 | 65 | 0 calls | 35.9 | 44.4 |
| bfly reps 1, 3 | 36 | 67 | **94 calls, from call 67** | 33.8 | **32.4** |

Schedules after the cutover (call: [slot 0, slot 1, slot 2]):

| | refreshes / realignments |
|---|---|
| reference | 86: slot 1 refresh [-29, 43, -39]; 93: realign [-74, -2, -84]; 138: realign [-119, -47, -129] |
| bfly reps 2, 4, 5 (B from 65) | identical to the reference |
| bfly reps 1, 3 (B from 67) | **67: slot 1 refresh [-29, 24, -39]** (not in the reference); 89: slot 1 refresh [-29, 46, -39] (reference: 86); 93 [-74, 1, -84]; 138 [-119, 1, -129] |

PSNR trajectory (fidelity_check.json; per call in metrics.csv): both cutovers start with the same transient (first calls
26-36 dB). The 34-call runs recover to 41-46 dB by call ~74 and stay there. The 36-call runs recover only to ~38 dB,
then fall to 30-34 dB as their Sink schedule stays different from the reference to the end of the run.

## Findings

1. **[V] The low-fidelity runs are exactly the runs whose Sink diverges after the cutover.** 8 / 10 OTTER runs follow
   the reference Sink schedule on every call after the cutover (0 differing calls); their terminal PSNR is 44-49 dB. The
   2 runs that end at 32.4 dB are the only runs whose schedule differs, from B's first generation call on.
2. **[V] The divergence is a refresh decision made by B, not a reconstruction error at the cutover.** In both 36-call
   runs the Sink was verified at the switch (SINKOK, 0 / 360 blocks differing). B's first live call (67) then refreshes
   Sink slot 1, which the reference does not do; a second refresh follows at 89 instead of the reference's 86. From then
   on slot 1 holds different content and positions (after the realignments: 1 vs -2 at 93, 1 vs -47 at 138).
3. **[V] Cutover timing decides whether this happens.** The switch call is set by replay readiness (window 12, lag
   <= 1) and varies by two calls between reps. With B starting at 65, no live decision flips; starting at 67, the
   decision at 67 flips. Dog (B from 63-64) never flips.
4. **[V, from the code] Why a decision can flip.** The adaptive refresh (`models/wan/causal_model.py`, threshold 0.2)
   compares the mean K / V of the incoming chunk with each Sink slot (cosine similarity) and refreshes the least similar
   slot below the threshold. The Sink was exact, so the flip comes from the incoming chunk's K / V on B, which differ
   from the reference because B's post-cutover generation is not bit-exact (first-call PSNR 33.8 dB).
5. **[H] Not separable from these logs:** which perturbation moves the similarity across 0.2 at call 67 — the VAE
   encoder cache that restarts empty at the cutover, the replay-reconstructed recent KV (not bitwise; E4), or both —
   and how close the reference's similarity at call 67 is to the threshold. The logs record neither the similarities
   nor per-layer schedules (only layer 0); other layers may diverge in runs that look identical on layer 0.

## Answer to the question

The degradation is not caused by the replay-reconstructed state alone or by a refresh boundary at the cutover. It is
an interaction: **the cutover timing places B's first live call where the reference's refresh decision is close to the
threshold, and B's not-bit-exact post-cutover state flips that decision.** The Sink, exact at the switch, then evolves
differently from the reference for the rest of the run, and the output does not re-converge.

## What this means for claims

- Sink exactness is a property **at the cutover**. It does not imply that the Sink trajectory after the cutover follows
  the uninterrupted run: B's own adaptive refresh decisions can diverge (2 / 10 runs here).
- "Exact Sink -> continuity" must be stated with that limit. The 34-call runs show what an undiverged Sink gives
  (44.4 dB terminal); the 36-call runs show the failure mode.
- Fig. 13 should report per-run Sink-schedule divergence next to PSNR, so the two outcomes are visible.

## Not done (options, each needs its own preregistration)

- Measure the similarity margin: log per-layer cosine similarities in a reference run (offline, one input) to see how
  many calls sit near 0.2.
- Separate the perturbation sources: offline cutover reproduction at calls 65 and 67 with (a) the encoder cache carried
  over vs restarted, (b) recent KV from replay vs copied.
- A design change (e.g., carrying refresh decisions across the cutover, or keeping the encoder cache) would change
  frozen M1 and is out of scope without a separate decision.
