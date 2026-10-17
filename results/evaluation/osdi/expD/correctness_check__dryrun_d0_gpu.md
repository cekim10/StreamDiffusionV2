# Experiment D focused correctness - check

`_dryrun_d0_gpu`; conditions in the docstring of `tools/eval/check_expD_correctness.py` (written before the runs).

| capability | policy | run | checks passed | verdict |
|---|---|---|---|---|
| hybrid | restart | 20261017-152854 | 14/14 | PASS |
| hybrid | split | 20261017-152929 | 14/14 | PASS |
| hybrid | reuse_dyn | 20261017-152957 | 14/14 | PASS |

3 runs; 0 failing.

Per-run checks:
```
[
 {
  "run": "policy=restart_bw=100_rho=2_tm=2.7_hybrid=3_rep=1_20261017-152854",
  "kind": "hybrid",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "network sessions restored": true,
   "network pacing valid": true,
   "combined A payload <= 1.05 cap / 10 s": true,
   "GPU chunk time unaffected (5 %)": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=split_bw=100_rho=2_tm=2.7_hybrid=3_rep=1_20261017-152929",
  "kind": "hybrid",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "network sessions restored": true,
   "network pacing valid": true,
   "combined A payload <= 1.05 cap / 10 s": true,
   "GPU chunk time unaffected (5 %)": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_dyn_bw=100_rho=2_tm=2.7_hybrid=3_rep=1_20261017-152957",
  "kind": "hybrid",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "network sessions restored": true,
   "network pacing valid": true,
   "combined A payload <= 1.05 cap / 10 s": true,
   "GPU chunk time unaffected (5 %)": true
  },
  "nic_ratio": {}
 }
]
```
