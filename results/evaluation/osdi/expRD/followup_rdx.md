# RD-X: exploratory real-migration follow-up to Experiment RD (plan, fixed before any run; 2026-10-20)

**Exploratory.** No hypothesis is tested and no verdict is produced; results are reported descriptively and never
merged into Experiment RD's pre-registered verdicts (`preregistration.md`, f850072), which stand as reported
(`rd_report.md`). No M1 / M2 / M3 mechanism and no frozen result is changed.

## Purpose
Experiment RD's Phase 0 showed that the in-place emulation reproduces five real runs exactly (0.00 dB per call), all at
1 Gbps. RD-X adds the one real condition RD has no real counterpart for: a **single move whose Sink arrives late
because the link is slow** (~75-80 Sink-less calls), and checks, on each real run, (a) the realized reset and bind
calls and (b) agreement with an emulation replay of exactly that realized schedule.

## Configuration (fixed)
- Real harness (`mobility_orchestrate.py`), frozen M1 + M2 policy `split`, path A -> B (one hop), all node caps
  **320 Mbps** (expected T_s ~ 43-44 s, i.e. a bind ~79 calls after the trigger), trigger **M = 80** (expected bind
  call ~159, near RD's anchor b1 = 155), warm destination, `--horizon_calls 190` (the destination generates calls
  80 .. 269), `--post_chunks 200`, `--max_run_s 600`.
- Workloads (seed 0): **butterfly-feeding-slow-motion, audi-snow-trail, dog**; **2 repetitions** each: **6 real runs**.
- Validity: the W / R / N run rules (`wrn_validity.py`), including the emulated-cap NIC checks.

## Measurements
1. Realized schedule per run: reset call = the move's call (`moves[0].call`), bind call = the destination's
   `sink_bind` call, realized Sink-less calls d = bind - reset.
2. Reference trajectory at the destination (RD section 5.1 outcomes over calls b .. b + 99): T, single crossing,
   sustained recovery, gap PSNR.
3. Emulation replay: one in-place replay per real run with its realized schedule (resets [reset], binds [bind],
   withheld Sink), same commit; **6 replays**. Agreement reported per run with the Phase 0 measures (same crossing and
   sustained outcome, |T_real - T_emul|, median and max per-call |dPSNR| over common calls); agreement is described,
   not gated.
4. Context only: the nearest Phase 1 condition (r1, d = 75, b155) for each workload.

## Recorded expectations (from RD Phase 1; not hypotheses)
butterfly: no crossing, T ~28-29 dB; audi-snow-trail: no crossing, T ~27-28 dB; dog: crosses and sustains, T ~45 dB;
replays: exact agreement (as in Phase 0). A disagreement is reported with its cause investigated, not explained away.

## Cost
6 real runs (~4-5 min each incl. node start) + 6 replays (~2.5 min each, three hosts in parallel): ~40-50 min.
