# Experiment D scenario readiness matrix (2026-10-16, before the focused GPU correctness tests)

Status legend: **dry** = loopback protocol test (fake runtime) passes; **GPU** = testbed correctness test passes;
**pending** = testbed test written, not run yet. Run counts from preregistration section 9 (3 reps).

| scenario | policies (prereg) | implemented | missing | instrumentation | correctness status | runs | blockers |
|---|---|---|---|---|---|---|---|
| A single A -> B, 1 Gbps + native | Full migration, Cold restart, M1 only, OTTER event-driven; OTTER cold destination; external C/R | all in-repo policies (`full`, `cold`, `restart`, `reuse_dyn`), `--cold_dest`, `--bw 0` | external C/R | TTFO, bind, rejoin (s, calls), per-chunk PSNR/SSIM, decode, bytes, GPU peak memory | D0 GPU: `reuse_dyn` 1 Gbps; dry: all; GPU pending: full, cold, cold dest, native | 30 in-repo (+24 external) | external C/R blocked (no CRIU / cuda-checkpoint / sudo) |
| A generalization | OTTER event-driven, Full migration on bird, boxing x seeds 0-1, 1 Gbps | via `--node_extra "--video_path examples/<clip>.mp4 --prompt_file_path examples/<clip>_prompt.txt --seed <s>"` | - | same | not tested on GPU | 24 | none known; clips and prompts present; reference per clip/seed computed at node start |
| B repeated A -> B -> C -> D, rho 2 and 4 | Full migration, Cold restart, M1 only, M1 + M2, OTTER at moves, OTTER event-driven | all | - | + B_pre/B_post/B_source, discarded, retained, reused, per-move timing, state bytes | D0 GPU: 4 fast policies at rho 2; dry: all; GPU pending: full, cold (rho 2) | 36 | none |
| C correct placement (top-1 = B) | M1 + M2 (no placement), M1 + M2 + top-1, Full OTTER, oracle | `split --prepos none`, `split --prepos top1`, `reuse_dyn --prepos top1`, `reuse_dyn --prepos oracle` | - | x verified at the move, B_pre, B_post, B_fwd | D0 GPU: Full OTTER; dry: all; GPU pending: split variants, oracle | 12 | none |
| D incorrect placement (true = C) | as C | as C | - | as C | D0 GPU: Full OTTER (G5 observation, `g5_shakedown_observation.md`); GPU pending: split variants | 12 | none |
| E hybrid: 1 GPU session + 3 network sessions | M1 only, M1 + M2, OTTER event-driven | `--hybrid_net 3` with `restart`, `split`, `reuse_dyn` | - | GPU session as B; network sessions' completion times separately; combined A payload | dry: all three; GPU pending | 9 | none |
| F degradation (C egress -> 62.5 Mbps at D 50 %) | OTTER event-driven, OTTER at moves (primary); M1 + M2, M1 only (secondary) | all (`--cap_events`) | - | re-plans with detection / transition / drained bytes / duplicates | D0 GPU: both primary; dry: all | 12 | none |
| G revisit A -> B -> C -> D -> B, rho 2 | M1 only, M1 + M2, OTTER at moves, OTTER event-driven | all (`--path A,B,C,D,B`) | - | `revisit` block (held on return, re-received), bind at revisited B | dry: all four; GPU pending | 12 | none |
| G9 steady state | OTTER enabled, no migration vs unmodified generation; peak memory across policies | peak memory per node per run (new) | **steady-state measurement mode** (200 chunks, unmodified vs OTTER-enabled, 3 reps) | - | not implemented | 6 | to implement and test before the sweep |

In-repo total without G9 and external C/R: 147 runs; with G9: 153.

## Can every frozen criterion be measured without inferring missing values?

| criterion | needed measurement | recorded where | status |
|---|---|---|---|
| G1 TTFO (OTTER <= 1.0 s at 1 Gbps and native; <= 0.1 x Full migration at 1 Gbps) | trigger -> first chunk at the new owner, both policies, both bandwidths | `latency_after_final_move_s.first_output`, `per_move[0].first_output_s` | measurable; native and Full pending GPU test |
| G2 rejoin (<= 6.0 s wall clock and <= 8 calls) | first bound chunk, first >= 35 dB chunk, calls | `final.first_bound_output_rel_s`, `final.rejoin_rel_s`, `continuity.rejoin_calls_after_bind` | measurable (D0 GPU) |
| G3 (a) source bytes, (b) discarded bytes, (c) bind-ready | per-session source bytes; bytes delivered to an owner that neither bound nor forwarded; bind-ready | `d0.source_bytes_total_sinks`, `bytes.wasted_delivered`, `latency_after_final_move_s.continuity_ready` | measurable (D0 GPU); descriptive retained/reused present |
| G4 bind-ready vs no placement - 0.5 x T_s | x verified at the destination at the trigger; both runs | `d0.x_verified_at_move`, `continuity_ready` | measurable; T_s = 14.05 s (Phase 1) |
| G5 (a)-(d) | bind-ready; B_pre, B_post, B_fwd from `recv` rows with sender and checksum | d0 block; orchestrator `fragments.csv` (every receipt: src, ok, dup) | measurable; (d) "not evaluable" rule applies only if receipts are missing |
| G6 GPU session bind-ready (M1 + M2, OTTER event-driven vs M1 only - 3.5 s) | GPU session only | hybrid run `continuity_ready` | measurable; GPU pending |
| G7 bind-ready ratio, re-plans <= 2, duplicates 0; no-change B and G: 0 re-plans, within 1.0 s | re-plan records, duplicates, bind-ready | `d0.replans`, `bytes.duplicate`, node `fragments.csv` | measurable (D0 GPU for F and B); G pending |
| G8 bind-ready at the revisited B <= 0.6 x M1 only | bind-ready of the final ownership | `latency_after_final_move_s.continuity_ready` (final ownership only), `revisit` | measurable; GPU pending |
| G9 steady-state chunk time within 2 %; peak memory within 1 % | steady-state mode; peak `memory_allocated` per policy | peak memory: `gpu_peak_mem_mb`; steady state: **missing** | peak memory measurable; steady-state clause not measurable yet |
| Run validity | fragments verified, digest, NIC <= 1.15 x cap, paced egress <= 1.05 x cap / 10 s, four hosts one commit, GPU 0 idle, reference, no version events | `validation` (`paced_egress_10s_within_cap`, `gpu0_idle_before_run`, `nodes_same_commit` added) | measurable; Full migration's paced egress is one token bucket at the cap (NIC counters reported) |

Descriptive metrics (decode intervals per chunk, chunk intervals, throughput over 60 s, coverage, quality trajectory)
are computable from `metrics.csv`. External C/R: not measurable on this testbed (blocked).

## Remaining blockers before the full Experiment D sweep

1. Focused GPU correctness tests of the new capabilities (`tools/eval/run_expD_correctness.sh`) and the D0 shakedown
   re-run on this commit: pending on the testbed.
2. G9 steady-state measurement mode: not implemented.
3. G1-G9 aggregation script (reads the run summaries, applies the frozen criteria, reports medians over valid reps and
   invalid runs): not written; should be written and dry-run before the sweep so no criterion is computed ad hoc.
4. Sweep driver (the matrix above, GPU 0 idle gate, skip completed runs, invalid-run re-runs): not written (by design
   until approval).
5. External C/R: blocked (administrators: CRIU >= 4.0 with the CUDA plugin, capabilities; driver pairs 01/02 or 03/04).
6. Known G5 observation (`g5_shakedown_observation.md`): preserved; no change.
