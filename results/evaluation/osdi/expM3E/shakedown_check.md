# M3E shakedown check

**PASS** (16 / 16 runs)

| scenario | policy | result | details |
|---|---|---|---|
| S1 | restart | PASS | {'dir': 'policy=restart_bw=1000_rho=2_tm=7.025_hybrid=3_rep=1_20261020-184305', 'bind': '56.926', 'ttfo': 1.2041945457458496, 'B_source': 1.2625638834102202, 'replans': 0, 'probes': 0, 'cap': 0, 'stop': 'rejoin+tail'} |
| S1 | split | PASS | {'dir': 'policy=split_bw=1000_rho=2_tm=7.025_hybrid=3_rep=1_20261020-184507', 'bind': '43.261', 'ttfo': 1.1300907135009766, 'B_source': 1.019449176548905, 'replans': 0, 'probes': 0, 'cap': 0, 'stop': 'rejoin+tail'} |
| S1 | reuse_dyn2 | PASS | {'dir': 'policy=reuse_dyn2_bw=1000_rho=2_tm=7.025_hybrid=3_rep=1_20261020-184647', 'bind': '43.090', 'ttfo': 1.008375644683838, 'B_source': 1.0121557353430657, 'replans': 0, 'probes': 0, 'cap': 0, 'stop': 'rejoin+tail'} |
| S2 | restart | PASS | {'dir': 'policy=restart_bw=1000_rho=2_tm=7.025_ev=Dge0.5Cout62.5_rep=1_20261020-180305', 'bind': '15.867', 'ttfo': 1.115077018737793, 'B_source': 2.0283752100233623, 'replans': 0, 'probes': 0, 'cap': 1, 'stop': 'rejoin+tail'} |
| S2 | split | PASS | {'dir': 'policy=split_bw=1000_rho=2_tm=7.025_ev=Dge0.5Cout62.5_rep=1_20261020-180416', 'bind': '79.480', 'ttfo': 1.0774240493774414, 'B_source': 1.031604911891971, 'replans': 0, 'probes': 0, 'cap': 1, 'stop': 'rejoin+tail'} |
| S2 | reuse_dyn2 | PASS | {'dir': 'policy=reuse_dyn2_bw=1000_rho=2_tm=7.025_ev=Dge0.5Cout62.5_rep=1_20261020-180631', 'bind': '20.809', 'ttfo': 1.0549180507659912, 'B_source': 1.179904883077373, 'replans': 2, 'probes': 1, 'cap': 1, 'stop': 'rejoin+tail'} |
| S2 | reuse_aware_in | PASS | {'dir': 'policy=reuse_aware_in_bw=1000_rho=2_tm=7.025_ev=Dge0.5Cout62.5_rep=1_20261020-180748', 'bind': '52.266', 'ttfo': 1.00169038772583, 'B_source': 1.0267426177547447, 'replans': 0, 'probes': 0, 'cap': 1, 'stop': 'rejoin+tail'} |
| S3 | restart | PASS | {'dir': 'policy=restart_bw=1000_rho=2_tm=7.025_ev=Dge0.5Din62.5_rep=1_20261020-181556', 'bind': '118.572', 'ttfo': 1.264129877090454, 'B_source': 2.038099798297815, 'replans': 0, 'probes': 0, 'cap': 1, 'stop': 'rejoin+tail'} |
| S3 | split | PASS | {'dir': 'policy=split_bw=1000_rho=2_tm=7.025_ev=Dge0.5Din62.5_rep=1_20261020-181850', 'bind': '118.222', 'ttfo': 1.1038126945495605, 'B_source': 1.0340360589605841, 'replans': 0, 'probes': 0, 'cap': 1, 'stop': 'rejoin+tail'} |
| S3 | reuse_dyn2 | PASS | {'dir': 'policy=reuse_dyn2_bw=1000_rho=2_tm=7.025_ev=Dge0.5Din62.5_rep=1_20261020-182144', 'bind': '117.847', 'ttfo': 1.1493291854858398, 'B_source': 1.031604911891971, 'replans': 0, 'probes': 0, 'cap': 1, 'stop': 'rejoin+tail'} |
| S4 | restart | PASS | {'dir': 'policy=restart_bw=1000_rho=2_tm=7.025_rep=1_20261020-175310', 'bind': '15.415', 'ttfo': 1.1311893463134766, 'B_source': 2.0283752100233623, 'replans': 0, 'probes': 0, 'cap': 0, 'stop': 'rejoin+tail'} |
| S4 | split | PASS | {'dir': 'policy=split_bw=1000_rho=2_tm=7.025_rep=1_20261020-175421', 'bind': '15.475', 'ttfo': 1.13387131690979, 'B_source': 1.0413295001664236, 'replans': 0, 'probes': 0, 'cap': 0, 'stop': 'rejoin+tail'} |
| S4 | reuse_dyn2 | PASS | {'dir': 'policy=reuse_dyn2_bw=1000_rho=2_tm=7.025_rep=1_20261020-175533', 'bind': '15.487', 'ttfo': 1.114680528640747, 'B_source': 1.0388983530978104, 'replans': 0, 'probes': 0, 'cap': 0, 'stop': 'rejoin+tail'} |
| S5 | restart | PASS | {'dir': 'policy=restart_bw=1000_rho=2_tm=7.025_ev=Dge0.5Aout62.5_rep=1_20261020-183053', 'bind': '118.883', 'ttfo': 1.2227599620819092, 'B_source': 2.0332375041605886, 'replans': 0, 'probes': 0, 'cap': 1, 'stop': 'rejoin+tail'} |
| S5 | split | PASS | {'dir': 'policy=split_bw=1000_rho=2_tm=7.025_ev=Dge0.5Aout62.5_rep=1_20261020-183348', 'bind': '30.606', 'ttfo': 1.017559289932251, 'B_source': 1.031604911891971, 'replans': 0, 'probes': 0, 'cap': 1, 'stop': 'rejoin+tail'} |
| S5 | reuse_dyn2 | PASS | {'dir': 'policy=reuse_dyn2_bw=1000_rho=2_tm=7.025_ev=Dge0.5Aout62.5_rep=1_20261020-183513', 'bind': '30.364', 'ttfo': 1.1081013679504395, 'B_source': 1.0364672060291973, 'replans': 0, 'probes': 0, 'cap': 1, 'stop': 'rejoin+tail'} |
