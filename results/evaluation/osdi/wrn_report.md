# W / R / N results (GPU, 2026-10-19)

Frozen plan: `followup_prereg_freeze.md` (commit 4001882). Verdicts: `wrn_results.md` / `wrn_results.json`
(`tools/eval/aggregate_wrn.py`, frozen rules); per-unit W2 table `w2_table.csv`. Runs on elves-01..04 GPU 0, nodes
and orchestrator on commit ca7c951, 2026-10-18 23:21 to 2026-10-19 12:48 (13.4 h, 56 orchestrator invocations, no
driver failure); the W2 audi-snow-trail seed-0 configuration re-run on 2026-10-19 (section 6). **312 runs** as planned:
W1 40, W2 80 (+ 1 re-run), R 90, N 90, W-AR 12. Nothing in the planner, thresholds, workloads or criteria changed
after the freeze; the dated amendments are listed in section 7.

## 1. Outcomes

| hypothesis | verdict | basis (medians over valid reps; `wrn_results.md`) |
|---|---|---|
| W-H1 TTFO stability | **SUPPORTED** | every workload's TTFO 0.668-0.693 s (<= 1.0 s); spread 0.024 s <= 0.25 x 0.556 s service time |
| W-H2 rejoin within the horizon (all 40 units) | **SUPPORTED** | 39 of 40 units rejoin (97.5 %); the non-rejoining unit is audi-snow-trail seed 1 |
| W-H2 S1 (no RVC) | counts only | n = 4 units without any reference Sink change: 4 of 4 rejoined (36 units excluded) |
| W-H2 S2 (no cut-induced RVC) | SUPPORTED | 25 of 26 (96.2 %), 14 excluded |
| W-H3 rejoin depends on the Sink | **SUPPORTED** | Cold restart reaches 35 dB in 0 of the qualifying units (its last-10-call medians: 18-30 dB) |
| R-H1 redundant source traffic | **SUPPORTED in 8 of 10 cells**; NOT EVALUABLE in rho 0.5 c = 0 (version event) and rho 8 c = 3 (R(M1 only) = 0.068 < 0.10) | M1 + M2 B_source 1.008-1.039 Sinks; reduction of M1 only's redundant bytes 87.0-99.6 % |
| R-H2 discarded work | **SUPPORTED in 9 of 10 cells**; NOT EVALUABLE in rho 0.5 c = 0 | M1 + M2 discarded 0.010-0.061 Sink; manipulation check MET at rho 2, 4, 8 (M1 only 1.028 / 0.520 / 0.265 vs >= 0.750 / 0.375 / 0.188) |
| R-H3(a) latency unchanged without contention | **SUPPORTED in 4 of 5**; NOT EVALUABLE rho 0.5 | bind-ready within 0.17 s at rho 1-8 (15.3-15.6 s, ingress-bound) |
| R-H3(b) system-level latency under contention | **SUPPORTED at rho 1 and 2**; NOT EVALUABLE at rho 0.5 (not exposure-valid for M1 + M2) | 28.9 vs 57.4 s (rho 1), 43.0 vs 57.0 s (rho 2); rho 4 / 8 descriptive: 49.8 vs 57.1, 53.6 vs 57.1 s |
| N-H1 no change, no action | SUPPORTED cells 1, 4; **NOT SUPPORTED cell 7** (as recorded in the prediction) | cell 7: 1 false-positive re-plan in every rep, B_source 1.226 vs 1.010, bind unchanged (15.00 vs 15.01 s) |
| N-H2 benefit where an alternative exists (cell 9) | **NOT SUPPORTED** (re-plan clause) | bind 15.07 vs 113.4 s meets the 0.5 x clause by 7.5 x; re-plans 3 > 2; duplicates 0; B_source 1.45 vs 1.00 |
| N-H3 no harm where no alternative exists | SUPPORTED cells 2, 3, 5, 6; **NOT SUPPORTED cells 8, 10** | cell 8: +3.5 s (18.56 vs 15.01 s), 3 re-plans; cell 10: B_source 1.229 vs 1.000 with 28-32 re-plans (bind 113.9 vs 117.8 s) |

Cell effect classes (N, descriptive): neutral 1-6; harmful 7, 8; beneficial with traffic flagged 9, 10. The only
general M3 statement the data allow: *the frozen event-driven rule shortens restoration only when a degraded holder's
fragments are also held by the source (cell 9), and there it exceeds its own re-plan bound; it is neutral where it never
re-plans (2, 3, 5, 6); under incorrect placement it re-plans without a network change (7), which costs 0.22 Sink and,
when the source is degraded afterwards, 3.5 s (8); under destination-ingress degradation it oscillates (10).*

## 2. W - workload diversity

- **TTFO** is independent of the input: 0.668-0.693 s over 20 workloads x 2 seeds (immediate state 2.67 MiB).
- **Rejoin** (single crossing >= 35 dB after the bind at call 58-59): 39 of 40 units; rejoin calls median 7 (range 3-40); the
  non-rejoining unit is audi-snow-trail seed 1 (the most refresh-active clip: 122 promotions in 330 W1 calls; its OTTER
  output stays at 30 dB through call 133).
- **Single crossing overstates continuity for refresh-heavy clips** (descriptive, pre-specified): 8 units never reach 10
  consecutive calls >= 35 dB (train x2, street-artist-painting x2, butterfly-feeding-slow-motion x2, cricket-bat-practice
  s0, audi-snow-trail s0) and 9 units end the horizon with a last-10-call median below 35 dB (train 32.0 / 31.8,
  mbike-trick s1 33.0, street-artist 34.5 / 32.8, butterfly s0 31.2, cricket s1 34.4, circus-ball-act s0 31.4,
  audi-snow-trail s0 31.9, whose single crossing came 40 calls after the bind). The ExpD workload (dog)
  rejoins in 7-8 calls and holds 44 dB.
- **RVC** (reference Sink change between the trigger and the bind): 36 of 40 units; cut-induced in 14. RVC did not
  prevent rejoin (35 of 36 RVC units rejoined): the transferred, older Sink version re-converges with the reference.
- **Cold restart** never reaches 35 dB (18-30 dB), so the rejoin criterion discriminates Sink restoration in every unit.
- **W1 Sink stability** (promotions counted from call 2, W Amendment 1): **no unit is single-version stable at w = 25
  calls (P_25 <= 0.05): 0 of 40**, as fed; medians P_25 = 0.50 (repo), 0.79 (LOVEU 32-frame), 0.97 (LOVEU 128-frame);
  only cows-grazing and seagull-flying are stable at w = 6 (0.04). Repeated-input within-clip promotions per 100 calls:
  medians 2.6 / 5.4 / 12.6 by group (range 1.2-66); boundary promotion probability medians 0.20 / 0.26 / 0.85. Within-clip
  P_25 is measurable only for bird / boxing (0.43 / 0.43-0.65) and the 128-frame clips (0.58-1.0). Adaptive refresh is
  decided **per layer** (`models/wan/causal_model.py`); in dog only 3 of 16 promotions touch layer 0, which is why ExpD's
  layer-0 position audit saw none (erratum appended to `expD/expD_report.md`; no ExpD run affected).
- **W-AR** (exploratory, crop-based preprocessing sensitivity; 4 videos): rejoin calls 6 / 8 / 6 / 8 on the center-band
  variant vs 7 / 8 / 6 / 9 primary; last-10 medians 39.5 / 33.3 / 39.3 / 36.9 vs 38.9 / 31.2 / 36.8 / 31.4 dB; W1
  promotions higher on the crop (135 / 259 / 75 / 203 vs 45 / 200 / 60 / 174); Cold never reaches 35 dB on either. No
  verdict depends on it.

## 3. R - repeated mobility

| rho | c | B_source M1 only / M1 + M2 | reduction | discarded M1 only / M1 + M2 | bind-ready M1 only / M1 + M2 (s) | verdicts |
|---|---|---|---|---|---|---|
| 0.5 | 0 | 3.000 / 1.000 | - | 0 / 0 | 15.4 / 15.5 | NOT EVALUABLE (version event, all 9 runs) |
| 1 | 0 | 3.000 / 1.008 | 99.6 % | 2.000 / 0.025 | 15.6 / 15.5 | R-H1, R-H2, R-H3(a) SUPPORTED |
| 2 | 0 | 2.028 / 1.039 | 96.2 % | 1.028 / 0.061 | 15.5 / 15.5 | SUPPORTED |
| 4 | 0 | 1.520 / 1.032 | 93.9 % | 0.520 / 0.044 | 15.5 / 15.3 | SUPPORTED |
| 8 | 0 | 1.265 / 1.027 | 89.9 % | 0.265 / 0.041 | 15.5 / 15.4 | SUPPORTED |
| 0.5 | 3 | 2.019 / 1.010 | 99.0 % | 1.019 / 0.010 | 56.9 / 15.4 | R-H1, R-H2 SUPPORTED; R-H3(b) NOT EVALUABLE (exposure) |
| 1 | 3 | 1.518 / 1.017 | 96.7 % | 0.518 / 0.017 | 57.4 / 28.9 | SUPPORTED |
| 2 | 3 | 1.260 / 1.019 | 92.5 % | 0.260 / 0.019 | 57.0 / 43.0 | SUPPORTED |
| 4 | 3 | 1.131 / 1.017 | 87.0 % | 0.131 / 0.017 | 57.1 / 49.8 | R-H1, R-H2 SUPPORTED; latency descriptive |
| 8 | 3 | 1.068 / 1.017 | - | 0.068 / 0.017 | 57.1 / 53.6 | R-H1 NOT EVALUABLE (nothing to remove); R-H2 SUPPORTED |

- **rho 0.5, c = 0:** B binds at 14.4-15.0 s and keeps generating until it is left at 28.1 s; the dog clip's call-60
  promotion (W1: calls 60, 78, 82) lands in that window in every run of every policy (owner-side version event at
  18.5-18.9 s; C again at call 123). The frozen rule makes the cell NOT EVALUABLE; nothing was changed to avoid it. It is
  the first direct observation of the single-version limit: at rho < 1 on this workload every holder would forward a stale
  Sink.
- **Exposure (c = 3):** M1 only sees 3 background flows on A's egress for the whole restoration (coverage 1.0); M1 + M2 at
  rho 0.5 sees none (coverage 0: the background sessions' holders serve everything, so the M2 system removes the source
  load entirely) and the rule declares R-H3(b) NOT EVALUABLE there; at rho >= 1 coverage is 0.98-1.0 for both.
- OTTER event-driven (descriptive): equal to M1 + M2 except at rho 0.5 / 1 with c = 0, where it re-plans fragments from the
  bound holder to the source (B_source 1.42 vs 1.00; the cell-7 mechanism with a holder on a shared ingress) and at
  rho 0.5 c = 3 (1.34).

## 4. N - network adaptation

| cell | class | at moves bind (s) | ED bind (s) | ED re-plans per rep | ED B_source | trigger after move | verdict |
|---|---|---|---|---|---|---|---|
| 1 none x 0 | no change | 15.02 | 15.16 | 0, 0, 0 | 1.000 | - | N-H1 SUPPORTED |
| 2 none x src | no alternative | 118.03 | 118.30 | 0 | 1.000 | 7.25 s | N-H3 SUPPORTED |
| 3 none x in | no alternative | 118.45 | 117.92 | 0 | 1.000 | 7.25 s | N-H3 SUPPORTED |
| 4 correct x 0 | no change | 4.95 | 4.95 | 0 | 1.000 | - | N-H1 SUPPORTED |
| 5 correct x src | no alternative | 32.80 | 32.62 | 0 | 1.000 | 2.17 s | N-H3 SUPPORTED |
| 6 correct x in | no alternative | 32.73 | 32.67 | 0 | 1.000 | 2.18 s | N-H3 SUPPORTED |
| 7 incorrect x 0 | no change | 15.01 | 15.00 | 1, 1, 1 | 1.226 | - | **N-H1 NOT SUPPORTED** |
| 8 incorrect x src | no alternative | 15.01 | 18.56 | 3, 3, 3 | 1.027 | 7.25 s | **N-H3 NOT SUPPORTED** |
| 9 incorrect x hold | alternative available | 113.40 | 15.07 | 3, 3, 3 | 1.450 | 7.25 s | **N-H2 NOT SUPPORTED** (re-plans) |
| 10 incorrect x in | no alternative | 117.75 | 113.89 | 29, 28, 32 | 1.229 | 7.25 s | **N-H3 NOT SUPPORTED** |

- The progress-aligned trigger fired once in every degraded run at ceil(|S| / 2) (|S| = 412 without placement or with
  incorrect placement, 112-113 with correct placement); reaction was feasible in every run (>= 7.0 s to Sink verified
  after the change); no run timed out; the planners' view of the caps never changed.
- **Cells 2, 3, 5, 6:** nothing can help (the degraded link carries the only copy, or the destination's ingress), and the
  event-driven rule correctly does nothing (0 re-plans); restoration takes 118 s (full Sink at 62.5 Mbps) or 33 s (0.29
  Sink after correct placement).
- **Cell 7** reproduces ExpD G5: with no network change the rule re-plans 2.3 s after the move (measured rates on the
  shared ingress taken as persistent), moving 89 fragments from the misplaced holder to the source: +0.22 Sink of source
  traffic, no latency change. **Cell 8** shows what that costs when the source is then degraded: the fragments moved to A
  at 12.3 s are the ones A has to send at 62.5 Mbps after 17.25 s; two further re-plans move most of them back, net
  +3.5 s. **Cell 9** is the G7 class: at moves leaves 0.73 Sink on the 62.5 Mbps holder (113 s); the event-driven rule
  moves it to the source in three steps and binds at 15.07 s, but its own bound is <= 2 re-plans, so N-H2 fails on that
  clause; B_source 1.45 (0.45 Sink re-sent from A). **Cell 10:** with the destination's ingress degraded, every provider's
  measured rate drops at once; the rule moves fragments between A and B 28-32 times (ETA 202 -> 144 -> 128 -> 99 ... s),
  re-sending 0.23 Sink from the source for a 3.9 s gain.
- M1 + M2 (no bottleneck-aware assignment) equals OTTER at moves in every cell within 0.5 s and 0.01 Sink.

## 5. What the paper may state

- **M1:** execution resumes in ~0.68 s for every tested input (W-H1); the stream returns to the uninterrupted one within
  the horizon in 39 of 40 units (W-H2), and the criterion is specific to Sink restoration (W-H3). Continuity is
  workload-dependent: refresh-heavy clips cross 35 dB but do not stay there (section 2), and one unit never crosses.
- **Single-version scope:** the Sink changes during a 1 Gbps restoration window in about half of the dog windows and
  nearly always for 128-frame LOVEU clips (W1); restoration of an older version still rejoins (W2), but at rho < 1 a
  bound holder forwards a stale version (R rho 0.5), which is unsupported and now measured, not assumed.
- **M2:** removes 87-99.6 % of M1 only's redundant source bytes and keeps discarded work <= 0.06 Sink over rho 1-8, with
  and without source contention; it does not change latency without contention and halves it (rho 1) or cuts 25 % (rho 2)
  as a system under contention.
- **M3 (frozen rule):** section 1's summary sentence; the false-positive re-plan under incorrect placement (G5, cell 7)
  is the root cause of the cell-8 harm and of the traffic cost in cells 9 and 10. No general "M3 improves performance"
  claim.

## 6. Validity, re-runs, censoring, applicability

- Validity (`tools/eval/wrn_validity.py`, common Amendment 1): 311 of 312 original runs valid. The W2 OTTER run of
  audi-snow-trail seed 0 was invalid (elves-01 NIC receive samples of 1.2-4.7 Gbps from -4.5 s to +30 s around the run:
  traffic into the source host that is not the run's; cap 1 Gbps x 1.15); kept, listed, and the configuration re-run per
  the frozen rule (1 re-run, valid: NIC receive peak at elves-01 0.8 Mbps; its result is in every verdict above). The
  invalid run's own trajectory (descriptive): bind 58, first crossing at call 84, last-10 median 34.9 dB.
- Timeouts / censoring: none (no run reached `max_run_s` or its call window); the only censored quantity is the rejoin of
  the non-rejoining W2 unit (right-censored at call 133).
- Applicability (owner-side Sink promotion before the final bind): R rho 0.5 c = 0, 9 of 9 runs inapplicable (section 3);
  all other R and all N runs applicable. The 40 W2 and 4 W-AR Cold-restart runs carry the "inapplicable" flag because
  Cold restart never binds (every promotion counts as "before the bind"); the flag is not used by any W verdict.
- Exposure: every c = 3 run recorded; exposure-valid for M1 only in all 15 runs, for M1 + M2 in 12 of 15 (not at
  rho 0.5), for OTTER event-driven in all 15.

## 7. Amendments after the freeze (dated; frozen texts unchanged)

1. `followup_shakedown_conditions.md` Amendment 1 (2026-10-18): shakedown condition R-b replaced (c = 3 invalidates the
   c = 0 byte numbers).
2. `expW/preregistration.md` Amendment 1 (2026-10-19): sink slot 2 is filled at call 1; promotions counted from call 2
   (found in the GPU shakedown; analysis only).
3. `followup_common.md` Amendment 1 (2026-10-19): a degraded link's NIC check uses 10 s means of the 1 s samples (one
   fragment exceeds the tolerance within one sample).
4. `expD/expD_report.md` erratum (2026-10-19): the layer-0 position audit under-detected per-layer promotions; no ExpD
   run affected.
Harness fixes before any measurement run (no M1 / M2 / M3 change): driver `--node_extra=` quoting; degraded-cap egress
estimator; checker digest comparison at call 0.

## 8. Limitations

One workload (dog) in R and N; one degradation magnitude and onset rule in N; short clips repeated with hard cuts in W
(cut-induced promotions reported separately; long-form stability not established); LOVEU licences collection-level (no
LOVEU frames in figures); the testbed's two driver versions (recorded per run); R-H3(b) is a system-level comparison.
