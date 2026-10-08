# Phase 0: network calibration (elves-01..04, 2026-10-07)

Transport: plain TCP with TCP_MAXSEG=1400 (effective MSS 1388) and TCP_NODELAY on every socket; sender-side token bucket for shaping; no RDMA. Orchestration through per-host agents over the same MSS-capped TCP, because inter-host ssh fails at key exchange on this path (NIC MTU 9200, path drops >1500-byte frames, no management network; /home is local ZFS per host). Raw records: results/evaluation/network_calibration/<run>/<pattern>/rep<k>/ on elves-01 (pulled from each host through the agents); aggregate: network_calibration.csv, network_calibration_summary.csv.

Runs: mss=1400_bytes=1073741824_20261007-180758 (patterns 1-5; p3/p4 without a sender barrier) and ..._181243 (patterns 3-5 with a common start barrier so concurrent flows overlap). 1 GiB per flow, 5 reps.

| pattern | flows | per-flow Gbps (median) | aggregate Gbps |
|---|---|---|---|
| p1 A->D | 1 | 9.23 | 9.23 |
| p2 A->B | 1 | 9.30 | 9.30 |
| p3 A->B & A->C (source egress shared) | 2 | 4.70 / 4.70 | 9.40 |
| p4 A->D & B->D (destination ingress shared) | 2 | 4.69 / 4.69 | 9.38 |
| p5 A->D & B->D & C->D | 3 | 3.13 / 3.13 / 3.13 | 9.40 |

Findings:
- One 10 GbE NIC per host bounds both egress and ingress at ~9.4 Gbps application throughput; concurrent flows share it almost exactly fairly (spread < 1%).
- Destination ingress does not scale with the number of senders: this testbed is the "1x shared ingress" case of the simulation (results/state_migration/ingress_notes.md). Any latency gain of progress-aware routing here cannot come from bandwidth aggregation; its measurable benefits are wasted-traffic and source-uplink reduction.
- Expected durable-state transfer time at native bandwidth: 1.6 GB sink ~ 1.5 s link time (+ serialization), measured in Phase 1.
- Pending: the MSS=0 control run (kernel default MSS) to document whether uncapped TCP stalls on this path.
These numbers are recorded for interpretation only; the routing mechanism is unchanged.
