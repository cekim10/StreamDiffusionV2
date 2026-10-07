# Repeated mobility reading (results/state_migration/mobility, harness d250703, 1 Gbps per link, sink 1.6 GB, T_s link = 13.8 s, bind-ready ~16.6 s)

All five policies now match the offline simulation (tools/test_sink_router.py) within serialization overhead.

## A -> B -> C -> D, T_m = 2 s (rho ~ 7 by link time): execution outruns its continuity state
| policy | D ready (s) | after last move (s) | traffic | wasted | lag mean / max | continuity at D |
|---|---|---|---|---|---|---|
| direct (oracle) | 17.7 | 12.6 | 1.65 GB | 0 | 0.53 / 3 | 43.9 dB |
| **split** | **17.7** | **12.7** | 2.4 GB | 0 | 0.53 / 3 | 43.9 dB |
| relay_pipe (pipelined chain) | 19.3 | 14.4 | 4.9 GB | 0 | 0.60 / 3 | 43.9 dB |
| restart | 23.8 | 18.7 | 2.2 GB | 548 MB | 0.76 / 3 | 41.3 dB |
| relay (store-and-forward chain) | 45.9 | 40.8 | 4.9 GB | 0 | 1.73 / 3 | 40.7 dB |

- Naive relay accumulates one full sink time per hop (45.9 s ~ 3 T_s): continuity lag stays at 2-3 hops for most of the run.
- Restart resets the clock at every move (always T_s after the last move) and wastes 548 MB over two moves (bandwidth x time spent streaming to edges that were then abandoned).
- Pipelining the chain fixes latency (19.3 s) but triples traffic (4.9 GB).
- Split (keep every delivered segment moving toward the current edge, send only the undelivered remainder from the source) reaches the oracle's readiness exactly (17.7 s) with zero waste and 2.4 GB of traffic (the forwarded prefixes are the only overhead). The source's bytes: 384 MB to B, 165 MB to C, 1,097 MB to D; the rest reached D via B and C.
- Caveat: split's new edge receives over up to three links at once (A->D, B->D, C->D); a shared-ingress variant is needed before claiming the latency result generally.

## A -> B -> C, T_m = 24 / 32 s (rho < 1 by link time): the current edge is continuous, the next edge is not
- B binds at 18.2 s in every non-oracle policy: with rho < 1 the edge the user is on gets its continuity before the user leaves.
- The next edge still needs a transfer: after the move, relay (B forwards) is ready in 14.1 s, restart (A resends) in 18.1 s with the full 1.6 GB wasted, direct is ready at the move (the sink was waiting there).
- So rho < 1 does not make the policies converge at the destination; it only guarantees continuity at the edge being left. Readiness of the next edge is bounded below by one link time unless the sink was pre-positioned.

## Observation for the paper
When mobility is faster than continuity-state transfer, single-destination policies pay either in wasted traffic (restart), accumulating lag (relay) or multiplied traffic (pipelined relay). Treating transfer progress as routable state (split) removes the trade-off: delivered segments follow execution from wherever they are, the source sends only what has not left, and readiness equals the oracle's at modest extra traffic. The remaining questions are the shared-ingress case, predictive pre-positioning (direct without the oracle), and fan-out (one source, several simultaneous destinations).
