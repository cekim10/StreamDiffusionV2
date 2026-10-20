# M1 / M2 follow-up results: Experiment A (recent-KV handoff) and Task B (exact Sink reuse) - 2026-10-20

Plans and the pre-specified rules: `m1m2_followup.md` (Experiment A frozen at bfc2ce0; Task B instrumentation 5c1e826 /
f4f4d25). Data: `results/evaluation/expA_*` (40 runs, commit 52fd5ce, 2026-10-20), `results/evaluation/expW_B`
(10 block-checksum runs, commit f4f4d25). Verdicts: `wrn_results.md` section A (`tools/eval/aggregate_wrn.py`),
`expB_reuse.md` (`tools/eval/expb_reuse.py`). Frozen ExpD / W / R / N / V results, M1 / M2 / M3-v1 / M3-v2 unchanged.

## Experiment A - M1 recent-KV handoff (native bandwidth, 10 units x n in {0, 1, 2, 3} slots): **NO-GO for every n**

| n | fast-path bytes (measured, median) | TTFO (median) | Sink bind-ready | units with sustained rejoin (10 calls >= 35 dB) | terminal PSNR (median of calls 124-133) | gap PSNR (first 6 calls, median) | consumption check |
|---|---|---|---|---|---|---|---|
| 0 (frozen M1) | 2.8 MB | 0.68 s | 3.2 s | **10 / 10** | 42.3 dB | 17.0 dB | - |
| 1 | 578 MB | 1.62 s | 4.1 s | 10 / 10 | 42.1 dB | 18.8 dB | 10 / 10 ok; outputs differ from n = 0 in 10 / 10 |
| 2 | 1,153 MB | 2.47 s | 5.0 s | 10 / 10 | 42.2 dB | 19.2 dB | 10 / 10; 10 / 10 |
| 3 | 1,728 MB | 3.37 s | 5.9 s | 10 / 10 | 42.2 dB | 19.2 dB | 10 / 10; 10 / 10 |

- Decision rule (fixed before the runs): GO iff (sustained units +3 or terminal PSNR +3 dB) and TTFO <= +1.5 s. Neither
  gain exists at any n; the cost is +0.9 s TTFO and +575 MB per slot, and the same +0.9 s per slot on Sink bind-ready
  (the Sink transfer starts after the fast path). **NO-GO**, also for the paper's 1 Gbps operating point (there: +4.6 s per
  slot, not run).
- The transferred slots were consumed (positions and value sums identical at the destination's first call, outputs
  differ from n = 0 in every unit); their effect is a +1.8-2.2 dB gap over the first 6 calls, not the ~10 dB the frozen
  ablation measured when the recent window was dropped *with the Sink present*: without a bound Sink the recent slots
  alone do not restore continuity.
- **Observation (not a hypothesis of A):** at native bandwidth every unit sustains 35 dB from 6-11 calls after the bind,
  including the four clips that never sustained it at 1 Gbps in W2 (audi-snow-trail, butterfly, circus-ball-act, train).
  Sustained continuity on refresh-heavy clips depends on how soon the Sink binds (here ~3.2 s / ~4 calls after the
  trigger vs ~26 calls at 1 Gbps), not on the recent window. W2's non-sustained units are a bandwidth effect.

## Task B - exact Sink block changes and fragment reuse (measured; 10 units x 330 calls)

Per call, every (layer, key, row, sink slot) block (360 per Sink) was checksummed; a change is attributed to **refresh**
(K and V of a slot change together with a position jump) or **realignment** (K only, the slot's position shifted by the
same delta as the recent slots at a t_refresh rewind). `other` = 0 in every unit.

| unit | refresh events (slot-rows, calls 30-329) | realign events | realign calls | 412-fragment reuse after 25 calls: with realign K changes / refresh-only | after 50 calls | update bandwidth, sync every 25 calls (with realign) |
|---|---|---|---|---|---|---|
| dog s0 / s1 | 9 / 10 | 527 / 528 | 48, 49, 93, 94, 138, 139, 183, 184 (two rows one call apart, every ~45 calls) | 0.79 / 0.99 | 0.64 / 0.99 | 120 Mbps |
| train s0 / s1 | 83 / 78 | 650 / 656 | same | 0.74 / 0.95 | 0.56 / 0.94 | 171 Mbps |
| audi-snow-trail s0 / s1 | 139 / 144 | 640 / 651 | same | 0.71 / 0.92 | 0.54 / 0.91 | 188-195 Mbps |
| circus-ball-act s0 / s1 | 233 / 244 | 637 / 638 | same | 0.70 / 0.92 | 0.54 / 0.92 | 196-200 Mbps |
| butterfly-feeding-slow-motion s0 / s1 | 356 / 371 | 668 / 676 | same | 0.66 / 0.88 | 0.50 / 0.89 | 234-236 Mbps |

- **Realignment, not refresh, dominates Sink byte churn.** Every ~45 calls the t_refresh rewind re-rotates the keys of
  nearly all sink slots (the early first-pass promotions replace the original sink frames in most layers, after which
  every sink slot is "movable" at a rewind): ~66-85 of the 180 slot-rows per realign call, i.e. half the Sink's K bytes
  (25 % of the Sink) every 45 calls. Refresh changes are 9-371 slot-rows per 300 calls.
- **The earlier V-only estimate was wrong for the quantity that matters.** It reported 94 % (median) of fragments
  reusable after 50 calls; the exact figure **including realignment is 50-64 %** on the current 412 x 4 MiB table
  (66-79 % after 25 calls), and the update bandwidth for a holder kept current every 25 calls is **120-236 Mbps**, not
  ~30 Mbps. The refresh-only numbers (88-99 % after 50 calls) are what *canonicalized keys* would give, if they
  reconstruct correctly.
- **Re-rotated keys are not bitwise equivalent** (round-trip test, sink K blocks rotated +d then -d with the model's own
  `_shift_temporal_rope`, d in {1, 5, 45}): 94-98 % of the bf16 elements equal, max abs error 0.125 (one bf16 ulp at
  |k| ~ 16-32), max error 0.4 % of max |k|; composition (d then 3 vs d + 3) max abs error 0.125. Every W2 / A run already
  binds through one such re-rotation (rejoin at 36-55 dB), so a single re-rotation is tolerated end to end; what a
  canonical representation would add is a second rotation per transfer, whose effect on outputs is **not measured**.

## Go / no-go

| proposal | decision | basis |
|---|---|---|
| A: recent-KV handoff (any n, native or 1 Gbps) | **NO-GO** | no sustained-recovery or terminal-PSNR gain; +0.9 s TTFO and +575 MB per slot at native, +4.6 s at 1 Gbps |
| B: exact instrumentation | done (GO) | 360 checksums / call, attribution exact (`other` = 0) |
| B: version-aware Continuity Wavefront with **realign-shifted K treated as dirty** | **GO for design** (next preregistration) | exact reuse 50-64 % after 50 calls, 66-79 % after 25 calls on the 412 table; no reconstruction risk |
| B: key canonicalization (fragment identity independent of rotation) | **conditional**: not now | not bitwise (one-ulp errors in 2-6 % of elements); needs an end-to-end PSNR test of a second re-rotation before adoption; would raise reuse to 88-99 % |
| B: rolling holder synchronization | **not now** (as instructed) | 120-236 Mbps at a 25-call period with realign churn; ~3-30 Mbps refresh-only |

Corrections to `m1m2_followup.md`: the "94 % reusable" estimate and the "~30 Mbps" update bandwidth are superseded by
the measured values above (the estimate ignored realignment and merged rows).
