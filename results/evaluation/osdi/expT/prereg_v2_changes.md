# Experiment T preregistration: v1 (a720b5d) -> v2 changes (2026-10-17)

| review item | v1 | v2 |
|---|---|---|
| 1. exact T1-T6 | short statements with [proposed] thresholds | section 5 defines T_r, S, R_s, dS_s; section 6.1 gives each hypothesis's metric, decision rule (SUPPORTED / NOT SUPPORTED / NOT EVALUABLE) and the reason for each value (T1 1.05 = run-to-run spread of Experiment D repeated-scenario bind-ready, ~5 %; 0.90 = about twice that; T3 0.05 Sink = spread of OTTER source bytes in D, 1.02-1.06; T4 20 % = judgement, no prior data; T2, T5 inherit Experiment D G7) |
| 2. k sensitivity | k = 2, 4 optional | default k = 1; ranking-by-first-appearance clustering; trigger = site change between consecutive seconds, no hysteresis; site-to-node assignment incl. returns to the source site; k = 2, 4 as block S, reported separately (6.3) and never changing primary verdicts |
| 3. MAWI framing | "cross-traffic" source | "measured source of traffic variability", explicitly not a representative edge-metro trace; residual capacity max(C(1 - u), 50 Mbps) with assumptions R1-R4 and limitations (3.2); pre-July-2023 days only |
| 4. counterfactual | outline | section 9: state capture, two branches, per-run model validation, gate (median error <= 10 %, eps = P90 of absolute error fixed before classification), five classes incl. ambiguous and costly-without-benefit, cost aggregation, controls cross-check |
| 5. Sink promotion | in the reporting rule | separate applicability study (section 10), events listed with count, timing and volume, invalidated runs reported |
| 6. freeze scope | "before the freeze" list | section 0: what is frozen before any formal outcome; implementation, loopback tests and shakedown after the freeze; measurement-bug fixes as dated errata |
