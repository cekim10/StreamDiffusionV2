# XB-N - P-full at native bandwidth: descriptive sensitivity (plan, 2026-10-23)

Approved 2026-10-23 as a separate descriptive sensitivity experiment. It does not modify the frozen XB
preregistration, XH2 (a 1 Gbps hypothesis) or any XB main result. No hypothesis and no verdict: XB-N reports what
happens and compares it with the frozen 1 Gbps runs.

**Question.** Does full-state pre-copy (P-full, Llumnix-style) converge when the 1 Gbps emulated cap is removed?

**Setting.**
- XB1 (single move A -> B, trigger chunk 30, dog, seed 0), P-full at its frozen setting (thr=256:rl=10, no-shrink rule
  10 %), 3 reps.
- Emulated caps off (`--bw 0`; no application-level shaping). The bandwidth is not assumed: the run measures what the
  testbed actually delivers.

**Measured per run:**
- whether it converges (switch reason: threshold vs no_shrink / round limit);
- rounds, and dirty bytes per round;
- total bytes sent;
- per-round throughput: dirty bytes / send time, end to end through the harness (hashing, packing and sending);
- NIC receive rate at the destination (network.csv);
- final stop-and-copy bytes and duration (from the switch to the destination's resume);
- TTFO-local, delivery gap, remote-serving time;
- output equivalence after the switchover.

**Reading (fixed now).** Whatever the outcome, the paper states the result with its measured throughput:
- does not converge: mutable state defeats pre-copy even without the cap on this testbed;
- converges: pre-copy needs bandwidth that outpaces the state mutation rate (stated in bytes per second), which
  bandwidth-constrained edge links may not offer;
- converges but the final stop or local resumption stays long: reported as such.
No claim that pre-copy cannot converge in general.

**Cost.** 3 runs on GPU 0 of A and B plus one node start (~15 min), about 30 min in all. Driver:
`run_wrn.py xb_native`. Aggregation: `aggregate_xb.py --prefix N_` style tables plus the per-round throughput.
