# Fig. 10 report: M2 versioned Sink reuse vs version age

Preregistration FROZEN a841a0cd (decisions D1-D6). Runs: 48 (7d712029, run commit a841a0c on A = elves-01 and
B = elves-02): A -> B -> A, seed 0, trigger 30, first switch s1 = 74, ages 10 / 60 / 150 / 240, Full (`--replay_retain`)
vs Versioned (`--replay_retain --replay_reuse`), 3 reps, both workloads. Numbers: `fig10_results.{json,md}`
(`tools/eval/fig10_report.py`); figures: `figures/` (`tools/eval/plot_fig10.py`, Fig. 6a canvas and axes box, style
font sizes; legend label "Versioned", no mechanism name).

## 1. Verdicts (frozen rules)

| hypothesis | Low-refresh (dog) | High-refresh (butterfly) | verdict |
|---|---|---|---|
| F10-H1: Versioned < changed-block base, ages 60 / 150 / 240 | 21.6 < 371.4; 21.6 < 371.4; 50.3 < 400.2 MB | 328.3 < 639.8; 395.4 < 673.3; 433.7 < 706.9 MB | **SUPPORTED** |
| F10-H2: Versioned < Full base (1,727.6 MB), every age | 12.0 / 21.6 / 21.6 / 50.3 MB | 98.2 / 328.3 / 395.4 / 433.7 MB | **SUPPORTED** |
| F10-H3: readiness Versioned < Full, every age | 8.80 / 8.82 / 8.84 / 8.88 vs 22.39-22.51 s | 9.30 / 9.03 / 9.12 / 8.99 vs 23.39-25.51 s | **SUPPORTED** |

Validity: 48 / 48 valid; 0 DELTANO fallbacks (every Versioned run DELTAOK, 360 / 360 blocks); arm equivalence (B's
outputs s1..s2 identical between Full and Versioned) true in all 24 (workload, age, rep) pairs. Extra-rep rule
(section 6): no cell has overlapping readiness ranges (max Versioned 9.36 s < min Full 22.21 s), so no extra reps.
Bytes are identical across reps in every cell (deterministic generation, fixed switch calls).

## 2. Panel 10a: Sink base bytes [V] measured (Versioned, Full); [C] computed from measured block sets (changed-block, entry-level)

| workload | age | refreshed / shift events | changed blocks K / V | Versioned | changed-block | entry-level unchanged-only | Full | Versioned / changed-block | Versioned / Full |
|---|---|---|---|---|---|---|---|---|---|
| dog | 10 | 1 / 0 | 1 / 1 | 12.0 | 12.0 | 12.0 | 1,727.6 | 1.00 | 0.007 |
| dog | 60 | 2 / 73 | 75 / 2 | 21.6 | 371.4 | 721.2 | 1,727.6 | 0.058 | 0.012 |
| dog | 150 | 2 / 73 | 75 / 2 | 21.6 | 371.4 | 721.2 | 1,727.6 | 0.058 | 0.012 |
| dog | 240 | 5 / 73 | 78 / 5 | 50.3 | 400.2 | 750.0 | 1,727.6 | 0.126 | 0.029 |
| bfly | 10 | 10 / 0 | 10 / 10 | 98.2 | 98.2 | 98.2 | 1,727.6 | 1.00 | 0.057 |
| bfly | 60 | 34 / 65 | 99 / 34 | 328.3 | 639.8 | 951.3 | 1,727.6 | 0.51 | 0.19 |
| bfly | 150 | 41 / 58 | 99 / 41 | 395.4 | 673.3 | 951.3 | 1,727.6 | 0.59 | 0.23 |
| bfly | 240 | 45 / 57 | 102 / 45 | 433.7 | 706.9 | 980.0 | 1,727.6 | 0.61 | 0.25 |

(MB. Total second-migration bytes, base + log + switch: dog Versioned 41-80 vs Full 1,747-1,757; bfly 635-856 vs
2,111-2,265.)

- **Where the saving over changed-block comes from.** Every changed V block belongs to a refreshed entry (V count =
  refreshed count in all 8 cells); the remaining changed blocks are K blocks re-rotated by realignment shifts (dog 73-76,
  bfly 57-65 per cell). Versioned sends those as ordered shift events instead of bytes, so its base is the refreshed
  entries plus metadata. The gap to changed-block is therefore large where shifts dominate (dog, 8-17x) and smaller
  where refreshes dominate (bfly, 1.6-2.0x).
- **Age 10** crosses no realignment (the first is at age 19): changed-block equals Versioned, as preregistered.
- **Growth with age** follows the refreshed-entry count, not the age: dog stays at 2 refreshed entries from age 60 to
  150 (identical bytes) and reaches 5 at 240; bfly grows 10 -> 34 -> 41 -> 45 and flattens. Shift events (one per
  recorded position change) stay at 73 in dog for ages 60-240 although ages 150 / 240 cross more realignment calls;
  in bfly they fall 65 -> 57 as shifted entries become refreshed ones (which drop their shifts). Why the later
  realignments add no position changes was not examined here.
- Predictions [H] vs measured: dog Versioned / changed-block 0.06-0.13 (predicted 0.05-0.2); bfly 0.51-0.61, rising
  (predicted 0.5-0.8, rising); bfly at age 240 is 0.25 of Full (predicted 0.4-0.7; the saving is larger than predicted).

## 3. Panel 10b: readiness [V] measured

| workload | age | readiness Full (s) | readiness Versioned (s) | ratio | base ready Full / Versioned (s) | interruption Full / Versioned (s) |
|---|---|---|---|---|---|---|
| dog | 10 | 22.51 [22.25-22.73] | 8.80 [8.75-8.81] | 0.39 | 18.62 / 2.45 | 1.55 / 1.42 |
| dog | 60 | 22.47 [22.44-22.87] | 8.82 [8.78-8.86] | 0.39 | 18.61 / 2.49 | 1.54 / 1.43 |
| dog | 150 | 22.39 [22.21-22.40] | 8.84 [8.83-8.85] | 0.40 | 18.51 / 2.53 | 1.55 / 1.42 |
| dog | 240 | 22.44 [22.40-22.46] | 8.88 [8.87-8.89] | 0.40 | 18.60 / 2.61 | 1.54 / 1.42 |
| bfly | 10 | 25.51 [24.33-25.54] | 9.30 [9.25-9.36] | 0.36 | 20.88 / 3.11 | 1.84 / 1.73 |
| bfly | 60 | 23.39 [23.06-23.84] | 9.03 [9.02-9.06] | 0.39 | 19.19 / 5.21 | 1.54 / 1.42 |
| bfly | 150 | 24.74 [23.38-24.81] | 9.12 [9.11-9.13] | 0.37 | 20.28 / 5.84 | 1.60 / 1.49 |
| bfly | 240 | 23.41 [22.82-23.60] | 8.99 [8.91-9.00] | 0.38 | 19.15 / 6.15 | 1.53 / 1.42 |

- Versioned readiness is flat in age (dog 8.80-8.88 s, bfly 8.99-9.30 s) while its base ready doubles in bfly
  (3.11 -> 6.15 s). Readiness is bounded below by the replay rule (W = 12 calls replayed past the base boundary,
  section 2 of the preregistration); in these cells the base arrives before that bound, so its growth does not reach
  readiness. Ratio 0.36-0.40 in both workloads.
- Prediction [H] vs measured: dog ~0.4 (measured 0.39-0.40); bfly predicted 0.45-0.7 rising with age, measured
  0.36-0.39 and flat: the bound is not reached by the bfly base at these ages at 1 Gbps. At lower bandwidth the base
  would cross the bound sooner (not measured here; Fig. 12).
- Interruption at the second cutover is about equal between arms (1.42-1.73 vs 1.53-1.84 s), as expected; M2 changes
  the base, not the cutover.

## 4. Answers to the questions (section 1)

- **10a.** With an older version on the destination, Versioned sends 0.7-2.9 % (dog) and 5.7-25 % (bfly) of the full
  Sink up to age 240, and 6-13 % (dog) / 51-61 % (bfly) of what reusing every unchanged K / V block would send. The
  saving over block-level reuse comes from shift events (K re-rotation) and is largest when refreshes are few.
- **10b.** The byte saving shortens readiness to 0.36-0.40 of Full at every tested age (up to 240 calls); readiness
  does not degrade with age here because the replay bound, not the base, sets it.

## 5. Limits

One seed per workload, one host pair (A, B), 1 Gbps, path A -> B -> A only. Changed-block and entry-level bytes are
computed from measured block / entry sets, not run as transfer methods. Ages beyond 240 and repeated versions (A -> B ->
A -> B) are not measured. Readiness depends on the W = 12 replay rule; it is not a lower bound on what reuse could reach.
