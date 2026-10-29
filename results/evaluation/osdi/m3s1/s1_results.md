# M3-S1 results (expM3S1; validity: frozen)

| cell | valid | remote s | local s | cancelled | final valid/180 | final base MB | final ready s | total MB | discarded | staged | wasted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bfly ρ1 S1c/fwd | 3/3 | 58.9 | 2.0 | 2 | 0 | 1728 | 25.6 | 5472 | 3107 | 0 | 0 |
| bfly ρ1 S1c/rev | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| bfly ρ1 S1o/fwd | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| bfly ρ1 S2/fwd | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| bfly ρ1 S2/rev | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| bfly ρ1 S3/fwd | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| bfly ρ1 S3/rev | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| bfly ρ1 none/fwd | 3/3 | 58.9 | 2.0 | 2 | 0 | 1728 | 25.5 | 5467 | 3107 | 0 | 0 |
| dog ρ1 S1c/fwd | 3/3 | 52.2 | 2.0 | 2 | 0 | 1728 | 21.9 | 4485 | 2695 | 0 | 0 |
| dog ρ1 S1c/rev | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| dog ρ1 S1o/fwd | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| dog ρ1 S2/fwd | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| dog ρ1 S2/rev | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| dog ρ1 S3/fwd | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| dog ρ1 S3/rev | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| dog ρ1 none/fwd | 3/3 | 52.2 | 2.0 | 2 | 0 | 1728 | 22.0 | 4474 | 2685 | 0 | 0 |
| dog ρ2 S3/fwd | 0/3 | - | - | - | - | - | - | 0 | 0 | 0 | 0 |
| dog ρ2 none/fwd | 3/3 | 38.4 | 2.0 | 2 | 0 | 1728 | 21.6 | 2929 | 1138 | 0 | 0 |

## Rules

```
{
 "R1": {
  "dog": {
   "per_order": {},
   "pass": false
  },
  "bfly": {
   "per_order": {},
   "pass": false
  }
 },
 "R2": {
  "dog": {
   "S1o_remote_ratio": 0,
   "S1c_remote_ratio": {
    "fwd": 0.9991763714373276,
    "rev": 0
   },
   "S2_remote_ratio": {
    "fwd": 0,
    "rev": 0
   },
   "S3_remote_ratio": {
    "fwd": 0,
    "rev": 0
   },
   "total_ratio": {
    "S1c": {
     "fwd": 1.002611151795318,
     "rev": 0
    },
    "S2": {
     "fwd": 0,
     "rev": 0
    },
    "S3": {
     "fwd": 0,
     "rev": 0
    }
   },
   "wasted_mb": {
    "S1c": {
     "fwd": 0.0,
     "rev": 0
    },
    "S2": {
     "fwd": 0,
     "rev": 0
    },
    "S3": {
     "fwd": 0,
     "rev": 0
    }
   },
   "one_candidate_suffices": false
  },
  "bfly": {
   "S1o_remote_ratio": 0,
   "S1c_remote_ratio": {
    "fwd": 1.0006626229675315,
    "rev": 0
   },
   "S2_remote_ratio": {
    "fwd": 0,
    "rev": 0
   },
   "S3_remote_ratio": {
    "fwd": 0,
    "rev": 0
   },
   "total_ratio": {
    "S1c": {
     "fwd": 1.0009590297250894,
     "rev": 0
    },
    "S2": {
     "fwd": 0,
     "rev": 0
    },
    "S3": {
     "fwd": 0,
     "rev": 0
    }
   },
   "wasted_mb": {
    "S1c": {
     "fwd": 0.0,
     "rev": 0
    },
    "S2": {
     "fwd": 0,
     "rev": 0
    },
    "S3": {
     "fwd": 0,
     "rev": 0
    }
   },
   "one_candidate_suffices": false
  }
 },
 "R3": {
  "dog": {
   "S3": null,
   "S2": null,
   "S1c": null,
   "pass": false
  },
  "bfly": {
   "S3": null,
   "S2": null,
   "S1c": null,
   "pass": false
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
    "S1c/fwd": {
     "remote_pred": 51.6,
     "remote_meas": 52.165,
     "remote_err": -0.010831016965398232,
     "total_pred_mb": 4552.0,
     "total_meas_mb": 4485.489872,
     "total_err": 0.01482784041385976
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
    "S1c/fwd": {
     "remote_pred": 59.04,
     "remote_meas": 58.896,
     "remote_err": 0.0024449877750611915,
     "total_pred_mb": 5535.8,
     "total_meas_mb": 5472.101584,
     "total_err": 0.011640576298190375
    }
   },
   "remote_within_15pct_all": true,
   "total_within_15pct_all": true
  }
 },
 "R5_invalid_runs": {
  "('bfly', 1.0, 'S1c', 'rev')": [
   [
    "policy=m3s1-bfly-S1c-rev_N=1_moves=2_rho=1_rep=1_20261029-130142",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S1c-rev_N=1_moves=2_rho=1_rep=2_20261029-130847",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S1c-rev_N=1_moves=2_rho=1_rep=3_20261029-131553",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('bfly', 1.0, 'S1o', 'fwd')": [
   [
    "policy=m3s1-bfly-S1o-fwd_N=1_moves=2_rho=1_rep=1_20261029-125949",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S1o-fwd_N=1_moves=2_rho=1_rep=2_20261029-130655",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S1o-fwd_N=1_moves=2_rho=1_rep=3_20261029-131400",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('bfly', 1.0, 'S2', 'fwd')": [
   [
    "policy=m3s1-bfly-S2-fwd_N=1_moves=2_rho=1_rep=1_20261029-130232",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S2-fwd_N=1_moves=2_rho=1_rep=2_20261029-130937",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S2-fwd_N=1_moves=2_rho=1_rep=3_20261029-131643",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('bfly', 1.0, 'S2', 'rev')": [
   [
    "policy=m3s1-bfly-S2-rev_N=1_moves=2_rho=1_rep=1_20261029-130322",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S2-rev_N=1_moves=2_rho=1_rep=2_20261029-131027",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S2-rev_N=1_moves=2_rho=1_rep=3_20261029-131733",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('bfly', 1.0, 'S3', 'fwd')": [
   [
    "policy=m3s1-bfly-S3-fwd_N=1_moves=2_rho=1_rep=1_20261029-130412",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S3-fwd_N=1_moves=2_rho=1_rep=2_20261029-131117",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S3-fwd_N=1_moves=2_rho=1_rep=3_20261029-131823",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('bfly', 1.0, 'S3', 'rev')": [
   [
    "policy=m3s1-bfly-S3-rev_N=1_moves=2_rho=1_rep=1_20261029-130502",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S3-rev_N=1_moves=2_rho=1_rep=2_20261029-131207",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-bfly-S3-rev_N=1_moves=2_rho=1_rep=3_20261029-131913",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('dog', 1.0, 'S1c', 'rev')": [
   [
    "policy=m3s1-dog-S1c-rev_N=1_moves=2_rho=1_rep=1_20261029-124218",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S1c-rev_N=1_moves=2_rho=1_rep=2_20261029-124825",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S1c-rev_N=1_moves=2_rho=1_rep=3_20261029-125430",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('dog', 1.0, 'S1o', 'fwd')": [
   [
    "policy=m3s1-dog-S1o-fwd_N=1_moves=2_rho=1_rep=1_20261029-124039",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S1o-fwd_N=1_moves=2_rho=1_rep=2_20261029-124646",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S1o-fwd_N=1_moves=2_rho=1_rep=3_20261029-125252",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('dog', 1.0, 'S2', 'fwd')": [
   [
    "policy=m3s1-dog-S2-fwd_N=1_moves=2_rho=1_rep=1_20261029-124300",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S2-fwd_N=1_moves=2_rho=1_rep=2_20261029-124907",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S2-fwd_N=1_moves=2_rho=1_rep=3_20261029-125513",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('dog', 1.0, 'S2', 'rev')": [
   [
    "policy=m3s1-dog-S2-rev_N=1_moves=2_rho=1_rep=1_20261029-124343",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S2-rev_N=1_moves=2_rho=1_rep=2_20261029-124949",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S2-rev_N=1_moves=2_rho=1_rep=3_20261029-125555",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('dog', 1.0, 'S3', 'fwd')": [
   [
    "policy=m3s1-dog-S3-fwd_N=1_moves=2_rho=1_rep=1_20261029-124425",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S3-fwd_N=1_moves=2_rho=1_rep=2_20261029-125032",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S3-fwd_N=1_moves=2_rho=1_rep=3_20261029-125637",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('dog', 2.0, 'S3', 'fwd')": [
   [
    "policy=m3s1-dog-S3-fwd_N=1_moves=2_rho=2_rep=1_20261029-132103",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S3-fwd_N=1_moves=2_rho=2_rep=2_20261029-132222",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S3-fwd_N=1_moves=2_rho=2_rep=3_20261029-132341",
    [
     "no_duplicates"
    ]
   ]
  ],
  "('dog', 1.0, 'S3', 'rev')": [
   [
    "policy=m3s1-dog-S3-rev_N=1_moves=2_rho=1_rep=1_20261029-124507",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S3-rev_N=1_moves=2_rho=1_rep=2_20261029-125114",
    [
     "no_duplicates"
    ]
   ],
   [
    "policy=m3s1-dog-S3-rev_N=1_moves=2_rho=1_rep=3_20261029-125719",
    [
     "no_duplicates"
    ]
   ]
  ]
 }
}
```

**Verdict: NO DATA (no valid S0 / S3 cells for a workload)**
