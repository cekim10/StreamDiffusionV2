# Version-aware Continuity Wavefront v0 (M2 extension): design and preregistration DRAFT (2026-10-20; not frozen; not implemented; nothing run)

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
   holder's `sink_buf` holds at most one byte image per fragment id (the newest verified), and an id may be overwritten
   only when no active flow still serves the old bytes (section 2.4).

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

`ABSENT -> RECEIVING -> VERIFIED(h)` where h is the SHA-256 of the bytes in `sink_buf[f]`; `VERIFIED(h)` is *valid for
the active snapshot* iff `h == S_active.sha256[f]`, else *stale* (kept, reusable if a later snapshot has the same hash,
which happens when a block changes back; otherwise it is overwritten by the next valid receipt). Transitions:
- `recv(f, bytes, h')`: if `h' != S_active.sha256[f]` -> reject (not a version mismatch any more: a **content**
  mismatch; logged `fragment_rejected_hash`); if `f` is VERIFIED(h) with h == h' -> duplicate (scratch, unchanged);
  if `f` is VERIFIED(h) stale and **no active outgoing flow is serving f** -> overwrite, VERIFIED(h'); if an active flow
  serves f -> receive into scratch and retry after the flow ends (section 2.4).
- `drop` (M1 only, as today).

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
- **I3 (immutable transfer view):** every byte ever sent comes from a host buffer that is never modified after its
  capture (S_k buffers are write-once; `sink_buf` writes only replace a stale id's bytes under the rule of I4).
- **I4 (safe replacement):** a holder overwrites `sink_buf[f]` only if (a) the new bytes verify against S_active and
  (b) no active outgoing flow of this node has f in its remaining queue or in flight; otherwise the receipt is parked
  (scratch) and applied when the flow ends. With one active snapshot, (b) can only arise during the cancellation window
  of a superseded flow (I1), which is bounded by one fragment's transmission.
- **I5 (freshness):** the Sink bound by O_{k+1} equals the Sink O_k was generating on at the handoff boundary (S_k),
  byte for byte, when O_k was bound; equals S_{k-1} otherwise. (This is what the frozen harness violates at rho <= 1:
  it binds S_0 at every owner.)
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
| `mobility_node.py` `_recv_frag` | replace the `sink_version` equality test by `hdr["sha256"] == man["frags"][fid]["sha256"]` (content check against the active manifest); stale-overwrite rule I4 (parked receipts, applied at `flow_end`) |
| `mobility_node.py` `cmd_manifest` | accept a **manifest update** mid-run: keep `sink_buf`, recompute `have` = ids whose stored hash equals the new manifest's (hashes of stored fragments are kept in `frag_ok` as the SHA-256, not a bool), report `(id, sha256)` holdings |
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
- **Host memory:** the capturing owner holds two Sink-sized buffers briefly (old `sink_buf` until its flows end, new
  S_k): peak 2 x 1.6 GB; every other node holds one `sink_buf` (as today) plus scratch for parked receipts (<= a few
  fragments). Bound: **<= 2 Sinks per node** (3.2 GB host), no change on the GPU (the live ring is the Sink).
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
- **Measured per run:** per move k: whether O_k was bound, dirty fraction of S_k vs S_{k-1} (hash table diff), snapshot
  capture time, manifest wait, fragment restoration time, bind time; bound-Sink digest vs intended snapshot; PSNR at
  the final owner after bind (first crossing, sustained 10 calls, median of the last 10 calls); **logical reuse** at the
  final owner = fragments verified from holders / 412; **source bytes** = bytes sent by the capturing owner of the
  final snapshot (role-based: A for S_0, O_k for S_k) / Sink; **aggregate network bytes** = all fragment bytes on all
  links / Sink; discarded bytes (Phase 1 definition (a)).
- **Hypotheses (thresholds from the frozen R / W texts; decision rules fixed at the freeze):**

| | H1a snapshot integrity | H1b post-bind quality | H2 bytes | H3 latency |
|---|---|---|---|---|
| unit | every `split_va` run (12) | every `split_va` run | rho x workload cell (4) | rho x workload cell |
| metric | bound Sink digest == intended snapshot's digest (S_k of the last bound owner, else S_{k-1}) at every bind | PSNR >= 35 dB within the horizon at the final owner (single crossing; sustained reported) | source bytes of `split_va` vs `restart_fresh`; logical reuse | bind-ready after the final move, `split_va` vs `restart_fresh`, decomposed |
| success | 100 % of binds (12 / 12 runs, every bound owner) | >= 11 of 12 runs (the frozen W rule's 80 % over 12 units rounds up to 10; 11 required here because the workload is fixed) | source bytes(`split_va`) <= source bytes(`restart_fresh`) - 0.9 x reuse_measured x 1 Sink, with reuse_measured = the hash-table reuse of the run (not a constant), **and** aggregate network bytes(`split_va`) <= aggregate(`restart_fresh`) + 0.05 | bind-ready(`split_va`) <= bind-ready(`restart_fresh`) + 1.0 s |
| failure | any bind whose digest differs from the intended snapshot | <= 10 of 12 | either clause | > 1.0 s |
| NOT EVALUABLE | < 12 valid runs | - | < 3 valid reps of either policy in a cell | as H2; censoring per `followup_common.md` section 3 |

  H1a and H1b are separate: a quality failure with H1a passing is a property of restoring a fresh-but-changing Sink,
  not an integrity fault; an integrity failure is a harness bug regardless of PSNR. **H2's denominator** is one Sink
  (1,725,236,640 B); "source bytes" counts only the capturing owner of the active snapshot (holders' forwarded bytes are
  counted in aggregate network bytes, never in source bytes); the 0.9 factor allows fragments in flight at the move.
  **H3's decomposition** (snapshot capture + manifest wait + restoration + bind) is reported for every move; the
  threshold applies to the total after the final move.
- **Descriptive, reported next to the verdicts:** `split` (stale) in every cell: its digest matches S_0 (correct for
  what it restores), its PSNR after bind, its bytes; the measured dirty fraction per move against the Task B prediction
  (dog ~0.21 after 25 calls, ~0.36 after 50; butterfly ~0.34 / ~0.50); the 4 MiB-vs-block amplification per move.
- **Recorded predictions:** H1a supported (by construction, the test is of the implementation); H1b uncertain for
  butterfly (W2: it crossed 35 dB but did not sustain at 1 Gbps); H2 supported at rho 1 (reuse ~0.7-0.8), borderline at
  rho 0.5 on butterfly (reuse ~0.5); H3 uncertain: the manifest wait (~1 s) is paid where `restart_fresh` starts sending
  at once, while holder forwarding in parallel should recover it at rho 1.

## 7. GO / NO-GO (fixed before any run)

- **GO (adopt v0 as the M2 extension for the paper):** H1a supported, H2 supported in >= 3 of 4 cells, H3 supported in
  >= 3 of 4 cells, H1b supported.
- **CONDITIONAL (keep v0 as a correctness fix only):** H1a supported and H1b supported, but H2 or H3 fails in >= 2
  cells: the paper states that fresh snapshots are required for correctness at rho <= 1 and that the byte / latency
  benefit of hash reuse is limited by realignment churn (Task B numbers), with v0 kept as the mechanism and the frozen
  M2 reported as the rho >= 2 special case.
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
