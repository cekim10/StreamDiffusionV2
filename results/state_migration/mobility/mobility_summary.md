# Repeated mobility: sink routing policy x mobility interval x hops (1000 Mbps per link, sink <= 1645 MB, link time T_s = 13.8 s, S = 547 ms/chunk)

Times in seconds after the A->B handoff. moves = when execution left each edge. ready = when the true sink bound at each edge. ready_final_after_last_move = readiness at the final edge minus the last move time. wasted = segments stranded on edges execution had already left. total = all link traffic (A->edge real, edge->edge emulated at the same per-link bandwidth; split gives the new edge two independent ingress links). lag = hops between the execution edge and the last edge with a bound sink, averaged over calls.

| policy | hops | T_m | ingress | rho | moves at | ready | ready_final | after last move | traffic by link (MB) | wasted MB | total MB | lag mean / max | PSNR before final bind | PSNR final bind+8.. | PSNR last 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| direct | 3 | 2 | 1x | 6.9 | B->C 3.5, C->D 5.0 | D 17.8 | 17.8 | 12.7 | A->D 1645 | 0 | 1653 | 0.53 / 3 | 16.5 | 43.9 | 43.3 |
| relay_pipe | 3 | 2 | 1x | 6.9 | B->C 3.5, C->D 5.1 | D 19.4 | 19.4 | 14.3 | A->B 1645, B->C 1645, C->D 1645 | 0 | 4944 | 0.60 / 3 | 16.5 | 43.9 | 43.4 |
| restart | 3 | 2 | 1x | 6.9 | B->C 3.5, C->D 5.0 | D 23.8 | 23.8 | 18.7 | A->B 384, A->C 165, A->D 1645 | 548 | 2201 | 0.76 / 3 | 16.6 | 41.3 | 40.2 |
| split | 3 | 2 | 1x | 6.9 | B->C 3.5, C->D 4.9 | D 21.0 | 21.0 | 16.1 | A->B 384, B->C 165, A->C 110, C->D 219, B->D 274, A->D 1152 | 0 | 2311 | 0.67 / 3 | 16.5 | 42.9 | 42.5 |
| direct | 3 | 2 | 2x | 6.9 | B->C 3.5, C->D 5.0 | D 17.7 | 17.7 | 12.7 | A->D 1645 | 0 | 1653 | 0.53 / 3 | 16.5 | 43.9 | 43.3 |
| relay_pipe | 3 | 2 | 2x | 6.9 | B->C 3.4, C->D 5.0 | D 19.3 | 19.3 | 14.3 | A->B 1645, B->C 1645, C->D 1645 | 0 | 4944 | 0.60 / 3 | 16.5 | 43.9 | 43.4 |
| restart | 3 | 2 | 2x | 6.9 | B->C 3.4, C->D 5.0 | D 23.8 | 23.8 | 18.8 | A->B 384, A->C 165, A->D 1645 | 548 | 2201 | 0.76 / 3 | 16.6 | 41.3 | 40.2 |
| split | 3 | 2 | 2x | 6.9 | B->C 3.5, C->D 5.0 | D 18.2 | 18.2 | 13.2 | A->B 384, B->C 219, A->C 165, C->D 274, B->D 274, A->D 1097 | 0 | 2421 | 0.55 / 3 | 16.5 | 43.9 | 43.3 |
| direct | 3 | 2 | unlim | 6.9 | B->C 3.4, C->D 5.0 | D 17.7 | 17.7 | 12.7 | A->D 1645 | 0 | 1653 | 0.53 / 3 | 16.5 | 43.9 | 43.3 |
| relay_pipe | 3 | 2 | unlim | 6.9 | B->C 3.5, C->D 5.0 | D 19.3 | 19.3 | 14.3 | A->B 1645, B->C 1645, C->D 1645 | 0 | 4944 | 0.60 / 3 | 16.5 | 43.9 | 43.4 |
| restart | 3 | 2 | unlim | 6.9 | B->C 3.4, C->D 5.6 | D 24.3 | 24.3 | 18.7 | A->B 384, A->C 219, A->D 1645 | 603 | 2256 | 0.78 / 3 | 16.6 | 42.9 | 42.5 |
| split | 3 | 2 | unlim | 6.9 | B->C 3.5, C->D 5.0 | D 17.7 | 17.7 | 12.7 | A->B 384, B->C 219, A->C 165, C->D 274, B->D 274, A->D 1097 | 0 | 2421 | 0.53 / 3 | 16.5 | 43.9 | 43.3 |

Reading guide: rho = T_s / T_m. rho < 1: the sink reaches an edge before execution leaves it and the policies should converge. rho > 1: restart wastes what reached obsolete edges and resets the clock at each move; relay accumulates one link time per hop; split keeps delivered segments moving and uses the direct link for the remainder; direct is the oracle.
