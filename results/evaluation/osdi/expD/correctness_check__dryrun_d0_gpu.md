# Experiment D focused correctness - check

`_dryrun_d0_gpu`; conditions in the docstring of `tools/eval/check_expD_correctness.py` (written before the runs).

| capability | policy | run | checks passed | verdict |
|---|---|---|---|---|
| fast | reuse_dyn | 20261016-172321 | 10/10 | PASS |
| fast | restart | 20261016-172335 | 10/10 | PASS |
| fast | split | 20261016-172352 | 10/10 | PASS |
| fast | reuse_aware_in | 20261016-172407 | 10/10 | PASS |
| fast | reuse_dyn | 20261016-172424 | 10/10 | PASS |
| fast | split | 20261016-172445 | 10/10 | PASS |
| fast | reuse_aware_in | 20261016-172506 | 10/10 | PASS |
| fast | reuse_dyn | 20261016-172526 | 10/10 | PASS |
| fast | reuse_dyn | 20261016-172549 | 10/10 | PASS |
| fast | reuse_dyn | 20261016-172604 | 10/10 | PASS |
| full | full | 20261016-172623 | 13/13 | PASS |
| full | full | 20261016-172655 | 13/13 | PASS |
| cold | cold | 20261016-172732 | 10/10 | PASS |
| revisit | restart | 20261016-172752 | 12/12 | PASS |
| revisit | split | 20261016-172811 | 11/11 | PASS |
| revisit | reuse_aware_in | 20261016-172827 | 11/11 | PASS |
| revisit | reuse_dyn | 20261016-172843 | 11/11 | PASS |
| hybrid | restart | 20261016-172904 | 14/14 | PASS |
| hybrid | split | 20261016-172939 | 14/14 | PASS |
| hybrid | reuse_dyn | 20261016-173014 | 14/14 | PASS |
| colddest | reuse_dyn | 20261016-173054 | 13/13 | PASS |
| fast | split | 20261016-173110 | 10/10 | PASS |
| fast | split | 20261016-173129 | 10/10 | PASS |
| fast | reuse_dyn | 20261016-173148 | 10/10 | PASS |
| full | full | 20261016-173203 | 12/12 | PASS |
| fast | reuse_dyn | 20261016-173208 | 9/9 | PASS |

26 runs; 0 failing.

Per-run checks:
```
[
 {
  "run": "policy=reuse_dyn_bw=100_rho=none_tm=inf_rep=1_20261016-172321",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=restart_bw=100_rho=2_tm=2.7_rep=1_20261016-172335",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=split_bw=100_rho=2_tm=2.7_rep=1_20261016-172352",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_aware_in_bw=100_rho=2_tm=2.7_rep=1_20261016-172407",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_dyn_bw=100_rho=2_tm=2.7_rep=1_20261016-172424",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=split_bw=100_rho=2_tm=2.7_ev=Dge0.5Cout12.5_rep=1_20261016-172445",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_aware_in_bw=100_rho=2_tm=2.7_ev=Dge0.5Cout12.5_rep=1_20261016-172506",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_dyn_bw=100_rho=2_tm=2.7_ev=Dge0.5Cout12.5_rep=1_20261016-172526",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_dyn_bw=100_rho=none_tm=inf_path=AB_pp=top1_L=4_b=1_rep=1_20261016-172549",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_dyn_bw=100_rho=none_tm=inf_path=AC_pp=top1_L=4_b=1_rep=1_20261016-172604",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=full_bw=100_rho=none_tm=inf_rep=1_20261016-172623",
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
  "run": "policy=full_bw=100_rho=2_tm=2.7_rep=1_20261016-172655",
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
  "run": "policy=cold_bw=100_rho=2_tm=2.7_rep=1_20261016-172732",
  "kind": "cold",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "no state sent": true,
   "PSNR for every produced chunk": true,
   "first output within 3 chunks of resume": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=restart_bw=100_rho=2_tm=2.7_path=ABCDB_rep=1_20261016-172752",
  "kind": "revisit",
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
   "M1 only: nothing held on return": true,
   "M1 only: re-received": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=split_bw=100_rho=2_tm=2.7_path=ABCDB_rep=1_20261016-172811",
  "kind": "revisit",
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
   "preserved on return": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_aware_in_bw=100_rho=2_tm=2.7_path=ABCDB_rep=1_20261016-172827",
  "kind": "revisit",
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
   "preserved on return": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_dyn_bw=100_rho=2_tm=2.7_path=ABCDB_rep=1_20261016-172843",
  "kind": "revisit",
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
   "preserved on return": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=restart_bw=100_rho=2_tm=2.7_hybrid=3_rep=1_20261016-172904",
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
  "run": "policy=split_bw=100_rho=2_tm=2.7_hybrid=3_rep=1_20261016-172939",
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
  "run": "policy=reuse_dyn_bw=100_rho=2_tm=2.7_hybrid=3_rep=1_20261016-173014",
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
  "run": "policy=reuse_dyn_bw=100_rho=none_tm=inf_colddest_rep=1_20261016-173054",
  "kind": "colddest",
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
   "process started after trigger": true,
   "TTFO > runtime ready > process start": true,
   "reference from cache": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=split_bw=100_rho=none_tm=inf_path=AC_pp=none_L=4_b=1_rep=1_20261016-173110",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=split_bw=100_rho=none_tm=inf_path=AC_pp=top1_L=4_b=1_rep=1_20261016-173129",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=reuse_dyn_bw=100_rho=none_tm=inf_path=AB_pp=oracle_L=4_b=1_rep=1_20261016-173148",
  "kind": "fast",
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
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=full_bw=native_rho=none_tm=inf_rep=1_20261016-173203",
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
  "run": "policy=reuse_dyn_bw=native_rho=none_tm=inf_rep=1_20261016-173208",
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
