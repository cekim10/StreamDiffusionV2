# Phase 1: physical single handoff (elves-01 -> elves-02), sweep v3

Commit of the harness: `32acfb9` (tools/proto_handoff.py, tools/eval/run_single_handoff.sh). Raw runs: `results/evaluation/single_handoff/policy=*` (3 reps x {full, cold, replay, ours} x {250, 500, 1000, 2500, 5000, native} Mbps, plus `repeat` once per rep). Earlier sweeps are kept under `_v1_inline_checksum/` and `_v2_async_checksum/`; they are superseded by v3 and should not be quoted (see "Measurement artifacts" below).

Workload: original demo clip, seed 0, 480x832, k=2, migration at chunk M (identical across policies), 80 post-migration calls (window extended for `ours` at <=1000 Mbps so the sink can arrive). Transport: TCP with TCP_MAXSEG=1400 on every socket (path drops >1500 B frames), sender-side token-bucket shaping for the sub-native points, one 10 GbE NIC per host (native single-flow throughput 9.2-9.4 Gbps from Phase 0). Clocks: NTP-style offset estimate over the control socket; all cross-host times are converted to destination time.

## Headline (median of 3 reps; `fig6_table.md` has p25/p75)

| policy | bytes | first output, 250 Mbps | first output, native | Sink bound, 250 Mbps | Sink bound, native |
|---|---|---|---|---|---|
| SDV2-FullMigration | 6164 MB | 209.9 s | 7.85 s | 209.9 s | 7.85 s |
| SDV2-Restart | 0 | 1.07 s | 1.07 s | never | never |
| Replay (seeds + sink history, W=3) | 42 MB | 7.13 s | 5.77 s | never | never |
| Ours (in-flight + metadata first, sink in background, late bind) | 1648 MB | 0.74 s | 0.69 s | 57.4 s | 3.09 s |

- `ours` first output is 0.69-0.74 s at every bandwidth: the foreground fragment is 0.2 MB in-flight rows + ~2 MB metadata, so first output is dominated by one chunk of generation (0.54 s) plus resume bookkeeping. It is below Restart (1.07 s) because Restart pays the SDV2 cold-start path (VAE cache rebuild, first-chunk warm-up).
- FullMigration scales with bytes/bandwidth exactly as expected (6.16 GB: 209.9 s at 250 Mbps, 53.8 s at 1 Gbps, 7.85 s native). At native speed the per-rep spread (6.86-8.95 s) tracks link throughput (6.0-8.1 Gbps effective for the 6 components, with H2D copies between messages); restore after the last byte is 0.55-0.75 s.
- `continuity_ready_rel_s` (Fig. 6b, 'Sink bound') is the output time of the first chunk produced on the transferred Sink, i.e. sink arrival + verification + bind at the next chunk boundary. At native, the 1.65 GB sink lands at 2.08 s after migration start, is verified at 2.17 s (off the data path), binds at 2.54 s, and the first chunk on the bound Sink is out at 3.09 s. Rejoin to the original trajectory (first chunk >= 35 dB vs the uninterrupted run) takes 6 further calls at every bandwidth (7-8 at 250/500 Mbps), i.e. ~3.5 s more; mean PSNR from bind+8 onward is 39-45 dB, the same stream rather than a different valid stream (cold/replay stay at 22-30 dB and never reach 35 dB). Fig. 7 (results/evaluation/continuity/) shows the full timeline.
- Replay (42 MB) still needs 5.8-7.1 s because replaying W=3 chunks of history is compute, not bytes, and it never rejoins the original trajectory.

## Validation

- `validation failures: none` from aggregate_single_handoff.py over all 75 runs.
- `repeat` (same host, same seed, no transfer) and `full` both reproduce the uninterrupted execution bit-exactly (PSNR 99 = identical for every post-migration chunk), on every rep and bandwidth: cross-host determinism holds.
- Every transferred component carries a SHA-256 digest (per-tensor digests hashed in order; computed in parallel on both sides, compared at END). All digests matched in all runs; a missing digest now fails validation instead of being skipped.
- MSS 1400 recorded on both ends of every run (`mss_source`, `mss_dest`); bytes per component recorded per run (`summary.json`); NIC/CPU/GPU utilization sampled at 1 Hz (`network.csv`).
- Clock offset and min RTT recorded per run (`clock_offset_s`, `rtt_min_s`).

## Measurement artifacts fixed between sweeps (why v1/v2 are superseded)

1. v1: SHA-256 computed inline on the data path (sender and receiver) added ~8.5 s to FullMigration at native and ~2 s to sink arrival.
2. v2: hashing moved to a background thread, but the sender still joined the hash before sending the next component (effective 5 Gbps for FullMigration), and the receiver allocated a fresh 1.6 GB bytearray for the sink while generation was running. That allocation holds the GIL for hundreds of ms and showed up as one 1.2 s chunk right after resume, inflating `ours` first output to 1.4 s.
3. v3: double-buffered preallocated receive pool, per-tensor digests in a thread pool, all digests shipped once in END and verified after bind. `ours` first output returns to 0.69-0.74 s; FullMigration native drops to 7.85 s.

Lesson for the paper's methodology section: verification and buffer management must be kept off the transfer path or they masquerade as mechanism cost.

## Figure

`fig6_handoff_latency.{pdf,png}` (tools/eval/plot_fig6.py --native_mbps 9400): (a) time to first output vs bandwidth, (b) time to original trajectory vs bandwidth; median with p25-p75 band; log-log.
