# RD Phase 1 verdicts

Valid runs 100 / 100; stops: none
Determinism (median |dPSNR|, repeat vs first): {'butterfly-feeding-slow-motion': 0.0, 'audi-snow-trail': 0.0, 'train': 0.0, 'dog': 0.0}
**Overall: UNCLASSIFIED for 2 of 3 refresh-heavy workloads**

| workload | class | D (drop d0->d100 by anchor; max rise) | R (median dR; positive / 8) | I | E |
|---|---|---|---|---|---|
| butterfly-feeding-slow-motion | **EPHEMERAL** | False (155: 6.4 / 2.6, 175: 4.6 / 5.8) | False (-0.0; 3) | False | True |
| audi-snow-trail | **UNCLASSIFIED** | False (155: 7.8 / 0.7, 175: 4.9 / 1.4) | False (0.0; 6) | False | False |
| train | **UNCLASSIFIED** | False (155: 12.7 / 1.4, 175: 2.0 / 0.1) | False (0.0; 5) | False | False |
| dog | **NOT REPRODUCED** | False (155: 1.7 / 4.6, 175: 1.2 / 2.8) | False (0.0; 6) | False | False |

Terminal PSNR T (dB), crossing (x) / sustained (s):

| workload | anchor | r1 d0 | r1 d10 | r1 d25 | r1 d50 | r1 d75 | r1 d100 | r3c d25 | r3c d50 | r3c d75 | r3c d100 | r3e d0 | r3e d75 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| butterfly-feeding-slow-motion | 155 | 34.6 xs | 37.2 xs | 33.5 xs | 29.1  | 28.8  | 28.2  | 33.6 xs | 29.1  | 28.8  | 28.2  | 30.8  | 28.4  |
| butterfly-feeding-slow-motion | 175 | 34.1 x | 39.9 xs | 36.2 xs | 31.6 x | 29.7  | 29.4  | 36.3 xs | 31.7 x | 29.7  | 29.4  | 33.8 x | 29.4  |
| audi-snow-trail | 155 | 35.2 x | 35.9 x | 30.4  | 28.1  | 27.8  | 27.4  | 30.4  | 28.1  | 27.8  | 27.4  | 33.3 x | 29.6  |
| audi-snow-trail | 175 | 32.4 xs | 33.8 x | 32.0 x | 27.6  | 26.7  | 27.5  | 31.9 x | 27.6  | 26.7  | 27.5  | 30.7  | 28.7  |
| train | 155 | 44.7 xs | 44.1 xs | 45.5 xs | 33.8 x | 33.8 x | 31.9  | 43.8 xs | 33.8 x | 33.8 x | 31.9  | 40.0 xs | 33.2 x |
| train | 175 | 35.6 xs | 35.5 xs | 34.8 x | 35.0 x | 34.1 x | 33.6 x | 34.8 x | 35.0 x | 34.0 x | 33.6 x | 35.4 xs | 32.5  |
| dog | 155 | 45.0 xs | 49.6 xs | 49.6 xs | 49.6 xs | 45.7 xs | 43.4 xs | 49.6 xs | 49.7 xs | 45.5 xs | 43.3 xs | 45.0 xs | 42.8 xs |
| dog | 175 | 46.7 xs | 49.6 xs | 47.9 xs | 48.0 xs | 48.0 xs | 45.6 xs | 47.9 xs | 47.9 xs | 47.9 xs | 45.5 xs | 49.3 xs | 45.4 xs |
