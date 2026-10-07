# A -> B -> C mobility reading (results/state_migration/mobility, harness ba92b5b, 1 Gbps, sink 1.6 GB)

Effective sink time from the A->B handoff to bind-ready is ~16.6 s (13.8 s link + ~2.5 s serialization and fast path), so every T_m in {1..16} is rho > 1: execution left B before the sink could bind there (ready_B is empty in all 15 runs). The move itself costs ~1.4 s after T_m (handoff + chunk quantization).

| policy | ready_C after the move | wasted bytes | total traffic | continuity at C after bind |
|---|---|---|---|---|
| restart | **constant 18.8 s** for every T_m: each move restarts a full 1.6 GB transfer | grows with T_m: 274 / 384 / 548 / 932 / 1645 MB (= bandwidth x time spent streaming to B) | 1.9 -> 3.3 GB | 41-43 dB |
| relay | 29.8 -> 14.6 s as T_m grows; ready_C is pinned at **32 s = 2 T_s** regardless of when the move happens | 0 | 3.3 GB (two hops) | 40 dB |
| direct (oracle) | 15.9 -> 0.6 s; ready_C = 18 s absolute, independent of the move | 0 | 1.65 GB | 43.7 dB (41 at T_m=16 where the bind coincided with the move) |

## Observation
When mobility is faster than continuity-state transfer (rho > 1), execution outruns its continuity state and no single-destination policy is good on both axes:
- restart keeps the post-move latency fixed at T_s but pays bandwidth x T_m in wasted bytes and resets the clock at every move, so for T_m < T_s the stream can never become continuity-ready across repeated moves;
- relay never wastes bytes but delays readiness at the final edge by one full extra hop (2 T_s), and would add a hop per move;
- direct achieves the lower bound on both axes but requires knowing the next edge when the transfer starts.
The trade-off is continuity-ready latency vs network traffic, and the gap between the naive policies and the oracle is the room for a continuity router (direct when the next edge is predictable, relay or redirect of the in-flight remainder otherwise).

## Also visible
- B phase and C gap sit at 16-17 dB (zero sink, refresh frozen): the gap-quality problem is unchanged by topology and still needs the placeholder.
- restart at T_m=16 streamed all of B's 1.6 GB before the move flag was observed and then another 1.6 GB to C: the worst case of "the sink follows execution from the source".

## Next
1. A -> B -> C -> D with T_m = 2 s to show execution-state lag L(t) growing under restart/relay.
2. T_m in {24, 32} to cover rho < 1 and confirm the policies converge there.
3. Then the router: redirect the in-flight remainder to the new edge (no restart, no second full hop) as the first non-oracle mechanism.
