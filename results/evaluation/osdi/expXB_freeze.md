# Experiment XB - freeze record (2026-10-23)

Frozen document: `expXB/preregistration.md` (status FROZEN 2026-10-23). The freeze commit is the commit that adds this
file; its hash is recorded by git. Nothing below changes a frozen experiment, result or mechanism (M1 / M2 / M3-v2).

**Frozen at this point:** hypotheses XH1a, XH1b (descriptive), XH2-XH5; the four outcome notions (section 2.1);
delivery accounting with measured vs estimated bytes (section 2.2); switchover consistency and exactness (3.1, 3.3);
recompute input codec and accounting (3.2); validity (section 8, including `source_served_until_switch` added
2026-10-22); scenarios XB1-XB4 (section 5); the final method settings (section 4.1); the run budget (section 9).

**Evidence before the freeze (not evidence for XH1-XH5):**
- the CPU codec validation;
- the exactness gate (4 runs, GATE PASS with harness code 0b034dd);
- the calibration (35 runs plus the 8-run extension; all valid, no jitter re-calibration);
- 12 voided runs, with the harness bugs and fixes (`expXB/void_runs.md`).

**Order from here (each step waits for the previous one's review):**
1. Shakedown: `run_wrn.py xb_shk`, 27 runs, one per method and scenario; `check_xb_shakedown.py --write`. Harness checks
   only.
2. Main sweep: `run_wrn.py xb_main`, 81 runs plus 18 rule-4 alternative runs (`--cells XB1,XB2,ALT` can run on A and B
   alone; `--cells XB3,XB4` need GPU 0 on all four hosts).
3. D5 lossy-input sensitivity: `run_wrn.py xb_lossy`, 8 runs, descriptive.
4. Aggregation and report.

**Known constraint:** during the calibration, other users held GPU 0 and 1 of C and D. XB3 and XB4 can start only when
those are free. The driver waits up to 30 min for idle GPUs, then stops.

**Separate open item, not part of XB:** frozen placement-lookahead and cold-destination runs (ExpD A / C / D, N, V,
m3dev) show no source output after the trigger. This is the same EXEC_START path that voided the first XB runs, and
is reported separately (memory note; decision pending). XB's scenarios do not use that path for OTTER, Full or
Wait-for-Sink.
