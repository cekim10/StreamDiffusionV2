# WX shakedown check

**PASS** (21 / 21 runs)

| workload | config | policy | result | details |
|---|---|---|---|---|
| bfly | X3 | restart | PASS | {'bind': '16.031', 'B_source': 2.038099798297815, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| bfly | X3 | split | PASS | {'bind': '15.381', 'B_source': 1.031604911891971, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| bfly | X3 | reuse_dyn2 | PASS | {'bind': '15.452', 'B_source': 1.0291737648233579, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| bfly | X5 | restart | PASS | {'bind': '15.500', 'B_source': 2.035668651229202, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| bfly | X5 | split | PASS | {'bind': '77.783', 'B_source': 1.0388983530978104, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| bfly | X5 | reuse_dyn2 | PASS | {'bind': '20.768', 'B_source': 1.1847671772145993, 'replans': 2, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| bfly | X5 | reuse_aware_in | PASS | {'bind': '51.992', 'B_source': 1.0340360589605841, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| audi | X3 | restart | PASS | {'bind': '15.537', 'B_source': 2.035668651229202, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| audi | X3 | split | PASS | {'bind': '15.286', 'B_source': 1.031604911891971, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| audi | X3 | reuse_dyn2 | PASS | {'bind': '15.398', 'B_source': 1.0291737648233579, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| audi | X5 | restart | PASS | {'bind': '15.507', 'B_source': 2.0308063570919757, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| audi | X5 | split | PASS | {'bind': '78.991', 'B_source': 1.031604911891971, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| audi | X5 | reuse_dyn2 | PASS | {'bind': '20.827', 'B_source': 1.17747373600876, 'replans': 2, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| audi | X5 | reuse_aware_in | PASS | {'bind': '53.378', 'B_source': 1.0267426177547447, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| train | X3 | restart | PASS | {'bind': '15.412', 'B_source': 2.0259440629547494, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| train | X3 | split | PASS | {'bind': '15.597', 'B_source': 1.051054088440876, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| train | X3 | reuse_dyn2 | PASS | {'bind': '15.280', 'B_source': 1.0267426177547447, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| train | X5 | restart | PASS | {'bind': '15.510', 'B_source': 2.0332375041605886, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| train | X5 | split | PASS | {'bind': '78.247', 'B_source': 1.0388983530978104, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| train | X5 | reuse_dyn2 | PASS | {'bind': '21.101', 'B_source': 1.1847671772145993, 'replans': 2, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
| train | X5 | reuse_aware_in | PASS | {'bind': '53.308', 'B_source': 1.0218803236175182, 'replans': 0, 'applicable': True, 'stop': 'window_exhausted', 'rejoin': False} |
