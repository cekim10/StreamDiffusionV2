# Experiment D focused correctness - check

`_dryrun_d0_gpu`; conditions in the docstring of `tools/eval/check_expD_correctness.py` (written before the runs).

| capability | policy | run | checks passed | verdict |
|---|---|---|---|---|
| full | full | 20261017-152511 | 13/13 | PASS |
| full | full | 20261017-152542 | 13/13 | PASS |
| full | full | 20261017-152619 | 12/12 | PASS |
| fast | reuse_dyn | 20261017-152624 | 9/9 | PASS |

4 runs; 0 failing.

Per-run checks:
```
[
 {
  "run": "policy=full_bw=100_rho=none_tm=inf_rep=1_20261017-152511",
  "kind": "full",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "state digests ok": true,
   "Sink digest = manifest": true,
   "bit-exact after resume": true,
   "completed transfer = whole state": true,
   "redirect discards partial state": true,
   "resume after transfer end": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=full_bw=100_rho=2_tm=2.7_rep=1_20261017-152542",
  "kind": "full",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "state digests ok": true,
   "Sink digest = manifest": true,
   "bit-exact after resume": true,
   "completed transfer = whole state": true,
   "redirect discards partial state": true,
   "resume after transfer end": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=full_bw=native_rho=none_tm=inf_rep=1_20261017-152619",
  "kind": "full",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "state digests ok": true,
   "Sink digest = manifest": true,
   "bit-exact after resume": true,
   "completed transfer = whole state": true,
   "redirect discards partial state": true,
   "resume after transfer end": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_dyn_bw=native_rho=none_tm=inf_rep=1_20261017-152624",
  "kind": "fast",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 }
]
```
