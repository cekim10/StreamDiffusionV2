# Existing results inventory (audit, 2026-10-16)

Every row was re-read from the committed artifact named in the "data" column. "Level" says what was physically
executed: **GPU** = StreamDiffusionV2 generation on L40S (elves-01..04, GPU 0); **net** = network-level restoration
harness (`tools/eval/restore_node.py` / `restore_orchestrate.py`: real TCP transfers of real-size Sink fragments with
SHA-256 verification between the four physical hosts, no GPU, no binding, no PSNR); **sim** = emulation or fluid model
(never plotted as data). Hypothesis outcomes are copied verbatim from the pre-registered criteria files and are not
redefined here.

## Metric vocabulary (not interchangeable)

| metric | definition | measured where |
|---|---|---|
| first output | trigger -> first chunk generated at the destination | GPU (single handoff, repeated mobility) |
| Sink verified ("sink_ready") | all Sink fragments received and checksummed at the destination | GPU |
| Sink bound ("continuity-ready") | first output generated *with* the transferred Sink bound | GPU |
| rejoin | first chunk >= 35 dB PSNR to the uninterrupted same-seed run after bind | GPU |
| network fragment completion (T_r) | move -> all fragments verified at the owner (no GPU binding) | net |
| makespan | last T_r over sessions / destinations | net |

Network fragment completion is a lower bound on Sink bound: on GPU, bind adds ~0.3-0.4 s after verification at 1 Gbps
(continuity notes: verified 14.47 s, bound 14.78 s) and rejoin adds ~6 calls (~4 s) after bind.

## Inventory

| # | experiment | level | runs | data | notes | headline (measured) | pre-registered outcome | figures |
|---|---|---|---|---|---|---|---|---|
| 1 | State characterization + component ablation (31 runs: clips x seeds x prompts) | GPU (single GPU, bit-exact reference) | 31 + mechanism runs | `results/state_migration/prompt_sweep/summary.csv`, `gen/`, `mechanism/` | `state_migration/ablation_notes.md`, `prompt_sweep/` notes, `figures/background/CAPTIONS.md` | immediate 2.67 MiB (0.043 %), durable Sink 1.61 GiB, ephemeral 4.41 GiB, total 6.02 GiB; Sink loss diverges 31/31; ephemeral-only loss heals 21/21 without a refresh before M, 5/10 with one | - | Fig. 2a/2b/3 (existing), F1c (new) |
| 2 | Late binding / rejoin vs delay | GPU (single GPU) | mechanism sweep | `results/state_migration/mechanism/ablation_raw.csv` | `mechanism_notes.md` | rejoin ~6 calls after bind regardless of delay | - | Fig. 4a/4b (existing) |
| 3 | Emulated repeated mobility (one GPU hosts B/C/D) | sim (emulation) | - | `results/state_migration/mobility/*.json` | `mobility_notes.md`, `ingress_notes.md` | superseded by #6 | - | Fig. 5a/5b (background, **emulated: motivation only, must not be cited as evaluation**) |
| 4 | Network calibration | net | - | `network_calibration_summary.csv` | `network_calibration_notes.md` | 9.2-9.4 Gbps per flow; TCP_MAXSEG 1400 required | - | - |
| 5 | Single handoff A->B, 4 policies x 6 bandwidths x 3 reps | **GPU** | 72 | `single_handoff/summary_by_policy_bw.csv`, `summary_runs.csv`, per-run `metrics.csv` | `single_handoff_notes.md` | OTTER first output 0.69-0.74 s at every bandwidth; full migration 7.85-209.85 s; Sink bound 3.09 s native / 15.33 s @1G / 57.41 s @250M; replay 5.77-7.13 s, cold 1.07 s (diverged, 19-22 dB); destination peak allocated 25.8-25.9 GiB for every policy (26375-26481 MB) | - | Fig. 6 (existing), F2a, F2b, F8a, F9b |
| 6 | Continuity timeline @1 Gbps (one rep per policy) | **GPU** | 4 | `continuity/fig7_data.csv` | `continuity/fig7_notes.md` | first output 0.71 s, Sink verified 14.39 s, bound 14.78 s, rejoin >= 35 dB at ~18.9 s | - | Fig. 7 (existing), F3a |
| 7 | Phase 1 repeated mobility A->B->C->D, 5 policies x rho {0.5..8} x 3 | **GPU** | 75 (+5 shakedown) | `repeated_mobility/figures/mobility_table.csv`, run dirs | `repeated_mobility_notes.md` | all non-oracle policies 14.8-15.4 s after the final move (ingress-bound); restart discards up to 2.0 Sinks; reuse 0.03-0.07; oracle 0.7-11.4 s | H1: progress loss in bytes yes, latency clause ill-posed; H2 latency rejected, traffic supported | figE1-E3 (existing), F4a, F4b |
| 8 | Scenario B v1 (source contention) | net | 72 | `restore_contention/` | criteria.md | superseded (harness cap overshoot) | - | not used |
| 9 | Scenario B v2: N sessions share the source, one move / continuous | net | 72 | `restore_contention_v2/` | `restore_contention_v2_notes.md` | one move: reuse beats restart by 7.6/9.7/10.2 s at N=2/4/8; continuous: restart restored 0 sessions in every run (within the run length), reuse all | H3a supported (both clauses); **H3b rejected** | figE6/E7/E7b, F4c, F9a |
| 10 | Step 2: holder egress 62.5-1000 Mbps | net | 180 | `restore_holder/` | `restore_holder_notes.md` | crossover exists; aware <= 0.85 x fixed in every crossover condition | P0, H4a, H4b supported; **H4c failed at (N=1, 500)** | figE8/E9 |
| 11 | Step 1: ingress-aware correction (`reuse_aware_in`) | net | 45 | `restore_holder_h4c/` | `restore_holder_h4c_notes.md` | (1,500) retransmission 0.17 -> 0.00 Sink, no latency change anywhere | all pass conditions met; H4a-c hold with the corrected rule | figE8/E9 |
| 12 | Pre-positioning pilot (A-pilot) | net | 12 | `restore_prepos_pilot/` | `restore_prepos_pilot_notes.md` | correct top-1 14.0 -> 4.0 s; incorrect 14.0 s with 0.72 Sink forwarded by a never-owner holder; source 1.00 Sink always | go/no-go GO | F7a |
| 13 | A3: pre-positioning under contention | net | 31 (30 valid + 1 re-run) | `restore_prepos_a3/` | `restore_prepos_a3_notes.md` | wrong placement 55.4 -> 27.8 s at N=4; 0 at N=1; fixed forwarding from a slow holder +24.5 s worse | **H5d FAIL** (+3.3 vs 3.5 s); H5d idle PASS; H5e: 3 of 4 clauses PASS, slow-holder aware **FAIL** by 0.2 s | - |
| 14 | Holder-bandwidth diagnostic (not pre-registered) | net | 60 | `restore_holder_diag/` | `restore_holder_diag_notes.md` | fixed forwarding of a wrong placement pays only >= 250 Mbps (analytical crossover); aware never worse than none | (diagnostic) | F7b |
| 15 | B-pilot: dissemination, uniform 1 Gbps | net | 5 | `restore_dissem_pilot/` | `restore_dissem_pilot_notes.md` | star 41.7, line 14.1, tree 27.9, multipath 14.0, aware 14.0 s | go/no-go GO | F5a |
| 16 | B heterogeneous subset | net | 45 | `restore_dissem_hetero/` | `restore_dissem_hetero_notes.md` | aware / best fixed = 1.00 / 0.91 / 1.01 / 1.00 | H6a-e supported; H6f supported **on the tested subset only** (full grid open) | figE10, F5a, D1 |
| 17 | E-pilot v1 | net | 21 | `restore_epilot/` | `restore_epilot_notes.md` | collapse: dyn 14.0 vs at-moves 53.3 s; one oscillation, premature re-plans | pilot (no criteria) | - |
| 18 | E-pilot v2 (hysteresis fixed) | net | 21 | `restore_epilot_v2/` | `restore_epilot_v2_notes.md` | 0 premature, 0 oscillation; control 0 re-plans; share change 41.6 -> 37.7 s | pilot (no criteria) | F6b |
| 19 | Full E: 7 policies x 4 conditions x 3 | net | 84 | `restore_fulle/` | `restore_fulle_notes.md` | dyn on the Pareto frontier in all 4 conditions; revisit 7.0 vs 14.0 s | **H8a NOT SUPPORTED; H8b SUPPORTED; H8c NOT SUPPORTED AS WRITTEN** | F4d, F5b, F5c, F6a |

## Existing plots: measured or not

| plot | basis |
|---|---|
| `state_migration/figures/background/fig2a_*`, `fig2b_state_ablation`, `fig3_state_loss_frames`, `fig4a/4b` | measured (single GPU) |
| `state_migration/figures/background/fig5a_mobility_slow`, `fig5b_mobility_fast`, `eval/fig_mobility_policies` | **emulated mobility harness (one GPU hosting B/C/D)**: motivation only; replaced by F4a/F4b (physical) |
| `single_handoff/fig6_handoff_latency`, `continuity/fig7_continuity_timeline` | measured (GPU) |
| `repeated_mobility/figures/figE1-E3` | measured (GPU) |
| `restore_*/figures/*` (figE6-E10) | measured (net) |
| `restore_model.py` tables in TOPOLOGY_PLAN.md | **model predictions**, written before each run; never plotted as data |
| `results/evaluation/paper_figures/eval/*` (this audit) | measured only; see each `.meta.json` |
| `results/evaluation/paper_figures/design/D1_transfer_graphs` | design diagram; panel 5 shows measured fragment counts per link, not timing |

## Gaps found by the audit

1. No GPU run exercises M2's bottleneck-aware assignment, M3's placement or event-driven re-planning: the GPU harness
   (`mobility_orchestrate.py`) implements restart / relay / relay_pipe / split (= wavefront with fixed routing) /
   direct (oracle). Every M3 result is network-level.
2. Per-fragment receive timestamps at non-orchestrator hosts (`node_{B,C,D}/fragments.csv`) were not copied back for the
   network-level experiments; flows.csv and events.csv are. Provider-by-provider progress curves need them.
3. Budget x lookahead (A1) and calibration (A2) sweeps were not run; the predictor is synthetic (seeded draws).
4. No GPU multi-session run; no GPU utilization trace in the evaluation runs beyond 1 Hz sampling in network.csv.
5. Single representative rep for the continuity timeline (F3a); medians with p25-p75 exist per bandwidth (F2b).
6. No external baseline has been run.
