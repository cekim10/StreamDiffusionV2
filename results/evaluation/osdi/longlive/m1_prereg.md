# LongLive: frozen OTTER M1 (Continuity Replay) with a longer replay horizon (FROZEN 2026-11-02; DRAFT 1 478e78c3 + user review; nothing run)

## 1. Question

Can OTTER support LongLive by adjusting M1's replay horizon, without changing its mechanisms?

The frozen claims and M1 / M2 / M3 are unchanged; no LongLive-specific mechanism is added. This study tests M1 only:
the source keeps generating and serving while the destination reconstructs the state it needs and catches up, then a
short cutover. A positive result is a cross-model check of M1, not of OTTER as a whole: M2 (versioned Sink
reconstruction) and M3 (Continuity Wavefront) are not exercised, and nothing here supports a claim about them.

## 2. Facts this rests on

- Ablation (`ablation_results.md`, 4 / 4 streams, measured): sink + replay of the last W calls rebuilds the window
  exactly at W = 96 (window and latents bit-exact on 100 / 100 calls) and not at W = 12 / 24 / 48 (W3 21-31 dB); the
  VAE decoder cache feeds nothing back and is rebuilt from the last logged blocks; a static estimate put W = 96 at
  about 106 s, because the ablation replayed all 96 calls with decode, stopped.
- LongLive's sink is written by call 0 only (`global_sink`) [V]: it never changes after the migration starts, so M1's
  Sink synchronisation holds trivially and the refreshes M2 versions do not occur in LongLive.
- Adaptation of M1 to a T2V model [V, code]: LongLive has no input frames, so the replay log holds each call's
  **source-generated output latents** and the replay is teacher-forced (the context pass the source ran after each
  call): the destination rebuilds the KV state from the source's outputs, it does not regenerate them. On SDV2 the
  log holds inputs. This is a valid Continuity Replay but not the same reconstruction semantics as SDV2's, and the
  paper says so. Its costs are measured, not assumed: every log block is in the bytes sent until the switch, and the
  source's per-call device -> host copy of the latents (logging on the serving path) and its call interval during the
  migration are recorded. Replay without decode updates the KV cache exactly; the VAE decoder is rebuilt by decoding the last K_v = 12
  logged blocks once the replay has caught up, before the switch (the ablation's 1-block rebuild also worked; 12 blocks
  give a bit-exact first call more often). This is the implementation in `tools/longlive/ll_migrate.py --method
  replay`, a port of M1, not the frozen SDV2 harness code.
- Measured costs: a live call 2.11 s (generate 1.37 + decode 0.75); replay with decode about 1.03 s per call, so the
  context pass alone about 0.28 s [H, derived]; sink 0.86 GB; one log block 0.6 MB.

## 3. Arms and runs

`python tools/longlive/ll_migrate_runs.py run --study m1` on elves-01 (agents, no ssh): lanes A > B and C > D in
parallel; rep r shifts the lane assignment, so every (arm, stream) runs on both pairs over 2 reps. Streams: the
ablation's prompts 0, 1 x seeds 0, 1; trigger M = 120 (so W = 96 fits); 1 Gbps shaping on the source -> destination
link; after the switch, 100 calls compared with the source's shadow continuation (never served).

| arm | moves | destination | role |
|---|---|---|---|
| otter_w96 | sink at M while the source serves; the 96 pre-trigger log blocks; every later call's log block | from the sink at M - 96, replays M - 96 ... (context only), VAE from the last 12 blocks once caught up, switch | M1 with the longer horizon |
| otter_w12 | same with W = 12 | same | M1 with the SDV2 horizon (control; ablation predicts the loss) |
| recache | sink at M while the source serves; at the switch: counters + latent buffer | LongLive KV recache, VAE warmed on the last block | LongLive-native |
| full | stop-and-copy of the whole state at M (5.06 GiB) | import | exact baseline |

4 arms x 4 streams x 2 reps = 32 runs, about 10 min each (model load, 120 calls, migration, 100 verified calls), about
2.7 h on the two lanes. A replay arm that has not caught up 300 s after the sink arrived is switched anyway and
recorded as forced.

## 4. Metrics (destination clock; source times converted by a ping offset)

- **Readiness:** trigger -> the destination's state at the switch call s complete.
- **Maximum output gap:** the largest interval between consecutive served calls (12 frames each) from call M - 5 to
  5 calls after the switch: the source's calls before s, then the destination's. Also the delivery gap (the source's
  last served call -> the destination's first) and the source call interval.
- **Fidelity:** PSNR of every post-cutover call vs the source's shadow (W1 = k 1-8, W2 = 9-24, W3 = 25-100 medians,
  first call); latents equal (digest) on how many of 100 calls; frames complete (12 per call); the sink + window
  fingerprint at s vs the source's.
- **Bytes** sent on the link until the switch (state and every log block; the shadow's verification frames are
  excluded). **Logging cost:** the source's per-call latent copy time; the source call interval before M vs during
  the migration (M - 1 to the switch).

## 5. Rules (written before the runs; 40 dB is the operational threshold used throughout, not a perceptual one)

For otter_w96 (a run whose destination has not caught up 300 s after the sink arrived is a **migration failure**: it
counts against R2 and is excluded from R1, R3, R4, R5; the switch it then makes is a diagnostic only, never counted
as an OTTER migration):
- **R1 exact,** in every run, split into: **R1a generation state** - the sink + window fingerprint at s equals the
  source's; **R1b latents** - 100 / 100 post-cutover latents equal the shadow; **R1c frame completeness** - 12 frames
  in every post-cutover call. **Frame fidelity** (first call PSNR, W1 / W2 / W3, frames bit-exact count) is reported
  separately and is not part of R1: complete frames and exact latents do not by themselves mean exact output frames
  (the decoder cache is rebuilt).
- **R2 catch-up:** no catch-up timeout in any run.
- **R3 short cutover:** median maximum output gap < Full's median, in >= 3 of 4 streams; the per-stream absolute
  differences are reported with the verdict (two reps per stream: a near tie is read as a tie, not as a win).
- **R4 readiness:** median readiness < Full's median, in >= 3 of 4 streams; absolute differences reported likewise.
- **R5 bytes:** bytes until the switch (state + log) < Full's in every run.

Controls, reported: otter_w12 and recache W3 PSNR (the ablation predicts < 40 dB), their gaps and readiness.

**Reading (as written):**
- R1, R2, R3, R5 hold and R4 holds: M1 carries over to LongLive with a longer replay horizon, with shorter readiness,
  a short cutover and fewer bytes than Full (one move, 1 Gbps): a cross-model check of M1.
- R1, R2, R3, R5 hold and R4 fails: M1 works on LongLive (exact, continuous, fewer bytes) but is not faster to be ready
  than Full: functional generality of M1 shown, performance generality not.
- R1 fails: a defect of the port first (fix, rerun, keep both records); if it persists, a replay horizon alone does not
  carry M1 over to LongLive.
- R2 fails: the replay does not outpace generation here (migration failures); the diagnostic switches are reported
  separately and are not migrations.
- R3 fails with R1 / R2 holding: M1's continuity does not hold on LongLive in this setting.

Never claimed from this study: M2 or M3 work on LongLive; OTTER as a whole generalizes; any model beyond LongLive;
equivalence of the port with the frozen SDV2 implementation beyond the mechanism described in section 2.

## 6. Predictions [H] (from the measured per-call costs; not used by any rule)

otter_w96: sink about 7 s at 1 Gbps (+ about 1 s export); 96 + about 4 replayed calls context-only about 28 s, during
which the source makes about 13 more; VAE rebuild about 9 s; the calls made meanwhile with decode; switch: readiness
about 45-55 s vs Full about 46-48 s, so R4 is uncertain. Maximum output gap about 2.5-4 s (Full about 48 s); bytes
about 0.92 GB vs 5.06 GiB; W3 99 dB (exact). The 0.28 s context-only replay cost is derived, not measured, and the
replay overlaps the source's generation and the transfer on the destination host only (the source runs on another
GPU), so R4 is a measurement, not an expectation. otter_w12: readiness about 20-25 s, W3 about 22-31 dB. recache: readiness
under 10 s, gap about 3-5 s (recache at the cutover), W3 about 22-30 dB.

## 7. Decisions (user, 2026-11-02)

| # | decision |
|---|---|
| D1 | reps 2 (a feasibility study; limited statistical generalization) |
| D2 | W = 96, the smallest measured horizon that was exact in the ablation |
| D3 | K_v = 12 |
| D4 | 100 verified calls after the switch |
| D5 | 1 Gbps |
| D6 | R1-R5 kept; 300 s is a catch-up timeout = migration failure (not a forced migration); absolute differences reported for R3 / R4 |
| added | the log is source-generated latents (costs measured); R1 split into generation state / latents / frame completeness, frame fidelity reported separately |

Run first on the testbed (before Fig. 12a). A positive result is used only as a cross-model check of M1; the frozen
claims are unchanged.

Tools: `tools/longlive/ll_migrate.py` (methods replay, recache, full; snap kept for the held study),
`ll_migrate_runs.py --study m1` (run, report). Loopback CPU test `tools/longlive/test_ll_migrate.py`: every method on
127.0.0.1 (replay W8: state exact, post-cutover latents 4 / 4 and frames 4 / 4 equal the shadow, fewer bytes than full;
recache runs and is complete; per-call PSNR vs the shadow and the maximum output gap recorded): ALL PASS. On the CPU
tiny model decode-replay is about as fast as generation, so its replay runs switch by the safeguard; GPU costs differ.

## Harness defect and fix (2026-11-02, after the first two jobs; before any valid run)

The first otter_w96 and otter_w12 jobs (p0 s0 r1, one per lane) failed: the destination did not catch up within the
300 s timeout (cause not yet known: its log was lost because the agent-run process was block-buffered and was killed
afterwards), the timeout's diagnostic switch came near call 266, and the source's 100 shadow calls then ran past
LongLive's RoPE table (1,024 latent frames = 341 calls; `causal_rope_apply` shape error), so the source crashed and
no JSON was written. Fix (no rule changed): the source stops on its own when its next call plus the shadow would
exceed 341 calls and reports it (`src_forced`; counted as a migration failure, as a timeout); the destination prints
its progress (state arrival, every 10th replayed call with backlog and per-call time, VAE rebuild, switch request)
and the runner starts both with `python -u`. Loopback test ALL PASS, plus a source-budget test (tiny model, trigger
330: the source stops at 337, the run ends with a JSON marked as a failure). The two failed jobs' logs are kept
(`migrate_m1/_failed_20261102/`); both jobs are rerun.

**Root cause of the failed jobs (found 2026-11-02 on the rerun's first job):** `ll_migrate.py` used plain sockets, not
the harness transport policy (tools/eval/common.py: TCP_MAXSEG 1,400 on the listening and the connecting socket). The
elves path drops jumbo frames while the NICs advertise MTU 9,200, so uncapped TCP blackholed every large segment:
the 9 clock pings (small) passed, the sink snapshot never arrived, the destination never started, and the source
served until its RoPE budget (rerun: source-forced stop at call 241, destination still waiting for the state, both
sockets' queues empty). Fixed: `tcp_listen` / `tcp_accept` / `tcp_connect` with the default MSS cap (`--mss`; 0 only
for the macOS loopback test). The rerun's p0 s0 r1 logs are kept with the first failure's in `_failed_20261102/`.

## Outcome (2026-11-02, 32 runs at 4b2c2d9b; rules above unchanged; `m1_results.md`)

otter_w96: R1a / R1b / R1c, R2, R3 (4 / 4 streams, gap 3.23-3.24 s vs Full 49.5-49.8 s), R5 (0.87 vs 5.06 GiB) HOLD;
R4 FAILS (0 / 4: readiness 58.4-59.4 s vs Full 47.3-47.6 s, +11.1 to +11.9 s). Reading as written: M1 works on LongLive
(exact, continuous, fewer bytes) but is not faster to be ready than Full; functional generality of M1 shown,
performance generality not. Frame fidelity (separate): 100 / 100 frames bit-exact in every run. Logging cost: latent
copy 0.1-0.2 ms per call, source call interval 2.11-2.13 s before and during the migration. Readiness (medians): sink
7.2 + context-only replay 31.6 (113 calls x 0.280 s; the derived 0.28 s confirmed) + VAE rebuild 8.8 + decode-replay of
the calls made meanwhile 10.3 (10 calls) + 0.8 s; the prediction (45-55 s) left out most of the decode-replay. Controls
as predicted: otter_w12 W3 23.8-30.3 dB, recache W3 20.2-30.8 dB (readiness 31.9 / 10.6 s, gaps 3.2 / 4.1 s). One move at
1 Gbps; a faster link shortens Full's transfer and not the replay. The two failed jobs' logs (harness defect above) are
kept on elves-01 (`migrate_m1/_failed_20261102/`; logs are not tracked by git).
