# ExpD C / D reproduction - reading (2026-10-24; generated comparison in `expD_repro_report.md`)

24 reproduction runs (`expDR_C`, `expDR_D`; commit a0fbae6), all valid under the frozen expD rules; the frozen runs
(`expD_C`, `expD_D`; commit 656dde6) are unchanged.

**The corrected code runs the specified scenario.** In every reproduction run the source generated during the
placement window (15-16 chunks before the move; 0 in the frozen runs), the handoff happened at call 46-47 instead of
30, the event order A:exec_start < A:first_output < move < A:exec_stop held in 12 / 12 runs per scenario, and the
handoff waited for the source's chunk boundary (median 0.27-0.28 s; 0.002 s in the frozen runs).

**What changed in the numbers.** Only the latencies measured from the move, and only by the boundary wait:
bind-ready +0.24 to +0.35 s and TTFO +0.26 to +0.36 s in every configuration (C: Full OTTER 4.94 -> 5.18 s, no
placement 15.42 -> 15.67 s; D: Full OTTER 15.46 -> 15.79 s, oracle 4.90 -> 5.25 s). Everything else is unchanged to
the third decimal: placement fraction x 0.716 (placement throughput was not affected by the source's generation
load), B_source, B_post, B_fwd, and the rejoin delay (6-7 calls; the transferred Sink is one promotion old at call 47
on dog, with no visible effect on rejoin).

**Verdicts.** G4 SUPPORTED in both sets (reproduction margin 5.18 s vs 10.64 s); G5 NOT SUPPORTED in both sets with
the same clause pattern ((a) pass, (b)-(d) fail on bytes). **No conclusion changed.** The two unmeasured channels of
the impact report (Sink staleness, placement contention) had no measurable effect in C / D.

**Recommendation for the paper (decision pending):** cite the reproduction set for scenarios C and D, since it runs
the scenario as specified and includes the boundary wait, and keep the frozen set in the artifact with the disposition
note. For N and V (not reproduced), the retained verdicts carry the stated limitation and the +0.24-0.36 s offset
measured here as the expected size of the effect.
