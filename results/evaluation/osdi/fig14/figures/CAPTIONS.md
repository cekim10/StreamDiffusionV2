# Fig. 14 captions (draft; measured on 4 x L40S, commit ccc6c06)

**Fig. 14(a) fig14a_overhead.** Per-call time increase (%). Each group has its own baseline. Tracking: OTTER's
metadata tracking inside upstream's native loop vs the same loop without it (same host, 5 reps). Transfer: the
source's per-call time while a migration transfers state vs its own uninterrupted reference session (10 runs).
Staging: the owner's per-call time while a staging flow is active vs outside those intervals (6 runs).
Low-refresh solid, High-refresh hatched; medians printed.
Text (not in the figure): OTTER's metadata tracking adds less than 0.1 % per call (0.06-0.09 %). The integrated
serving path is 5.3-5.6 % slower than native inference, while the harness without OTTER already incurs 4.6-4.7 %.
These measurements suggest that most of the integrated slowdown is associated with the serving harness rather than
OTTER's metadata tracking; the two were measured on different hosts, so the split is not exact.

**Fig. 14(b1) fig14b1_gpu.** Bars: peak allocated GPU memory of the source and the destination of a single migration
(median of 3 runs, GiB). Dashed: the steady-state serving allocation without migration state (19.7 GiB). The source
peak includes a full-state GPU snapshot (6.2 GiB, held during the first transfer round); the destination peak
includes the receive buffer (6.2 GiB) and the replay clone (1.6 GiB), which the prototype holds until the session
ends.

**Fig. 14(b2) fig14b2_host.** Process RSS increase relative to the first sample (peak minus first sample, GiB). It is
the whole process's increase, not an OTTER-specific overhead. The retained Sink (1.6 GiB, measured bytes) is part of
the source's increase and drawn inside its bar, not added to it; the rest of the source's increase (about 3.4 GiB) is
not attributed.

**Fig. 14(c) fig14c_cluster.** Four-node chain with staging (A -> B -> C -> D): retained and staged Sink bytes held per
node at the run end (measured). Each former owner retains both a local Sink copy and a staged entry, resulting in
seven Sink-sized copies (11.2 GiB) across the four-node chain. D, the final owner, keeps a staged copy while serving.

## Text that must appear in the paper (user 2026-11-03)

- Intermediate owners reach 33.6-35.8 GiB of GPU allocation when initiating another migration, primarily due to
  overlapping receive and outbound state snapshots (measured; L40S 45 GiB).
- In the four-node chain, the prototype holds seven Sink-sized copies (11.2 GiB) at the end: each former owner keeps
  its retained copy and a staged entry of the same version, and the final owner keeps a staged copy.
- These costs come from buffer lifetimes in the prototype (whole-session snapshots, a replay clone, duplicated
  retained / staged copies) and are reported as measured; no reduced number is claimed for an optimized
  implementation.
- The cluster simulation's memory results assume one copy per site and session with owner cleanup and LRU eviction
  ([A11]); the A11 sensitivity (osdi/fig_cluster/a11_sensitivity_protocol.md) reports the implementation-like case.

## DRAFT 2 (user 2026-11-03: two panels; `figures/v2/`, `tools/eval/plot_fig14_v2.py`; existing data only)

**Fig. 14(a) fig14a_dots.** Per-call slowdown (%) of OTTER's operations (vertical dot plot on the Fig. 11 canvas); Low-refresh filled, High-refresh open; each
row has its own baseline. Tracking: metadata tracking inside upstream's native loop vs the same loop without it
(same host, 5 reps). Transfer: the source while a migration transfers state vs its own uninterrupted reference
(10 runs). Staging: the owner while a staging flow is active vs outside those intervals (6 runs). Medians.

**Fig. 14(b) fig14b_timeline.** GPU allocated memory on the four nodes of one four-node chain with staging
(A -> B -> C -> D; Low-refresh; the first of two runs, not selected), sampled at 2 Hz, so transients shorter than
0.5 s can be missed. Shaded: each migration from its start to its cutover. Before a hop the source takes a full-state
snapshot (+6.2 GiB); warm destinations hold a receive buffer of the same size; after a cutover the new owner keeps the
receive buffer and a replay clone (27.4 GiB); an intermediate owner that starts the next migration adds its outbound
snapshot (33.6 GiB; 33.6-35.8 GiB over the 8 intermediate-owner instances of the 4 chain runs). The source returns to
its serving allocation (19.7 GiB). Measured.

Text: integrated 5.3-5.6 % vs native, harness without OTTER 4.6-4.7 % (cross-host); host RSS increase source
+5.0-5.2 GiB, destination +1.7-2.0 GiB; retained Sink 1.61 GiB per former owner; chain retained / staged 7 x Sink
(11.25 GiB); E9's [A11] and its sensitivity.
