# Experiment XB - external migration baselines (re-implemented): preregistration DRAFT (2026-10-20)

Status: **DRAFT, not frozen. Nothing implemented or run.** Roadmap step 3 (`../evaluation_roadmap.md`). No frozen result
is modified; no M1 / M2 / M3-v2 change. Open decisions in section 10; **D1 (the fairness rule) must be closed first**.

## 1. Purpose and scope of the comparison

No published system migrates streaming video diffusion sessions. XB compares OTTER with the two closest recent migration
methods, both from LLM serving (autoregressive transformers with a KV cache), **re-implemented inside OTTER's harness**
(same model, transport, caps, fragment table and timing boundaries), plus one internal ablation:

| name | origin (principle only) | what it does here |
|---|---|---|
| **Pre-copy (Llumnix-style)** | Llumnix, OSDI '24 (live migration of a request's KV cache, pipelined with decoding) | after the trigger the source keeps generating and serving; state is copied to the destination in rounds; each round sends what changed since the previous one; then a short stop-and-copy and the destination resumes with all copied state |
| **Recompute (ServerlessLLM-style)** | ServerlessLLM, OSDI '24 (migrate tokens, not KV; the destination recomputes the KV) | the destination rebuilds the state by re-running the session from its inputs; the source keeps serving until the destination has caught up (or a round limit is hit) |
| **Wait-for-Sink (internal ablation)** | - | M1 fast path, but the destination does not generate until the Sink is bound (no Sink-less generation) |
| Full migration (existing) | - | stop, copy the whole 6.02 GiB state, resume (ExpD) |
| OTTER | - | M1 + frozen M2 + M3-v2 (`reuse_dyn2`) |

These are not the original systems (different workload, framework, cluster); the paper names them "Llumnix-style
pre-copy" and "ServerlessLLM-style recompute" and compares principles, not products. VM post-copy and edge proactive
synchronization are related work only; proactive placement is OTTER's own M3 (ExpD C / D).

**Where the original assumptions break (to be measured, not assumed):** Llumnix relies on an append-only KV cache; here
the Sink changes (refresh, RoPE realignment: Task B, half of the Sink's K every ~45 calls) and the recent KV and VAE
caches change every call. ServerlessLLM relies on fast parallel prefill; here every chunk depends on the
previous chunk's output, so recomputation costs about as much as generation (state study: full replay of 30 chunks
17.2 s, bit-exact, ~570 ms per history chunk).

## 2. Fairness rule (D1, to be closed before anything else)

Pre-copy and recompute let the **source keep generating after the trigger**. If that is free, they never interrupt the
stream and keep the reference trajectory, so the comparison hinges on what serving from the old host costs.

- **Option (a) - no remote serving:** at the trigger the user's connection to the old host ends; anything the source
  generates afterwards is not delivered. Pre-copy / recompute then deliver nothing until the destination resumes.
- **Option (b) - remote serving allowed and charged (recommended):** the source keeps serving; every chunk delivered
  from a host other than the user's current edge counts as **remote-served**, reported as remote-serving time and
  remote chunk count, and never as interruption-free local service. With repeated moves (rho >= 1) the user leaves the
  intended destination before pre-copy or recompute finishes; the method then restarts toward the new edge (no reuse
  of the abandoned copy, as in the original methods) and remote serving continues.

Under either option all methods are reported on the same timeline; under (b) a method may look better on continuity
and worse on locality, and both are reported.

## 3. Method definitions (fixed parameters)

- **Pre-copy, two variants.** (P-full) all state components (Sink, recent KV, VAE caches, meta, in-flight);
  (P-sink) Sink only by pre-copy, the rest by OTTER's M1 fast path at the switchover (recent KV and VAE rebuilt as in
  M1). Rounds: round 1 sends the whole component set; round r >= 2 sends the fragments whose content hash changed
  since they were last sent (content hashes per 4 MiB fragment, as VACW). **Switchover** when a round's dirty set is
  <= 64 MiB, or after 6 rounds, or when a round's dirty bytes do not shrink by >= 10 % (non-convergence); then the
  source stops at a chunk boundary and sends the final dirty set plus immediate state. Predicted: P-full does not
  converge at 1 Gbps (every call rewrites one recent-KV ring slot, ~0.54 GiB, and updates the VAE feature caches,
  up to 2.8 GiB: a dirty rate far above 1 Gbps; the actual per-call dirty bytes are measured in the shakedown);
  P-sink converges or hits the round limit depending on refresh / realignment.
- **Recompute, two variants.** (R-full) the destination replays the session from call 0 from the input frames
  (transferred, measured bytes) with the same per-call seeds (bit-exact by construction); (R-win) it replays only the
  last W = 3 chunks (the earlier single-handoff `replay` policy; not exact). Multi-round: the source keeps serving
  while the destination replays; switchover when the destination is <= 1 chunk behind, or after 6 rounds (then the
  source stops and the destination finishes catching up while nothing is delivered). Predicted: R-full never catches up
  with a source generating at the same per-chunk cost, so the round limit decides; its catch-up stall grows with the
  session length.
- **Wait-for-Sink:** destination resumes generation only at Sink bind; TTFO = bind-ready.
- **OTTER, Full migration:** frozen implementations.

## 4. Scenarios

| id | mobility | network | workloads | methods |
|---|---|---|---|---|
| XB1 | single move A -> B at trigger chunk 30 | 1 Gbps | dog, butterfly-feeding-slow-motion (seed 0) | all seven (OTTER, Full, Wait-for-Sink, P-full, P-sink, R-full, R-win) |
| XB2 | single move, trigger chunk 120 (longer session) | 1 Gbps | dog | OTTER, P-sink, R-full |
| XB3 | A -> B -> C -> D, rho 1 | 1 Gbps | dog | OTTER, Full, Wait-for-Sink, P-sink, R-full |
| XB4 | A -> B -> C -> D, rho 2 | 1 Gbps | dog | as XB3 |

XB2 isolates the dependence of recompute on session length. P-full and R-win are only in XB1 (their outcome there
decides whether they matter).

## 5. Metrics (all on the orchestrator clock, relative to the trigger or the final move)

- **Local resumption:** time until the user's **current** edge produces its first chunk (TTFO-local).
- **Delivery gap:** longest interval with no chunk delivered to the user from any host (option (b)) or from the
  current edge (option (a)).
- **Remote serving (option b):** seconds and chunks delivered from a host other than the current edge.
- **Trajectory:** PSNR against the uninterrupted run (single crossing, sustained 10 calls, terminal median), as RD
  section 5.1; pre-copy and R-full are expected bit-exact after switchover.
- **Bytes:** source egress, total network bytes, including pre-copy rounds and transferred inputs.
- **GPU work:** destination GPU-seconds spent before it serves (recompute), extra source GPU-seconds while serving
  remotely.
- **Convergence:** rounds, dirty bytes per round, switchover reason.

## 6. Hypotheses (medians over 3 valid reps; thresholds fixed at the freeze)

| id | statement | success | prediction |
|---|---|---|---|
| XH1 | OTTER resumes locally much sooner than every baseline (XB1, both workloads) | TTFO-local(OTTER) <= 0.1 x each baseline's | OTTER ~0.7 s; Wait-for-Sink ~15 s; P-sink >= ~15 s; Full ~54 s; R-full ~17 s + rounds |
| XH2 | pre-copy of the full state does not converge at 1 Gbps (XB1) | P-full ends by the round limit or the non-convergence rule in every run | as stated |
| XH3 | recompute cost grows with session length (XB1 vs XB2, dog) | R-full's destination GPU-seconds before serving at trigger 120 >= 3 x at trigger 30 | ~4x |
| XH4 | under repeated mobility the baselines that wait for state accumulate remote serving or delivery gap (XB3, XB4) | remote-serving time (b) or delivery gap (a) of P-sink and R-full >= 5 x OTTER's TTFO-local at rho 1 and rho 2 | the user leaves before the copy or replay completes |
| XH5 | OTTER's trajectory cost is reported, not hidden | descriptive: OTTER's gap PSNR and rejoin vs the bit-exact baselines | OTTER diverges until bind (~17 dB), baselines do not |

NOT EVALUABLE: < 3 valid reps of a compared method; censoring per `followup_common.md` section 3. Every baseline's
numbers are reported in every scenario whether or not a hypothesis uses them.

## 7. Validity

W / R / N run rules (all fragments verified, digest, NIC checks, GPU 0 idle, one commit); for recompute, the replayed
state's frame digests vs the reference (R-full must be bit-exact; a mismatch is a harness fault); pre-copy's final
state digest vs the source's at switchover.

## 8. Runs, runtime, occupancy

XB1: 7 methods x 2 workloads x 3 reps = 42; XB2: 3 x 3 = 9; XB3: 5 x 3 = 15; XB4: 15 -> **81 runs**. Recompute runs
take longer (catch-up). Estimate **~5-6 h** of exclusive use of GPU 0 on the four hosts, plus a shakedown (one run per
method and scenario, ~1 h).

## 9. Implementation (not started)

1. Pre-copy: the source keeps generating after the trigger while a copier thread sends rounds; per-round content hashes
   (VACW snapshot capture and hash comparison reused); switchover protocol; P-full packs every component.
2. Recompute: destination replay from inputs (the state-study `replay_full` / `replay_W` code paths moved into the
   node), input-frame transfer, round bookkeeping and switchover.
3. Wait-for-Sink: node flag that defers generation until bind.
4. Remote-serving accounting (which host delivered each chunk vs the user's current edge) and the delivery-gap metric.
5. Loopback tests of every method, then the shakedown. No change to OTTER's mechanisms.

## 10. Open decisions (close before the freeze)

- **D1** - fairness rule (a) or (b)? Recommended: (b), remote serving allowed and charged.
- **D2** - keep P-full and R-win (XB1 only) or drop them (-12 runs)? Recommended: keep; they show why the simple
  versions fail.
- **D3** - pre-copy switchover parameters (64 MiB, 6 rounds, 10 % shrink) and recompute round limit (6): keep as
  written or adjust before the freeze.
- **D4** - add a refresh-heavy workload to XB3 / XB4 (+30 runs)? Recommended: no (WX covers workload breadth for
  OTTER; XB is about the methods).
