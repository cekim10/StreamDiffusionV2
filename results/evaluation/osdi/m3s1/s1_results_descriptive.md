# M3-S1 results (expM3S1; validity: descriptive)

| cell | valid | remote s | local s | cancelled | final valid/180 | final base MB | final ready s | total MB | discarded | staged | wasted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bfly ρ1 S1c/fwd | 3/3 | 58.9 | 2.0 | 2 | 0 | 1728 | 25.6 | 5472 | 3107 | 0 | 0 |
| bfly ρ1 S1c/rev | 3/3 | 45.9 | 2.0 | 2 | 108 | 692 | 12.6 | 5757 | 3117 | 1591 | 556 |
| bfly ρ1 S1o/fwd | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.7 | 5298 | 3108 | 1150 | 115 |
| bfly ρ1 S2/fwd | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.7 | 5766 | 3107 | 1610 | 575 |
| bfly ρ1 S2/rev | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.6 | 5775 | 3108 | 1610 | 575 |
| bfly ρ1 S3/fwd | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.6 | 5776 | 3107 | 1620 | 585 |
| bfly ρ1 S3/rev | 3/3 | 46.0 | 2.0 | 2 | 108 | 692 | 12.7 | 5768 | 3107 | 1610 | 575 |
| bfly ρ1 none/fwd | 3/3 | 58.9 | 2.0 | 2 | 0 | 1728 | 25.5 | 5467 | 3107 | 0 | 0 |
| dog ρ1 S1c/fwd | 3/3 | 52.2 | 2.0 | 2 | 0 | 1728 | 21.9 | 4485 | 2695 | 0 | 0 |
| dog ρ1 S1c/rev | 3/3 | 38.4 | 2.0 | 2 | 138 | 405 | 8.1 | 4787 | 2695 | 1639 | 316 |
| dog ρ1 S1o/fwd | 3/3 | 38.4 | 2.0 | 2 | 137 | 415 | 8.2 | 4481 | 2695 | 1332 | 19 |
| dog ρ1 S2/fwd | 3/3 | 38.4 | 2.0 | 2 | 137 | 415 | 8.2 | 4797 | 2695 | 1639 | 326 |
| dog ρ1 S2/rev | 3/3 | 38.4 | 2.0 | 2 | 137 | 415 | 8.2 | 4816 | 2695 | 1629 | 316 |
| dog ρ1 S3/fwd | 3/3 | 38.4 | 2.0 | 2 | 137 | 415 | 8.1 | 4806 | 2695 | 1658 | 335 |
| dog ρ1 S3/rev | 3/3 | 38.4 | 2.0 | 2 | 137 | 415 | 8.2 | 4806 | 2695 | 1649 | 326 |
| dog ρ1 none/fwd | 3/3 | 52.2 | 2.0 | 2 | 0 | 1728 | 22.0 | 4474 | 2685 | 0 | 0 |
| dog ρ2 S3/fwd | 3/3 | 32.3 | 2.0 | 2 | 61 | 1143 | 15.5 | 3262 | 1138 | 920 | 335 |
| dog ρ2 none/fwd | 3/3 | 38.4 | 2.0 | 2 | 0 | 1728 | 21.6 | 2929 | 1138 | 0 | 0 |

## Rules

```
{
 "R1": {
  "dog": {
   "per_order": {
    "fwd": {
     "remote_ratio": 0.7353662273981,
     "total_ratio": 1.0743464131791725,
     "pass": true
    },
    "rev": {
     "remote_ratio": 0.7358833895188477,
     "total_ratio": 1.0743464131791725,
     "pass": true
    }
   },
   "pass": true
  },
  "bfly": {
   "per_order": {
    "fwd": {
     "remote_ratio": 0.7808926720695923,
     "total_ratio": 1.0565288083582414,
     "pass": true
    },
    "rev": {
     "remote_ratio": 0.7818441306896377,
     "total_ratio": 1.0551591940320981,
     "pass": true
    }
   },
   "pass": true
  }
 },
 "R2": {
  "dog": {
   "S1o_remote_ratio": 0.7355194606190623,
   "S1c_remote_ratio": {
    "fwd": 0.9991763714373276,
    "rev": 0.7346192154459087
   },
   "S2_remote_ratio": {
    "fwd": 0.7357876187557463,
    "rev": 0.73603662273981
   },
   "S3_remote_ratio": {
    "fwd": 0.7353662273981,
    "rev": 0.7358833895188477
   },
   "total_ratio": {
    "S1c": {
     "fwd": 1.002611151795318,
     "rev": 1.0700616339358036
    },
    "S2": {
     "fwd": 1.0722040235574881,
     "rev": 1.076488802800857
    },
    "S3": {
     "fwd": 1.0743464131791725,
     "rev": 1.0743464131791725
    }
   },
   "wasted_mb": {
    "S1c": {
     "fwd": 0.0,
     "rev": 316.29312
    },
    "S2": {
     "fwd": 325.87776,
     "rev": 316.29312
    },
    "S3": {
     "fwd": 335.4624,
     "rev": 325.87776
    }
   },
   "one_candidate_suffices": false
  },
  "bfly": {
   "S1o_remote_ratio": 0.7812324787196085,
   "S1c_remote_ratio": {
    "fwd": 1.0006626229675315,
    "rev": 0.7806887880795826
   },
   "S2_remote_ratio": {
    "fwd": 0.7810795657271014,
    "rev": 0.7809776237320964
   },
   "S3_remote_ratio": {
    "fwd": 0.7808926720695923,
    "rev": 0.7818441306896377
   },
   "total_ratio": {
    "S1c": {
     "fwd": 1.0009590297250894,
     "rev": 1.0530223559258831
    },
    "S2": {
     "fwd": 1.0547755821420621,
     "rev": 1.0563370024132235
    },
    "S3": {
     "fwd": 1.0565288083582414,
     "rev": 1.0551591940320981
    }
   },
   "wasted_mb": {
    "S1c": {
     "fwd": 0.0,
     "rev": 555.90912
    },
    "S2": {
     "fwd": 575.0784,
     "rev": 575.0784
    },
    "S3": {
     "fwd": 584.66304,
     "rev": 575.0784
    }
   },
   "one_candidate_suffices": false
  }
 },
 "R3": {
  "dog": {
   "S3": 0.0005171621207476616,
   "S2": 0.0002490039840637091,
   "S1c": 0.2645571559914189,
   "pass": true
  },
  "bfly": {
   "S3": 0.0009514586200452706,
   "S2": 0.00010194199500484611,
   "S1c": 0.2199738348879488,
   "pass": true
  }
 },
 "R4": {
  "dog": {
   "per_policy": {
    "S0": {
     "remote_pred": 51.6,
     "remote_meas": 52.208,
     "remote_err": -0.011645724793135082,
     "total_pred_mb": 4552.0,
     "total_meas_mb": 4473.80808,
     "total_err": 0.01747770995129505
    },
    "S1o": {
     "remote_pred": 37.66,
     "remote_meas": 38.4,
     "remote_err": -0.019270833333333348,
     "total_pred_mb": 4546.7,
     "total_meas_mb": 4480.541904,
     "total_err": 0.014765646079760497
    },
    "S1c/fwd": {
     "remote_pred": 51.6,
     "remote_meas": 52.165,
     "remote_err": -0.010831016965398232,
     "total_pred_mb": 4552.0,
     "total_meas_mb": 4485.489872,
     "total_err": 0.01482784041385976
    },
    "S1c/rev": {
     "remote_pred": 37.66,
     "remote_meas": 38.353,
     "remote_err": -0.01806899069173218,
     "total_pred_mb": 4625.5,
     "total_meas_mb": 4787.250384,
     "total_err": -0.03378774265507478
    },
    "S2/fwd": {
     "remote_pred": 37.66,
     "remote_meas": 38.414,
     "remote_err": -0.019628260530015207,
     "total_pred_mb": 4625.5,
     "total_meas_mb": 4796.835024,
     "total_err": -0.035718348273968026
    },
    "S2/rev": {
     "remote_pred": 37.66,
     "remote_meas": 38.427,
     "remote_err": -0.01995992401176261,
     "total_pred_mb": 4625.5,
     "total_meas_mb": 4816.004304,
     "total_err": -0.039556506177075845
    },
    "S3/fwd": {
     "remote_pred": 37.66,
     "remote_meas": 38.392,
     "remote_err": -0.019066472181704652,
     "total_pred_mb": 4661.8,
     "total_meas_mb": 4806.419664,
     "total_err": -0.030088854929418374
    },
    "S3/rev": {
     "remote_pred": 37.66,
     "remote_meas": 38.419,
     "remote_err": -0.019755849970066852,
     "total_pred_mb": 4661.8,
     "total_meas_mb": 4806.419664,
     "total_err": -0.030088854929418374
    }
   },
   "remote_within_15pct_all": true,
   "total_within_15pct_all": true
  },
  "bfly": {
   "per_policy": {
    "S0": {
     "remote_pred": 59.04,
     "remote_meas": 58.857,
     "remote_err": 0.0031092308476476926,
     "total_pred_mb": 5535.8,
     "total_meas_mb": 5466.858704,
     "total_err": 0.012610769681966838
    },
    "S1o": {
     "remote_pred": 45.68,
     "remote_meas": 45.981,
     "remote_err": -0.0065461821187012825,
     "total_pred_mb": 5376.7,
     "total_meas_mb": 5297.710288,
     "total_err": 0.014910160749809442
    },
    "S1c/fwd": {
     "remote_pred": 59.04,
     "remote_meas": 58.896,
     "remote_err": 0.0024449877750611915,
     "total_pred_mb": 5535.8,
     "total_meas_mb": 5472.101584,
     "total_err": 0.011640576298190375
    },
    "S1c/rev": {
     "remote_pred": 45.68,
     "remote_meas": 45.949,
     "remote_err": -0.005854316742475274,
     "total_pred_mb": 5678.8,
     "total_meas_mb": 5756.724432,
     "total_err": -0.013536244946317
    },
    "S2/fwd": {
     "remote_pred": 45.68,
     "remote_meas": 45.972,
     "remote_err": -0.0063516923344645315,
     "total_pred_mb": 5678.8,
     "total_meas_mb": 5766.309072,
     "total_err": -0.01517592465255213
    },
    "S2/rev": {
     "remote_pred": 45.68,
     "remote_meas": 45.966,
     "remote_err": -0.006221990166644931,
     "total_pred_mb": 5678.8,
     "total_meas_mb": 5774.845136,
     "total_err": -0.016631638379575042
    },
    "S3/fwd": {
     "remote_pred": 45.68,
     "remote_meas": 45.961,
     "remote_err": -0.0061138791584168795,
     "total_pred_mb": 5865.5,
     "total_meas_mb": 5775.893712,
     "total_err": 0.015513839497051984
    },
    "S3/rev": {
     "remote_pred": 45.68,
     "remote_meas": 46.017,
     "remote_err": -0.007323380489819065,
     "total_pred_mb": 5865.5,
     "total_meas_mb": 5768.406224,
     "total_err": 0.016831993488258812
    }
   },
   "remote_within_15pct_all": true,
   "total_within_15pct_all": true
  }
 },
 "R5_invalid_runs": {}
}
```

**Verdict: [DESCRIPTIVE validity] GO (R1 holds for both workloads; next: M3-S2 GPU validation, to be preregistered)**
