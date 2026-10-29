# M3-S0 report: offline feasibility of lineage-staged restoration under repeated mobility (2026-10-29)

**Verdict by the preregistered rules: CONDITIONAL.** Feasibility holds at ρ = 1 for both workloads under the causal
policy; the end-to-end rule fails. The failure is not the one the preregistration's CONDITIONAL text anticipated
(prediction quality): the remote-serving criterion *is* met, and the two criteria that fail are the discarded-bytes
bound, which no staging policy can meet because the first migration cannot be staged, and the total-bytes bound,
which two-candidate staging exceeds by 17-25 %.

Labels: **simulated** (fluid model, `tools/eval/m3s0_sim.py`), **measured** (constants from M3-E0 / E9 / E10),
**recorded** (lineage table, `events_{dog,bfly}.json`, G0 consistency 1.000 for both).

## 1. Validity

| gate | result |
|---|---|
| G0 lineage rule vs per-block checksums (recorded) | dog 1.000, butterfly 1.000 (every (s, t) pair of calls 25..140, 180 entries × K / V); 0 inconsistent blocks |
| G1 S0 vs measured M3-E0 (after Amendment 1: η 0.96, h 2.36 s) | dog ρ1 PASS; dog ρ2 PASS; butterfly ρ1 PASS; **butterfly ρ2 FAIL** (remote +10.3 %, discarded +33 %) → no verdict for that configuration |

Model limits (stated): the lineage after an ownership change is the uninterrupted trajectory's; staging flows carry no
startup cost; one link-efficiency factor; the log is a constant-rate flow (measured mean), although it is bursty
(butterfly residuals ±0.9 s).

## 2. Feasibility (ρ = 1, causal / fair / once; simulated, per migration: lineage-valid entries at c0 of 180, delta
MB, readiness after start)

| graph | dog: A→B / A→C / A→D | butterfly: A→B / A→C / A→D |
|---|---|---|
| none (S0) | 0 / 0 / 0; 1,728 MB; final ready 21.3 s | 0 / 0 / 0; final ready 25.7 s |
| star | 0 / 64 / 125; 530 MB; 19.6 s | 0 / 43 / 86; 903 MB; 34.5 s |
| **line** | 0 / 105 / **169**; **108 MB**; **7.3 s** | 0 / 76 / **109**; 683 MB; **12.5 s** |
| tree | 0 / 64 / 125; 530 MB; 16.2 s | 0 / 43 / 86; 903 MB; 29.0 s |
| butterfly = adaptive | 0 / 64 / 129; 491 MB; 14.4 s | 0 / 43 / 86; 903 MB; 28.6 s |

- **Feasibility rule met** (≥ 90 valid entries, completed, readiness < 14.05 s) for both workloads by `line`; with
  residual sharing also by tree, butterfly and adaptive (dog 158 valid / 213 MB / 7.3 s; butterfly 122-126 valid /
  520-558 MB / 10.4-10.9 s).
- The readiness floor binds for dog: 7.3 s = call c0 + 12 (Replay-W) + 0.6 s. Butterfly's 12.5 s is base-bound
  (683 MB) because 68 entries were refreshed between staging and c0 (recorded: 146 refresh events over 71 calls).
- The first migration (A → B) is never stageable (nothing exists before t0) and is cancelled in every policy at ρ = 1
  and ρ = 2 (measured and simulated).
- **ρ = 2: infeasible for every policy, as predicted.** Even the floor (metadata-only base) is ready 6.8-7.3 s after
  the start, ≥ T_m = 7.0 s; the intermediate migrations are cancelled and only the final one completes.

## 3. End-to-end (simulated; S0 → policy; "captured" = share of the achievable reduction S0 − floor)

| configuration | S0 remote s | floor | best causal primary (graph) | captured | discarded MB (S0) | total MB (S0) | e2e rule |
|---|---|---|---|---|---|---|---|
| dog ρ1 | 51.6 | 26.8 | **37.5** (line) | **0.57** | 1,408 (2,784) | 5,302 (4,552) | fail: discarded > 0.5 S0 (1,392) |
| butterfly ρ1 | 59.0 | 30.4 | **45.8** (line) | **0.46** | 1,892 (3,152) | 6,931 (5,536) | fail: captured < 0.5; discarded; total > 1.25 S0 (6,920) |
| dog ρ2 | 37.9 | 24.0 | 35.8 (line) | 0.15 | 602 (1,194) | 5,296 (2,975) | fail (descriptive) |
| butterfly ρ2 | no verdict (G1) | | | | | | |

Sensitivity (simulated):
- **Residual sharing** (staging only from capacity left by the active migration and the log): dog ρ1 line = tree =
  butterfly = adaptive **37.5 s** (captured 0.57); butterfly ρ1 42.7-45.3 s (0.48-0.57); total bytes +18-25 %
  (dog) / +23-25 % (butterfly); discarded unchanged from S0 (the base is never slowed).
- **Oracle candidate**: holder-sourced graphs 37.5 s (dog) / 42.0-42.3 s (butterfly), the same as causal; wasted
  staging falls from 0.5-2.0 GB to 10-450 MB. Source-only staging (star) with the oracle: 41.4 / 49.5 s.
- **Fair sharing with source-sourced staging to two candidates hurts**: star / tree / butterfly / adaptive causal fair
  at dog ρ2 53.3 / 50.3 / 48.8 / 48.8 s vs S0 37.9 s; butterfly ρ1 67.9 / 62.3 / 61.9 / 61.9 vs 59.0 s. The active
  base shares the source's egress with two staging flows.
- **Re-staging refreshed entries (`fresh`)** never improves remote serving and raises total bytes by 0.3-1.2 GB.

Why the discarded criterion fails everywhere: S0 discards two cancelled migrations (dog ρ1: 1,395 + 1,389 MB). Staging
can shrink the second one (to 669-721 MB with line) but never the first, so the floor of discarded bytes under any
staging is ≈ 0.5 × S0 + the second migration's remainder. The criterion as written is unreachable; this is a defect of
the preregistration, recorded as such and not corrected after the fact.

## 4. The four topologies as staging graphs (preregistered reading)

Under the primary policy (causal / fair) `line` beats `adaptive` by more than 10 % in every configuration (dog ρ1
37.5 vs 44.7 s; butterfly ρ1 45.8 vs 61.9 s), so by the preregistered reading *structure matters and the reason is
reported from the flows*:

- **The reason is the source's egress budget, not graph shape.** `line` stages only the first candidate from the
  source and the second from the first candidate; `adaptive`, `butterfly` and `tree` stage both candidates'
  source-only entries from the source, so the active migration's base runs at 1/3 of A's egress (dog ρ1 A→B base sent
  461 MB in 14.5 s under adaptive / fair vs 1,395 MB under residual). Under residual sharing the four holder-sourced
  graphs coincide (dog 37.5 s all; butterfly 42.7 / 44.2 / 43.7 / 43.7 s, within 10 %).
- **What actually produces the gain is holder → candidate forwarding of the abandoned partial base.** In dog ρ1 line
  / causal the abandoned B forwarded 633 MB to D and C forwarded 1,006 MB to D (`stage:B>D`, `stage:C>D`); D started
  its migration with 169 / 180 valid entries and a 108 MB delta. The source's own staging to D was 0 (line) or
  322 MB (adaptive / residual). Star, which cannot do this, captures 0.07-0.12 under causal.
- **Fragility**: `line`'s advantage under fair sharing depends on the candidate order placing the abandoned holder
  upstream (B before D after the move to C). With the order reversed it would stage D from the busy source.
- **Conclusion for the topology question**: selection among star / line / tree / butterfly is not the mechanism. The
  decisions that matter are (i) prioritize the active migration over staging (a budget), and (ii) forward the
  abandoned destination's lineage-valid partial base to the candidates from its idle egress. Once (i) is in place, the
  adaptive per-entry assignment matches every fixed graph within 10 %, as Experiment B found for dissemination.

## 5. Reading

1. **Feasible (simulated): a delta migration ready before the next move at ρ = 1**, on both workloads, from
   lineage-valid state that already exists at the abandoned destination plus a small source delta (dog 60-213 MB,
   butterfly 434-683 MB). Readiness 7.3 s (dog, at the Replay-W floor) and 9.4-12.5 s (butterfly).
2. **Remote serving falls by 27 % (dog, 51.6 → 37.5 s) and 23-28 % (butterfly, 59.0 → 42.7-45.8 s)**, 52-57 % of
   what any staging could achieve. The rest is the unstageable first migration and the Replay-W floor.
3. **Prediction is not the critical assumption.** Oracle and two-candidate causal staging reach the same remote
   serving when staging is holder-sourced; the oracle only avoids 0.5-2.0 GB of wasted staging per run.
4. **Bytes are the cost**: total traffic rises 17-25 % (two-candidate waste 0.5-2.3 GB) and discarded transfer does
   not fall below ≈ 0.5 × S0.
5. **ρ = 2 is out of reach for any staging** (floor ≥ T_m), as predicted; and naive source-sourced staging makes it
   worse (+30-40 % remote serving).

## 6. Recommendation (by the preregistration's mapping: CONDITIONAL)

The mechanism worth pursuing is narrower and better defined than "staging graphs":

> **Lineage-aware forwarding of abandoned restoration progress.** When a move cancels a migration, the abandoned
> destination keeps its verified partial base (tagged with its snapshot call) and forwards the lineage-valid part to
> the user's next candidates from its own egress; the source sends only refreshed and missing entries, after the
> active migration; the destination assembles and verifies the base as M2 does (ordered shifts + refreshed entries,
> 360 block checksums, full-base fallback).

- Star / line / tree / butterfly: baselines and states of this process, not the mechanism; the paper can show that
  source-only staging (star) fails and holder-sourced staging (the other three and the adaptive assignment) converge.
- The condition to resolve before implementation is **not a mobility model** but two cheaper questions: (a) does
  holder forwarding of a partial, version-tagged base work end to end on the network harness with the source
  prioritized (feasibility is simulated only); (b) is a 17-25 % traffic increase acceptable against −23-28 % remote
  serving, or should staging be limited to one candidate (admission, C3) — a policy question for the paper, not an
  experiment.
- Suggested next step [R]: a **network-level run** with `restore_orchestrate.py` / `restore_node.py` (no GPU): A → B →
  C → D at ρ = 1 with the measured base / log / delta sizes, policies S0, holder-forward-residual (one and two
  candidates), measured against the simulated 37.5 / 42.7 s and 5.3 / 6.9 GB. GO for GPU integration only if the
  measured remote-serving reduction is ≥ 20 % with total bytes ≤ 1.3 × S0.
- A new preregistration is needed for that run; it should replace the discarded-bytes criterion by "discarded bytes
  of migrations after the first".

## 7. Files

`preregistration.md` (+ Amendment 1), `calibration.json`, `events_{dog,bfly}.json` (recorded, elves-01, f6263707),
`s0_results.{json,md}` (simulated, this commit), `tools/eval/m3s0_sim.py`, `tools/eval/m3s0_dump_events.py`.
