# A -> B -> C mobility: sink policy x mobility interval (1000 Mbps, sink 1645 MB, link time T_s = 13.8 s, S = 547 ms/chunk)

Times in seconds after the A->B handoff. ready_C = true sink bound at C (continuity restored at the final edge); ready_after_move = ready_C minus the B->C move time. wasted = sink bytes delivered to an edge that execution had already left (restart). PSNR vs the uninterrupted baseline: B phase (before the move), C gap (move -> bind), C after bind+8, last 8 calls.

| policy | T_m (s) | rho = T_s/T_m | moved at | ready_B | ready_C | ready_after_move | A->B MB | A->C MB | B->C MB | wasted MB | total MB | PSNR B phase | PSNR C gap | PSNR C bind+8.. | PSNR last 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| direct | 1 | 13.8 | 2.3 | - | 18.2 | 15.9 | 0 | 1645 | 0 | 0 | 1650 | 16.3 | 16.5 | 43.7 | 44.6 |
| relay | 1 | 13.8 | 2.2 | - | 32.0 | 29.8 | 1645 | 0 | 1645 | 0 | 3296 | 16.3 | 16.7 | 39.9 | 40.4 |
| restart | 1 | 13.8 | 2.3 | - | 21.0 | 18.8 | 274 | 1645 | 0 | 274 | 1925 | 16.3 | 16.6 | 42.7 | 43.7 |
| direct | 2 | 6.9 | 3.5 | - | 18.0 | 14.5 | 0 | 1645 | 0 | 0 | 1650 | 16.1 | 16.7 | 43.7 | 44.5 |
| relay | 2 | 6.9 | 3.5 | - | 32.1 | 28.6 | 1645 | 0 | 1645 | 0 | 3296 | 16.1 | 16.7 | 40.0 | 40.4 |
| restart | 2 | 6.9 | 3.5 | - | 22.3 | 18.8 | 384 | 1645 | 0 | 384 | 2034 | 16.1 | 16.7 | 41.2 | 41.4 |
| direct | 4 | 3.5 | 5.3 | - | 18.0 | 12.7 | 0 | 1645 | 0 | 0 | 1650 | 16.4 | 16.6 | 43.7 | 44.5 |
| relay | 4 | 3.5 | 5.2 | - | 32.0 | 26.7 | 1645 | 0 | 1645 | 0 | 3296 | 16.4 | 16.7 | 39.9 | 40.4 |
| restart | 4 | 3.5 | 5.3 | - | 24.1 | 18.8 | 548 | 1645 | 0 | 548 | 2199 | 16.4 | 16.7 | 42.7 | 43.7 |
| direct | 8 | 1.7 | 9.5 | - | 18.1 | 8.5 | 0 | 1645 | 0 | 0 | 1650 | 16.6 | 16.5 | 43.7 | 44.7 |
| relay | 8 | 1.7 | 9.5 | - | 32.0 | 22.5 | 1645 | 0 | 1645 | 0 | 3296 | 16.6 | 16.7 | 39.9 | 40.4 |
| restart | 8 | 1.7 | 9.5 | - | 28.3 | 18.8 | 932 | 1645 | 0 | 932 | 2583 | 16.6 | 16.6 | 42.9 | 43.7 |
| direct | 16 | 0.9 | 17.5 | - | 18.1 | 0.6 | 0 | 1645 | 0 | 0 | 1650 | 16.7 | 14.7 | 41.2 | 42.2 |
| relay | 16 | 0.9 | 17.4 | - | 32.0 | 14.6 | 1645 | 0 | 1645 | 0 | 3296 | 16.7 | 16.7 | 39.9 | 40.4 |
| restart | 16 | 0.9 | 17.4 | - | 36.1 | 18.7 | 1645 | 1645 | 0 | 1645 | 3296 | 16.7 | 16.7 | 39.9 | 40.4 |

Reading guide: rho < 1 means the sink can reach B before execution leaves; rho > 1 means execution outruns its continuity state and the single-destination policies diverge: restart wastes what reached B, relay delays C by a second hop, direct (oracle) needs to know C in advance.
