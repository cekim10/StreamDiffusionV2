# Prototype run 2 (results/state_migration/proto, harness e4368ec): execution handoff decoupled from bulk state transfer

Two processes on one host (GPU 0 source, GPU 1 destination), state only over a TCP socket with a sender-side token bucket. 1.3B, k=2, 480x832, M=30, 80 post-migration calls, destination service time S = 547 ms/chunk. Full state at k=2 = 6.2 GB; sink = 1.6 GB; fast path (in-flight row + ring/session metadata) = 2.7 MB.

## Headline
| policy | first output (s) at 500 / 1000 / 2000 / 5000 / 10000 Mbps | continuity after settling |
|---|---|---|
| full (6.2 GB before resume) | 109.7 / 57.2 / 31.3 / 15.6 / 10.4 | 99 dB (identical) |
| cold (nothing) | 1.07 at every bandwidth | ~22 dB (different stream) |
| replay (42 MB seeds + 5 s replay) | 6.4 / 6.0 / 5.9 / 5.7 / 5.7 | 30 dB |
| ours (2.7 MB now, 1.6 GB sink in background) | 1.43 / 1.56 / 1.54 / 1.51 / 1.44 | 44-46 dB after the sink binds at 29 / 15 / 8 / 4 / 2.8 s |

T_handoff for `ours` is ~1.5 s at every bandwidth (stall over S: 0.9-1.0 s, within 0.4 s of a cold restart) while `full` scales as 6.2 GB / BW. The sink arrives 2.8-29 s later, binds atomically at the next chunk boundary (call 34-82), and the stream rejoins the uninterrupted baseline at 43.6-45.5 dB; 39.7 dB at 500 Mbps where the bind lands after the t_refresh realign and only 28 calls remain in the window. No output hiccups were attributed to the background transfer (0-1 per run, same as cold).

## Gap and the refresh variant
- During the wait `ours` (refresh frozen, zero sink) renders 16.1-16.7 dB, below cold restart's 19.2 dB. `ours_refresh` (adaptive refresh left on) renders 17.3-18.4 dB in the gap and rejoins identically when the sink binds before the realign at call 48 (2-10 Gbps: 43.8-45.6 dB), but only 30 dB when it binds after (500-1000 Mbps) because the refresh-on bind writes the true sink's positions verbatim without re-rotating for the realign. Fixable the same way as `ours`; not yet done.
- The gap is where a placeholder belongs; the mechanism-run numbers (local placeholder +1-3 dB over zero) suggest it will land near cold-restart quality during the wait while keeping the rejoin.

## Costs that are real and now measured
- Serializing 6.2 GB through host memory costs ~5 s on top of link time at 10 Gbps (one D2H and one H2D copy); a 1.6 GB sink costs ~1.3 s on top of its 1.3 s link time.
- Replay reproduces 30 dB at 5.7-6.4 s regardless of bandwidth: its cost is compute and session age, not bytes.

## Caveats
- Same host, loopback TCP with application-level shaping: bandwidth is modeled, RTT and loss are not.
- One video, one seed, k=2, L40S cadence (not 16 FPS real time). The two-node and real-time versions are the next steps, then repeated mobility (A -> B -> C while the sink is still in flight) to expose the routing problem.
