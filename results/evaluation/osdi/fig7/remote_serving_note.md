# Remote serving during migration: what the Fig. 7 runs record (analysis of existing runs, 2026-11-04)

No new run. Source: the 40 frozen Fig. 7 runs (`expF7_{dog,bfly}`), `xb_delivery.delivery_metrics`. Medians of 5 reps.

## What the testbed does and does not measure

- "Delivered" = a chunk finished on its serving host (orchestrator delivery log). **The output stream is not
  transmitted to a client**, and input frames are read locally by each node. So the testbed measures *when and how fast*
  output is produced, not the user-perceived latency of a remotely served frame.
- Inter-host RTT is the LAN's (A-B median 0.26 ms, p95 1.4 ms). **WAN / radio latency is neither emulated nor measured**
  (already stated in the Fig. 7 protocol and caption).
- Recorded: remote stretch length, chunks served remotely, their content time, and the H.264 size of those chunks
  encoded live by the serving node (ESTIMATED bytes; not transmitted).

## Numbers (measured except the bitrate, which is estimated)

| input | method | remote serving (s) | chunks remote | remote rate (chunks / s) | local rate after TTFO | est. remote stream (Mbps, CRF 23) | max gap (s) | TTFO-local (s) |
|---|---|---|---|---|---|---|---|---|
| dog | Full | 0 | 0 | - | 1.68 | - | 54.2 | 54.2 |
| dog | Llumnix | 162.9 | 246 | 1.51 | 1.68 | 0.58 | 50.9 | 213.8 |
| dog | SLLM | 18.4 | 30 | 1.63 | 1.67 | 0.62 | 18.5 | 36.9 |
| dog | OTTER | 21.6 | 33 | 1.53 | 1.67 | 0.59 | 1.63 | 23.3 |
| bfly | Full | 0 | 0 | - | 1.68 | - | 54.2 | 54.2 |
| bfly | Llumnix | 166.6 | 252 | 1.51 | 1.68 | 0.50 | 52.6 | 219.2 |
| bfly | SLLM | 18.4 | 30 | 1.63 | 1.67 | 0.54 | 18.3 | 36.8 |
| bfly | OTTER | 23.1 | 35 | 1.51 | 1.67 | 0.51 | 1.59 | 24.6 |

## Reading

1. Remote serving is not specific to OTTER: every live method (Llumnix, SLLM, OTTER) serves from the source while it
   migrates; only Full avoids it, by stopping for 54 s. OTTER's remote stretch (22-23 s) is 3-5 s longer than SLLM's
   and 7x shorter than Llumnix's.
2. While migrating, the source serves at 1.51-1.53 chunks / s, 9 % below the local rate (1.67-1.68); SLLM's source
   1.63 (it stops earlier). This throughput cost is measured.
3. The remote stream is small (about 0.5-0.6 Mbps at CRF 23), so carrying it does not compete with the state transfer
   in a meaningful way (estimate).
4. Not measured: the added per-frame latency of remote serving. Under the testbed's model it is one inter-edge round
   trip (input up to the source, output back), for every live method alike, during its remote stretch. It shifts
   frame latency; it does not create a delivery gap. This is a stated limitation, not a result.
