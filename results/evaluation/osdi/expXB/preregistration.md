# Experiment XB - external migration baselines (re-implemented): preregistration REVISED DRAFT (2026-10-20)

Status: **REVISED DRAFT 2 (2026-10-21), not frozen. Nothing implemented or run.** Roadmap step 3
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
| | **P-full** (Llumnix-style pre-copy) | source keeps generating and serving; all components copied in rounds (changed fragments only after round 1); short stop-and-copy; destination resumes | bit-exact |
| | **R-full** (ServerlessLLM-style recompute) | destination re-runs the session from call 0 from the input frames (same per-call seeds); source keeps serving until it catches up | bit-exact by construction |
| **hybrid (uses OTTER's M1)** | **P-sink** | the Sink is pre-copied in rounds while the source serves; at switchover the rest goes by OTTER's M1 fast path and the destination rebuilds recent KV / VAE caches as in M1 | Sink exact, ephemeral state rebuilt |
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

- **P-full / P-sink rounds:** round 1 sends the component set; round r >= 2 sends fragments whose content hash changed
  since last sent (4 MiB fragments, VACW hashing). Switchover threshold (dirty set size), round limit and the
  non-convergence rule are **fixed by the calibration** (section 4) before the main sweep.
- **R-full rounds:** the destination replays while the source serves; switchover when the destination is within a lag
  threshold, else after a round limit (then the source stops and the destination finishes catching up while nothing is
  delivered). Lag threshold and round limit fixed by the calibration.
- **R-win window W:** fixed by the calibration from W in {1, 3, 6} (the existing replay variants).
- **Wait-for-Sink, Full migration, OTTER:** no parameters (frozen implementations).

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
1. Eligibility: the run is valid (W / R / N rules) and passes its class's correctness check (P-full and R-full
   bit-exact after switchover; P-sink Sink digest at bind).
2. P-full, P-sink, R-full: smallest TTFO-local; settings within 5 % of the smallest are tied, and the tie goes to the
   smallest delivery gap, then to the fewest remote-served chunks, then to the smaller threshold / round limit.
3. R-win: among W whose terminal PSNR is within 1.0 dB of the best W, the smallest TTFO-local (so the approximate
   baseline is not handicapped by a needlessly large window, nor credited with a window that only looks fast because it
   degrades the stream).
4. Timing-jitter check: if a selected setting's two repeats differ from its first run by more than 10 % in TTFO-local,
   the calibration of that method is repeated with 3 runs per setting and the median decides (stated, not silent).
5. The selected values, the whole grid (TTFO-local, delivery gap, remote-serving time, rounds, dirty bytes per round,
   switchover reason) and the alternative "minimum delivery gap" setting of each pre-copy variant are written into this
   document and frozen with it before any main-sweep run. If the minimum-delivery-gap setting differs from the selected
   one, its main-sweep numbers are not run; its calibration numbers are reported next to the main results.

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
or the last 10 delivered calls), bytes (source egress, total network, transferred inputs, pre-copy rounds), destination
GPU-seconds before serving, extra source GPU-seconds while serving remotely, convergence (rounds, dirty bytes per round,
switchover reason).

## 7. Hypotheses (medians over 3 valid reps; thresholds fixed at the freeze)

| id | class | statement | success | prediction |
|---|---|---|---|---|
| **XH1a** | exact, full state (Full, P-full, R-full) | OTTER resumes locally much sooner than every method that moves or recomputes the whole state (XB1, both workloads) | TTFO-local(OTTER) <= 0.25 x each exact method's | OTTER ~0.7 s; Full ~54 s; P-full >= 35 s; R-full >= 17 s |
| **XH1b** | hybrid and approximate (P-sink, Wait-for-Sink, R-win) | OTTER resumes locally sooner; the price is reported next to it | TTFO-local(OTTER) <= each method's TTFO-local - 1.0 s; descriptive (no threshold): delivery gap, remote-serving cost, trajectory of each | Wait-for-Sink ~15 s; P-sink >= ~15 s with no delivery gap but remote serving; R-win 5.8-7.1 s (earlier single-handoff replay) and never rejoins; OTTER rejoins after bind |
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
remote-serving accounting checked against the delivered-chunk log (each chunk delivered once).

## 9. Runs, runtime, occupancy

| phase | runs | hosts | time |
|---|---|---|---|
| calibration (section 4) | 35 | A, B | ~1.5-2 h |
| shakedown (one run per method and scenario: XB1 7 x 2, XB2 3, XB3 5, XB4 5) | 27 | A-D | ~1.5 h |
| main sweep: XB1 7 x 2 workloads x 3 = 42; XB2 3 x 3 = 9; XB3 5 x 3 = 15; XB4 5 x 3 = 15 | **81** | A-D | ~5-6 h |
| **total GPU runs** | **143** | | **~8-9.5 h** |

Shakedown and calibration are not evidence. Exclusive use of GPU 0 on the listed hosts; no commit or pull on the
testbed while a phase runs.

## 10. Implementation (after review; not started)

1. Pre-copy: source keeps generating after the trigger while a copier sends rounds; per-round content hashes (VACW
   snapshot capture and hash comparison reused); switchover protocol; P-full packs every component; P-sink hands the
   rest to M1.
2. Recompute: destination replay from inputs (the state-study `replay_full` / `replay_W` paths moved into the node),
   input-frame transfer, rounds, switchover.
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
