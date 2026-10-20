# Version-aware Continuity Wavefront v0 (M2 extension): design and preregistration (FROZEN 2026-10-20; record `../vacw_v0_freeze.md`; not implemented at the freeze; nothing run)

Revision history: draft 89f2334; review corrections (I5 scope, I3 / I4 buffer ownership, H2 reuse definitions, H1b wording, exposure criterion) applied before the freeze.

Mechanism names: M1 Temporal State Decomposition, M2 Continuity Wavefront, M3 Restoration Graph Morphing. Experiment A
is frozen NO-GO; M1, M3-v1, M3-v2 and every frozen result (ExpD, W / R / N, V, A, B) are unchanged. Inputs from Task B
(`../m1m2_results.md`): exact 412-fragment reuse after 50 calls 50-64 % (after 25 calls 66-79 %) with realignment-induced
key changes, 88-99 % refresh-only; RoPE re-rotation is not bitwise; key canonicalization and rolling synchronization are
**out of scope** for v0.

## 0. What exists and what is new (from the code, `tools/eval/mobility_node.py`, `mobility_orchestrate.py`, `proto_handoff.py`)

Exists today (frozen harness):
- At the trigger the source A runs to chunk M, serializes the Sink (D2H) into **one contiguous host buffer** (immutable
  for the run), builds the fragment table (412 x 4 MiB byte ranges, each with its SHA-256), the whole-Sink digest, and
  one **manifest** `{session_id, sink_version = digest prefix, nbytes, frags[id: off, len, sha256]}` pushed to every node.
- A node keeps `sink_buf` (host, Sink-sized), `have` (verified ids), `frag_ok`; on receipt it rejects a fragment whose
  `sink_version` or `session_id` differs from its manifest, verifies `sha256(bytes) == manifest.sha256 == header.sha256`,
  never overwrites verified bytes (duplicates go to scratch), forwards only ids in `have`, and binds only after the
  **whole-Sink digest** of `sink_buf` matches the manifest. M1 only drops holdings at a move (`SINK_DROP`, epoch).
- Every owner that binds continues generating with adaptive refresh on; its live Sink then diverges from the manifest's
  snapshot (refresh and realignment), but **no owner ever re-snapshots**: the manifest stays A's chunk-M snapshot for
  the whole run.

New in v0 (and nothing else):
1. **Fresh snapshot at every handoff from a bound owner**: the leaving owner captures its live Sink at the generation
   boundary of the handoff and publishes a new manifest S_k (k = move index).
2. **Content-hash reuse across snapshots**: a held fragment is valid for S_k iff its SHA-256 equals S_k's entry for that
   id, regardless of which snapshot it was received under; the version tag check becomes a hash check.
3. **Single active snapshot** (assumption, enforced): at any time exactly one manifest is the restoration target; a
   node holds at most one verified byte image per fragment id (the newest), stored as an **immutable per-fragment
   object** (section 2, I3 / I4), so replacing it never mutates bytes an outgoing flow is sending.

## 1. State machine

### 1.1 Snapshots

S_0 = A's snapshot at chunk M (as today). For each move k >= 1 from owner O_k to O_{k+1}:
- if O_k **bound** a Sink during its ownership (bind event before the handoff) and generated on it, O_k captures
  **S_k** at the handoff boundary (after its last call, before the fast-path send completes; the GPU ring is frozen
  because O_k stops generating): D2H of the live sink K/V and positions into a **new host buffer**, fragment table with
  SHA-256 per fragment, whole digest; S_k becomes the active snapshot;
- if O_k never bound (rho >= 2 regime: it is left before the Sink arrives), **S_k = S_{k-1}** (the active snapshot is
  unchanged; O_k's verified fragments of S_{k-1} remain valid holdings).

### 1.2 Per-node fragment state (per fragment id f, per node)

`ABSENT -> RECEIVING -> VERIFIED(h)` where h is the SHA-256 of the immutable `bytes` object stored for f (`store[f]`);
`VERIFIED(h)` is *valid for the active snapshot* iff `h == S_active.sha256[f]`, else *stale* (kept; reusable if a later
snapshot has the same hash, otherwise replaced by the next valid receipt). Transitions:
- `recv(f, bytes, h')`: the node verifies `h' == sha256(bytes)` and compares h' with **its current manifest's** entry
  for f: equal -> if `store[f]` exists with the same hash, duplicate (dropped); else `store[f] = bytes` (rebinding the
  dict entry; any outgoing flow still holding the previous object keeps it alive); not equal -> rejected and logged
  `fragment_rejected_hash`. No ordering assumption between `MANIFEST_UPDATE` and in-flight fragments is needed: a
  fragment of an older flow that arrives after the update is accepted iff its hash matches the new manifest (its
  content is then exactly what the new snapshot needs), and one that arrives before the update is judged against the
  old manifest and becomes stale or valid at the update by its hash.
- `drop` (M1 only, as today: the store is cleared; objects referenced by draining flows survive until those end).

### 1.3 Owner states

`PROVISIONED -> OWNER(unbound) -> OWNER(bound, S_j) -> LEAVING -> HOLDER` with:
- `OWNER(bound, S_j)` bind happens only when every fragment is VERIFIED and valid for S_j and the whole-Sink digest
  equals S_j's (unchanged);
- `LEAVING`: on the handoff request the owner stops at the next chunk boundary, sends the fast path (as today), then,
  if it was bound, **captures S_k** (section 1.1) and publishes the manifest; until the manifest is published the
  orchestrator plans nothing for the new owner's Sink (the "manifest wait", measured);
- `HOLDER`: serves fragments from `sink_buf` whose hash matches the **active** snapshot; if it captured S_k it also
  holds S_k entirely (its `sink_buf` is replaced by the new buffer; the old buffer is released once no flow uses it).

### 1.4 Orchestrator

`manifest_active` replaces the single `manifest`; `holders[e]` becomes `valid[e]` = ids whose hash at e equals the
active manifest's (recomputed from the nodes' reported hashes when the manifest changes; nodes report `(id, sha256)` for
their holdings at a manifest change); planning (M2 / M3, unchanged rules) runs over `valid[·]`; the provider of a dirty
fragment (no holder has the new hash) is the capturing owner O_k (the "source" role moves with the snapshot; A is the
source only for S_0).

## 2. Correctness invariants (checked in every run; a violation is a harness fault)

- **I1 (single active snapshot):** at any time the orchestrator and every node agree on one `manifest_active`; a flow
  started under manifest S_j is cancelled when S_k != S_j becomes active (its in-flight fragment, if still valid by
  hash, is kept).
- **I2 (no cross-snapshot mixing in a bound Sink):** a node binds only when all 412 fragments are VERIFIED with hashes
  equal to S_active's **and** the whole-buffer digest equals S_active's digest. Hash-equal fragments received under an
  older snapshot are byte-identical by construction (SHA-256), so reuse never mixes *content*; the whole digest guards
  the table itself.
- **I3 (immutable transfer view; buffer ownership and lifetime):** fragments live as immutable `bytes` objects
  (`store[f]`, one per id); a snapshot capture produces 412 such objects from a write-once D2H buffer. An outgoing flow
  takes references to the objects of the fragments it will send **when it starts** and sends from those references;
  the objects stay alive until the flow terminates (Python reference counting pins them), whatever the store does
  meanwhile. Today's shared `sink_buf` + `memoryview` (which an in-place receive could mutate under an active sender)
  is replaced by this store; the contiguous image needed for the GPU unpack is assembled from the store at bind time
  (one 1.6 GB host copy, ~0.3 s, counted in the bind component of H3).
- **I4 (safe replacement):** receiving a newer fragment rebinds `store[f]`; it never writes into an existing object, so
  bytes referenced by an active outgoing flow cannot change. A flow started under a superseded manifest is cancelled by
  the orchestrator (I1); fragments it already sent are judged by hash at the receiver (section 1.2). Memory: a node
  holds at most one object per id in the store plus the objects pinned by draining flows (bounded by the fragments in
  those flows' queues, <= 1 Sink), i.e. <= 2 Sinks in the worst case, usually ~1.
- **I5 (Sink-snapshot freshness; scope):** the Sink bound by O_{k+1} equals, byte for byte, the Sink O_k was
  generating on at the handoff boundary (S_k) when O_k was bound, and S_{k-1} otherwise. (The frozen harness binds S_0
  at every owner, violating this at rho <= 1.) **I5 is a statement about the Sink only:** the recent KV window and the
  VAE caches are still reconstructed at O_{k+1} (M1 unchanged), so a fresh Sink does **not** imply equivalence of the
  whole generation state with O_k's, nor visual continuity; H1b measures the latter separately and a H1b failure with
  I5 / H1a holding is not an integrity fault.
- **I6 (progress preservation):** a fragment VERIFIED at an abandoned owner with hash equal to S_active's entry is
  never re-sent from the capturing owner if the planner can assign it to that holder (M2 rule unchanged); dropped only
  under M1 only.
- **I7 (positions travel with the snapshot):** S_k includes the sink-slot positions of its capture (as today: the
  `ring/pos_sink` tensors are part of the Sink pack), so bind re-rotation at the receiver (existing) uses S_k's positions.

Checksums alone do not guarantee correctness; I2 (whole digest), I3 (write-once buffers), I4 (no overwrite under an
active flow) and I7 (positions in the snapshot) are what make a hash match sufficient.

## 3. Minimal code-change plan (no M1 / M3 change; M2 assignment rules unchanged)

| where | change |
|---|---|
| `mobility_node.py` `cmd_exec_handoff` | after the fast path, if `r["bound_call"] is not None`: `snap = self.rt.serialize_live()` (sink + positions only), pack `sink`, build `frag_table` + SHA-256s (existing `component_digest` / `frag_table`), swap `sink_buf` to the new buffer (old buffer kept until flows end), set `have` = all ids, return the new manifest in the handoff reply (`fresh_manifest`); log `snapshot_captured` with D2H, pack and hash times |
| `mobility_node.py` fragment store | replace `sink_buf` (shared bytearray + memoryview sends) by `store: dict[id -> bytes]` with `hash_of[id]`; `_recv_frag` receives into a fresh `bytes`, verifies, rebinds; `_sender` takes object references at flow start and sends from them (I3 / I4); `_unpack_sink` assembles the contiguous image from the store in manifest order before the H2D (one host copy; timed) |
| `mobility_node.py` `_recv_frag` | replace the `sink_version` equality test by `hdr["sha256"] == man["frags"][fid]["sha256"]` (content check against the node's current manifest); log `fragment_rejected_hash` |
| `mobility_node.py` `cmd_manifest` | accept a **manifest update** mid-run: keep the store, recompute `have` = ids whose stored hash equals the new manifest's, report `(id, sha256)` holdings; a node that captured S_k installs its 412 objects directly |
| `mobility_orchestrate.py` `handoff` | if the reply carries `fresh_manifest`: `manifest_active = fresh`, push `MANIFEST_UPDATE` to every node, rebuild `holders[e]` from the reported holdings, cancel flows of the superseded manifest, then `plan("move")` (existing); record `t_snapshot`, `t_manifest` per move |
| `mobility_orchestrate.py` planning | provider of fragments no holder validly holds = the capturing owner (`SOURCE` role per snapshot: `self.source_of[S_k]`), M2 / M3 rules unchanged; `holder_order` unchanged |
| `mobility_orchestrate.py` accounting | per move: snapshot capture time, manifest wait (handoff -> first plan), fragment restoration (first plan -> Sink verified), bind; bytes by role (capturing owner vs holders vs A); **logical reuse** = fragments of S_k verified at the new owner from holders / 412; dirty fraction of S_k vs S_{k-1} |
| policy name | `split_va` (= `split` + fresh snapshots + hash reuse); `restart_fresh` (= M1 only with fresh snapshots: the capturing owner sends S_k whole); the frozen `split` and `restart` stay byte-identical |

Estimated size: ~250 lines; no change to transport, fragment format (header already carries `sha256`), M3 planners.

## 4. Snapshot capture and memory overhead

- **Capture cost (per handoff from a bound owner):** D2H of the sink K/V, 1,725,236,640 B over pinned host memory at
  ~6-12 GB/s: 0.15-0.3 s; fragment SHA-256 over 1.6 GB with the existing thread pool (6 workers): ~0.6-1.0 s (ExpD's
  `pack_hash_s` at A was ~1.5 s for the same work single-threaded); block-level GPU checksums (Task B, 2 ms) could
  replace SHA-256 for *dirtiness* but not for the transport's integrity check, so v0 keeps SHA-256. The capture happens
  **after** the fast path and after the owner stops generating, so TTFO is unaffected; it adds a **manifest wait** of
  ~0.8-1.3 s before the new owner's restoration plan (measured, part of H3's decomposition).
- **Host memory:** the store holds one object per id (1 Sink); objects of a superseded snapshot stay alive only while
  a draining flow references them (<= the fragments in that flow's queue); the capturing owner additionally holds the
  write-once D2H buffer until its 412 objects are cut from it (then released) and, at bind, every node assembles one
  contiguous image (1 Sink, released after the H2D). Bound: **<= 2 Sinks per node** (3.2 GB host) at any instant, ~1
  Sink in steady state; no change on the GPU.
- **Metadata:** 412 SHA-256 strings per manifest (~27 KB) per move; holdings reports 412 x (id, hash) per node per
  manifest change.
- **4 MiB fragment / 4.57 MiB block misalignment (kept in v0):** a changed block dirties the 2-3 fragments that overlap
  it; the measured 412-table reuse (50-64 % after 50 calls) already includes this amplification; block-aligned
  fragments (360 x 4,792,320 B) would raise reuse to the block-level values (Task B: +10-15 points) and are a
  serialization option for a later version, not v0.

## 5. Why the target regime is rho <= 1, and why the stale-M2 baseline is not freshness-correct

- At rho >= 2 (T_m < T_s) no owner binds before being left (ExpD / R data: 0 of 69 + 81 runs), so every owner's Sink is
  S_0 and content-hash reuse equals today's version-tag reuse: v0 changes nothing there (and is not evaluated there).
- At rho <= 1 an owner binds, generates with refresh on (W1: the Sink changes within 25 calls in ~50 % of dog windows,
  nearly always on refresh-heavy clips) and is then left. The frozen harness restores **S_0** at the next owner: holders
  forward S_0 fragments as valid (version tag matches), the whole digest of S_0 verifies, the bind succeeds - but the
  bound Sink is the one A had at chunk M, not the one the previous owner was generating on (I5 violated). R rho 0.5
  c = 0 was NOT EVALUABLE for exactly this (owner-side version events), i.e. the frozen M2 has no freshness-correct
  result in this regime, and its PSNR after the bind at C / D measures continuity with a stale anchor.

## 6. Preregistered evaluation (36 runs; to be frozen with the implementation)

- **Mobility:** A -> B -> C -> D, trigger M = 30, rho in {0.5, 1} (T_m = 28.10 s, 14.05 s), 1 Gbps, warm destinations,
  `post_chunks` 300, `max_run_s` 600. **Workloads:** dog seed 0 (refresh-light) and butterfly-feeding-slow-motion seed
  0 (refresh-heavy; W1: 356 refresh slot-rows / 300 calls). **Policies:** `restart_fresh` (M1 only, fresh snapshots:
  byte upper bound), `split` (frozen M2: stale S_0; reported as today's behaviour), `split_va` (v0). 3 reps:
  2 x 2 x 3 x 3 = **36 runs** (~2.5 h).
- **Measured per run:** per move k: whether O_k was bound (**fresh transition** = bound owner -> generation -> fresh
  snapshot -> handoff), snapshot capture time, manifest wait, fragment restoration time, bind time (assembly + H2D +
  bind); bound-Sink digest vs intended snapshot; PSNR at the final owner after bind (first crossing, sustained 10
  calls, median of the last 10 calls); three reuse quantities for the final snapshot S_K: **content reuse potential**
  = |{f : S_K.sha256[f] == S_{K-1}.sha256[f]}| / 412 (hash-table diff); **available verified reuse** = |{f : some node
  other than the final owner and the capturing owner holds f verified with hash S_K.sha256[f] at the final move's
  plan time}| / 412; **realized reuse** = fragments of S_K that the final owner verified from a node other than the
  capturing owner (or already held) / 412; **source bytes** = bytes sent by the capturing owner of S_K / Sink (A for
  S_0); **aggregate network bytes** = all fragment bytes on all links / Sink; discarded bytes (Phase 1 definition (a))
  and **invalidated bytes** (verified fragments whose hash no longer matches the active snapshot) separately.
- **Exposure criterion (fixed now):** a cell's freshness-related hypotheses (H1a's fresh binds, H2, H3) are judged only
  if, in every valid rep of `split_va`, at least one fresh transition occurred (an owner bound, generated and was then
  left, producing S_k != S_{k-1} by at least one fragment); a cell without it is **NOT EVALUABLE (no fresh transition)**
  for those hypotheses, and the fact is reported. Recorded prediction: at rho = 1 (T_m 14.05 s) the first owner's
  bind-ready at 1 Gbps is ~15.1-15.5 s (ExpD G3, R rho 1: binds after the owner is left), so the **rho = 1 cells may
  not exercise the fresh path** and would be NOT EVALUABLE; rho = 0.5 (T_m 28.1 s; R: B bound at 14.5 s and promoted
  at 18.6 s before leaving) is expected to exercise it in every run. The matrix is kept as instructed; a NOT EVALUABLE
  rho = 1 cell is itself the finding that the fresh path needs T_m > T_s.
- **Hypotheses (thresholds from the frozen R / W texts; decision rules fixed at the freeze):**

| | H1a snapshot integrity | H1b post-bind quality | H2 bytes | H3 latency |
|---|---|---|---|---|
| unit | every `split_va` run (12) | every `split_va` run | rho x workload cell (4) | rho x workload cell |
| metric | bound Sink digest == intended snapshot's digest (S_k of the last bound owner, else S_{k-1}) at every bind | PSNR >= 35 dB within the horizon at the final owner (**single crossing**, as W / ExpD; sustained 10-call recovery and the last-10-call median are reported and are not claimed as continuity) | source bytes of `split_va` vs `restart_fresh`, against the run's **available verified reuse** | bind-ready after the final move, `split_va` vs `restart_fresh`, decomposed |
| success | 100 % of binds (12 / 12 runs, every bound owner) | >= 11 of 12 runs. **This is a newly preregistered, stricter threshold** (the frozen W rule's 80 % would be 10 of 12); chosen because the workload diversity here is two clips | source bytes(`split_va`) <= source bytes(`restart_fresh`) - 0.9 x R_avail x 1 Sink, where R_avail = the median available verified reuse of the cell's `split_va` runs (measured per run, not a constant), **and** aggregate network bytes(`split_va`) <= aggregate(`restart_fresh`) + 0.05. Content reuse potential and realized reuse are reported next to it (realized <= available <= potential is a consistency check) | bind-ready(`split_va`) <= bind-ready(`restart_fresh`) + 1.0 s |
| failure | any bind whose digest differs from the intended snapshot | <= 10 of 12 | either clause | > 1.0 s |
| NOT EVALUABLE | < 12 valid runs | - | < 3 valid reps of either policy in a cell; exposure criterion not met | as H2; censoring per `followup_common.md` section 3 |

  H1a and H1b are separate: a quality failure with H1a passing is a property of restoring a fresh Sink into a node whose
  recent KV and VAE state are reconstructed (I5 scope), not an integrity fault; an integrity failure is a harness bug
  regardless of PSNR. **H2's denominator** is one Sink (1,725,236,640 B); "source bytes" counts only the capturing
  owner of the active snapshot (holders' forwarded bytes are counted in aggregate network bytes, never in source
  bytes); available verified reuse, not hash equality, is the basis because an identical fragment helps only if a
  reachable holder still has it verified; the 0.9 factor allows fragments in flight at the move. **H3's
  decomposition** (snapshot capture + manifest wait + fragment restoration + bind incl. assembly) is reported for every
  move; the threshold applies to the total after the final move.
- **Descriptive, reported next to the verdicts:** `split` (stale) in every cell: its digest matches S_0 (correct for
  what it restores), its PSNR after bind, its bytes; the measured dirty fraction per move against the Task B prediction
  (dog ~0.21 after 25 calls, ~0.36 after 50; butterfly ~0.34 / ~0.50); the 4 MiB-vs-block amplification per move.
- **Recorded predictions:** H1a supported (by construction, the test is of the implementation); H1b uncertain for
  butterfly (W2: it crossed 35 dB but did not sustain at 1 Gbps); exposure: rho 0.5 cells exercise the fresh path,
  rho 1 cells may not (NOT EVALUABLE); H2 at rho 0.5: potential ~0.64 (dog) / ~0.50 (butterfly) after ~50 calls,
  available reuse lower (the previous owner B is the only holder of S_1-valid fragments besides the capturing owner C
  at the move to D, and B holds only what it received), so the saving is bounded by what B holds and is valid;
  H3 uncertain: the manifest wait (~1 s) and the assembly (~0.3 s) are paid where `restart_fresh` starts sending at
  once, while holder forwarding in parallel may recover it.

## 7. GO / NO-GO (fixed before any run)

- **GO (adopt v0 as the M2 extension for the paper):** H1a supported, H1b supported, and H2 and H3 each supported in
  every **evaluable** cell with at least two evaluable cells (if only the rho 0.5 cells are evaluable, GO is stated for
  the T_m > T_s regime only).
- **CONDITIONAL (keep v0 as a correctness fix only):** H1a supported and H1b supported, but H2 or H3 fails in an
  evaluable cell: the paper states that fresh snapshots are required for correctness at rho <= 1 and that the byte /
  latency benefit of hash reuse is limited by realignment churn and holder availability (Task B numbers, measured
  available reuse), with v0 kept as the mechanism and the frozen M2 reported as the rho >= 2 special case.
- **NO-GO:** any H1a failure after re-run of the affected runs (implementation fault), or H1b <= 10 of 12 with H1a
  passing (fresh-but-changing Sinks do not restore continuity on these workloads): keep the frozen M2, state the stable-
  version assumption and the rho <= 1 limitation explicitly.

## 8. Key technical challenges (for the implementation step)

1. The capturing owner serves two buffers for a short time (old `sink_buf` to in-flight flows, new S_k): buffer
   lifetime tied to flow ends (I3 / I4).
2. Manifest updates mid-run reach nodes asynchronously; flows started under the old manifest must be cancelled before
   the new plan starts, and a FRAG with a hash equal to the new manifest's entry must still be accepted (I1).
3. The orchestrator's holder bookkeeping changes from "received under this version" to "hash-valid for the active
   manifest"; every accounting metric that reads `holders` (retained / reused / x) must be reinterpreted per snapshot.
4. The `late` mechanism (fragments in flight to a holder at the move) must carry the hash so a late-landing fragment of
   an old snapshot is not forwarded if its hash no longer matches.
5. Reporting discarded bytes per snapshot (a fragment of S_{k-1} that became dirty is not "discarded work" in the Phase
   1 sense; it is reported separately as *invalidated* bytes).

Smallest viable evaluation: the 36-run matrix above; a loopback version (fake nodes, dry promotions injected at known
calls to make S_k differ from S_{k-1} by a known fragment set) tests I1-I7 before any GPU run.

## Amendment 1 (2026-10-20, before implementation and before any run; frozen text above unchanged)

**I3 / I4 realization.** The frozen text realizes buffer immutability with one immutable `bytes` object per fragment
and a contiguous assembly at bind (~0.3 s). The implementation realizes the same guarantees without the assembly and
without touching the frozen policies' bind path:
- every outgoing flow binds its **manifest and buffer object at flow start** (today's `_sender` already does: `man`,
  `memoryview(sink_buf)` are taken once); a fresh snapshot installs a **new** buffer object, so flows started before
  the capture keep sending from the old object (pinned by reference until the flow ends; never written again);
- within one buffer object, a fragment is **copied under the node lock into a private `bytes` immediately before it is
  sent**, and a verified receipt replaces a fragment's bytes **in place under the same lock**; a sender therefore never
  observes a torn or changed fragment (I3), and a newer receipt cannot mutate bytes a send is using (I4);
- cost: one 4 MiB memcpy per sent fragment (~1 ms; the 1 Gbps fragment time is 34 ms), applied to every policy in the
  36-run matrix alike; no bind-time assembly.
Guarantees, invariants and hypotheses are unchanged; this is the engineering form of I3 / I4.
