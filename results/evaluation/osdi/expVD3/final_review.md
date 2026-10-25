# VD-3 final pre-freeze review (2026-10-25)

For the review requested on 2026-10-25 before any Phase C run. Nothing here is a candidate result; no VD-3 candidate
condition has been run.

## 1. Threshold table (`vd3_thresholds.{md,json}`; written from `vd3_phaseT.json` only)

| cell | conf. | t_DINO (A) | t_dE (A) | t_dEx (A) | B: t_DINO / t_dE | C: t_DINO / t_dE |
|---|---|---|---|---|---|---|
| dog s1 OT-1 / OT-L (copied) | Y | 0.037 / 0.026 | 0.90 / 0.88 | 1.56 / 1.61 | 0.037 / 0.71; 0.026 / 0.88 | 0.004 / 0.14; 0.003 / 0.23 |
| train s0 OT-1 / OT-L (copied) | Y | 0.036 / 0.024 | 1.06 / 1.26 | 2.66 / 2.64 | 0.018 / 1.00; 0.018 / 1.18 | 0.014 / 0.73; 0.015 / 0.69 |
| train s1 OT-1 / OT-L (copied) | Y | 0.046 / 0.024 | 1.23 / 0.93 | 2.48 / 2.27 | 0.024 / 1.22; 0.022 / 0.75 | 0.014 / 0.73; 0.015 / 0.69 |
| butterfly s1 OT-1 / OT-L (copied) | Y | 0.047 / 0.027 | 0.59 / 0.75 | 3.65 / 3.50 | 0.026 / 0.54; 0.022 / 0.74 | 0.016 / 0.54; 0.011 / 0.49 |
| audi s0 OT-1 (copied) / OT-L | Y | 0.139 / 0.219 | 4.72 / 8.67 | 8.33 / 9.43 | 0.130 / 4.68; 0.202 / 7.77 | 0.042 / 0.39; 0.045 / 0.51 |
| audi s1 OT-1 / OT-L (copied) | Y | 0.148 / 0.244 | 4.86 / 8.40 | 8.28 / 9.13 | 0.153 / 4.91; 0.224 / 7.66 | 0.042 / 0.39; 0.045 / 0.51 |

Replication cells (dog, butterfly seed 0) are in the JSON. Fixed for every cell and set (engineering acceptance
criteria, not REF-derived confidence bounds): warp-error ratio <= 1.10 (one-sided), frame difference within +/- 10 %,
absolute safeguard below a REF window mean of 1.0 gray level (inactive here: REF window means >= 1.74); V1 <= REF P99
per unit; R3 excess drift <= t_DINO; cost <= 1.5 s and <= 1 MB.

**No candidate measurement was used.** `vd3_thresholds.py` refuses to write if any VD-3 condition exists in any unit
and records the check (`candidate_data_present: {}`) with the Phase T file's SHA-256 (f725401a...). The only
condition data in the units are REF, the frozen-M1 controls (VC-1 and Phase T) and, on dog / butterfly seed 0, the
VD-2 conditions, which are not inputs of the thresholds. Frozen M1 was used only as context and to state which cells
are discriminative; no threshold was tightened because of it.

## 2. Aggregation rules (`aggregate_vd3.py`; preregistration draft 7 section 4)

Phases: P1 boundary (R1), P2a content / appearance (R2a whole window + R3 late window), P2b motion / temporal (R2b),
P3 no-harm (R4), cost (R5). Per phase and cell: FAIL / DISCRIMINATIVE PASS / NON-DISCRIMINATIVE PASS (P3, cost:
PASS / FAIL). Continuity: NO-GO on any FAIL or veto; GO if every input has discriminative P1 and P2 evidence; else
INCONCLUSIVE. Identity preservation: ESTABLISHED only with discriminative P2a evidence on every input, else
INCONCLUSIVE. B and C are reported as sensitivity.

Frozen M1 under A (context): P1 violated in every confirmation cell except train OT-1 (both seeds), P2a in every one
except audi OT-L (both seeds), P2b in every one, P3 in none - so each input can produce discriminative P1, P2a and P2b
evidence.

**For confirmation - P3 reading.** With absolute REF limits after the bind, frozen M1 itself fails P3 on dog s0 / s1
OT-L (post-bind-20 warp 1.11-1.12) and butterfly s0 OT-L (content 0.002 beyond t_DINO); every one recovers fully in
the last 10 calls. Because the bind is the exact Sink in every condition, P3 is implemented as no harm relative to
frozen M1 (bind V1 <= max(REF P99, M1's); post-bind-20 not worse than M1's by more than the limits) plus full
recovery against REF in the last 10 calls. Under this reading frozen M1 passes P3 everywhere.

**Synthetic verification** (`test_vc.py` section 6): a stream inside every limit passes all phases; boundary V1,
content drift, late excess drift, +12 % warp, -13 % motion and post-bind color each fail their phase; the near-zero
warp safeguard (0.05 above 0.5 passes, 0.15 fails) and the one-sided warp check; P3 relative to frozen M1 (equal
post-bind passes, +14 % warp or a last-10 content gap fails; M1's own recovery passes); phase classes against frozen M1;
an invalid stream fails every phase; overall GO with identity ESTABLISHED; GO with identity INCONCLUSIVE (an input with
only P2b discrimination); INCONCLUSIVE (no discriminative P1 on an input); NO-GO by a P3 failure, a phase FAIL and an
inspection veto; refusal without thresholds; verdicts withheld without a recorded, keyed inspection.

## 3. Overlap disposition

Cause of the missing output (log on host D): an AttributeError before any trial (`GpuRuntime.step` reads the baseline
reference `self.base`, which the overlap script never built; the fake runtime has no such dependency, so the dry test
missed it). Fixed in 21532c3 and re-run (`vd3_overlap.json`, dog seed 0 OT-1, 5 repeats, commit 21532c3):

| order | first output (median) | generation (DiT) GPU time (median) | DR-2 decode |
|---|---|---|---|
| serial | 1.054 s | 268 ms | 0.518 s |
| overlapped (second CUDA stream) | 1.058 s | 523 ms | concurrent |

- (a) output digests equal in all 10 trials: **pass** (the event ordering is correct);
- (b) generation time under the concurrent decode 1.95 x its time alone: **fail** (limit 1.10);
- (c) first output earlier than serial: **fail** (1.058 vs 1.054 s).

**Disposition: overlap is not validated.** The report uses the serial reconstruction costs, and overlap is an
unvalidated optional optimization (on this GPU the two kernels' work did not run faster concurrently). These are
destination-side emulator times; they are not extrapolated to testbed TTFO.

## 4. Audi provenance (for completeness)

Verified reproduction; corrected W / R / N aggregates: 82 verdicts unchanged, one aggregate field (audi workload mean
TTFO 0.677 -> 0.682 s), the audi seed-0 row; the counts the paper cites unchanged; no figure reads W / R / N outputs
(`../expW/audi_s0_corrected_aggregate.md`, `../audi_s0_w2_provenance.md` sections 7-8).

## 5. Before Phase C

Confirm the P3 reading and the overlap disposition (serial costs); freeze
(`expVD3_freeze.md`, with `vd3_thresholds.json` committed).
