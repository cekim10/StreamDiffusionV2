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

**Fig. 14(b1) fig14b1_gpu.** Peak allocated GPU memory of the source and the destination of a single migration
(median of 3 runs). Dashed: the source while serving without migration state (19.7 GiB). The rest is the prototype
holding whole-session GPU copies: the transfer / receive snapshot (6.2 GiB) and, at the destination, a replay clone
(1.6 GiB).

**Fig. 14(b2) fig14b2_host.** Increase in process RSS over the run (peak minus first sample, GiB). It is the whole
process's increase, not an OTTER-specific overhead. The retained Sink (1.6 GiB, measured bytes) is part of the
source's increase and drawn inside its bar, not added to it.

**Fig. 14(c) fig14c_cluster.** Four-node chain with staging (A -> B -> C -> D): retained and staged Sink bytes held per
node at the run end (measured). Each former owner retains both a local Sink copy and a staged entry, resulting in
seven Sink-sized copies (11.2 GiB) across the four-node chain. D, the final owner, keeps a staged copy while serving.
