# Repeated mobility: sink routing policy x mobility interval x hops (1000 Mbps per link, sink <= 1645 MB, link time T_s = 13.8 s, S = 548 ms/chunk)

Times in seconds after the A->B handoff. moves = when execution left each edge. ready = when the true sink bound at each edge. ready_final_after_last_move = readiness at the final edge minus the last move time. wasted = segments stranded on edges execution had already left. total = all link traffic (A->edge real, edge->edge emulated at the same per-link bandwidth; split gives the new edge two independent ingress links). lag = hops between the execution edge and the last edge with a bound sink, averaged over calls.

| policy | hops | T_m | ingress | rho | moves at | ready | ready_final | after last move | traffic by link (MB) | wasted MB | total MB | lag mean / max | PSNR before final bind | PSNR final bind+8.. | PSNR last 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| direct | 3 | 2 | 1x | 6.9 | B->C 3.2, C->D 5.2 | D 32.8 | 32.8 | 27.6 | A->D 1645 | 0 | 1653 | 1.17 / 3 | 16.6 | 40.6 | 41.3 |
| relay_pipe | 3 | 2 | 1x | 6.9 | B->C 3.2, C->D 5.2 | D 34.4 | 34.4 | 29.2 | A->B 1645, B->C 1645, C->D 1645 | 0 | 4944 | 1.24 / 3 | 16.6 | 40.5 | 41.3 |
| restart | 3 | 2 | 1x | 6.9 | B->C 3.2, C->D 5.2 | D 40.2 | 40.2 | 35.0 | A->B 219, A->C 110, A->D 1645 | 329 | 1982 | 1.47 / 3 | 16.7 | 40.4 | 41.0 |
| split | 3 | 2 | 1x | 6.9 | B->C 3.3, C->D 5.2 | D 33.3 | 33.3 | 28.1 | A->B 219, B->C 219, A->C 110, C->D 219, B->D 110, A->D 1316 | 0 | 2201 | 1.19 / 3 | 16.6 | 40.6 | 41.3 |
| direct | 3 | 2 | 2x | 6.9 | B->C 3.2, C->D 5.1 | D 33.1 | 33.1 | 28.0 | A->D 1645 | 0 | 1653 | 1.19 / 3 | 16.6 | 40.6 | 41.3 |
| relay_pipe | 3 | 2 | 2x | 6.9 | B->C 3.2, C->D 5.2 | D 34.3 | 34.3 | 29.1 | A->B 1645, B->C 1645, C->D 1645 | 0 | 4944 | 1.24 / 3 | 16.6 | 40.5 | 41.3 |
| restart | 3 | 2 | 2x | 6.9 | B->C 3.2, C->D 5.2 | D 40.2 | 40.2 | 35.0 | A->B 219, A->C 110, A->D 1645 | 329 | 1982 | 1.47 / 3 | 16.7 | 40.4 | 41.0 |
| split | 3 | 2 | 2x | 6.9 | B->C 3.2, C->D 5.2 | D 33.3 | 33.3 | 28.1 | A->B 219, B->C 219, A->C 110, B->D 110, C->D 219, A->D 1316 | 0 | 2201 | 1.19 / 3 | 16.6 | 40.6 | 41.3 |
| direct | 3 | 2 | unlim | 6.9 | B->C 3.2, C->D 5.2 | D 33.1 | 33.1 | 28.0 | A->D 1645 | 0 | 1653 | 1.19 / 3 | 16.6 | 40.6 | 41.3 |
| relay_pipe | 3 | 2 | unlim | 6.9 | B->C 3.1, C->D 5.1 | D 34.2 | 34.2 | 29.1 | A->B 1645, B->C 1645, C->D 1645 | 0 | 4944 | 1.24 / 3 | 16.6 | 40.5 | 41.3 |
| restart | 3 | 2 | unlim | 6.9 | B->C 3.2, C->D 5.2 | D 40.0 | 40.0 | 34.9 | A->B 219, A->C 110, A->D 1645 | 329 | 1982 | 1.47 / 3 | 16.7 | 40.4 | 41.0 |
| split | 3 | 2 | unlim | 6.9 | B->C 3.2, C->D 5.2 | D 33.2 | 33.2 | 28.0 | A->B 219, B->C 219, A->C 110, C->D 219, B->D 110, A->D 1316 | 0 | 2201 | 1.19 / 3 | 16.6 | 40.6 | 41.3 |

Reading guide: rho = T_s / T_m. rho < 1: the sink reaches an edge before execution leaves it and the policies should converge. rho > 1: restart wastes what reached obsolete edges and resets the clock at each move; relay accumulates one link time per hop; split keeps delivered segments moving and uses the direct link for the remainder; direct is the oracle.
