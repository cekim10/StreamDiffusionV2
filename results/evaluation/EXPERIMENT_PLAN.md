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

## Experiment 3 Scenario B: source-egress contention (pre-registered 2026-10-13, before any server run)

Motivation (Phase 1): with one session, restoration at the final owner is bound by that owner's ingress, so reuse
cannot beat restart; reuse only removed waste and halved the source's egress. Scenario B asks whether that offload
turns into latency when the source is the shared bottleneck.

Harness: `tools/eval/restore_node.py` + `restore_orchestrate.py` (+ `run_restore_contention.sh`), network level, no GPU.
Same Sink size (1,725,236,640 B), 4 MiB fragments, MSS-capped TCP, per-flow token buckets, per-fragment SHA-256 as the
GPU harness; contents are deterministic per (session, fragment) so holders forward exactly the bytes they verified.
Validated on loopback (4 nodes, 64 MiB Sink, 100 Mbps): runs complete, all fragments verify, restart and reuse behave
as specified.

Setup: source A = elves-01; edges B, C, D = elves-02..04. N sessions; session i starts at edge [B, C, D][i mod 3] and
moves to the next edge every T_m (moves staggered by T_m * i / N). Every node's egress and ingress capped at 1 Gbps,
shared max-min fairly by all flows of all sessions (so A's egress is shared by N sessions, each edge's ingress by about
N/3). T_s = 14.05 s, rho = 2 (T_m = 7.02 s). Independent variables: N in {1, 2, 4, 8}; mobility mode {one move then
stay, continuous moves over B -> C -> D -> B ...}; policy {restart, reuse_fixed, reuse_adaptive}. 3 reps each (72 runs,
~1.7 h). Single-move runs end when every session is restored at its final edge (deadline 2 N T_s + 3 T_m); continuous
runs last 2 N T_s + 2 T_m.

Metrics: per session first restoration time (all fragments verified at the edge while it is the owner) and makespan;
coverage (share of the run during which the current owner holds the whole Sink); source bytes, total bytes, unused
bytes (delivered to an edge, never part of a restoration there, never forwarded), duplicates; source egress over time;
kernel NIC peaks per node (validation: within 1.15 x cap).

Flow-model predictions (written before the runs):
- Single move, N = 1: no difference (the edge's 1 Gbps ingress, not A, is the bottleneck, as in Phase 1).
- Single move, N >= 2: A is the bottleneck. Restart must resend what it delivered before the moves; reuse sends every
  byte from A once. Predicted makespans: restart ~ N T_s + (A's bytes delivered before the moves) / 1 Gbps, reuse ~ N T_s;
  the absolute saving is about T_m to 2 T_m (7-14 s) independent of N, so the relative saving shrinks as N grows.
- Continuous mobility: restart never restores any session when N rho > 1 (each ownership period delivers at most
  S / (N rho) < S and is then discarded); here N rho >= 2 for every N, so restart is predicted to restore 0 sessions.
  Reuse accumulates progress across edges, restores every session after about N T_s, and once all three edges hold a
  session's Sink every later move restores it immediately (coverage rises toward 1).
- reuse_adaptive vs reuse_fixed: no difference expected; with A as the bottleneck, fixed routing already sends every held
  fragment from its holder, and adaptive's only extra freedom (sending a held fragment from A instead) cannot help.

Decision criteria (median of 3 reps; fixed now):
- H3a single move: supported at N if reuse_fixed's makespan is shorter than restart's by >= 0.5 T_m (3.5 s).
- H3a continuous: supported at N if restart restores fewer than N sessions within the run in all 3 reps while
  reuse_fixed restores all N in all 3 reps.
- H3b: supported at N if reuse_adaptive's makespan is shorter than reuse_fixed's by >= 1 s (single move) or its
  coverage is higher by >= 0.05 (continuous), without being worse by the same margin at any other N.
- A run is invalid if any fragment fails verification or a NIC peak exceeds 1.15 x its cap; invalid runs are listed,
  not dropped, and the condition is re-run.

### Scenario B harness fixes before the reported run (2026-10-14; criteria unchanged)

The first server run (`restore_contention/`, 72 runs, v1) is kept but not reported. Inspecting its NIC counters showed
nodes up to ~8 % above their 1 Gbps cap at times, from three harness defects, all fixed and validated on loopback before
the v2 run (`restore_contention_v2/`):
1. Rate updates and cancels that reached a node before the flow's start command were dropped (commands run in separate
   threads); they are now kept and applied at start.
2. A cancelled flow kept sending its in-flight fragment but no longer counted in the max-min allocation; it now counts
   until its sender reports it stopped.
3. New flows started with a full token bucket (1 MiB burst); buckets now start empty.
Validation added: every node's paced payload, counted at its token bucket, must stay within 1.05 x its egress cap in
every 10 s window (1 s windows over-count by up to one 1 MiB chunk per flow). Reuse planning also no longer asks the
source to resend a fragment that is already in flight to a holder (that holder forwards it once it lands; if it is not
there in time the source sends it). Loopback check at the real fragments-per-Sink ratio (412 fragments): reuse_fixed
sends exactly 1.00 Sink per session from the source and its single-move makespan equals N T_s.
The v1 data already agreed with every prediction (single move: restart - fixed = 0.0 / 7.5 / 9.6 / 10.0 s at N = 1/2/4/8;
continuous: restart restored 0 sessions at every N, reuse_fixed all; adaptive worse than fixed at N >= 2), see
`restore_contention/criteria.md`.

## Experiment 3 Step 2: heterogeneous holder bandwidth (pre-registered 2026-10-14, before any server run)

Question: when should restoration abandon fragment reuse and retransmit from the original source? Scenario B showed
that unconditional reuse (reuse_fixed) is optimal in source bytes and never beaten by the Scenario B adaptive rule, but
every holder there had the same 1 Gbps egress as the source. If a holder is slow, retransmitting its fragments from the
(shared) source can be faster. Step 2 is limited to establishing whether that crossover exists and whether a simple
bottleneck-aware provider selection captures it without regressing where holders are fast. It decides how OTTER's third
component is described (Case 1: bottleneck-aware provider selection + progress preservation; Case 2: progress-preserving
restoration only; Case 3: drop adaptive routing).

Harness: Scenario B harness (restore_node.py, restore_orchestrate.py, run_restore_holder.sh), single move per session,
rho = 2 (T_m = 7.02 s), source A egress and every ingress 1 Gbps. New independent variable: every edge's egress cap
B_h in {62.5, 125, 250, 500, 1000} Mbps (what previous holders forward with). N in {1, 2, 4}; N = 8 is omitted because
the model below predicts no crossover there (the source is too congested for any holder to matter). Policies:
- restart, reuse_fixed, reuse_adaptive: unchanged from Scenario B (adaptive is kept as the baseline that explains H3b).
- reuse_aware (new): same holders as reuse_fixed; fragments that only the source holds are assigned to the source
  first; each held fragment then goes to the provider (newest holder of it, or the source) with the smallest
  (egress backlog over every session + bytes assigned so far + one fragment) / egress cap, ties to the holder. It never
  re-plans a session while its flows run, so a holder that goes idle early is not reused (a known limitation).
3 reps, 60 configurations, 180 runs (~2.5-3 h). Deadline per run: max(2 N T_s, 2 S / B_h) + 3 T_m.

Fluid-model predictions (tools/eval/restore_model.py, written before the runs; the same model reproduces every
Scenario B v2 single-move median within 0.3 s and the adaptive source bytes within 0.03 Sink):

```
 N   B_h |          restart      reuse_fixed   reuse_adaptive      reuse_aware   (makespan s / source Sinks per session)
 1    62 |       20.9 /1.51      119.3 /1.00       20.9 /1.48       20.9 /1.45
 1   125 |       20.9 /1.51       63.2 /1.00       20.9 /1.46       20.9 /1.40
 1   250 |       20.9 /1.51       35.1 /1.00       20.9 /1.41       20.9 /1.31
 1   500 |       20.9 /1.51       21.1 /1.00       20.9 /1.34       20.9 /1.18
 1  1000 |       20.9 /1.51       20.9 /1.00       20.9 /1.26       20.9 /1.01
 2    62 |       36.5 /1.32       92.7 /1.00       35.6 /1.28       33.8 /1.21
 2   125 |       36.5 /1.32       50.8 /1.00       35.0 /1.25       31.6 /1.12
 2   250 |       36.5 /1.32       29.9 /1.00       34.1 /1.20       28.9 /1.01
 2   500 |       36.5 /1.32       28.9 /1.00       32.9 /1.15       28.9 /1.00
 2  1000 |       36.5 /1.32       28.9 /1.00       32.2 /1.12       28.9 /1.00
 4    62 |       65.0 /1.18       83.8 /1.00       63.4 /1.15       57.2 /1.03
 4   125 |       65.0 /1.18       55.4 /1.00       61.8 /1.12       55.4 /1.00
 4   250 |       65.0 /1.18       55.4 /1.00       60.2 /1.09       55.4 /1.00
 4   500 |       65.0 /1.18       55.4 /1.00       58.5 /1.06       55.4 /1.00
 4  1000 |       65.0 /1.18       55.4 /1.00       58.0 /1.05       55.4 /1.00
```

Crossover set C (model: reuse_fixed slower than restart): (N, B_h) in {(1, 62.5), (1, 125), (1, 250), (2, 62.5),
(2, 125), (4, 62.5)}; the other 9 conditions are the no-crossover set. Regimes: holders fast enough (B_h >= 250 at
N >= 2) -> reuse_fixed = reuse_aware; holders slow (C) -> fixed loses to restart, aware beats both at N >= 2 and ties
restart at N = 1 (ingress-bound); holders and source both congested (N = 4, B_h <= 125: edges forward for more than one
session while the source is shared by four) -> aware's advantage comes from balancing the two backlogs.

Decision criteria (medians of 3 reps; fixed now):
- P0 crossover exists: in every condition of C, restart's makespan is shorter than reuse_fixed's by >= 0.5 T_m (3.5 s).
- H4a heterogeneity benefit: in every condition of C, reuse_aware's makespan <= 0.85 x reuse_fixed's (predicted ratios
  0.18-0.68).
- H4b no regression: in every no-crossover condition, reuse_aware's makespan <= 1.05 x reuse_fixed's; and in every
  condition, reuse_aware's makespan <= 1.05 x restart's.
- H4c source efficiency: in every no-crossover condition, reuse_aware's source bytes per session <= reuse_fixed's + 0.05
  Sink; in every condition, <= restart's. Source bytes per session and total bytes are reported for all policies.
- Validity: as Scenario B (every fragment verified, paced egress within 1.05 x cap over 10 s windows, NIC peaks within
  1.15 x cap); invalid runs are listed and the condition re-run.
Outcome mapping: Case 1 if P0, H4a and H4b all hold; Case 2 if H4b holds but P0 or H4a fails (no useful crossover);
Case 3 if H4b fails. H4c qualifies the claim in Case 1 (latency bought with source bytes only where reuse is slower).
