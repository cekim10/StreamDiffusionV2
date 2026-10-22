# Experiment XB - external migration baselines (re-implemented): preregistration REVISED DRAFT (2026-10-20)

Status: **REVISED DRAFT 4 (2026-10-22), not frozen.** Draft 4 adds section 3.2 (recompute input transfer: lossless
FFV1 as the primary codec, chosen by the CPU-only validation in `codec_validation.md`; lossy H.264 sensitivity; raw
upper bound; accounting rules) and decision D5. **No GPU calibration until the codec validation is reviewed.**
Draft 3 (2026-10-21) was approved for implementation preparation. Corrections of
2026-10-21 applied (alternative min-gap calibration setting, jitter runs outside the 35, P-full exactness at an atomic
chunk boundary, P-sink Sink-snapshot correctness vs trajectory equivalence, XH1b descriptive). The final document is
frozen after the calibration results are recorded and reviewed, before the shakedown and the main sweep. Roadmap step 3
(`../evaluation_roadmap.md`), after M3E and WX (their frozen results and verdicts are unchanged). Revision of 950e12f
with decisions D1, D2, D4 closed, a calibration plan for the D3 parameters (section 4, exact run counts and selection
rules), XH1 split by baseline class, and the four outcome notions of section 2.1 kept apart. **No implementation or run until this revision and the calibration plan are reviewed.** The
switchover / round parameters are fixed by the calibration of section 4 before the main sweep. No frozen result is
modified; no M1 / M2 / M3-v2 change.

## 1. Purpose and baseline classes

No published system migrates streaming video diffusion sessions. XB compares OTTER with the two closest recent migration
methods, both from LLM serving (autoregressive transformers with a KV cache), **re-implemented inside OTTER's harness**
(same model, transport, caps, fragment table, timing boundaries). The paper names them "Llumnix-style pre-copy" and
"ServerlessLLM-style recompute" and compares principles, not the original systems (different workload, framework,
cluster). VM post-copy and edge proactive synchronization are related work only; proactive placement is OTTER's own M3
(ExpD C / D).

| class | method | what it does | final state at the destination |
|---|---|---|---|
| **exact, full state** | Full migration (existing) | stop, copy all 6.02 GiB, resume | bit-exact |
| | **P-full** (Llumnix-style pre-copy) | source keeps generating and serving; all components copied in rounds (changed fragments only after round 1); short stop-and-copy at a chunk boundary; destination resumes | bit-exact **only if the switchover validation of section 3.1 passes**; until then P-full is not classified exact |
| | **R-full** (ServerlessLLM-style recompute) | destination re-runs the session from call 0 from the transferred input frames (losslessly compressed, section 3.2; same per-call seeds); source keeps serving until it catches up | bit-exact if the decoded inputs are bit-exact (checked per segment) and the replay reproduces the reference (checked on the outputs) |
| **hybrid (uses OTTER's M1)** | **P-sink** (M1-based hybrid baseline) | the Sink is pre-copied in rounds while the source serves; at switchover the rest goes by OTTER's M1 fast path and the destination rebuilds recent KV / VAE caches as in M1 | **Sink snapshot exact** (digest at the switchover boundary); **not trajectory-equivalent**: recent KV and VAE caches are rebuilt, so the output is expected to deviate transiently (RD's "immediate Sink bind after an M1 reset", d = 0) |
| | **Wait-for-Sink** (internal ablation) | M1 fast path, but no generation until the Sink is bound | Sink exact, ephemeral rebuilt |
| **approximate** | **R-win** (approximate recomputation) | the destination re-runs only the last W input chunks from a fresh session | not exact (Sink not reproduced) |
| system | OTTER | M1 + frozen M2 + M3-v2 (`reuse_dyn2`) | Sink exact after bind; Sink-less generation until then |

**Where the original assumptions break (measured, not assumed):** Llumnix relies on an append-only KV cache; here the
Sink changes (refresh, RoPE realignment: Task B, half of the Sink's K every ~45 calls) and the recent KV and VAE caches
change every call. ServerlessLLM relies on fast parallel prefill; here every chunk depends on the previous chunk's output,
so recomputation costs about as much as generation (state study: full replay of 30 chunks 17.2 s, bit-exact, ~570 ms per
history chunk).

## 2. Fairness rule (D1: option (b), closed)

After the trigger the source **may keep generating and delivering** (pre-copy, recompute); this is allowed and charged.
Three quantities are always reported separately and never combined into one score:

1. **Local resumption** (TTFO-local): time from the trigger (or the final move) until the user's **current** edge delivers
   its first chunk.
2. **Delivery gap**: the longest interval in which **no** chunk is delivered to the user from any host.
3. **Remote-serving cost**: chunks and seconds delivered from a host other than the user's current edge after the trigger
   (or after each move), and, where measurable:
   - **remote delivery network cost**: bytes of the delivered output stream that cross the inter-edge path, measured by
     encoding each remotely served chunk with a fixed codec and setting (H.264, fixed CRF, chosen in calibration) and
     summing the encoded sizes;
   - **remote delivery latency**: the measured round-trip time between the serving host and the current edge on the
     testbed (ping, per run). The testbed is one LAN, so this is a floor; WAN or radio latency is **not emulated** and is
     stated as unmeasured.

With repeated moves the user may leave the intended destination before a copy or replay finishes; the method then
restarts toward the user's new edge from the serving host (no reuse of the abandoned copy, as in the original methods)
and remote serving continues.

### 2.1 Four outcome notions, never merged

| notion | question | measured by | who is expected to win |
|---|---|---|---|
| **fast local resumption** | how soon does the user's current edge produce output? | TTFO-local | OTTER (M1 fast path) |
| **uninterrupted remote delivery** | does the user keep receiving frames, from any host, while state moves? | delivery gap; remote-serving time / chunks; remote delivery bytes and RTT | pre-copy and recompute (the source keeps serving), at a remote-serving cost |
| **restoration correctness** | is the state the destination ends with exactly the intended one? | exact methods: whole-state digest / bit-exact frames; Sink-based methods (OTTER, P-sink, Wait-for-Sink): Sink digest at bind; R-win: not exact by design | all except R-win are correct for what they restore |
| **reference-trajectory recovery** | does the output return to the uninterrupted stream? | PSNR vs reference: single crossing, sustained 10 calls, terminal median | exact methods (no Sink-less generation); OTTER only after its bind (input-dependent, WX / RD) |

No hypothesis turns one notion into evidence for another (e.g. no delivery-gap result is read as trajectory recovery,
and no correctness result as visual continuity).

## 3. Method parameters

### 3.1 Switchover consistency (P-full and P-sink)

The final switchover is **atomic at a chunk boundary**: the source finishes call c, stops generating, serializes its
state at that boundary, and sends the final dirty fragments (P-full: of every component; P-sink: of the Sink) plus the
immediate state; no source call runs after c. The destination resumes at call c + 1 only after it has verified, per
component, the digest of its assembled state against the digest the source computed at boundary c (P-full: Sink,
recent KV, VAE caches, metadata, in-flight rows; P-sink: Sink). P-full is classified **exact** only if (i) this
validation passes in every run and (ii) its first post-switchover chunk equals the uninterrupted reference (PSNR 99 dB,
bit-exact) in the loopback-equivalent GPU check of the calibration; otherwise P-full is reported as "not exact" with
the mismatch. For P-sink the claim is limited to Sink snapshot correctness; its trajectory is measured, not assumed.

- **P-full / P-sink rounds:** round 1 sends the component set; round r >= 2 sends fragments whose content hash changed
  since last sent (4 MiB fragments, VACW hashing). Switchover threshold (dirty set size), round limit and the
  non-convergence rule are **fixed by the calibration** (section 4) before the main sweep.
- **R-full rounds:** the destination replays while the source serves; switchover when the destination is within a lag
  threshold, else after a round limit (then the source stops and the destination finishes catching up while nothing is
  delivered). Lag threshold and round limit fixed by the calibration.
- **R-win window W:** fixed by the calibration from W in {1, 3, 6} (the existing replay variants).
- **Recompute input codec:** not a calibrated parameter; fixed by section 3.2.
- **Wait-for-Sink, Full migration, OTTER:** no parameters (frozen implementations).

### 3.2 Recompute input transfer (R-full, R-win; decided 2026-10-22, CPU validation `codec_validation.md`)

**Transfer unit.** The runtime's input is the clip resized to 480 x 832 as uint8 RGB, normalized as x / 127.5 - 1 and
cast to bf16. The recompute baselines transfer the **uint8 frames** (1,198,080 B each). Before a recompute run every
node checks that its uint8 history reproduces its runtime input tensor bit for bit (`input_check`). A bit-exact uint8
transfer therefore gives a bit-exact replay input.

**Primary codec: FFV1, lossless** (RGB as `bgr0`, level 3, intra-only, 4 slices with CRC). It was selected by the
CPU-only validation (dog and butterfly-feeding-slow-motion; R-full at triggers 30 and 120, a later R-full round, and
the R-win W = 3 window). FFV1 was bit-exact in every case and had the best compression ratio and the fastest encode
among the lossless candidates:

| codec | class | ratio vs raw (dog / butterfly) | bit-exact | encode / decode per frame (Apple M-series, indicative) |
|---|---|---|---|---|
| raw | upper bound | 1.0 / 1.0 | yes | - |
| zlib level 1 / 6 | lossless | 1.42-1.47 / 1.31-1.32 | yes | ~13.5-21 / ~2 ms |
| PNG per frame | lossless | 2.04-2.09 / 2.58 | yes | ~17-19 / ~4.5 ms |
| **FFV1** | **lossless (primary)** | **2.99-3.05 / 4.12-4.13** | **yes** | **~3-4.5 / ~3.5-4.5 ms** |
| x264rgb qp 0 | lossless | 2.64-2.77 / 2.43-2.45 | yes | ~6.5-7 / ~6.5-7.5 ms |
| H.264 CRF 23 (yuv420p) | lossy | 108-140 / 123-149 | no (PSNR 34.7-36.4 dB) | ~1.7-2 / ~0.6 ms |
| H.264 CRF 28 (yuv420p) | lossy | 203-290 / 220-279 | no (PSNR 31.8-34.2 dB) | ~1.5-1.7 / ~0.5 ms |

For example, R-full at trigger 30 (calls 0-30, 125 frames) is 150 MB raw, 49.6 MB FFV1 for dog and 36.3 MB FFV1 for
butterfly; at 1 Gbps that is about 0.4 s and 0.3 s of transfer against about 17 s of replay. Testbed CPU costs are
measured online in every run; the table above is not used as a result.

**Protocol (implemented).**
- The source encodes the requested frame range in 32-frame segments in a 4-thread pool. Segments are sent as they are
  encoded, through the same emulated caps as every other transfer.
- The destination decodes each segment off the receive path. It compares the decoded frames with its own copy of the
  same frames (`np.array_equal`). It writes the **decoded** frames into the runtime input, so the replay always consumes
  the transferred data.
- Replay call c waits only until frames [0, 5 + 4(c + 1)) are decoded (R-full). R-win waits for its window
  [5 + 4(c - W) - 1, 5 + 4c). Replay is therefore pipelined with transfer and decode.
- R-full is classified exact in a run only if every decoded segment of the replay that switches over is bit-exact
  **and** the replayed outputs match the reference (section 8).

**Lossy sensitivity (H.264 CRF 23 and CRF 28).** The same protocol with lossy segments. The destination replays from
the lossy decoded frames, and the input PSNR is recorded per segment. These runs are labelled "R-full / R-win, lossy
inputs (CRF x)". They are **never classified as exact recomputation** unless bit-exact replay is independently verified
(not expected). Runs: decision D5.

**Raw upper bound.** Every recompute run also records the raw size of the frames it transferred (frames x 1,198,080 B).
Raw is the network-byte upper bound and needs no extra runs. A raw-transfer run is possible with the codec flag but is
not planned.

**Accounting rules.**
1. **Actual bytes.** Input bytes are the codec's output bytes actually sent: every segment, every part, every target.
2. **History generated while the source serves.** R-full sends frames [0, 5 + 4c) at the start (c = the source's next
   call). Each round then sends the frames of the calls the source generated meanwhile. The final part, after the
   source stops at call c', sends the remaining frames up to 5 + 4c'. R-win sends its window at the start and the
   frames the window gained by the stop call at the finish.
3. **No reuse across abandoned targets.** A new target (after a move) receives its whole range again: frames from 0
   (R-full) or its whole window (R-win). Bytes sent to abandoned targets are counted and reported separately.
   Segments arriving for a cancelled task are discarded at the destination (counted as discarded).
4. **Encode and decode costs.** The source records encode CPU time per segment; this encoding runs on the source's
   CPU while it keeps generating, so any effect on its chunk service time appears in its per-chunk times. The
   destination records decode CPU time per segment and the time its replay waited for decoded inputs.
5. **Reported per run:** encoded bytes sent (total, per task, to abandoned targets), raw bytes, compression ratio,
   encode CPU seconds, decode CPU seconds, replay input-wait seconds, segment exactness and, for lossy runs, the
   minimum input PSNR.

## 4. Calibration plan (before the main sweep; baseline-favorable; not evidence)

Goal: give each baseline its best parameters in the tested setting, so that no comparison is won against a poorly
tuned baseline. Calibration runs are kept and reported (full grid in the appendix) but are never evidence for XH1-XH5.

**Setting:** XB1 configuration (single move A -> B, trigger chunk 30, 1 Gbps, dog, seed 0), hosts A and B only.

**Grids and exact run counts:**

| method | parameters | settings | runs |
|---|---|---|---|
| P-full | dirty-set switchover threshold {16, 64, 256} MiB x round limit {3, 6, 10}; non-convergence rule fixed: stop when a round's dirty bytes shrink by < 10 % | 9 | 9 |
| P-sink | same grid | 9 | 9 |
| R-full | catch-up lag threshold {1, 2} chunks x round limit {3, 6, 10} | 6 | 6 |
| R-win | replay window W in {1, 3, 6} chunks | 3 | 3 |
| repeats of each method's selected setting (timing jitter check) | - | 4 x 2 | 8 |
| **total** | | | **35** |

One run per setting suffices because generation is deterministic (WX / M3E reps agree within 0.1 dB and ~0.5 s); the
two repeats of each selected setting check timing jitter. Remote delivery bytes are computed offline from the P-sink
calibration runs at H.264 CRF 23 and 28 (no extra runs); CRF 23 is reported in the main sweep, CRF 28 as sensitivity.

**Selection rules (fixed now; lexicographic, baseline-favorable on the metric XH1 compares):**
1. Eligibility: the run is valid (W / R / N rules) and passes its class's correctness check (section 3.1: P-full whole-
   state digests and bit-exact first chunk after switchover; P-sink Sink digest at the boundary; R-full bit-exact).
   **Calibration starts only after the loopback exactness checks pass**; a GPU calibration run that fails its check is
   not eligible and the failure is reported.
2. Primary criterion, P-full, P-sink, R-full: smallest TTFO-local; settings within 5 % of the smallest are tied, and the
   tie goes to the smallest delivery gap, then to the fewest remote-served chunks, then to the smaller threshold / round
   limit.
3. R-win: among W whose terminal PSNR is within 1.0 dB of the best W, the smallest TTFO-local.
4. **Alternative setting:** for every applicable baseline (P-full, P-sink, R-full, R-win) the eligible setting with the
   smallest delivery gap is also recorded (ties as in rule 2). It is reported in the calibration table and, where it
   differs from the selected setting, also run in XB1 (3 reps x 2 workloads per differing baseline, at most 4 x 6 = 24
   extra runs) and reported next to the selected setting; no hypothesis is evaluated on it.
5. Timing-jitter check: if a selected setting's two repeats differ from its first run by more than 10 % in TTFO-local,
   that method is re-calibrated with 3 runs per setting and the median decides. **These runs are in addition to the
   35** (at most 2 more runs per setting: P-full / P-sink 18 each, R-full 12, R-win 6, i.e. up to 54 extra).
6. The selected values, the alternative settings and the whole grid (TTFO-local, delivery gap, remote-serving time and
   chunks, rounds, dirty bytes per round, switchover reason, correctness result) are written into this document and
   frozen with it before the shakedown.

**Cost:** 35 runs on GPU 0 of A and B, ~1.5-2 h.

## 5. Scenarios (main sweep)

| id | mobility | network | workloads | methods |
|---|---|---|---|---|
| XB1 | single move A -> B at trigger chunk 30 | 1 Gbps | dog, butterfly-feeding-slow-motion (seed 0) | all seven |
| XB2 | single move, trigger chunk 120 | 1 Gbps | dog | OTTER, P-sink, R-full |
| XB3 | A -> B -> C -> D, rho 1 | 1 Gbps | dog | OTTER, Full, Wait-for-Sink, P-sink, R-full |
| XB4 | A -> B -> C -> D, rho 2 | 1 Gbps | dog | as XB3 |

D4 closed: no further workloads in XB3 / XB4 (WX covers input breadth for OTTER). P-full and R-win (D2: kept) appear in
XB1 only.

## 6. Metrics

Local resumption, delivery gap, remote-serving cost (chunks, seconds, remote delivery bytes, LAN RTT) as section 2;
trajectory (PSNR vs the uninterrupted run: single crossing, sustained 10 calls, terminal median of calls b + 90 .. b + 99
or the last 10 delivered calls), bytes (source egress, total network, transferred inputs as actual encoded bytes with
the raw upper bound and encode / decode CPU time per section 3.2, pre-copy rounds), destination
GPU-seconds before serving, extra source GPU-seconds while serving remotely, convergence (rounds, dirty bytes per round,
switchover reason).

## 7. Hypotheses (medians over 3 valid reps; thresholds fixed at the freeze)

| id | class | statement | success | prediction |
|---|---|---|---|---|
| **XH1a** | exact, full state (Full, P-full, R-full) | OTTER resumes locally much sooner than every method that moves or recomputes the whole state (XB1, both workloads) | TTFO-local(OTTER) <= 0.25 x each exact method's | OTTER ~0.7 s; Full ~54 s; P-full >= 35 s; R-full >= 17 s |
| **XH1b** | hybrid and approximate (P-sink, Wait-for-Sink, R-win) | **descriptive comparison, no threshold:** the trade-off of each against OTTER on every notion of section 2.1 | reported per method: TTFO-local, delivery gap, remote-serving time / chunks and delivery cost, Sink correctness, trajectory (crossing, sustained, terminal) | Wait-for-Sink ~15 s local resumption with a ~15 s delivery gap; P-sink >= ~15 s local resumption, ~no gap, remote serving meanwhile; R-win 5.8-7.1 s (earlier single-handoff replay), approximate, never rejoins |
| XH2 | exact | full-state pre-copy does not converge at 1 Gbps (XB1) | P-full ends by the round limit or the non-convergence rule in every run | every call rewrites one recent-KV ring slot (~0.54 GiB) and updates the VAE caches (up to 2.8 GiB) |
| XH3 | exact | recompute cost grows with session length (XB1 vs XB2, dog) | R-full's destination GPU-seconds before serving at trigger 120 >= 3 x at trigger 30 | ~4 x |
| XH4 | hybrid and exact, repeated mobility | methods that wait for state accumulate remote serving or delivery gap when the user keeps moving (XB3, XB4) | remote-serving seconds of P-sink and R-full >= 5 x OTTER's TTFO-local at rho 1 and 2 | the user leaves before the copy or replay completes |
| XH5 | all | OTTER's trajectory cost is reported, not hidden | descriptive: OTTER's gap PSNR and rejoin vs the exact and hybrid baselines | OTTER diverges until bind (~17 dB), exact / hybrid baselines do not |

No hypothesis combines local resumption, delivery gap and remote-serving cost into one figure of merit. NOT EVALUABLE:
< 3 valid reps of a compared method; censoring per `followup_common.md` section 3. Every method's numbers are reported
in every scenario.

## 8. Validity

W / R / N run rules (all fragments verified, digest, NIC checks, GPU 0 idle, one commit); exactness checks per class
(R-full replayed frame digests vs the reference; P-full and P-sink final state digest vs the source at switchover);
recompute runs: every node's `input_check` passes, and with the lossless codec every decoded input segment of the
switching replay is bit-exact (a failure makes the run invalid and is reported); lossy-input runs are valid as
sensitivity runs and never count as exact;
remote-serving accounting checked against the delivered-chunk log (each chunk delivered once).

## 9. Runs, runtime, occupancy

| phase | runs | hosts | time |
|---|---|---|---|
| calibration (section 4) | 35 | A, B | ~1.5-2 h |
| shakedown (one run per method and scenario: XB1 7 x 2, XB2 3, XB3 5, XB4 5) | 27 | A-D | ~1.5 h |
| main sweep: XB1 7 x 2 workloads x 3 = 42; XB2 3 x 3 = 9; XB3 5 x 3 = 15; XB4 5 x 3 = 15 | **81** | A-D | ~5-6 h |
| alternative min-gap settings in XB1 (only where they differ, rule 4) | 0-24 | A, B | 0-1.5 h |
| jitter-triggered re-calibration (rule 5, only if triggered) | 0-54 | A, B | 0-3 h |
| lossy-input sensitivity (section 3.2, D5 proposal: XB1, R-full and R-win at their selected settings, CRF 23 and 28, dog and butterfly, 1 rep) | 8 | A, B | ~0.5 h |
| **total GPU runs** | **151-229** | | **~8.5-14.5 h** |

Shakedown and calibration are not evidence. Exclusive use of GPU 0 on the listed hosts; no commit or pull on the
testbed while a phase runs.

## 10. Implementation (status 2026-10-22: items 1-3 implemented and loopback-tested; item 4 pending)

1. Pre-copy: source keeps generating after the trigger while a copier sends rounds; per-round content hashes (VACW
   snapshot capture and hash comparison reused); switchover protocol; P-full packs every component; P-sink hands the
   rest to M1.
2. Recompute: destination replay from inputs (the state-study `replay_full` / `replay_W` paths moved into the node),
   encoded input-frame transfer with per-segment bit-exactness checks (section 3.2; `tools/eval/xb_codec.py`), rounds,
   switchover.
3. Wait-for-Sink: node flag deferring generation until bind.
4. Delivery accounting: per delivered chunk, the serving host and the user's current edge; delivery gap; remote-served
   chunk encoding (H.264) for remote delivery bytes; per-run RTT between hosts.
5. Loopback tests of every method, calibration, then shakedown. No change to OTTER's mechanisms.

## 11. Decisions

- **D1 (closed)** - option (b): remote serving allowed and charged; local resumption, delivery gap and remote-serving
  cost reported separately; remote delivery bytes and LAN RTT where measurable.
- **D2 (closed)** - P-full and R-win kept; R-win labelled approximate recomputation; P-sink labelled a hybrid baseline
  using M1.
- **D3 (open until calibration)** - switchover / round parameters fixed by the section-4 calibration and recorded here
  before the main sweep.
- **D4 (closed)** - no further workloads in XB3 / XB4.
- **D5 (open)** - lossy-input sensitivity runs. Proposal: 8 runs (section 9), descriptive only, never evidence for
  XH1-XH5. Alternative: report the lossy cases from the CPU validation only (bytes and input PSNR), with no GPU runs.
