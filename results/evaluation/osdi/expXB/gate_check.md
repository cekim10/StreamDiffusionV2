# XB exactness gate

| run | policy | result | components | output equivalence | notes |
|---|---|---|---|---|---|
| policy=precopy_full_bw=1000_rho=none_tm=inf_thr=64_rl=6_rep=1_20261022-160815 | precopy_full | PASS | {'inflight': True, 'meta': True, 'recent': True, 'sink': True, 'vae': True} | 101 / 101 | - |
| policy=recompute_full_bw=1000_rho=none_tm=inf_lag=1_rl=6_rep=1_20261022-161312 | recompute_full | PASS | {'inflight': True, 'meta': True, 'recent': True, 'sink': True, 'vae': True} | 101 / 101 | - |
| policy=precopy_full_bw=1000_rho=none_tm=inf_thr=64_rl=6_rep=1_20261022-163337 | precopy_full | PASS | {'inflight': True, 'meta': True, 'recent': True, 'sink': True, 'vae': True} | 101 / 101 | - |
| policy=recompute_full_bw=1000_rho=none_tm=inf_lag=1_rl=6_rep=1_20261022-163842 | recompute_full | PASS | {'inflight': True, 'meta': True, 'recent': True, 'sink': True, 'vae': True} | 101 / 101 | - |

GATE PASS
