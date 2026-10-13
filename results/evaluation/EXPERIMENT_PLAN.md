# OTTER evaluation plan (OSDI) and Phase 0 audit

Written 2026-10-12 before any Phase 1 (repeated-mobility) run. Success criteria below are fixed now and are not to be
edited after results exist. Harness commit at the time of writing: see `git log` for this file.

## 1. Existing experiments and verified results

Every number below was re-read from the committed artifact named in the right column (not from notes).

| experiment | status | result | artifact |
|---|---|---|---|
| Network calibration (Phase 0) | done | single flow 9.2-9.4 Gbps; per-node ingress and egress shared at ~9.4 Gbps total; kernel-default MSS stalls, TCP_MAXSEG 1400 (effective 1388) on every socket | `network_calibration_summary.csv`, `network_calibration_notes.md` |
| Single handoff elves-01 -> elves-02 (Phase 1 v3, frozen) | done, 3 reps x 6 bandwidths | full migration first output 209.85 s @250 Mbps, 7.85 s native; OTTER-style handoff 0.74 / 0.69 s; Sink bound 57.4 / 3.09 s; rejoin 6 calls after bind at every bandwidth; checksums all OK; cross-host bit-exact | `single_handoff/summary_by_policy_bw.csv`, `single_handoff_notes.md`, Fig. 6 |
| Continuity timeline (Fig. 7) | done | GO 0.16 s, first output 0.71 s, Sink received 14.39 s, verified 14.47 s, bound 14.78 s, rejoin 18.89 s (1 Gbps rep 2) | `continuity/fig7_data.csv`, `continuity/fig7_notes.md` |
| State characterization | done, 31 runs | Immediate 2.67 MiB (0.04%), durable Sink 1.61 GiB, ephemeral 4.41 GiB, total 6.02 GiB; Sink loss diverges in 31/31 runs; ephemeral-only loss heals in 21/21 runs without a pre-migration adaptive refresh, 5/10 with one | `state_migration/prompt_sweep/summary.csv`, `notes.md`, Figs. 2-3 |
| Emulated repeated mobility (one GPU hosts B/C/D) | done, superseded | restart 23.8 s + 548 MB waste, relay 45.9 s, relay_pipe 19.3 s / 4.9 GB, split 17.7 s = oracle at unlimited ingress; at 1x shared ingress split 21.0 vs restart 23.8 vs oracle 17.8 | `state_migration/mobility_notes.md`, `ingress_notes.md` (motivation only, not evaluation evidence) |
| Physical Phase 3 harness | implemented, dry-run validated, Ts measured | Ts (transfer start -> verified) at 1 Gbps 14.05 s, 2.5 Gbps 5.71 s, 5 Gbps 2.94 s, native 2.08 s; fragmented path reproduces Phase 1 (first output 0.67 s, Sink bound 15.40 s @1 Gbps) | `tools/eval/mobility_node.py`, `mobility_orchestrate.py`; Ts runs are on elves-01 under `results/evaluation/repeated_mobility/` and NOT yet committed (push them) |

No repeated-mobility run on four physical hosts exists yet. Nothing about OTTER's routing has been measured physically.

### Sink immutability audit (correctness precondition for fragment reuse)

The Sink KV can change through exactly two code paths (`models/wan/causal_model.py`):
1. adaptive refresh (line 332-347): when `adapt_sink_thr > -1` and the cosine similarity of a new frame to the sink drops below the threshold (0.2), a recent frame is promoted into a sink slot (content change);
2. `_realign_kv_positions` (line 204, called at line 330) when the streaming caller rewinds `current_start` every `t_refresh = 50` latent frames (`streamv2v/inference.py:100,234`): positions (RoPE) change, content does not.

What the harness does:
- the source serializes the Sink once at the migration chunk M; `sink_version` = first 16 hex of the SHA-256 of that serialization; every fragment carries session_id + sink_version; a receiver drops any fragment whose version or session differs and logs `fragment_rejected_version` (`mobility_node.py:534-537`); whole-Sink digest is re-verified before bind;
- every destination runs with adaptive refresh frozen (`adapt_sink_thr = -1`, `mobility_node.py:146`) until the true Sink binds, so no destination ever creates a different Sink content before binding;
- realigns that happen while waiting are absorbed at bind by re-rotating each transferred slot by its measured position delta (`proto_handoff.py:427-448`); verified in Phase 1 v3: binds at calls 34-127, i.e. after the realigns at calls 48 and 93, all rejoin in 6-8 calls at 39-45 dB.

Measured on the evaluation workload (dog clip, k = 2): over the full 110-call window the only sink-slot events are the first fill (call 4) and realigns at calls 48, 93, 138 (`single_handoff/*/config.json: refresh_calls_baseline`); no adaptive promotion fires. So for this workload the Sink content serialized at M is the only version for the whole experiment and all fragments of it remain bindable at any later destination.

Open limitation (to state in the paper): after a destination binds and re-enables refresh, a later promotion would create a new Sink version; the harness has no version bump or re-fetch path, only rejection of mismatched fragments. With the evaluation workload this path is never exercised (no promotions); for high-motion content (bird, train) promotions occur and the fallback would have to be "serialize a new version at the current owner and route that", which is not implemented. Experiment 7 (generality) must measure, not assume, this.

## 2. Missing experiments and required implementation

| experiment | hypothesis | what exists | what must be built |
|---|---|---|---|
| E1 repeated mobility A->B->C->D, rho sweep (restart, relay, relay_pipe, direct, + reuse-fixed) | H1 | all five policies implemented in the orchestrator (`split` = reuse with fixed routing: holders forward what they hold, source sends the rest, max-min fair per-node caps); Ts measured; logging of flows, fragments, moves, p_current, per-chunk PSNR at the owner; byte classification useful / wasted-delivered / wasted-in-transit / duplicate / reused | nothing new; run shakedown then sweep |
| E2 controlled fragment availability 0/25/50/75/100 % at intermediate nodes; policies no-reuse / reuse-fixed / reuse+source-selection / oracle | H2 | reuse-fixed and no-reuse (restart, direct) exist | pre-positioning mode (deliver x % of fragments to B and C before the move, then measure completion at D); source selection by expected completion time (per-flow rate estimate from measured link capacity and current sharing); offline oracle (min-time assignment given measured capacities) |
| E3 contention: ingress bottleneck, egress bottleneck, asymmetric links, background traffic, route switching | H3 | per-node egress/ingress caps = one link rate (max-min fair); physical 9.4 Gbps shared ingress measured in Phase 0; `netcal.py` can act as background sender | per-link bandwidth matrix (A->D 250 Mbps while B->D 1 Gbps); background-traffic flows scheduled through the agents; route-switch cost instrumentation (already logged per cancel: bytes in transit lost, reconnect time; needs an explicit switch experiment) |
| E4 routing ablation | H3 | - | depends on E2/E3 outcome; build only the components that E2/E3 show matter |
| E5 end-to-end continuity across repeated handoffs vs full / cold / replay | B, C | per-chunk PSNR at the executing site is logged for every policy; rejoin events per site; full / cold / replay exist only in the single-handoff harness | add full-migration, cold-restart and replay as execution policies in the repeated-mobility harness (each move transfers everything / restarts / replays) |
| E6 overhead with no handoff | - | 1 Hz CPU/GPU/NIC sampling per node; service time per chunk | an "OTTER enabled, no migration" run (fragment tracking + background hashing active, no transfer) vs unmodified streaming; metadata size accounting (fragment table = 412 entries x ~120 B) |
| E7 sensitivity (fragment size, Sink size via k, holders, asymmetry, workloads) | - | `--frag_bytes`; `--step k` changes Sink size (k x 0.8 GiB) | sweeps only |

## 3-9. Design of Experiment 1 (the first to run)

- Hypothesis: H1. Testbed: A = elves-01, B = elves-02, C = elves-03, D = elves-04, one L40S each, GPU 0; one node process per host launched through the per-host agents; orchestrator on elves-01.
- Network: primary condition 1 Gbps per flow with per-node ingress and egress capped at 1 Gbps (max-min fair shares pushed to each sender's token bucket; the physical NIC caps at ~9.4 Gbps). Kernel NIC counters are recorded per node to show the caps on the wire. Native (unshaped) is a secondary condition for one rho only, since rho 8 at native would mean a 0.26 s mobility interval, below one chunk (0.555 s).
- Independent variables: policy in {restart, relay, relay_pipe, direct, reuse-fixed(split)}; rho in {0.5, 1, 2, 4, 8} with T_m = T_s / rho from the measured T_s = 14.05 s: 28.10, 14.05, 7.02, 3.51, 1.76 s (moves are executed at chunk boundaries; the actual move times are logged and the effective rho is reported per run).
- Controlled: same clip, prompt, seed 0, k = 2, migration at chunk 30, fragment size 4 MiB (412 fragments), 12 tail calls after rejoin at D, deadline 600 s.
- Dependent variables (per run, `summary.json`): after the final move: time to first output, Sink received, verified, bound, continuity-ready (first output on the bound Sink), rejoin (first chunk >= 35 dB); bytes: total sent, useful, wasted-delivered (to an abandoned owner, never forwarded), wasted-in-transit (cancelled mid-flow), duplicate, reused from non-source; per-link throughput, per-node ingress/egress peaks (orchestrator bookkeeping and NIC counters); number and residue of cancelled flows per move; execution interruption per move (stop -> resume); PSNR per chunk at the owner; p_current(t).
- Baseline fairness: identical transport (MSS 1400 TCP + token bucket), Sink version, fragment table, schedule generator, GPUs; policies differ only in routing decisions.
- Repetitions: shakedown 1 run per policy at rho 2 (stop and inspect); sweep 3 reps, extended to 5 if the interquartile range of continuity-ready exceeds 10 % of the median.
- Figures: E1 continuity-ready after the final move vs rho (median, p25-p75) with Direct dashed as the oracle lower bound; E2 total bytes / Sink size and wasted bytes / Sink size vs rho; E3 one fast-mobility timeline (owner, fragment availability per node, bind, rejoin) from the run's `p_current.csv` and `events.csv`.
- Cost: each run ~1.5-3 min after a one-time ~3 min node start (model load + 250-call baseline per host); shakedown 5 runs ~15 min; sweep 75 runs ~2.5 h; GPUs on all four hosts must be free for the duration.
- Risks and confounders: (i) rho 8 has only ~3 chunks per owner, so chunk-boundary quantization changes the effective rho by up to 30 %: report effective rho; (ii) rho 1 is a knife edge (the move to C comes 0.2 s before B's Sink completes): expect bimodal results across reps and report both modes; (iii) other users on elves-03/04 GPUs or NICs: `network.csv` and `host_info.json` capture utilization; abort if GPU util is non-zero before launch; (iv) token-bucket shaping is at the application layer: the NIC-counter peaks in `validation` must stay within 1.15x the emulated cap, otherwise the run is invalid; (v) the dog workload has no adaptive promotions, so the version-mismatch path is never exercised here (limitation, see audit).
- Pre-registered decision criteria for H1 (judged on the 3-rep medians at 1 Gbps):
  - supported if, for rho >= 2, restart's wasted bytes are >= 0.25 x Sink size and its continuity-ready after the final move is >= T_s + 3 s, while direct's is lower by >= T_s / 2; and for rho <= 1 restart's waste is <= 0.1 x Sink size (the regime change around rho = 1);
  - not supported if restart's waste stays below 0.1 x Sink at every rho, or if its continuity-ready is within 1 s of direct's at every rho.
- Pre-registered decision criteria for H2 from the same runs (reuse-fixed vs restart, single 1 Gbps ingress at D):
  - latency benefit supported only if reuse-fixed's continuity-ready after the final move beats restart's by >= 1 s at rho >= 2; the emulation (ingress 1x) predicted a tie, so the expected and acceptable outcome is "no latency benefit with one receive link; benefit confined to waste and traffic";
  - traffic/waste benefit supported if reuse-fixed's wasted bytes <= 0.1 x Sink and total bytes <= 0.6 x relay_pipe's at rho >= 2.
  - If neither holds, H2 is rejected for this topology and E2 is still run with pre-positioned fragments to find whether any availability level helps.

## 10. Methodology checklist (applies to every run)

Recorded per run: git commit, config (policy, bw, rho, T_m, fragment size, seed, workload, migration chunk), host assignment with hostnames and GPU names, shaping settings and NIC MSS, clock-sync offsets, start/end wall times, raw `events.csv` / `fragments.csv` / `metrics.csv` / `flows.csv` / `p_current.csv` / per-node `network.csv`, `summary.json` with the validation block (four distinct hosts, ownership sequence, single owner, all fragments verified, version consistency, final digest match, ingress within physical and emulated caps on the wire, continuity comparable to Phase 1, stop reason). Failed or timed-out runs are kept and listed in the aggregate with their failure flags, never dropped.

## 11. Order

Phase 0 (this document) -> Phase 1 shakedown at rho 2, one run per policy, inspect the OTTER-style trace (owner, % held per node, active flows, next decision at every move) -> Phase 1 sweep -> Phase 2 pre-positioned reuse (build pre-positioning + source selection + offline oracle) -> Phase 3 contention (per-link matrix, background flows, route switch) -> design the routing rule from Phases 2-3 -> Phase 4 end-to-end with full / cold / replay in the repeated-mobility harness and overhead -> Phase 5 sensitivity.

## 12. Deliverables after each phase

Research summary, raw locations, figures, unexpected observations, negative results, remaining uncertainties, next experiments: written to `results/evaluation/<experiment>_notes.md` and summarized to the user before the next phase starts.
