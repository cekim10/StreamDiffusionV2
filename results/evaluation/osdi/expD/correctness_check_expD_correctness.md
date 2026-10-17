# Experiment D focused correctness - check

`expD_correctness`; conditions in the docstring of `tools/eval/check_expD_correctness.py` (written before the runs).

| capability | policy | run | checks passed | verdict |
|---|---|---|---|---|
| full | full | 20261016-175402 | 16/16 | PASS |
| full | full | 20261016-180053 | 16/16 | PASS |
| cold | cold | 20261016-180756 | 13/13 | PASS |
| cold | cold | 20261016-181412 | 13/13 | PASS |
| revisit | restart | 20261016-182047 | 15/15 | PASS |
| revisit | split | 20261016-182205 | 14/14 | PASS |
| revisit | reuse_aware_in | 20261016-182315 | 14/14 | PASS |
| revisit | reuse_dyn | 20261016-182426 | 14/14 | PASS |
| hybrid | restart | 20261016-183059 | 16/16 | PASS |
| hybrid | split | 20261016-183259 | 16/16 | PASS |
| hybrid | reuse_dyn | 20261016-183453 | 16/16 | PASS |
| - | - | 20261016-184202 | - | INCOMPLETE (no summary.json) |
| colddest | reuse_dyn | 20261016-223452 | 16/16 | PASS |
| fast | split | 20261016-224214 | 14/14 | PASS |
| fast | split | 20261016-224842 | 13/14 | FAIL: placement delivered (allocation - max(2, 5 %) fragments) |
| fast | reuse_dyn | 20261016-225518 | 14/14 | PASS |
| full | full | 20261016-230130 | 15/15 | PASS |
| fast | reuse_dyn | 20261016-230213 | 12/12 | PASS |
| full | full | 20261017-153610 | 16/16 | PASS |
| full | full | 20261017-154300 | 16/16 | PASS |
| full | full | 20261017-155009 | 15/15 | PASS |
| fast | reuse_dyn | 20261017-155052 | 12/12 | PASS |
| fast | split | 20261017-155647 | 14/14 | PASS |
| fast | split | 20261017-160314 | 14/14 | PASS |
| fast | reuse_dyn | 20261017-160936 | 14/14 | PASS |
| hybrid | restart | 20261017-161553 | 16/16 | PASS |
| hybrid | split | 20261017-161754 | 16/16 | PASS |
| hybrid | reuse_dyn | 20261017-161933 | 16/16 | PASS |

28 runs; 2 failing.

Per-run checks:
```
[
 {
  "run": "policy=full_bw=1000_rho=none_tm=inf_rep=1_20261016-175402",
  "kind": "full",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "state digests ok": true,
   "Sink digest = manifest": true,
   "bit-exact after resume": true,
   "completed transfer = whole state": true,
   "redirect discards partial state": true,
   "resume after transfer end": true
  },
  "nic_ratio": {
   "A": 1.0476097052096263
  }
 },
 {
  "run": "policy=full_bw=1000_rho=2_tm=7.025_rep=1_20261016-180053",
  "kind": "full",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "state digests ok": true,
   "Sink digest = manifest": true,
   "bit-exact after resume": true,
   "completed transfer = whole state": true,
   "redirect discards partial state": true,
   "resume after transfer end": true
  },
  "nic_ratio": {
   "A": 1.0473231703094084
  }
 },
 {
  "run": "policy=cold_bw=1000_rho=none_tm=inf_rep=1_20261016-180756",
  "kind": "cold",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "no state sent": true,
   "PSNR for every produced chunk": true,
   "first output within 3 chunks of resume": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=cold_bw=1000_rho=2_tm=7.025_rep=1_20261016-181412",
  "kind": "cold",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "no state sent": true,
   "PSNR for every produced chunk": true,
   "first output within 3 chunks of resume": true
  },
  "nic_ratio": {}
 },
 {
  "run": "policy=restart_bw=1000_rho=2_tm=7.025_path=ABCDB_rep=1_20261016-182047",
  "kind": "revisit",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "M1 only: nothing held on return": true,
   "M1 only: re-received": true
  },
  "nic_ratio": {
   "A": 1.0477708998026454
  }
 },
 {
  "run": "policy=split_bw=1000_rho=2_tm=7.025_path=ABCDB_rep=1_20261016-182205",
  "kind": "revisit",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "preserved on return": true
  },
  "nic_ratio": {
   "A": 1.0478377102474725,
   "B": 1.0485955133118987,
   "C": 1.0482476468442916,
   "D": 1.0512173840651293
  }
 },
 {
  "run": "policy=reuse_aware_in_bw=1000_rho=2_tm=7.025_path=ABCDB_rep=1_20261016-182315",
  "kind": "revisit",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "preserved on return": true
  },
  "nic_ratio": {
   "A": 1.0478661442736892,
   "B": 1.0499702230024153,
   "C": 1.0493763457734613,
   "D": 1.0526706596683058
  }
 },
 {
  "run": "policy=reuse_dyn_bw=1000_rho=2_tm=7.025_path=ABCDB_rep=1_20261016-182426",
  "kind": "revisit",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "preserved on return": true
  },
  "nic_ratio": {
   "A": 1.0478795515577053,
   "B": 1.0490569592369532,
   "C": 1.0492847580277478,
   "D": 1.052390619472586
  }
 },
 {
  "run": "policy=restart_bw=1000_rho=2_tm=7.025_hybrid=3_rep=1_20261016-183059",
  "kind": "hybrid",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
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
  "run": "policy=split_bw=1000_rho=2_tm=7.025_hybrid=3_rep=1_20261016-183259",
  "kind": "hybrid",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
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
  "run": "policy=reuse_dyn_bw=1000_rho=2_tm=7.025_hybrid=3_rep=1_20261016-183453",
  "kind": "hybrid",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
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
  "run": "policy=reuse_dyn_bw=1000_rho=none_tm=inf_colddest_rep=1_20261016-223452",
  "kind": "colddest",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "process started after trigger": true,
   "TTFO > runtime ready > process start": true,
   "reference from cache": true
  },
  "nic_ratio": {
   "A": 1.0478172198533455
  }
 },
 {
  "run": "policy=split_bw=1000_rho=none_tm=inf_path=AC_pp=none_L=10_b=1_rep=1_20261016-224214",
  "kind": "fast",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "placement delivered (allocation - max(2, 5 %) fragments)": true
  },
  "nic_ratio": {
   "A": 1.0478159803216254
  }
 },
 {
  "run": "policy=split_bw=1000_rho=none_tm=inf_path=AC_pp=top1_L=10_b=1_rep=1_20261016-224842",
  "kind": "fast",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "placement delivered (allocation - max(2, 5 %) fragments)": false
  },
  "nic_ratio": {
   "A": 1.0477929651890794
  }
 },
 {
  "run": "policy=reuse_dyn_bw=1000_rho=none_tm=inf_path=AB_pp=oracle_L=10_b=1_rep=1_20261016-225518",
  "kind": "fast",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "placement delivered (allocation - max(2, 5 %) fragments)": true
  },
  "nic_ratio": {
   "A": 1.047817542472277
  }
 },
 {
  "run": "policy=full_bw=native_rho=none_tm=inf_rep=1_20261016-230130",
  "kind": "full",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "state digests ok": true,
   "Sink digest = manifest": true,
   "bit-exact after resume": true,
   "completed transfer = whole state": true,
   "redirect discards partial state": true,
   "resume after transfer end": true
  },
  "nic_ratio": {
   "A": 1.0477679954907366
  }
 },
 {
  "run": "policy=reuse_dyn_bw=native_rho=none_tm=inf_rep=1_20261016-230213",
  "kind": "fast",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {
   "A": 1.047634946491521
  }
 },
 {
  "run": "policy=full_bw=1000_rho=none_tm=inf_rep=1_20261017-153610",
  "kind": "full",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "state digests ok": true,
   "Sink digest = manifest": true,
   "bit-exact after resume": true,
   "completed transfer = whole state": true,
   "redirect discards partial state": true,
   "resume after transfer end": true
  },
  "nic_ratio": {
   "A": 1.0475913306494908
  }
 },
 {
  "run": "policy=full_bw=1000_rho=2_tm=7.025_rep=1_20261017-154300",
  "kind": "full",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "state digests ok": true,
   "Sink digest = manifest": true,
   "bit-exact after resume": true,
   "completed transfer = whole state": true,
   "redirect discards partial state": true,
   "resume after transfer end": true
  },
  "nic_ratio": {
   "A": 1.0473393738414702
  }
 },
 {
  "run": "policy=full_bw=native_rho=none_tm=inf_rep=1_20261017-155009",
  "kind": "full",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "state digests ok": true,
   "Sink digest = manifest": true,
   "bit-exact after resume": true,
   "completed transfer = whole state": true,
   "redirect discards partial state": true,
   "resume after transfer end": true
  },
  "nic_ratio": {
   "A": 1.0476075191433831
  }
 },
 {
  "run": "policy=reuse_dyn_bw=native_rho=none_tm=inf_rep=1_20261017-155052",
  "kind": "fast",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true
  },
  "nic_ratio": {
   "A": 1.0477808164809521
  }
 },
 {
  "run": "policy=split_bw=1000_rho=none_tm=inf_path=AC_pp=none_L=10_b=1_rep=1_20261017-155647",
  "kind": "fast",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "placement delivered (allocation - max(2, 5 %) fragments)": true
  },
  "nic_ratio": {
   "A": 1.0478262066044786
  }
 },
 {
  "run": "policy=split_bw=1000_rho=none_tm=inf_path=AC_pp=top1_L=10_b=1_rep=1_20261017-160314",
  "kind": "fast",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "placement delivered (allocation - max(2, 5 %) fragments)": true
  },
  "nic_ratio": {
   "A": 1.0478098356921628,
   "B": 1.0488986886466167
  }
 },
 {
  "run": "policy=reuse_dyn_bw=1000_rho=none_tm=inf_path=AB_pp=oracle_L=10_b=1_rep=1_20261017-160936",
  "kind": "fast",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
   "per-move timing": true,
   "final owner keeps generating": true,
   "NIC egress vs accounted": true,
   "all fragments verified": true,
   "final Sink digest = source": true,
   "rejoin >= 35 dB": true,
   "placement delivered (allocation - max(2, 5 %) fragments)": true
  },
  "nic_ratio": {
   "A": 1.0477997689052747
  }
 },
 {
  "run": "policy=restart_bw=1000_rho=2_tm=7.025_hybrid=3_rep=1_20261017-161553",
  "kind": "hybrid",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
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
  "run": "policy=split_bw=1000_rho=2_tm=7.025_hybrid=3_rep=1_20261017-161754",
  "kind": "hybrid",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
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
  "run": "policy=reuse_dyn_bw=1000_rho=2_tm=7.025_hybrid=3_rep=1_20261017-161933",
  "kind": "hybrid",
  "checks": {
   "version events 0": true,
   "duplicates 0": true,
   "NIC <= 1.15 cap": true,
   "four hosts, one commit": true,
   "stop reason": true,
   "paced egress 10 s <= 1.05 cap": true,
   "GPU 0 idle before run": true,
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
