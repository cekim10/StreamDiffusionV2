# WX verdicts (frozen preregistration a181126)

Per workload, imported frozen hypotheses; dog = frozen R / M3E verdicts. Generality: supported on k of 4 tested inputs (seed 0, one model).

| config | hypothesis | dog (frozen) | butterfly | audi-snow-trail | train | supported on |
|---|---|---|---|---|---|---|
| X1 | R-H1 | SUPPORTED | SUPPORTED (B_src 3.000 / 1.008, reduction 99.6%) | SUPPORTED (B_src 3.000 / 1.011, reduction 99.5%) | SUPPORTED (B_src 3.000 / 1.008, reduction 99.6%) | 4 / 4 |
| X1 | R-H2 | SUPPORTED | SUPPORTED (discarded M1+M2 0.023, M1 only 2.000) | SUPPORTED (discarded M1+M2 0.020, M1 only 2.000) | SUPPORTED (discarded M1+M2 0.025, M1 only 2.000) | 4 / 4 |
| X1 | R-H3(a) | SUPPORTED | SUPPORTED (bind 15.685 vs 15.858) | SUPPORTED (bind 15.632 vs 15.688) | SUPPORTED (bind 15.843 vs 15.446) | 4 / 4 |
| X2 | R-H1 | SUPPORTED | SUPPORTED (B_src 1.520 / 1.036, reduction 93.0%) | SUPPORTED (B_src 1.518 / 1.036, reduction 93.0%) | SUPPORTED (B_src 1.518 / 1.029, reduction 94.4%) | 4 / 4 |
| X2 | R-H2 | SUPPORTED | SUPPORTED (discarded M1+M2 0.053, M1 only 0.520) | SUPPORTED (discarded M1+M2 0.053, M1 only 0.518) | SUPPORTED (discarded M1+M2 0.044, M1 only 0.518) | 4 / 4 |
| X2 | R-H3(a) | SUPPORTED | SUPPORTED (bind 15.486 vs 15.790) | SUPPORTED (bind 15.534 vs 15.520) | SUPPORTED (bind 15.368 vs 15.446) | 4 / 4 |
| X3 | R-H1 | SUPPORTED | SUPPORTED (B_src 2.033 / 1.039, reduction 96.2%) | SUPPORTED (B_src 2.026 / 1.036, reduction 96.4%) | SUPPORTED (B_src 2.028 / 1.039, reduction 96.2%) | 4 / 4 |
| X3 | R-H2 | SUPPORTED | SUPPORTED (discarded M1+M2 0.058, M1 only 1.033) | SUPPORTED (discarded M1+M2 0.056, M1 only 1.026) | SUPPORTED (discarded M1+M2 0.058, M1 only 1.028) | 4 / 4 |
| X3 | R-H3(a) | SUPPORTED | SUPPORTED (bind 15.600 vs 15.654) | SUPPORTED (bind 15.368 vs 15.443) | SUPPORTED (bind 15.400 vs 15.475) | 4 / 4 |
| X3 | H4 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X3 | H6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X3 | H7 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X4 | H1 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X4 | H6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X4 | H7 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X5 | H2 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X5 | H6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X5 | H7 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X6 | H3 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X6 | H6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |
| X6 | H7 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED | 4 / 4 |

Notes (descriptive):
- bfly X2 manipulation_check: MET (M1 only discarded 0.520 vs 0.375)
- bfly X3 manipulation_check: MET (M1 only discarded 1.033 vs 0.750)
- bfly X5 H2_source_rationale: {'M1_only_redundant_sinks': 1.023512915886136, 'M3v2_redundant_sinks': 0.17747373600875993, 'fraction_removed': 0.8266033254156769}
- audi X2 manipulation_check: MET (M1 only discarded 0.518 vs 0.375)
- audi X3 manipulation_check: MET (M1 only discarded 1.026 vs 0.750)
- audi X5 H2_source_rationale: {'M1_only_redundant_sinks': 1.0332375041605886, 'M3v2_redundant_sinks': 0.18476717721459934, 'fraction_removed': 0.8211764705882353}
- train X2 manipulation_check: MET (M1 only discarded 0.518 vs 0.375)
- train X3 manipulation_check: MET (M1 only discarded 1.028 vs 0.750)
- train X5 H2_source_rationale: {'M1_only_redundant_sinks': 1.021081768817523, 'M3v2_redundant_sinks': 0.1823360301459862, 'fraction_removed': 0.8214285714285715}
