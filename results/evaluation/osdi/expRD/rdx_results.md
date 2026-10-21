# RD-X: one hop at 320 Mbps vs emulation replay (EXPLORATORY; no verdict)

| workload | rep | valid | reset / bind call (d) | bind after move (s) | real: T / crossed / sustained | replay: same crossing / sustained, abs dT, median / max abs dPSNR | Phase 1 r1 d75 b155 T |
|---|---|---|---|---|---|---|---|
| butterfly-feeding-slow-motion | 1 | True | 80 / 154 (74) | 43.84 | 28.57 / False / False | True / True, 0.00, 0.00 / 0.00 | 28.84 |
| butterfly-feeding-slow-motion | 2 | True | 80 / 154 (74) | 44.32 | 28.57 / False / False | True / True, 0.00, 0.00 / 0.00 | 28.84 |
| audi-snow-trail | 1 | True | 80 / 154 (74) | 43.99 | 27.71 / False / False | True / True, 0.00, 0.00 / 0.00 | 27.84 |
| audi-snow-trail | 2 | True | 80 / 154 (74) | 43.92 | 27.71 / False / False | True / True, 0.00, 0.00 / 0.00 | 27.84 |
| dog | 1 | True | 80 / 154 (74) | 44.09 | 44.93 / True / True | True / True, 0.00, 0.00 / 0.00 | 45.74 |
| dog | 2 | True | 80 / 154 (74) | 44.03 | 44.93 / True / True | True / True, 0.00, 0.00 / 0.00 | 45.74 |
