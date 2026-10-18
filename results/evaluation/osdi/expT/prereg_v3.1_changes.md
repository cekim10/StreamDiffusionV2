# Experiment T preregistration: v3 (79c0505) -> v3.1 (frozen) changes (2026-10-17)

| item | change |
|---|---|
| hysteresis timing | the migration happens at t + H once the dwell has been observed; never backdated (no future information); timing metrics start at t + H |
| T6 calibration | noise band from a separate GPU calibration block GC (1 pair x {AM, ED} x 3, run before G, never used for T6); T6 described as a limited consistency check |
| counterfactual scope | block V validates the model on "the first event-driven re-plan under a policy that afterwards follows at-moves scheduling" only; not the effect of a first re-plan inside full ED; no claim about unexecuted policies in general |
| reviewer notes added | paper wording for derived migration schedules; mobility cluster = measurement session when metadata identifies it; V_used reported next to V; restoration bytes sent during clamped seconds; C_min values are model bounds, not trace values; feasibility rule (report shortfalls, never change the frozen rules) |
| runs | GPU 36 -> 42 (GC) |
