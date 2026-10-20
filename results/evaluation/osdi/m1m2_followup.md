# M1 / M2 follow-up: recent-KV handoff ablation (Task A) and Sink version reuse feasibility (Task B)

Inspection report and plans, 2026-10-19. **Nothing run on a GPU for this document; no code changed.** Frozen results
(ExpD, W / R / N), the M3-v1 and M3-v2 code and the M3-v2 evaluation are untouched. Mechanism names: M1 Temporal State
Decomposition, M2 Continuity Wavefront, M3 Restoration Graph Morphing. Observed facts and hypotheses are marked.

## Task A - M1 continuity ablation: recent-KV handoff

### A.1-A.2 Temporal KV layout and what can be transferred consistently (observed, from the code)

- Ring per layer: `num_kv_cache` = 6 slots x `frame_seq_length` tokens (480x832: 1,560 tokens = one latent frame = 4
  video frames), x 2 Stream-Batch rows (k = 2); `num_sink_tokens` = 3 slots are the Sink, the other **3 slots are the
  recent window** (`models/wan/causal_stream_inference.py`). Per slot, row, layer and key: 1,560 x 1,536 x 2 B =
  4,792,320 B; the whole recent window (30 layers x k, v x 2 rows x 3 slots) = 1,725,236,480 B, the same size as the
  Sink. **One recent slot (all layers, k + v, both rows) = 575 MB.**
- Each slot carries its RoPE frame position (`kv_cache["pos"]`, `KV_POS_EMPTY` = unused); the model re-rotates filled
  slots itself at a t_refresh rewind (`causal_model.py` `_realign_kv_positions`, decided from `pos`), so a transferred
  slot is consistent as long as its K/V and its `pos` arrive together. The `meta` component already carries `pos`,
  `global/local_end_index` and the eviction queues for all 6 slots; `restore_state` zeroes every slot and writes the
  selected components (`tools/state_ablation.py`): today M1 writes the Sink later (bind) and leaves the recent slots
  **zero with their positions set**, which is the measured "recent dropped" behaviour (attention sees zero K/V in those
  slots until the ring refills them).
- Therefore the transferable recent windows are **0, 1, 2 or 3 slots** (= 0, 4, 8, 12 video frames), selected per row
  as the slots with the largest `pos`; their K/V are written to the same slot indices with the existing `pos`, the
  others stay zero exactly as now. "4 or 6 positions" do not exist as recent slots: 6 = the whole ring = Sink + recent
  (the Full-migration KV); the proposal maps the requested {0, 2, 4, 6} to the feasible {0, 1, 2, 3} slots.
- Timing semantics (observed in the frozen ablation, `results/state_migration/ablation_notes.md`): recent KV is
  **immediate** state: delivered 1 call late it gives a slight gain (25.0 dB vs 23.7), 2 calls late none. So a recent
  window only helps if it is part of the **fast path** (sent with in-flight + meta before the first call at the
  destination), and its cost is paid in TTFO: 575 MB per slot = **4.6 s per slot at 1 Gbps, ~0.5 s per slot at the
  native 9.4 Gbps**. There is no "late recent" variant worth testing.
- Prior evidence (frozen ablation, dog, k = 2): dropping the recent window costs -10 dB over calls M+0..3 (23.7 dB) and
  heals by ~M+6; on bird k = 2 and k = 4, dropping recent KV **and** the VAE caches together fails to heal within 40
  chunks while dropping either alone heals (interaction; `state-ablation` notes). W2 (frozen): 8 of 40 units never hold
  35 dB for 10 consecutive calls after the bind, all refresh-heavy clips.
- **Hypotheses (not results):** (A-H1) a 1-3-slot recent window raises the gap quality (M+0..5) by ~10 dB on every
  workload; (A-H2) it does not change TTFO at native bandwidth by more than ~0.5 s per slot but by 4.6 s per slot at
  1 Gbps, so at 1 Gbps it cannot satisfy W-H1's 1.0 s bound by construction; (A-H3) on refresh-heavy clips it may turn a
  non-sustained recovery into a sustained one (the bird evidence), which is the only outcome that would justify its
  TTFO cost.

### A.3-A.5 Implementation plan (baseline preserved; not implemented)

- Node option `--recent_slots n` (default 0 = the frozen M1 fast path, byte-identical behaviour). In `cmd_exec_handoff`
  (mode "fast") the source packs, after `inflight` and `meta`, a new component `recent_n`: for each row the n slots with
  the largest `pos` among the recent slots: tensors `kv/<layer>/<k|v>` restricted to those slot indices plus the index
  list; the destination's `restore_fast` writes them into the same indices (shapes [rows, n x 1,560, 12 x 128]); `pos`
  comes from `meta` as now. Nothing else changes (Sink restoration, bind, re-rotation, M2, M3).
- Checks before the GPU runs: shapes and indices (unit test on a CPU snapshot), the destination's first call uses the
  transferred slots (positions equal to the source's), realign after bind unchanged.

### A.6-A.9 Ablation plan (small; preregistered rules; to run after the M3-v2 holdout)

- **Workloads (rule, fixed now):** dog (the ExpD workload) + the four workloads with the lowest W2 last-10-call
  median PSNR among distinct workloads: audi-snow-trail (30.2 / 31.9), butterfly-feeding-slow-motion (31.2 / 35.3),
  circus-ball-act (31.4 / 39.3), train (31.8 / 32.0). Seeds 0 and 1: 10 units.
- **Factors:** recent window n in {0, 1, 2, 3} slots; bandwidth 1 Gbps and native. Policy OTTER event-driven
  (reuse_dyn), single move A -> B at M = 34, horizon 100 calls, as W2. 10 x 4 x 2 = **80 runs (~5 h)**; the 1 Gbps half
  can be dropped to 40 runs if time is short (it is the cost-dominated regime).
- **Metrics:** TTFO; sustained recovery (first call from which PSNR >= 35 dB holds for 10 consecutive calls; censored at
  the horizon); terminal PSNR (median of calls 124-133); additional migration bytes (n x 575 MB, measured); Sink
  bind-ready; gap PSNR (mean over the first 6 post-trigger calls). A single crossing is reported but is not the
  recovery measure.
- **Go / no-go rule (fixed before data):** GO for n* if at native bandwidth n* raises the number of units with sustained
  recovery by >= 3 of 10 **or** the median terminal PSNR by >= 3 dB, with a median TTFO increase <= 1.5 s over n = 0;
  otherwise NO-GO. At 1 Gbps the result is reported as the cost side (TTFO +4.6 s per slot) and cannot be GO under
  W-H1's 1.0 s bound. Recorded prediction: GO is plausible only at native bandwidth and only for the refresh-heavy
  clips; at 1 Gbps NO-GO.

## Task B - M2 version reuse feasibility

### B.1-B.2 What the W1 logs contain (observed)

Per call (330 calls x 40 units, `results/evaluation/expW_W1/*/w1_calls.csv`): for each of 30 layers x 3 sink slots the
float64 **sum of the value cache** over both rows (90 numbers), the sink-slot positions (layer 0), the call class.
They are **not sufficient for exact fragment-level reuse**: (i) keys are not fingerprinted (a promotion writes K and V
of a slot; a t_refresh realign re-rotates every K block without touching V: K bytes change at calls 48, 93, 138, ...
while the V fingerprints do not); (ii) the two Stream-Batch rows are summed, so a change cannot be attributed to a row
(each row is a separate byte block); (iii) a sum is not a content identity. The Sink pack layout is known exactly
(`tools/proto_handoff.pack_component`: per layer k then v, [row, slot] blocks of 4,792,320 B, then 48 B of positions;
1,725,236,640 B = 412 fragments of 4 MiB), so block-level dirtiness maps to fragments, but a block (4.57 MiB) is not
fragment-aligned (~2.1 fragments per block).

### B.3-B.5 Approximate reuse from the existing logs (observed numbers under stated assumptions)

Assumptions: a V change marks the (layer, slot) block dirty in K and V and in **both** rows (over-estimates dirtiness
by up to 2x in rows); realigns are ignored (they would dirty every K fragment = 50 % of the Sink unless the receiver
re-rotates locally, which `bind_sink_into_live` already does by position delta). For every trigger call c in [30, 330-d]
the dirty set over (c, c + d]:

| delta (calls; s at 0.556 s/call) | slot-level dirty (median over 40 units) | fragment-level dirty, mean / max over triggers (median unit) | refresh-heaviest unit (butterfly s0) mean / max | dirty bytes (median unit, mean) | update bandwidth if synced every delta (median / butterfly) |
|---|---|---|---|---|---|
| 1 (0.56 s) | 0.1 % | 0.1 % / 4.1 % | 2 % / 15 % | 1.7 MB | 25 Mbps / 500 Mbps |
| 5 (2.8 s) | 0.4 % | 0.7 % / 6.3 % | 9 % / 22 % | 12 MB | 35 / 450 Mbps |
| 10 (5.6 s) | 0.7 % | 1.3 % / 8.3 % | 14 % / 25 % | 22 MB | 32 / 350 Mbps |
| 25 (13.9 s) | 1.8 % | 3.2 % / 9.8 % | 22 % / 30 % | 55 MB | 32 / 220 Mbps |
| 50 (27.8 s) | 3.4 % | 5.6 % / 11.9 % | 28 % / 34 % | 97 MB | 28 / 140 Mbps |

Reading: for the median workload > 94 % of the Sink's fragments are unchanged 50 calls (28 s) later, and keeping a
remote copy current costs ~30 Mbps; for the refresh-heaviest clips 66-72 % remain valid after 28 s and per-call
synchronization would need 450-500 Mbps (batched every 14-28 s: 140-220 Mbps). These are **approximations** (V-only,
rows merged); they bound the exact numbers from above in rows and from below in keys-at-realign.

### B.6 Minimal instrumentation for exact numbers

Per call at the source, per (layer, key, row, slot): a content checksum of the 4,792,320 B block computed on the GPU
(e.g. the int64 sum of the block viewed as int32, ~1.7 GB read per call, ~2 ms) = 720 integers per call, plus the
realign events and `pos`. With a **block-aligned fragment table** (fragment = one block, 360 fragments of 4.57 MiB
instead of 412 x 4 MiB) dirtiness becomes exact at fragment granularity. Cost: one W1-style run per unit (no network);
10 units suffice for the estimate (~30 min), 40 for the full table. No inference from promotion counts.

### B.7-B.8 Version-Aware Continuity Wavefront (design proposal; not implemented)

- **Content-addressed, block-aligned fragments:** fragment id = (layer, key, row, slot); a fragment's identity is its
  block checksum; the source's per-call checksum table is the version table.
- **Snapshot consistency:** the Sink transferred to a destination is one source snapshot S_t (as now); the manifest
  carries S_t's 360 checksums. A holder's fragment is reusable for S_t iff its checksum equals S_t's; otherwise it is
  dirty for S_t. The destination binds only when all 360 fragments of S_t are verified (unchanged rule).
- **Keys at a canonical rotation:** K blocks are stored and forwarded as rotated at their own `pos`; a realign at the
  source changes only `pos`, and the receiver re-rotates at bind (as today), so realigns never dirty fragments.
- **Wavefront with versions (M2):** at a move, the planner assigns each of S_t's fragments to a holder whose copy has
  the same checksum (verified fragments of an older snapshot that did not change), otherwise to the source; the
  frozen M2 / M3 assignment rules then apply unchanged to the per-fragment provider sets.
- **No rolling synchronization yet:** holders are not refreshed between moves; the numbers above say what a refresh
  would cost if it were added later.

## Go / no-go (preliminary; the GPU ablation decides Task A)

| proposal | recommendation now | basis |
|---|---|---|
| A: recent-KV handoff at 1 Gbps | **NO-GO** (predicted) | +4.6 s TTFO per slot against a 0.68 s fast path; the ablation shows the window only matters within ~2 calls |
| A: recent-KV handoff at native bandwidth | **run the ablation** (40 runs, ~2.5 h) | +0.5 s per slot; the bird evidence and the 8 non-sustained W2 units make a sustained-recovery gain plausible but unproven |
| B: exact reuse instrumentation + offline study | **GO** (cheap, no mechanism change) | the logs cannot give exact numbers; 720 checksums per call do |
| B: version-aware wavefront implementation | **design only, not now** | the approximate numbers (>= 94 % reusable after 28 s for the median clip) justify the design; implementation would be a new mechanism with its own preregistration, after the M3-v2 holdout |

## Decisions and constraints (user, 2026-10-19)

Execution order: M3-v2 regression -> freeze -> V holdout -> Task A (native) -> Task B instrumentation.

Task A: the native-network 40-run ablation first (5 workloads x 2 seeds x n in {0, 1, 2, 3} slots, policy OTTER
event-driven, M = 34, horizon 100); the n = 0 baseline's TTFO is preserved (default path, byte-identical); the actual
transferred bytes of the fast path are measured per run (not n x 575 MB assumed); success = sustained 10-call rejoin
and terminal median PSNR, never a transient PSNR gain. **Consumption check:** the destination logs, at its first call,
the K/V fingerprint and `pos` of each recent slot; they must equal the source's at the handoff (the transferred slots are
in the live ring) and the first output must differ from the n = 0 run's (the slots were attended to) - a run failing
either check is a harness fault, not a result.

Task B: the 94 % figure is an **estimate from V-only fingerprints**, not a measurement. The exact study measures K and
V block changes separately per (layer, key, row, slot) and per call, and attributes each change to Sink refresh
(promotion: K and V of a slot change together, `pos` of the slot changes) or to key realignment (K changes, V and the
slot's content identity do not, `pos` of every filled slot shifts by the same delta). **Canonicalized RoPE keys are not
assumed bitwise equivalent:** re-rotation in bf16 is lossy; before any canonicalization is adopted, the exact study
compares re-rotated keys with the source's keys at the same position (bitwise and max abs error) and the resulting
outputs (PSNR against the uninterrupted reference), as the current bind already re-rotates and ExpD's bit-exactness of
Full migration does not cover that path. No rolling synchronization is implemented.

## Experiment A preregistration (M1 recent-KV handoff; to be frozen at the commit that implements it; nothing run)

- **Question:** does sending the n most recent ring slots with the fast path (n in {1, 2, 3}) turn M1's transient gap into a
  sustained recovery on workloads where the frozen W2 showed none, and at what TTFO and byte cost?
- **Unit:** (workload, seed): dog, audi-snow-trail, butterfly-feeding-slow-motion, circus-ball-act, train x seeds 0, 1 = 10
  units (rule: dog + the four distinct workloads with the lowest W2 last-10-call median PSNR). **Factor:** n in
  {0, 1, 2, 3} slots (n = 0 = the frozen M1 fast path, byte-identical code path). **Fixed:** OTTER event-driven
  (`reuse_dyn`), single move A -> B at M = 34, horizon 100 calls (133), **native bandwidth** (unshaped, ~9.4 Gbps), k = 2,
  one run per (unit, n): **40 runs**, 10 orchestrator invocations (n is a per-run handoff parameter).
- **Primary metrics** (per run): TTFO (s); fast-path bytes actually sent (`fg_bytes`, measured); sustained rejoin = the
  first call >= the bind call from which PSNR >= 35 dB holds for 10 consecutive calls (censored at 133); terminal PSNR =
  median of calls 124-133; Sink bind-ready (s). Descriptive: gap PSNR (mean of the first 6 post-trigger calls),
  single-crossing rejoin (reported, never the success measure).
- **Consumption check** (harness correctness, per run with n > 0): the destination's live ring before its first call
  holds, for every transferred slot, the same position and value fingerprint the source logged at the handoff
  (`recent_handoff_src` / `recent_handoff_dst` events), and its PSNR series over the first 6 post-trigger calls differs
  from the n = 0 run's. A run failing either check is a harness fault and is listed, not counted.
- **Go / no-go (decision rule fixed now; `tools/eval/aggregate_wrn.py` section A):** for each n* in {1, 2, 3}: GO iff
  (units with a sustained rejoin at n* - units at n = 0 >= 3) or (median terminal PSNR at n* - at n = 0 >= 3.0 dB), and
  (median TTFO at n* - at n = 0) <= 1.5 s; NOT EVALUABLE if fewer than 8 of 10 units have a valid run at n* or at n = 0.
- **Recorded predictions:** TTFO +0.5-0.6 s per slot at native bandwidth (575 MB per slot); gap PSNR +~10 dB (frozen
  ablation); sustained-recovery gain uncertain (the only outcome that would make GO); 1 Gbps not run (cost 4.6 s per
  slot, NO-GO by construction).
- Validity: `followup_common.md` section 3 (native: NIC peaks against the 9.4 Gbps physical cap, as in ExpD's native runs).

**Experiment A frozen at commit `bfc2ce08ebdf8fa41fc7b6b229d8c4dfe5910b71` (2026-10-20):** matrix, metrics, consumption check and the go / no-go rule above;
code `tools/proto_handoff.py` (recent_n), `tools/eval/mobility_node.py`, `tools/eval/mobility_orchestrate.py`
(`--recent_slots`), `tools/eval/run_wrn.py a`, `tools/eval/aggregate_wrn.py` section A. Development data: the frozen
ablation (2026-10-06/09), W2, the loopback. No Experiment A GPU run exists.
