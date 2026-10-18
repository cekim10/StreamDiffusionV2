# Experiment T preregistration: v2 (f799a74) -> v3 changes (2026-10-17)

| review item | v2 | v3 |
|---|---|---|
| 1. persistent mapping; handover vs migration | sites cycled over B, C, D (a site could change node); every tower change = migration; returns to the source site redirected | A = origin edge outside the trace; each site keeps one node for the whole run (revisits reuse the same holder); eligibility <= 3 distinct sites per window (selection effect reported from traces before any run); migration = site change persisting H = 3 s (primary); every-handover migration (H = 0) and H = 10 s, k = 2, 4 are block S sensitivity |
| 2. strata and analysis unit | tertiles of the coefficient of variation; pair-level medians | V = mean over the 7 used series of the standard deviation of available / **nominal** capacity (no blow-up at low mean; mean level L reported); trace-level aggregation by Lumos5G run file next to pair level, both required by T1/T3; cluster bootstrap by run file; at most one window per run file per cell; distinct MAWI days preferred |
| 3. T4 | primary hypothesis (harmful <= 20 %) | removed from the hypotheses; section 9 exploratory "model-estimated" re-planning effects, no verdict |
| counterfactual validation | factual gate (median <= 10 %) | factual (median <= 10 % and P90 <= 20 %) and controlled counterfactual validation: block V (ED limited to its first re-plan) vs the AM run on the same pair gives a measured first-re-plan effect to compare with the model |
| 4. C_min | 50 Mbps floor | 50 Mbps primary, stated as required by the harness (rate 0 = unshaped); clamped seconds reported per run; C_min = 10 Mbps in block S |
| T6 | <= 1.0 s band | direction only; band = max(1.0 s, 2 x median GPU rep range) |
| runs | 582 + 36 GPU | 654 + 36 GPU (S restricted to 9 pairs x {AM, ED} per condition; V 18 runs) |
