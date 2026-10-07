# Repeated mobility: sink routing policy x mobility interval x hops (1000 Mbps per link, sink <= 1645 MB, link time T_s = 13.8 s, S = 548 ms/chunk)

Times in seconds after the A->B handoff. moves = when execution left each edge. ready = when the true sink bound at each edge. ready_final_after_last_move = readiness at the final edge minus the last move time. wasted = segments stranded on edges execution had already left. total = all link traffic (A->edge real, edge->edge emulated at the same per-link bandwidth; split gives the new edge two independent ingress links). lag = hops between the execution edge and the last edge with a bound sink, averaged over calls.

| policy | hops | T_m | rho | moves at | ready | ready_final | after last move | traffic by link (MB) | wasted MB | total MB | lag mean / max | PSNR before final bind | PSNR final bind+8.. | PSNR last 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| direct | 2 | 24 | 0.6 | B->C 24.9 | C 24.9 | 24.9 | 0.0 | A->C 1645 | 0 | 1650 | 0.32 / 1 | 16.7 | 42.5 | 42.2 |
| relay | 2 | 24 | 0.6 | B->C 25.1 | B 18.2 | - | - | A->B 1645, B->C 55 | 1590 | 1705 | 0.92 / 1 | 18.1 | - | 16.8 |
| restart | 2 | 24 | 0.6 | B->C 25.1 | B 18.2, C 43.2 | 43.2 | 18.1 | A->B 1645, A->C 1645 | 1645 | 3296 | 0.46 / 1 | 19.2 | 40.6 | 40.8 |
| direct | 2 | 32 | 0.4 | B->C 33.0 | C 33.0 | 33.0 | 0.0 | A->C 1645 | 0 | 1650 | 0.43 / 1 | 16.7 | 40.1 | 41.1 |
| relay | 2 | 32 | 0.4 | B->C 32.8 | B 18.2 | - | - | A->B 1645, B->C 55 | 1590 | 1705 | 0.81 / 1 | 20.9 | - | 16.8 |
| restart | 2 | 32 | 0.4 | B->C 33.3 | B 18.1, C 51.4 | 51.4 | 18.1 | A->B 1645, A->C 1645 | 1645 | 3296 | 0.46 / 1 | 23.4 | 39.6 | 39.4 |
| direct | 3 | 2 | 6.9 | B->C 3.5, C->D 5.0 | D 17.7 | 17.7 | 12.7 | A->D 1645 | 0 | 1653 | 0.53 / 3 | 16.5 | 43.9 | 43.3 |
| relay | 3 | 2 | 6.9 | B->C 3.5, C->D 5.1 | - | - | - | A->B 1645, B->C 55 | 1645 | 1708 | 2.93 / 3 | 16.7 | - | 16.8 |
| relay_pipe | 3 | 2 | 6.9 | B->C 3.4, C->D 5.4 | D 19.7 | 19.7 | 14.3 | A->B 1645, B->C 1645, C->D 1645 | 0 | 4944 | 0.62 / 3 | 16.5 | 43.9 | 43.3 |
| restart | 3 | 2 | 6.9 | B->C 3.5, C->D 5.1 | D 23.8 | 23.8 | 18.7 | A->B 384, A->C 165, A->D 1645 | 548 | 2201 | 0.76 / 3 | 16.6 | 41.3 | 40.2 |
| split | 3 | 2 | 6.9 | B->C 3.5, C->D 5.1 | D 17.8 | 17.8 | 12.7 | A->B 384, B->C 219, A->C 165, C->D 384, B->D 165, A->D 1097 | 0 | 2421 | 0.53 / 3 | 16.5 | 43.9 | 43.3 |

Reading guide: rho = T_s / T_m. rho < 1: the sink reaches an edge before execution leaves it and the policies should converge. rho > 1: restart wastes what reached obsolete edges and resets the clock at each move; relay accumulates one link time per hop; split keeps delivered segments moving and uses the direct link for the remainder; direct is the oracle.
