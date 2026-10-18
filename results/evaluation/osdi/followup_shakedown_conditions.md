# W / R / N GPU shakedown - pass conditions (written before any W / R / N GPU run; frozen with the preregistrations)

Execution correctness only. No hypothesis threshold, matrix entry or rule is set or changed from shakedown results;
shakedown runs are not part of any verdict. A failed condition is a correctness bug: it is fixed, recorded as a dated
amendment in the affected document if it changes frozen text, and the shakedown is repeated.

## Prerequisites (CPU / loopback, before the GPU)

- P1 `tools/eval/expw_loop_audit.py` labels equal the labels the runners write (unit test on the arithmetic).
- P2 loopback dry runs (fake nodes) of: R rho 0.5 and rho 8 with `--hybrid_net 3` for restart / split / reuse_dyn; N cell 9
  and cell 6 for reuse_aware_in / reuse_dyn; W2 fixed horizon for reuse_dyn and cold. Each completes, writes the new
  record fields, and the N trigger fires once at ceil(|S| / 2).

## GPU shakedown configurations (elves-01..04, GPU 0)

- **W:** unit mbike-trick, seed 0 (32-frame clip: cuts every 8 calls): W1 run (330 calls) on elves-02 GPU 0 (the W2
  destination host, so W-b / W-c compare like with like) and W2 OTTER event-driven and Cold restart (M = 34, horizon 133).
- **R:** rho 0.5, c = 3: restart, split, reuse_dyn, 1 rep each.
- **N:** cell 9 (incorrect x hold): reuse_aware_in and reuse_dyn, 1 rep each.

## Pass conditions

| id | condition |
|---|---|
| W-a | the W1 run completes calls 0-329 and logs a value fingerprint for every call, layer and sink slot |
| W-b | reproducibility / alignment: the per-call output-frame SHA-256 of the W1 run equals the destination node baseline's for every call 0-163 of the same unit (same model, seed, noise, input) |
| W-c | the value fingerprints of the W1 run equal the node baseline's for calls 0-163 |
| W-d | at every call where sink-slot positions change without a value-fingerprint change (t_refresh realignment), no promotion is counted; every counted promotion has a value change |
| W-e | the call-class labels written for the unit equal `loop_audit.json` (cut calls 6, 14, 22, ...) |
| W-f | both W2 runs: first destination call c0 = 34; the destination generates through call 133 (fixed horizon) whatever the rejoin; PSNR recorded for every output call; the OTTER run logs `sink_bind`; the rejoin rule output (call or censored) is consistent with the logged PSNR series |
| W-g | the reference fingerprints are available for calls 34-163 so RVC can be classified (W-c) |
| R-a | three runs complete; moves at T_m = 28.10 s intervals (+- 0.2 s); valid by `expD_validity.py` (or listed with the reason) |
| R-b | split: the final owner receives forwarded fragments from a previous owner that had bound the Sink (B_fwd > 0.9 Sink), B_source,total <= 1.10; restart: the abandoned owners drop (`sink_drop` events) and B_source,total >= 2.5 |
| R-c | exposure record present for every run (background flow intervals and bytes on A's egress, coverage of I) and the exposure-valid flag computed |
| R-d | version events (owner-side promotions before the final bind) are logged per run, whatever their number |
| N-a | both runs: exactly one `cap_change` on B `out` to 62.5 Mbps; it fires when the destination C has verified ceil(|S| / 2) fragments of the set S frozen at the move (from `fragments.csv` / events) |
| N-b | the trigger record (time, |S|, verified count, time to Sink verified, reaction feasibility, availability count) is in `summary.json` |
| N-c | no planner input contains the changed cap (planners see only `known_caps`) |
| N-d | a run that reaches `max_run_s` or the call window keeps its directory and records timeout status, last progress, bytes and re-plans (checked with a forced short `max_run_s` in the loopback test, P2) |

## Amendment 1 (2026-10-18, before any W / R / N GPU run; the frozen text above is unchanged)

**R-b is replaced** (correctness issue in a pass condition, found while writing the checker): its numbers (restart
B_source,total >= 2.5; split B_fwd > 0.9) come from the c = 0 analytic model, but the R shakedown configuration is c = 3,
where the abandoned owners receive less from the contended source (each restoration slows down), so a correct harness
could fail R-b. Replacement, independent of the delivered amounts:
- **R-b'** restart: every abandoned owner (B, C) logs `sink_dropped` at its move and the final owner receives no fragment
  from a non-source node (B_fwd = 0); split: verified progress reused >= 0.9 (fragments verified at abandoned owners and
  needed by the final owner arrive from those owners, not again from A), and, if an intermediate owner bound the Sink
  before it was left (`sink_bind` at that owner before its move), the next owner received fragments from it.
No hypothesis, threshold or matrix entry is affected. N-d is checked in the loopback test (P2) as written.
