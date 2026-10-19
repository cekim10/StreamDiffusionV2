# M3-v2 GPU regression on N cells 7-10 (GPU; development data, not evidence)

| cell | pass | detail |
|---|---|---|
| 7 incorrect x 0 | PASS | v2: bind 15.04 s, B_src 1.010, re-plans 0 (probes 0), valid True []; at moves: bind 15.67, B_src 1.010; v1: bind 15.22, B_src 1.226, re-plans 1; trigger ok True; records ok True; v2 re-plans:  |
| 8 incorrect x src | PASS | v2: bind 15.03 s, B_src 1.000, re-plans 0 (probes 0), valid True []; at moves: bind 15.06, B_src 1.000; v1: bind 18.64, B_src 1.027, re-plans 3; trigger ok True; records ok True; v2 re-plans:  |
| 9 incorrect x hold | PASS | v2: bind 20.42 s, B_src 1.423, re-plans 2 (probes 1), valid True []; at moves: bind 113.10, B_src 1.000; v1: bind 15.01, B_src 1.450, re-plans 3; trigger ok True; records ok True; v2 re-plans: +10.3s B->{'A': 4} probe eta 95.0->6.4 I 1000 c {'A': 1000, 'B': 67}; +12.9s B->{'A': 170} eta 90.5->6.1 I 1000 c {'A': 1000, 'B': 67} |
| 10 incorrect x in | PASS | v2: bind 117.67 s, B_src 1.010, re-plans 1 (probes 1), valid True []; at moves: bind 118.04, B_src 1.000; v1: bind 114.28, B_src 1.226, re-plans 27; trigger ok True; records ok True; v2 re-plans: +18.9s B->{'A': 4} probe eta 146.4->91.5 I 67 c {'A': 1000, 'B': 42} |

Overall: PASS
