# Fig. 13 preregistration: output fidelity after a verified cutover (DRAFT 1, not frozen, nothing run)

Plan: `osdi/eval_plan/plan.md` (Fig. 13, RQ6, P0). User review 2026-11-01: Fig. 13 is the test of OTTER's central
claim, not an add-on; separate Sink correctness from output fidelity; fixed cutover; quality over time; reference-
relative temporal consistency; more inputs and seeds; find when and why the butterfly Sink diverges; the claim is
written from the result. Labels: [V] verified in code or earlier records, [H] hypothesis / expectation,
[R] recommendation. Open decisions: section 11.

## 1. Questions

- **Q1 Sink correctness at the cutover.** Answered: SINKOK, 0 / 360 blocks differing, in every OTTER switch of Figs.
  7, 9-11 [V]. Re-checked here as a validity condition, not a result.
- **Q2 Output fidelity.** After a verified cutover, how close is the destination's output to the uninterrupted run, in
  three windows after the cutover: calls 1-8 (recent-state reconstruction), 9-24 (recovery), 25-100 (long-term
  divergence)?
- **Q3 Temporal consistency.** Is the motion across and after the boundary the reference's motion
  (reference-relative, not raw frame differences)?
- **Q4 Sink trajectory.** After the cutover, does the destination's Sink follow the reference's refresh / realignment
  schedule on every layer? When it does not, when does it diverge and is the flipped refresh decision one that sits
  near the threshold in the reference?
- **Q5 Generality.** How do Q2-Q4 vary over inputs with different refresh intensity and over seeds?

Out of scope: latency (Figs. 7, 9-12); this is a **quality-isolation experiment**: every method cuts over at the same
absolute generation call, which a real migration would not choose (it switches when ready). Stated in the caption.

## 2. Facts this protocol rests on

| fact | source | tag |
|---|---|---|
| Every Full, P-full and R-full run of Fig. 7 is bit-exact to the uninterrupted reference on every scored call (99 dB, 5 / 5 each workload): they restore the whole state. OTTER has 0 bit-exact calls of 101. | `osdi/fig7/fig7_report.md` | [V] |
| OTTER (Fig. 7 flags, W = 12): first-output PSNR 29.3 / 35.9 dB, terminal 48.8 / 44.4 dB (dog / bfly); bfly 2 / 5 runs end at 32.4 dB. | Fig. 7 | [V] |
| The 32.4 dB runs are exactly the runs whose Sink slot schedule (layer 0) differs from the reference after the cutover: B's first live call (67) refreshes a slot the reference does not; the Sink was exact at the switch. 8 / 10 runs follow the reference schedule. Only layer 0 positions were logged; similarities were not. | `osdi/fig7/bfly_fidelity_analysis.md` | [V] |
| Adaptive refresh: per layer and row, the mean K / V of the incoming chunk vs each Sink slot (cosine), refresh the least similar slot if min avg similarity < 0.2. A decision can flip when B's not-bit-exact K / V cross 0.2. | `models/wan/causal_model.py:336-351` | [V] code |
| Sink content changes only by refresh (K + V + position of one slot) or realignment (K re-rotation of promoted slots, all positions shift). After a cutover, every refresh writes B's own (not bit-exact) K / V, so Sink **content** differs from the reference after the first refresh even when the **schedule** matches. | `causal_model.py`; Fig. 10 / E-B | [V] code |
| Replay helps only early: +7-8 dB in B's calls 1-8 vs no replay; the step comparison was confounded by different start calls (30 / 63-67 / 68-77). | Fig. 9 | [V] |
| The per-call reference record (`baseline`) can hold all 360 Sink block checksums and all slot positions (`--block_ck`); owned calls record only layer-0 positions (`sink_slot_pos`), PSNR, SSIM, frame digest match. | `mobility_node.py:270-300`, metrics.csv | [V] code |
| `--replay_switch_calls S` fixes the switch call (missed if not ready: `switch_call_missed`); only `precopy_replay` honors it. `--dump_frames` keeps destination and reference frames on the host. | `mobility_orchestrate.py:1128` | [V] code |
| **The replay window W is only a readiness gate**: the destination replays from the base boundary c0 to the switch (`n_replayed` 43 for c0 = 31, switch 74), and may switch once `fr - c0 + 1 >= W`. At a fixed S, W = 6 and W = 12 replay the same calls, so the plan's R-win (W = 6) arm is expected to give the same output and is not a quality condition here. The replay length at the switch is S - c0. | `mobility_node.py:2051`; Fig. 10 events | [V] code |
| `--nodes A=host,...` maps labels to hosts, so two independent pairs (elves-01/02 and elves-03/04) can run at once. | `mobility_orchestrate.py:2199` | [V] code; not yet run that way |
| Fig. 5 refresh intensity (refreshes per 100 calls, seed 0): dog 3.6, bird 3.6, boxing 8.2, basketball 9.1, hockey 16.4, swimmer 22.7, train 34.5, audi 53.6, circus 89.1, bfly 128.2 (20 inputs in all; examples/ = dog, bird, boxing, train; the rest LOVEU). | `m123_figures.data.json` `fig5_inputs` | [V] |
| A run with the same input, seed and switch call is deterministic (Fig. 7 bfly reps 2, 4, 5: identical PSNR series). | Fig. 7 | [V]; re-checked here |

## 3. Conditions

Path A -> B (one migration), 1 Gbps, trigger at call 30, Fig. 7 OTTER flags otherwise.

| factor | levels | note |
|---|---|---|
| input (D2) | 10: dog, bird, boxing, basketball, hockey, swimmer, train, audi, circus, bfly | spans 3.6-128 refreshes / 100 calls |
| seed (D2) | 0, 1 | |
| cutover call S (D3) | seed 0: 70, 71, ..., 79 (10 consecutive); seed 1: 70, 72, 74, 76, 78 | >= OTTER's readiness (switched at 63-67 in Fig. 7); consecutive calls sample every position of B's first live call relative to near-threshold reference decisions (Fig. 7: 65 fine, 67 diverged) |
| arm | **OTTER** (Fig. 7 flags, W = 12) | the quality condition; replay length S - c0 varies with S and is recorded |
| control (D4) | **Full** at S = 74, one per (input, seed) | exact positive control: must be bit-exact; otherwise the reference / determinism is broken for that input |
| determinism (D4) | OTTER at S = 74 repeated once per input (seed 0) | must equal its first run call by call |
| optional (D10) | **P-sink at S = 74** (no replay), seed 0, 10 inputs | needs a harness addition (planned switch call for `precopy_sink`); resolves Fig. 9's start-call confound: replay vs no replay at the same call |

Runs: OTTER 10 x 10 + 10 x 5 = 150, + 20 Full + 10 repeats = **180** (+ 10 with D10). Estimate [H] ~6 min per run
(model load + reference of ~200 calls + run): ~18 h on one pair, **~9 h on two pairs in parallel** (D1).

## 4. Per-run records (instrumentation, D7; record-only, flag-gated, no behavioral change)

- **Destination Sink trajectory**: per owned call, the 360 Sink block checksums and all slot positions (every layer,
  row), the same function as the reference record (`--block_ck` extended to owned calls).
- **Refresh margins**: per call, layer and row, the minimum average K / V cosine similarity and the chosen slot, in the
  reference and on the destination (new flag in `causal_model.py`, values copied after the decision; the decision is
  unchanged).
- Frames: `--dump_frames` (destination + reference), reduced on the host to per-frame metrics (section 5); frames kept
  only for the strip inputs (D8).
Regression (test_xb, test_m1_live, test_m2_live, test_m2_track_cpu, test_m3v2) after the instrumentation, before the
freeze; flags off reproduce the old records.

## 5. Metrics (k = call index after the cutover, k = 1 is B's first generated call)

- **Fidelity**: per-call PSNR and SSIM vs the reference (existing); per run the median over windows **W1 = k 1-8,
  W2 = 9-24, W3 = 25-100**, plus first call and terminal (k 91-100). LPIPS optional (D6).
- **Temporal consistency (reference-relative)**: per frame t, TE(t) = MSE((O_t - O_{t-1}) - (R_t - R_{t-1})) over
  pixels, reported as tPSNR = 10 log10(255^2 / TE). The **boundary** value uses the last frame delivered from A and
  B's first frame (reference: the same two frame indices). Per window as above. A frozen picture has a small raw
  difference but a large TE when the reference moves.
- **Sink schedule divergence**: first k at which any layer / row's slot positions differ from the reference; number of
  diverged layers by k = 100. **Sink content divergence**: first k at which any block checksum differs (expected at
  B's first refresh); descriptive.
- **Margin at a flip**: for the first schedule divergence, the reference's min similarity at that call and layer;
  margin = |sim - 0.2|.

## 6. Hypotheses

- **F13-H1 (long-term fidelity when the Sink schedule holds).** Among OTTER conditions with no schedule divergence by
  k = 100, >= 90 % have W3 median PSNR >= 40 dB. [H] yes (Fig. 7: 44-49 dB when undiverged).
- **F13-H2 (divergence mechanism).** For >= 80 % of schedule divergences, the reference's margin at the first diverged
  call and layer is below the 10th percentile of all reference margins of that input over calls 30-180. [H] yes
  (Fig. 7: a flip of a decision near 0.2).
- **F13-H3 (divergence vs refresh intensity).** Across the 10 inputs, Spearman rho between refresh intensity (Fig. 5)
  and the OTTER divergence rate (over its 15 conditions) >= 0.6. [H] yes (bfly diverged, dog did not).
- **(with D10) F13-H4 (replay at the same call).** Median W1 PSNR(OTTER) > W1 PSNR(P-sink) at S = 74 in >= 8 of 10
  inputs. [H] yes (Fig. 9: +7-8 dB in calls 1-8, confounded there).
- **Descriptive, always reported**: divergence rate per input and arm vs refresh intensity; W1-W3 PSNR / SSIM / tPSNR
  per input; boundary tPSNR; diverged vs undiverged W3; Full control and determinism outcomes.

## 7. Claim rule (written now, applied to the result; D5)

The paper sentence about output quality is chosen by this rule, over all OTTER conditions (10 inputs x 15
conditions = 150):
- **"preserves output fidelity"** only if >= 90 % of conditions have W3 median PSNR >= 40 dB **and** schedule
  divergence occurs in <= 10 %;
- otherwise **conditional**: "Sink exact at the cutover; output within X dB of uninterrupted generation in N % of
  conditions; in M % (inputs ..., refresh >= ...) the Sink schedule diverges after the cutover and W3 fidelity is
  Y dB", with the divergence mechanism from H3.
No other wording about preserved quality is used.

## 8. Validity

Per run: switch at the planned S (`switch_call_missed` false), SINKOK 0 / 360, B's calls k = 1-100 present, reference
cache for (input, seed, M, N) from the same run, no fallback. Full control: bit-exact on every scored call. A
non-deterministic repeat or a non-exact Full control marks that input **not evaluable** (excluded from H1-H3 and the
claim rule, listed). Harness defect: fix, rerun, keep both records.

## 9. Procedure

1. Instrumentation + `run_fig13.sh` + `fig13_report.py` + `plot_fig13.py`; regression ALL PASS; local dry run.
2. Freeze.
3. Testbed: `d0_remote.py pull`, preflight, `first` (dog seed 0 S = 74 OTTER) + `--sanity`, then `rest` on two pairs
   (interleaved: per pair half of the inputs).
4. Report; claim rule applied; figures.

## 10. Plot specification (Fig. 6a canvas and axes box, style font sizes, OTTER blue)

- **13a**: PSNR vs k after the cutover (log-x or the three windows marked), OTTER median line with the inter-condition
  range (P-sink dashed with D10); diverged conditions drawn separately (light) so the 32-dB-type failure is visible, not averaged.
- **13b**: W3 PSNR per input (x sorted by refresh intensity), points = conditions, diverged marked; or the
  divergence rate per input (D9).
- **13c**: frame strip around the boundary, reference vs OTTER, **non-LOVEU inputs only** (dog, plus boxing or train).
- Temporal consistency: one panel or a table in the text (D9).

## 11. Open decisions

| # | decision | recommendation |
|---|---|---|
| D1 | execution | real runs on two pairs in parallel (`--nodes`; one dry check first); no single-GPU emulation |
| D2 | inputs / seeds | the 10 inputs of section 3 x seeds 0, 1 |
| D3 | cutover calls | seed 0: S = 70-79; seed 1: S = 70, 72, 74, 76, 78 |
| D4 | arms | OTTER only (R-win dropped: W is a readiness gate, section 2), Full control, one determinism repeat per input |
| D5 | claim rule thresholds | 40 dB W3, 90 % conditions, <= 10 % divergence |
| D6 | perceptual metric | PSNR / SSIM / tPSNR; LPIPS only if the package and weights can be installed on the hosts (download needs approval) |
| D7 | instrumentation | owned-call Sink checksums + positions; refresh margins in reference and destination (record-only, flag-gated) |
| D8 | frame strips | dog + one of boxing / train (non-LOVEU) |
| D9 | panels | 13a over time, 13b per input, 13c strip; temporal consistency in a table |
| D10 | P-sink at the same S (harness addition) | yes, 10 runs: the clean replay-vs-no-replay comparison Fig. 9 could not make |
