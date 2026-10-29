# M3-S1 results (expM3S1c; validity: frozen)

| cell | valid | remote s | local s | cancelled | final valid/180 | final base MB | final ready s | total MB | discarded | staged | wasted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bfly ρ1 S1c/fwd | 3/3 | 58.8 | 2.0 | 2 | 0 | 1728 | 25.5 | 5482 | 3117 | 0 | 0 |
| bfly ρ1 S1c/rev | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.6 | 5748 | 3117 | 1591 | 556 |
| bfly ρ1 S1o/fwd | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.6 | 5296 | 3107 | 1150 | 115 |
| bfly ρ1 S2/fwd | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.7 | 5767 | 3108 | 1620 | 585 |
| bfly ρ1 S2/rev | 3/3 | 45.9 | 2.0 | 2 | 108 | 692 | 12.6 | 5757 | 3107 | 1610 | 575 |
| bfly ρ1 S3/fwd | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.7 | 5776 | 3107 | 1629 | 594 |
| bfly ρ1 S3/rev | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.6 | 5757 | 3107 | 1610 | 575 |
| bfly ρ1 none/fwd | 3/3 | 58.9 | 2.0 | 2 | 0 | 1728 | 25.6 | 5471 | 3107 | 0 | 0 |
| dog ρ1 S1c/fwd | 3/3 | 52.1 | 2.0 | 2 | 0 | 1728 | 21.9 | 4485 | 2695 | 0 | 0 |
| dog ρ1 S1c/rev | 3/3 | 38.4 | 2.0 | 2 | 138 | 405 | 8.1 | 4778 | 2695 | 1639 | 316 |
| dog ρ1 S1o/fwd | 3/3 | 38.4 | 2.0 | 2 | 137 | 415 | 8.2 | 4471 | 2685 | 1332 | 19 |
| dog ρ1 S2/fwd | 3/3 | 38.4 | 2.0 | 2 | 138 | 405 | 8.1 | 4787 | 2685 | 1658 | 335 |
| dog ρ1 S2/rev | 3/3 | 38.4 | 2.0 | 2 | 138 | 405 | 8.1 | 4787 | 2695 | 1649 | 326 |
| dog ρ1 S3/fwd | 3/3 | 38.3 | 2.0 | 2 | 138 | 405 | 8.1 | 4797 | 2695 | 1658 | 335 |
| dog ρ1 S3/rev | 3/3 | 38.3 | 2.0 | 2 | 138 | 405 | 8.1 | 4787 | 2685 | 1649 | 326 |
| dog ρ1 none/fwd | 3/3 | 52.2 | 2.0 | 2 | 0 | 1728 | 22.0 | 4485 | 2695 | 0 | 0 |
| dog ρ2 S3/fwd | 3/3 | 32.3 | 2.0 | 2 | 61 | 1143 | 15.5 | 3243 | 1138 | 911 | 326 |
| dog ρ2 none/fwd | 3/3 | 38.5 | 2.0 | 2 | 0 | 1728 | 21.6 | 2919 | 1128 | 0 | 0 |

## Rules

```
{
 "R1": {
  "dog": {
   "per_order": {
    "fwd": {
     "remote_ratio": 0.7342397548831865,
     "total_ratio": 1.0694116274664949,
     "pass": true
    },
    "rev": {
     "remote_ratio": 0.7342206051321333,
     "total_ratio": 1.0672748173803033,
     "pass": true
    }
   },
   "pass": true
  },
  "bfly": {
   "per_order": {
    "fwd": {
     "remote_ratio": 0.780973902405872,
     "total_ratio": 1.055718835762375,
     "pass": true
    },
    "rev": {
     "remote_ratio": 0.7808719586788093,
     "total_ratio": 1.0522150715012777,
     "pass": true
    }
   },
   "pass": true
  }
 },
 "R2": {
  "dog": {
   "S1o_remote_ratio": 0.7358674837227116,
   "S1c_remote_ratio": {
    "fwd": 0.9986595174262735,
    "rev": 0.7344312523937189
   },
   "S2_remote_ratio": {
    "fwd": 0.7343929528916124,
    "rev": 0.7344312523937189
   },
   "S3_remote_ratio": {
    "fwd": 0.7342397548831865,
    "rev": 0.7342206051321333
   },
   "total_ratio": {
    "S1c": {
     "fwd": 1.0,
     "rev": 1.0651380072941117
    },
    "S2": {
     "fwd": 1.0672748173803033,
     "rev": 1.0672748173803033
    },
    "S3": {
     "fwd": 1.0694116274664949,
     "rev": 1.0672748173803033
    }
   },
   "wasted_mb": {
    "S1c": {
     "fwd": 0.0,
     "rev": 316.29312
    },
    "S2": {
     "fwd": 335.4624,
     "rev": 325.87776
    },
    "S3": {
     "fwd": 335.4624,
     "rev": 325.87776
    }
   },
   "one_candidate_suffices": false
  },
  "bfly": {
   "S1o_remote_ratio": 0.780820986815278,
   "S1c_remote_ratio": {
    "fwd": 0.9997621313035204,
    "rev": 0.7811607992388201
   },
   "S2_remote_ratio": {
    "fwd": 0.7811268179964659,
    "rev": 0.78051515563409
   },
   "S3_remote_ratio": {
    "fwd": 0.780973902405872,
    "rev": 0.7808719586788093
   },
   "total_ratio": {
    "S1c": {
     "fwd": 1.001943541030301,
     "rev": 1.0506548482704814
    },
    "S2": {
     "fwd": 1.0541586125315787,
     "rev": 1.0522150715012777
    },
    "S3": {
     "fwd": 1.055718835762375,
     "rev": 1.0522150715012777
    }
   },
   "wasted_mb": {
    "S1c": {
     "fwd": 0.0,
     "rev": 555.90912
    },
    "S2": {
     "fwd": 584.66304,
     "rev": 575.0784
    },
    "S3": {
     "fwd": 594.24768,
     "rev": 575.0784
    }
   },
   "one_candidate_suffices": false
  }
 },
 "R3": {
  "dog": {
   "S3": 1.9149751053191677e-05,
   "S2": 3.8299502106383354e-05,
   "S1c": 0.26422826503255464,
   "pass": true
  },
  "bfly": {
   "S3": 0.00010194372706266528,
   "S2": 0.0006116623623758709,
   "S1c": 0.21860133206470028,
   "pass": true
  }
 },
 "R4": {
  "dog": {
   "per_policy": {
    "S0": {
     "remote_pred": 51.6,
     "remote_meas": 52.22,
     "remote_err": -0.011872845653006503,
     "total_pred_mb": 4552.0,
     "total_meas_mb": 4485.489872,
     "total_err": 0.01482784041385976
    },
    "S1o": {
     "remote_pred": 37.66,
     "remote_meas": 38.427,
     "remote_err": -0.01995992401176261,
     "total_pred_mb": 4546.7,
     "total_meas_mb": 4470.957264,
     "total_err": 0.01694105569066351
    },
    "S1c/fwd": {
     "remote_pred": 51.6,
     "remote_meas": 52.15,
     "remote_err": -0.010546500479386323,
     "total_pred_mb": 4552.0,
     "total_meas_mb": 4485.489872,
     "total_err": 0.01482784041385976
    },
    "S1c/rev": {
     "remote_pred": 37.66,
     "remote_meas": 38.352,
     "remote_err": -0.018043387567793112,
     "total_pred_mb": 4625.5,
     "total_meas_mb": 4777.665744,
     "total_err": -0.031849390927168986
    },
    "S2/fwd": {
     "remote_pred": 37.66,
     "remote_meas": 38.35,
     "remote_err": -0.01799217731421132,
     "total_pred_mb": 4625.5,
     "total_meas_mb": 4787.250384,
     "total_err": -0.03378774265507478
    },
    "S2/rev": {
     "remote_pred": 37.66,
     "remote_meas": 38.352,
     "remote_err": -0.018043387567793112,
     "total_pred_mb": 4625.5,
     "total_meas_mb": 4787.250384,
     "total_err": -0.03378774265507478
    },
    "S3/fwd": {
     "remote_pred": 37.66,
     "remote_meas": 38.342,
     "remote_err": -0.017787282875176058,
     "total_pred_mb": 4661.8,
     "total_meas_mb": 4796.835024,
     "total_err": -0.02815085849823462
    },
    "S3/rev": {
     "remote_pred": 37.66,
     "remote_meas": 38.341,
     "remote_err": -0.017761665058292797,
     "total_pred_mb": 4661.8,
     "total_meas_mb": 4787.250384,
     "total_err": -0.02620510187210623
    }
   },
   "remote_within_15pct_all": true,
   "total_within_15pct_all": true
  },
  "bfly": {
   "per_policy": {
    "S0": {
     "remote_pred": 59.04,
     "remote_meas": 58.856,
     "remote_err": 0.003126274296588294,
     "total_pred_mb": 5535.8,
     "total_meas_mb": 5471.053008,
     "total_err": 0.01183446621798856
    },
    "S1o": {
     "remote_pred": 45.68,
     "remote_meas": 45.956,
     "remote_err": -0.006005744625293796,
     "total_pred_mb": 5376.7,
     "total_meas_mb": 5295.613136,
     "total_err": 0.015312082268390315
    },
    "S1c/fwd": {
     "remote_pred": 59.04,
     "remote_meas": 58.842,
     "remote_err": 0.003364943407770049,
     "total_pred_mb": 5535.8,
     "total_meas_mb": 5481.686224,
     "total_err": 0.009871739057788265
    },
    "S1c/rev": {
     "remote_pred": 45.68,
     "remote_meas": 45.976,
     "remote_err": -0.006438141639116046,
     "total_pred_mb": 5678.8,
     "total_meas_mb": 5748.188368,
     "total_err": -0.012071345536670774
    },
    "S2/fwd": {
     "remote_pred": 45.68,
     "remote_meas": 45.974,
     "remote_err": -0.006394918867185684,
     "total_pred_mb": 5678.8,
     "total_meas_mb": 5767.357648,
     "total_err": -0.015354977687348725
    },
    "S2/rev": {
     "remote_pred": 45.68,
     "remote_meas": 45.938,
     "remote_err": -0.005616265401192977,
     "total_pred_mb": 5678.8,
     "total_meas_mb": 5756.724432,
     "total_err": -0.013536244946317
    },
    "S3/fwd": {
     "remote_pred": 45.68,
     "remote_meas": 45.965,
     "remote_err": -0.006200369846622533,
     "total_pred_mb": 5865.5,
     "total_meas_mb": 5775.893712,
     "total_err": 0.015513839497051984
    },
    "S3/rev": {
     "remote_pred": 45.68,
     "remote_meas": 45.959,
     "remote_err": -0.006070628168585168,
     "total_pred_mb": 5865.5,
     "total_meas_mb": 5756.724432,
     "total_err": 0.018895392559586055
    }
   },
   "remote_within_15pct_all": true,
   "total_within_15pct_all": true
  }
 },
 "R5_invalid_runs": {}
}
```

**Verdict: GO (R1 holds for both workloads; next: M3-S2 GPU validation, to be preregistered)**
