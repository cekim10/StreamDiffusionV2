# E7: retained-Sink reuse across A -> B -> A (feasibility probe; plan fixed before the run, 2026-10-28)

**Question.** Can A reuse the Sink it held at the first migration when the session comes back from B, instead of
receiving a fresh 1.73 GB Sink base? What information brings that old Sink exactly to B's current Sink, and at what
cost?

**Method.** Offline reconstruction in one process on one GPU (`tools/eval/m2_reuse_probe.py`). This is not a
protocol: a full repeated-migration protocol would need substantial node and orchestrator changes, which the request
allows to defer. Workload dog s1, as in E5: base call c0 = 31, first migration at M1 = 64, B generating for a fixed
interval of 60 calls up to M2 = 124.

1. **A** generates to M1 and logs calls c0 .. M1 - 1 (E5's log: inputs, forced decisions, exact refresh patches).
2. **A's retained snapshot** is a host-memory copy of A's Sink K / V and positions at the M1 boundary: a defined
   snapshot, not a live buffer.
3. **B** is built as E5's destination: the ring at c0 with the recent slots zeroed, then log replay with patches. B's
   Sink digest must equal A's at M1. The cutover is E5's: in-flight state and metadata from A, the replayed ring kept,
   refresh on.
4. **B** generates calls M1 .. M2 - 1. Every Sink event is recorded per call:
   - realignment shifts of unwritten Sink slots, with their RoPE delta;
   - refresh writes, with their exact K / V.
5. **Reconstructions from the retained Sink.** Positions at M2 count as metadata in all of them.

| strategy | content |
|---|---|
| ordered | every event in call order |
| current_values | refreshed entries take B's values at M2; the others take each recorded shift in order |
| summed_shift | as current_values, but one shift by the sum of the deltas |
| last_written | last written value without the shifts that followed it |
| patches_only | no shifts |

   Each is compared with B's Sink at M2 per block (bitwise) and with the existing Sink digest.

**Measured:**
- Sink digest equality and block equality per strategy.
- Update bytes per strategy, against the fresh Sink base.
- GPU apply time.
- Host-to-GPU time of the retained Sink.
- The interval's refresh writes, distinct refreshed entries, shift events and calls.
- B's per-call tracking cost.
- Retained bytes.

**Estimated, not measured:**
- Transfer times at 1 Gbps, computed from bytes.
- Destination readiness time and preparation time, computed from E5's measured timeline (base transfer, catch-up,
  cutover).
- The interruption, which reuse does not change by construction.

**Reading.**
- Exact reuse is feasible if at least one strategy gives digest equality and 180 / 180 equal blocks.
- The cheapest such strategy defines the update cost.
- Strategies that fail identify the information that cannot be dropped.
