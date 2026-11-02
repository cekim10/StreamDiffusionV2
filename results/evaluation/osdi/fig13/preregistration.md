# Fig. 13 preregistration: output fidelity after a verified cutover (DRAFT 2, not frozen, nothing run)

Plan: `osdi/eval_plan/plan.md` (Fig. 13, RQ6, P0). Draft 1: 930590e8. Draft 2 applies the user's review (2026-11-01):
D1-D4, D6, D8-D10 approved (D1 conditional on a pair-equivalence check, D8 / D9 extended); D5 and D7 revised; H1
framed as conditional, H2 revised to compare both runs' decisions, H3 treated as partly exploratory with a
near-threshold analysis added; analysis units for correlated cutover calls; D10 checks; post-cutover length check.
Fig. 13 answers three questions: **how close** (fidelity and temporal consistency after a verified cutover), **when**
(which inputs and cutover calls diverge), **why** (does the approximate recent state flip refresh decisions).
Labels: [V] verified in code or earlier records, [H] hypothesis / expectation, [R] recommendation.

## 1. Questions

- **Q1 Sink correctness at the cutover.** Answered: SINKOK, 0 / 360 blocks differing, in every OTTER switch of Figs.
  7, 9-11 [V]. Re-checked here as a validity condition, not a result.
- **Q2 How close.** After a verified cutover, how close is the destination's output to the uninterrupted run, in three
  windows after the cutover: calls 1-8 (recent-state reconstruction), 9-24 (recovery), 25-100 (long-term divergence)?
  How consistent is the motion across and after the boundary, relative to the reference's motion?
- **Q3 When.** After the cutover, does the destination's Sink follow the reference's refresh / realignment decisions on
  every layer? For which inputs and cutover calls does it not, and at which call?
- **Q4 Why.** At the first divergence, which decision differs (refresh only on one side, a different slot, a write or
  a realignment), and was it near the 0.2 threshold in the reference and on the destination?
- **Q5 Replay at the same call (D10).** At the same cutover call, how much does replay improve the first calls over a
  Sink-exact cutover without replay (P-sink)?

Out of scope: latency (Figs. 7, 9-12). **This is a quality-isolation experiment**: every method cuts over at the same
absolute generation call, which a real migration would not choose (it switches when ready). Stated in the caption.

## 2. Facts this protocol rests on

| fact | source | tag |
|---|---|---|
| Every Full, P-full and R-full run of Fig. 7 is bit-exact to the uninterrupted reference on every scored call (99 dB, 5 / 5 each workload): they restore the whole state. OTTER has 0 bit-exact calls of 101. | `osdi/fig7/fig7_report.md` | [V] |
| OTTER (Fig. 7 flags, W = 12): first-output PSNR 29.3 / 35.9 dB, terminal 48.8 / 44.4 dB (dog / bfly); bfly 2 / 5 runs end at 32.4 dB. | Fig. 7 | [V] |
| The 32.4 dB runs are exactly the runs whose Sink slot schedule (layer 0) differs from the reference after the cutover: B's first live call (67) refreshes a slot the reference does not; the Sink was exact at the switch. 8 / 10 runs follow the reference schedule. Only layer 0 positions were logged; similarities were not. | `osdi/fig7/bfly_fidelity_analysis.md` | [V] |
| Adaptive refresh (`causal_model.py`): in every forward with a KV cache, per layer and row, the avg K / V cosine similarity of the incoming chunk with each of the 3 Sink slots; if the minimum is below 0.2 the least similar slot is queued (`evict_idx`); a later cache write (ring full) writes the queued slot. Realignment (`_realign_kv_positions`) re-rotates the K of promoted slots and shifts their positions when the stream position is rewound. | `models/wan/causal_model.py:208-227, 336-380` | [V] code |
| Sink content changes only by a refresh write (K + V + position of one slot) or a realignment (K + positions). After a cutover every refresh writes B's own (not bit-exact) K / V, so Sink **content** differs from the reference after the first post-cutover refresh even when the **schedule** matches. Equal positions do not imply equal content, and a queued but not yet written decision changes neither positions nor content until it is written. | code | [V] code |
| Replay helps only early: +7-8 dB in B's calls 1-8 vs no replay; the step comparison was confounded by different start calls (30 / 63-67 / 68-77). | Fig. 9 | [V] |
| `--replay_switch_calls S` fixes OTTER's switch call (`switch_call_missed` if not ready). **The replay window W is only a readiness gate**: the destination replays from the base boundary c0 to the switch (43 calls for c0 = 31, S = 74) and may switch once `fr - c0 + 1 >= W`; at a fixed S, W = 6 and W = 12 replay the same calls, so the plan's R-win arm is not a quality condition. | `mobility_orchestrate.py:1128`, `mobility_node.py:2051` | [V] code |
| P-sink (`precopy_sink`): Sink pre-copy rounds, then a stop-and-copy of the dirty Sink, in-flight and metadata components; the destination's recent state starts empty (no replay). Before this draft it had no planned switch call. | `mobility_node.py` `_precopy` | [V] code |
| `--nodes` / `--agent_hosts` map labels to hosts, so two independent pairs (P1 = elves-01 / 02, P2 = elves-03 / 04, both labelled A, B) can run at once from elves-01. | `mobility_orchestrate.py` | [V] code; not yet run that way |
| Fig. 5 refresh intensity (refreshes per 100 calls, seed 0): dog 3.6, bird 3.6, boxing 8.2, basketball 9.1, hockey 16.4, swimmer 22.7, train 34.5, audi 53.6, circus 89.1, bfly 128.2 (input / prompt pairs of `run_sink_char.sh`; examples/ = dog, bird, boxing, train; the rest LOVEU). | `m123_figures.data.json` | [V] |
| A run with the same input, seed and switch call is deterministic (Fig. 7 bfly reps 2, 4, 5: identical PSNR series). | Fig. 7 | [V]; re-checked here per input |

## 3. Conditions and runs

Path A -> B (one migration), 1 Gbps, trigger at call 30, Fig. 7 OTTER flags otherwise.

| factor | levels | note |
|---|---|---|
| input (D2) | 10: dog, bird, boxing, basketball, hockey, swimmer, train, audi, circus, bfly | refresh 3.6-128 / 100 calls |
| seed (D2) | 0, 1 | two seeds only: a stated limit of generality |
| cutover call S (D3) | seed 0: 70, 71, ..., 79; seed 1: 70, 72, 74, 76, 78 | >= OTTER's readiness (switched at 63-67 in Fig. 7) |
| method | **OTTER** (Fig. 7 flags, W = 12) | the quality condition; replay length S - c0 recorded |
| control (D4) | **Full**, one per (input, seed) | exact positive control: must be bit-exact |
| repeat (D4, D1) | OTTER seed 0, S = 74, once per input, **on the other pair** | determinism and pair equivalence in one run |
| D10 | **P-sink** at S = 74, seed 0 (`--sink_switch_calls 74`) | replay vs no replay at the same call |

Runs: OTTER 150 + Full 20 + repeats 10 + P-sink 10 = **190**. Pairs: P1 = dog, boxing, hockey, train, circus; P2 = bird,
basketball, swimmer, audi, bfly (each spans the refresh range); each pair also runs the other pair's repeats. The first
step runs dog seed 0 S = 74 OTTER on both pairs at once (P1 rep 1, P2 rep 2). Estimate [H] ~6 min per run: ~9.5 h
per pair, both pairs at once.

**Length.** `--migration_chunk 30 --post_chunks 160` (reference and run to call 189), `--xb_horizon 101`: k = 1-100
exists for S = 79 (call 178). A run without k 1-100 is invalid (section 8); the sanity step checks it on the first run.

## 4. Instrumentation (D7; record-only, flag-gated; no behavioral change)

- **Model probe** (`causal_model.REFRESH_PROBE`, None by default, like the Experiment VD `ATTN_PROBE`): called after the
  model's own decision with the similarities ("sim"), the cache slot written ("write") and the realignment shift
  ("realign"). Nothing in the forward pass reads it.
- **Node `--fidelity_log`** (with `--block_ck`): per call, in the reference and on every owned call, per (layer, row):
  number of similarity evaluations, the minimum avg similarity and its slot, the slots queued for refresh (minimum
  < 0.2), the cache slots written, the realignment shift. Per owned call: the 360 Sink block checksums and all slot
  positions compared with the reference call (number and first indices of differing blocks; (layer, row) with differing
  positions), and the reference-relative temporal error per frame. Returned at run end into
  `node_<X>/fidelity_record.json.gz`.
- **P-sink planned switch** (`--sink_switch_calls`): the source stops at S after its pre-copy rounds, through the same
  `stop_at` path OTTER's `--replay_switch_calls` uses; unset = unchanged.
Regression (test_xb, test_m1_live, test_m2_live, test_m2_track_cpu, test_m3v2) after these changes and before the
freeze; flags off reproduce the old records. Local dry run of OTTER (S = 70, 79), Full and P-sink.

**Pre-freeze record (2026-11-01).** Regression ALL PASS: test_xb 87 ok (a first attempt failed its two 4-node cases
with a clock-sync connection reset, right after a hung run of the previous attempt was killed; the local venv had lost
package files; rerun after reinstalling, unchanged code: 87 / 87), test_m1_live 50, test_m2_live 45, test_m2_track_cpu,
test_m3v2 28. Local dry run: all four conditions valid; fixes it found (harness / report only, no criterion changed):
(1) Full is judged with the W / R / N validity rule, as in Fig. 7 (`fig7_report.validity`), not the XB rule (no
pre-copy switchover, by design); (2) Full runs end on the non-XB orchestrator path, which now also writes
`fidelity_record.json.gz` (record only); (3) `run_fig13.sh dry` clears earlier dry runs; (4) 13a x ticks 1 / 25 / 50 /
75 / 100 (the window edges are the vertical lines; "100" was clipped at 28 pt).

## 5. Metrics (k = call - S + 1; k = 1 is B's first generated call; Full: k from B's first call)

- **Fidelity**: per-call PSNR and SSIM vs the reference; per run the medians over **W1 = k 1-8, W2 = 9-24,
  W3 = 25-100**, first call, terminal (k 91-100). LPIPS only if installable (D6), never blocking.
- **Temporal consistency (reference-relative)**: per frame t, TE(t) = mean over pixels of
  ((O_t - O_{t-1}) - (R_t - R_{t-1}))^2 on 0-255 values, as tPSNR = 10 log10(255^2 / TE) (99 when 0). The frame before
  B's first frame is the source's last delivered frame (= the reference's, source bit-exact), so the first frame of
  k = 1 gives the **boundary** tPSNR. Per-call value: median over the call's frames; windows as above.
- **Sink divergence, three levels** (first k where ... on any layer / row):
  - **decision**: the queued slots, written slots or realignment shift differ from the reference's at the same call;
  - **position**: the slot positions differ;
  - **content**: any of the 360 block checksums differs (expected at B's first refresh write; descriptive).
  "Schedule divergence" = decision or position divergence by k = 100.
- **First decision divergence**: its call, layer, row and class: `dest_only` (only B queued a refresh), `ref_only`,
  `slot` (both, different slots), `write`, `realign`; the reference's and B's minimum similarities there, their
  margins |sim - 0.2| and their difference |sim_B - sim_ref|; the same pair of records for the calls just before.

## 6. Hypotheses and analysis units

**Units (D3).** The 15 cutover calls of one (input, seed) are correlated conditions, not independent samples. Results
are reported per input, per seed, against S, and as the distribution over conditions; inputs are the unit of H3.

- **F13-H1 (fidelity when the Sink schedule holds; a conditional result).** Among OTTER conditions with no schedule
  divergence by k = 100, >= 90 % have W3 median PSNR >= 40 dB. [H] yes (Fig. 7: 44-49 dB when undiverged). This tests
  the undiverged case only; the overall quality result is the distribution of section 7.
- **F13-H2 (divergence by a threshold crossing).** For >= 80 % of first decision divergences: the class is `dest_only`
  or `ref_only` (the two runs fall on opposite sides of 0.2) **and** the reference's margin is below the 10th
  percentile of that input's reference margins over calls 30-180. Reported with B's margin and |sim_B - sim_ref| at the
  divergence vs the same difference at non-diverging decisions in k 1-8. [H] yes (Fig. 7).
- **F13-H3 (divergence vs refresh intensity; partly exploratory).** Across the 10 inputs, Spearman rho(Fig. 5 refresh
  intensity, OTTER schedule-divergence rate over the input's 15 conditions) >= 0.6. [H] yes. A failure of H3 does not
  refute H2. **Exploratory, always reported**: rho of the divergence rate with the near-threshold decision frequency
  (share of reference decisions, calls 30-180, with margin < 0.02), which may explain divergence better than refresh
  intensity; and whether the refresh ordering of the inputs holds on seed 1 (refresh writes per 100 calls measured in
  this experiment's references, seed 0 vs seed 1, Spearman).
- **F13-H4 (replay at the same call, D10).** Median W1 PSNR(OTTER) > W1 PSNR(P-sink) at S = 74, seed 0, in >= 8 of 10
  inputs. [H] yes (Fig. 9: +7-8 dB in calls 1-8, confounded there).

## 7. Quality claim rule (D5; written now, applied to the result)

The thresholds below are **operational criteria fixed in advance**, not validated perceptual thresholds; the paper
says so. PSNR alone never decides the wording.

**Primary quality result (always reported, all OTTER conditions of evaluable inputs, 10 x 15 = 150):**
- F_P = share with W3 median PSNR >= 40 dB; F_T = share with W3 median tPSNR >= 40 dB;
- distributions of W1, W2, W3 PSNR / SSIM / tPSNR, the boundary tPSNR, per input and seed.

**Wording.**
- "OTTER **preserves output fidelity** after the cutover (W3)" only if F_P >= 0.90 **and** F_T >= 0.90; the sentence
  always gives the W1 transient (first-call and W1 values) next to it.
- Otherwise conditional: "after a Sink-exact cutover, output stays at >= 40 dB PSNR (and tPSNR) in N % of conditions
  25-100 calls later; in the others (inputs ..., cutover calls ...) it falls to Y dB", with the measured mechanism.

**Mechanism result (reported separately, not part of the wording rule):** schedule-divergence share and the first
divergence's k, class and margins; W3 of diverged vs undiverged conditions. Schedule divergence does not by itself imply
low quality, and its absence does not by itself imply high quality.

## 8. Validity

Per run: switch at the planned S (`switch_call_missed` false); OTTER SINKOK 0 / 360; k = 1-100 present; the run's own
reference (input, seed, M, N); the fidelity record present. Full control: bit-exact on every scored call. P-sink: switch
at S, no replay (no replay events), scored against the same reference call indices. **Not evaluable input**: a Full
control not exact, or the repeat (other pair) not equal to rep 1 call by call (PSNR series and first decision
divergence); excluded from H1-H4 and the claim rule, listed. **Pair equivalence**: the first step's two runs must be
equal call by call; otherwise the two-pair plan stops (all runs on P1). Harness defect: fix, rerun, keep both records.

## 9. Procedure

1. Instrumentation + `run_fig13.sh` + `fig13_report.py` + `plot_fig13.py`; regression ALL PASS; local dry run.
2. Freeze.
3. Testbed: `d0_remote.py pull`, `run_fig13.sh preflight`, `first` (dog s0 S74 OTTER on P1 and P2 at once) +
   `fig13_report.py --sanity`: both valid, equal call by call, k 1-100 present.
4. `rest1` and `rest2` in two terminals (P1, P2 at once).
5. Report; claim rule; figures.

## 10. Plot specification (Fig. 6a canvas and axes box, style font sizes, OTTER blue)

- **13a** PSNR vs k after the cutover (windows marked): OTTER median with the inter-condition range, P-sink (D10)
  dashed; diverged conditions drawn separately so a 32-dB-type failure is visible, not averaged.
- **13b** per input (x sorted by refresh intensity): W3 PSNR of every condition, diverged marked; divergence rate.
- **13c** temporal consistency in the main text (D9): boundary and W1-W3 tPSNR per input (panel or a table in the body).
- **13d** frame strip around the boundary, reference vs OTTER, **non-LOVEU inputs only: dog and train** (D8). Frames
  come from a deterministic re-run of the chosen condition with `--dump_frames` after the sweep (a strip run is checked
  equal to its sweep run by the PSNR series; it adds no data to the analysis). A divergence case is shown as a Sink decision timeline (reference vs destination:
  queued / written slots and similarity vs 0.2 per call); its frames only if the input is non-LOVEU.

## 11. Decisions

| # | decision | status |
|---|---|---|
| D1 | two pairs in parallel (`--nodes`), conditional on the pair-equivalence check in the first step | approved |
| D2 | 10 inputs x seeds 0, 1; the two-seed limit stated | approved |
| D3 | seed 0 S = 70-79, seed 1 S = 70-78 step 2; correlated conditions, analysis units of section 6 | approved |
| D4 | OTTER; Full control; one repeat per input on the other pair; R-win not run | approved |
| D5 | quality claim rule of section 7 (primary F_P and F_T, operational 40 dB; mechanism reported separately) | revised |
| D6 | LPIPS only if installable, never blocking | approved |
| D7 | decisions (queued / written slot, min similarity, margin, realignment) in reference and destination; three divergence levels; first-divergence classes | revised |
| D8 | strips: dog + train; divergence case as a decision timeline | approved, extended |
| D9 | temporal consistency visible in the main text | approved, extended |
| D10 | P-sink at S = 74, seed 0, 10 inputs (harness addition with regression) | approved |
