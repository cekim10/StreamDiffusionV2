# M3E verdicts (frozen preregistration abf74d6)

| hypothesis | verdict |
|---|---|
| H1 | SUPPORTED |
| H2 | SUPPORTED |
| H3 | NOT EVALUABLE (< 3 valid reps or cap event not fired) |
| H5 | SUPPORTED |
| H4 | SUPPORTED |
| H6 | NOT EVALUABLE (a scenario not evaluable) |
| H7 | NOT EVALUABLE (a scenario not evaluable) |

**M3-v2 is reported as the end-to-end M3 (H1, H2, H4 supported; H3, H5 not failed)**

| scenario | policy | valid / all | bind-ready (s) | TTFO (s) | B_source | total net | re-plans (probes) per rep | chunk s move->bind | dup bytes | net sessions |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | restart | 3 / 3 | 57.226 | 1.06 | 1.260 | 1.260 | [0, 0, 0] ([0, 0, 0]) | 0.5449 | [0, 0, 0] | [{'restored_sessions': 3, 'makespan_s': 72.38524770736694, 'first_restored': {'median': 71.93329811096191, 'max': 72.38524770736694, 'all': [71.0863254070282, 71.93329811096191, 72.38524770736694]}}, {'restored_sessions': 3, 'makespan_s': 72.34253287315369, 'first_restored': {'median': 71.89297604560852, 'max': 72.34253287315369, 'all': [71.04099535942078, 71.89297604560852, 72.34253287315369]}}, {'restored_sessions': 3, 'makespan_s': 72.31205201148987, 'first_restored': {'median': 71.8566620349884, 'max': 72.31205201148987, 'all': [70.98051071166992, 71.8566620349884, 72.31205201148987]}}] |
| S1 | split | 3 / 3 | 43.225 | 1.01 | 1.017 | 1.382 | [0, 0, 0] ([0, 0, 0]) | 0.5432 | [0, 0, 0] | [{'restored_sessions': 3, 'makespan_s': 55.78219413757324, 'first_restored': {'median': 55.705793619155884, 'max': 55.78219413757324, 'all': [55.78219413757324, 55.705793619155884, 55.67238807678223]}}, {'restored_sessions': 3, 'makespan_s': 55.7619252204895, 'first_restored': {'median': 55.673768758773804, 'max': 55.7619252204895, 'all': [55.7619252204895, 55.673768758773804, 55.643208503723145]}}, {'restored_sessions': 3, 'makespan_s': 55.74738264083862, 'first_restored': {'median': 55.670995235443115, 'max': 55.74738264083862, 'all': [55.74738264083862, 55.670995235443115, 55.66823601722717]}}] |
| S1 | reuse_dyn2 | 3 / 3 | 43.084 | 1.01 | 1.015 | 1.382 | [0, 0, 0] ([0, 0, 0]) | 0.5422 | [0, 0, 0] | [{'restored_sessions': 3, 'makespan_s': 55.706339597702026, 'first_restored': {'median': 55.67777156829834, 'max': 55.706339597702026, 'all': [55.67777156829834, 55.706339597702026, 55.65890836715698]}}, {'restored_sessions': 3, 'makespan_s': 55.708993434906006, 'first_restored': {'median': 55.68876886367798, 'max': 55.708993434906006, 'all': [55.708993434906006, 55.68876886367798, 55.67557954788208]}}, {'restored_sessions': 3, 'makespan_s': 55.77943420410156, 'first_restored': {'median': 55.68343162536621, 'max': 55.77943420410156, 'all': [55.77943420410156, 55.683037996292114, 55.68343162536621]}}] |
| S2 | restart | 3 / 3 | 15.504 | 1.01 | 2.021 | 2.021 | [0, 0, 0] ([0, 0, 0]) | 0.5417 | [0, 0, 0] | - |
| S2 | split | 3 / 3 | 78.532 | 0.98 | 1.032 | 2.024 | [0, 0, 0] ([0, 0, 0]) | 0.5415 | [0, 0, 0] | - |
| S2 | reuse_dyn2 | 3 / 3 | 20.714 | 1.05 | 1.180 | 2.028 | [2, 2, 2] ([1, 1, 1]) | 0.5424 | [0, 0, 0] | - |
| S2 | reuse_aware_in | 3 / 3 | 52.134 | 1.04 | 1.032 | 2.026 | [0, 0, 0] ([0, 0, 0]) | 0.5420 | [0, 0, 0] | - |
| S3 | restart | 3 / 3 | 118.499 | 0.98 | 2.019 | 2.019 | [0, 0, 0] ([0, 0, 0]) | 0.5434 | [0, 0, 0] | - |
| S3 | split | 3 / 3 | 117.517 | 1.05 | 1.034 | 2.028 | [0, 0, 0] ([0, 0, 0]) | 0.5429 | [0, 0, 0] | - |
| S3 | reuse_dyn2 | 2 / 3 | 117.440 | 1.06 | 1.035 | 2.028 | [0, 0] ([0, 0]) | 0.5427 | [0, 0] | - |
| S4 | restart | 3 / 3 | 15.335 | 1.11 | 2.028 | 2.028 | [0, 0, 0] ([0, 0, 0]) | 0.5404 | [0, 0, 0] | - |
| S4 | split | 3 / 3 | 15.379 | 1.11 | 1.036 | 2.031 | [0, 0, 0] ([0, 0, 0]) | 0.5411 | [0, 0, 0] | - |
| S4 | reuse_dyn2 | 3 / 3 | 15.326 | 1.04 | 1.027 | 2.026 | [0, 0, 0] ([0, 0, 0]) | 0.5408 | [0, 0, 0] | - |
| S5 | restart | 3 / 3 | 118.508 | 1.15 | 2.028 | 2.028 | [0, 0, 0] ([0, 0, 0]) | 0.5425 | [0, 0, 0] | - |
| S5 | split | 3 / 3 | 29.928 | 1.09 | 1.034 | 2.028 | [0, 0, 0] ([0, 0, 0]) | 0.5431 | [0, 0, 0] | - |
| S5 | reuse_dyn2 | 3 / 3 | 30.435 | 1.06 | 1.034 | 2.026 | [0, 0, 0] ([0, 0, 0]) | 0.5431 | [0, 0, 0] | - |

Historical M3-v1 (ExpD, cross-commit context only, not pooled):
- S1: ExpD E (v1): M1 only 57.07, M1 + M2 43.09, v1 42.82 s
- S2: ExpD F (v1): M1 only 15.36, M1 + M2 78.39, at moves 51.58, v1 15.80 s (B_source 1.19, 2 re-plans)
- S4: ExpD B rho 2 (v1): M1 only 15.52, M1 + M2 15.11, v1 15.45 s, 0 re-plans
- S3: no ExpD counterpart (N cell 10 class)
- S5: no ExpD counterpart (N cell 8 class)
